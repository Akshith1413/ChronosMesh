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
