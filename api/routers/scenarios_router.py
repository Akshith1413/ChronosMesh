"""Scenarios router — load pre-built microservice scenarios."""

import random
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_role, ROLE_ADMIN
from api.store import ChronosMeshStore, get_store
from chronosmesh.events.generator import ScenarioBuilder

router = APIRouter()

# Catalogue of available scenarios
# Catalogue of available scenarios / traces
SCENARIO_CATALOGUE: Dict[str, Dict[str, Any]] = {
    "order_payment_flow": {
        "id": "order_payment_flow",
        "trace_id": "T-1001",
        "name": "Order → Payment → Inventory → Shipping",
        "description": (
            "Linear causal chain across four microservices. "
            "Simulates a standard e-commerce order fulfillment pipeline."
        ),
        "pattern": "chain",
        "expected_nodes": 8,
        "services": ["order-svc", "payment-svc", "inventory-svc", "shipping-svc"],
    },
    "concurrent_branches": {
        "id": "concurrent_branches",
        "trace_id": "T-1002",
        "name": "Concurrent Payment + Inventory",
        "description": (
            "Order service triggers Payment and Inventory services in parallel. "
            "Demonstrates concurrency detection (E2 ∥ E3)."
        ),
        "pattern": "fork",
        "expected_nodes": 3,
        "services": ["order-svc", "payment-svc", "inventory-svc"],
    },
    "diamond_pattern": {
        "id": "diamond_pattern",
        "trace_id": "T-1003",
        "name": "Diamond (Fork + Join)",
        "description": (
            "ROOT → (Branch A ∥ Branch B) → JOIN. "
            "Classic DAG pattern showing concurrent execution merging at a synchronisation point."
        ),
        "pattern": "diamond",
        "expected_nodes": 4,
        "services": ["order-svc", "payment-svc", "inventory-svc", "shipping-svc"],
    },
    "ecommerce_demo": {
        "id": "ecommerce_demo",
        "trace_id": "TRACE-DEMO-001",
        "name": "Deterministic E-Commerce Order Flow (Stage 6 Final Demo)",
        "description": (
            "Complete 5-service multi-cloud workflow (Order → Payment → Inventory → Shipping → Notification). "
            "Demonstrates out-of-order Kafka arrival (E1 → E3 → E2 → E5 → E4 → E6) vs reconstructed causal order, "
            "cross-region physical clock skew, and anomaly detection."
        ),
        "pattern": "distributed_pipeline",
        "expected_nodes": 6,
        "services": ["order-svc", "payment-svc", "inventory-svc", "shipping-svc", "notification-svc"],
    },
}

TRACE_ALIAS_MAP: Dict[str, str] = {
    "T-1001": "order_payment_flow",
    "T-1002": "concurrent_branches",
    "T-1003": "diamond_pattern",
    "TRACE-DEMO-001": "ecommerce_demo",
    "T-DEMO-001": "ecommerce_demo",
}


def _resolve_scenario_name(identifier: str) -> str:
    """Resolve either scenario_name or trace_id (e.g. T-1001, TRACE-DEMO-001)."""
    if identifier in TRACE_ALIAS_MAP:
        return TRACE_ALIAS_MAP[identifier]
    if identifier in SCENARIO_CATALOGUE:
        return identifier
    raise HTTPException(status_code=404, detail=f"Scenario or Trace '{identifier}' not found")


def _build_scenario(name: str):
    """Call ScenarioBuilder or MockDistributedCluster and return (events, arrival_order)."""
    resolved = _resolve_scenario_name(name)
    if resolved == "ecommerce_demo":
        from chronosmesh.services.mock_services import MockDistributedCluster
        cluster = MockDistributedCluster(
            simulate_network_delay=True,
            simulate_clock_skew=True,
            simulate_out_of_order=True,
        )
        events = cluster.generate_ecommerce_trace(trace_id="TRACE-DEMO-001")
        arrival_sorted = sorted(events, key=lambda x: x.arrival_time_ms)
        arrival_ids = [e.event_id for e in arrival_sorted]
        return events, arrival_ids

    builder = ScenarioBuilder()
    if resolved == "order_payment_flow":
        events = builder.order_payment_flow()
    elif resolved == "concurrent_branches":
        events = builder.concurrent_branches()
    elif resolved == "diamond_pattern":
        events = builder.diamond_pattern()
    else:
        raise ValueError(f"Unknown scenario: {resolved}")

    causal_ids = [e.event_id for e in events]
    # Simulate network out-of-order delivery
    arrival_ids = list(causal_ids)
    random.shuffle(arrival_ids)
    # Inject simulated network delay into arrival timestamps
    for evt in events:
        evt.arrival_time_ms += random.uniform(0, 500)

    return events, arrival_ids


