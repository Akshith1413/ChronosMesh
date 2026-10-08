"""
ChronosMesh API – main FastAPI application entry point.
Author: Guru Sai Prasad Reddy (Full-Stack: API, Frontend, Dashboards)
"""

import sys
import os
import logging
import time

# Ensure project root on sys.path so `chronosmesh` package resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse

from api.routers import auth_router, scenarios_router, events_router, dag_router, analysis_router, graphql_router
from api.metrics import get_prometheus_output, API_REQUESTS, API_REQUEST_DURATION, CONTENT_TYPE_LATEST
from api.logger import setup_structured_logging
from api.auth import get_current_user
from api.store import ChronosMeshStore, get_store

# ── Logging Setup ─────────────────────────────────────────────────────────────
setup_structured_logging(level=logging.INFO)
logger = logging.getLogger("chronosmesh.api")

# ── App Definition ────────────────────────────────────────────────────────────
app = FastAPI(
    title="ChronosMesh API",
    description="""
## ChronosMesh REST API

REST API layer for the ChronosMesh Distributed Causality Engine.

### Features
- 🕐 **Causal DAG reconstruction** from disordered event streams
- 🔍 **Anomaly detection** — time inversions, cycles, duplicate events
- 🔭 **Root-cause tracing** via backward DAG traversal
- 🎯 **What-if blast radius** simulation
- 📊 **Clock strategy benchmarking** — Lamport vs Vector vs HLC
- 🔐 **JWT authentication** with role-based access (VIEWER, ANALYST, ADMIN)
- 📈 **Prometheus Observability** at `/api/metrics`

### Demo Credentials
| User | Password | Role |
|------|----------|------|
| `guru` | `chronosmesh` | admin |
| `analyst` | `analyst123` | analyst |
| `demo` | `demo123` | viewer |

**Author:** Guru Sai Prasad Reddy  
**Project:** ChronosMesh — Cloud Computing PE-5
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Secure CORS Configuration ─────────────────────────────────────────────────
# Production whitelisting (avoids wildcard '*' when credentials are used)
_raw_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8000",
)
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── HTTP Security Headers Middleware ──────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ── Observability & Request Logging Middleware ─────────────────────────────────
@app.middleware("http")
async def log_and_record_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    path = request.url.path
    method = request.method
    status_code = str(response.status_code)

    # Record Prometheus metrics
    if not path.startswith("/frontend") and not path.endswith(".ico"):
        API_REQUESTS.labels(method=method, endpoint=path, status=status_code).inc()
        API_REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)
        logger.info(
            f"{method} {path} -> {status_code} [{duration * 1000:.1f}ms]",
            extra={"service": "fastapi", "status_code": status_code, "processing_time_ms": duration * 1000},
        )
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(scenarios_router.router, prefix="/api/scenarios", tags=["Scenarios"])
app.include_router(scenarios_router.traces_router, prefix="/api/traces", tags=["Traces"])
app.include_router(events_router.router, prefix="/api/events", tags=["Events"])
app.include_router(dag_router.router, prefix="/api/dag", tags=["Causal DAG"])
app.include_router(analysis_router.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(graphql_router.router, prefix="/api", tags=["GraphQL"])
app.include_router(graphql_router.router, prefix="", tags=["GraphQL"])


@app.get("/api/clocks/benchmark", tags=["Analysis"])
async def clocks_benchmark(
    num_events: int = 50,
    packet_loss_pct: float = 0.0,
    clock_drift_ms: float = 0.0,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Compare Lamport vs Vector vs HLC clock strategies."""
    if not store.events:
        from api.routers.scenarios_router import _build_scenario
        events, arrival_ids = _build_scenario("order_payment_flow")
        store.load_scenario("order_payment_flow", events, arrival_ids)

    from chronosmesh.analysis.benchmarking import ClockBenchmark
    bench = ClockBenchmark()
    results = bench.benchmark(
        store.dag, store.events,
        packet_loss_pct=packet_loss_pct / 100.0,
        clock_drift_ms=clock_drift_ms,
    )
    comparison = bench.compare_strategies(results)

    benchmarks_dict = {
        r.strategy_name.lower(): {
            "accuracy_pct": round(r.reconstruction_accuracy * 100, 1),
            "memory_kb": round(r.memory_bytes / 1024, 1),
            "computation_time_ms": r.computation_time_ms,
            "correct_orderings": r.correct_orderings,
            "total_orderings": r.total_orderings,
            "false_positives": r.false_positives,
            "false_negatives": r.false_negatives,
        }
        for r in results
    }

    return {
        "parameters": {
            "num_events": num_events,
            "packet_loss_pct": packet_loss_pct,
            "clock_drift_ms": clock_drift_ms,
            "event_count": len(store.events),
        },
        "benchmarks": benchmarks_dict,
        "results": [
            {
                "strategy": r.strategy_name,
                "accuracy_pct": round(r.reconstruction_accuracy * 100, 1),
                "memory_kb": round(r.memory_bytes / 1024, 1),
                "computation_time_ms": r.computation_time_ms,
            }
            for r in results
        ],
        "winner": max(comparison, key=comparison.get) if comparison else "vector",
    }


# ── System & Monitoring Endpoints ─────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
def health_check():
    """Health check endpoint for Docker & Kubernetes probes."""
    return {"status": "healthy", "service": "chronosmesh-api", "version": "1.0.0"}


@app.get("/metrics", tags=["System"], include_in_schema=False)
def prometheus_metrics(request: Request):
    """Prometheus metrics scraper endpoint returning standard Prometheus text exposition format."""
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/plain" not in accept:
        return get_metrics_json()
    return Response(content=get_prometheus_output(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/metrics", tags=["System"])
def api_metrics(request: Request):
    """
    ChronosMesh system and application metrics.
    Returns JSON dashboard metrics by default, or Prometheus text format if requested.
    """
    accept = request.headers.get("accept", "")
    if "text/plain" in accept or request.query_params.get("format") == "prometheus":
        return Response(content=get_prometheus_output(), media_type=CONTENT_TYPE_LATEST)
    return get_metrics_json()


@app.get("/api/metrics/json", tags=["System"], include_in_schema=False)
def get_metrics_json():
    """Structured runtime metrics for the dashboard monitoring panels."""
    from api.store import get_store
    store = get_store()
    return {
        "event_count": len(store.events),
        "dag_nodes": store.dag.number_of_nodes(),
        "dag_edges": store.dag.number_of_edges(),
        "services_tracked": len({e.service_id for e in store.events}),
        "current_scenario": store.current_scenario,
        "data_source": store.data_source,
        "neo4j_connected": store.neo4j.is_connected(),
        "api_version": "1.0.0",
    }


# ── Serve frontend static files ───────────────────────────────────────────────
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
_dist_dir = os.path.join(_frontend_dir, "dist")
_dist_assets = os.path.join(_dist_dir, "assets")

if os.path.isdir(_dist_assets):
    app.mount("/assets", StaticFiles(directory=_dist_assets), name="assets")

if os.path.isdir(_frontend_dir):
    app.mount("/frontend", StaticFiles(directory=_frontend_dir), name="frontend")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        if os.path.isfile(os.path.join(_dist_dir, "index.html")):
            return FileResponse(os.path.join(_dist_dir, "index.html"))
        return FileResponse(os.path.join(_frontend_dir, "index.html"))

    @app.get("/vanilla", include_in_schema=False)
    def serve_vanilla_frontend():
        vanilla_path = os.path.join(_frontend_dir, "vanilla.html")
        if os.path.isfile(vanilla_path):
            return FileResponse(vanilla_path)
        return FileResponse(os.path.join(_frontend_dir, "index.html"))

    @app.get("/api/docs", include_in_schema=False)
    def redirect_api_docs():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")

    @app.get("/api/redoc", include_in_schema=False)
    def redirect_api_redoc():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/redoc")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
