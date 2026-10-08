import pytest
from chronosmesh.clocks.factory import ClockFactory
from chronosmesh.clocks.lamport import LamportClock
from chronosmesh.clocks.vector import VectorClock
from chronosmesh.clocks.hlc import HybridLogicalClock
from chronosmesh.clocks.base import ClockStrategy

def test_create_lamport():
    clock = ClockFactory.create("lamport", "node_A")
    assert isinstance(clock, LamportClock)
    assert clock.node_id == "node_A"

def test_create_vector():
    clock = ClockFactory.create("vector", "node_A")
    assert isinstance(clock, VectorClock)
    assert clock.node_id == "node_A"

def test_create_hlc():
    clock = ClockFactory.create("hlc", "node_A")
    assert isinstance(clock, HybridLogicalClock)
    assert clock.node_id == "node_A"

def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        ClockFactory.create("unknown_clock", "node_A")

def test_register_custom_strategy():
    class CustomClock(LamportClock):
        pass
        
    ClockFactory.register("custom", CustomClock)
    clock = ClockFactory.create("custom", "node_A")
    assert isinstance(clock, CustomClock)

def test_available_strategies():
    strategies = ClockFactory.available_strategies()
    assert "lamport" in strategies
    assert "vector" in strategies
    assert "hlc" in strategies
