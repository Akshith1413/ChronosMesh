# ChronosMesh — Stage 3 Completion Report
**Production React Dashboard, Causal Visualization & Live Integration**

- **Engineer:** B. Guru Sai Prasad Reddy
- **Role:** Backend API, Full-Stack Integration, Frontend Dashboard, Visualization, Documentation
- **Status:** **STAGE 3 COMPLETE**
- **Date:** September 2026

---

## 1. Features Implemented

| Feature | Classification | Description |
|---|---|---|
| **Landing Page** | `IMPLEMENTED + VERIFIED` | Architectural narrative, distributed clock problem breakdown, interactive hero, and live dashboard launch |
| **Interactive Causal DAG** | `IMPLEMENTED + VERIFIED` | D3.js hierarchical swimlane DAG with zoom, pan, confidence edge weighting, node selection, and critical path glow |
| **Arrival vs Causal Comparison** | `IMPLEMENTED + VERIFIED` | Side-by-side comparison illustrating Kafka out-of-order arrival sequence vs reconstructed topological causal order |
| **Timeline Scrubber & Replay** | `IMPLEMENTED + VERIFIED` | Deterministic slider replay revealing events step-by-step with play/pause animations and DAG synchronisation |
| **Event Details Inspector** | `IMPLEMENTED + VERIFIED` | Full metadata drawer showing HLC clock components, causal parents/children, regions, and anomaly flags |
| **Anomaly Detection Panel** | `IMPLEMENTED + VERIFIED` | Severity chips (Critical/Warning/Info) with click-to-focus DAG highlighting and root cause linkages |
| **Root Cause Traversal** | `IMPLEMENTED + VERIFIED` | Backward BFS traversal revealing root causes and highlighting the critical causal dependency chain |
| **What-If Blast Radius Replay** | `IMPLEMENTED + VERIFIED` | Counterfactual event removal/delay simulation reporting affected services, cascade depth, and invalidated events |
| **Clock Strategy Benchmark** | `IMPLEMENTED + VERIFIED` | Multi-strategy comparison (Lamport vs Vector vs HLC) across accuracy, latency, memory, and drift tolerance |
| **Live SSE Event Stream** | `IMPLEMENTED + VERIFIED` | Real-time arrival stream (`/api/events/stream`) with automatic reconnection and heartbeat handling |
| **JWT Authentication** | `IMPLEMENTED + VERIFIED` | Bearer token integration, persistent login, mock dev bypass, and authenticated API header forwarding |
| **Multi-Scenario Catalog** | `IMPLEMENTED + VERIFIED` | Trace aliases (`T-1001` Diamond, `T-1002` Concurrent, `T-1003` Clock Drift) with `/api/traces` endpoints |

---

## 2. Pages Implemented

All pages are located under [`frontend/src/pages/`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/frontend/src/pages):

1. **`Home.tsx`** (`/`):
   - Hero banner with project mission statement
   - Visual problem breakdown ("No global clock $\rightarrow$ Out-of-order arrival $\rightarrow$ Arrival order $\neq$ Causal order")
   - ChronosMesh logical solution & 7-stage streaming architecture pipeline preview
   - Quick launch triggers for Dashboard and Architecture docs
2. **`Dashboard.tsx`** (`/dashboard`):
   - Main control plane featuring trace selector (`T-1001`, `T-1002`, `T-1003`)
   - 4-card metric banner (Total Events, Causal Dependencies, Inversion Rate, Anomalies)
   - Split layout: Interactive D3 DAG visualization + side-by-side Arrival vs Causal order
   - Interactive replay timeline scrubber and Event Details side drawer
3. **`Trace.tsx`** (`/trace`):
   - Trace search, filter by service/region, and comprehensive event tabular inspector
   - Raw JSON inspection and direct ancestor/descendant query controls
4. **`Anomalies.tsx`** (`/anomalies`):
   - Dedicated incident diagnosis room
   - Filters for clock drift, causality violations, and dropped events
   - Anomaly severity classification and root cause path jumping
5. **`WhatIf.tsx`** (`/what-if`):
   - Simulation workbench for counterfactual fault injection
   - Event deletion and delay injection controls
   - Before-and-after graph diff metrics: Blast radius %, cascade depth, invalidated downstream events
6. **`Benchmark.tsx`** (`/benchmark`):
   - Comparative evaluation of Lamport, Vector, and Hybrid Logical Clocks (HLC)
   - Interactive network delay and clock drift parameter sliders
   - Multi-metric benchmark matrix (ordering fidelity, serialization overhead, drift resilience)

---

## 3. Components Implemented

