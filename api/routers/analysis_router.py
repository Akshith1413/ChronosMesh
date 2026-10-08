"""Analysis router — anomalies, confidence, root-cause, what-if, benchmark."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.store import ChronosMeshStore, get_store
from api.schemas.analysis_models import (
    ServiceHealthReport,
    ClockDriftTimeline,
    LatencyHistogramReport,
    TopologyStatsReport,
    EventReplayReport,
)
from api.services.analysis_service import AnalysisService

router = APIRouter()


def _require_dag(store: ChronosMeshStore):
    if not store.events:
        raise HTTPException(
            status_code=400,
            detail="No events loaded. Load a scenario first via POST /api/scenarios/{name}/load",
        )


# ── Anomaly Detection ───────────────────────────────────────────────────────────
@router.get("/anomalies", summary="Detect causal anomalies in the DAG")
async def detect_anomalies(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Runs Akshith's CausalAnomalyDetector on the current DAG.
    Detects: CYCLE, TIME_INVERSION, DUPLICATE_EVENT, CLOCK_DRIFT, CONCURRENT_MUTATION.
    """
    _require_dag(store)
    from chronosmesh.analysis.anomaly import CausalAnomalyDetector

    detector = CausalAnomalyDetector(clock_skew_tolerance_ms=50.0, max_clock_drift_ms=500.0)
    anomalies = detector.detect_all(store.dag, store.events)

    result = [
        {
            "anomaly_type": a.anomaly_type,
            "severity": a.severity,
            "source_event_id": a.source_event_id,
            "target_event_id": a.target_event_id,
            "description": a.description,
            "details": a.details,
        }
        for a in anomalies
    ]

    severity_counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    for a in result:
        sev = a["severity"]
        if sev in severity_counts:
            severity_counts[sev] += 1

    return {
        "anomalies": result,
        "total": len(result),
        "severity_summary": severity_counts,
    }


