# ChronosMesh Stage 2 — Repository Audit

> **Author:** B. Guru Sai Prasad Reddy  
> **Inspected:** 2026-09-28  
> **Source:** Complete file-by-file audit of local repository  

---

## Existing Components

| Component | Location | Technology | Status | Purpose |
|---|---|---|---|---|
| Clock Base Interface | `chronosmesh/clocks/base.py` | Python ABC | ✅ Complete | `ClockStrategy` ABC + `CausalRelation` enum (HAPPENS_BEFORE=-1, CONCURRENT=2, EQUAL=0, HAPPENS_AFTER=1) |
| Lamport Clock | `chronosmesh/clocks/lamport.py` | Python dataclass | ✅ Complete | Per-service integer counter with merge logic |
| Vector Clock | `chronosmesh/clocks/vector.py` | Python dataclass | ✅ Complete | Per-service dict `{service_id: int}` with comparison operators |
| Hybrid Logical Clock | `chronosmesh/clocks/hlc.py` | Python dataclass | ✅ Complete | `(physical_time_ms, logical_counter)` combining wall clock + counter |
| Clock Factory | `chronosmesh/clocks/factory.py` | Python | ✅ Complete | Pluggable strategy registry: `"lamport"`, `"vector"`, `"hlc"` |
| Event Model | `chronosmesh/events/event.py` | Python dataclass | ✅ Complete | Core `Event` + `EventMetadata` with `to_dict()`/`from_dict()` |
| Event Generator | `chronosmesh/events/generator.py` | Python | ✅ Complete | `EventGenerator` + `ScenarioBuilder` (order_payment_flow, concurrent_branches, diamond_pattern) |
| Event Schemas | `chronosmesh/events/schemas.py` | Pydantic v2 | ✅ Complete | `EventSchema`, `EventMetadataSchema`, `validate_event()`, `serialize_event()`, `deserialize_event()` |
| Happens-Before Detector | `chronosmesh/causality/happens_before.py` | Python | ✅ Complete | Vector clock comparison → Lamport fallback |
| Concurrency Detector | `chronosmesh/causality/concurrency.py` | Python | ✅ Complete | Identifies concurrent event pairs |
| DAG Builder | `chronosmesh/causality/dag_builder.py` | NetworkX DiGraph | ✅ Complete | `CausalDAGBuilder`: batch build, incremental build, transitive reduction |
| Out-of-Order Buffer | `chronosmesh/causality/buffer.py` | Python | ✅ Complete | Watermark-based buffering for late-arriving events |
| Transitive Reduction | `chronosmesh/causality/transitive_reduction.py` | NetworkX | ✅ Complete | Removes redundant edges from DAG |
| Confidence Scorer | `chronosmesh/analysis/confidence.py` | Python + math | ✅ Complete | `EdgeConfidence` dataclass; TrueTime-style Gaussian CDF probability |
| Anomaly Detector | `chronosmesh/analysis/anomaly.py` | NetworkX | ✅ Complete | `AnomalyReport` dataclass; detects CYCLE, TIME_INVERSION, DUPLICATE_EVENT |
| Root Cause Tracer | `chronosmesh/analysis/root_cause.py` | NetworkX | ✅ Complete | `RootCauseResult`; backward DAG traversal, critical path |
| What-If Simulator | `chronosmesh/analysis/what_if.py` | NetworkX | ✅ Complete | `WhatIfResult`; forward reachability, blast radius, cascade depth |
| Clock Benchmarker | `chronosmesh/analysis/benchmarking.py` | Python | ✅ Stub | `BenchmarkResult`; compares vector/lamport/physical_time (dummy implementation) |
| Graph Differ | `chronosmesh/analysis/graph_diff.py` | NetworkX | ✅ Complete | `GraphDiffResult`; Jaccard similarity, structural drift score |
| Kafka Consumer | `chronosmesh/stream/consumer.py` | Mock/stub | ✅ Stub | Stubbed Kafka consumer interface |
| Stream Processor | `chronosmesh/stream/processor.py` | Python | ✅ Stub | Stateful DAG construction from event stream |
| Windowing | `chronosmesh/stream/windowing.py` | Python | ✅ Complete | Time-window logic for out-of-order event batching |
| FastAPI App | `api/main.py` | FastAPI | ✅ Complete | Main app: CORS, static files, router mounting, `/api/health`, `/api/metrics` |
| In-Memory Store | `api/store.py` | Python singleton | ✅ Complete | `ChronosMeshStore`: event list, DAG, arrival_order, scenario name |
| JWT Auth | `api/auth.py` | python-jose + passlib | ✅ Complete | `get_current_user` dependency, demo user store (guru/admin, demo/viewer) |
| Auth Router | `api/routers/auth_router.py` | FastAPI | ✅ Complete | `POST /auth/login` (OAuth2 password flow) |
| Scenarios Router | `api/routers/scenarios_router.py` | FastAPI | ✅ Complete | `GET /api/scenarios/`, `POST /api/scenarios/{name}/load`, `DELETE /api/scenarios/` |
| Events Router | `api/routers/events_router.py` | FastAPI | ✅ Partial | Basic event query endpoints |
| DAG Router | `api/routers/dag_router.py` | FastAPI | ✅ Complete | DAG, roots, leaves, timeline, ancestors, descendants, neighbors |
| Analysis Router | `api/routers/analysis_router.py` | FastAPI | ✅ Complete | anomalies, confidence, rootcause, whatif, benchmark, graphdiff |
| Frontend HTML | `frontend/index.html` | HTML5 | ✅ Complete | Single-page application (930 lines) |
| Frontend CSS | `frontend/css/styles.css` | Vanilla CSS | ✅ Complete | Dark space theme, glassmorphism (1083 lines) |
| Frontend JS — App | `frontend/js/app.js` | Vanilla JS | ✅ Complete | API calls, state management, view routing |
| Frontend JS — DAG | `frontend/js/dag-viz.js` | D3.js v7 | ✅ Complete | Interactive DAG visualization |
| Frontend JS — Timeline | `frontend/js/timeline.js` | Vanilla JS | ✅ Complete | Timeline replay slider |
| Frontend JS — Charts | `frontend/js/charts.js` | Chart.js v4 | ✅ Complete | Benchmark comparison charts |
| Frontend JS — Landing | `frontend/js/landing.js` | Vanilla JS | ✅ Complete | Star canvas, scroll animations |
| Docker Compose | `docker-compose.guru.yml` | Docker | ✅ Complete | Single `chronosmesh-api` service, port 8000 |
| Dockerfile | `api/Dockerfile` | Docker | ✅ Complete | API container |

