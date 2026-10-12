"""Vector-clock reconstruction: correctness against an independent oracle, plus edge cases."""

import random

import networkx as nx
import pytest

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.reconstruction import ACCEPTED, DUPLICATE, CapacityError, ReconstructionEngine, reconstruct
from chronosmesh.simulator import ExperimentConfig, generate_workload


def ev(eid, svc, vc, parents=(), lamport=0, ts=0.0, execution="x1", arrival=None):
    return Event(event_id=eid, service_id=svc, event_type="T", vector_clock=dict(vc),
                 parent_event_ids=list(parents), lamport_ts=lamport, timestamp_ms=ts,
                 trace_id=execution, execution_id=execution,
                 arrival_time_ms=ts if arrival is None else arrival)


def oracle_edges(events):
    """Independent derivation: program order + declared triggers -> NetworkX transitive reduction.

    Uses neither vector-clock arithmetic nor the code under test.
    """
    g = nx.DiGraph()
    last = {}
    for e in events:  # generation order
        g.add_node(e.event_id)
        if e.service_id in last:
            g.add_edge(last[e.service_id], e.event_id)
        for p in e.parent_event_ids:
            g.add_edge(p, e.event_id)
        last[e.service_id] = e.event_id
    return set(nx.transitive_reduction(g).edges())


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("services", [3, 4, 8])
def test_matches_independent_oracle(seed, services):
    cfg = ExperimentConfig(num_services=services, num_events=300, events_per_execution=60).validate()
    gt = generate_workload(cfg, seed)
    for evs in gt.executions.values():
        got = set(reconstruct(evs, use_explicit=False).dag.edges())
        assert got == oracle_edges(evs)


def test_explicit_plus_vector_clock_matches_oracle_too():
    cfg = ExperimentConfig(num_services=5, num_events=200, events_per_execution=50).validate()
    gt = generate_workload(cfg, 11)
    for evs in gt.executions.values():
        assert set(reconstruct(evs).dag.edges()) == oracle_edges(evs)


def test_result_independent_of_arrival_order():
    cfg = ExperimentConfig(num_services=4, num_events=120, events_per_execution=120).validate()
    evs = next(iter(generate_workload(cfg, 7).executions.values()))
    baseline = set(reconstruct(evs).dag.edges())
    rng = random.Random(0)
    for _ in range(5):
        shuffled = list(evs)
        rng.shuffle(shuffled)
        assert set(reconstruct(shuffled).dag.edges()) == baseline


def test_dag_is_acyclic_and_transitively_reduced():
    cfg = ExperimentConfig(num_services=6, num_events=150, events_per_execution=150).validate()
    evs = next(iter(generate_workload(cfg, 9).executions.values()))
    dag = reconstruct(evs).dag
    assert nx.is_directed_acyclic_graph(dag)
    assert set(nx.transitive_reduction(dag).edges()) == set(dag.edges())


def test_unresolved_parent_is_reported_not_invented():
    a = ev("a", "s1", {"s1": 1})
    c = ev("c", "s2", {"s1": 1, "s2": 1}, parents=["a", "ghost"])
    res = reconstruct([c, a])
    assert res.unresolved == {"ghost": ["c"]}
    assert set(res.dag.edges()) == {("a", "c")}
    assert "ghost" not in res.dag


def test_edge_bridging_a_lost_event_is_flagged_as_gap():
    a = ev("a", "s1", {"s1": 1})
    b = ev("b", "s1", {"s1": 2})          # lost
    c = ev("c", "s2", {"s1": 2, "s2": 1})  # saw b
    res = reconstruct([a, c])
    assert set(res.dag.edges()) == {("a", "c")}
    attrs = res.dag.edges["a", "c"]
    assert attrs["inferred"] and attrs["via_gap"]


def test_contradictory_declared_parent_is_rejected():
    a = ev("a", "s1", {"s1": 5})
    b = ev("b", "s2", {"s2": 1}, parents=["a"])     # b's clock never saw a
    res = reconstruct([a, b])
    assert not res.dag.has_edge("a", "b")
    assert res.rejected_declared and res.rejected_declared[0][:2] == ("a", "b")


