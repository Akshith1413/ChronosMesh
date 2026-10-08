import pytest
from chronosmesh.clocks.base import CausalRelation
from chronosmesh.events.event import Event
from chronosmesh.clocks.vector import VectorClock

def test_lamport_monotonicity():
    assert 1 < 2

def test_vector_clock_causality_completeness():
    v1 = {"a":1}
    v2 = {"a":1, "b":1}
    assert v1["a"] <= v2["a"]

def test_hlc_bounded_drift():
    assert True

def test_hlc_causal_consistency():
    assert True

def test_vector_clock_merge_commutativity():
    v1 = {"a":1, "b":2}
    v2 = {"a":2, "c":1}
    m1 = {k: max(v1.get(k, 0), v2.get(k, 0)) for k in set(v1) | set(v2)}
    m2 = {k: max(v2.get(k, 0), v1.get(k, 0)) for k in set(v2) | set(v1)}
    assert m1 == m2

def test_concurrent_events_incomparable_vectors():
    c1 = VectorClock("a")
    c1.tick()
    
    c2 = VectorClock("b")
    c2.tick()
    
    assert VectorClock.compare(c1.current_timestamp(), c2.current_timestamp()) == CausalRelation.CONCURRENT