---

## Existing Services

| Service | Location | Input | Output | Port |
|---|---|---|---|---|
| FastAPI API | `api/main.py` | HTTP REST requests | JSON responses | 8000 |
| Static Frontend | Served by FastAPI | Browser GET `/` or `/frontend/*` | HTML/CSS/JS | 8000 |

---

## Existing Databases

| Database | Location/Config | Purpose |
|---|---|---|
| In-Memory Store | `api/store.py` — Python singleton `ChronosMeshStore` | Events list, NetworkX DAG, arrival order, current scenario. Resets on restart. |
| **Neo4j** | Not present | Mentioned in README architecture diagram but **NOT implemented in any code** |
| **Kafka** | `pyproject.toml` dependency: `confluent-kafka>=2.3.0` | Listed as dependency; `consumer.py` is a stub; **no broker configured** |
| **PostgreSQL / TimescaleDB / InfluxDB** | Not present | Mentioned in project spec but **not implemented** |

---

## Existing APIs

| Endpoint | Method | Request | Response | Status |
|---|---|---|---|---|
| `/api/health` | GET | — | `{status, service, version}` | ✅ Working |
| `/api/metrics` | GET | — | `{event_count, dag_nodes, dag_edges, services_tracked, current_scenario, api_version}` | ✅ Working |
| `/auth/login` | POST | `form-data: username, password` | `{access_token, token_type}` | ✅ Working |
| `/api/scenarios/` | GET | Bearer token | List of scenario objects | ✅ Working |
| `/api/scenarios/{name}/load` | POST | Bearer token | `{scenario, dag, arrival_order, causal_order, event_count}` | ✅ Working |
| `/api/scenarios/` | DELETE | Bearer token | `{message}` | ✅ Working |
| `/api/events/` | GET | Bearer token | List of event dicts | ✅ Working |
| `/api/dag/` | GET | Bearer token | `{nodes[], edges[], topological_order[], roots[], leaves[]}` | ✅ Working |
| `/api/dag/roots` | GET | Bearer token | `{roots[]}` | ✅ Working |
| `/api/dag/leaves` | GET | Bearer token | `{leaves[]}` | ✅ Working |
| `/api/dag/timeline` | GET | Bearer token | `{timeline[], total_steps}` | ✅ Working |
| `/api/dag/ancestors/{event_id}` | GET | Bearer token + path param | `{event_id, ancestors[], count}` | ✅ Working |
| `/api/dag/descendants/{event_id}` | GET | Bearer token + path param | `{event_id, descendants[], count}` | ✅ Working |
| `/api/dag/neighbors/{event_id}` | GET | Bearer token + path param | `{event_id, immediate_parents[], immediate_children[]}` | ✅ Working |
| `/api/analysis/anomalies` | GET | Bearer token | `{anomalies[], total, severity_summary}` | ✅ Working |
| `/api/analysis/confidence` | GET | Bearer token | `{edge_scores[], low_confidence_edges[], average_confidence}` | ✅ Working |
| `/api/analysis/rootcause/{event_id}` | GET | Bearer token + path param | `{failure_event_id, root_causes[], trace_paths[], critical_path[], root_cause_count}` | ✅ Working |
| `/api/analysis/whatif/{event_id}` | POST | Bearer token + path param | `{removed_event_id, blast_radius_pct, cascade_depth, invalidated_events[], surviving_events[], affected_services[], invalidated_count}` | ✅ Working |
| `/api/analysis/benchmark` | GET | Bearer token + query params | `{parameters, results[], winner}` | ✅ Working (stub data) |
| `/api/analysis/graphdiff` | GET | Bearer token | `{diff, scenario}` | ✅ Working |
| `/api/docs` | GET | — | Swagger UI | ✅ Working |

