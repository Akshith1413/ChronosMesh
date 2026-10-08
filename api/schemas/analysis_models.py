"""
Pydantic response models for ChronosMesh advanced analysis endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── 1. Service Health ─────────────────────────────────────────────────────────

class ServiceHealthItem(BaseModel):
    service_name: str
    status: str  # "Healthy" | "Degraded" | "Critical" | "Unavailable"
    event_count: int
    anomaly_count: int
    latest_activity_ms: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ServiceHealthReport(BaseModel):
    services: List[ServiceHealthItem]
    total_services: int
    healthy_count: int
    degraded_count: int
    critical_count: int
    unavailable_count: int
    timestamp_ms: float


# ── 2. Clock Drift Timeline ───────────────────────────────────────────────────

class ClockDriftPoint(BaseModel):
    event_id: str
    service_id: str
    timestamp_ms: float
    arrival_time_ms: float
    arrival_skew_ms: float
    causal_skew_ms: Optional[float] = None
    is_inversion: bool = False
    clock_type: str = "physical"


class ClockDriftTimeline(BaseModel):
    trace_id: Optional[str] = None
    data_points: List[ClockDriftPoint]
    max_arrival_skew_ms: float
    inversion_count: int
    skew_tolerance_ms: float
    methodology: str = (
        "Calculated from physical timestamps (timestamp_ms vs arrival_time_ms and "
        "causal edge transit delta). Logical clocks (Lamport/Vector) are strictly "
        "preserved for topological ordering and never subtracted from physical time."
    )


# ── 3. Latency Histogram ──────────────────────────────────────────────────────

class LatencyBin(BaseModel):
    bin_start_ms: float
    bin_end_ms: float
    count: int


class LatencyHistogramReport(BaseModel):
    sample_size: int
    p50_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None
    mean_ms: Optional[float] = None
    bins: List[LatencyBin] = Field(default_factory=list)
    inversion_edge_count: int = 0
    note: Optional[str] = None


# ── 4. Topology Stats ─────────────────────────────────────────────────────────

class LongestPathInfo(BaseModel):
    length: int
    path: List[str] = Field(default_factory=list)
    duration_ms: Optional[float] = None


class TopologyStatsReport(BaseModel):
    node_count: int
    edge_count: int
    density: float
    is_connected: bool
    connected_components: int
    root_nodes: List[str] = Field(default_factory=list)
    leaf_nodes: List[str] = Field(default_factory=list)
    longest_causal_path: LongestPathInfo
    coupling_metric: float  # Average degree: 2 * E / V
    concurrency_pairs_count: int
    concurrency_ratio: float  # Concurrent pairs / Total pairwise pairs


# ── 5. Event Replay (Causal Generations) ──────────────────────────────────────

class EventSummary(BaseModel):
    event_id: str
    service_id: str
    event_type: str
    timestamp_ms: float
    lamport_ts: int
    parents: List[str] = Field(default_factory=list)


class ReplayLayer(BaseModel):
    layer_index: int
    events: List[EventSummary]
    concurrent_count: int


class EventReplayReport(BaseModel):
    total_layers: int
    total_events: int
    max_parallelism: int
    layers: List[ReplayLayer]
