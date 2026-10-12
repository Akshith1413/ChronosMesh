"""Experiment runner: simulate -> inject faults -> reconstruct -> score against ground truth."""

from __future__ import annotations

import random
import resource
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from chronosmesh.evaluation.metrics import ExecutionView, chain_edges, concurrency_scores, mean_ci, prf
from chronosmesh.events.event import Event
from chronosmesh.reconstruction import ReconstructionEngine, reconstruct
from chronosmesh.simulator import ExperimentConfig, generate_workload, inject_faults
from chronosmesh.simulator.faults import DeliveryResult
from chronosmesh.simulator.workload import GroundTruth

APPROACHES = ("arrival_order", "wall_clock", "declared_only", "chronosmesh")
RECOVERY_F1_THRESHOLD = 0.99
OVERLAP = 10  # messages redelivered after a crash although already checkpointed (visibility timeout)

ProgressFn = Callable[[float, str], None]


class EngineRouter:
    """One streaming engine per execution -- what a queue worker holds in memory."""

    def __init__(self) -> None:
        self.engines: Dict[str, ReconstructionEngine] = {}

    def ingest(self, ev: Event) -> None:
        eid = ev.effective_execution_id
        engine = self.engines.get(eid)
        if engine is None:
            engine = self.engines[eid] = ReconstructionEngine(eid)
        engine.ingest(ev)

    def checkpoint(self) -> Dict[str, List[Dict[str, Any]]]:
        return {eid: eng.checkpoint() for eid, eng in self.engines.items()}

    @classmethod
    def restore(cls, checkpoint: Dict[str, List[Dict[str, Any]]]) -> "EngineRouter":
        router = cls()
        for eid, snap in checkpoint.items():
            router.engines[eid] = ReconstructionEngine.restore(eid, snap)
        return router

    def duplicates(self) -> int:
        return sum(e.counters.get("duplicate", 0) for e in self.engines.values())

    def unresolved_links(self) -> int:
        return sum(e.unresolved_links for e in self.engines.values())