---

## Existing Event Schemas

**Python Dataclass** (`chronosmesh/events/event.py`):
```
Event:
  event_id: str          (uuid4)
  service_id: str
  event_type: str
  timestamp_ms: float    (wall-clock ms when event occurred)
  lamport_ts: int
  vector_clock: Dict[str, int]
  hlc_ts: Optional[Dict[str, Any]]  → {"pt": float, "l": int}
  trace_id: str          (uuid4)
  span_id: str           (8-char prefix of uuid4)
  parent_event_ids: List[str]
  payload: Dict[str, Any]
  metadata: EventMetadata
  arrival_time_ms: float (wall-clock ms when ChronosMesh received event)

EventMetadata:
  region: str                    (default: "unknown")
  availability_zone: str         (default: "unknown")
  clock_uncertainty_ms: float    (default: 5.0)
  tags: Dict[str, str]
```

**Pydantic Schema** (`chronosmesh/events/schemas.py`): Mirror of above as `EventSchema` / `EventMetadataSchema`.

---

## Existing DAG Structures

The DAG is a **NetworkX `DiGraph`** where:

**Nodes** (keyed by `event_id: str`):
```
node attributes:
  event_id: str
  service_id: str
  event_type: str
  timestamp_ms: float
  lamport_ts: int
  vector_clock: Dict[str, int]
  parent_event_ids: List[str]
  metadata: Dict  → {region, availability_zone, clock_uncertainty_ms, tags}
```

**Edges** (directed, source → target means source happens-before target):
```
edge attributes:
  explicit: bool    (True if declared via parent_event_ids, False if inferred)
```

**API serialization** (`store.get_dag_json()`):
```json
{
  "nodes": [{"id", "service_id", "event_type", "timestamp_ms", "lamport_ts", "vector_clock", "region", "clock_uncertainty_ms", "parent_event_ids"}],
  "edges": [{"source", "target", "explicit"}],
  "topological_order": ["event_id", ...],
  "roots": ["event_id", ...],
  "leaves": ["event_id", ...]
}
```

---

## Existing Configuration

