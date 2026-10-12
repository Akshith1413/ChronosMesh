# ChronosMesh — Security Architecture & Access Control Model

## 1. Overview
ChronosMesh implements defense-in-depth security across authentication, authorization, HTTP transport, and data isolation. This document formalizes the production security model implemented and verified during Stages 5 and 6.

---

## 2. Authentication & JWT Tokens
- **Mechanism:** JSON Web Token (JWT) using the HMAC-SHA256 (`HS256`) algorithm.
- **Token Claims:** `sub` (subject identifier / username), `role` (assigned RBAC role), `exp` (expiration timestamp, default: 60 minutes).
- **Enforcement:** Protected REST endpoints and SSE streams require an `Authorization: Bearer <token>` header or query parameter (`?token=<token>`).
- **Signature & Expiration Validation:** Handled by PyJWT in [`api/auth.py`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/api/auth.py). Invalid or expired tokens immediately return HTTP 401 Unauthorized.

---

## 3. Role-Based Access Control (RBAC) Matrix

ChronosMesh implements a 3-tier Role-Based Access Control model enforced by the `require_role(min_role)` dependency:

| Operation / Endpoint Group | Minimum Role | Viewer (`demo`) | Analyst (`analyst`) | Admin (`guru`) |
| :--- | :---: | :---: | :---: | :---: |
| **View Traces & Metadata** (`GET /api/traces/`) | `ROLE_VIEWER` | Allowed | Allowed | Allowed |
| **Inspect Reconstructed DAG** (`GET /api/traces/{id}/dag`)| `ROLE_VIEWER` | Allowed | Allowed | Allowed |
| **View Timelines & Events** (`GET /api/traces/{id}/timeline`)| `ROLE_VIEWER` | Allowed | Allowed | Allowed |
| **View Causal Anomalies** (`GET /api/traces/{id}/anomalies`)| `ROLE_VIEWER` | Allowed | Allowed | Allowed |
| **Subscribe to Live SSE Stream** (`GET /api/events/stream`)| `ROLE_VIEWER` | Allowed | Allowed | Allowed |
| **Root-Cause Analysis** (`GET /api/analysis/root-cause/{id}`)| `ROLE_ANALYST` | Denied (403) | Allowed | Allowed |
| **What-If Fault Simulation** (`POST /api/analysis/what-if`)| `ROLE_ANALYST` | Denied (403) | Allowed | Allowed |
| **Clock Benchmarking** (`GET /api/clocks/benchmark`) | `ROLE_ANALYST` | Denied (403) | Allowed | Allowed |
| **Trigger Scenario / Ingest** (`POST /api/scenarios/{id}/load`)| `ROLE_ADMIN` | Denied (403) | Denied (403) | Allowed |
| **Clear Graph Store** (`DELETE /api/scenarios/`) | `ROLE_ADMIN` | Denied (403) | Denied (403) | Allowed |

*Verified in [`tests/integration/test_stage6_validation.py::test_rbac_authorization_matrix`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/tests/integration/test_stage6_validation.py).*

---

## 4. Network & Transport Security

### 4.1 CORS Policy
Wildcard origins (`*`) are prohibited when credentials/cookies are active. Configured origins are governed by the `CORS_ALLOWED_ORIGINS` environment variable:
- `http://localhost:5173` (Vite development dashboard)
- `http://localhost:8000` (FastAPI local Swagger UI)
- `http://127.0.0.1:5173`
- `http://127.0.0.1:8000`

### 4.2 HTTP Security Headers
Every HTTP response carries the following hardened headers injected via ASGI middleware:
- `X-Content-Type-Options: nosniff`: Prevents MIME-type confusion attacks.
- `X-Frame-Options: DENY`: Prevents UI redressing and clickjacking.
- `Referrer-Policy: strict-origin-when-cross-origin`: Controls referrer leakage.
- `X-XSS-Protection: 1; mode=block`: Activates browser XSS protection.

---

## 5. Secrets Management & Credential Sanitization
- **Repository Protection:** `.gitignore` excludes `.env`, `*.key`, `*.pem`, `*.dump`, and temporary secrets.
- **Audit Verification:** No hardcoded credentials exist in source code. `.env.example` provides explicit template variables.
- **Log Sanitization:** Structured JSON logger ([`api/logger.py`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/api/logger.py)) intercepts all log fields and masks sensitive keys matching `password`, `token`, `secret`, `jwt`, `api_key`, and `credential`.