def stream_through_engines(delivered: List[Event], cfg: ExperimentConfig) -> Dict[str, Any]:
    """Feed the delivered stream to streaming engines, optionally crashing and recovering them.

    Models an at-least-once queue: after a crash the worker restores its last checkpoint and the
    broker redelivers everything that was not acknowledged -- plus a few already-checkpointed
    messages, which the engines must treat idempotently.
    """
    n = len(delivered)
    crashes = min(cfg.worker_failures, max(0, n // 20))
    crash_at = {int(n * (k + 1) / (crashes + 1)) for k in range(crashes)}
    checkpoint_every = max(50, n // (crashes * 3 + 4)) if crashes else 0

    router = EngineRouter()
    checkpoint: Dict[str, List[Dict[str, Any]]] = {}
    committed = recoveries = redelivered = suppressed_before_crash = 0
    i = 0
    while i < n:
        router.ingest(delivered[i])
        i += 1
        if checkpoint_every and i % checkpoint_every == 0:
            checkpoint, committed = router.checkpoint(), i
        if i in crash_at:
            crash_at.discard(i)
            suppressed_before_crash += router.duplicates()
            router = EngineRouter.restore(checkpoint)       # in-memory state lost
            replay_from = max(0, committed - OVERLAP)
            redelivered += i - replay_from
            i = replay_from
            recoveries += 1
    return {"router": router, "recoveries": recoveries, "redelivered": redelivered,
            "duplicates_suppressed": suppressed_before_crash + router.duplicates()}


def _group(events: List[Event]) -> Dict[str, List[Event]]:
    out: Dict[str, List[Event]] = defaultdict(list)
    for e in events:
        out[e.effective_execution_id].append(e)
    return out


def _first_deliveries(events: List[Event]) -> List[Event]:
    seen: Set[str] = set()
    out = []
    for e in events:
        if e.event_id not in seen:
            seen.add(e.event_id)
            out.append(e)
    return out


@dataclass
class DeliveryMeta:
    """What the simulator did to the stream (needed to report fault counts without the originals)."""

    dropped: int = 0
    duplicated: int = 0
    metadata_lost: int = 0

    @classmethod
    def from_delivery(cls, d: DeliveryResult) -> "DeliveryMeta":
        return cls(len(d.dropped_ids), len(d.duplicated_ids), len(d.metadata_lost_ids))

    def to_dict(self) -> Dict[str, int]:
        return {"dropped": self.dropped, "duplicated": self.duplicated, "metadata_lost": self.metadata_lost}


def score_trial(
    cfg: ExperimentConfig,
    seed: int,
    gt: GroundTruth,
    meta: DeliveryMeta,
    delivered: List[Event],
    router: EngineRouter,
    *,
    elapsed: float,
    cpu: float,
    streamed: Dict[str, Any],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """Score reconstructed graphs against the independent ground truth.

    ``delivered`` may be in any order (a queue does not preserve it); the simulated arrival order is
    recovered from each event's ``arrival_time_ms``.
    """
    def report(frac: float, msg: str) -> None:
        if progress:
            progress(frac, msg)

    delivered = sorted(delivered, key=lambda e: e.arrival_time_ms)
    unique = _first_deliveries(delivered)
    unique_by_exec = _group(unique)
    true_by_id = {e.event_id: e for e in gt.events}

    report(0.3, "computing ground-truth edges")
    truth_edges: Set[Tuple[str, str]] = set()
    for evs in unique_by_exec.values():
        oracle = reconstruct([true_by_id[e.event_id] for e in evs], use_explicit=False)  # TRUE clocks
        truth_edges |= set(oracle.dag.edges())

    chronos_edges: Set[Tuple[str, str]] = set()
    stats: Counter = Counter()
    for engine in router.engines.values():
        res = engine.result()
        chronos_edges |= set(res.dag.edges())
        stats.update(res.stats)

    consistent = True
    if cfg.worker_failures:
        clean: Set[Tuple[str, str]] = set()
        for evs in _group(delivered).values():
            clean |= set(reconstruct(evs).dag.edges())
        consistent = clean == chronos_edges

    report(0.65, "scoring baselines")
    arrival_edges: Set[Tuple[str, str]] = set()
    wall_edges: Set[Tuple[str, str]] = set()
    declared_edges: Set[Tuple[str, str]] = set()
    views: Dict[str, ExecutionView] = {}
    for eid, evs in unique_by_exec.items():
        arrival_edges |= chain_edges([e.event_id for e in evs])
        wall_edges |= chain_edges([e.event_id for e in sorted(evs, key=lambda e: e.timestamp_ms)])
    for eid, evs in _group(delivered).items():
        declared = reconstruct(evs, use_vector_clocks=False)
        declared_edges |= set(declared.dag.edges())
        uniq = unique_by_exec[eid]
        views[eid] = ExecutionView([e.event_id for e in uniq], {e.event_id: e for e in uniq},
                                   router.engines[eid].dag, declared.dag)

    approaches = {
        "arrival_order": prf(arrival_edges, truth_edges),
        "wall_clock": prf(wall_edges, truth_edges),
        "declared_only": prf(declared_edges, truth_edges),
        "chronosmesh": prf(chronos_edges, truth_edges),
    }

    # Late-event recovery: ground-truth edges whose *cause arrived after its effect* (the out-of-order case).
    first_arrival = {e.event_id: e.arrival_time_ms for e in unique}
    late_truth = {(u, v) for u, v in truth_edges if first_arrival.get(u, 0) > first_arrival.get(v, 0)}
    late_recovery = {
        name: (len(edges & late_truth) / len(late_truth) if late_truth else None)
        for name, edges in (("arrival_order", arrival_edges), ("wall_clock", wall_edges),
                            ("declared_only", declared_edges), ("chronosmesh", chronos_edges))
    }

    report(0.8, "classifying concurrency")
    concurrency = concurrency_scores(views, true_by_id, rng=random.Random(seed ^ 0x5EED))

    report(0.92, "detecting anomalies")
    by_type: Counter = Counter()
    total_anoms = 0
    for engine in router.engines.values():
        found = engine.anomalies()
        total_anoms += len(found)
        by_type.update(a.anomaly_type for a in found)

    return {
        "seed": seed,
        "executions": len(unique_by_exec),
        "events_generated": len(gt.events),
        "events_delivered_unique": len(unique),
        "deliveries_total": len(delivered),
        "events_dropped": meta.dropped,
        "events_duplicated": meta.duplicated,
        "events_metadata_lost": meta.metadata_lost,
        "arrival_disorder": _disorder(unique, gt.true_time_ms),
        "truth_edges": len(truth_edges),
        "approaches": approaches,
        "concurrency": concurrency,
        "late_edges": len(late_truth),
        "late_event_recovery": late_recovery,
        "recovered": approaches["chronosmesh"]["f1"] >= RECOVERY_F1_THRESHOLD,
        "performance": {
            "reconstruction_seconds": elapsed,
            "throughput_eps": len(delivered) / elapsed if elapsed else None,
            "cpu_seconds": cpu,
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
        },
        "fault_tolerance": {
            "worker_crashes_injected": cfg.worker_failures,
            "recoveries": streamed["recoveries"],
            "redelivered_messages": streamed["redelivered"],
            "duplicates_suppressed": streamed["duplicates_suppressed"],
            "duplicate_detection_rate": (min(1.0, streamed["duplicates_suppressed"] / meta.duplicated)
                                         if meta.duplicated else None),
            "state_consistent_after_recovery": consistent,
        },
        "reconstruction": dict(stats),
        "anomalies": {"total": total_anoms, "by_type": dict(by_type)},
    }


def run_single(cfg: ExperimentConfig, seed: int, *, progress: Optional[ProgressFn] = None,
               keep_samples: int = 0, samples_out: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    def report(frac: float, msg: str) -> None:
        if progress:
            progress(frac, msg)

    report(0.05, "generating ground-truth workload")
    gt: GroundTruth = generate_workload(cfg, seed)
    report(0.2, "injecting faults")
    delivery: DeliveryResult = inject_faults(gt, cfg, seed)

    report(0.45, "reconstructing (streaming engines)")
    cpu0 = time.process_time()
    t0 = time.perf_counter()
    streamed = stream_through_engines(delivery.delivered, cfg)
    router: EngineRouter = streamed["router"]
    for engine in router.engines.values():   # force the lazy rebuild inside the timed region
        engine.result()
    elapsed = time.perf_counter() - t0
    cpu = time.process_time() - cpu0

    result = score_trial(cfg, seed, gt, DeliveryMeta.from_delivery(delivery), delivery.delivered, router,
                         elapsed=elapsed, cpu=cpu, streamed=streamed, progress=progress)
    if keep_samples and samples_out is not None:
        samples_out.extend(extract_samples(gt, delivery.delivered, router, keep_samples))
    return result


def extract_samples(gt: GroundTruth, delivered: List[Event], router: EngineRouter, k: int) -> List[Dict[str, Any]]:
    """The first ``k`` executions, as delivered, with their ground-truth edges (for UI drill-down)."""
    by_exec = _group(delivered)
    true_by_id = {e.event_id: e for e in gt.events}
    out = []
    for eid in list(by_exec)[:k]:
        uniq = _first_deliveries(by_exec[eid])
        truth = reconstruct([true_by_id[e.event_id] for e in uniq], use_explicit=False)
        out.append({
            "execution_id": eid,
            "events": [e.to_dict() for e in by_exec[eid]],
            "truth_edges": [list(edge) for edge in truth.dag.edges()],
        })
    return out


def _disorder(unique: List[Event], true_time: Dict[str, float]) -> float:
    """Fraction of adjacent arrivals whose true generation order is reversed."""
    if len(unique) < 2:
        return 0.0
    inv = sum(1 for a, b in zip(unique, unique[1:]) if true_time[a.event_id] > true_time[b.event_id])
    return inv / (len(unique) - 1)


def summarize(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"approaches": {}, "concurrency": {}, "ordering": {}, "late_event_recovery": {}, "performance": {}}
    for ap in APPROACHES:
        summary["approaches"][ap] = {
            m: mean_ci([r["approaches"][ap][m] for r in runs]) for m in ("precision", "recall", "f1")
        }
        summary["concurrency"][ap] = {
            m: mean_ci([r["concurrency"][ap][m] for r in runs if r["concurrency"][ap]["pairs_evaluated"]])
            for m in ("accuracy", "concurrent_precision", "concurrent_recall")
        }
        summary["ordering"][ap] = mean_ci([r["concurrency"][ap]["ordering_accuracy"] for r in runs
                                           if r["concurrency"][ap].get("ordering_pairs")])
        summary["late_event_recovery"][ap] = mean_ci([r["late_event_recovery"][ap] for r in runs
                                                      if r["late_event_recovery"][ap] is not None])
    for m in ("reconstruction_seconds", "throughput_eps", "cpu_seconds", "peak_rss_mb"):
        summary["performance"][m] = mean_ci([r["performance"][m] for r in runs])
    summary["recovery_rate"] = sum(1 for r in runs if r["recovered"]) / len(runs)
    summary["recovery_f1_threshold"] = RECOVERY_F1_THRESHOLD
    rates = [r["fault_tolerance"]["duplicate_detection_rate"] for r in runs if r["fault_tolerance"]["duplicate_detection_rate"] is not None]
    summary["duplicate_detection_rate"] = mean_ci(rates) if rates else None
    summary["duplicates_suppressed_total"] = sum(r["fault_tolerance"]["duplicates_suppressed"] for r in runs)
    summary["all_recoveries_consistent"] = all(r["fault_tolerance"]["state_consistent_after_recovery"] for r in runs)
    return summary


def run_experiment(cfg: ExperimentConfig, *, progress: Optional[ProgressFn] = None,
                   keep_samples: int = 0, samples_out: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    cfg.validate()
    runs: List[Dict[str, Any]] = []
    for i in range(cfg.repeats):
        seed = cfg.seed + i

        def sub(frac: float, msg: str, _i: int = i) -> None:
            if progress:
                progress((_i + frac) / cfg.repeats, f"run {_i + 1}/{cfg.repeats}: {msg}")

        # drill-down samples come from the first repeat only
        runs.append(run_single(cfg, seed, progress=sub, keep_samples=keep_samples if i == 0 else 0,
                               samples_out=samples_out))
    if progress:
        progress(1.0, "done")
    return {"config": cfg.to_dict(), "runs": runs, "summary": summarize(runs)}