| Config Item | Location | Value |
|---|---|---|
| JWT Secret Key | `api/auth.py` line 15 | Hardcoded string `"chronosmesh-secret-key-guru-2024-xQ9mP2vL"` ⚠️ |
| JWT Algorithm | `api/auth.py` line 16 | `"HS256"` |
| Token expiry | `api/auth.py` line 17 | 1440 minutes (24 hours) |
| Demo users | `api/auth.py` lines 23-38 | `guru/chronosmesh` (admin), `demo/demo123` (viewer) ⚠️ |
| API port | `api/main.py` / `docker-compose.guru.yml` | 8000 |
| Python version | `pyproject.toml` | >=3.10 |
| Key dependencies | `pyproject.toml` | networkx>=3.1, confluent-kafka>=2.3.0, pydantic>=2.5.0, numpy>=1.24.0 |

---

## Existing Tests

| Test File | Count | Status |
|---|---|---|
| `tests/unit/test_anomaly.py` | 6 | ✅ All pass |
| `tests/unit/test_benchmarking.py` | 5 | ✅ All pass |
| `tests/unit/test_buffer.py` | 7 | ✅ All pass |
| `tests/unit/test_clock_factory.py` | 6 | ✅ All pass |
| `tests/unit/test_concurrency.py` | 5 | ✅ All pass |
| `tests/unit/test_confidence.py` | 8 | ✅ All pass |
| `tests/unit/test_consumer.py` | 6 | ✅ All pass |
| `tests/unit/test_dag_builder.py` | 10 | ✅ All pass |
| `tests/unit/test_graph_diff.py` | 8 | ✅ All pass |
| `tests/unit/test_happens_before.py` | 8 | ✅ All pass |
| `tests/unit/test_hlc.py` | 17 | ✅ All pass |
| `tests/unit/test_lamport.py` | 15 | ✅ All pass |
| `tests/unit/test_processor.py` | 7 | ✅ All pass |
| `tests/unit/test_root_cause.py` | 6 | ✅ All pass |
| `tests/unit/test_transitive_reduction.py` | 6 | ✅ All pass |
| `tests/unit/test_vector.py` | 16 | ✅ All pass |
| `tests/unit/test_what_if.py` | 7 | ✅ All pass |
| `tests/unit/test_windowing.py` | 7 | ✅ All pass |
| **TOTAL** | **150** | **✅ 150 passed, 0 failed** |

---

## Integration Risks

| Risk | Severity | Detail |
|---|---|---|
| Hardcoded JWT secret | HIGH | `SECRET_KEY` is a plaintext string in `api/auth.py`. Must move to `.env` before any production deploy. |
| Hardcoded demo passwords | HIGH | `chronosmesh` / `demo123` in `auth.py`. Must move to `.env`. |
| In-memory store resets on restart | MEDIUM | All events lost on server restart. Needs persistence (Neo4j/SQLite) for demo continuity. |
| Neo4j not implemented | MEDIUM | Project spec requires Neo4j; only mentioned in README — no connection code exists. |
| Kafka consumer is a stub | MEDIUM | `consumer.py` uses a mock interface; no real Kafka broker is connected. |
| CSS asset paths were broken | LOW | Fixed: `css/styles.css` → `/frontend/css/styles.css` in `index.html`. |
| `scenarios_router.py` bug line 103-106 | LOW | `causal_events` variable built incorrectly (list comprehension creates nested lists); unused variable. |
| `benchmarking.py` returns dummy data | LOW | Hardcoded accuracy ratios; not real benchmarking yet. |

---

## Missing Interfaces (Unresolved Integration Points)

| Missing Item | Required For | Owner |
|---|---|---|
| Neo4j connection + Cypher queries | Persistent DAG storage | Surya |
| Kafka broker + topic config | Real event ingestion | Surya |
| Mock microservices (Order/Payment/Inventory/Shipping/Notification) | Live event emission | Surya |
| Real clock drift injection across regions | Realistic demo | Surya |
| `.env` file for secrets | Security | Guru (Stage 2) |
| `api/schemas/` Pydantic response models | API contract | Guru (Stage 2) |
| `api/services/neo4j_service.py` | DB abstraction | Guru (Stage 2) |
| Integration test: Event → DAG → API response | Contract validation | Guru (Stage 2) |
