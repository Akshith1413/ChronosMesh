import time
import uuid
import random
from typing import Dict, List, Tuple, Any, Optional

from chronosmesh.events.event import Event, EventMetadata

class EventGenerator:
    def __init__(self, service_configs: List[Dict[str, Any]]):
        self.services = {}
        self.lamport_clocks = {}
        self.vector_clocks = {}
        self.hlc_clocks = {}
        for config in service_configs:
            sid = config["service_id"]
            self.services[sid] = config
            self.lamport_clocks[sid] = 0
            self.vector_clocks[sid] = {c["service_id"]: 0 for c in service_configs}
            self.hlc_clocks[sid] = (time.time(), 0)
        
        self.events = []
    
    def emit_event(self, service_id: str, event_type: str, parent_event_ids: Optional[List[str]] = None, payload: Optional[Dict[str, Any]] = None) -> Event:
        self.lamport_clocks[service_id] += 1
        self.vector_clocks[service_id][service_id] += 1
        
        pt = time.time()
        curr_pt, curr_l = self.hlc_clocks[service_id]
        if pt > curr_pt:
            self.hlc_clocks[service_id] = (pt, 0)
        else:
            self.hlc_clocks[service_id] = (curr_pt, curr_l + 1)
            
        evt = Event(
            event_id=str(uuid.uuid4()),
            service_id=service_id,
            event_type=event_type,
            timestamp_ms=time.time() * 1000,
            lamport_ts=self.lamport_clocks[service_id],
            vector_clock=dict(self.vector_clocks[service_id]),
            hlc_ts={"pt": self.hlc_clocks[service_id][0], "l": self.hlc_clocks[service_id][1]},
            parent_event_ids=parent_event_ids or [],
            payload=payload or {},
            metadata=EventMetadata(
                region=self.services[service_id].get("region", "unknown"),
                clock_uncertainty_ms=self.services[service_id].get("clock_uncertainty_ms", 5.0)
            )
        )
        self.events.append(evt)
        return evt

    def emit_send_receive(self, sender_id: str, receiver_id: str, send_type: str, receive_type: str) -> Tuple[Event, Event]:
        send_evt = self.emit_event(sender_id, send_type)
        
        self.lamport_clocks[receiver_id] = max(self.lamport_clocks[receiver_id], self.lamport_clocks[sender_id])
        for k, v in self.vector_clocks[sender_id].items():
            self.vector_clocks[receiver_id][k] = max(self.vector_clocks[receiver_id].get(k, 0), v)
            
        recv_evt = self.emit_event(receiver_id, receive_type, parent_event_ids=[send_evt.event_id])
        return send_evt, recv_evt

    def inject_network_delay(self, event: Event, delay_ms: float):
        event.arrival_time_ms += delay_ms

    def inject_clock_drift(self, service_id: str, drift_ms: float):
        pass # Simply a placeholder if needed, usually we change timestamp

    def get_events(self) -> List[Event]:
        return list(self.events)

    def get_events_by_arrival_order(self) -> List[Event]:
        return sorted(self.events, key=lambda x: x.arrival_time_ms)

    def shuffle_arrival_order(self, events: List[Event], seed: Optional[int] = None) -> List[Event]:
        if seed is not None:
            random.seed(seed)
        shuffled = list(events)
        random.shuffle(shuffled)
        return shuffled

