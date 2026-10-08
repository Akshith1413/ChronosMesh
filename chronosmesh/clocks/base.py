"""
Abstract base class for all clock strategies in ChronosMesh.

Defines the pluggable clock interface so Lamport, Vector, and HLC
implementations can be swapped and benchmarked interchangeably.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict


class CausalRelation(Enum):
    """Result of comparing two clock timestamps for causal ordering.

    HAPPENS_BEFORE: First event causally precedes the second (A → B)
    HAPPENS_AFTER:  First event causally follows the second (B → A)
    CONCURRENT:     Events are causally independent (A ∥ B)
    EQUAL:          Timestamps are identical
    """

    HAPPENS_BEFORE = -1
    HAPPENS_AFTER = 1
    CONCURRENT = 2
    EQUAL = 0


class ClockStrategy(ABC):
    """Abstract interface for distributed clock implementations.

    Every clock strategy must support:
    - tick(): Advance the clock for a local event
    - send(): Advance the clock and return timestamp to attach to outgoing message
    - receive(remote_ts): Update clock upon receiving a message with a remote timestamp
    - compare(ts1, ts2): Determine causal relationship between two timestamps
    - to_dict() / from_dict(): Serialization for network transport and persistence
    """

    @abstractmethod
    def __init__(self, node_id: str, **kwargs: Any) -> None:
        """Initialize the clock for a specific node/service.

        Args:
            node_id: Unique identifier for the node running this clock.
        """
        ...

    @property
    @abstractmethod
    def node_id(self) -> str:
        """Return the node ID this clock belongs to."""
        ...

    @abstractmethod
    def tick(self) -> Any:
        """Record a local event and advance the clock.

        Returns:
            The new timestamp after the local event.
        """
        ...

    @abstractmethod
    def send(self) -> Any:
        """Prepare a timestamp for an outgoing message.

        Advances the clock (like a local event) and returns the timestamp
        to be attached to the outgoing message.

        Returns:
            The timestamp to attach to the outgoing message.
        """
        ...

    @abstractmethod
    def receive(self, remote_timestamp: Any) -> Any:
        """Update the clock upon receiving a remote timestamp.

        Merges the remote timestamp with the local clock state
        according to the clock algorithm's rules.

        Args:
            remote_timestamp: The timestamp received from a remote node.

        Returns:
            The new local timestamp after merging.
        """
        ...

    @staticmethod
    @abstractmethod
    def compare(ts1: Any, ts2: Any) -> CausalRelation:
        """Compare two timestamps and determine their causal relationship.

        Args:
            ts1: First timestamp.
            ts2: Second timestamp.

        Returns:
            CausalRelation indicating the relationship between ts1 and ts2.
        """
        ...

    @abstractmethod
    def current_timestamp(self) -> Any:
        """Return the current clock timestamp without advancing it.

        Returns:
            The current timestamp value.
        """
        ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the clock state to a dictionary.

        Returns:
            Dictionary representation of the clock state,
            suitable for JSON serialization and network transport.
        """
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClockStrategy":
        """Deserialize a clock from a dictionary representation.

        Args:
            data: Dictionary containing serialized clock state.

        Returns:
            A new clock instance restored from the serialized state.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset the clock to its initial state."""
        ...

    @abstractmethod
    def copy(self) -> "ClockStrategy":
        """Create an independent copy of this clock.

        Returns:
            A new clock instance with the same state.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(node_id={self.node_id!r}, ts={self.current_timestamp()})"
