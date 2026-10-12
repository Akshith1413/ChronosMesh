"""Experiments + executions API: lifecycle, ownership isolation, idempotent ingest, security."""

import time

import pytest
from fastapi.testclient import TestClient

import api.auth as auth
from api.main import app
from api.services.execution_service import ExecutionService, set_service
from chronosmesh.config import Settings
from chronosmesh.persistence import MemoryRepository


@pytest.fixture
def svc():
    service = ExecutionService(Settings(max_experiment_events=5000), MemoryRepository())
    set_service(service)
    yield service
    service.shutdown()
    set_service(None)


@pytest.fixture
def client(svc):
    return TestClient(app)


def login(client, user, password):
    r = client.post("/auth/login", data={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return login(client, "guru", "chronosmesh")


@pytest.fixture
def analyst(client):
    return login(client, "analyst", "analyst123")


@pytest.fixture
def viewer(client):
    return login(client, "demo", "demo123")


@pytest.fixture
def other_analyst(client, monkeypatch):
    monkeypatch.setitem(auth._USERS, "analyst2", {
        "username": "analyst2", "full_name": "Second Analyst", "email": "a2@x", "role": auth.ROLE_ANALYST,
        "hashed_password": auth.pwd_context.hash("pw-two")})
    return login(client, "analyst2", "pw-two")


def wait_for(client, headers, exp_id, want=("succeeded", "failed"), timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = client.get(f"/api/experiments/{exp_id}", headers=headers).json()
        if rec["status"] in want:
            return rec
        time.sleep(0.05)
    raise AssertionError(f"experiment stuck: {rec}")


SMALL = {"name": "t", "num_services": 4, "num_events": 300, "events_per_execution": 20, "network_delay_ms": 300,
         "duplicate_rate": 0.05, "missing_rate": 0.02}


# ── experiments ────────────────────────────────────────────────────────────────
def test_experiment_full_lifecycle(client, analyst):
    r = client.post("/api/experiments", json=SMALL, headers=analyst)
    assert r.status_code == 201 and r.json()["status"] == "created"
    exp = r.json()["execution_id"]

    assert client.post(f"/api/experiments/{exp}/start", headers=analyst).status_code == 202
    rec = wait_for(client, analyst, exp)
    assert rec["status"] == "succeeded", rec
    s = rec["summary"]
    assert s["f1"]["chronosmesh"] == pytest.approx(1.0)
    assert s["f1"]["chronosmesh"] > s["f1"]["declared_only"] > s["f1"]["arrival_order"]
    assert rec["samples"] and rec["duration_seconds"] > 0

    full = client.get(f"/api/experiments/{exp}/result", headers=analyst).json()
    assert set(full["summary"]["approaches"]) == {"arrival_order", "wall_clock", "declared_only", "chronosmesh"}
    assert full["config"]["num_events"] == 300 and len(full["runs"]) == 1

    assert client.post(f"/api/experiments/{exp}/start", headers=analyst).status_code == 409   # not restartable


def test_experiment_drilldown_graph_anomalies_truth_and_explorer(client, analyst):
    exp = client.post("/api/experiments", json=SMALL, headers=analyst).json()["execution_id"]
    client.post(f"/api/experiments/{exp}/start", headers=analyst)
    wait_for(client, analyst, exp)

    samples = client.get(f"/api/experiments/{exp}/executions", headers=analyst).json()["executions"]
    assert samples and all(s["kind"] == "sample" and s["parent_id"] == exp for s in samples)
    sid = samples[0]["execution_id"]

    g = client.get(f"/api/executions/{sid}/graph", headers=analyst).json()
    assert g["nodes"] and g["edges"] and g["roots"] and "topological_order" in g
    truth = client.get(f"/api/executions/{sid}/truth", headers=analyst).json()["edges"]
    got = {(e["source"], e["target"]) for e in g["edges"]}
    assert got == {tuple(e) for e in truth}      # clocks intact -> reconstruction equals the oracle exactly

    an = client.get(f"/api/executions/{sid}/anomalies", headers=analyst).json()
    assert an["total"] == sum(an["by_type"].values()) and "by_severity" in an
    m = client.get(f"/api/executions/{sid}/metrics", headers=analyst).json()
    assert m["stats"]["events"] > 0
    assert client.post(f"/api/executions/{sid}/explore", headers=analyst).json()["events"] > 0
    # sample executions don't clutter the default listing
    listed = client.get("/api/executions", headers=analyst).json()["executions"]
    assert all(r["kind"] != "sample" for r in listed)


def test_experiment_validation(client, analyst):
    assert client.post("/api/experiments", json={**SMALL, "duplicate_rate": 0.5}, headers=analyst).status_code == 422
    assert client.post("/api/experiments", json={**SMALL, "delivery_mode": "weird"}, headers=analyst).status_code == 422
    assert client.post("/api/experiments", json={**SMALL, "bogus": 1}, headers=analyst).status_code == 422
    big = client.post("/api/experiments", json={**SMALL, "num_events": 6000}, headers=analyst)   # > deployment limit
    assert big.status_code == 422 and "limit" in big.json()["detail"]
    assert client.post("/api/experiments", json={**SMALL, "transport": "sqs"}, headers=analyst).status_code == 422


def test_experiment_options(client, viewer):
    o = client.get("/api/experiments/options", headers=viewer).json()
    assert o["limits"]["num_services"] == [2, 50] and "heavily_delayed" in o["delivery_modes"]
    assert o["transports"] == ["direct"]


# ── authentication / authorisation ─────────────────────────────────────────────
def test_unauthenticated_requests_are_rejected(client):
    for method, path in [("get", "/api/experiments"), ("post", "/api/experiments"), ("get", "/api/executions"),
                         ("get", "/api/system/status"), ("post", "/graphql")]:
        r = getattr(client, method)(path, **({"json": {"query": "{ dag }"}} if path == "/graphql" else {}))
        assert r.status_code == 401, (method, path, r.status_code)


def test_viewer_is_read_only(client, viewer):
    assert client.post("/api/experiments", json=SMALL, headers=viewer).status_code == 403
    assert client.post("/api/executions", json={"name": "x"}, headers=viewer).status_code == 403
    assert client.get("/api/experiments", headers=viewer).status_code == 200


def test_users_cannot_see_each_others_executions(client, analyst, other_analyst, admin):
    exp = client.post("/api/experiments", json=SMALL, headers=analyst).json()["execution_id"]
    ex = client.post("/api/executions", json={"name": "private"}, headers=analyst).json()["execution_id"]
    for path in (f"/api/experiments/{exp}", f"/api/experiments/{exp}/result", f"/api/executions/{ex}",
                 f"/api/executions/{ex}/graph", f"/api/executions/{ex}/anomalies", f"/api/executions/{ex}/events"):
        assert client.get(path, headers=other_analyst).status_code == 404, path    # 404, not 403: existence not leaked
    assert client.post(f"/api/experiments/{exp}/start", headers=other_analyst).status_code == 404
    assert client.post(f"/api/executions/{ex}/events", json={"events": [{"event_id": "e"}]},
                       headers=other_analyst).status_code == 404
    assert client.get("/api/executions", headers=other_analyst).json()["executions"] == []
    # admins can see everything
    assert client.get(f"/api/experiments/{exp}", headers=admin).status_code == 200
    assert {r["execution_id"] for r in client.get("/api/executions", headers=admin).json()["executions"]} >= {ex}


# ── live ingestion ─────────────────────────────────────────────────────────────
def ev(eid, svc, vc, parents=(), lamport=1, etime="2026-10-09T11:00:02Z", **kw):
    return {"event_id": eid, "service": svc, "event_type": "STEP", "parent_event_ids": list(parents),
            "lamport_clock": lamport, "vector_clock": vc, "event_time": etime, **kw}


def test_live_ingest_out_of_order_duplicates_and_invalid(client, analyst):
    ex = client.post("/api/executions", json={"name": "orders"}, headers=analyst).json()["execution_id"]
    order = ev("o1", "order-service", {"order-service": 1})
    pay = ev("p1", "payment-service", {"order-service": 1, "payment-service": 1}, ["o1"], lamport=2)

    # the child arrives before its parent
    r = client.post(f"/api/executions/{ex}/events", json={"events": [pay]}, headers=analyst).json()
    assert r["accepted"] == 1 and r["mode"] == "inline"
    g = client.get(f"/api/executions/{ex}/graph", headers=analyst).json()
    assert g["edges"] == [] and g["unresolved"] == {"o1": ["p1"]}
    types = {a["anomaly_type"] for a in client.get(f"/api/executions/{ex}/anomalies", headers=analyst).json()["anomalies"]}
    assert {"UNRESOLVED_PARENT", "ORPHAN_EVENT"} <= types

    # parent arrives (plus a duplicate of it and an invalid event)
    r = client.post(f"/api/executions/{ex}/events", json={"events": [order, order, {"event_id": "bad"}]},
                    headers=analyst).json()
    assert (r["accepted"], r["duplicates"]) == (1, 1)
    assert r["rejected"] == [{"index": 2, "reason": "'event_type' is required"}]

    g = client.get(f"/api/executions/{ex}/graph", headers=analyst).json()
    assert [(e["source"], e["target"]) for e in g["edges"]] == [("o1", "p1")] and g["unresolved"] == {}
    an = client.get(f"/api/executions/{ex}/anomalies", headers=analyst).json()
    assert an["by_type"].get("DUPLICATE_EVENT") == 1 and "UNRESOLVED_PARENT" not in an["by_type"]
    assert client.get(f"/api/executions/{ex}/metrics", headers=analyst).json()["stats"]["duplicates"] == 1


def test_ingest_validation_rules(client, analyst):
    ex = client.post("/api/executions", json={}, headers=analyst).json()["execution_id"]
    post = lambda events: client.post(f"/api/executions/{ex}/events", json={"events": events}, headers=analyst)
    bad = post([ev("a", "s", {"s": -1}), ev("b", "s", {"s": "x"}), {**ev("c", "s", {}), "parent_event_ids": "p"},
                {"event_id": "d", "event_type": "T"}])
    assert bad.status_code == 200
    body = bad.json()
    assert body["accepted"] == 0 and [r["index"] for r in body["rejected"]] == [0, 1, 2, 3]
    assert "vector_clock" in body["rejected"][0]["reason"] and "parent_event_ids" in body["rejected"][2]["reason"]
    assert "service" in body["rejected"][3]["reason"]
    assert post(["not-an-object"]).status_code == 422          # malformed envelope is rejected outright
    assert post([]).status_code == 422
    assert post([ev(f"e{i}", "s", {"s": i + 1}) for i in range(1001)]).status_code == 422


def test_server_stamps_execution_and_ingestion_time(client, analyst):
    ex = client.post("/api/executions", json={}, headers=analyst).json()["execution_id"]
    before = time.time() * 1000
    client.post(f"/api/executions/{ex}/events", headers=analyst, json={"events": [
        ev("a", "s1", {"s1": 1}, execution_id="somebody-elses", ingestion_time="2001-01-01T00:00:00Z")]})
    e = client.get(f"/api/executions/{ex}/events", headers=analyst).json()["events"][0]
    assert e["execution_id"] == ex                       # the URL decides, not the payload
    assert e["arrival_time_ms"] >= before                # ingestion time is the platform's own clock


def test_live_execution_survives_engine_eviction(client, analyst, svc):
    ex = client.post("/api/executions", json={}, headers=analyst).json()["execution_id"]
    client.post(f"/api/executions/{ex}/events", headers=analyst, json={"events": [
        ev("a", "s1", {"s1": 1}), ev("b", "s2", {"s1": 1, "s2": 1}, ["a"], lamport=2)]})
    svc._engines.clear()                                  # e.g. API restart / another replica
    g = client.get(f"/api/executions/{ex}/graph", headers=analyst).json()
    assert [(e["source"], e["target"]) for e in g["edges"]] == [("a", "b")]


# ── platform ───────────────────────────────────────────────────────────────────
def test_system_status_and_readiness(client, analyst):
    s = client.get("/api/system/status", headers=analyst).json()
    assert s["storage"]["ok"] and s["ingest_mode"] == "inline" and s["queue"] is None
    r = client.get("/api/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert client.get("/api/health").json()["status"] == "healthy"


def test_prometheus_exposes_the_blueprint_metric_names(client, analyst):
    ex = client.post("/api/executions", json={}, headers=analyst).json()["execution_id"]
    client.post(f"/api/executions/{ex}/events", headers=analyst, json={"events": [ev("a", "s1", {"s1": 1})] * 2})
    client.get(f"/api/executions/{ex}/graph", headers=analyst)
    text = client.get("/metrics").text
    for name in ("chronosmesh_events_received_total", "chronosmesh_events_processed_total",
                 "chronosmesh_events_duplicate_total", "chronosmesh_unresolved_dependencies",
                 "chronosmesh_reconstruction_duration_seconds_bucket", "chronosmesh_queue_oldest_message_age_seconds",
                 "chronosmesh_graph_nodes", "chronosmesh_graph_edges", "chronosmesh_processing_errors_total"):
        assert name in text, name


def test_metrics_endpoint_can_require_a_bearer_token(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "scrape-me")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer scrape-me"}).status_code == 200


def test_cors_allow_list_not_wildcard(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    evil = client.options("/api/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil.headers
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_security_headers_present(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_graphql_requires_auth_and_resolves_real_data(client, analyst):
    assert client.post("/graphql", json={"query": "{ dag }"}).status_code == 401
    client.post("/api/scenarios/diamond_pattern/load", headers=analyst)
    r = client.post("/graphql", json={"query": "{ concurrency { scenario concurrent_pairs } }"}, headers=analyst).json()
    pairs = r["data"]["concurrency"]["concurrent_pairs"]
    assert pairs, "concurrent_pairs used to be silently empty (store method was missing)"
    t = client.post("/graphql", json={"query": "{ timeline }"}, headers=analyst).json()["data"]["timeline"]
    assert len(t["causal_order"]) == len(t["arrival_order"]) > 0


# ── explorer isolation ─────────────────────────────────────────────────────────
def test_explore_loads_into_a_private_store_other_users_cannot_see(client, analyst, other_analyst, admin, svc):
    import api.store as store_mod
    store_mod._user_stores.clear()
    exp = client.post("/api/experiments", json=SMALL, headers=analyst).json()["execution_id"]
    client.post(f"/api/experiments/{exp}/start", headers=analyst)
    wait_for(client, analyst, exp)
    sample = client.get(f"/api/experiments/{exp}/executions", headers=analyst).json()["executions"][0]["execution_id"]

    assert client.post(f"/api/executions/{sample}/explore", headers=analyst).json()["events"] > 0
    mine = client.get("/api/events/", headers=analyst).json()
    assert mine["count"] > 0 and mine["scenario"] == f"exec:{sample}"
    # nobody else sees it through the legacy endpoints (they keep the shared demo store)
    theirs = client.get("/api/events/", headers=other_analyst).json()
    assert theirs["scenario"] != f"exec:{sample}"
    assert client.get("/api/metrics", headers=admin).json()["current_scenario"] != f"exec:{sample}"
    assert client.get("/api/metrics", headers=analyst).json()["current_scenario"] == f"exec:{sample}"
    # and another user cannot explore it at all
    assert client.post(f"/api/executions/{sample}/explore", headers=other_analyst).status_code == 404
    store_mod._user_stores.clear()


def test_event_stream_requires_a_valid_token(client, analyst):
    assert client.get("/api/events/stream?limit=1").status_code == 401
    assert client.get("/api/events/stream?limit=1&token=garbage").status_code == 401
    token = analyst["Authorization"].split()[1]
    r = client.get(f"/api/events/stream?limit=1&token={token}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")


def test_json_metrics_require_authentication_but_prometheus_text_does_not(client, analyst):
    assert client.get("/api/metrics").status_code == 401
    assert client.get("/api/metrics/json").status_code == 401
    assert client.get("/api/metrics", headers=analyst).status_code == 200
    prom = client.get("/api/metrics", headers={"Accept": "text/plain"})
    assert prom.status_code == 200 and "chronosmesh_" in prom.text


def test_documented_example_events_reconstruct_the_blueprint_dag(client, analyst):
    """examples/events.json is delivered out of order on purpose; the README promises this exact graph."""
    import json, pathlib
    payload = json.loads((pathlib.Path(__file__).resolve().parents[2] / "examples" / "events.json").read_text())
    ex = client.post("/api/executions", json={"name": "readme"}, headers=analyst).json()["execution_id"]
    r = client.post(f"/api/executions/{ex}/events", json=payload, headers=analyst).json()
    assert r["accepted"] == 6 and r["rejected"] == []
    g = client.get(f"/api/executions/{ex}/graph", headers=analyst).json()
    edges = {(e["source"], e["target"]) for e in g["edges"]}
    assert edges == {("evt-order-created", "evt-payment-start"), ("evt-order-created", "evt-stock-check"),
                     ("evt-payment-start", "evt-payment-done"), ("evt-stock-check", "evt-stock-reserved"),
                     ("evt-payment-done", "evt-shipping"), ("evt-stock-reserved", "evt-shipping")}
    assert g["unresolved"] == {} and g["roots"] == ["evt-order-created"] and g["leaves"] == ["evt-shipping"]
    # payment and inventory branches are concurrent: neither reaches the other
    reach = {(e["source"], e["target"]) for e in g["edges"]}
    assert ("evt-payment-start", "evt-stock-check") not in reach and ("evt-stock-check", "evt-payment-start") not in reach
