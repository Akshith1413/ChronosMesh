"""Execution & experiment orchestration for the ChronosMesh API.

Responsibilities
----------------
* **Ownership / authorization** -- a user can only see their own executions; admins see all.
  Someone else's execution is reported as *not found* (404), never 403, so existence is not leaked.
* **Live executions** -- events are ingested either inline (in-process engine) or through SQS
  (worker consumes, persists, and snapshots; the API then serves the persisted snapshot).
* **Experiments** -- configured, started (in-process thread, or published to SQS for the worker),
  and polled. Results are persisted so any API replica can serve them.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional, Tuple

from chronosmesh.config import Settings, get_settings
from chronosmesh.evaluation import DeliveryMeta
from chronosmesh.events.event import Event
from chronosmesh.experiments import (
    fail_experiment,
    new_record,
    run_experiment_direct,
)
from chronosmesh.observability import metrics as m
from chronosmesh.observability.cloudwatch import CloudWatchPublisher
from chronosmesh.persistence import create_repository
from chronosmesh.persistence.base import Repository
from chronosmesh.reconstruction import CapacityError, ReconstructionEngine
from chronosmesh.simulator import ExperimentConfig, generate_workload, inject_faults
from chronosmesh.utils import iso_now, now_ms, to_jsonable

logger = logging.getLogger("chronosmesh.executions")

MAX_INGEST_BATCH = 1000
MAX_LOAD_INTO_EXPLORER = 400
ENGINE_CACHE_SIZE = 64


class ServiceError(Exception):
    """Domain error carrying the HTTP status the router should return."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _is_admin(user: Dict[str, Any]) -> bool:
    return str(user.get("role", "")).lower() == "admin"