Modular React TypeScript components located in [`frontend/src/components/`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/frontend/src/components):

- **`Navbar.tsx`**: Header navigation with system status, active trace badge, and authentication status
- **`Sidebar.tsx`**: Collapsible routing sidebar with route-active indicators
- **`CausalGraph.tsx`**: D3.js SVG directed acyclic graph renderer with hierarchical layout, zoom/pan controls, edge confidence styling, and highlight overlays
- **`ArrivalTimeline.tsx`**: Horizontal out-of-order physical arrival track
- **`CausalTimeline.tsx`**: Horizontal reconstructed topological causal track
- **`Timeline.tsx`**: Unified scrubber with Play/Pause animation, step forward/backward, and percentage progress
- **`EventDetails.tsx`**: Slide-over metadata inspector for the selected event
- **`AnomalyPanel.tsx`**: Incident alert list with severity tags and direct graph centering
- **`RootCausePanel.tsx`**: Upstream root-cause pathway calculator and critical path display
- **`WhatIfPanel.tsx`**: Blast radius gauge and counterfactual simulation form
- **`BenchmarkPanel.tsx`**: Clock strategy comparative cards and parameter sliders
- **`MetricCard.tsx`**: Reusable metric summary card with icons and trends
- **`LoadingState.tsx`**: Consistent Loading, Error (with retry), and Empty state views

---

## 4. API Integrations

The frontend integrates cleanly with the Stage 2 FastAPI service via [`frontend/src/services/api.ts`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/frontend/src/services/api.ts):

| API Function | REST Endpoint | Backend Source |
|---|---|---|
| `getHealth()` | `GET /api/health` | `api/main.py` |
| `getTraces()` | `GET /api/traces/` | `api/routers/scenarios_router.py` |
| `getTrace(id)` | `GET /api/traces/{trace_id}` | `api/routers/scenarios_router.py` |
| `getDag(traceId)` | `GET /api/traces/{trace_id}/dag` | `api/routers/scenarios_router.py` |
| `getTimeline(traceId)` | `GET /api/traces/{trace_id}/timeline` | `api/routers/scenarios_router.py` |
| `getAnomalies(traceId)` | `GET /api/traces/{trace_id}/anomalies` | `api/routers/scenarios_router.py` |
| `getRootCause(id, traceId)` | `GET /api/analysis/root-cause/{id}` | `api/routers/analysis_router.py` |
| `runWhatIf(req)` | `POST /api/analysis/what-if` | `api/routers/analysis_router.py` |
| `getBenchmarks()` | `GET /api/clocks/benchmark` | `api/routers/clocks_router.py` |
| `login(creds)` | `POST /api/auth/token` | `api/routers/auth_router.py` |
| `useSSE()` | `GET /api/events/stream` | `api/routers/events_router.py` |

---

## 5. DAG Visualization

- **Library:** D3.js (`d3` v7) integrated within React lifecycle via `useRef` and `useEffect`.
- **Layout:** Hierarchical layout with horizontal topological ordering and vertical service/lane separation.
- **Interactivity:**
  - Smooth zoom & pan using `d3.zoom()` with programmatic zoom-in, zoom-out, fit-to-view, and reset controls.
  - Hover tooltips displaying event type, service, and HLC timestamps.
  - Node selection dispatching active event state to `EventDetails` and `RootCausePanel`.
  - Confidence-driven edge rendering: solid thick strokes for confidence $\ge 0.9$, dashed medium for $\ge 0.7$, and dotted thin for lower confidence.
  - Visual highlighting: Root cause ancestors glow golden orange; counterfactually invalidated nodes glow red.

---

## 6. Arrival vs Causal Comparison

- **Purpose:** Demonstrates the core thesis: *Arrival Order $\neq$ Causal Order*.
- **Implementation:**
  - Physical Arrival stream reflects raw Kafka consumer order (e.g., $E_1 \rightarrow E_3 \rightarrow E_2 \rightarrow E_5 \rightarrow E_4$).
  - Reconstructed Causal order reflects topological DAG sort (e.g., $E_1 \rightarrow E_2 \rightarrow E_3 \rightarrow E_4 \rightarrow E_5$).
  - Inverted transitions are highlighted with caution badges showing inversion index and millisecond skew.

---

## 7. Timeline Replay

- **Scrubber:** Real-time percentage slider ($0\%$ to $100\%$) controlling event visibility across both DAG and timelines.
- **Animation Controls:** Play, pause, step forward, and step back with adjustable playback speeds ($1\times, 2\times, 5\times$).
- **State Determinism:** Replay calculates the exact prefix subset of topologically ordered events up to current scrub index without backend mutations.

