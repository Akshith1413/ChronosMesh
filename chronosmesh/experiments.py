"""Experiment lifecycle shared by the API (in-process runs) and the queue worker (SQS runs)."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from chronosmesh.config import Settings
from chronosmesh.evaluation import run_experiment
from chronosmesh.observability import metrics as m
from chronosmesh.persistence.base import Repository
from chronosmesh.reconstruction import ReconstructionEngine
from chronosmesh.events.event import Event
from chronosmesh.simulator import ExperimentConfig
from chronosmesh.utils import iso_now, now_ms, to_jsonable


def new_id(prefix: str = "exp") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def new_record(owner: str, name: str, kind: str, *, config: Optional[Dict[str, Any]] = None,
               parent_id: Optional[str] = None, execution_id: Optional[str] = None) -> Dict[str, Any]:
    ts = now_ms()
    rec: Dict[str, Any] = {
        "execution_id": execution_id or new_id("exp" if kind == "experiment" else "exec"),
        "owner": owner, "name": name, "kind": kind, "status": "created", "progress": 0.0, "message": "",
        "created_at": iso_now(), "created_at_ms": ts, "updated_at": iso_now(), "updated_at_ms": ts,
    }
    if config is not None:
        rec["config"] = config
    if parent_id:
        rec["parent_id"] = parent_id
    return rec


def compact_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """The headline numbers shown in lists (full result lives in the 'result' blob)."""
    s = result["summary"]
    run0 = result["runs"][0]
    return {
        "f1": {k: v["f1"]["mean"] for k, v in s["approaches"].items()},
        "precision": {k: v["precision"]["mean"] for k, v in s["approaches"].items()},
        "recall": {k: v["recall"]["mean"] for k, v in s["approaches"].items()},
        "concurrency_accuracy": {k: v["accuracy"]["mean"] for k, v in s["concurrency"].items()},
        "ordering_accuracy": {k: v["mean"] for k, v in s["ordering"].items()},
        "recovery_rate": s["recovery_rate"],
        "throughput_eps": s["performance"]["throughput_eps"]["mean"],
        "reconstruction_seconds": s["performance"]["reconstruction_seconds"]["mean"],
        "events": run0["events_delivered_unique"],
        "executions": run0["executions"],
        "anomalies": run0["anomalies"]["by_type"],
        "repeats": len(result["runs"]),
    }


def persist_samples(repo: Repository, settings: Settings, experiment: Dict[str, Any],
                    samples: List[Dict[str, Any]]) -> List[str]:
    """Store drill-down executions (events as received + ground-truth edges) as child records."""
    ids = []
    for s in samples:
        eid = s["execution_id"]
        engine = ReconstructionEngine(eid)
        engine.ingest_many(Event.from_dict(d) for d in s["events"])
        child = new_record(experiment["owner"], f"{experiment['name']} · {eid}", "sample",
                           parent_id=experiment["execution_id"], execution_id=eid)
        child.update(status="succeeded", progress=1.0, stats=to_jsonable(engine.stats()),
                     anomalies=engine.anomaly_summary())
        repo.put_execution(child)
        repo.put_blob(eid, "truth", s["truth_edges"])
        repo.put_blob(eid, "events", s["events"])
        if len(s["events"]) <= settings.event_persist_max:
            repo.put_events(eid, s["events"])
        repo.put_graph(eid, engine.snapshot(max_nodes=2000))
        repo.put_anomalies(eid, [a.to_dict() for a in engine.anomalies(limit=2000)])
        ids.append(eid)
    return ids


def finish_experiment(repo: Repository, settings: Settings, experiment_id: str, result: Dict[str, Any],
                      samples: List[Dict[str, Any]], *, started_at: float) -> Dict[str, Any]:
    rec = repo.get_execution(experiment_id) or {}
    repo.put_blob(experiment_id, "result", result)
    sample_ids = persist_samples(repo, settings, rec, samples) if rec else []
    duration = time.time() - started_at
    m.EXPERIMENTS.labels(status="succeeded").inc()
    m.EXPERIMENT_DURATION.observe(duration)
    return repo.update_execution(
        experiment_id, status="succeeded", progress=1.0, message="completed", summary=compact_summary(result),
        samples=sample_ids, duration_seconds=round(duration, 3), finished_at=iso_now(), updated_at=iso_now(),
        updated_at_ms=now_ms()) or {}


def fail_experiment(repo: Repository, experiment_id: str, error: str, *, started_at: Optional[float] = None) -> None:
    m.EXPERIMENTS.labels(status="failed").inc()
    repo.update_execution(experiment_id, status="failed", message="failed", error=error[:500],
                          updated_at=iso_now(), updated_at_ms=now_ms())


def run_experiment_direct(repo: Repository, settings: Settings, experiment_id: str,
                          on_progress: Optional[Callable[[float, str], None]] = None) -> None:
    """Run an experiment in-process and persist everything. Never raises (status carries failures)."""
    started = time.time()
    last_write = 0.0
    try:
        rec = repo.get_execution(experiment_id)
        if rec is None:
            return
        cfg = ExperimentConfig.from_dict(rec["config"]).validate(max_events=settings.max_experiment_events)
        repo.update_execution(experiment_id, status="running", message="starting", started_at=iso_now())

        def progress(frac: float, msg: str) -> None:
            nonlocal last_write
            if on_progress:
                on_progress(frac, msg)
            now = time.time()
            if now - last_write >= 1.0 or frac >= 1.0:
                last_write = now
                repo.update_execution(experiment_id, progress=round(min(frac, 0.99), 3), message=msg,
                                      updated_at=iso_now(), updated_at_ms=now_ms())

        samples: List[Dict[str, Any]] = []
        result = run_experiment(cfg, progress=progress, keep_samples=settings.sample_executions_kept,
                                samples_out=samples)
        finish_experiment(repo, settings, experiment_id, result, samples, started_at=started)
    except Exception as exc:  # status must reflect failure; the API thread must not die
        fail_experiment(repo, experiment_id, f"{type(exc).__name__}: {exc}", started_at=started)
