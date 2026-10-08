import pytest
import networkx as nx
from chronosmesh.analysis.root_cause import RootCauseTracer

def test_simple_chain_root_cause():
    tracer = RootCauseTracer()
    dag = nx.DiGraph()
    dag.add_node("1")
    dag.add_node("2")
    dag.add_node("3")
    dag.add_edges_from([("1", "2"), ("2", "3")])
    res = tracer.trace(dag, "3")
    assert len(res.root_causes) == 1
    assert res.root_causes[0]["event_id"] == "1"

def test_diamond_dag_root_cause():
    tracer = RootCauseTracer()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("1", "3"), ("2", "4"), ("3", "4")])
    res = tracer.trace(dag, "4")
    assert len(res.root_causes) == 1
    assert res.root_causes[0]["event_id"] == "1"

def test_multiple_root_causes():
    tracer = RootCauseTracer()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "3"), ("2", "3")])
    res = tracer.trace(dag, "3")
    assert len(res.root_causes) == 2
    ids = [rc["event_id"] for rc in res.root_causes]
    assert "1" in ids and "2" in ids

def test_critical_path():
    tracer = RootCauseTracer()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "4"), ("1", "3"), ("3", "5"), ("5", "6"), ("6", "4")])
    res = tracer.find_critical_path(dag, "4")
    assert res == ["1", "3", "5", "6", "4"]

def test_ancestor_subgraph():
    tracer = RootCauseTracer()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "3"), ("4", "5")])
    res = tracer.get_ancestor_subgraph(dag, "3")
    assert set(res.nodes()) == {"1", "2", "3"}

def test_max_depth_limit():
    tracer = RootCauseTracer()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "3"), ("3", "4")])
    res = tracer.trace(dag, "4", max_depth=1)
    # The root cause "1" is at depth 3, which is > 1.
    assert len(res.root_causes) == 0
