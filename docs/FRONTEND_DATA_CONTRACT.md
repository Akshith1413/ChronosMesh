# ChronosMesh Frontend Data Contract

> **Author:** B. Guru Sai Prasad Reddy — Stage 2 Documentation  
> **Source:** Actual API responses from `api/store.py`, `api/routers/dag_router.py`, `api/routers/analysis_router.py`  
> **Consumer:** `frontend/js/app.js`, `frontend/js/dag-viz.js`, `frontend/js/timeline.js`, `frontend/js/charts.js`

---

## DAG Structure (consumed by `dag-viz.js`)

Consumed from `GET /api/dag/`. The D3.js visualizer uses this exact structure.

```typescript
interface DAGResponse {
  nodes: DAGNode[];
  edges: DAGEdge[];
  topological_order: string[];   // event_ids in causal order
  roots: string[];               // event_ids with no parents
  leaves: string[];              // event_ids with no children
}

interface DAGNode {
  id: string;                    // event_id — D3 node key
  service_id: string;            // "order-svc" — determines node color
  event_type: string;            // "ORDER_CREATED" — node label
  timestamp_ms: number;          // wall-clock ms — tooltip
  lamport_ts: number;            // integer — tooltip
  vector_clock: {[svc: string]: number};  // dict — tooltip
  region: string;                // "aws-mumbai" — node badge
  clock_uncertainty_ms: number;  // float — confidence display
  parent_event_ids: string[];    // explicit parents — edge style hint
}

interface DAGEdge {
  source: string;   // event_id
  target: string;   // event_id
  explicit: boolean; // true = solid line, false = dashed
}
```

### Service Color Mapping (from `frontend/css/styles.css`)

```
order-svc:     #3b82f6  (blue)
payment-svc:   #10b981  (emerald)
inventory-svc: #f59e0b  (amber)
shipping-svc:  #8b5cf6  (purple)
notification:  #ec4899  (pink)
unknown:       #64748b  (slate)
```

---

## Event Details (consumed by `app.js`)

Consumed from `GET /api/events/`. Each element is an `Event.to_dict()` output:

```typescript
interface EventDetail {
  event_id: string;
  service_id: string;
  event_type: string;
  timestamp_ms: number;
  arrival_time_ms: number;
  lamport_ts: number;
  vector_clock: {[svc: string]: number};
  hlc_ts: {pt: number; l: number} | null;
  trace_id: string;
  span_id: string;
  parent_event_ids: string[];
  payload: {[key: string]: any};
  metadata: {
    region: string;
    availability_zone: string;
    clock_uncertainty_ms: number;
    tags: {[key: string]: string};
  };
}
```

---

## Anomalies (consumed by `app.js` anomaly panel)

Consumed from `GET /api/analysis/anomalies`:

```typescript
interface AnomalyResponse {
  anomalies: Anomaly[];
  total: number;
  severity_summary: {CRITICAL: number; WARNING: number; INFO: number};
}

interface Anomaly {
  anomaly_type: "CYCLE" | "TIME_INVERSION" | "DUPLICATE_EVENT";
  severity: "CRITICAL" | "WARNING" | "INFO";
  source_event_id: string;
  target_event_id: string | null;
  description: string;
  details: {
    // TIME_INVERSION:
    parent_ts?: number;
    child_ts?: number;
    diff?: number;
    // CYCLE:
    cycle?: string[];
  };
}
```

### Severity → UI Mapping

```
CRITICAL → red badge (#ef4444), always visible
WARNING  → amber badge (#f59e0b), collapsible
INFO     → blue badge (#3b82f6), hidden by default
```

---

## Root Cause (consumed by `app.js` root-cause panel)

Consumed from `GET /api/analysis/rootcause/{event_id}`:

```typescript
interface RootCauseResponse {
  failure_event_id: string;
  root_causes: RootCause[];
  trace_paths: string[][];       // Each path is [event_id, ...]
  critical_path: string[];       // Longest path to failure
  root_cause_count: number;
}

interface RootCause {
  event_id: string;
  service_id: string;
  event_type: string;
  depth: number;                 // Hops from root to failure
  path: string[];                // [root_id, ..., failure_id]
  confidence: number;            // Always 1.0 in current implementation
}
```

---

## Timeline (consumed by `timeline.js`)

Consumed from `GET /api/dag/timeline` and `POST /api/scenarios/{name}/load`:

```typescript
interface TimelineResponse {
  timeline: TimelineStep[];   // causal (topological) order
  total_steps: number;
}

interface TimelineStep {
  step: number;               // 1-based causal step
  // ...all EventDetail fields...
  event_id: string;
  service_id: string;
  event_type: string;
  timestamp_ms: number;
  arrival_time_ms: number;
  lamport_ts: number;
}

// Arrival order (from load scenario response):
interface DualViewData {
  arrival_order: EventDetail[];  // shuffled network arrival order
  causal_order: EventDetail[];   // topological sort order
}
```

---

## What-If (consumed by `app.js` what-if lab)

Consumed from `POST /api/analysis/whatif/{event_id}`:

```typescript
interface WhatIfResponse {
  removed_event_id: string;
  blast_radius_pct: number;        // 0–100
  cascade_depth: number;
  invalidated_events: string[];    // event_ids to highlight in orange
  surviving_events: string[];      // event_ids that survive
  affected_services: string[];     // service_ids involved
  invalidated_count: number;
}
```

### UI Behavior

```
invalidated_events  → DAG nodes highlighted orange (#f97316)
surviving_events    → DAG nodes highlighted green (#10b981)
blast_radius_pct    → displayed as "X% of events invalidated"
cascade_depth       → displayed as "Max cascade depth: N hops"
```

---

## Benchmark (consumed by `charts.js`)

Consumed from `GET /api/analysis/benchmark?packet_loss_pct=0&clock_drift_ms=0`:

```typescript
interface BenchmarkResponse {
  parameters: {
    packet_loss_pct: number;
    clock_drift_ms: number;
    event_count: number;
  };
  results: BenchmarkResult[];
  winner: string;   // strategy name with highest accuracy
}

interface BenchmarkResult {
  strategy: "vector_clock" | "lamport_clock" | "physical_time";
  accuracy_pct: number;           // 0–100
  memory_kb: number;
  computation_time_ms: number;
  correct_orderings: number;
  total_orderings: number;
  false_positives: number;
  false_negatives: number;
}
```

### Chart.js Rendering

`charts.js` renders a grouped bar chart with:
- X-axis: strategy names
- Y-axis: accuracy_pct
- Bars colored: vector=#00d4ff, lamport=#8b5cf6, physical=#f59e0b

---

## Confidence Edges (consumed by `dag-viz.js`)

Consumed from `GET /api/analysis/confidence`:

```typescript
interface ConfidenceResponse {
  edge_scores: ConfidenceEdge[];
  low_confidence_edges: {source: string; target: string; confidence: number}[];
  average_confidence: number;
}

interface ConfidenceEdge {
  source: string;
  target: string;
  confidence: number;    // 0.0–1.0
  method: "explicit" | "vector_clock" | "physical_time";
  uncertainty_ms: number;
}
```

### Confidence → DAG Edge Color

```
0.9 – 1.0  →  #10b981  (emerald — high confidence)
0.7 – 0.9  →  #f59e0b  (amber — medium confidence)
0.0 – 0.7  →  #ef4444  (red — low confidence / anomalous)
"explicit"  →  solid stroke-width: 2
inferred    →  dashed stroke-dasharray: 4,4
```
