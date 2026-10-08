"""
ChronosMesh Mock Distributed Microservice Cluster.

Simulates 5 multi-cloud microservices (Order, Payment, Inventory, Shipping, Notification)
operating across AWS and GCP regions (Mumbai, Singapore) with configurable
fault injection: network delay, clock skew, out-of-order delivery, and service failures.
"""

import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from chronosmesh.events.event import Event, EventMetadata

logger = logging.getLogger(__name__)


# Standard multi-cloud service configuration
SERVICE_CONFIGS = {
    "order-svc": {
        "service_id": "order-svc",
        "region": "aws-mumbai",
        "availability_zone": "ap-south-1a",
        "clock_uncertainty_ms": 4.0,
    },
    "payment-svc": {
        "service_id": "payment-svc",
        "region": "aws-singapore",
        "availability_zone": "ap-southeast-1a",
        "clock_uncertainty_ms": 8.0,
    },
    "inventory-svc": {
        "service_id": "inventory-svc",
        "region": "gcp-mumbai",
        "availability_zone": "asia-south1-a",
        "clock_uncertainty_ms": 6.0,
    },
    "shipping-svc": {
        "service_id": "shipping-svc",
        "region": "gcp-singapore",
        "availability_zone": "asia-southeast1-a",
        "clock_uncertainty_ms": 9.0,
    },
    "notification-svc": {
        "service_id": "notification-svc",
        "region": "aws-mumbai",
        "availability_zone": "ap-south-1b",
        "clock_uncertainty_ms": 5.0,
    },
}


