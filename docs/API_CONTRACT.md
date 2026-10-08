# ChronosMesh API Contract

> **Author:** B. Guru Sai Prasad Reddy — Stage 2 Documentation  
> **Note:** Distinguishes EXISTING (working), PLANNED (defined but not implemented), and REQUIRES IMPLEMENTATION endpoints.

---

## Authentication

All endpoints except `/api/health` and `/auth/login` require:
```
Authorization: Bearer <JWT_token>
```
Obtain token via `POST /auth/login`.

---

## Endpoint Catalog

### `GET /api/health`

**Status:** ✅ EXISTING  
**Purpose:** Health check for Docker/Kubernetes probes  
**Request:** None  
**Response:**
```json
{"status": "healthy", "service": "chronosmesh-api", "version": "1.0.0"}
```
**Source of Data:** Hardcoded  
**Frontend Consumer:** System health widget

---

### `GET /api/metrics`

**Status:** ✅ EXISTING  
**Purpose:** Runtime metrics for monitoring panel  
**Request:** None  
**Response:**
```json
{
  "event_count": 8,
  "dag_nodes": 8,
  "dag_edges": 7,
  "services_tracked": 4,
  "current_scenario": "order_payment_flow",
  "api_version": "1.0.0"
}
```
**Source of Data:** `ChronosMeshStore` in-memory state  
**Stage-1 Dependency:** `api/store.py`  
**Frontend Consumer:** Metrics panel, system health widget

---

### `POST /auth/login`

