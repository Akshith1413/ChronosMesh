import pytest
from chronosmesh.clocks.lamport import LamportClock
from chronosmesh.clocks.base import CausalRelation

def test_initial_state():
    clock = LamportClock("node_A")
    assert clock.node_id == "node_A"
    assert clock.current_timestamp() == (0, "node_A")

def test_tick_increments():
    clock = LamportClock("node_A")
    ts = clock.tick()
    assert ts == (1, "node_A")
    assert clock.current_timestamp() == (1, "node_A")

def test_send_returns_timestamp():
    clock = LamportClock("node_A")
    ts = clock.send()
    assert ts == (1, "node_A")
    assert clock.current_timestamp() == (1, "node_A")

def test_receive_takes_max_plus_one():
    clock = LamportClock("node_A")
    clock.tick() # counter = 1
    ts = clock.receive(5)
    assert ts == (6, "node_A")
    assert clock.current_timestamp() == (6, "node_A")

def test_receive_with_lower_remote():
    clock = LamportClock("node_A")
    clock.tick()
    clock.tick() # counter = 2
    ts = clock.receive(1)
    assert ts == (3, "node_A")

def test_receive_with_higher_remote():
    clock = LamportClock("node_A")
    ts = clock.receive(10)
    assert ts == (11, "node_A")

def test_receive_tuple_timestamp():
    clock = LamportClock("node_A")
    ts = clock.receive((10, "node_B"))
    assert ts == (11, "node_A")

def test_compare_different_counters():
    ts1 = (1, "node_A")
    ts2 = (2, "node_B")
    assert LamportClock.compare(ts1, ts2) == CausalRelation.HAPPENS_BEFORE
    assert LamportClock.compare(ts2, ts1) == CausalRelation.HAPPENS_AFTER

def test_compare_same_counter_different_nodes():
    ts1 = (1, "node_A")
    ts2 = (1, "node_B")
    assert LamportClock.compare(ts1, ts2) == CausalRelation.HAPPENS_BEFORE
    assert LamportClock.compare(ts2, ts1) == CausalRelation.HAPPENS_AFTER

def test_compare_equal():
    ts1 = (1, "node_A")
    ts2 = (1, "node_A")
    assert LamportClock.compare(ts1, ts2) == CausalRelation.EQUAL

def test_serialization_roundtrip():
    clock = LamportClock("node_A")
    clock.tick()
    data = clock.to_dict()
    clock2 = LamportClock.from_dict(data)
    assert clock.current_timestamp() == clock2.current_timestamp()
    assert clock.node_id == clock2.node_id

def test_reset():
    clock = LamportClock("node_A")
    clock.tick()
    clock.reset()
    assert clock.current_timestamp() == (0, "node_A")

def test_copy_independence():
    clock = LamportClock("node_A")
    clock.tick()
    clock2 = clock.copy()
    clock2.tick()
    assert clock.current_timestamp() == (1, "node_A")
    assert clock2.current_timestamp() == (2, "node_A")

def test_multiple_ticks():
    clock = LamportClock("node_A")
    for i in range(5):
        clock.tick()
    assert clock.current_timestamp() == (5, "node_A")

def test_causal_chain():
    clock_a = LamportClock("A")
    clock_b = LamportClock("B")
    clock_c = LamportClock("C")
    
    ts_a = clock_a.send()
    ts_b1 = clock_b.receive(ts_a)
    ts_b2 = clock_b.send()
    ts_c = clock_c.receive(ts_b2)
    
    assert LamportClock.compare(ts_a, ts_b1) == CausalRelation.HAPPENS_BEFORE
    assert LamportClock.compare(ts_b1, ts_b2) == CausalRelation.HAPPENS_BEFORE
    assert LamportClock.compare(ts_b2, ts_c) == CausalRelation.HAPPENS_BEFORE
    assert LamportClock.compare(ts_a, ts_c) == CausalRelation.HAPPENS_BEFORE
