"""Ground-truth workload generator.

An experiment is a stream of independent business executions (think: many users each
placing an order) spread over ``num_services`` services. Inside an execution events are
causally linked through message passing (fork / join), across executions they are
unrelated. The generator keeps its own *true* vector clocks and true wall-clock times;
the reconstruction engine only ever sees the (possibly corrupted) copies produced by
``faults``.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.simulator.config import ExperimentConfig

BASE_TIME_MS = 1_760_000_000_000.0
MEAN_EVENT_GAP_MS = 4.0       # mean gap between events inside one execution
MEAN_START_GAP_MS = 25.0      # mean gap between execution start times
WINDOW = 6                    # how far back an event looks for its triggering events
JOIN_P = 0.25                 # probability of a second (join) parent

CANONICAL_SERVICES = [
    ("order-service", "aws-mumbai", ["ORDER_CREATED", "ORDER_VALIDATED", "ORDER_CONFIRMED", "ORDER_CLOSED"]),
    ("payment-service", "aws-singapore", ["PAYMENT_STARTED", "PAYMENT_AUTHORIZED", "PAYMENT_COMPLETED", "PAYMENT_REFUNDED"]),
    ("inventory-service", "gcp-mumbai", ["STOCK_CHECKED", "STOCK_RESERVED", "STOCK_RELEASED", "STOCK_UPDATED"]),
    ("shipping-service", "gcp-singapore", ["SHIPMENT_PLANNED", "SHIPMENT_CREATED", "SHIPMENT_DISPATCHED", "SHIPMENT_DELIVERED"]),
]
REGIONS = ["aws-mumbai", "aws-singapore", "gcp-mumbai", "gcp-singapore"]
GENERIC_TYPES = ["REQUEST_RECEIVED", "STATE_UPDATED", "MESSAGE_PUBLISHED", "TASK_COMPLETED"]


def make_services(n: int) -> List[Tuple[str, str, List[str]]]:
    services = list(CANONICAL_SERVICES[: min(n, len(CANONICAL_SERVICES))])
    for i in range(len(services), n):
        services.append((f"svc-{i + 1:02d}", REGIONS[i % len(REGIONS)], GENERIC_TYPES))
    return services


@dataclass
class GroundTruth:
    """Everything the simulator knows that the engine must *not* be given."""

    events: List[Event]                      # all events sorted by true time, TRUE clocks
    executions: Dict[str, List[Event]]       # execution_id -> its events (generation order)
    true_time_ms: Dict[str, float]
    services: List[str]
    regions: Dict[str, str]
    seed: int = 0
    meta: Dict[str, int] = field(default_factory=dict)

    def event_ids(self) -> set:
        return {e.event_id for e in self.events}


def generate_workload(cfg: ExperimentConfig, seed: int) -> GroundTruth:
    rng = random.Random(seed)
    services = make_services(cfg.num_services)
    names = [s[0] for s in services]
    region_of = {s[0]: s[1] for s in services}
    types_of = {s[0]: s[2] for s in services}

    executions: Dict[str, List[Event]] = {}
    true_time: Dict[str, float] = {}
    remaining = cfg.num_events
    start = BASE_TIME_MS

    for e in range(cfg.num_executions):
        k = min(cfg.events_per_execution, remaining)
        remaining -= k
        start += rng.expovariate(1.0 / MEAN_START_GAP_MS)
        execution_id = f"exec-{seed:04d}-{e:05d}"

        local_vc: Dict[str, Dict[str, int]] = {n: {} for n in names}
        local_lamport: Dict[str, int] = {n: 0 for n in names}
        window: deque = deque(maxlen=WINDOW)
        evs: List[Event] = []
        t = start

        while len(evs) < k:
            i = len(evs)
            t += rng.expovariate(1.0 / MEAN_EVENT_GAP_MS) + 0.001
            svc = names[rng.randrange(len(names))]

            parents: List[Event] = []
            if window:
                n_par = 1 + (rng.random() < JOIN_P) + (rng.random() < JOIN_P / 3)
                chosen = set()
                for _ in range(n_par):
                    if rng.random() < cfg.branching:
                        chosen.add(rng.randrange(len(window)))     # fork from an older event
                    else:
                        chosen.add(len(window) - 1)                # continue the latest chain
                parents = [window[j] for j in sorted(chosen)]

            vc = dict(local_vc[svc])
            lamport = local_lamport[svc]
            for p in parents:
                for key, v in p.vector_clock.items():
                    if v > vc.get(key, 0):
                        vc[key] = v
                lamport = max(lamport, p.lamport_ts)
            vc[svc] = vc.get(svc, 0) + 1
            lamport += 1
            local_vc[svc] = vc
            local_lamport[svc] = lamport

            ev = Event(
                event_id=f"{execution_id}-{i:04d}",
                execution_id=execution_id,
                trace_id=execution_id,
                span_id=f"span-{e:05d}-{i:04d}",
                service_id=svc,
                event_type=types_of[svc][rng.randrange(len(types_of[svc]))],
                timestamp_ms=t,
                lamport_ts=lamport,
                vector_clock=dict(vc),
                hlc_ts=None,
                parent_event_ids=[p.event_id for p in parents],
                payload={},
                metadata=EventMetadata(region=region_of[svc], availability_zone=f"{region_of[svc]}-a",
                                       clock_uncertainty_ms=5.0),
                arrival_time_ms=t,
            )
            evs.append(ev)
            true_time[ev.event_id] = t
            window.append(ev)

            # Retry storm: the service re-executes the operation several times; each attempt is a real event
            # caused by the previous attempt and advances the service's clocks, so ground truth stays exact.
            if cfg.retry_rate and rng.random() < cfg.retry_rate and len(evs) < k:
                prev = ev
                for attempt in range(2, cfg.retry_burst + 2):
                    if len(evs) >= k:
                        break
                    t += rng.expovariate(1.0 / MEAN_EVENT_GAP_MS) + 0.001
                    vc = dict(local_vc[svc])
                    vc[svc] = vc.get(svc, 0) + 1
                    lamport = local_lamport[svc] + 1
                    local_vc[svc], local_lamport[svc] = vc, lamport
                    retry = Event(
                        event_id=f"{execution_id}-{len(evs):04d}", execution_id=execution_id, trace_id=execution_id,
                        span_id=f"span-{e:05d}-{len(evs):04d}", service_id=svc, event_type=ev.event_type,
                        timestamp_ms=t, lamport_ts=lamport, vector_clock=dict(vc), hlc_ts=None,
                        parent_event_ids=[prev.event_id],
                        payload={"attempt": attempt, "retry_of": ev.event_id},
                        metadata=EventMetadata(region=region_of[svc], availability_zone=f"{region_of[svc]}-a",
                                               clock_uncertainty_ms=5.0),
                        arrival_time_ms=t,
                    )
                    evs.append(retry)
                    true_time[retry.event_id] = t
                    window.append(retry)
                    prev = retry
        executions[execution_id] = evs

    all_events = sorted((ev for evs in executions.values() for ev in evs), key=lambda x: true_time[x.event_id])
    return GroundTruth(all_events, executions, true_time, names, region_of, seed,
                       meta={"executions": len(executions)})
