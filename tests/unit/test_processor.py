import pytest
from chronosmesh.events.event import Event
from chronosmesh.stream.processor import StreamProcessor

def test_stream_processor_process_event():
    processor = StreamProcessor()
    e = Event(event_id="E1", vector_clock={"a":1})
    res = processor.process_event(e)
    assert res["dag_nodes"] == 1
    assert processor.get_statistics()["processed_events"] == 1

def test_stream_processor_process_batch():
    processor = StreamProcessor()
    events = [Event(event_id=f"E{i}", vector_clock={"a":i}) for i in range(1, 4)]
    res = processor.process_batch(events)
    assert res["dag_nodes"] == 3
    assert processor.get_statistics()["processed_events"] == 3

def test_stream_processor_get_dag():
    processor = StreamProcessor()
    processor.process_event(Event(event_id="E1", vector_clock={"a":1}))
    dag = processor.get_dag()
    assert len(dag.nodes) == 1

def test_stream_processor_get_anomalies():
    processor = StreamProcessor()
    assert processor.get_anomalies() == []

def test_stream_processor_flush():
    processor = StreamProcessor()
    processor.flush()
    # just testing that it doesn't raise exception

def test_stream_processor_reset():
    processor = StreamProcessor()
    processor.process_event(Event(event_id="E1", vector_clock={"a":1}))
    processor.reset()
    assert processor.get_statistics()["processed_events"] == 0
    
def test_stream_processor_callbacks():
    handled = []
    processor = StreamProcessor(event_callback=lambda x: handled.append(x))
    processor.process_event(Event(event_id="E1", vector_clock={"a":1}))
    assert len(handled) == 1


# ── The anomaly/confidence stages used to be dead code (imported a non-existent module) ──
def _ev(eid, svc, vc, parents=(), ts=0.0, lamport=0):
    return Event(event_id=eid, service_id=svc, vector_clock=vc, parent_event_ids=list(parents),
                 timestamp_ms=ts, lamport_ts=lamport)


def test_stream_processor_reports_unresolved_parent_then_links_late_parent():
    seen = []
    p = StreamProcessor(anomaly_callback=seen.append)
    child = _ev("c", "s2", {"s1": 1, "s2": 1}, parents=["a"], lamport=2)
    r = p.process_event(child)
    assert {a["anomaly_type"] for a in r["anomalies"]} >= {"UNRESOLVED_PARENT", "ORPHAN_EVENT"}
    assert r["dag_edges"] == 0 and r["unresolved_parents"] == 1
    r2 = p.process_event(_ev("a", "s1", {"s1": 1}, lamport=1))
    assert r2["dag_edges"] == 1 and r2["unresolved_parents"] == 0
    assert seen, "anomaly_callback must fire"


def test_stream_processor_is_idempotent_for_duplicates():
    p = StreamProcessor()
    e = _ev("a", "s1", {"s1": 1})
    p.process_event(e)
    r = p.process_event(e)
    assert r["duplicate"] is True and r["dag_nodes"] == 1
    assert [a["anomaly_type"] for a in r["anomalies"]] == ["DUPLICATE_EVENT"]
    assert p.get_statistics()["duplicates"] == 1


def test_stream_processor_flags_causal_violation():
    p = StreamProcessor()
    p.process_event(_ev("a", "s1", {"s1": 5}, ts=1000.0, lamport=5))
    r = p.process_event(_ev("b", "s2", {"s2": 1}, parents=["a"], ts=100.0, lamport=1))
    types = {a["anomaly_type"] for a in r["anomalies"]}
    assert "CAUSAL_VIOLATION" in types


def test_stream_processor_scores_edge_confidence():
    p = StreamProcessor(enable_anomaly_detection=False)
    p.process_event(_ev("a", "s1", {"s1": 1}, ts=1000.0, lamport=1))
    r = p.process_event(_ev("b", "s2", {"s1": 1, "s2": 1}, parents=["a"], ts=1001.0, lamport=2))
    assert r["low_confidence_edges"] == []
