# ChronosMesh Stage 3 — Production Frontend & Causal Visualization Architecture

> **Author:** B. Guru Sai Prasad Reddy  
> **Role:** Full-Stack/API, Dashboard, Visualization, Documentation, and Final Integration  
> **Status:** Stage 3 Complete · Production Ready  
> **Test Coverage:** 175 Backend Tests Passing + 4 Vitest Frontend Tests Passing  

---

## 1. Overview & Architecture

ChronosMesh Stage 3 transforms the Stage 1 Core Algorithm Engine and Stage 2 REST API/Interface foundation into an interactive, real-time web dashboard. It acts as the primary demonstration surface for understanding distributed-system causality, verifying that **raw arrival order does not equal causal order**, and providing debugging tools (anomaly detection, root-cause tracing, what-if blast radius, and clock benchmarking).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CHRONOSMESH WEB DASHBOARD                       │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│  │   Landing    │   │  Cluster         │   │  Causal DAG            │  │
│  │   Hero & Nav │──▶│  Overview & Feed │──▶│  Interactive D3 Engine │  │
│  └──────────────┘   └──────────────────┘   └────────────────────────┘  │
│         │                    │                          │              │
│         ▼                    ▼                          ▼              │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│  │  JWT Auth    │   │  Timeline Replay │   │  Root-Cause Tracing    │  │
│  │  Session     │   │  Arrival vs DAG  │   │  & What-If Blast Rad.  │  │
│  └──────────────┘   └──────────────────┘   └────────────────────────┘  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ (HTTP REST + Server-Sent Events)
┌────────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND SERVICE (PORT 8000)                │
│  /auth/*  ·  /api/scenarios/*  ·  /api/traces/*  ·  /api/events/*      │
│  /api/dag/*  ·  /api/analysis/*  ·  /api/events/stream (SSE)           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Tech Stack

- **Core Framework:** React 18 + TypeScript + Vite
- **Styling:** Custom CSS Design System (`styles.css`) with curated HSL color tokens, dark mode, glassmorphism, responsive CSS grid, and micro-animations.
- **Graph Visualization:** D3.js v7 with hierarchical service swimlanes, curved quadratic Bézier links, zoom/pan behaviors, and dynamic glow filters.
- **Metrics & Charting:** Chart.js v4 for empirical clock accuracy and memory comparisons.
- **Real-Time Feed:** Native Server-Sent Events (`EventSource`) with automated reconnection.
- **Testing:** Vitest for TypeScript unit testing + Pytest for full-stack API integration testing.

---

## 3. Directory & Component Hierarchy

```
frontend/
├── package.json                   # Dependencies: React 18, Vite 5, D3 7, Vitest
├── tsconfig.json                  # TypeScript bundler compiler options
├── vite.config.ts                 # Proxy configuration and build options
├── index.html                     # Production landing and dashboard shell
├── css/
│   └── styles.css                 # Unified CSS design system
├── js/                            # High-performance vanilla runtime bundle
│   ├── app.js                     # State management, routing, and API bindings
│   ├── dag-viz.js                 # D3.js hierarchical swimlane DAG engine
│   ├── timeline.js                # Side-by-side timeline scrub controller
│   ├── charts.js                  # Chart.js benchmark and confidence renderers
│   └── landing.js                 # Star canvas animations and landing logic
└── src/                           # Modular React Component Architecture
    ├── __tests__/
    │   └── dashboard.test.ts      # Vitest test suite
    ├── components/
    │   ├── Navbar.tsx             # Real-time SSE indicator, user status, scenario badge
    │   ├── Sidebar.tsx            # View switcher, active trace dropdown, user card
    │   ├── MetricCard.tsx         # Statistic counter cards with icon gradients
    │   ├── LoadingState.tsx       # Loading spinner, Error boundary, and Empty states
    │   ├── EventDetails.tsx       # Vector clock bars, Lamport pills, timestamps, parents
    │   ├── CausalGraph.tsx        # React-wrapped D3 causal graph visualizer
    │   ├── ArrivalTimeline.tsx    # Raw out-of-order Kafka event track
    │   ├── CausalTimeline.tsx     # Reconstructed topological causal event track
    │   ├── Timeline.tsx           # Side-by-side scrub slider & animated playback
    │   ├── AnomalyPanel.tsx       # Anomaly list with severity chips & event jump
    │   ├── RootCausePanel.tsx     # Backward reachability & critical path visualizer
    │   ├── WhatIfPanel.tsx        # Counterfactual simulation & blast radius gauge
    │   └── BenchmarkPanel.tsx     # Lamport vs Vector vs Physical comparison cards
    ├── hooks/
    │   ├── useAuth.ts             # JWT token persistence and login/logout handlers
    │   └── useSSE.ts              # Live SSE event stream hook with auto-reconnect
    ├── pages/
    │   ├── Home.tsx               # Professional landing page with architecture preview
    │   ├── Dashboard.tsx          # Metrics, trace cards, and live feed
    │   ├── Trace.tsx              # Interactive DAG view with EventDetails sidebar
    │   ├── Anomalies.tsx          # Anomaly center & root-cause traversal
    │   ├── WhatIf.tsx             # Blast radius lab & graph overlay
    │   └── Benchmark.tsx          # Clock comparison benchmarks
    ├── services/
    │   └── api.ts                 # Typed API client matching Stage 2 contracts
    ├── types/
    │   └── index.ts               # Strict TypeScript interfaces
    ├── utils/
    │   └── colors.ts              # Service color maps and severity tokens
    ├── App.tsx                    # Root dashboard application controller
    └── main.tsx                   # React DOM root mounting
```

---

## 4. Key Demonstration Features

### A. Raw Arrival Order vs Reconstructed Causal Order
- Visualizes the central premise of ChronosMesh: microservice events arriving disordered due to network jitter and asynchronous queuing.
- Side-by-side layout:
  - **Left (Red/Jitter):** Raw Kafka arrival sequence with injected delays.
  - **Right (Emerald/DAG):** Topologically sorted causal sequence computed by Akshith's `CausalDAGBuilder` and `compute_transitive_reduction`.
- Interactive step-scrubber and play/pause button progress through events deterministically.

### B. Interactive D3.js Causal Graph
- **Service Swimlanes:** Grouped into microservice columns (`order-svc`, `payment-svc`, `inventory-svc`, `shipping-svc`).
- **Curved Bézier Links:** Distinguishes explicit communication links from inferred transitive relationships.
- **Node Inspection:** Displays Lamport timestamp, physical timestamp, clock uncertainty, and vector clock bar charts.
- **Zoom & Navigation:** Smooth zoom in/out, pan, and auto-centering.

### C. Anomaly Center
- Directly consumes `GET /api/analysis/anomalies` and `GET /api/traces/{trace_id}/anomalies`.
- Detects and categorizes:
  - `TIME_INVERSION` (Physical clock backward skew)
  - `CYCLE` (Deadlocks or impossible causality)
  - `DUPLICATE_EVENT` (At-least-once redelivery anomalies)
  - `CLOCK_DRIFT` (Multi-region skew exceeding tolerance)
- Clicking an anomaly centers the graph directly on the offending event.

### D. Root-Cause Tracing
- Directly consumes `GET /api/analysis/rootcause/{event_id}`.
- Performs backward reachability analysis on the DAG to isolate root causes.
- Traces the critical causal path (`E1 → E2 → ... → E_failure`) and highlights it in amber on the graph.

### E. What-If Blast Radius Simulation
- Directly consumes `POST /api/analysis/whatif/{event_id}`.
- Evaluates: "If this event had failed or not occurred, what downstream events break?"
- Calculates blast radius percentage, cascade depth, and lists invalidated vs surviving events.
- Overlays the invalidated blast radius directly on the DAG in red.

### F. Clock Strategy Benchmarking
- Directly consumes `GET /api/analysis/benchmark`.
- Evaluates `vector_clock`, `lamport_clock`, and `physical_time` across accuracy, memory footprint, and computation latency.
- Allows user to inject simulated network packet loss (0% to 30%) and clock drift (0 to 200 ms).

### G. Live Server-Sent Events (SSE)
- Directly consumes `GET /api/events/stream`.
- Real-time event consumption with automatic reconnection and heartbeat indicators.

---

## 5. Running and Testing Locally

### Start API and Dashboard
```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- Open [http://localhost:8000/](http://localhost:8000/) for the interactive dashboard.
- Open [http://localhost:8000/api/docs](http://localhost:8000/api/docs) for the Swagger API explorer.

### Run Tests
```powershell
# Run backend pytest suite (175 tests)
python -m pytest tests/

# Run frontend Vitest suite (4 tests)
cd frontend
npm test
```