@router.get("/", summary="List available demo scenarios")
async def list_scenarios(_: dict = Depends(get_current_user)):
    return list(SCENARIO_CATALOGUE.values())


@router.post("/{scenario_name}/load", summary="Load a scenario into the engine")
async def load_scenario(
    scenario_name: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Load and reconstruct causality for a named scenario or trace ID (e.g. T-1001).

    Returns the full causal DAG JSON plus both event orderings
    (arrival order vs reconstructed causal order) so the frontend
    can render the side-by-side comparison view.
    """
    resolved_name = _resolve_scenario_name(scenario_name)
    events, arrival_ids = _build_scenario(resolved_name)
    store.load_scenario(resolved_name, events, arrival_ids)

    dag_json = store.get_dag_json()
    arrival_events = store.get_arrival_order_json()

    return {
        "scenario": SCENARIO_CATALOGUE[resolved_name],
        "dag": dag_json,
        "arrival_order": arrival_events,
        "causal_order": [
            e for e in store.get_events_json()
            if e["event_id"] in {n for n in dag_json["topological_order"]}
        ],
        "event_count": len(events),
    }


@router.delete("/", summary="Clear all loaded events")
async def clear_store(
    _: dict = Depends(require_role(ROLE_ADMIN)),
    store: ChronosMeshStore = Depends(get_store),
):
    store.clear()
    return {"message": "Store cleared successfully"}


# ── Trace Sub-Router (/api/traces) ───────────────────────────────────────────
traces_router = APIRouter()


@traces_router.get("/", summary="List available workflow traces")
async def list_traces(_: dict = Depends(get_current_user)):
    return [
        {
            "trace_id": s["trace_id"],
            "scenario_id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "pattern": s["pattern"],
            "expected_nodes": s["expected_nodes"],
            "services": s["services"],
        }
        for s in SCENARIO_CATALOGUE.values()
    ]


@traces_router.get("/{trace_id}", summary="Get trace metadata and load it")
async def get_trace(
    trace_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    resolved = _resolve_scenario_name(trace_id)
    if store.current_scenario != resolved:
        events, arrival_ids = _build_scenario(resolved)
        store.load_scenario(resolved, events, arrival_ids)
    return {
        "trace": SCENARIO_CATALOGUE[resolved],
        "event_count": len(store.events),
        "dag_nodes": store.dag.number_of_nodes(),
        "dag_edges": store.dag.number_of_edges(),
    }


@traces_router.get("/{trace_id}/dag", summary="Get reconstructed causal DAG for a trace")
async def get_trace_dag(
    trace_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    resolved = _resolve_scenario_name(trace_id)
    if store.current_scenario != resolved:
        events, arrival_ids = _build_scenario(resolved)
        store.load_scenario(resolved, events, arrival_ids)
    return store.get_dag_json()


@traces_router.get("/{trace_id}/timeline", summary="Get arrival and causal timeline for a trace")
async def get_trace_timeline(
    trace_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    resolved = _resolve_scenario_name(trace_id)
    if store.current_scenario != resolved:
        events, arrival_ids = _build_scenario(resolved)
        store.load_scenario(resolved, events, arrival_ids)
    topo = store._safe_topo()
    eid_map = {e.event_id: e.to_dict() for e in store.events}
    causal = [eid_map[eid] for eid in topo if eid in eid_map]
    return {
        "trace_id": trace_id,
        "scenario": resolved,
        "arrival_order": store.get_arrival_order_json(),
        "causal_order": causal,
        "total_steps": len(causal),
    }


@traces_router.get("/{trace_id}/anomalies", summary="Get anomalies for a trace")
async def get_trace_anomalies(
    trace_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    resolved = _resolve_scenario_name(trace_id)
    if store.current_scenario != resolved:
        events, arrival_ids = _build_scenario(resolved)
        store.load_scenario(resolved, events, arrival_ids)
    from chronosmesh.analysis.anomaly import CausalAnomalyDetector
    detector = CausalAnomalyDetector()
    anomalies = detector.detect_all(store.dag, store.events)
    return {
        "trace_id": trace_id,
        "scenario": resolved,
        "total": len(anomalies),
        "anomalies": [
            {
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "source_event_id": a.source_event_id,
                "target_event_id": a.target_event_id,
                "description": a.description,
                "details": a.details,
            }
            for a in anomalies
        ],
    }

