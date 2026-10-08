"""
Integration tests for ChronosMesh REST API endpoints.
Author: Guru Sai Prasad Reddy
"""

import pytest
from starlette.testclient import TestClient
from api.main import app
from api.store import get_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_store():
    """Ensure clean store state before each test."""
    store = get_store()
    store.clear()
    yield
    store.clear()


@pytest.fixture
def auth_headers():
    """Obtain JWT Bearer token for admin user 'guru'."""
    res = client.post(
        "/auth/login",
        data={"username": "guru", "password": "chronosmesh"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "chronosmesh-api"
    assert data["version"] == "1.0.0"


def test_metrics_empty():
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["event_count"] == 0
    assert data["dag_nodes"] == 0
    assert data["dag_edges"] == 0
    assert data["services_tracked"] == 0


def test_auth_login_success():
    response = client.post(
        "/auth/login",
        data={"username": "guru", "password": "chronosmesh"},
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["role"] == "admin"
    assert token_data["user"]["username"] == "guru"


def test_auth_login_failure():
    response = client.post(
        "/auth/login",
        data={"username": "guru", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_auth_me_endpoint(auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "guru"
    assert data["role"] == "admin"


def test_list_scenarios(auth_headers):
    response = client.get("/api/scenarios/", headers=auth_headers)
    assert response.status_code == 200
    scenarios = response.json()
    assert isinstance(scenarios, list)
    scenario_ids = [s["id"] for s in scenarios]
    assert "order_payment_flow" in scenario_ids
    assert "concurrent_branches" in scenario_ids
    assert "diamond_pattern" in scenario_ids


def test_load_order_payment_flow_scenario(auth_headers):
    # Load the order_payment_flow scenario
    response = client.post("/api/scenarios/order_payment_flow/load", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["scenario"]["id"] == "order_payment_flow"
    assert data["event_count"] > 0
    assert len(data["dag"]["nodes"]) > 0

    # Verify DAG endpoint
    dag_res = client.get("/api/dag/", headers=auth_headers)
    assert dag_res.status_code == 200
    dag_data = dag_res.json()
    assert len(dag_data["nodes"]) == len(data["dag"]["nodes"])
    assert len(dag_data["edges"]) == len(data["dag"]["edges"])
    assert len(dag_data["roots"]) > 0

    # Verify DAG roots & leaves endpoints
    roots_res = client.get("/api/dag/roots", headers=auth_headers)
    assert roots_res.status_code == 200
    assert len(roots_res.json()["roots"]) > 0

    leaves_res = client.get("/api/dag/leaves", headers=auth_headers)
    assert leaves_res.status_code == 200
    assert len(leaves_res.json()["leaves"]) > 0

    # Verify Events endpoints
    events_res = client.get("/api/events/", headers=auth_headers)
    assert events_res.status_code == 200
    assert len(events_res.json()["events"]) == data["event_count"]

    arrival_res = client.get("/api/events/arrival", headers=auth_headers)
    assert arrival_res.status_code == 200
    assert len(arrival_res.json()["events"]) == data["event_count"]

    causal_res = client.get("/api/events/causal", headers=auth_headers)
    assert causal_res.status_code == 200
    assert len(causal_res.json()["events"]) == data["event_count"]


def test_analysis_endpoints(auth_headers):
    # First load order_payment_flow scenario
    load_res = client.post("/api/scenarios/order_payment_flow/load", headers=auth_headers)
    assert load_res.status_code == 200

    dag_res = client.get("/api/dag/", headers=auth_headers)
    nodes = dag_res.json()["nodes"]
    assert len(nodes) > 0
    node_id = nodes[-1]["id"]

    # Test Anomaly Detection
    anom_res = client.get("/api/analysis/anomalies", headers=auth_headers)
    assert anom_res.status_code == 200
    anom_data = anom_res.json()
    assert "anomalies" in anom_data
    assert "severity_summary" in anom_data
    assert "total" in anom_data

    # Test Root Cause Analysis
    rc_res = client.get(f"/api/analysis/rootcause/{node_id}", headers=auth_headers)
    assert rc_res.status_code == 200
    rc_data = rc_res.json()
    assert rc_data["failure_event_id"] == node_id
    assert "root_causes" in rc_data
    assert "critical_path" in rc_data

    # Test What-If Analysis
    whatif_res = client.post(f"/api/analysis/whatif/{node_id}", headers=auth_headers)
    assert whatif_res.status_code == 200
    wi_data = whatif_res.json()
    assert wi_data["removed_event_id"] == node_id
    assert "blast_radius_pct" in wi_data
    assert "invalidated_events" in wi_data

    # Test Benchmark
    bench_res = client.get("/api/analysis/benchmark", headers=auth_headers)
    assert bench_res.status_code == 200
    bench_data = bench_res.json()
    assert "results" in bench_data
    assert len(bench_data["results"]) == 3
    strategies = [r["strategy"] for r in bench_data["results"]]
    assert "lamport_clock" in strategies
    assert "vector_clock" in strategies
    assert "physical_time" in strategies

    # Test Graph Diff
    diff_res = client.get("/api/analysis/graphdiff", headers=auth_headers)
    assert diff_res.status_code == 200
    assert "diff" in diff_res.json()
