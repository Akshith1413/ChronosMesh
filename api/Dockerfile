# syntax=docker/dockerfile:1.7
# One Dockerfile, three targets:
#   --target api      FastAPI + the built React dashboard (default; pushed to the chronosmesh-api repo)
#   --target worker   SQS consumer / reconstruction worker  (pushed to the chronosmesh-engine repo)
#   --target grafana  Grafana with the ChronosMesh dashboards and data sources baked in
# Build from the repository root:  docker build -f api/Dockerfile --target api -t chronosmesh-api .

# ── Frontend build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Python base (dependencies only; cached until requirements change) ─────────
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 chronos
COPY requirements.runtime.txt ./
RUN pip install -r requirements.runtime.txt
COPY chronosmesh/ chronosmesh/
COPY api/ api/

# ── API ───────────────────────────────────────────────────────────────────────
FROM base AS api
COPY --from=frontend /build/dist frontend/dist
COPY frontend/index.html frontend/vanilla.html frontend/
COPY frontend/css frontend/css
COPY frontend/js frontend/js
USER chronos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# ── Worker ────────────────────────────────────────────────────────────────────
FROM base AS worker
USER chronos
ENV WORKER_METRICS_PORT=9100
EXPOSE 9100
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:9100/metrics >/dev/null || exit 1
CMD ["python", "-m", "chronosmesh.worker"]

# ── Grafana for AWS (stateless; CloudWatch data source + AWS dashboard provisioned from files) ──
FROM grafana/grafana:10.4.2 AS grafana
COPY observability/grafana/provisioning-aws /etc/grafana/provisioning
COPY observability/grafana/dashboards/chronosmesh-aws.json /var/lib/grafana/dashboards/chronosmesh-aws.json
ENV GF_AUTH_ANONYMOUS_ENABLED=false \
    GF_USERS_ALLOW_SIGN_UP=false \
    GF_ANALYTICS_REPORTING_ENABLED=false \
    GF_PATHS_PROVISIONING=/etc/grafana/provisioning
