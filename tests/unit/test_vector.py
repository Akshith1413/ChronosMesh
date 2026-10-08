import pytest
from chronosmesh.clocks.vector import VectorClock
from chronosmesh.clocks.base import CausalRelation

def test_initial_state():
    clock = VectorClock("node_A")
    assert clock.node_id == "node_A"
    assert clock.current_timestamp() == {"node_A": 0}

def test_tick_increments_own_counter():
    clock = VectorClock("node_A")
    ts = clock.tick()
    assert ts == {"node_A": 1}
    assert clock.current_timestamp() == {"node_A": 1}

def test_send_returns_snapshot():
    clock = VectorClock("node_A")
    ts = clock.send()
    assert ts == {"node_A": 1}

def test_receive_merges_and_increments():
    clock = VectorClock("node_A")
    clock.tick()
    ts = clock.receive({"node_B": 2, "node_C": 1})
    assert ts == {"node_A": 2, "node_B": 2, "node_C": 1}

def test_happens_before_detection():
    v1 = {"A": 1, "B": 0}
    v2 = {"A": 1, "B": 1}
    assert VectorClock.compare(v1, v2) == CausalRelation.HAPPENS_BEFORE

def test_happens_after_detection():
    v1 = {"A": 1, "B": 1}
    v2 = {"A": 1, "B": 0}
    assert VectorClock.compare(v1, v2) == CausalRelation.HAPPENS_AFTER

def test_concurrent_detection():
    v1 = {"A": 1, "B": 0}
    v2 = {"A": 0, "B": 1}
    assert VectorClock.compare(v1, v2) == CausalRelation.CONCURRENT

def test_equal_detection():
    v1 = {"A": 1, "B": 1}
    v2 = {"A": 1, "B": 1}
    assert VectorClock.compare(v1, v2) == CausalRelation.EQUAL

def test_dominates_helper():
    assert VectorClock.dominates({"A": 1, "B": 1}, {"A": 1, "B": 0})
    assert not VectorClock.dominates({"A": 1, "B": 0}, {"A": 1, "B": 1})
    assert not VectorClock.dominates({"A": 1, "B": 0}, {"A": 0, "B": 1})

def test_three_service_scenario():
    order = VectorClock("Order")
    payment = VectorClock("Payment")
    inventory = VectorClock("Inventory")
    
    order_ts = order.send()
    payment_ts = payment.receive(order_ts)
    inventory_ts = inventory.receive(order_ts)
    
    assert VectorClock.compare(order_ts, payment_ts) == CausalRelation.HAPPENS_BEFORE
    assert VectorClock.compare(order_ts, inventory_ts) == CausalRelation.HAPPENS_BEFORE
    assert VectorClock.compare(payment_ts, inventory_ts) == CausalRelation.CONCURRENT

def test_serialization_roundtrip():
    clock = VectorClock("A")
    clock.receive({"B": 2})
    data = clock.to_dict()
    clock2 = VectorClock.from_dict(data)
    assert clock.current_timestamp() == clock2.current_timestamp()

def test_causal_chain_across_services():
    a = VectorClock("A")
    b = VectorClock("B")
    c = VectorClock("C")
    
    ts_a = a.send()
    ts_b = b.receive(ts_a)
    ts_c = c.receive(ts_b)
    
    assert VectorClock.compare(ts_a, ts_c) == CausalRelation.HAPPENS_BEFORE

def test_sparse_vector_missing_keys():
    v1 = {"A": 1}
    v2 = {"B": 1}
    assert VectorClock.compare(v1, v2) == CausalRelation.CONCURRENT

def test_copy_independence():
    clock = VectorClock("A")
    clock.tick()
    clock2 = clock.copy()
    clock2.tick()
    assert clock.current_timestamp() == {"A": 1}
    assert clock2.current_timestamp() == {"A": 2}
    
def test_merge_does_not_increment():
    clock = VectorClock("A")
    clock.merge({"B": 2})
    assert clock.current_timestamp() == {"A": 0, "B": 2}

def test_reset():
    clock = VectorClock("A")
    clock.tick()
    clock.reset()
    assert clock.current_timestamp() == {"A": 0}
