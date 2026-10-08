import pytest
import networkx as nx
from chronosmesh.analysis.graph_diff import CausalGraphDiffer

def test_identical_graphs_zero_drift():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_edges_from([("1", "2"), ("2", "3")])
    res = differ.diff(dag1, dag1)
    assert res.structural_similarity == 1.0
    assert res.behavioral_drift_score == 0.0

def test_completely_different_graphs():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_edges_from([("1", "2")])
    dag2 = nx.DiGraph()
    dag2.add_edges_from([("3", "4")])
    res = differ.diff(dag1, dag2)
    assert res.structural_similarity == 0.0
    assert res.behavioral_drift_score == 1.0

def test_added_edge():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_edges_from([("1", "2")])
    dag2 = nx.DiGraph()
    dag2.add_edges_from([("1", "2"), ("2", "3")])
    res = differ.diff(dag1, dag2)
    assert ("2", "3") in res.added_edges

def test_removed_edge():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_edges_from([("1", "2"), ("2", "3")])
    dag2 = nx.DiGraph()
    dag2.add_edges_from([("1", "2")])
    res = differ.diff(dag1, dag2)
    assert ("2", "3") in res.removed_edges

def test_added_node():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_node("1")
    dag2 = nx.DiGraph()
    dag2.add_node("1")
    dag2.add_node("2")
    res = differ.diff(dag1, dag2)
    assert "2" in res.added_nodes

def test_structural_similarity():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_edges_from([("1", "2"), ("2", "3")])
    dag2 = nx.DiGraph()
    dag2.add_edges_from([("1", "2"), ("3", "4")])
    res = differ.diff(dag1, dag2)
    # intersection: 1, union: 3
    assert abs(res.structural_similarity - 0.333) < 0.01

def test_behavioral_drift_score():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag1.add_edges_from([("1", "2"), ("2", "3")])
    dag2 = nx.DiGraph()
    dag2.add_edges_from([("1", "2"), ("3", "4")])
    res = differ.diff(dag1, dag2)
    assert abs(res.behavioral_drift_score - 0.666) < 0.01

def test_change_summary():
    differ = CausalGraphDiffer()
    dag1 = nx.DiGraph()
    dag2 = nx.DiGraph()
    res = differ.diff(dag1, dag2)
    summary = differ.get_change_summary(res)
    assert isinstance(summary, str)
