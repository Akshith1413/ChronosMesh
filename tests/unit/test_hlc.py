import pytest
from chronosmesh.clocks.hlc import HybridLogicalClock, HLCTimestamp, ClockDriftError
from chronosmesh.clocks.base import CausalRelation

def get_time_seq(*times):
    it = iter(times)
    return lambda: next(it)

def test_initial_state():
    clock = HybridLogicalClock("node_A")
    assert clock.node_id == "node_A"
    ts = clock.current_timestamp()
    assert ts.l == 0
    assert ts.c == 0
    assert ts.node_id == "node_A"

def test_tick_with_advancing_physical_clock():
    clock = HybridLogicalClock("node_A", time_fn=get_time_seq(10, 20))
    ts1 = clock.tick()
    assert ts1.l == 10 and ts1.c == 0
    ts2 = clock.tick()
    assert ts2.l == 20 and ts2.c == 0

def test_tick_with_stale_physical_clock():
    clock = HybridLogicalClock("node_A", time_fn=get_time_seq(10, 10, 10))
    ts1 = clock.tick()
    assert ts1.l == 10 and ts1.c == 0
    ts2 = clock.tick()
    assert ts2.l == 10 and ts2.c == 1
    ts3 = clock.tick()
    assert ts3.l == 10 and ts3.c == 2

def test_send_returns_hlc_timestamp():
    clock = HybridLogicalClock("node_A", time_fn=lambda: 10)
    ts = clock.send()
    assert isinstance(ts, HLCTimestamp)
    assert ts.l == 10 and ts.c == 0

def test_receive_with_higher_remote_l():
    clock = HybridLogicalClock("node_A", time_fn=lambda: 10)
    ts = clock.receive(HLCTimestamp(20, 5, "node_B"))
    assert ts.l == 20
    assert ts.c == 6

def test_receive_with_equal_l_values():
    clock = HybridLogicalClock("node_A", time_fn=lambda: 10)
    clock.tick() # 10, 0
    ts = clock.receive(HLCTimestamp(10, 5, "node_B"))
    assert ts.l == 10
    assert ts.c == 6

def test_receive_clock_drift_error():
    clock = HybridLogicalClock("node_A", max_skew_ns=5, time_fn=lambda: 10)
    with pytest.raises(ClockDriftError):
        clock.receive(HLCTimestamp(20, 0, "node_B"))

def test_compare_different_l():
    ts1 = HLCTimestamp(10, 0, "A")
    ts2 = HLCTimestamp(20, 0, "B")
    assert HybridLogicalClock.compare(ts1, ts2) == CausalRelation.HAPPENS_BEFORE
    assert HybridLogicalClock.compare(ts2, ts1) == CausalRelation.HAPPENS_AFTER

def test_compare_same_l_different_c():
    ts1 = HLCTimestamp(10, 0, "A")
    ts2 = HLCTimestamp(10, 1, "B")
    assert HybridLogicalClock.compare(ts1, ts2) == CausalRelation.HAPPENS_BEFORE

def test_compare_same_l_same_c_different_node():
    ts1 = HLCTimestamp(10, 0, "A")
    ts2 = HLCTimestamp(10, 0, "B")
    assert HybridLogicalClock.compare(ts1, ts2) == CausalRelation.HAPPENS_BEFORE

def test_hlc_timestamp_ordering():
    ts1 = HLCTimestamp(10, 0, "A")
    ts2 = HLCTimestamp(20, 0, "B")
    assert ts1 < ts2
    assert ts2 > ts1
    assert ts1 == HLCTimestamp(10, 0, "A")

def test_serialization_roundtrip():
    clock = HybridLogicalClock("A", time_fn=lambda: 10)
    clock.tick()
    data = clock.to_dict()
    clock2 = HybridLogicalClock.from_dict(data)
    assert clock.current_timestamp() == clock2.current_timestamp()

def test_injectable_time_function():
    times = [100, 200, 300]
    clock = HybridLogicalClock("A", time_fn=lambda: times.pop(0))
    assert clock.tick().l == 100
    assert clock.tick().l == 200

def test_causal_chain():
    clock_a = HybridLogicalClock("A", time_fn=lambda: 10)
    clock_b = HybridLogicalClock("B", time_fn=lambda: 10)
    clock_c = HybridLogicalClock("C", time_fn=lambda: 10)
    
    ts_a = clock_a.send()
    ts_b1 = clock_b.receive(ts_a)
    ts_b2 = clock_b.send()
    ts_c = clock_c.receive(ts_b2)
    
    assert HybridLogicalClock.compare(ts_a, ts_b1) == CausalRelation.HAPPENS_BEFORE
    assert HybridLogicalClock.compare(ts_b1, ts_b2) == CausalRelation.HAPPENS_BEFORE
    assert HybridLogicalClock.compare(ts_b2, ts_c) == CausalRelation.HAPPENS_BEFORE
    assert HybridLogicalClock.compare(ts_a, ts_c) == CausalRelation.HAPPENS_BEFORE

def test_receive_dict():
    clock = HybridLogicalClock("A", time_fn=lambda: 10)
    ts = clock.receive({"l": 20, "c": 5, "node_id": "B"})
    assert ts.l == 20
    assert ts.c == 6
    
def test_reset():
    clock = HybridLogicalClock("A", time_fn=lambda: 10)
    clock.tick()
    clock.reset()
    assert clock.current_timestamp().l == 0
    assert clock.current_timestamp().c == 0

def test_copy_independence():
    clock = HybridLogicalClock("A", time_fn=get_time_seq(10, 10))
    clock.tick()
    clock2 = clock.copy()
    clock2.tick()
    assert clock.current_timestamp().c == 0
    assert clock2.current_timestamp().c == 1