# ── Confidence Scoring ──────────────────────────────────────────────────────────
@router.get("/confidence", summary="Get confidence scores for all causal edges")
async def get_confidence(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    TrueTime-style confidence scoring for each causal edge in the DAG.
    Uses clock uncertainty intervals to compute P(A before B).
    """
    _require_dag(store)
    from chronosmesh.analysis.confidence import ConfidenceScorer

    scorer = ConfidenceScorer(default_uncertainty_ms=5.0)
    scores = scorer.score_all_edges(store.dag)
    low_conf = scorer.get_low_confidence_edges(store.dag, threshold=0.8)

    result = [
        {
            "source": k[0],
            "target": k[1],
            "confidence": round(v.confidence, 4),
            "method": v.method,
            "uncertainty_ms": v.uncertainty_ms,
        }
        for k, v in scores.items()
    ]

    return {
        "edge_scores": result,
        "low_confidence_edges": [
            {"source": e.source_id, "target": e.target_id, "confidence": round(e.confidence, 4)}
            for e in low_conf
        ],
        "average_confidence": round(
            sum(s["confidence"] for s in result) / max(1, len(result)), 4
        ),
    }


# ── Root-Cause Tracing ──────────────────────────────────────────────────────────
@router.get("/root-cause/{event_id}", summary="Trace root causes of a failure event (hyphenated alias)")
@router.get("/rootcause/{event_id}", summary="Trace root causes of a failure event")
async def root_cause(
    event_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Backward DAG traversal to find root events that causally led to the given event.
    Useful for distributed debugging: 'What caused this failure?'
    """
    _require_dag(store)
    if event_id not in store.dag:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not in DAG")

    from chronosmesh.analysis.root_cause import RootCauseTracer

    tracer = RootCauseTracer()
    result = tracer.trace(store.dag, event_id)
    critical = tracer.find_critical_path(store.dag, event_id)

    return {
        "failure_event_id": event_id,
        "root_causes": result.root_causes,
        "trace_paths": result.trace_paths,
        "critical_path": critical,
        "root_cause_count": len(result.root_causes),
    }


# ── What-If Simulation ──────────────────────────────────────────────────────────
@router.post("/what-if/{event_id}", summary="Simulate removal of an event (hyphenated alias)")
@router.post("/whatif/{event_id}", summary="Simulate removal of an event (blast radius)")
async def what_if(
    event_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    'If event X had NOT happened, what downstream events would be invalidated?'
    Returns blast radius % and list of invalidated / surviving events.
    """
    _require_dag(store)
    if event_id not in store.dag:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not in DAG")

    from chronosmesh.analysis.what_if import WhatIfSimulator

    sim = WhatIfSimulator()
    result = sim.simulate_removal(store.dag, event_id)

    return {
        "removed_event_id": event_id,
        "blast_radius_pct": round(result.blast_radius * 100, 1),
        "cascade_depth": result.cascade_depth,
        "invalidated_events": list(result.invalidated_events),
        "surviving_events": list(result.surviving_events),
        "affected_services": list(result.affected_services),
        "invalidated_count": len(result.invalidated_events),
    }


@router.post("/what-if", summary="Simulate what-if fault with JSON payload")
async def what_if_json(
    payload: Dict[str, Any],
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Support POST /api/analysis/what-if with JSON body."""
    scenario = payload.get("scenario")
    if scenario and store.current_scenario != scenario:
        from api.routers.scenarios_router import _build_scenario
        events, arrival_ids = _build_scenario(scenario)
        store.load_scenario(scenario, events, arrival_ids)
    _require_dag(store)

    fault = payload.get("fault", {})
    event_id = fault.get("event_id") or payload.get("event_id")
    if not event_id or event_id not in store.dag:
        nodes = list(store.dag.nodes)
        event_id = nodes[1] if len(nodes) > 1 else (nodes[0] if nodes else None)
        if not event_id:
            raise HTTPException(status_code=404, detail="No events in DAG for what-if simulation")

    from chronosmesh.analysis.what_if import WhatIfSimulator
    sim = WhatIfSimulator()
    result = sim.simulate_removal(store.dag, event_id)

    return {
        "scenario": store.current_scenario,
        "removed_event_id": event_id,
        "what_if_analysis": {
            "removed_event_id": event_id,
            "blast_radius": round(result.blast_radius * 100, 1),
            "cascade_depth": result.cascade_depth,
            "invalidated_events": list(result.invalidated_events),
            "surviving_events": list(result.surviving_events),
            "affected_services": list(result.affected_services),
        },
        "blast_radius_pct": round(result.blast_radius * 100, 1),
        "cascade_depth": result.cascade_depth,
        "invalidated_events": list(result.invalidated_events),
        "surviving_events": list(result.surviving_events),
        "affected_services": list(result.affected_services),
    }


# ── Clock Benchmarking ──────────────────────────────────────────────────────────
@router.get("/benchmark", summary="Compare Lamport vs Vector vs HLC clock strategies")
async def benchmark(
    packet_loss_pct: float = 0.0,
    clock_drift_ms: float = 0.0,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Benchmarks all three clock strategies against the current DAG ground truth.
    Params control simulated network conditions.
    """
    _require_dag(store)
    from chronosmesh.analysis.benchmarking import ClockBenchmark

    bench = ClockBenchmark()
    results = bench.benchmark(
        store.dag, store.events,
        packet_loss_pct=packet_loss_pct / 100.0,
        clock_drift_ms=clock_drift_ms,
    )
    comparison = bench.compare_strategies(results)

    return {
        "parameters": {
            "packet_loss_pct": packet_loss_pct,
            "clock_drift_ms": clock_drift_ms,
            "event_count": len(store.events),
        },
        "results": [
            {
                "strategy": r.strategy_name,
                "accuracy_pct": round(r.reconstruction_accuracy * 100, 1),
                "memory_kb": round(r.memory_bytes / 1024, 1),
                "computation_time_ms": r.computation_time_ms,
                "correct_orderings": r.correct_orderings,
                "total_orderings": r.total_orderings,
                "false_positives": r.false_positives,
                "false_negatives": r.false_negatives,
            }
            for r in results
        ],
        "winner": max(comparison, key=comparison.get),
    }


# ── Graph Diff ──────────────────────────────────────────────────────────────────
@router.get("/graphdiff", summary="Compare two scenario runs for behavioral drift")
async def graph_diff(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Compares the current DAG to a freshly regenerated version of the same scenario
    to illustrate graph diffing capability.
    """
    _require_dag(store)
    if not store.current_scenario:
        raise HTTPException(status_code=400, detail="No scenario loaded")

    from dataclasses import asdict
    from chronosmesh.analysis.graph_diff import CausalGraphDiffer
    from api.routers.scenarios_router import _build_scenario

    try:
        events_b, _ = _build_scenario(store.current_scenario)
        from chronosmesh.causality.dag_builder import CausalDAGBuilder
        builder_b = CausalDAGBuilder()
        dag_b = builder_b.build(events_b)

        differ = CausalGraphDiffer()
        diff = differ.diff(store.dag, dag_b)
        summary = differ.get_change_summary(diff)
        diff_dict = asdict(diff)
        diff_dict["summary"] = summary
        return {"diff": diff_dict, "scenario": store.current_scenario}
    except Exception as exc:
        return {
            "diff": {"note": f"Graph diff unavailable: {exc}"},
            "scenario": store.current_scenario,
        }


# ── 1. Service Health Map ───────────────────────────────────────────────────────
@router.get(
    "/service-health",
    response_model=ServiceHealthReport,
    summary="Get real-time deterministic service health derived from DAG and anomalies",
)
async def get_service_health(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Derives service health deterministically from actual loaded DAG data and anomalies.
    Statuses: Healthy, Degraded, Critical, Unavailable.
    """
    return AnalysisService.get_service_health(store)


# ── 2. Clock Drift Timeline ─────────────────────────────────────────────────────
@router.get(
    "/clock-drift-timeline",
    response_model=ClockDriftTimeline,
    summary="Get timeline of physical clock drift and arrival skew",
)
async def get_clock_drift_timeline(
    skew_tolerance_ms: float = 50.0,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Calculates physical clock skew and arrival delay for each event in the trace.
    NOTE: Lamport/Vector logical counters are NEVER subtracted from physical milliseconds.
    """
    return AnalysisService.get_clock_drift_timeline(store, skew_tolerance_ms=skew_tolerance_ms)


# ── 3. Latency Histogram ────────────────────────────────────────────────────────
@router.get(
    "/latency-histogram",
    response_model=LatencyHistogramReport,
    summary="Get edge transit latency distribution and percentiles (p50, p95, p99)",
)
async def get_latency_histogram(
    bins: int = 5,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Computes distribution and percentiles (p50, p95, p99, min, max, mean)
    for positive edge transit latencies across causal edges.
    """
    return AnalysisService.get_latency_histogram(store, num_bins=bins)


# ── 4. Topology Stats ───────────────────────────────────────────────────────────
@router.get(
    "/topology-stats",
    response_model=TopologyStatsReport,
    summary="Get NetworkX graph-theoretic topology metrics, critical path, and concurrency",
)
async def get_topology_stats(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Computes graph metrics: density, coupling, longest causal path,
    and pairwise concurrency factor.
    """
    return AnalysisService.get_topology_stats(store)


# ── 5. Event Replay ─────────────────────────────────────────────────────────────
@router.get(
    "/event-replay",
    response_model=EventReplayReport,
    summary="Get topological generations for causal replay preserving concurrency",
)
async def get_event_replay(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Reconstructs replay sequences in causal layers via topological generations.
    Events within each layer are causally concurrent and execute in parallel.
    """
    return AnalysisService.get_event_replay(store)

