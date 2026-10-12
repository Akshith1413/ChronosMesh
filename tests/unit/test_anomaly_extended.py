"""The anomaly types added on top of the original three."""

import networkx as nx

from chronosmesh.analysis.anomaly import CausalAnomalyDetector
from chronosmesh.events.event import Event
from chronosmesh.reconstruction import reconstruct


def E(eid, svc="s1", vc=None, parents=(), lamport=0, ts=0.0, arrival=0.0, payload=None, etype="T"):
    return Event(event_id=eid, service_id=svc, event_type=etype, vector_clock=vc or {}, parent_event_ids=list(parents),
                 lamport_ts=lamport, timestamp_ms=ts, arrival_time_ms=arrival, payload=payload or {})


def types(found):
    return [a.anomaly_type for a in found]


def test_vector_clock_gap_detects_lost_event():
    found = CausalAnomalyDetector().detect_vector_clock_gaps([E("a", vc={"s1": 1}), E("c", vc={"s1": 3})])
    assert types(found) == ["VECTOR_CLOCK_GAP"] and found[0].details["missing_counters"] == [2]


def test_vector_clock_without_gap_is_clean():
    assert CausalAnomalyDetector().detect_vector_clock_gaps([E("a", vc={"s1": 1}), E("b", vc={"s1": 2})]) == []


def test_clock_drift_flags_proven_lag_beyond_tolerance():
    parent = E("p", "s1", ts=10_000.0)
    child = E("c", "s2", parents=["p"], ts=8_000.0)   # child clock lags by >= 2000 ms
    found = CausalAnomalyDetector(max_clock_drift_ms=500).detect_clock_drift([parent, child])
    assert types(found) == ["CLOCK_DRIFT"] and found[0].details["min_offset_ms"] == 2000.0


def test_clock_drift_ignores_small_skew():
    parent = E("p", "s1", ts=1000.0)
    child = E("c", "s2", parents=["p"], ts=900.0)
    assert CausalAnomalyDetector(max_clock_drift_ms=500).detect_clock_drift([parent, child]) == []


def test_unresolved_parent_and_orphan():
    c = E("c", parents=["ghost"])
    d = CausalAnomalyDetector()
    assert types(d.detect_unresolved_parents([c])) == ["UNRESOLVED_PARENT"]
    assert types(d.detect_orphans([c])) == ["ORPHAN_EVENT"]


def test_orphan_not_reported_when_one_parent_is_known():
    a, c = E("a"), E("c", parents=["a", "ghost"])
    assert CausalAnomalyDetector().detect_orphans([a, c]) == []


def test_causal_violation_when_parent_clock_not_dominated():
    a = E("a", "s1", vc={"s1": 5}, lamport=5)
    b = E("b", "s2", vc={"s2": 1}, lamport=6, parents=["a"])
    assert types(CausalAnomalyDetector().detect_causal_violations([a, b])) == ["CAUSAL_VIOLATION"]


def test_causal_violation_on_lamport_regression():
    a = E("a", "s1", vc={"s1": 1}, lamport=9)
    b = E("b", "s2", vc={"s1": 1, "s2": 1}, lamport=3, parents=["a"])
    assert types(CausalAnomalyDetector().detect_causal_violations([a, b])) == ["CAUSAL_VIOLATION"]


def test_valid_dependency_is_not_a_violation():
    a = E("a", "s1", vc={"s1": 1}, lamport=1)
    b = E("b", "s2", vc={"s1": 1, "s2": 1}, lamport=2, parents=["a"])
    assert CausalAnomalyDetector().detect_causal_violations([a, b]) == []


def test_retry_storm_threshold_and_severity():
    evs = [E(f"r{i}", payload={"attempt": 2, "retry_of": "op1"}, etype="CHARGE") for i in range(5)]
    found = CausalAnomalyDetector(retry_storm_threshold=5).detect_retry_storms(evs)
    assert types(found) == ["RETRY_STORM"] and found[0].severity == "WARNING"
    many = [E(f"r{i}", payload={"retry_of": "op1"}, etype="CHARGE") for i in range(15)]
    assert CausalAnomalyDetector(retry_storm_threshold=5).detect_retry_storms(many)[0].severity == "CRITICAL"
    assert CausalAnomalyDetector(retry_storm_threshold=5).detect_retry_storms(evs[:3]) == []


def test_late_arrival_when_parent_arrives_after_child():
    p = E("p", arrival=200.0)
    c = E("c", parents=["p"], arrival=100.0)
    found = CausalAnomalyDetector().detect_late_arrivals([p, c])
    assert types(found) == ["LATE_ARRIVAL"] and found[0].details["lateness_ms"] == 100.0
    assert CausalAnomalyDetector().detect_late_arrivals([E("p", arrival=1.0), E("c", parents=["p"], arrival=2.0)]) == []


def test_concurrent_mutation_on_shared_resource():
    root = E("o", "order", vc={"order": 1})
    a = E("a", "payment", vc={"order": 1, "payment": 1}, parents=["o"], payload={"resource": "acct-1", "op": "write"})
    b = E("b", "inventory", vc={"order": 1, "inventory": 1}, parents=["o"], payload={"resource": "acct-1", "op": "write"})
    res = reconstruct([root, a, b])
    found = CausalAnomalyDetector().detect_concurrent_mutations(res.dag, [root, a, b])
    assert types(found) == ["CONCURRENT_MUTATION"]


def test_ordered_mutations_are_fine_and_reads_ignored():
    a = E("a", "payment", vc={"payment": 1}, payload={"resource": "acct-1", "op": "write"})
    b = E("b", "inventory", vc={"payment": 1, "inventory": 1}, parents=["a"], payload={"resource": "acct-1", "op": "write"})
    c = E("c", "shipping", vc={"shipping": 1}, payload={"resource": "acct-1", "op": "read"})
    res = reconstruct([a, b, c])
    assert CausalAnomalyDetector().detect_concurrent_mutations(res.dag, [a, b, c]) == []


def test_detect_all_includes_new_detectors_without_events_argument():
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=1)
    assert CausalAnomalyDetector().detect_all(dag) == []
