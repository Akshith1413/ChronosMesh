"""
Unit and Integration tests for ChronosMesh Advanced Analysis APIs and Service layer:
- GET /api/analysis/service-health
- GET /api/analysis/clock-drift-timeline
- GET /api/analysis/latency-histogram
- GET /api/analysis/topology-stats
- GET /api/analysis/event-replay
"""

import pytest
from starlette.testclient import TestClient
from api.main import app
from api.store import get_store
from api.routers.scenarios_router import _build_scenario

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_store():
    store = get_store()
    store.clear()
    yield
    store.clear()


@pytest.fixture
def auth_headers():
    res = client.post(
        "/auth/login",
        data={"username": "guru", "password": "chronosmesh"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def loaded_store():
    store = get_store()
    events, arrival_ids = _build_scenario("ecommerce_demo")
    store.load_scenario("ecommerce_demo", events, arrival_ids)
    return store


# ── Auth & Permission Guard Tests ─────────────────────────────────────────────

def test_endpoints_require_authentication():
    for endpoint in [
        "/api/analysis/service-health",
        "/api/analysis/clock-drift-timeline",
        "/api/analysis/latency-histogram",
        "/api/analysis/topology-stats",
        "/api/analysis/event-replay",
    ]:
        res = client.get(endpoint)
        assert res.status_code == 401, f"Expected 401 for unauthenticated {endpoint}"


# ── 1. Service Health Tests ───────────────────────────────────────────────────

def test_service_health_empty(auth_headers):
    res = client.get("/api/analysis/service-health", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_services"] == 0
    assert data["services"] == []
    assert data["healthy_count"] == 0


def test_service_health_deterministic_status(auth_headers, loaded_store):
    res = client.get("/api/analysis/service-health", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_services"] > 0
    service_names = [s["service_name"] for s in data["services"]]
    assert len(service_names) == data["total_services"]

    for s in data["services"]:
        assert s["status"] in ["Healthy", "Degraded", "Critical", "Unavailable"]
        assert s["event_count"] >= 0
        assert s["anomaly_count"] >= 0
        if s["event_count"] > 0:
            assert s["latest_activity_ms"] is not None


# ── 2. Clock Drift Timeline Tests ─────────────────────────────────────────────

def test_clock_drift_timeline_empty(auth_headers):
    res = client.get("/api/analysis/clock-drift-timeline", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["data_points"] == []
    assert data["max_arrival_skew_ms"] == 0.0


def test_clock_drift_timeline_semantics(auth_headers, loaded_store):
    res = client.get("/api/analysis/clock-drift-timeline", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["data_points"]) == len(loaded_store.events)

    for pt in data["data_points"]:
        # Verify physical timestamps are preserved
        assert pt["timestamp_ms"] > 0
        assert pt["arrival_time_ms"] > 0
        # Arrival skew is defined as arrival_time_ms - timestamp_ms
        expected_skew = round(pt["arrival_time_ms"] - pt["timestamp_ms"], 3)
        assert abs(pt["arrival_skew_ms"] - expected_skew) < 0.01
        assert pt["clock_type"] == "physical"

    # Verify methodology documentation in response
    assert "Logical clocks" in data["methodology"]


# ── 3. Latency Histogram Tests ────────────────────────────────────────────────

def test_latency_histogram_empty(auth_headers):
    res = client.get("/api/analysis/latency-histogram", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["sample_size"] == 0
    assert data["bins"] == []
    assert data["note"] is not None


def test_latency_histogram_valid_dag(auth_headers, loaded_store):
    res = client.get("/api/analysis/latency-histogram?bins=4", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["sample_size"] >= 0
    if data["sample_size"] > 0:
        assert data["p50_ms"] is not None
        assert data["p95_ms"] is not None
        assert data["p99_ms"] is not None
        assert data["min_ms"] <= data["p50_ms"] <= data["max_ms"]
        assert len(data["bins"]) <= 4
        total_binned = sum(b["count"] for b in data["bins"])
        assert total_binned == data["sample_size"]


# ── 4. Topology Stats Tests ───────────────────────────────────────────────────

def test_topology_stats_empty(auth_headers):
    res = client.get("/api/analysis/topology-stats", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["node_count"] == 0
    assert data["edge_count"] == 0
    assert data["density"] == 0.0
    assert data["is_connected"] is False


def test_topology_stats_dag_metrics(auth_headers, loaded_store):
    res = client.get("/api/analysis/topology-stats", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["node_count"] == loaded_store.dag.number_of_nodes()
    assert data["edge_count"] == loaded_store.dag.number_of_edges()
    assert 0.0 <= data["density"] <= 1.0
    assert len(data["root_nodes"]) >= 1
    assert len(data["leaf_nodes"]) >= 1
    assert data["longest_causal_path"]["length"] >= 1
    assert 0.0 <= data["concurrency_ratio"] <= 1.0


# ── 5. Event Replay Tests ─────────────────────────────────────────────────────

def test_event_replay_empty(auth_headers):
    res = client.get("/api/analysis/event-replay", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_layers"] == 0
    assert data["total_events"] == 0
    assert data["layers"] == []


def test_event_replay_causal_layers(auth_headers, loaded_store):
    res = client.get("/api/analysis/event-replay", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_layers"] > 0
    assert data["total_events"] == loaded_store.dag.number_of_nodes()
    assert data["max_parallelism"] >= 1

    seen_events = set()
    for layer in data["layers"]:
        assert layer["concurrent_count"] == len(layer["events"])
        for evt in layer["events"]:
            assert evt["event_id"] not in seen_events
            seen_events.add(evt["event_id"])
            assert evt["service_id"] is not None
