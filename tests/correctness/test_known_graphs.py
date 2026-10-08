import pytest
import networkx as nx
from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder as DAGBuilder

def _are_concurrent(vc1, vc2):
    less1 = False
    less2 = False
    keys = set(vc1.keys()).union(vc2.keys())
    for k in keys:
        v1 = vc1.get(k, 0)
        v2 = vc2.get(k, 0)
        if v1 < v2: less1 = True
        if v2 < v1: less2 = True
    return less1 and less2

def test_chain():
    e1 = Event(vector_clock={"a":1})
    e2 = Event(vector_clock={"a":2})
    assert not _are_concurrent(e1.vector_clock, e2.vector_clock)

def test_diamond():
    e1 = Event(vector_clock={"a":1})
    e2 = Event(vector_clock={"a":1, "b":1})
    e3 = Event(vector_clock={"a":1, "c":1})
    e4 = Event(vector_clock={"a":1, "b":1, "c":1, "d":1})
    assert _are_concurrent(e2.vector_clock, e3.vector_clock)

def test_tree():
    e1 = Event(vector_clock={"a":1})
    e2 = Event(vector_clock={"a":1, "b":1})
    e3 = Event(vector_clock={"a":1, "c":1})
    assert _are_concurrent(e2.vector_clock, e3.vector_clock)

def test_complex_dag():
    builder = DAGBuilder()
    events = [
        Event(event_id="E1", vector_clock={"a":1}),
        Event(event_id="E2", vector_clock={"a":1, "b":1}),
        Event(event_id="E3", vector_clock={"a":1, "c":1}),
        Event(event_id="E4", vector_clock={"a":1, "b":1, "d":1}),
        Event(event_id="E5", vector_clock={"a":1, "c":1, "e":1}),
        Event(event_id="E6", vector_clock={"a":1, "b":1, "c":1, "d":1, "e":1, "f":1})
    ]
    builder.build(events)
    dag = builder.get_dag()
    assert len(dag.nodes) == 6
    # E2 and E3 concurrent
    assert _are_concurrent(events[1].vector_clock, events[2].vector_clock)
    # E4 and E5 concurrent
    assert _are_concurrent(events[3].vector_clock, events[4].vector_clock)