class MockDistributedCluster:
    """Multi-cloud microservice cluster with clock simulation and fault injection."""

    def __init__(
        self,
        simulate_network_delay: Optional[bool] = None,
        simulate_clock_skew: Optional[bool] = None,
        simulate_out_of_order: Optional[bool] = None,
        simulate_failure: Optional[bool] = None,
    ) -> None:
        self.simulate_network_delay = (
            simulate_network_delay
            if simulate_network_delay is not None
            else os.getenv("SIMULATE_NETWORK_DELAY", "true").lower() in ("true", "1")
        )
        self.simulate_clock_skew = (
            simulate_clock_skew
            if simulate_clock_skew is not None
            else os.getenv("SIMULATE_CLOCK_SKEW", "true").lower() in ("true", "1")
        )
        self.simulate_out_of_order = (
            simulate_out_of_order
            if simulate_out_of_order is not None
            else os.getenv("SIMULATE_OUT_OF_ORDER", "true").lower() in ("true", "1")
        )
        self.simulate_failure = (
            simulate_failure
            if simulate_failure is not None
            else os.getenv("SIMULATE_FAILURE", "false").lower() in ("true", "1")
        )

        # Service logical clocks state
        self.lamport_clocks: Dict[str, int] = {s: 0 for s in SERVICE_CONFIGS}
        self.vector_clocks: Dict[str, Dict[str, int]] = {
            s: {other: 0 for other in SERVICE_CONFIGS} for s in SERVICE_CONFIGS
        }
        self.hlc_clocks: Dict[str, Tuple[float, int]] = {
            s: (time.time(), 0) for s in SERVICE_CONFIGS
        }

        # Simulated physical clock drift per service (in milliseconds)
        self.clock_skews_ms: Dict[str, float] = {
            "order-svc": 0.0,
            "payment-svc": 65.0 if self.simulate_clock_skew else 0.0,  # Singapore clock ahead
            "inventory-svc": -40.0 if self.simulate_clock_skew else 0.0,  # GCP Mumbai clock behind
            "shipping-svc": 120.0 if self.simulate_clock_skew else 0.0,  # Cross-region drift
            "notification-svc": 5.0 if self.simulate_clock_skew else 0.0,
        }

    def _tick_clocks(self, service_id: str) -> Tuple[int, Dict[str, int], Dict[str, Any], float]:
        """Advance logical, vector, and hybrid logical clocks for a service."""
        # Lamport tick
        self.lamport_clocks[service_id] += 1
        lamport_val = self.lamport_clocks[service_id]

        # Vector tick
        self.vector_clocks[service_id][service_id] += 1
        vc_val = dict(self.vector_clocks[service_id])

        # HLC tick with skew
        now_sec = time.time() + (self.clock_skews_ms.get(service_id, 0.0) / 1000.0)
        curr_pt, curr_l = self.hlc_clocks[service_id]
        if now_sec > curr_pt:
            self.hlc_clocks[service_id] = (now_sec, 0)
        else:
            self.hlc_clocks[service_id] = (curr_pt, curr_l + 1)

        hlc_val = {
            "pt": self.hlc_clocks[service_id][0],
            "l": self.hlc_clocks[service_id][1],
        }
        wall_time_ms = now_sec * 1000.0
        return lamport_val, vc_val, hlc_val, wall_time_ms

    def _synchronize_clocks(self, sender: str, receiver: str):
        """Cross-service message reception: update logical clocks."""
        # Lamport max + 1
        self.lamport_clocks[receiver] = max(self.lamport_clocks[receiver], self.lamport_clocks[sender])
        # Vector element-wise max
        for s in SERVICE_CONFIGS:
            self.vector_clocks[receiver][s] = max(
                self.vector_clocks[receiver].get(s, 0),
                self.vector_clocks[sender].get(s, 0),
            )
        # HLC receive
        r_pt, r_l = self.hlc_clocks[receiver]
        s_pt, s_l = self.hlc_clocks[sender]
        now_pt = time.time() + (self.clock_skews_ms.get(receiver, 0.0) / 1000.0)
        max_pt = max(r_pt, s_pt, now_pt)
        if max_pt == r_pt and max_pt == s_pt:
            self.hlc_clocks[receiver] = (max_pt, max(r_l, s_l) + 1)
        elif max_pt == r_pt:
            self.hlc_clocks[receiver] = (max_pt, r_l + 1)
        elif max_pt == s_pt:
            self.hlc_clocks[receiver] = (max_pt, s_l + 1)
        else:
            self.hlc_clocks[receiver] = (max_pt, 0)

    def emit_event(
        self,
        service_id: str,
        event_type: str,
        trace_id: str,
        parent_event_ids: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        network_delay_ms: float = 0.0,
    ) -> Event:
        """Create and emit an event from a microservice."""
        conf = SERVICE_CONFIGS.get(service_id, {
            "region": "unknown",
            "availability_zone": "unknown",
            "clock_uncertainty_ms": 5.0,
        })

        lamport, vc, hlc, wall_ms = self._tick_clocks(service_id)
        arrival_ms = time.time() * 1000.0

        if self.simulate_network_delay:
            arrival_ms += network_delay_ms

        return Event(
            event_id=f"E-{str(uuid.uuid4())[:8]}",
            service_id=service_id,
            event_type=event_type,
            timestamp_ms=wall_ms,
            arrival_time_ms=arrival_ms,
            lamport_ts=lamport,
            vector_clock=vc,
            hlc_ts=hlc,
            trace_id=trace_id,
            span_id=str(uuid.uuid4())[:8],
            parent_event_ids=parent_event_ids or [],
            payload=payload or {},
            metadata=EventMetadata(
                region=conf["region"],
                availability_zone=conf["availability_zone"],
                clock_uncertainty_ms=conf["clock_uncertainty_ms"],
                tags={"environment": "production-sim", "tier": "microservices"},
            ),
        )

    def generate_ecommerce_trace(self, trace_id: Optional[str] = None) -> List[Event]:
        """Generate a complete end-to-end distributed order trace across 5 services.
        
        Causal Sequence:
          E1: Order Created (order-svc, Mumbai)
          E2: Payment Started (payment-svc, Singapore)
          E3: Payment Completed (payment-svc, Singapore)
          E4: Inventory Reserved (inventory-svc, GCP Mumbai)
          E5: Shipment Created (shipping-svc, GCP Singapore)
          E6: Notification Sent (notification-svc, Mumbai)
        """
        tid = trace_id or f"T-{str(uuid.uuid4())[:6]}"
        events = []

        # 1. Order Created
        e1 = self.emit_event(
            "order-svc",
            "ORDER_CREATED",
            trace_id=tid,
            payload={"order_id": f"ORD-{tid}", "amount": 250.0},
            network_delay_ms=10.0,
        )
        events.append(e1)

        # 2. Payment Started (cross-region Mumbai -> Singapore)
        self._synchronize_clocks("order-svc", "payment-svc")
        e2 = self.emit_event(
            "payment-svc",
            "PAYMENT_STARTED",
            trace_id=tid,
            parent_event_ids=[e1.event_id],
            payload={"gateway": "Stripe", "currency": "USD"},
            network_delay_ms=85.0,  # cross-region network lag
        )
        events.append(e2)

        # 3. Payment Completed
        e3 = self.emit_event(
            "payment-svc",
            "PAYMENT_COMPLETED",
            trace_id=tid,
            parent_event_ids=[e2.event_id],
            payload={"status": "SUCCESS", "tx_hash": f"TXN-{str(uuid.uuid4())[:8]}"},
            network_delay_ms=15.0,
        )
        events.append(e3)

        # 4. Inventory Reserved (Singapore -> GCP Mumbai)
        self._synchronize_clocks("payment-svc", "inventory-svc")
        e4 = self.emit_event(
            "inventory-svc",
            "INVENTORY_RESERVED",
            trace_id=tid,
            parent_event_ids=[e3.event_id],
            payload={"sku": "SKU-9921", "qty": 1, "warehouse": "bom-1"},
            network_delay_ms=110.0,
        )
        events.append(e4)

        # 5. Shipment Created (GCP Mumbai -> GCP Singapore)
        self._synchronize_clocks("inventory-svc", "shipping-svc")
        e5 = self.emit_event(
            "shipping-svc",
            "SHIPMENT_CREATED",
            trace_id=tid,
            parent_event_ids=[e4.event_id],
            payload={"carrier": "DHL Express", "tracking": f"TRK-{str(uuid.uuid4())[:10]}"},
            network_delay_ms=45.0,
        )
        events.append(e5)

        # 6. Notification Sent (GCP Singapore -> AWS Mumbai)
        self._synchronize_clocks("shipping-svc", "notification-svc")
        e6 = self.emit_event(
            "notification-svc",
            "NOTIFICATION_SENT",
            trace_id=tid,
            parent_event_ids=[e5.event_id],
            payload={"channel": "SMS_EMAIL", "recipient": "customer@chronosmesh.io"},
            network_delay_ms=25.0,
        )
        events.append(e6)

        # Out-of-order delivery simulation:
        # Deliberately adjust arrival_time_ms to cause out-of-order Kafka consumption:
        # E1 -> E3 -> E2 -> E5 -> E4 -> E6
        if self.simulate_out_of_order:
            base_arrival = time.time() * 1000.0
            e1.arrival_time_ms = base_arrival + 10.0   # 1st to arrive
            e3.arrival_time_ms = base_arrival + 30.0   # 2nd to arrive (OUT OF ORDER - before parent E2!)
            e2.arrival_time_ms = base_arrival + 70.0   # 3rd to arrive (late parent arrival)
            e5.arrival_time_ms = base_arrival + 90.0   # 4th to arrive (OUT OF ORDER - before parent E4!)
            e4.arrival_time_ms = base_arrival + 130.0  # 5th to arrive (late parent arrival)
            e6.arrival_time_ms = base_arrival + 150.0  # 6th to arrive

        return events
