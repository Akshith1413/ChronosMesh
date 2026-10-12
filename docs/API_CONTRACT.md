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



---

# v2 — Experiments, Executions & Platform Status (✅ implemented 2026-10-12)

These endpoints implement the blueprint's API contract (§5). All require `Authorization: Bearer <token>`; every
execution/experiment is **owned by its creator** — other users get `404` (not `403`, so existence is not leaked);
admins can see everything. Errors use `{"detail": "..."}`.

| Method | Path | Role | Purpose |
|---|---|---|---|
| `GET` | `/auth/config` | public | `{demo_users_enabled}` — lets the UI hide one-click demo logins |
| `GET` | `/api/experiments/options` | viewer | Allowed parameter ranges, delivery modes, transports, deployment limits |
| `POST` | `/api/experiments` | analyst | Create an experiment (validated; **does not start it**). `201` |
| `POST` | `/api/experiments/{id}/start` | analyst | Start it. `202`; `409` if not in `created` |
| `GET` | `/api/experiments` | viewer | My experiments, newest first |
| `GET` | `/api/experiments/{id}` | viewer | Status (`created→queued→running/streaming→succeeded/failed`), progress, headline summary |
| `GET` | `/api/experiments/{id}/result` | viewer | Full evaluation (baselines, precision/recall/F1 with 95 % CI, concurrency, performance, fault tolerance) |
| `GET` | `/api/experiments/{id}/executions` | viewer | Drill-down executions sampled from the run |
| `POST` | `/api/executions` | analyst | Create a **live** execution to ingest events into |
| `GET` | `/api/executions` | viewer | My executions (`?kind=live|experiment|sample`) |
| `GET` | `/api/executions/{id}` | viewer | Record + statistics |
| `POST` | `/api/executions/{id}/events` | analyst | Ingest up to 1000 events (idempotent by `event_id`; `accepted`/`duplicates`/`rejected[{index,reason}]`) |
| `GET` | `/api/executions/{id}/events` | viewer | Events as received |
| `GET` | `/api/executions/{id}/graph` | viewer | Reconstructed causal graph: `nodes`, `edges` (`explicit`/`inferred`/`verified`/`via_gap`), `roots`, `leaves`, `topological_order`, `unresolved` |
| `GET` | `/api/executions/{id}/anomalies` | viewer | `?type=…&severity=…&limit=…` + `by_type`/`by_severity` counts |
| `GET` | `/api/executions/{id}/metrics` | viewer | Reconstruction statistics |
| `GET` | `/api/executions/{id}/truth` | viewer | Ground-truth edges (simulated executions only) |
| `POST` | `/api/executions/{id}/explore` | analyst | Load (≤ 400 events) into the caller's **private** Trace Explorer store |
| `GET` | `/api/system/status` | viewer | Storage health, ingest mode, SQS backlog/age, **worker heartbeat**, limits, dashboard links |
| `GET` | `/api/health/ready` | public | Readiness (verifies persistence); `503` when degraded |

### Experiment parameters (`POST /api/experiments`)

| Field | Range | Meaning |
|---|---|---|
| `num_services` | 2–50 | Simulated microservices (canonical order/payment/inventory/shipping first) |
| `num_events` | 10–100 000 (deployment cap `MAX_EXPERIMENT_EVENTS`) | Total events across all executions |
| `events_per_execution` | 5–num_events | Size of each business flow |
| `network_delay_ms` | 0–2000 | Maximum one-way delivery delay |
| `delivery_mode` | `in_order` \| `randomized` \| `heavily_delayed` | Delay model (heavy tail + stragglers) |
| `duplicate_rate` | 0–0.10 | Duplicate deliveries |
| `missing_rate` | 0–0.05 | Events lost in transit |
| `clock_drift_ms` | 0–5000 | Per-service wall-clock offset (±) |
| `metadata_loss_rate` | 0–1 | Fraction of events that lose their vector clock |
| `worker_failures` | 0–10 | Simulated worker crash/restarts (at-least-once redelivery) |
| `repeats` | 1–30 | Repeats with distinct seeds → mean ± 95 % CI |
| `transport` | `direct` \| `sqs` | In-process, or publish to the SQS queue for the worker (`repeats` must be 1) |

### Event ingestion contract (`POST /api/executions/{id}/events`)

```json
{"events": [{
  "event_id": "evt-104", "service": "payment-service", "event_type": "PAYMENT_COMPLETED",
  "trace_id": "trace-abc", "span_id": "span-payment-02", "parent_event_ids": ["evt-102"],
  "lamport_clock": 7,
  "vector_clock": {"order-service": 2, "payment-service": 4, "inventory-service": 1},
  "event_time": "2026-10-09T11:00:02Z"
}]}
```
`ingestion_time` and `execution_id` are **assigned by the platform** (the URL decides the execution; a client-supplied
value is ignored). Re-sending an `event_id` is safe. Internal field names (`service_id`, `lamport_ts`, `timestamp_ms`) are also accepted.

### Changes to existing endpoints
* `POST /graphql` requires authentication again (a regression had removed it) and resolves real data
  (`concurrent_pairs` and `causal_order` previously always returned empty).
* `GET /api/events/stream` now verifies its token (header, or `?token=` for `EventSource`).
* `GET /api/metrics` (JSON) requires authentication; Prometheus text format stays public unless `METRICS_TOKEN` is set.
