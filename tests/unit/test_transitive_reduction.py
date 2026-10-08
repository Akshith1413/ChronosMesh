import pytest
import networkx as nx
from chronosmesh.causality.transitive_reduction import compute_transitive_reduction, is_transitively_reduced

def test_already_reduced_dag():
    G = nx.DiGraph()
    G.add_edges_from([(1, 2), (2, 3)])
    reduced = compute_transitive_reduction(G)
    assert list(reduced.edges()) == [(1, 2), (2, 3)]

def test_chain_with_skip_edge():
    G = nx.DiGraph()
    G.add_edges_from([(1, 2), (2, 3), (1, 3)])
    reduced = compute_transitive_reduction(G)
    assert (1, 3) not in reduced.edges()
    assert len(reduced.edges()) == 2

def test_diamond_dag_reduction():
    G = nx.DiGraph()
    G.add_edges_from([(1, 2), (1, 3), (2, 4), (3, 4)])
    reduced = compute_transitive_reduction(G)
    assert len(reduced.edges()) == 4

def test_complex_dag():
    G = nx.DiGraph()
    G.add_edges_from([(1, 2), (2, 3), (3, 4), (1, 4), (1, 3), (2, 4)])
    reduced = compute_transitive_reduction(G)
    assert list(reduced.edges()) == [(1, 2), (2, 3), (3, 4)]

def test_is_transitively_reduced():
    G1 = nx.DiGraph([(1, 2), (2, 3)])
    assert is_transitively_reduced(G1) is True
    
    G2 = nx.DiGraph([(1, 2), (2, 3), (1, 3)])
    assert is_transitively_reduced(G2) is False

def test_cycle_detection_raises():
    G = nx.DiGraph()
    G.add_edges_from([(1, 2), (2, 3), (3, 1)])
    with pytest.raises(ValueError, match="cycle detected"):
        compute_transitive_reduction(G)
    with pytest.raises(ValueError, match="cycle detected"):
        is_transitively_reduced(G)