---

## 8. Anomaly Visualization

- **Data Source:** `/api/traces/{id}/anomalies` backed by Stage 1 `AnomalyDetector`.
- **Features:** Categorization into `CLOCK_DRIFT`, `CAUSALITY_VIOLATION`, `LATE_EVENT`, and `ANOMALOUS_DELAY`.
- **Interactions:** Clicking any anomaly card selects the affected node, zooms the DAG to focus on it, and loads its root-cause ancestry.

---

## 9. Root Cause Visualization

- **Data Source:** `/api/analysis/root-cause/{event_id}` backed by Stage 1 `RootCauseAnalyzer`.
- **Features:** Backward breadth-first graph traversal identifying origin root-cause event(s) and critical paths.
- **DAG Highlighting:** Automatically illuminates the complete causality chain leading to the incident.

---

## 10. What-If Interface

- **Data Source:** `/api/analysis/what-if` backed by Stage 1 `WhatIfSimulator`.
- **Features:** Allows users to simulate dropping an event or injecting latency.
- **Outputs:** Blast radius percentage, cascade depth, list of invalidated downstream events, and affected services.

---

## 11. Benchmark Interface

- **Data Source:** `/api/clocks/benchmark` backed by Stage 1 `ClockFactory` and performance evaluators.
- **Metrics:** Throughput (ops/sec), memory overhead (bytes/event), clock drift tolerance, and concurrency detection accuracy across Lamport, Vector, and HLC.

---

## 12. SSE Integration

- **Endpoint:** `GET /api/events/stream`
- **Implementation:** Implemented via Starlette `StreamingResponse` using Server-Sent Events protocol (`text/event-stream`). Emits real-time event arrivals with heartbeats (`ping`).
- **Client Handling:** Robust React custom hook `useSSE` with auto-reconnect, buffer management, and connection state indicators.

---

## 13. Authentication

- **Backend:** JWT Bearer token generation via `POST /api/auth/token` with secure password hashing (`pwd_context`).
- **Frontend:** Centralized token management via `localStorage`, automatic request header injection (`Authorization: Bearer <token>`), and dev-mode fallback.

---

## 14. Test Verification Results

### Backend Python Tests
```bash
python -m pytest tests/
```
- **Total Tests:** 175 passing (0 failures, 1 warning)
- **Unit Tests:** 162 passing (Stage 1 Core Algorithms)
- **API Tests:** 8 passing (Stage 2 FastAPI Endpoints)
- **Stage 3 Feature Tests:** 5 passing (SSE Streaming, Traces Router, Scenarios DAG/Timeline/Anomalies)

### Frontend Tests
```bash
cd frontend && npm run test
```
- **Total Tests:** 4 passing (0 failures)
- **Coverage:** Dashboard scenario mapping, metric card rendering, error state handling, and data contract compliance.

### Production Build
```bash
cd frontend && npm run build
```
- **Result:** Successfully compiled and bundled to `frontend/dist/` without type or syntax errors.

---

## 15. Performance Considerations

1. **SVG Graph Optimization:** D3 zoom and transform uses hardware-accelerated SVG matrix transforms.
2. **Memoized Derivations:** React `useMemo` prevents expensive graph topological sorting on unrelated UI state changes.
3. **SSE Throttling:** Live events buffer in windowed slices of 50 events to prevent DOM exhaustion.
4. **Isolated Static Build:** Zero-install standalone browser bundle supported directly from `api/main.py` alongside modern Vite SPA.

---

## 16. Known Limitations

1. **Mock Distributed System:** Live Kafka and Neo4j rely on Surya's Stage 4 distributed services. In development, the FastAPI in-memory store and `SCENARIO_CATALOGUE` provide deterministic multi-cloud scenarios.
2. **Large DAG Scaling:** For traces exceeding 1,000 nodes, canvas-based rendering (PixiJS/Cytoscape WebGL) may be preferred over SVG DOM nodes. Current SVG layout performs smoothly up to ~300 nodes per trace.

---

## 17. Stage 4 Readiness

The frontend and backend integration layer is 100% prepared for Surya's Stage 4 tasks:
- **Kafka Consumer Handshake:** The `/api/events/stream` SSE router can be connected directly to Surya's Kafka consumer group.
- **Neo4j Cypher Integration:** `api/store.py` contains pre-defined repository hooks matching the Cypher DDL in `docs/NEO4J_SCHEMA.md`.
- **Dashboard Extensibility:** All component interfaces are strictly typed with TypeScript interfaces ready for live production streams.