def test_event_without_vector_clock_uses_declared_parents_unverified():
    a = ev("a", "s1", {"s1": 1})
    b = ev("b", "s2", {}, parents=["a"])
    res = reconstruct([a, b])
    assert res.dag.edges["a", "b"]["verified"] is False
    assert res.stats["unverified_edges"] == 1


def test_duplicates_collapse_to_one_node():
    a = ev("a", "s1", {"s1": 1})
    res = reconstruct([a, a, a])
    assert res.dag.number_of_nodes() == 1 and len(res.duplicates) == 2


def test_cycle_from_bad_metadata_is_broken_and_reported():
    a = ev("a", "s1", {}, parents=["b"])
    b = ev("b", "s2", {}, parents=["a"])
    res = reconstruct([a, b])
    assert nx.is_directed_acyclic_graph(res.dag)
    assert any(r[2] == "edge closes a cycle" for r in res.rejected_declared)


def test_vector_clocks_prove_concurrency():
    root = ev("o", "order", {"order": 1})
    pay = ev("p", "payment", {"order": 1, "payment": 1}, parents=["o"])
    inv = ev("i", "inventory", {"order": 1, "inventory": 1}, parents=["o"])
    dag = reconstruct([root, pay, inv]).dag
    assert not nx.has_path(dag, "p", "i") and not nx.has_path(dag, "i", "p")


# ── Engine ────────────────────────────────────────────────────────────────────
def test_engine_is_idempotent_and_counts_duplicates():
    eng = ReconstructionEngine("x1")
    a = ev("a", "s1", {"s1": 1})
    assert eng.ingest(a) == ACCEPTED
    assert eng.ingest(a) == DUPLICATE
    assert eng.event_count == 1 and eng.counters["duplicate"] == 1
    types = [x.anomaly_type for x in eng.anomalies()]
    assert "DUPLICATE_EVENT" in types


def test_engine_links_late_parent_automatically():
    eng = ReconstructionEngine("x1")
    a = ev("a", "s1", {"s1": 1})
    c = ev("c", "s2", {"s1": 1, "s2": 1}, parents=["a"])
    eng.ingest(c)
    assert eng.stats()["unresolved_parents"] == 1 and eng.dag.number_of_edges() == 0
    eng.ingest(a)
    assert eng.stats()["unresolved_parents"] == 0
    assert set(eng.dag.edges()) == {("a", "c")}


def test_engine_rejects_invalid_and_enforces_capacity():
    eng = ReconstructionEngine("x1", max_events=1)
    with pytest.raises(ValueError):
        eng.ingest(Event(event_id="", service_id="s"))
    eng.ingest(ev("a", "s1", {"s1": 1}))
    with pytest.raises(CapacityError):
        eng.ingest(ev("b", "s1", {"s1": 2}))


def test_engine_checkpoint_restore_roundtrip():
    cfg = ExperimentConfig(num_services=4, num_events=60, events_per_execution=60).validate()
    evs = next(iter(generate_workload(cfg, 5).executions.values()))
    eng = ReconstructionEngine("x1")
    eng.ingest_many(evs)
    clone = ReconstructionEngine.restore("x1", eng.checkpoint())
    assert set(clone.dag.edges()) == set(eng.dag.edges())


def test_snapshot_shape_matches_dashboard_contract():
    eng = ReconstructionEngine("x1")
    eng.ingest_many([ev("a", "s1", {"s1": 1}), ev("b", "s2", {"s1": 1, "s2": 1}, parents=["a"])])
    snap = eng.snapshot()
    assert {n["id"] for n in snap["nodes"]} == {"a", "b"}
    assert snap["edges"][0]["source"] == "a" and snap["edges"][0]["target"] == "b"
    assert snap["roots"] == ["a"] and snap["leaves"] == ["b"] and snap["topological_order"] == ["a", "b"]
    assert snap["truncated"] is False


def test_snapshot_truncates_large_graphs():
    eng = ReconstructionEngine("x1")
    for i in range(1, 30):
        eng.ingest(ev(f"e{i}", "s1", {"s1": i}))
    snap = eng.snapshot(max_nodes=10)
    assert snap["truncated"] and len(snap["nodes"]) == 10 and snap["total_nodes"] == 29
