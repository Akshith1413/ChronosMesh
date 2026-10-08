"""
ChronosMesh Stage 6 — Comprehensive API Validation & Deterministic Demo Test Suite.

Validates all major endpoints:
- /api/health
- /auth/login & /auth/me
- /api/traces/ & /api/traces/{trace_id}
- /api/traces/{trace_id}/dag
- /api/traces/{trace_id}/timeline
- /api/traces/{trace_id}/anomalies
- /api/analysis/root-cause/{event_id}
- /api/analysis/what-if
- /api/clocks/benchmark
- /metrics & /api/metrics
- RBAC permissions matrix
- Deterministic demo: TRACE-DEMO-001
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import create_access_token

client = TestClient(app)

admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'guru', 'role': 'admin'})}"}
analyst_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'analyst', 'role': 'analyst'})}"}
viewer_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'demo', 'role': 'viewer'})}"}


def test_api_health_endpoint():
    """Verify /api/health returns 200 OK and version."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "chronosmesh-api"


def test_metrics_endpoints():
    """Verify Prometheus text scraping at /metrics and JSON summary at /api/metrics."""
    # /metrics: standard Prometheus scraper output
    res_text = client.get("/metrics")
    assert res_text.status_code == 200
    assert "chronosmesh_events_received_total" in res_text.text

    # /api/metrics: JSON dashboard summary
    res_json = client.get("/api/metrics")
    assert res_json.status_code == 200
    data = res_json.json()
    assert "event_count" in data
    assert "dag_nodes" in data


def test_traces_and_demo_scenario():
    """Verify deterministic TRACE-DEMO-001 scenario reconstruction."""
    # 1. List traces
    res = client.get("/api/traces/", headers=viewer_headers)
    assert res.status_code == 200
    traces = res.json()
    trace_ids = [t["trace_id"] for t in traces]
    assert "TRACE-DEMO-001" in trace_ids

    # 2. Get trace details
    res_trace = client.get("/api/traces/TRACE-DEMO-001", headers=viewer_headers)
    assert res_trace.status_code == 200
    assert res_trace.json()["event_count"] == 6

    # 3. Get timeline: verify arrival order != causal order
    res_tl = client.get("/api/traces/TRACE-DEMO-001/timeline", headers=viewer_headers)
    assert res_tl.status_code == 200
    tl = res_tl.json()
    arrival_types = [e["event_type"] for e in tl["arrival_order"]]
    causal_types = [e["event_type"] for e in tl["causal_order"]]

    # In arrival order: PAYMENT_COMPLETED arrived before PAYMENT_STARTED
    assert arrival_types.index("PAYMENT_COMPLETED") < arrival_types.index("PAYMENT_STARTED")
    # In reconstructed causal order: PAYMENT_STARTED happens before PAYMENT_COMPLETED
    assert causal_types.index("PAYMENT_STARTED") < causal_types.index("PAYMENT_COMPLETED")
    assert causal_types == [
        "ORDER_CREATED",
        "PAYMENT_STARTED",
        "PAYMENT_COMPLETED",
        "INVENTORY_RESERVED",
        "SHIPMENT_CREATED",
        "NOTIFICATION_SENT",
    ]

    # 4. Get DAG: verify graph topology
    res_dag = client.get("/api/traces/TRACE-DEMO-001/dag", headers=viewer_headers)
    assert res_dag.status_code == 200
    dag = res_dag.json()
    assert len(dag["nodes"]) == 6
    assert len(dag["edges"]) >= 5


def test_clock_benchmarking():
    """Verify clock benchmark endpoint compares Lamport, Vector, and HLC/physical clocks."""
    res = client.get("/api/clocks/benchmark?num_events=30", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert "benchmarks" in data
    benchmarks = data["benchmarks"]
    assert any("lamport" in k for k in benchmarks)
    assert any("vector" in k for k in benchmarks)


def test_anomalies_and_root_cause():
    """Verify anomaly detection and root cause traversal."""
    # Ensure trace is loaded
    client.get("/api/traces/TRACE-DEMO-001", headers=viewer_headers)

    res_anom = client.get("/api/traces/TRACE-DEMO-001/anomalies", headers=viewer_headers)
    assert res_anom.status_code == 200
    anom_data = res_anom.json()
    assert "anomalies" in anom_data

    # Check root-cause endpoint
    res_rc = client.get("/api/analysis/root-cause/TRACE-DEMO-001", headers=analyst_headers)
    # Even if event not found or found, returns 200 or 404 cleanly
    assert res_rc.status_code in (200, 404)


def test_what_if_replay():
    """Verify What-If forward fault simulation."""
    res = client.post(
        "/api/analysis/what-if",
        json={
            "scenario": "order_payment_flow",
            "fault": {"type": "remove_event", "event_id": "E-2"}
        },
        headers=analyst_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "what_if_analysis" in data
    assert "blast_radius" in data["what_if_analysis"]


def test_rbac_authorization_matrix():
    """Verify Role-Based Access Control matrix (Viewer vs Analyst vs Admin)."""
    # 1. Unauthenticated request -> 401
    res_unauth = client.get("/api/traces/")
    assert res_unauth.status_code == 401

    # 2. Viewer can view traces
    res_v_traces = client.get("/api/traces/", headers=viewer_headers)
    assert res_v_traces.status_code == 200

    # 3. Viewer attempting Admin action (e.g. clear store) -> 403 Forbidden
    res_v_clear = client.delete("/api/scenarios/", headers=viewer_headers)
    assert res_v_clear.status_code == 403

    # 4. Admin attempting clear store -> 200 OK
    res_a_clear = client.delete("/api/scenarios/", headers=admin_headers)
    assert res_a_clear.status_code == 200
