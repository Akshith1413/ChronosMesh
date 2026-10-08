"""
Integration tests for ChronosMesh Stage 3 Features (Traces, SSE, Frontend).
Author: Guru Sai Prasad Reddy
"""

import pytest
from starlette.testclient import TestClient
from api.main import app
from api.store import get_store

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


def test_traces_list(auth_headers):
    res = client.get("/api/traces/", headers=auth_headers)
    assert res.status_code == 200
    traces = res.json()
    assert len(traces) >= 3
    trace_ids = [t["trace_id"] for t in traces]
    assert "T-1001" in trace_ids
    assert "T-1002" in trace_ids
    assert "T-1003" in trace_ids


def test_trace_lookup_and_dag(auth_headers):
    res = client.get("/api/traces/T-1001", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["trace"]["trace_id"] == "T-1001"
    assert data["event_count"] > 0

    dag_res = client.get("/api/traces/T-1001/dag", headers=auth_headers)
    assert dag_res.status_code == 200
    dag = dag_res.json()
    assert len(dag["nodes"]) > 0
    assert len(dag["edges"]) > 0


def test_trace_timeline_and_anomalies(auth_headers):
    tl_res = client.get("/api/traces/T-1001/timeline", headers=auth_headers)
    assert tl_res.status_code == 200
    tl = tl_res.json()
    assert tl["trace_id"] == "T-1001"
    assert "arrival_order" in tl
    assert "causal_order" in tl
    assert len(tl["arrival_order"]) == len(tl["causal_order"])

    anom_res = client.get("/api/traces/T-1001/anomalies", headers=auth_headers)
    assert anom_res.status_code == 200
    anom = anom_res.json()
    assert anom["trace_id"] == "T-1001"
    assert "anomalies" in anom


def test_frontend_serving():
    res = client.get("/")
    assert res.status_code == 200
    assert "ChronosMesh" in res.text


def test_sse_stream_endpoint(auth_headers):
    # Load trace first
    client.get("/api/traces/T-1001", headers=auth_headers)
    # Connect to stream with limit
    with client.stream("GET", "/api/events/stream?limit=2") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        lines = [line for line in response.iter_lines() if line]
        assert len(lines) >= 1
        assert lines[0].startswith("data:")
