# ChronosMesh — Developer Setup & Quickstart Guide

This guide provides tested, reproducible instructions for getting ChronosMesh running on a local development machine.

---

## 1. Prerequisites

Ensure you have the following installed:
- **Python:** 3.11 or 3.12 (`python --version`)
- **Node.js:** v18+ or v20+ or v24+ (`node --version`)
- **npm:** v9+ or v10+ (`npm --version`)
- **Docker & Docker Compose:** Optional for local mock mode; required for full distributed container stack.

---

## 2. Canonical Step-by-Step Setup

### Step 1: Clone & Configure Environment
```bash
git clone https://github.com/Akshith1413/ChronosMesh.git
cd ChronosMesh

# Copy environment configuration
cp .env.example .env
```

Review `.env` and verify defaults:
- `JWT_SECRET_KEY`: Default dev secret provided; change for production.
- `NEO4J_PASSWORD`: Set to `chronosmesh2026`.
- `DATA_SOURCE`: Set to `demo` (for standalone local development) or `live` (with Docker containers).

---

### Step 2: Backend Python Setup
```bash
# Create and activate virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Install core and API dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
pip install prometheus_client
```

---

### Step 3: Frontend React Setup & Production Build
```bash
cd frontend
npm install
npm run build
cd ..
```

---

### Step 4: Run Verification Tests
```bash
# 1. Run Python test suite (from repository root)
python -m pytest tests/ -v
# Result: 204 passed, 1 warning (100% green)

# 2. Run Frontend Vitest tests
cd frontend
npm run test
# Result: 4 passed (100% green)
cd ..
```

---

### Step 5: Start Services (Canonical Startup Path)

#### Primary Production Mode (Recommended)
FastAPI serves both the backend REST/GraphQL API and the compiled React 18 + Vite production bundle directly:

```bash
# Start FastAPI (serves API on port 8000 and React UI at http://localhost:8000)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# Or on Windows:
.\start_guru.bat
```

#### Optional: Frontend Hot-Reload Development Server
If modifying React source code with instant HMR:
```bash
cd frontend
npm run dev
# Vite runs at http://localhost:3000 (proxies /api and /auth to port 8000)
```

---

## 3. Interacting with ChronosMesh

| Service | URL | Credentials / Notes |
| :--- | :--- | :--- |
| **React Dashboard (Production)** | `http://localhost:8000` | Login: `guru` / `chronosmesh` (Admin) |
| **React Dashboard (Dev Vite)** | `http://localhost:3000` | Login: `guru` / `chronosmesh` (Admin) |
| **FastAPI Swagger Docs** | `http://localhost:8000/api/docs` | Interactive OpenAPI documentation |
| **GraphQL Query Endpoint** | `http://localhost:8000/graphql` | Causal ancestors, descendants, concurrency |
| **Prometheus Telemetry**| `http://localhost:8000/metrics` | System metrics & alert status |

### User Accounts & RBAC Matrix
| Username | Password | Role | Permissions |
|---|---|---|---|
| `guru` | `chronosmesh` | `admin` | Full control, load scenarios, reset state |
| `analyst` | `analyst123` | `operator` | Load scenarios, what-if replay, benchmarks |
| `demo` | `demo123` | `viewer` | Read-only inspection of DAGs & timelines |

---

## 4. Demonstrating Causal Reconstruction (`TRACE-DEMO-001`)

1. Open the React Dashboard at `http://localhost:8000` (or `http://localhost:3000`).
2. Login with `guru` / `chronosmesh`.
3. Under **Scenarios**, select **Deterministic E-Commerce Order Flow (`TRACE-DEMO-001`)**.
4. Observe:
   - **Arrival Order:** Events arrive out of causal sequence (`E1 -> E3 -> E2 -> E5 -> E4 -> E6`).
   - **Causal DAG:** Reconstructs the true happens-before path (`E1 -> E2 -> E3 -> E4 -> E5 -> E6`).
   - **Concurrency:** `payment-svc` and `inventory-svc` execute concurrently.
   - **Anomalies Panel:** Inspect cross-region clock drift and TrueTime confidence scores.
   - **What-If Simulation:** Invalidate an event to view downstream cascade blast radius and graph diffs.
