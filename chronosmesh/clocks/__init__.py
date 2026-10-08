"""
Clock Systems — Pluggable distributed clock implementations.

Provides Lamport logical clocks, Vector clocks, and Hybrid Logical Clocks (HLC)
with a unified interface for causal ordering in distributed systems.
"""

from chronosmesh.clocks.base import CausalRelation, ClockStrategy
from chronosmesh.clocks.lamport import LamportClock
from chronosmesh.clocks.vector import VectorClock
from chronosmesh.clocks.hlc import HybridLogicalClock
from chronosmesh.clocks.factory import ClockFactory

__all__ = [
    "CausalRelation",
    "ClockStrategy",
    "LamportClock",
    "VectorClock",
    "HybridLogicalClock",
    "ClockFactory",
]
