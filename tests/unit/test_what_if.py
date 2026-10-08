import pytest
import networkx as nx
from chronosmesh.analysis.what_if import WhatIfSimulator

def test_remove_root_invalidates_all():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "3")])
    res = sim.simulate_removal(dag, "1")
    assert res.invalidated_events == {"1", "2", "3"}

def test_remove_leaf_invalidates_none():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "3")])
    res = sim.simulate_removal(dag, "3")
    assert res.invalidated_events == {"3"}

def test_remove_fork_point_partial_invalidation():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("1", "3"), ("2", "4")])
    res = sim.simulate_removal(dag, "2")
    assert res.invalidated_events == {"2", "4"}

def test_surviving_events_with_multiple_parents():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "3"), ("2", "3")])
    res = sim.simulate_removal(dag, "1")
    assert "3" in res.surviving_events
    assert "3" not in res.invalidated_events

def test_blast_radius_calculation():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "3"), ("3", "4")])
    res = sim.simulate_removal(dag, "1")
    assert res.blast_radius == 1.0

def test_affected_services():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_node("1", service_id="A")
    dag.add_node("2", service_id="B")
    dag.add_edge("1", "2")
    res = sim.simulate_removal(dag, "1")
    assert res.affected_services == {"A", "B"}

def test_cascade_depth():
    sim = WhatIfSimulator()
    dag = nx.DiGraph()
    dag.add_edges_from([("1", "2"), ("2", "3"), ("3", "4")])
    res = sim.simulate_removal(dag, "1")
    assert res.cascade_depth == 3
