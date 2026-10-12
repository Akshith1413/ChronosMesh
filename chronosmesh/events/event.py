"""
Core Event data model for ChronosMesh.

Represents a distributed system event with all metadata needed for
causal reconstruction: service identity, clock timestamps, trace context,
region information, and arrival timing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def ms_to_iso(ms: float) -> str:
    """Epoch milliseconds -> ISO-8601 UTC string with millisecond precision (``...Z``)."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def iso_to_ms(value: Any) -> float:
    """ISO-8601 string (or already-numeric epoch ms) -> epoch milliseconds."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp() * 1000.0


@dataclass
class EventMetadata:
    """Additional metadata attached to an event.

    Attributes:
        region: Cloud region where the event originated (e.g., 'aws-mumbai', 'gcp-singapore').
        availability_zone: Specific AZ within the region.
        clock_uncertainty_ms: Estimated clock uncertainty in milliseconds
                              (for TrueTime-style confidence scoring).
        tags: Arbitrary key-value tags for filtering and grouping.
    """

    region: str = "unknown"
    availability_zone: str = "unknown"
    clock_uncertainty_ms: float = 5.0
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to dictionary."""
        return {
            "region": self.region,
            "availability_zone": self.availability_zone,
            "clock_uncertainty_ms": self.clock_uncertainty_ms,
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventMetadata":
        """Deserialize metadata from dictionary."""
        return cls(
            region=data.get("region", "unknown"),
            availability_zone=data.get("availability_zone", "unknown"),
            clock_uncertainty_ms=data.get("clock_uncertainty_ms", 5.0),
            tags=data.get("tags", {}),
        )


@dataclass
class Event:
    """A distributed system event with full causal context.

    This is the core data unit flowing through ChronosMesh. Each event
    carries enough information for the causal reconstruction engine to
    determine happens-before relationships, detect concurrency, and
    build the causal DAG.

    Attributes:
        event_id: Globally unique event identifier.
        service_id: ID of the microservice that emitted this event.
        event_type: Type/name of the event (e.g., 'ORDER_CREATED', 'PAYMENT_STARTED').
        timestamp_ms: Wall-clock timestamp in milliseconds when the event occurred
                      (subject to clock skew — this is NOT the causal ordering).
        lamport_ts: Lamport logical clock timestamp at emission time.
        vector_clock: Vector clock state at emission time — dict of {service_id: counter}.
        hlc_ts: Hybrid Logical Clock timestamp — tuple of (physical_component, logical_counter).
        trace_id: Distributed trace ID linking related events across services.
        span_id: Span ID within the trace for this specific operation.
        parent_event_ids: IDs of events that directly caused this event
                          (explicit causal links from the emitting service).
        payload: Application-specific event payload data.
        metadata: Additional metadata (region, uncertainty, tags).
        arrival_time_ms: Wall-clock timestamp when ChronosMesh received this event
                         (always monotonic on the receiving side).
        execution_id: Logical execution (one business flow / experiment run) the event
                      belongs to. Falls back to ``trace_id`` when not supplied.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    event_type: str = ""
    timestamp_ms: float = 0.0
    lamport_ts: int = 0
    vector_clock: Dict[str, int] = field(default_factory=dict)
    hlc_ts: Optional[Dict[str, Any]] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_event_ids: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)
    arrival_time_ms: float = field(default_factory=lambda: time.time() * 1000)
    execution_id: str = ""

    @property
    def effective_execution_id(self) -> str:
        """Execution the event belongs to (``trace_id`` when none was supplied)."""
        return self.execution_id or self.trace_id

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the event to a dictionary for transport/storage."""
        return {
            "event_id": self.event_id,
            "service_id": self.service_id,
            "event_type": self.event_type,
            "timestamp_ms": self.timestamp_ms,
            "lamport_ts": self.lamport_ts,
            "vector_clock": dict(self.vector_clock),
            "hlc_ts": self.hlc_ts,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_event_ids": list(self.parent_event_ids),
            "payload": dict(self.payload),
            "metadata": self.metadata.to_dict(),
            "arrival_time_ms": self.arrival_time_ms,
            "execution_id": self.effective_execution_id,
        }

    def to_spec_dict(self) -> Dict[str, Any]:
        """Serialize using the published ChronosMesh event contract.

        ``event_time`` is when the event occurred at the producer (subject to clock
        skew); ``ingestion_time`` is when the platform received it.
        """
        return {
            "event_id": self.event_id,
            "execution_id": self.effective_execution_id,
            "service": self.service_id,
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_event_ids": list(self.parent_event_ids),
            "lamport_clock": self.lamport_ts,
            "vector_clock": dict(self.vector_clock),
            "event_time": ms_to_iso(self.timestamp_ms),
            "ingestion_time": ms_to_iso(self.arrival_time_ms),
            "hlc": self.hlc_ts,
            "payload": dict(self.payload),
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_spec_dict(cls, data: Dict[str, Any]) -> "Event":
        """Build an event from the published contract (see :meth:`to_spec_dict`)."""
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Deserialize an event from a dictionary.

        Accepts both the internal field names (``service_id``, ``lamport_ts``,
        ``timestamp_ms``, ``arrival_time_ms``) and the published contract names
        (``service``, ``lamport_clock``, ``event_time``, ``ingestion_time``).
        """
        data = dict(data)
        if "service_id" not in data and "service" in data:
            data["service_id"] = data["service"]
        if "lamport_ts" not in data and "lamport_clock" in data:
            data["lamport_ts"] = data["lamport_clock"]
        if "timestamp_ms" not in data and "event_time" in data:
            data["timestamp_ms"] = iso_to_ms(data["event_time"])
        if "arrival_time_ms" not in data and "ingestion_time" in data:
            data["arrival_time_ms"] = iso_to_ms(data["ingestion_time"])
        if "hlc_ts" not in data and data.get("hlc") is not None:
            data["hlc_ts"] = data["hlc"]
        metadata_data = data.get("metadata", {})
        metadata = (
            EventMetadata.from_dict(metadata_data)
            if isinstance(metadata_data, dict)
            else metadata_data
        )
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            service_id=data.get("service_id", ""),
            event_type=data.get("event_type", ""),
            timestamp_ms=data.get("timestamp_ms", 0.0),
            lamport_ts=data.get("lamport_ts", 0),
            vector_clock=data.get("vector_clock", {}),
            hlc_ts=data.get("hlc_ts"),
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            span_id=data.get("span_id", str(uuid.uuid4())[:8]),
            parent_event_ids=data.get("parent_event_ids", []),
            payload=data.get("payload", {}),
            metadata=metadata,
            arrival_time_ms=data.get("arrival_time_ms", time.time() * 1000),
            execution_id=data.get("execution_id", "") or "",
        )

    @property
    def physical_time_ms(self) -> float:
        """Alias for timestamp_ms — the physical wall-clock time."""
        return self.timestamp_ms

    def has_explicit_parent(self, other_event_id: str) -> bool:
        """Check if this event explicitly declares a causal dependency on another event."""
        return other_event_id in self.parent_event_ids

    def __hash__(self) -> int:
        return hash(self.event_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.event_id == other.event_id

    def __repr__(self) -> str:
        return (
            f"Event(id={self.event_id[:8]}..., service={self.service_id}, "
            f"type={self.event_type}, lamport={self.lamport_ts})"
        )
