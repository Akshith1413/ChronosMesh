import pytest
from chronosmesh.events.event import Event
from chronosmesh.causality.happens_before import HappensBeforeDetector
from chronosmesh.clocks.base import CausalRelation
from chronosmesh.events.generator import ScenarioBuilder

def test_happens_before_with_vector_clocks():
    detector = HappensBeforeDetector()
    e1 = Event(event_id="1", vector_clock={"A": 1, "B": 0})
    e2 = Event(event_id="2", vector_clock={"A": 1, "B": 1})
    assert detector.detect(e1, e2) == CausalRelation.HAPPENS_BEFORE

def test_happens_after_with_vector_clocks():
    detector = HappensBeforeDetector()
    e1 = Event(event_id="1", vector_clock={"A": 1, "B": 1})
    e2 = Event(event_id="2", vector_clock={"A": 1, "B": 0})
    assert detector.detect(e1, e2) == CausalRelation.HAPPENS_AFTER

def test_concurrent_events():
    detector = HappensBeforeDetector()
    e1 = Event(event_id="1", vector_clock={"A": 1, "B": 0})
    e2 = Event(event_id="2", vector_clock={"A": 0, "B": 1})
    assert detector.detect(e1, e2) == CausalRelation.CONCURRENT

def test_equal_events():
    detector = HappensBeforeDetector()
    e1 = Event(event_id="1", vector_clock={"A": 1})
    e2 = Event(event_id="1", vector_clock={"A": 1})
    assert detector.detect(e1, e2) == CausalRelation.EQUAL

def test_detect_all_pairwise():
    detector = HappensBeforeDetector()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    results = detector.detect_all(events)
    assert len(results) == 3 # (0,1), (0,2), (1,2)
    assert all(r[2] == CausalRelation.HAPPENS_BEFORE for r in results)

def test_build_relation_set():
    detector = HappensBeforeDetector()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    rel_set = detector.build_relation_set(events)
    assert len(rel_set) == 3

def test_three_service_ordering_scenario():
    detector = HappensBeforeDetector()
    sb = ScenarioBuilder()
    events = sb.order_payment_flow()
    e1 = events[0]
    e2 = events[-1]
    assert detector.detect(e1, e2) == CausalRelation.HAPPENS_BEFORE

def test_fallback_to_lamport():
    detector = HappensBeforeDetector()
    e1 = Event(event_id="a", lamport_ts=1, vector_clock={})
    e2 = Event(event_id="b", lamport_ts=2, vector_clock={})
    assert detector.detect(e1, e2) == CausalRelation.HAPPENS_BEFORE
