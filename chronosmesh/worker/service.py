"""Queue worker: SQS -> reconstruction engines -> DynamoDB / S3.

Delivery semantics: **at-least-once with idempotent processing**.

* every message is written to the durable segment log *before* it is acknowledged;
* a message is deleted only after its events are in the engine, so a crash redelivers it;
* redelivered messages are recognised by ``(stream_id, seq)`` and skipped, and redelivered *events*
  are recognised by ``event_id`` and counted as duplicates;
* after a restart the worker rebuilds a stream's state from its segments.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from chronosmesh.config import Settings
from chronosmesh.evaluation import DeliveryMeta, EngineRouter, score_trial, summarize
from chronosmesh.evaluation.runner import extract_samples
from chronosmesh.events.event import Event
from chronosmesh.experiments import fail_experiment, finish_experiment
from chronosmesh.observability import metrics as m
from chronosmesh.persistence.base import Repository
from chronosmesh.reconstruction import ReconstructionEngine
from chronosmesh.simulator import ExperimentConfig
from chronosmesh.transport.sqs import QueueMessage, SqsTransport
from chronosmesh.utils import iso_now, now_ms

logger = logging.getLogger("chronosmesh.worker")

SNAPSHOT_EVERY_EVENTS = 500
SNAPSHOT_EVERY_SECONDS = 5.0
IDLE_SNAPSHOT_AFTER_SECONDS = 1.0     # an idle stream with unpublished changes is snapshotted this soon
DIRTY_POLL_SECONDS = 2                # long-poll no longer than this while there is something to publish


@dataclass
class StreamState:
    stream_id: str
    kind: str                                  # live | experiment
    router: EngineRouter = field(default_factory=EngineRouter)
    seen: Set[int] = field(default_factory=set)
    total_messages: Optional[int] = None
    events: List[Event] = field(default_factory=list)       # kept for experiment scoring
    since_snapshot: int = 0
    last_snapshot: float = field(default_factory=time.time)
    finalized: bool = False
    started_at: float = field(default_factory=time.time)
    busy_seconds: float = 0.0                  # time spent reconstructing (excludes queue wait)


class Worker:
    def __init__(self, settings: Settings, repo: Repository, transport: SqsTransport, *,
                 publisher=None, clock=time.time) -> None:
        self.settings = settings
        self.repo = repo
        self.transport = transport
        self.publisher = publisher
        self.clock = clock
        self.streams: Dict[str, StreamState] = {}
        self._stop = threading.Event()
        self.stats = {"messages": 0, "events": 0, "duplicate_events": 0, "errors": 0, "duplicate_messages": 0}
        self._last_publish = 0.0
        self._published: Dict[str, int] = {}
        self._oldest_age = 0.0

    # ── lifecycle ────────────────────────────────────────────────────────────
    def stop(self) -> None:
        self._stop.set()

    def run_forever(self, wait_seconds: int = 20) -> None:
        logger.info("worker started (queue=%s)", self.transport.queue_url)
        while not self._stop.is_set():
            self.poll_once(wait_seconds)
        self.flush_all()
        logger.info("worker stopped cleanly")

    def _dirty_live_streams(self) -> List[StreamState]:
        return [s for s in self.streams.values() if s.kind == "live" and s.since_snapshot > 0]

    def _snapshot_idle(self) -> None:
        """Publish graph/anomaly snapshots for live streams that have unpublished changes.

        Without this a small batch (fewer than ``SNAPSHOT_EVERY_EVENTS`` events and no follow-up message)
        would never become visible through the API.
        """
        now = time.time()
        for st in self._dirty_live_streams():
            if now - st.last_snapshot >= IDLE_SNAPSHOT_AFTER_SECONDS:
                try:
                    self.snapshot(st)
                except Exception as exc:
                    m.record_error("snapshot")
                    logger.warning("snapshot of %s failed: %s", st.stream_id, exc)

    def poll_once(self, wait_seconds: int = 20) -> int:
        if self._dirty_live_streams():
            wait_seconds = min(wait_seconds, DIRTY_POLL_SECONDS)     # come back soon to publish what we have
        try:
            messages = self.transport.receive(wait_seconds=wait_seconds)
        except Exception as exc:
            logger.error("receive failed: %s", exc)
            m.record_error("receive")
            time.sleep(min(5, max(1, wait_seconds)))
            return 0
        handled = 0
        for msg in messages:
            self._observe_age(msg)
            try:
                if self.handle(msg):
                    self.transport.delete(msg)
                    handled += 1
            except Exception as exc:        # leave the message: SQS redelivers, then dead-letters it
                self.stats["errors"] += 1
                m.record_error("handle")
                logger.exception("message failed (receive_count=%s): %s", msg.receive_count, exc)
        self._snapshot_idle()
        m.WORKER_HEARTBEAT.set(self.clock())
        self._maybe_publish_metrics()
        return handled

    # ── message handling ─────────────────────────────────────────────────────
    def handle(self, msg: QueueMessage) -> bool:
        """Process one message. Returns True when it may be deleted."""
        body = msg.body
        mtype = body.get("type")
        if mtype not in ("events", "end"):
            logger.error("unrecognised message type %r -> left for redrive to the DLQ", mtype)
            m.record_error("invalid_message")
            return False
        stream = self._stream(body["stream_id"], body.get("kind", "live"))
        self.stats["messages"] += 1
        if mtype == "end":
            stream.total_messages = int(body["total_messages"])
            self.repo.put_blob(stream.stream_id, "end", {"total_messages": stream.total_messages})
        else:
            self._handle_events(stream, body)
        self._after_message(stream)
        return True

    def _handle_events(self, stream: StreamState, body: Dict[str, Any]) -> None:
        seq = int(body["seq"])
        if seq in stream.seen:
            self.stats["duplicate_messages"] += 1
            return
        raw = body["events"]
        for e in raw:
            if stream.kind == "live":
                e.setdefault("execution_id", stream.stream_id)
        self.repo.put_segment(stream.stream_id, seq, raw)              # durable BEFORE ack
        self._ingest(stream, [Event.from_dict(e) for e in raw])
        stream.seen.add(seq)

    def _ingest(self, stream: StreamState, events: List[Event]) -> None:
        t0 = time.perf_counter()
        for ev in events:
            stream.router.ingest(ev)
            m.record_event_received(ev.service_id, ev.metadata.region)
            self.stats["events"] += 1
            if stream.kind == "experiment":
                stream.events.append(ev)
        stream.since_snapshot += len(events)
        dups = stream.router.duplicates()
        if dups > self.stats["duplicate_events"]:
            m.record_duplicate(dups - self.stats["duplicate_events"])
            self.stats["duplicate_events"] = dups
        m.EVENTS_PROCESSED.labels(service_id="all").inc(len(events))
        m.UNRESOLVED_DEPENDENCIES.set(self._unresolved())
        stream.busy_seconds += time.perf_counter() - t0

    def _unresolved(self) -> int:
        return sum(s.router.unresolved_links() for s in self.streams.values())

    def _after_message(self, stream: StreamState) -> None:
        if stream.kind == "experiment":
            self._maybe_finalize(stream)
            self._progress(stream)
        else:
            if (stream.since_snapshot >= SNAPSHOT_EVERY_EVENTS
                    or time.time() - stream.last_snapshot >= SNAPSHOT_EVERY_SECONDS):
                self.snapshot(stream)

    # ── state recovery ───────────────────────────────────────────────────────
    def _stream(self, stream_id: str, kind: str) -> StreamState:
        st = self.streams.get(stream_id)
        if st is not None:
            return st
        st = StreamState(stream_id, kind)
        self.streams[stream_id] = st
        seqs = self.repo.list_segments(stream_id)
        if seqs:
            logger.info("recovering stream %s from %d durable segment(s)", stream_id, len(seqs))
            for seq in seqs:
                self._ingest(st, [Event.from_dict(e) for e in self.repo.get_segment(stream_id, seq)])
                st.seen.add(seq)
            end = self.repo.get_blob(stream_id, "end")
            if end:
                st.total_messages = int(end["total_messages"])
        return st

    # ── persistence of derived state ─────────────────────────────────────────
    def snapshot(self, stream: StreamState) -> None:
        stream.since_snapshot = 0
        stream.last_snapshot = time.time()
        engine = next(iter(stream.router.engines.values()), None)
        if engine is None:
            return
        res = engine.result()
        m.observe_reconstruction(engine.last_rebuild_seconds, res)
        self.repo.put_graph(stream.stream_id, engine.snapshot(max_nodes=2000))
        self.repo.put_anomalies(stream.stream_id, [a.to_dict() for a in engine.anomalies(limit=2000)])
        self.repo.update_execution(stream.stream_id, stats=engine.stats(), anomalies=engine.anomaly_summary(),
                                   status="streaming", updated_at=iso_now(), updated_at_ms=now_ms())

    def flush_all(self) -> None:
        for st in list(self.streams.values()):
            if st.kind == "live" and st.since_snapshot:
                try:
                    self.snapshot(st)
                except Exception as exc:
                    logger.warning("final snapshot failed for %s: %s", st.stream_id, exc)

    def _progress(self, stream: StreamState) -> None:
        if stream.total_messages:
            self.repo.update_execution(stream.stream_id, status="streaming",
                                       progress=round(min(0.95, 0.5 + 0.45 * len(stream.seen) / stream.total_messages), 3),
                                       message=f"reconstructing: {len(stream.seen)}/{stream.total_messages} messages")

    # ── experiment finalisation ──────────────────────────────────────────────
    def _maybe_finalize(self, stream: StreamState) -> None:
        if stream.finalized or stream.total_messages is None or len(stream.seen) < stream.total_messages:
            return
        stream.finalized = True
        t0 = time.perf_counter()
        try:
            rec = self.repo.get_execution(stream.stream_id) or {}
            cfg = ExperimentConfig.from_dict(rec["config"]).validate()
            gt = self._load_ground_truth(stream.stream_id)
            meta = DeliveryMeta(**self.repo.get_blob(stream.stream_id, "delivery_meta"))
            for eng in stream.router.engines.values():
                eng.result()
            elapsed = stream.busy_seconds + (time.perf_counter() - t0)   # compute time, not queue wait
            streamed = {"router": stream.router, "recoveries": 0, "redelivered": 0,
                        "duplicates_suppressed": stream.router.duplicates()}
            seed = int(self.repo.get_blob(stream.stream_id, "seed") or cfg.seed)
            run = score_trial(cfg, seed, gt, meta, stream.events, stream.router,
                              elapsed=elapsed, cpu=elapsed, streamed=streamed)
            result = {"config": cfg.to_dict(), "runs": [run], "summary": summarize([run]), "transport": "sqs"}
            samples = extract_samples(gt, stream.events, stream.router, self.settings.sample_executions_kept)
            finish_experiment(self.repo, self.settings, stream.stream_id, result, samples, started_at=stream.started_at)
            logger.info("experiment %s finalised", stream.stream_id)
        except Exception as exc:
            logger.exception("finalising %s failed", stream.stream_id)
            fail_experiment(self.repo, stream.stream_id, f"{type(exc).__name__}: {exc}")
            m.record_error("finalize")
        finally:
            self.streams.pop(stream.stream_id, None)       # free memory

    def _load_ground_truth(self, stream_id: str):
        from chronosmesh.simulator.workload import GroundTruth

        events = [Event.from_dict(d) for d in self.repo.get_blob(stream_id, "ground_truth") or []]
        executions: Dict[str, List[Event]] = {}
        for e in events:
            executions.setdefault(e.effective_execution_id, []).append(e)
        true_time = {e.event_id: e.timestamp_ms for e in events}
        return GroundTruth(events, executions, true_time, sorted({e.service_id for e in events}), {})

    # ── metrics ──────────────────────────────────────────────────────────────
    def _observe_age(self, msg: QueueMessage) -> None:
        if msg.sent_timestamp_ms:
            age = max(0.0, self.clock() - msg.sent_timestamp_ms / 1000.0)
            self._oldest_age = age
            m.QUEUE_OLDEST_MESSAGE_AGE.set(age)

    def _maybe_publish_metrics(self) -> None:
        now = time.time()
        if now - self._last_publish < 30:
            return
        self._last_publish = now
        try:
            depth = self.transport.depth()
            m.QUEUE_DEPTH.set(depth["visible"])
            if depth["visible"] == 0 and depth["in_flight"] == 0:
                m.QUEUE_OLDEST_MESSAGE_AGE.set(0)
                self._oldest_age = 0.0
        except Exception as exc:
            depth = {"visible": None}
            logger.debug("depth lookup failed: %s", exc)
        if self.publisher is not None:
            def delta(name: str, key: str) -> int:
                """Per-interval counts (CloudWatch Sum), not ever-growing totals."""
                d = self.stats[key] - self._published.get(name, 0)
                self._published[name] = self.stats[key]
                return d

            self.publisher.put({
                "EventsProcessed": delta("EventsProcessed", "events"),
                "DuplicateEvents": delta("DuplicateEvents", "duplicate_events"),
                "ProcessingErrors": delta("ProcessingErrors", "errors"),
                "QueueDepth": depth.get("visible"),
                "QueueOldestMessageAge": self._oldest_age,
                "WorkerHeartbeat": 1,
                "UnresolvedDependencies": self._unresolved(),
            })