class ScenarioBuilder:
    def __init__(self):
        self.configs = [
            {"service_id": "order-svc", "region": "aws-mumbai", "clock_uncertainty_ms": 5.0},
            {"service_id": "payment-svc", "region": "aws-mumbai", "clock_uncertainty_ms": 5.0},
            {"service_id": "inventory-svc", "region": "aws-mumbai", "clock_uncertainty_ms": 5.0},
            {"service_id": "shipping-svc", "region": "aws-mumbai", "clock_uncertainty_ms": 5.0}
        ]
        
    def order_payment_flow(self):
        gen = EventGenerator(self.configs)
        gen.emit_event("order-svc", "ORDER_CREATED")
        gen.emit_send_receive("order-svc", "payment-svc", "SEND_PAYMENT", "PAYMENT_STARTED")
        gen.emit_send_receive("payment-svc", "inventory-svc", "PAYMENT_DONE", "RESERVE_INVENTORY")
        gen.emit_send_receive("inventory-svc", "shipping-svc", "INVENTORY_RESERVED", "SHIP_ORDER")
        return gen.get_events()
        
    def concurrent_branches(self):
        gen = EventGenerator(self.configs)
        e1 = gen.emit_event("order-svc", "ORDER_CREATED")
        
        gen.lamport_clocks["payment-svc"] = max(gen.lamport_clocks["payment-svc"], gen.lamport_clocks["order-svc"])
        for k, v in gen.vector_clocks["order-svc"].items():
            gen.vector_clocks["payment-svc"][k] = max(gen.vector_clocks["payment-svc"].get(k, 0), v)
        gen.emit_event("payment-svc", "PROCESS_PAYMENT", parent_event_ids=[e1.event_id])
        
        gen.lamport_clocks["inventory-svc"] = max(gen.lamport_clocks["inventory-svc"], gen.lamport_clocks["order-svc"])
        for k, v in gen.vector_clocks["order-svc"].items():
            gen.vector_clocks["inventory-svc"][k] = max(gen.vector_clocks["inventory-svc"].get(k, 0), v)
        gen.emit_event("inventory-svc", "RESERVE_INVENTORY", parent_event_ids=[e1.event_id])
        
        return gen.get_events()
        
    def diamond_pattern(self):
        gen = EventGenerator(self.configs)
        e1 = gen.emit_event("order-svc", "ROOT")
        
        gen.lamport_clocks["payment-svc"] = max(gen.lamport_clocks["payment-svc"], gen.lamport_clocks["order-svc"])
        for k, v in gen.vector_clocks["order-svc"].items():
            gen.vector_clocks["payment-svc"][k] = max(gen.vector_clocks["payment-svc"].get(k, 0), v)
        e2 = gen.emit_event("payment-svc", "BRANCH_A", parent_event_ids=[e1.event_id])
        
        gen.lamport_clocks["inventory-svc"] = max(gen.lamport_clocks["inventory-svc"], gen.lamport_clocks["order-svc"])
        for k, v in gen.vector_clocks["order-svc"].items():
            gen.vector_clocks["inventory-svc"][k] = max(gen.vector_clocks["inventory-svc"].get(k, 0), v)
        e3 = gen.emit_event("inventory-svc", "BRANCH_B", parent_event_ids=[e1.event_id])
        
        gen.lamport_clocks["shipping-svc"] = max(gen.lamport_clocks["shipping-svc"], gen.lamport_clocks["payment-svc"], gen.lamport_clocks["inventory-svc"])
        for k, v in gen.vector_clocks["payment-svc"].items():
            gen.vector_clocks["shipping-svc"][k] = max(gen.vector_clocks["shipping-svc"].get(k, 0), v)
        for k, v in gen.vector_clocks["inventory-svc"].items():
            gen.vector_clocks["shipping-svc"][k] = max(gen.vector_clocks["shipping-svc"].get(k, 0), v)
            
        gen.emit_event("shipping-svc", "JOIN", parent_event_ids=[e2.event_id, e3.event_id])
        
        return gen.get_events()
        
    def chain(self, n):
        gen = EventGenerator(self.configs)
        last_id = None
        for i in range(n):
            e = gen.emit_event("order-svc", f"EVT_{i}", parent_event_ids=[last_id] if last_id else None)
            last_id = e.event_id
        return gen.get_events()

    def with_anomaly(self, type='time_inversion'):
        events = self.chain(2)
        if type == 'time_inversion':
            events[1].timestamp_ms, events[0].timestamp_ms = events[0].timestamp_ms, events[1].timestamp_ms
        return events