---

## 6. Input Validation & Error Handling
- All incoming payloads are validated using Pydantic schemas ([`chronosmesh/events/schemas.py`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/chronosmesh/events/schemas.py)).
- Invalid inputs, negative timestamps, or malformed JSON return HTTP 422 Unprocessable Entity or 400 Bad Request.
- Production error handlers catch internal exceptions and return structured JSON error envelopes without dumping Python tracebacks to client callers.


---

# Hardening applied 2026-10-12

| Area | Before | Now |
|---|---|---|
| **JWT secret** | Hard-coded fallback string, also committed in `.env.example` and a k8s ConfigMap | Must come from `JWT_SECRET_KEY` or Secrets Manager (`JWT_SECRET_ARN`). With `ENVIRONMENT=production` the process **refuses to start** on a missing, short (<32) or known-leaked secret. The previously committed values are on a deny-list. |
| **Users** | Demo accounts (`guru/chronosmesh`, …) always enabled | Demo accounts default **off in production**. Real users via `AUTH_USERS` + `AUTH_PASSWORD_<NAME>` (what ECS secret injection produces), `USERS_JSON` or `USERS_SECRET_ARN`; bcrypt-hashed in memory. The UI hides one-click demo login (`GET /auth/config`) and no longer auto-signs in as admin. |
| **CORS** | `allow_origin_regex=".*"` with credentials (reflects any origin) | Explicit allow-list (`CORS_ORIGINS`); `*` is refused; no localhost origins in production; headers limited to `Authorization`/`Content-Type`. The deployed dashboard is same-origin (CloudFront routes API paths), so it needs no CORS. |
| **GraphQL** | Last commit removed authentication and broke every POST (422) | Authenticated again; resolvers return real data. |
| **SSE** `/api/events/stream` | Token accepted but never verified | Token (header or `?token=`) is verified; 401 otherwise. |
| **JSON metrics** | Public | Require authentication. Prometheus text can require `METRICS_TOKEN`. |
| **Tenant isolation** | One global in-memory store | Executions/experiments are owner-scoped (404 for others; admin sees all). "Open in Trace Explorer" loads into a **private per-user store**. |
| **Secrets in Git** | Default Neo4j password and JWT signing strings in `k8s/`, `.env.example`, `neo4j_store.py` | Removed; k8s uses a `Secret` (template only) and the Neo4j client never guesses a default password. A test fails if a known leaked value reappears. The old values must be treated as compromised and were rotated. |
| **Containers** | root user, whole repo (incl. `venv/`) copied | Multi-stage image, non-root UID 10001, read-only root filesystem on ECS, `.dockerignore`, health checks, image scanning (ECR scan-on-push + Trivy in CI). |
| **Network (AWS)** | Instances with all-traffic-from-anywhere security group, SSH/Prometheus/Grafana open to the world | New stack: ALB reachable **only from CloudFront's origin-facing prefix list** and only with a secret `X-Origin-Verify` header; tasks reachable only from the ALB; S3 buckets private (OAC) with TLS-only policies. |
| **IAM (AWS)** | Task role with `AmazonSQS/DynamoDB/S3FullAccess` | One role per workload, scoped to named tables/indexes, `executions/*` objects and the single queue; `PutMetricData` limited to the `ChronosMesh` namespace. |

### RBAC for the v2 endpoints

| Operation | Viewer | Analyst | Admin |
|---|:--:|:--:|:--:|
| Read my experiments/executions, graphs, anomalies, status | ✔ | ✔ | ✔ (all users') |
| Create/start experiments, create executions, ingest events, explore | ✘ 403 | ✔ | ✔ |

### Known limitations
* Between CloudFront and the ALB traffic is HTTP (there is no custom domain/ACM certificate); viewers always use HTTPS. Mitigated by the prefix-list + secret-header restriction.
* CloudFront's default certificate negotiates TLS ≥ 1.0 from old clients; a custom domain + ACM certificate would allow `TLSv1.2_2021`.
* JWTs are stateless (no server-side revocation); lifetime is 60 minutes in production.
* No AWS WAF (cost); recommended before exposing the site to untrusted traffic.
