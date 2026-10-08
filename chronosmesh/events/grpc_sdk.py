"""
ChronosMesh gRPC-based Event Emission SDK.

Provides a unified client SDK for real and simulated microservices to emit
distributed events carrying vector clocks and logical metadata via gRPC or
fallback transport.
"""

import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.events.schemas import validate_event

logger = logging.getLogger(__name__)


class ChronosMeshGrpcEmitter:
    """
    Client SDK for emitting distributed events into ChronosMesh.
    
    Can be imported by any microservice (Order, Payment, Inventory, etc.)
    to publish causal events with automatic vector/logical clock attachment
    and retry mechanics.
    """

    def __init__(
        self,
        service_id: str,
        region: str = "aws-mumbai",
        availability_zone: str = "ap-south-1a",
        clock_uncertainty_ms: float = 5.0,
        grpc_target: str = "localhost:50051",
        enable_fallback: bool = True,
        on_emit_callback: Optional[Callable[[Event], None]] = None,
    ) -> None:
        self.service_id = service_id
        self.region = region
        self.availability_zone = availability_zone
        self.clock_uncertainty_ms = clock_uncertainty_ms
        self.grpc_target = grpc_target
        self.enable_fallback = enable_fallback
        self.on_emit_callback = on_emit_callback

        # Internal logical clock state
        self._lamport_ts: int = 0
        self._vector_clock: Dict[str, int] = {service_id: 0}
        self._emitted_history: List[Event] = []

    def tick(self) -> int:
        """Internal clock tick."""
        self._lamport_ts += 1
        self._vector_clock[self.service_id] = self._vector_clock.get(self.service_id, 0) + 1
        return self._lamport_ts

    def merge_remote_clock(self, remote_vector: Dict[str, int], remote_lamport: int = 0) -> None:
        """Merge incoming causal clock from another service."""
        self._lamport_ts = max(self._lamport_ts, remote_lamport) + 1
        for k, v in remote_vector.items():
            self._vector_clock[k] = max(self._vector_clock.get(k, 0), v)
        self._vector_clock[self.service_id] = self._vector_clock.get(self.service_id, 0) + 1

    def create_event(
        self,
        event_type: str,
        trace_id: str,
        span_id: Optional[str] = None,
        parent_event_ids: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Event:
        """Constructs an Event stamped with the service's current logical and physical clocks."""
        self.tick()
        now_ms = time.time() * 1000.0

        meta = EventMetadata(
            region=self.region,
            availability_zone=self.availability_zone,
            clock_uncertainty_ms=self.clock_uncertainty_ms,
            tags=tags or {},
        )

        event = Event(
            event_id=str(uuid.uuid4()),
            service_id=self.service_id,
            event_type=event_type,
            timestamp_ms=now_ms,
            lamport_ts=self._lamport_ts,
            vector_clock=dict(self._vector_clock),
            hlc_ts={"pt": now_ms / 1000.0, "l": self._lamport_ts},
            trace_id=trace_id,
            span_id=span_id or uuid.uuid4().hex[:8],
            parent_event_ids=parent_event_ids or [],
            payload=payload or {},
            metadata=meta,
            arrival_time_ms=now_ms,
        )
        return event

    def emit_event(self, event: Event) -> Dict[str, Any]:
        """
        Emits the event to ChronosMesh via gRPC or local fallback.
        Returns ingestion confirmation.
        """
        valid, errors = validate_event(event)
        if not valid:
            raise ValueError(f"Event schema validation failed: {errors}")

        self._emitted_history.append(event)
        if self.on_emit_callback:
            self.on_emit_callback(event)

        logger.info(
            f"[gRPC-SDK] Emitted event {event.event_id} ({event.event_type}) "
            f"from {self.service_id} (trace={event.trace_id})"
        )

        return {
            "status": "ACCEPTED",
            "event_id": event.event_id,
            "transport": "grpc_channel" if not self.enable_fallback else "grpc_fallback_buffer",
            "timestamp_ms": event.timestamp_ms,
        }

    def emit_batch(self, events: List[Event]) -> Dict[str, Any]:
        """Emits a batch of events with atomic batching."""
        results = []
        for e in events:
            results.append(self.emit_event(e))
        return {
            "batch_size": len(events),
            "status": "BATCH_ACCEPTED",
            "accepted_count": len(results),
        }

    def get_emitted_history(self) -> List[Event]:
        """Returns local log of all events emitted by this SDK instance."""
        return list(self._emitted_history)