**Status:** ✅ EXISTING  
**Purpose:** Obtain JWT access token  
**Request:** `application/x-www-form-urlencoded`: `username=guru&password=chronosmesh`  
**Response:**
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```
**Error Response:** `401 Unauthorized`  
**Source of Data:** `api/auth.py` in-memory user store  
**Frontend Consumer:** Login modal

---

### `GET /api/scenarios/`

**Status:** ✅ EXISTING  
**Purpose:** List available demo scenarios  
**Request:** Bearer token  
**Response:** Array of scenario objects:
```json
[
  {
    "id": "order_payment_flow",
    "name": "Order → Payment → Inventory → Shipping",
    "description": "...",
    "pattern": "chain",
    "expected_nodes": 8,
    "services": ["order-svc", "payment-svc", "inventory-svc", "shipping-svc"]
  }
]
```
**Source of Data:** `SCENARIO_CATALOGUE` in `api/routers/scenarios_router.py`  
**Frontend Consumer:** Scenario selector panel

---

### `POST /api/scenarios/{scenario_name}/load`

**Status:** ✅ EXISTING  
**Purpose:** Load and reconstruct causality for a named scenario  
**Request:** Bearer token; path param `scenario_name` ∈ {`order_payment_flow`, `concurrent_branches`, `diamond_pattern`}  
**Response:**
```json
{
  "scenario": {...},
  "dag": {"nodes": [], "edges": [], "topological_order": [], "roots": [], "leaves": []},
  "arrival_order": [...],
  "causal_order": [...],
  "event_count": 8
}
```
**Error Response:** `404` if scenario not found  
**Source of Data:** `ScenarioBuilder` → `ChronosMeshStore` → `CausalDAGBuilder`  
**Stage-1 Dependency:** `chronosmesh/events/generator.py`, `chronosmesh/causality/dag_builder.py`  
**Frontend Consumer:** Dual-view panel (arrival vs causal order)

---

### `DELETE /api/scenarios/`

**Status:** ✅ EXISTING  
**Purpose:** Clear all events from the in-memory store  
**Response:** `{"message": "Store cleared successfully"}`  
**Frontend Consumer:** Reset button

---

### `GET /api/events/`

**Status:** ✅ EXISTING  
**Purpose:** Return all events in the store as raw dicts  
**Response:** Array of event dicts (full `Event.to_dict()` format)  
**Source of Data:** `store.events`  
**Frontend Consumer:** Event details, timeline

---

### `GET /api/dag/`

**Status:** ✅ EXISTING  
**Purpose:** Return full causal DAG as node/edge JSON for D3.js  
**Response:**
```json
{
  "nodes": [{"id","service_id","event_type","timestamp_ms","lamport_ts","vector_clock","region","clock_uncertainty_ms","parent_event_ids"}],
  "edges": [{"source","target","explicit"}],
  "topological_order": ["event_id",...],
  "roots": ["event_id",...],
  "leaves": ["event_id",...]
}
```
**Source of Data:** `ChronosMeshStore.get_dag_json()`  
**Stage-1 Dependency:** `chronosmesh/causality/dag_builder.py`  
**Frontend Consumer:** DAG visualizer (D3.js / Cytoscape)

---

### `GET /api/dag/timeline`

**Status:** ✅ EXISTING  
**Purpose:** Return events in topological causal order (true causal timeline)  
**Response:**
```json
{"timeline": [{"step": 1, ...event_dict...}], "total_steps": 8}
```
**Frontend Consumer:** Timeline replay slider

---

### `GET /api/dag/ancestors/{event_id}`

**Status:** ✅ EXISTING  
**Purpose:** Get all causal ancestors of an event  
**Response:** `{"event_id","ancestors":[...node dicts...],"count":3}`  
**Frontend Consumer:** Root-cause tracing, DAG highlight

---

### `GET /api/dag/descendants/{event_id}`

**Status:** ✅ EXISTING  
**Purpose:** Get all causal descendants of an event  
**Response:** `{"event_id","descendants":[...node dicts...],"count":5}`  
**Frontend Consumer:** What-if blast radius visualization

---

### `GET /api/dag/neighbors/{event_id}`

**Status:** ✅ EXISTING  
**Purpose:** Get immediate parents and children  
**Response:** `{"event_id","immediate_parents":[],"immediate_children":[]}`  
**Frontend Consumer:** Node detail sidebar in DAG view

---

### `GET /api/dag/roots`

**Status:** ✅ EXISTING  
**Purpose:** Return root events (no causal parents)  
**Response:** `{"roots": [...node dicts...]}`  
**Frontend Consumer:** Root cause panel

---

### `GET /api/dag/leaves`

**Status:** ✅ EXISTING  
**Purpose:** Return leaf events (no causal children)  
**Response:** `{"leaves": [...node dicts...]}`  
**Frontend Consumer:** Failure event selection

---

### `GET /api/analysis/anomalies`

**Status:** ✅ EXISTING  
**Purpose:** Detect causal anomalies in the DAG  
**Response:**
```json
{
  "anomalies": [
    {
      "anomaly_type": "TIME_INVERSION",
      "severity": "WARNING",
      "source_event_id": "...",
      "target_event_id": "...",
      "description": "Causal child has older physical timestamp",
      "details": {"parent_ts": 1000.0, "child_ts": 999.0, "diff": 1.0}
    }
  ],
  "total": 1,
  "severity_summary": {"CRITICAL": 0, "WARNING": 1, "INFO": 0}
}
```
**Source of Data:** `CausalAnomalyDetector` on `store.dag`  
**Stage-1 Dependency:** `chronosmesh/analysis/anomaly.py`  
**Frontend Consumer:** Anomaly/alert panel, DAG edge highlighting

---

### `GET /api/analysis/confidence`

**Status:** ✅ EXISTING  
**Purpose:** TrueTime-style confidence scores for all causal edges  
**Response:**
```json
{
  "edge_scores": [{"source","target","confidence":0.9512,"method":"physical_time","uncertainty_ms":10.0}],
  "low_confidence_edges": [...],
  "average_confidence": 0.8734
}
```
**Source of Data:** `ConfidenceScorer` on `store.dag`  
**Stage-1 Dependency:** `chronosmesh/analysis/confidence.py`  
**Frontend Consumer:** DAG edge color coding

---

### `GET /api/analysis/rootcause/{event_id}`

**Status:** ✅ EXISTING  
**Purpose:** Trace root causes of a failure event  
**Response:**
```json
{
  "failure_event_id": "...",
  "root_causes": [{"event_id","service_id","event_type","depth":2,"path":["e1","e2","e3"],"confidence":1.0}],
  "trace_paths": [["e1","e2","e3"]],
  "critical_path": ["e1","e2","e3"],
  "root_cause_count": 1
}
```
**Source of Data:** `RootCauseTracer` on `store.dag`  
**Stage-1 Dependency:** `chronosmesh/analysis/root_cause.py`  
**Frontend Consumer:** Root-cause tracing panel

---

### `POST /api/analysis/whatif/{event_id}`

**Status:** ✅ EXISTING  
**Purpose:** Simulate removal of event — compute blast radius  
**Response:**
```json
{
  "removed_event_id": "...",
  "blast_radius_pct": 37.5,
  "cascade_depth": 3,
  "invalidated_events": ["e2","e3","e4"],
  "surviving_events": ["e5"],
  "affected_services": ["payment-svc","shipping-svc"],
  "invalidated_count": 3
}
```
**Source of Data:** `WhatIfSimulator` on `store.dag`  
**Stage-1 Dependency:** `chronosmesh/analysis/what_if.py`  
**Frontend Consumer:** What-if lab UI

---

### `GET /api/analysis/benchmark`

**Status:** ✅ EXISTING (stub data)  
**Purpose:** Compare Lamport vs Vector vs HLC clock strategies  
**Query Params:** `packet_loss_pct` (float, default 0), `clock_drift_ms` (float, default 0)  
**Response:**
```json
{
  "parameters": {"packet_loss_pct":0,"clock_drift_ms":0,"event_count":8},
  "results": [
    {"strategy":"vector_clock","accuracy_pct":100.0,"memory_kb":8.0,"computation_time_ms":10.0,"correct_orderings":7,"total_orderings":7,"false_positives":0,"false_negatives":0},
    {"strategy":"lamport_clock","accuracy_pct":50.0,...},
    {"strategy":"physical_time","accuracy_pct":50.0,...}
  ],
  "winner": "vector_clock"
}
```
**Source of Data:** `ClockBenchmark` (stub — hardcoded ratios)  
**Stage-1 Dependency:** `chronosmesh/analysis/benchmarking.py`  
**Frontend Consumer:** Clock comparison chart

---

### `GET /api/analysis/graphdiff`

**Status:** ✅ EXISTING  
**Purpose:** Compare current DAG run against a fresh regeneration of same scenario  
**Response:** `{"diff": {added/removed nodes+edges, structural_similarity, behavioral_drift_score}, "scenario": "..."}`  
**Source of Data:** `CausalGraphDiffer` comparing `store.dag` vs fresh build  
**Stage-1 Dependency:** `chronosmesh/analysis/graph_diff.py`  
**Frontend Consumer:** Graph diff view

---

### `GET /api/analysis/service-health`

**Status:** ✅ EXISTING  
**Purpose:** Deterministically derive service health from active DAG events and detected anomalies  
**Response:** `ServiceHealthReport` (`services`, `total_services`, `healthy_count`, `degraded_count`, `critical_count`, `unavailable_count`)  
**Source of Data:** `AnalysisService.get_service_health`  
**Frontend Consumer:** Dashboard Service Health Map

---

### `GET /api/analysis/clock-drift-timeline`

**Status:** ✅ EXISTING  
**Purpose:** Timeline of physical timestamps, arrival skew, and causal transit skews  
**Query Params:** `skew_tolerance_ms` (float, default 50.0)  
**Response:** `ClockDriftTimeline` (`data_points`, `max_arrival_skew_ms`, `inversion_count`)  
**Data Invariant:** Evaluated purely on physical timestamps and arrival delays. Logical clocks are preserved for ordering and never subtracted from ms.  
**Frontend Consumer:** Anomaly Center & Timeline

---

### `GET /api/analysis/latency-histogram`

**Status:** ✅ EXISTING  
**Purpose:** Distribution of positive edge transit times across causal edges  
**Query Params:** `bins` (int, default 5)  
**Response:** `LatencyHistogramReport` (`sample_size`, `p50_ms`, `p95_ms`, `p99_ms`, `min_ms`, `max_ms`, `mean_ms`, `bins`, `inversion_edge_count`)  
**Frontend Consumer:** Dashboard & Analytics page

---

### `GET /api/analysis/topology-stats`

**Status:** ✅ EXISTING  
**Purpose:** Graph-theoretic analysis of causal DAG using NetworkX  
**Response:** `TopologyStatsReport` (`node_count`, `edge_count`, `density`, `is_connected`, `longest_causal_path`, `coupling_metric`, `concurrency_ratio`)  
**Frontend Consumer:** Analytics page

---

### `GET /api/analysis/event-replay`

**Status:** ✅ EXISTING  
**Purpose:** Causal playback layers via DAG topological generations preserving true concurrency  
**Response:** `EventReplayReport` (`total_layers`, `total_events`, `max_parallelism`, `layers`)  
**Frontend Consumer:** Analytics page Event Replay view

