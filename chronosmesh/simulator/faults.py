"""Fault injection: turns a ground-truth execution into what the platform actually receives."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Set

from chronosmesh.events.event import Event
from chronosmesh.simulator.config import ExperimentConfig
from chronosmesh.simulator.workload import GroundTruth


@dataclass
class DeliveryResult:
    delivered: List[Event]                     # arrival order, duplicates included
    dropped_ids: Set[str] = field(default_factory=set)
    duplicated_ids: Set[str] = field(default_factory=set)
    metadata_lost_ids: Set[str] = field(default_factory=set)
    service_offsets_ms: Dict[str, float] = field(default_factory=dict)

    @property
    def unique_delivered_ids(self) -> Set[str]:
        return {e.event_id for e in self.delivered}


# The platform ingests in aws-mumbai: other regions pay a fixed extra latency (scaled by ``cross_region_delay_ms``).
REGION_DISTANCE = {"aws-mumbai": 0.0, "gcp-mumbai": 0.15, "aws-singapore": 1.0, "gcp-singapore": 1.2}


def _delay_ms(rng: random.Random, cfg: ExperimentConfig, region: str = "aws-mumbai") -> float:
    d = cfg.network_delay_ms
    regional = REGION_DISTANCE.get(region, 0.5) * cfg.cross_region_delay_ms
    if cfg.delivery_mode == "in_order":
        return 1.0
    if cfg.delivery_mode == "randomized":
        return 1.0 + regional + rng.uniform(0.0, d)
    # heavily_delayed: heavy-tailed latency plus occasional stragglers
    delay = 1.0 + d * math.exp(rng.gauss(0.0, 1.2))
    if rng.random() < 0.05:
        delay *= rng.uniform(5.0, 10.0)
    return regional + min(delay, max(20.0 * d, 50.0) if d else 50.0)


def inject_faults(gt: GroundTruth, cfg: ExperimentConfig, seed: int) -> DeliveryResult:
    rng = random.Random(seed * 7919 + 13)
    offsets = {s: rng.uniform(-cfg.clock_drift_ms, cfg.clock_drift_ms) if cfg.clock_drift_ms else 0.0
               for s in gt.services}

    delivered: List[Event] = []
    dropped: Set[str] = set()
    duplicated: Set[str] = set()
    lost_meta: Set[str] = set()

    last_arrival = 0.0
    for ev in gt.events:
        if rng.random() < cfg.missing_rate:
            dropped.add(ev.event_id)
            continue

        copy_ev = copy.copy(ev)
        copy_ev.metadata = copy.copy(ev.metadata)
        copy_ev.vector_clock = dict(ev.vector_clock)
        copy_ev.parent_event_ids = list(ev.parent_event_ids)
        copy_ev.timestamp_ms = ev.timestamp_ms + offsets[ev.service_id] + rng.uniform(-0.5, 0.5)

        arrival = gt.true_time_ms[ev.event_id] + _delay_ms(rng, cfg, ev.metadata.region)
        if cfg.delivery_mode == "in_order":
            arrival = max(arrival, last_arrival + 1e-6)
            last_arrival = arrival
        copy_ev.arrival_time_ms = arrival

        if cfg.metadata_loss_rate and rng.random() < cfg.metadata_loss_rate:
            copy_ev.vector_clock = {}
            lost_meta.add(ev.event_id)

        delivered.append(copy_ev)

        if cfg.duplicate_rate and rng.random() < cfg.duplicate_rate:
            dup = copy.copy(copy_ev)
            dup.metadata = copy.copy(copy_ev.metadata)
            dup.vector_clock = dict(copy_ev.vector_clock)
            dup.parent_event_ids = list(copy_ev.parent_event_ids)
            dup.arrival_time_ms = arrival + 1.0 + rng.uniform(0.0, max(cfg.network_delay_ms, 5.0) * 2)
            delivered.append(dup)
            duplicated.add(ev.event_id)

    if not delivered:  # never deliver nothing
        first = copy.copy(gt.events[0])
        first.arrival_time_ms = gt.true_time_ms[first.event_id] + 1.0
        delivered.append(first)
        dropped.discard(first.event_id)

    delivered.sort(key=lambda e: e.arrival_time_ms)
    return DeliveryResult(delivered, dropped, duplicated, lost_meta, offsets)