class ExecutionService:
    def __init__(self, settings: Optional[Settings] = None, repo: Optional[Repository] = None,
                 transport=None, workers: int = 1) -> None:
        self.settings = settings or get_settings()
        self.repo: Repository = repo or create_repository(self.settings)
        self.transport = transport
        if self.transport is None and self.settings.sqs_events_queue_url:
            from chronosmesh.transport.sqs import SqsTransport

            self.transport = SqsTransport(self.settings.sqs_events_queue_url, self.settings.aws_region)
        self._engines: "OrderedDict[str, ReconstructionEngine]" = OrderedDict()
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="experiment")
        self._last_persist: Dict[str, float] = {}
        self._cw: Optional[CloudWatchPublisher] = None
        self._queue_age_cache: Tuple[float, Optional[float]] = (0.0, None)
        self._worker_cache: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)

    # ── access control ───────────────────────────────────────────────────────
    def get_record(self, user: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        rec = self.repo.get_execution(execution_id)
        if rec is None or (not _is_admin(user) and rec.get("owner") != user["username"]):
            raise ServiceError(404, f"Execution '{execution_id}' not found")
        return to_jsonable(rec)

    def list_records(self, user: Dict[str, Any], *, kind: Optional[str] = None, limit: int = 50,
                     parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        owner = None if _is_admin(user) else user["username"]
        rows = self.repo.list_executions(owner, limit=limit * 3 if kind else limit, parent_id=parent_id)
        if kind:
            rows = [r for r in rows if r.get("kind") == kind]
        return to_jsonable(rows[:limit])

    # ── engine cache ─────────────────────────────────────────────────────────
    def _remember(self, engine: ReconstructionEngine) -> None:
        with self._lock:
            self._engines[engine.execution_id] = engine
            self._engines.move_to_end(engine.execution_id)
            while len(self._engines) > ENGINE_CACHE_SIZE:
                self._engines.popitem(last=False)

    def _cached(self, execution_id: str) -> Optional[ReconstructionEngine]:
        with self._lock:
            eng = self._engines.get(execution_id)
            if eng:
                self._engines.move_to_end(execution_id)
            return eng

    def _new_engine(self, execution_id: str) -> ReconstructionEngine:
        return ReconstructionEngine(execution_id, on_rebuild=m.observe_reconstruction,
                                    max_events=self.settings.max_execution_events)

    def _engine_from_store(self, execution_id: str) -> Optional[ReconstructionEngine]:
        """Rebuild an engine from persisted events (after eviction / on another replica)."""
        raw = self.repo.get_events(execution_id) or self.repo.get_blob(execution_id, "events") or []
        if not raw:
            return None
        engine = self._new_engine(execution_id)
        engine.ingest_many(Event.from_dict(e) for e in raw)
        self._remember(engine)
        return engine

    def _engine(self, rec: Dict[str, Any]) -> Optional[ReconstructionEngine]:
        return self._cached(rec["execution_id"]) or self._engine_from_store(rec["execution_id"])

    # ── live executions ──────────────────────────────────────────────────────
    def create_execution(self, user: Dict[str, Any], name: str) -> Dict[str, Any]:
        rec = new_record(user["username"], name or "live execution", "live")
        rec.update(status="created", message="waiting for events", ingest_mode=self.ingest_mode())
        self.repo.put_execution(rec)
        if self.ingest_mode() == "inline":
            self._remember(self._new_engine(rec["execution_id"]))
        return to_jsonable(rec)

    def ingest_mode(self) -> str:
        return "queue" if (self.settings.use_queue and self.transport is not None) else "inline"

    @staticmethod
    def parse_event(raw: Dict[str, Any], execution_id: str) -> Event:
        if not isinstance(raw, dict):
            raise ValueError("event must be an object")
        for field in ("event_id", "event_type"):
            if not raw.get(field):
                raise ValueError(f"'{field}' is required")
        if not (raw.get("service") or raw.get("service_id")):
            raise ValueError("'service' (or 'service_id') is required")
        vc = raw.get("vector_clock", {})
        if not isinstance(vc, dict) or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in vc.values()):
            raise ValueError("'vector_clock' must map service -> non-negative integer")
        parents = raw.get("parent_event_ids", [])
        if not isinstance(parents, list) or any(not isinstance(p, str) for p in parents):
            raise ValueError("'parent_event_ids' must be a list of event ids")
        if len(str(raw["event_id"])) > 200 or len(parents) > 100 or len(vc) > 500:
            raise ValueError("event exceeds size limits")
        data = dict(raw)
        data["execution_id"] = execution_id            # the URL decides the execution
        data.setdefault("trace_id", execution_id)
        event = Event.from_dict(data)
        event.arrival_time_ms = time.time() * 1000.0   # ingestion time is the platform's, not the client's
        return event

    def ingest(self, user: Dict[str, Any], execution_id: str, raw_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        rec = self.get_record(user, execution_id)
        if rec.get("kind") != "live":
            raise ServiceError(409, "events can only be ingested into live executions")
        if not isinstance(raw_events, list) or not raw_events:
            raise ServiceError(422, "'events' must be a non-empty list")
        if len(raw_events) > MAX_INGEST_BATCH:
            raise ServiceError(413, f"at most {MAX_INGEST_BATCH} events per request")

        parsed: List[Event] = []
        rejected: List[Dict[str, Any]] = []
        for i, raw in enumerate(raw_events):
            try:
                parsed.append(self.parse_event(raw, execution_id))
            except (ValueError, TypeError) as exc:
                rejected.append({"index": i, "reason": str(exc)})
                m.EVENTS_FAILED.labels(reason="invalid").inc()

        accepted = duplicates = 0
        if parsed:
            if self.ingest_mode() == "queue":
                seq = secrets.randbits(53)             # unique per publish; the worker skips repeats
                self.transport.publish_events(execution_id, [e.to_dict() for e in parsed], kind="live", start_seq=seq)
                accepted = len(parsed)
                for e in parsed:
                    m.record_event_received(e.service_id, e.metadata.region)
                self.repo.update_execution(execution_id, status="streaming", updated_at=iso_now(),
                                           updated_at_ms=now_ms(), message="events queued for the worker")
            else:
                accepted, duplicates, more_rejected = self._ingest_inline(execution_id, parsed)
                rejected += more_rejected
        return {"execution_id": execution_id, "accepted": accepted, "duplicates": duplicates,
                "rejected": rejected, "mode": self.ingest_mode()}

    def _ingest_inline(self, execution_id: str, events: List[Event]) -> Tuple[int, int, List[Dict[str, Any]]]:
        engine = self._cached(execution_id) or self._engine_from_store(execution_id) or self._new_engine(execution_id)
        self._remember(engine)
        accepted = dups = 0
        rejected: List[Dict[str, Any]] = []
        for i, ev in enumerate(events):
            m.record_event_received(ev.service_id, ev.metadata.region)
            try:
                outcome = engine.ingest(ev)
            except (ValueError, CapacityError) as exc:
                rejected.append({"index": i, "reason": str(exc)})
                m.EVENTS_FAILED.labels(reason="rejected").inc()
                continue
            if outcome == "duplicate":
                dups += 1
                m.record_duplicate()
            else:
                accepted += 1
                m.record_event_processed(ev.service_id)
        if engine.event_count <= self.settings.event_persist_max:
            self.repo.put_events(execution_id, [e.to_dict() for e in events])
        m.UNRESOLVED_DEPENDENCIES.set(engine.unresolved_links)
        self._persist_snapshot(execution_id, engine)
        return accepted, dups, rejected

    def _persist_snapshot(self, execution_id: str, engine: ReconstructionEngine, *, force: bool = False) -> None:
        """Throttled write of derived state so other replicas / restarts can serve it."""
        now = time.time()
        if not force and now - self._last_persist.get(execution_id, 0.0) < 3.0:
            return
        self._last_persist[execution_id] = now
        try:
            self.repo.put_graph(execution_id, engine.snapshot(max_nodes=2000))
            self.repo.put_anomalies(execution_id, [a.to_dict() for a in engine.anomalies(limit=2000)])
            self.repo.update_execution(execution_id, status="streaming", stats=to_jsonable(engine.stats()),
                                       anomalies=engine.anomaly_summary(), updated_at=iso_now(),
                                       updated_at_ms=now_ms(), message="receiving events")
        except Exception as exc:
            logger.warning("snapshot persist failed for %s: %s", execution_id, exc)
            m.record_error("persist")

    # ── execution views ──────────────────────────────────────────────────────
    def graph(self, user: Dict[str, Any], execution_id: str, max_nodes: int = 2000) -> Dict[str, Any]:
        rec = self.get_record(user, execution_id)
        engine = self._engine(rec)
        if engine is not None:
            snap = engine.snapshot(max_nodes=max_nodes)
        else:
            snap = self.repo.get_graph(execution_id)
            if snap is None:
                raise ServiceError(404, "graph not available yet")
        snap = to_jsonable(snap)
        snap["status"] = rec.get("status")
        return snap

    def anomalies(self, user: Dict[str, Any], execution_id: str, *, types: Optional[List[str]] = None,
                  severity: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
        rec = self.get_record(user, execution_id)
        engine = self._engine(rec)
        if engine is not None:
            rows = [a.to_dict() for a in engine.anomalies()]
        else:
            rows = self.repo.get_anomalies(execution_id)
        by_type: Dict[str, int] = {}
        by_sev: Dict[str, int] = {}
        for r in rows:
            by_type[r["anomaly_type"]] = by_type.get(r["anomaly_type"], 0) + 1
            by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
        if types:
            rows = [r for r in rows if r["anomaly_type"] in set(types)]
        if severity:
            rows = [r for r in rows if r["severity"] == severity.upper()]
        order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        rows.sort(key=lambda r: order.get(r["severity"], 3))
        return to_jsonable({"execution_id": execution_id, "total": sum(by_sev.values()), "by_type": by_type,
                            "by_severity": by_sev, "returned": min(len(rows), limit), "anomalies": rows[:limit]})

    def execution_metrics(self, user: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        rec = self.get_record(user, execution_id)
        engine = self._engine(rec)
        out: Dict[str, Any] = {"execution_id": execution_id, "status": rec.get("status"), "kind": rec.get("kind")}
        if engine is not None:
            out.update(stats=engine.stats(), anomalies=engine.anomaly_summary())
        else:
            out.update(stats=rec.get("stats") or {}, anomalies=rec.get("anomalies") or {})
        if rec.get("summary"):
            out["summary"] = rec["summary"]
        return to_jsonable(out)

    def events(self, user: Dict[str, Any], execution_id: str, limit: int = 500) -> Dict[str, Any]:
        rec = self.get_record(user, execution_id)
        engine = self._engine(rec)
        if engine is not None:
            rows = [e.to_dict() for e in engine.events[:limit]]
            total = engine.event_count
        else:
            rows = self.repo.get_events(execution_id, limit=limit)
            total = len(rows)
        return to_jsonable({"execution_id": execution_id, "count": len(rows), "total": total, "events": rows})

    def truth(self, user: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        self.get_record(user, execution_id)
        edges = self.repo.get_blob(execution_id, "truth")
        if edges is None:
            raise ServiceError(404, "no ground truth for this execution (only simulated executions have one)")
        return {"execution_id": execution_id, "edges": edges}

    def load_into_explorer(self, user: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        """Copy an execution into the caller's *private* explorer store (no other user can read it)."""
        rec = self.get_record(user, execution_id)
        engine = self._engine(rec)
        if engine is None:
            raise ServiceError(404, "no events available for this execution")
        if engine.event_count > MAX_LOAD_INTO_EXPLORER:
            raise ServiceError(413, f"explorer supports up to {MAX_LOAD_INTO_EXPLORER} events; "
                                    f"this execution has {engine.event_count}")
        from api.store import user_store

        events = sorted(engine.events, key=lambda e: e.arrival_time_ms)
        name = f"exec:{execution_id}"
        user_store(user["username"]).load_scenario(name, events, [e.event_id for e in events])
        return {"scenario": name, "events": len(events)}

    # ── experiments ──────────────────────────────────────────────────────────
    def create_experiment(self, user: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cfg = ExperimentConfig.from_dict(params).validate(max_events=self.settings.max_experiment_events)
        except (ValueError, TypeError) as exc:
            raise ServiceError(422, str(exc))
        if cfg.transport == "sqs":
            if self.transport is None:
                raise ServiceError(422, "transport 'sqs' requires a configured event queue")
            if cfg.repeats != 1:
                raise ServiceError(422, "transport 'sqs' supports repeats=1")
        rec = new_record(user["username"], cfg.name, "experiment", config=cfg.to_dict())
        self.repo.put_execution(rec)
        return to_jsonable(rec)

    def start_experiment(self, user: Dict[str, Any], experiment_id: str) -> Dict[str, Any]:
        rec = self.get_record(user, experiment_id)
        if rec.get("kind") != "experiment":
            raise ServiceError(409, "not an experiment")
        if rec["status"] != "created":
            raise ServiceError(409, f"experiment is already {rec['status']}")
        updated = self.repo.update_execution(experiment_id, status="queued", message="queued",
                                             updated_at=iso_now(), updated_at_ms=now_ms())
        cfg = ExperimentConfig.from_dict(rec["config"])
        if cfg.transport == "sqs":
            self._pool.submit(self._start_via_queue, experiment_id, cfg)
        else:
            self._pool.submit(run_experiment_direct, self.repo, self.settings, experiment_id)
        return to_jsonable(updated)

    def _start_via_queue(self, experiment_id: str, cfg: ExperimentConfig) -> None:
        """Simulator side of the queue pipeline: publish the faulty stream, keep the ground truth."""
        try:
            self.repo.update_execution(experiment_id, status="running", message="simulating workload",
                                       started_at=iso_now())
            gt = generate_workload(cfg, cfg.seed)
            delivery = inject_faults(gt, cfg, cfg.seed)
            self.repo.put_blob(experiment_id, "ground_truth", [e.to_dict() for e in gt.events])
            self.repo.put_blob(experiment_id, "delivery_meta", DeliveryMeta.from_delivery(delivery).to_dict())
            self.repo.put_blob(experiment_id, "seed", cfg.seed)
            self.repo.update_execution(experiment_id, message=f"publishing {len(delivery.delivered)} events to the queue",
                                       progress=0.1)
            events = [e.to_dict() for e in delivery.delivered]
            total = self.transport.publish_events(experiment_id, events, kind="experiment", start_seq=0)
            # The worker owns the record from the moment the END marker is visible: write everything
            # we need to say BEFORE publishing it, and nothing after.
            self.repo.update_execution(experiment_id, status="streaming", progress=0.5, messages=total,
                                       message=f"{total} messages queued; worker is reconstructing")
            self.transport.publish_end(experiment_id, total)
        except Exception as exc:
            logger.exception("queue experiment %s failed", experiment_id)
            fail_experiment(self.repo, experiment_id, f"{type(exc).__name__}: {exc}")

    def experiment_result(self, user: Dict[str, Any], experiment_id: str) -> Dict[str, Any]:
        rec = self.get_record(user, experiment_id)
        if rec.get("kind") != "experiment":
            raise ServiceError(409, "not an experiment")
        result = self.repo.get_blob(experiment_id, "result")
        if result is None:
            raise ServiceError(404 if rec["status"] in ("created", "queued", "running", "streaming") else 410,
                               f"result not available (status: {rec['status']})")
        return to_jsonable(result)

    # ── system ───────────────────────────────────────────────────────────────
    def queue_status(self) -> Optional[Dict[str, Any]]:
        if self.transport is None:
            return None
        out: Dict[str, Any] = {"queue": self.transport.queue_name}
        try:
            out.update(self.transport.depth())
        except Exception as exc:
            out["error"] = type(exc).__name__
        ts, cached = self._queue_age_cache
        if time.time() - ts > 30:
            if self._cw is None:
                try:
                    self._cw = CloudWatchPublisher(self.settings.metrics_namespace, self.settings.aws_region)
                except Exception:
                    self._cw = None
            age = self._cw.queue_age_seconds(self.transport.queue_name) if self._cw else None
            self._queue_age_cache = (time.time(), age)
            cached = age
        out["oldest_message_age_seconds"] = cached
        if cached is not None:
            m.QUEUE_OLDEST_MESSAGE_AGE.set(cached)
        if "visible" in out:
            m.QUEUE_DEPTH.set(out["visible"])
        return out

    def worker_health(self) -> Optional[Dict[str, Any]]:
        """Is the queue worker alive? Reads its CloudWatch heartbeat (published every ~30 s)."""
        if self.transport is None:
            return None
        ts, cached = self._worker_cache
        if time.time() - ts < 30:
            return cached
        result: Dict[str, Any] = {"status": "unknown", "last_heartbeat_age_seconds": None}
        try:
            if self._cw is None:
                self._cw = CloudWatchPublisher(self.settings.metrics_namespace, self.settings.aws_region)
            age = self._cw.last_datapoint_age("WorkerHeartbeat", {"Service": "worker"})
            if age is not None:
                result = {"status": "healthy" if age <= 180 else "down", "last_heartbeat_age_seconds": round(age)}
            else:
                result["status"] = "down"
        except Exception:
            pass
        self._worker_cache = (time.time(), result)
        return result

    def system_status(self) -> Dict[str, Any]:
        import os

        return to_jsonable({
            "environment": self.settings.environment,
            "storage": self.repo.health(),
            "ingest_mode": self.ingest_mode(),
            "queue": self.queue_status(),
            "worker": self.worker_health(),
            "limits": {"max_experiment_events": self.settings.max_experiment_events,
                       "max_execution_events": self.settings.max_execution_events,
                       "max_ingest_batch": MAX_INGEST_BATCH},
            "grafana_url": os.getenv("GRAFANA_URL") or None,
            "links": {
                "grafana": os.getenv("GRAFANA_URL") or None,
                "cloudwatch": os.getenv("CLOUDWATCH_DASHBOARD_URL") or None,
                "xray": os.getenv("XRAY_URL") or None,
            },
            "tracing": bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
            "cached_engines": len(self._engines),
        })

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


# ── process-wide singleton (tests replace it via set_service) ─────────────────
_service: Optional[ExecutionService] = None
_service_lock = threading.Lock()


def get_service() -> ExecutionService:
    global _service
    with _service_lock:
        if _service is None:
            _service = ExecutionService()
        return _service


def set_service(service: Optional[ExecutionService]) -> None:
    global _service
    with _service_lock:
        _service = service
