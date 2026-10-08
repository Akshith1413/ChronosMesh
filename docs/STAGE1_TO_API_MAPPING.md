# Stage 1 → API Mapping

> **Author:** B. Guru Sai Prasad Reddy — Stage 2 Documentation  
> **Source:** Actual code inspection of `chronosmesh/` engine and `api/` layer

---

## Mapping Table

| Stage-1 Output | Source Class/Module | Source Method/Field | API Representation | API Endpoint | Frontend Use |
|---|---|---|---|---|---|
| `Event` object | `chronosmesh/events/event.py` | `Event.to_dict()` | `EventResponse` (dict) | `GET /api/events/` | Event details panel, timeline |
| `EventMetadata` | `chronosmesh/events/event.py` | `EventMetadata.to_dict()` | Flattened into node: `region`, `clock_uncertainty_ms` | `GET /api/dag/` nodes | DAG node tooltip, confidence coloring |
| `nx.DiGraph` (DAG) | `chronosmesh/causality/dag_builder.py` | `CausalDAGBuilder.build()` | `DAGResponse` via `store.get_dag_json()` | `GET /api/dag/` | DAG visualizer (D3.js) |
| DAG nodes | `chronosmesh/causality/dag_builder.py` | `_add_node()` writes to `dag.nodes[event_id]` | Node objects in `dag.nodes[]` array | `GET /api/dag/` | Graph nodes, tooltips |
| DAG edges | `chronosmesh/causality/dag_builder.py` | `dag.add_edge(u, v)` | Edge objects in `dag.edges[]` array | `GET /api/dag/` | Graph edges, arrows |
| `CausalRelation.HAPPENS_BEFORE` | `chronosmesh/clocks/base.py` | Enum value -1 | `"explicit": bool` on edge | `GET /api/dag/` edges | Edge style (solid vs dashed) |
| `CausalRelation.CONCURRENT` | `chronosmesh/clocks/base.py` | Enum value 2 | No edge in DAG | — | No arrow between concurrent nodes |
| Topological sort | `chronosmesh/causality/dag_builder.py` | `topological_order()` → `nx.topological_sort()` | `topological_order: [event_id...]` | `GET /api/dag/` | Timeline causal order |
| Arrival order | `api/store.py` | `ChronosMeshStore.arrival_order` (shuffled list) | `arrival_order: [event_dict...]` | `POST /api/scenarios/{name}/load` | Left panel of dual-view |
| Ancestors | `chronosmesh/causality/dag_builder.py` | `get_ancestors()` → `nx.ancestors()` | `ancestors: [node_dict...]` | `GET /api/dag/ancestors/{id}` | Root-cause highlight, ancestor panel |
| Descendants | `chronosmesh/causality/dag_builder.py` | `get_descendants()` → `nx.descendants()` | `descendants: [node_dict...]` | `GET /api/dag/descendants/{id}` | Blast radius visualization |
| `EdgeConfidence` | `chronosmesh/analysis/confidence.py` | `ConfidenceScorer.score_all_edges()` | `{source, target, confidence, method, uncertainty_ms}` | `GET /api/analysis/confidence` | Edge color (green=high, red=low) |
| `AnomalyReport` | `chronosmesh/analysis/anomaly.py` | `CausalAnomalyDetector.detect_all()` | `{anomaly_type, severity, source_event_id, target_event_id, description, details}` | `GET /api/analysis/anomalies` | Anomaly alert panel, badge count |
| `RootCauseResult` | `chronosmesh/analysis/root_cause.py` | `RootCauseTracer.trace()` | `{failure_event_id, root_causes[], trace_paths[], critical_path[], root_cause_count}` | `GET /api/analysis/rootcause/{id}` | Root-cause tracing panel |
| `WhatIfResult` | `chronosmesh/analysis/what_if.py` | `WhatIfSimulator.simulate_removal()` | `{removed_event_id, blast_radius_pct, cascade_depth, invalidated_events[], surviving_events[], affected_services[]}` | `POST /api/analysis/whatif/{id}` | What-if lab: invalidated nodes in orange |
| `BenchmarkResult` | `chronosmesh/analysis/benchmarking.py` | `ClockBenchmark.benchmark()` | `{strategy, accuracy_pct, memory_kb, computation_time_ms, correct_orderings, false_positives, false_negatives}` | `GET /api/analysis/benchmark` | Clock comparison bar chart |
| `GraphDiffResult` | `chronosmesh/analysis/graph_diff.py` | `CausalGraphDiffer.diff()` | `{added_edges, removed_edges, added_nodes, removed_nodes, structural_similarity, behavioral_drift_score}` | `GET /api/analysis/graphdiff` | Graph diff view |
| `validate_event()` | `chronosmesh/events/schemas.py` | Pydantic `EventSchema` validation | Used in `api/schemas/event.py` for request validation | Any `POST` event endpoint | Client-side error display |

---

## Data Transformation Notes

### Store → API (Flattening)
`store.get_dag_json()` flattens `metadata` dict onto node level:
```python
# Engine DAG node:
node["metadata"] = {"region": "aws-mumbai", "clock_uncertainty_ms": 5.0, ...}

# API response node (flattened):
{"region": "aws-mumbai", "clock_uncertainty_ms": 5.0, ...}
```

### HLC not in DAG nodes
`hlc_ts` is stored on `Event` objects in `store.events` but not copied to `dag.nodes[]`. Retrieve via `GET /api/events/` when needed for display.

### Set → List serialization
`WhatIfResult` uses Python `Set` types for `invalidated_events` and `affected_services`. These are converted to `list()` in `analysis_router.py` before JSON serialization.

### Confidence scoring uses DAG node dicts
`ConfidenceScorer.score_all_edges()` reads directly from `dag.nodes[u]` and `dag.nodes[v]` — not from `Event` objects. This means it uses the flattened metadata dict on the node, not the nested `EventMetadata` object.
