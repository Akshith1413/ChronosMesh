# ChronosMesh — Stage 5 Baseline Verification
**Pre-Hardening Benchmark & Test Inventory**

- **Engineer:** B. Guru Sai Prasad Reddy
- **Role:** Full-Stack Integration, API, Dashboard, Visualization, Documentation, End-to-End Integration
- **Recorded Date:** September 2026

---

## 1. Test Verification Baseline

| Test Suite | Framework | Target / Focus | Passed | Failed | Warnings | Execution Time |
|---|---|---|---|---|---|---|
| **Core Algorithm & Clocks** | `pytest` | Stage 1 (Lamport, Vector, HLC, DAG, Buffer, Anomaly, What-if) | 162 | 0 | 0 | ~8.5s |
| **API Endpoints & Auth** | `pytest` | Stage 2 (FastAPI routers, JWT auth, schema compliance) | 8 | 0 | 1 | ~1.2s |
| **Stage 3 Features** | `pytest` | Stage 3 (Scenarios, DAG/Timeline endpoints, static serving) | 5 | 0 | 0 | ~1.1s |
| **Stage 4 Distributed E2E**| `pytest` | Stage 4 (Mock cluster, Kafka producer, Flink pipeline, Neo4j, SSE) | 7 | 0 | 0 | ~16.5s |
| **Total Backend Tests** | `pytest` | Entire repository | **182** | **0** | **1** | **37.98s** |
| **Frontend Component Tests**| `vitest` | Dashboard utilities, scenario mapping, auth contracts | **4** | **0** | **0** | **3.91s** |
| **Frontend Production Build**| `vite` | HTML/JS/CSS bundle generation (`dist/index.html`) | **Success** | **0** | **0** | **303ms** |

---

## 2. Current Performance Profile

- **Throughput (Incremental Transitive Reduction):** ~72 events/sec (constrained by per-event $O(N^3)$ full-graph reduction).
- **Throughput (Windowed/Batch Processing):** >2,500 events/sec.
- **REST API Latency:** 2–8 ms per request (in-memory mode).
- **SSE Stream Heartbeat:** Configured at 2.0-second intervals.
- **D3 Graph Rendering:** Smooth for traces up to ~300 nodes; SVG DOM degradation beyond 1,000 nodes.

---

## 3. Current Docker Status

- Unified [`docker-compose.yml`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/docker-compose.yml) defined with 6 services:
  1. `zookeeper` (port 2181)
  2. `kafka` (ports 9092, 29092)
  3. `neo4j` (ports 7474, 7687)
  4. `flink-jobmanager` (port 8081)
  5. `flink-taskmanager`
  6. `chronosmesh-api` (port 8000)

---

## 4. Known Warnings & Target Improvement Areas

1. **PendingDeprecationWarning:** `starlette.formparsers` deprecation regarding `python_multipart`.
2. **Observability:** No real-time Prometheus `/api/metrics` endpoint or Grafana dashboard configuration existed in Stage 4.
3. **Role-Based Access Control (RBAC):** All authenticated users currently have uniform permissions; RBAC (`VIEWER`, `ANALYST`, `ADMIN`) needed.
4. **Security Headers:** Missing explicit HTTP security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP).
5. **CORS:** Currently configured with broad development allowance; needs strict environment-driven whitelist.
6. **Causal Engine Optimization:** Address the per-event $O(N^3)$ transitive reduction bottleneck.
7. **CI/CD:** No automated GitHub Actions workflows existed.
