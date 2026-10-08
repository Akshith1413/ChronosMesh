import pytest
from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.events.generator import ScenarioBuilder

def test_build_simple_chain():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    dag = builder.build(events)
    assert len(dag.nodes) == 3
    assert len(dag.edges) == 2

def test_build_diamond_dag():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.diamond_pattern()
    dag = builder.build(events)
    assert len(dag.nodes) == 4
    assert len(dag.edges) == 4

def test_build_with_concurrent_branches():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.concurrent_branches()
    dag = builder.build(events)
    assert len(dag.nodes) == 3
    assert len(dag.edges) == 2

def test_transitive_reduction_removes_redundant_edges():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    dag = builder.build(events)
    assert (events[0].event_id, events[2].event_id) not in dag.edges

def test_get_roots_and_leaves():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    builder.build(events)
    assert len(builder.get_roots()) == 1
    assert len(builder.get_leaves()) == 1

def test_get_ancestors_descendants():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    builder.build(events)
    assert len(builder.get_ancestors(events[2].event_id)) == 2
    assert len(builder.get_descendants(events[0].event_id)) == 2

def test_topological_order():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    builder.build(events)
    order = builder.topological_order()
    assert len(order) == 3

def test_incremental_build():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(3)
    builder.build_incremental(events[0])
    builder.build_incremental(events[1])
    dag = builder.build_incremental(events[2])
    assert len(dag.nodes) == 3
    assert len(dag.edges) == 2

def test_empty_dag():
    builder = CausalDAGBuilder()
    dag = builder.build([])
    assert len(dag.nodes) == 0

def test_single_event():
    builder = CausalDAGBuilder()
    sb = ScenarioBuilder()
    events = sb.chain(1)
    dag = builder.build(events)
    assert len(dag.nodes) == 1
    assert len(dag.edges) == 0
