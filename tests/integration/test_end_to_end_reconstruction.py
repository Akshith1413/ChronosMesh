import pytest
from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder as DAGBuilder

def _are_concurrent(builder, e1, e2):
    dag = builder.get_dag()
    from networkx.algorithms.shortest_paths.generic import has_path
    if has_path(dag, e1.event_id, e2.event_id):
        return False
    if has_path(dag, e2.event_id, e1.event_id):
        return False
    return True

def test_end_to_end_reconstruction():
    builder = DAGBuilder()
    
    e1 = Event(event_id="E1", event_type="OrderCreated", vector_clock={"order": 1})
    e2 = Event(event_id="E2", event_type="PaymentStarted", vector_clock={"order": 1, "payment": 1})
    e3 = Event(event_id="E3", event_type="InventoryCheck", vector_clock={"order": 1, "inventory": 1})
    e4 = Event(event_id="E4", event_type="PaymentSuccess", vector_clock={"order": 1, "payment": 2})
    e5 = Event(event_id="E5", event_type="InventoryReserved", vector_clock={"order": 1, "inventory": 2})
    e6 = Event(event_id="E6", event_type="ShippingStarted", vector_clock={"order": 1, "payment": 2, "inventory": 2, "shipping": 1})
    
    events = [e1, e2, e3, e4, e5, e6]
    builder.build(events)
        
    dag = builder.get_dag()
    
    edges = set(dag.edges())
    expected_edges = {
        ("E1", "E2"),
        ("E1", "E3"),
        ("E2", "E4"),
        ("E3", "E5"),
        ("E4", "E6"),
        ("E5", "E6")
    }
    
    assert expected_edges.issubset(edges)
    assert _are_concurrent(builder, e2, e3)
