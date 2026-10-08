"""
ChronosMesh API — Canonical Pydantic response schemas.

These models define the stable contract between:
  - Akshith's core engine (Stage 1 outputs)
  - This API layer (Guru's work)
  - The React/JS frontend (Stage 3)

Design decisions:
  - All models inherit from BaseModel (Pydantic v2).
  - Fields map 1:1 to the Stage-1 Event dataclass fields.
  - Optional fields mirror what the engine may or may not populate.
  - No fields are invented; all are verified against chronosmesh/events/event.py.

Author: B. Guru Sai Prasad Reddy
Stage: 2 — Interface & Schema Foundation
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Metadata ──────────────────────────────────────────────────────────────────

class MetadataResponse(BaseModel):
    """EventMetadata fields as returned by the API."""
    region: str = "unknown"
    availability_zone: str = "unknown"
    clock_uncertainty_ms: float = 5.0
    tags: Dict[str, str] = Field(default_factory=dict)


# ── Event ─────────────────────────────────────────────────────────────────────

class EventResponse(BaseModel):
    """
    Full event as returned by GET /api/events/ and GET /api/events/{event_id}.

    Maps directly from Event.to_dict() with no field renaming.
    The frontend uses this for event detail panels and timeline view.
    """
    event_id: str
    service_id: str
    event_type: str
    timestamp_ms: float
    arrival_time_ms: float
    lamport_ts: int
    vector_clock: Dict[str, int] = Field(default_factory=dict)
    hlc_ts: Optional[Dict[str, Any]] = None          # {"pt": float, "l": int}
    trace_id: str
    span_id: str
    parent_event_ids: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: MetadataResponse = Field(default_factory=MetadataResponse)


class EventIngestRequest(BaseModel):
    """
    Schema for POST /api/events/ (planned endpoint).
    Allows external services or Surya's Kafka adapter to push events.

    Required fields match the Event dataclass required fields.
    Optional fields have sensible defaults.
    """
    event_id: Optional[str] = None          # auto-generated if absent
    service_id: str
    event_type: str
    timestamp_ms: float
    lamport_ts: int = 0
    vector_clock: Dict[str, int] = Field(default_factory=dict)
    hlc_ts: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None          # auto-generated if absent
    span_id: Optional[str] = None           # auto-generated if absent
    parent_event_ids: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: MetadataResponse = Field(default_factory=MetadataResponse)
    arrival_time_ms: Optional[float] = None # set to now() if absent


# ── DAG Node and Edge ─────────────────────────────────────────────────────────

class DAGNodeResponse(BaseModel):
    """
    One node in the causal DAG as returned by GET /api/dag/.

    Note: metadata fields (region, clock_uncertainty_ms) are flattened
    directly onto the node — they are NOT nested under "metadata".
    This matches store.get_dag_json() behaviour.
    """
    id: str                                           # same as event_id
    service_id: str
    event_type: str
    timestamp_ms: float
    lamport_ts: int
    vector_clock: Dict[str, int] = Field(default_factory=dict)
    region: str = "unknown"
    clock_uncertainty_ms: float = 5.0
    parent_event_ids: List[str] = Field(default_factory=list)


class DAGEdgeResponse(BaseModel):
    """
    One edge in the causal DAG.
    source → target means source HAPPENS_BEFORE target.
    """
    source: str
    target: str
    explicit: bool = False   # True if declared via parent_event_ids


class DAGResponse(BaseModel):
    """Full causal DAG as returned by GET /api/dag/."""
    nodes: List[DAGNodeResponse]
    edges: List[DAGEdgeResponse]
    topological_order: List[str]   # event_ids in causal order
    roots: List[str]               # event_ids with in-degree 0
    leaves: List[str]              # event_ids with out-degree 0


# ── Timeline ─────────────────────────────────────────────────────────────────

class TimelineStepResponse(BaseModel):
    """One step in the causal timeline (GET /api/dag/timeline)."""
    step: int
    event_id: str
    service_id: str
    event_type: str
    timestamp_ms: float
    arrival_time_ms: float
    lamport_ts: int
    vector_clock: Dict[str, int] = Field(default_factory=dict)
    trace_id: str
    region: str = "unknown"


class TimelineResponse(BaseModel):
    timeline: List[TimelineStepResponse]
    total_steps: int


# ── Anomaly ───────────────────────────────────────────────────────────────────

class AnomalyItemResponse(BaseModel):
    """
    One anomaly from CausalAnomalyDetector.
    Maps from AnomalyReport dataclass in chronosmesh/analysis/anomaly.py.
    """
    anomaly_type: str                    # "CYCLE" | "TIME_INVERSION" | "DUPLICATE_EVENT"
    severity: str                        # "CRITICAL" | "WARNING" | "INFO"
    source_event_id: str
    target_event_id: Optional[str] = None
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AnomalyResponse(BaseModel):
    anomalies: List[AnomalyItemResponse]
    total: int
    severity_summary: Dict[str, int]     # {"CRITICAL": 0, "WARNING": 1, "INFO": 0}


# ── Confidence ────────────────────────────────────────────────────────────────

class ConfidenceEdgeResponse(BaseModel):
    """
    One confidence-scored edge.
    Maps from EdgeConfidence dataclass in chronosmesh/analysis/confidence.py.
    """
    source: str
    target: str
    confidence: float                    # 0.0–1.0
    method: str                          # "explicit" | "vector_clock" | "physical_time"
    uncertainty_ms: float


class ConfidenceResponse(BaseModel):
    edge_scores: List[ConfidenceEdgeResponse]
    low_confidence_edges: List[ConfidenceEdgeResponse]
    average_confidence: float


# ── Root Cause ────────────────────────────────────────────────────────────────

class RootCauseItemResponse(BaseModel):
    """One root cause entry from RootCauseTracer."""
    event_id: str
    service_id: str
    event_type: str
    depth: int
    path: List[str]
    confidence: float


class RootCauseResponse(BaseModel):
    failure_event_id: str
    root_causes: List[RootCauseItemResponse]
    trace_paths: List[List[str]]
    critical_path: List[str]
    root_cause_count: int


# ── What-If ───────────────────────────────────────────────────────────────────

class WhatIfResponse(BaseModel):
    """
    Blast radius result from WhatIfSimulator.simulate_removal().
    Note: Python Sets are serialized to Lists for JSON compatibility.
    """
    removed_event_id: str
    blast_radius_pct: float              # 0.0–100.0
    cascade_depth: int
    invalidated_events: List[str]
    surviving_events: List[str]
    affected_services: List[str]
    invalidated_count: int


# ── Benchmark ─────────────────────────────────────────────────────────────────

class BenchmarkResultResponse(BaseModel):
    """One strategy result from ClockBenchmark."""
    strategy: str                        # "vector_clock" | "lamport_clock" | "physical_time"
    accuracy_pct: float
    memory_kb: float
    computation_time_ms: float
    correct_orderings: int
    total_orderings: int
    false_positives: int
    false_negatives: int


class BenchmarkResponse(BaseModel):
    parameters: Dict[str, Any]
    results: List[BenchmarkResultResponse]
    winner: str


# ── Scenario ─────────────────────────────────────────────────────────────────

class ScenarioResponse(BaseModel):
    """Scenario metadata from SCENARIO_CATALOGUE."""
    id: str
    name: str
    description: str
    pattern: str
    expected_nodes: int
    services: List[str]


class ScenarioLoadResponse(BaseModel):
    """Response from POST /api/scenarios/{name}/load."""
    scenario: ScenarioResponse
    dag: DAGResponse
    arrival_order: List[EventResponse]
    causal_order: List[EventResponse]
    event_count: int


# ── Health & Metrics ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class MetricsResponse(BaseModel):
    event_count: int
    dag_nodes: int
    dag_edges: int
    services_tracked: int
    current_scenario: Optional[str]
    api_version: str
