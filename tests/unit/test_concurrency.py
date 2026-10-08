import pytest
from chronosmesh.events.event import Event
from chronosmesh.causality.concurrency import ConcurrencyDetector
from chronosmesh.events.generator import ScenarioBuilder

def test_detect_concurrent_pair():
    detector = ConcurrencyDetector()
    e1 = Event(event_id="1", vector_clock={"A": 1, "B": 0})
    e2 = Event(event_id="2", vector_clock={"A": 0, "B": 1})
    assert detector.is_concurrent(e1, e2) is True

def test_no_concurrent_in_chain():
    detector = ConcurrencyDetector()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    pairs = detector.detect_concurrent_pairs(events)
    assert len(pairs) == 0

def test_concurrent_branches():
    detector = ConcurrencyDetector()
    sb = ScenarioBuilder()
    events = sb.concurrent_branches()
    pairs = detector.detect_concurrent_pairs(events)
    assert len(pairs) == 1

def test_find_concurrent_groups():
    detector = ConcurrencyDetector()
    sb = ScenarioBuilder()
    events = sb.concurrent_branches()
    groups = detector.find_concurrent_groups(events)
    assert len(groups) == 1
    assert len(groups[0]) == 2

def test_mixed_concurrent_and_causal():
    detector = ConcurrencyDetector()
    sb = ScenarioBuilder()
    events = sb.diamond_pattern()
    pairs = detector.detect_concurrent_pairs(events)
    assert len(pairs) == 1
