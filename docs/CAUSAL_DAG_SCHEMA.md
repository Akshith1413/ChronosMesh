# ChronosMesh Causal DAG Schema

> **Source:** Direct inspection of `chronosmesh/causality/dag_builder.py`, `api/store.py`, and all analysis modules  
> **Author:** B. Guru Sai Prasad Reddy — Stage 2 Documentation

---

## Overview

The causal graph is a **directed acyclic graph (DAG)** represented as a NetworkX `DiGraph`. Edges flow from cause to effect: `source → target` means "source happens-before target". After construction it undergoes **transitive reduction** to remove redundant edges.

---

## Node Model

Nodes are keyed by `event_id` (string). Each node carries these attributes set by `CausalDAGBuilder._add_node()`:

```python
node[event_id] = {
    "event_id":         str,          # same as key
    "service_id":       str,          # e.g. "order-svc"
    "event_type":       str,          # e.g. "ORDER_CREATED"
    "timestamp_ms":     float,        # wall-clock ms at emission
    "lamport_ts":       int,          # Lamport counter
    "vector_clock":     Dict[str,int],# full vector state
    "parent_event_ids": List[str],    # explicit parent declarations
    "metadata":         Dict,         # {region, availability_zone, clock_uncertainty_ms, tags}
}
```

**Note:** `hlc_ts`, `trace_id`, `span_id`, `payload`, and `arrival_time_ms` are stored on the `Event` object in `store.events` but **not** copied onto DAG nodes. The API retrieves them from `store.events` when needed.

### API Wire Format (per node in `GET /api/dag/`)

```json
{
  "id": "event_id_string",
  "service_id": "order-svc",
  "event_type": "ORDER_CREATED",
  "timestamp_ms": 1727506800000.0,
  "lamport_ts": 1,
  "vector_clock": {"order-svc": 1, "payment-svc": 0},
  "region": "aws-mumbai",
  "clock_uncertainty_ms": 5.0,
  "parent_event_ids": []
}
```

---

## Edge Model

Edges are directed: `(source_event_id, target_event_id)` where source → target means **source happens-before target**.

```python
dag.edges[source, target] = {
    "explicit": bool   # True if declared via parent_event_ids; False if inferred by clock comparison
}
```

### API Wire Format (per edge in `GET /api/dag/`)

```json
{
  "source": "source_event_id",
  "target": "target_event_id",
  "explicit": true
}
```

---

## Causal Relationship Types

Defined in `chronosmesh/clocks/base.py` as `CausalRelation` enum:

| Value | Int | Meaning |
|---|---|---|
| `HAPPENS_BEFORE` | -1 | Source causally precedes target (A → B edge in DAG) |
| `HAPPENS_AFTER` | 1 | Source follows target (B → A edge in DAG) |
| `CONCURRENT` | 2 | Events are causally independent (no edge, A ∥ B) |
| `EQUAL` | 0 | Identical timestamps (treated as equal, no edge) |

**Detection priority** in `HappensBeforeDetector.detect()`:
1. If both events have non-empty vector clocks → vector clock comparison
2. Otherwise → Lamport timestamp comparison, tie-broken by `event_id` lexicographic order

---

## Confidence Score

Source: `chronosmesh/analysis/confidence.py` → `EdgeConfidence` dataclass

```python
@dataclass
class EdgeConfidence:
    source_id: str
    target_id: str
    confidence: float    # 0.0–1.0 probability that source truly happens-before target
    method: str          # "explicit" | "vector_clock" | "physical_time"
    uncertainty_ms: float  # combined clock uncertainty of both events
```

**Scoring methods:**
- `"explicit"` → `confidence = 1.0` (declared via `parent_event_ids`)
- `"vector_clock"` → `confidence = 1.0` (vector clock confirms ordering)
- `"physical_time"` → Gaussian CDF: `P(t_a < t_b)` using `clock_uncertainty_ms` as σ/3

**API wire format** (per edge in `GET /api/analysis/confidence`):
```json
{
  "source": "event_id_a",
  "target": "event_id_b",
  "confidence": 0.9512,
  "method": "physical_time",
  "uncertainty_ms": 10.0
}
```

