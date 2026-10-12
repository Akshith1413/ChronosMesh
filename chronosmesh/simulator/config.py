"""Experiment configuration with the ranges from the ChronosMesh blueprint (§9)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Dict

DELIVERY_MODES = ("in_order", "randomized", "heavily_delayed")
TRANSPORTS = ("direct", "sqs")

LIMITS = {
    "num_services": (2, 50),
    "num_events": (10, 100_000),
    "network_delay_ms": (0.0, 2000.0),
    "duplicate_rate": (0.0, 0.10),
    "missing_rate": (0.0, 0.05),
    "clock_drift_ms": (0.0, 5000.0),
    "cross_region_delay_ms": (0.0, 2000.0),
    "metadata_loss_rate": (0.0, 1.0),
    "events_per_execution": (5, 100_000),
    "retry_rate": (0.0, 0.10),
    "retry_burst": (2, 20),
    "worker_failures": (0, 10),
    "repeats": (1, 30),
}


@dataclass
class ExperimentConfig:
    name: str = "experiment"
    num_services: int = 4
    num_events: int = 1000
    events_per_execution: int = 20
    network_delay_ms: float = 200.0
    duplicate_rate: float = 0.0
    missing_rate: float = 0.0
    clock_drift_ms: float = 0.0
    cross_region_delay_ms: float = 0.0   # extra delivery delay for services far from the ingestion region
    metadata_loss_rate: float = 0.0
    retry_rate: float = 0.0          # fraction of events that trigger a burst of retries (retry storm)
    retry_burst: int = 6             # retries per storm (the detector flags >= 5 of the same operation)
    delivery_mode: str = "randomized"
    worker_failures: int = 0
    repeats: int = 1
    seed: int = 42
    transport: str = "direct"
    # Probability that an event is triggered by earlier events (vs. starting a new flow).
    branching: float = 0.7

    def validate(self, *, max_events: int | None = None) -> "ExperimentConfig":
        for key, (lo, hi) in LIMITS.items():
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{key} must be a number")
            if not lo <= value <= hi:
                raise ValueError(f"{key}={value} outside allowed range [{lo}, {hi}]")
        if max_events is not None and self.num_events > max_events:
            raise ValueError(f"num_events={self.num_events} exceeds this deployment's limit of {max_events}")
        if self.delivery_mode not in DELIVERY_MODES:
            raise ValueError(f"delivery_mode must be one of {DELIVERY_MODES}")
        if self.transport not in TRANSPORTS:
            raise ValueError(f"transport must be one of {TRANSPORTS}")
        if not 0.0 <= self.branching <= 1.0:
            raise ValueError("branching must be within [0, 1]")
        for key in ("num_services", "num_events", "events_per_execution", "retry_burst", "worker_failures", "repeats", "seed"):
            setattr(self, key, int(getattr(self, key)))
        self.events_per_execution = min(self.events_per_execution, self.num_events)
        return self

    @property
    def num_executions(self) -> int:
        return -(-self.num_events // max(1, self.events_per_execution))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown experiment parameter(s): {sorted(unknown)}")
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