---

## Clock Metadata

Each node retains full clock context for offline re-analysis:

| Field on Node | Type | Clock System |
|---|---|---|
| `lamport_ts` | `int` | Lamport — scalar counter |
| `vector_clock` | `Dict[str,int]` | Vector clock — full service map |
| `metadata["clock_uncertainty_ms"]` | `float` | TrueTime-style uncertainty bound |

HLC (`hlc_ts`) is stored on the `Event` object but not on the DAG node. If needed for analysis, retrieve via `store.events`.

---

## Anomaly Metadata

Source: `chronosmesh/analysis/anomaly.py` → `AnomalyReport` dataclass

```python
@dataclass
class AnomalyReport:
    anomaly_type: str           # "CYCLE" | "TIME_INVERSION" | "DUPLICATE_EVENT"
    severity: str               # "CRITICAL" | "WARNING" | "INFO"
    source_event_id: str        # Primary event involved
    target_event_id: Optional[str]  # Secondary event (null for single-event anomalies)
    description: str            # Human-readable explanation
    details: Dict[str, Any]     # Extra info (e.g. cycle path, timestamp diff)
```

**Implemented anomaly types:**
- `CYCLE` (CRITICAL) — cycle detected in DAG via `nx.simple_cycles()`
- `TIME_INVERSION` (WARNING) — causal child has older physical timestamp > tolerance
- `DUPLICATE_EVENT` (WARNING) — same `event_id` appears more than once

**Stub anomaly types** (implementations empty, return `[]`):
- `VECTOR_CLOCK_GAP` — gaps in vector clock sequences
- `CLOCK_DRIFT` — excessive clock drift between services
- `CONCURRENT_MUTATION` — concurrent writes to same entity

---

## Root Cause Information

Source: `chronosmesh/analysis/root_cause.py` → `RootCauseResult` dataclass

```python
@dataclass
class RootCauseResult:
    failure_event_id: str
    root_causes: List[Dict[str, Any]]   # Each: {event_id, service_id, event_type, depth, path, confidence}
    trace_paths: List[List[str]]        # All simple paths from any root to failure event
```

**Algorithm:** Backward traversal from `failure_event_id` using `nx.ancestors()` → identify in-degree-0 nodes in subgraph.

---

## What-If Information

Source: `chronosmesh/analysis/what_if.py` → `WhatIfResult` dataclass

```python
@dataclass
class WhatIfResult:
    removed_event_id: str
    invalidated_events: Set[str]   # Events that would not occur if removed_event_id didn't happen
    surviving_events: Set[str]     # Descendants that survive (have at least one non-invalidated parent)
    blast_radius: float            # len(invalidated) / len(dag.nodes) ∈ [0.0, 1.0]
    affected_services: Set[str]    # service_ids of invalidated events
    cascade_depth: int             # Maximum topological depth of invalidation
```

---

## Example DAG (JSON representation)

Scenario: `concurrent_branches` (Order → Payment ∥ Inventory)

```json
{
  "nodes": [
    {"id": "e1", "service_id": "order-svc",     "event_type": "ORDER_CREATED",    "lamport_ts": 1, "vector_clock": {"order-svc":1,"payment-svc":0,"inventory-svc":0,"shipping-svc":0}},
    {"id": "e2", "service_id": "payment-svc",   "event_type": "PROCESS_PAYMENT",  "lamport_ts": 2, "vector_clock": {"order-svc":1,"payment-svc":1,"inventory-svc":0,"shipping-svc":0}},
    {"id": "e3", "service_id": "inventory-svc", "event_type": "RESERVE_INVENTORY","lamport_ts": 2, "vector_clock": {"order-svc":1,"payment-svc":0,"inventory-svc":1,"shipping-svc":0}}
  ],
  "edges": [
    {"source": "e1", "target": "e2", "explicit": true},
    {"source": "e1", "target": "e3", "explicit": true}
  ],
  "topological_order": ["e1", "e2", "e3"],
  "roots": ["e1"],
  "leaves": ["e2", "e3"]
}
```

> **Note:** e2 ∥ e3 — they are concurrent. No edge exists between them.
