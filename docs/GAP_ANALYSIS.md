# ChronosMesh — Gap Analysis (Baseline Audit)

**Audit date:** 2026-10-12 · **Repo commit audited:** `8eb1c1f` (`main`, up to date with `origin/main`)
**AWS account audited:** `712715586366`, region `ap-south-2` (read-only inspection via AWS CLI)
**Reference spec:** the "ChronosMesh — Complete Technical Architecture" blueprint (event schema, causal rules, API contract, AWS service plan, evaluation plan, 4 deployment phases).

> This file is the **frozen "before" list**. Its companion, [`COMPLETION_STATUS.md`](COMPLETION_STATUS.md), uses the **same IDs** and shows what was completed afterwards.

Legend: ✅ implemented & verified · 🟡 partially implemented · ❌ not implemented · ⚠️ implemented but broken/unsafe

---

## 0. Measured baseline

| Check | Result |
|---|---|
| `pytest tests/` | **212 passed, 3 failed** (README/status docs claim 215 green) |
| Failing tests | `test_graphql.py::test_graphql_schema_info`, `::test_graphql_concurrency_query`, `::test_graphql_dag_query` (HTTP 422) |
| `vitest run` | 18 passed |
| `vite build` | OK, 648 modules |
| `boto3` usage in repo | **0 files** — no code talks to any AWS service |
| Live API (`http://18.61.252.175`) | up, `/api/health` OK, **default demo credentials accepted from the public internet over plain HTTP** |

---

## 1. What is already solid (✅ keep as-is)

| Area | Evidence |
|---|---|
| Lamport / Vector / Hybrid Logical clocks | `chronosmesh/clocks/*`, unit tests |
| Happens-before + concurrency detection from vector clocks | `chronosmesh/causality/happens_before.py`, `concurrency.py` |
| Causal DAG with (incremental) transitive reduction | `chronosmesh/causality/dag_builder.py`, `transitive_reduction.py` |
| Root-cause, what-if, graph-diff, confidence scoring, clock benchmark | `chronosmesh/analysis/*` |
| FastAPI REST + SSE + GraphQL endpoint, JWT + 3-tier RBAC | `api/` |
| React 18 + TS + Vite dashboard (graph 2D/3D, timeline, anomalies, what-if, analytics, diff) | `frontend/src` |
| Prometheus exporter, Grafana dashboard JSON, alert rules | `api/metrics.py`, `observability/` |
| Docker Compose (Kafka/Neo4j/Flink/Prometheus/Grafana), k8s manifests | `docker-compose.yml`, `k8s/` |
| AWS base resources exist (S3 ×2, SQS ×3, DynamoDB ×4, ECS cluster, 2 ECR repos, IAM roles, SNS topic, log groups, 2 EC2) | AWS CLI inventory |

---

## 2. Core engine & data model (folder)

| ID | Item (spec ref) | State | Finding |
|---|---|:---:|---|
| E-01 | Event contract: `execution_id`, `event_time`, `ingestion_time` (spec §7A) | 🟡 | Model has `trace_id`, `timestamp_ms`, `arrival_time_ms`; no `execution_id`, no ISO times, no spec-format (de)serialiser |
| E-02 | Streaming pipeline anomaly/confidence stage | ⚠️ | `stream/processor.py` imports non-existent `chronosmesh.analyzer.*`; `ImportError` is swallowed → anomaly detection and confidence scoring **silently never run** |
| E-03 | Anomaly types: vector-clock gaps, clock drift, concurrent mutations | ⚠️ | `detect_vector_clock_gaps`, `detect_clock_drift`, `detect_concurrent_mutations` are empty stubs returning `[]` |
| E-04 | Spec anomalies: unresolved parent / missing dependency, late arrival, orphan event, retry storm, causal violation | ❌ | Only CYCLE, TIME_INVERSION, DUPLICATE_EVENT are functional |
| E-05 | "Mark unresolved dependencies rather than inventing edges" + link when the late parent arrives (spec §7E 4,7) | ❌ | `build_incremental` silently **drops** an edge whose parent has not arrived yet and never repairs it — the core out-of-order problem is unhandled in the incremental path |
| E-06 | Idempotent processing / duplicate suppression (spec §7E 2, §11) | ❌ | Re-ingesting an event ID silently overwrites the DAG node (dict-keyed); duplicates are only reported if the raw list happens to contain them; no suppression and no duplicate counter |
| E-07 | Scalable reconstruction (1k–100k events, spec §9) | 🟡 | `CausalDAGBuilder.build()` is O(n²) pairwise vector-clock comparison; incremental fallback scans every node |
| E-08 | Execution concept (`execution_id`), multiple executions side by side | ❌ | One global in-memory `ChronosMeshStore` for the whole process |
| E-09 | Fault-injection / chaos simulator with the spec's knobs (4/10/25/50 services, 1k–100k events, delay 0–2000 ms, duplicates 0–10 %, missing 0–5 %, clock drift, delivery modes in-order / randomized / heavily-delayed, retries) and **independent ground-truth graph** (spec §9) | ❌ | `MockDistributedCluster` is a fixed 5-service e-commerce flow; no ground truth, no rate knobs |
| E-10 | Research evaluation: 3 approaches (arrival-order, wall-clock, ChronosMesh); edge precision / recall / F1; concurrency-classification accuracy; latency; throughput; recovery rate; repeated runs with mean ± CI (spec §10) | ❌ | `ClockBenchmark` compares Lamport/Vector/HLC only; no baselines, no ground-truth scoring |
| E-11 | Worker that consumes the event queue and reconstructs (spec §6 Service C) | ❌ | No consumer process; only an in-process `StreamProcessor` |

## 3. API & persistence (folder)

| ID | Item | State | Finding |
|---|---|:---:|---|
| B-01 | Event ingestion endpoint (producers → platform) | ❌ | No `POST` for events; data only enters through built-in scenarios |
| B-02 | Spec API contract: `POST /api/experiments`, `POST /api/experiments/{id}/start`, `GET /api/executions/{id}`, `/graph`, `/anomalies`, `/metrics` (spec §5) | ❌ | None of these routes exist |
| B-03 | DynamoDB persistence (events, executions, anomalies, causal graphs) | ❌ | Tables exist in AWS; **zero code** writes to them |
| B-04 | SQS transport (producer → queue → worker → results queue) with DLQ handling | ❌ | Queues exist; zero code |
| B-05 | S3 archive of experiment results / graph exports | ❌ | Bucket exists, empty; zero code |
| B-06 | Storage abstraction with in-memory fallback so local/dev still works | ❌ | `store.py` hard-wires in-memory + Neo4j |
| B-07 | GraphQL endpoint | ⚠️ | Last commit made `current_user: Optional[Dict] = None` → FastAPI treats it as a 2nd body param → **HTTP 422 on every POST** (3 failing tests) **and removed authentication** from `/graphql` |
| B-08 | Per-user authorisation of executions (spec §11 "one user cannot access another's data") | ❌ | Single shared store, no ownership |
| B-09 | Spec Prometheus metrics: `events_duplicate_total`, `unresolved_dependencies`, `reconstruction_duration_seconds`, `queue_oldest_message_age_seconds`, `graph_nodes`, `graph_edges`, `processing_errors_total` | 🟡 | Have received/processed/failed/anomalies/…, but the 7 spec names above are missing |

## 4. Frontend (folder)

| ID | Item (spec §5) | State | Finding |
|---|---|:---:|---|
| F-01 | Screen 01 System Overview (events/s, queue backlog, processor health, reconstruction latency) | 🟡 | Dashboard exists but has no queue-backlog / processor-health / events-per-second from the live pipeline |
| F-02 | Experiments screen: create → configure faults → start → inspect (spec §5, §9) | ❌ | No page, no API client calls |
| F-03 | Screen 04 Anomaly Lab with injected failures, unresolved parents, late arrivals, duplicates | 🟡 | Anomalies page shows 3 anomaly types only |
| F-04 | Evaluation / results screen (baseline vs ChronosMesh precision/recall/F1 charts) | ❌ | — |
| F-05 | Screen 05 Observability (link/embed Grafana) | ❌ | No Grafana reference anywhere in `frontend/src` |
| F-06 | Spec library choices (Tailwind, React Flow, Recharts, TanStack Query, Zustand, React Router) | 🟡 (accepted deviation) | Implementation uses D3 + hand-written design system + Chart.js + local state. Functionally equivalent; **documented as a deviation, not re-platformed** |

## 5. Observability (folder)

| ID | Item | State | Finding |
|---|---|:---:|---|
| O-01 | OpenTelemetry instrumentation + Collector config (`observability/otel-collector.yaml`) | ❌ | No OTel anywhere |
| O-02 | Grafana auto-provisioning (datasource + dashboard provider) | ❌ | Dashboard JSON is mounted but nothing loads it; no datasource |
| O-03 | Prometheus scrape config correct for compose | ⚠️ | Targets `api:8000`, but the compose service is `chronosmesh-api` → scrape fails (only `host.docker.internal` works) |
| O-04 | Dashboards B (causal-engine performance) and C (fault injection) from spec §8 | 🟡 | One generic dashboard only |
| O-05 | Alert rules for spec signals (unresolved deps, queue age, reconstruction latency, worker down) | 🟡 | 6 rules, none for the spec signals |

## 6. Security (folder)

| ID | Item | State | Finding |
|---|---|:---:|---|
| S-01 | CORS whitelist | ⚠️ | `allow_origin_regex=".*"` **with** `allow_credentials=True` — reflects any origin; README claims a whitelist |
| S-02 | JWT secret management | ⚠️ | Hard-coded fallback secret in `api/auth.py`, the same value committed in `.env.example`; no fail-fast outside demo mode |
| S-03 | Secrets committed to Git | ⚠️ | `k8s/service.yaml` ConfigMap contains `JWT_SECRET` and `NEO4J_PASSWORD`; compose files contain Neo4j / Grafana passwords |
| S-04 | Demo users in production | ⚠️ | `guru/chronosmesh` (admin), `analyst/analyst123`, `demo/demo123` always enabled, no way to disable or supply real users |
| S-05 | Compiled artefacts tracked in Git | ⚠️ | 84 `__pycache__/*.pyc` files are committed |

## 7. Repo, CI/CD, containers, IaC (folder)

| ID | Item | State | Finding |
|---|---|:---:|---|
| R-01 | GitHub Actions CI | ⚠️ | Workflows live in `ChronosMesh-main/.github/workflows/` (nested dir) → **GitHub never runs them**; README cites a `ci.yml` that doesn't exist |
| R-02 | Infrastructure as Code (spec: `infrastructure/terraform/`, "high priority") | ❌ | Only a hand-made `task-definition.json`, `trust.json`, `userdata.sh`; AWS was built by hand |
| R-03 | Dockerfile | ⚠️ | `COPY . .` with no `.dockerignore` (ships `venv/`, `node_modules/`, `.git`); runs as root; **does not build the frontend** and `dist/` is gitignored → a fresh `git clone` deploy serves no React app |
| R-04 | Worker / simulator containers & compose services | ❌ | Only the API container exists |
| R-05 | k8s HPA / secrets split | 🟡 | HPA is embedded in `service.yaml` (status doc claims `k8s/hpa.yaml`); secrets in ConfigMap (see S-03) |
| R-06 | `userdata.sh` hardening | 🟡 | Uses `--reload` dev server via compose, runs `apt upgrade`, no health gate |

## 8. AWS cloud (account 712715586366 / ap-south-2)

| ID | Item (spec §3, §11, §12) | State | Finding |
|---|---|:---:|---|
| A-01 | ECR images | ❌ | Both repos (`chronosmesh-api`, `chronosmesh-engine`) are **empty** |
| A-02 | ECS Fargate services | ❌ | Cluster `chronosmesh-cluster` has **0 services, 0 tasks**; only `chronosmesh-api:1` task def (references a non-existent image); no worker/simulator task defs |
| A-03 | Live runtime | ⚠️ | The only running app is a hand-deployed t3.small EC2 (`18.61.252.175`); a **second EC2 (t3.micro, `40.192.110.111`) is running but unreachable on every port** — idle cost |
| A-04 | SQS dead-letter wiring | ❌ | `chronosmesh-events-dlq` exists but **no redrive policy** on `chronosmesh-events` / `-results` |
| A-05 | DynamoDB design | 🟡 | 4 on-demand tables, but **no TTL, no PITR, no GSIs** (cannot query by trace/service/time), no tags |
| A-06 | S3 policies | 🟡 | Private + SSE-S3 ✔; data bucket has **no lifecycle/retention** (spec §11); frontend bucket **not versioned**, nothing deployed |
| A-07 | Frontend delivery (S3 + CloudFront with OAC) | ❌ | No CloudFront distribution; frontend bucket empty |
| A-08 | CloudWatch alarms + dashboard | ❌ | **0 alarms, 0 dashboards**; `/chronosmesh/anomalies` log group has no retention |
| A-09 | SNS alerting | 🟡 | Topic exists with **0 subscriptions** |
| A-10 | IAM least privilege | ⚠️ | Task role has `AmazonSQSFullAccess`, `AmazonDynamoDBFullAccess`, `AmazonS3FullAccess`, `CloudWatchLogsFullAccess` (account-wide) instead of per-resource policies; EC2 instances have **no instance profile** |
| A-11 | Network exposure | ⚠️ | `chronosmesh-sg` allows **all protocols from 0.0.0.0/0**, SSH (22) world-open, Prometheus 9090 and Grafana 3000 world-open; `launch-wizard-1` SG exposes 22/8000 |
| A-12 | HTTPS / TLS to users | ❌ | Plain HTTP only |
| A-13 | Secrets Manager (spec: "high before production") | ❌ | No secrets; JWT secret is a code default |
| A-14 | X-Ray tracing (spec: "high") | ❌ | Not wired (sampling rule is the account default) |
| A-15 | API Gateway / Cognito | ❌ | Not present (API fronted directly by EC2) |
| A-16 | AWS Budgets / cost guard (spec §11) | ❌ | No budget found |
| A-17 | EventBridge / Step Functions (spec: medium) | ❌ | Not present |
| A-18 | Amazon MSK + Flink (spec phase 3) | ❌ | **Blocked by the account**: `kafka`/`kinesis` calls return `SubscriptionRequiredException` (free-tier restriction). Needs paid plan or a self-hosted Kafka substitute |
| A-19 | Managed Prometheus / Grafana (spec: optional) | ❌ | Not present (spec allows self-hosted) |
| A-20 | WAF / EKS / ElastiCache / RDS (spec: optional/advanced) | ❌ | Not present (optional per spec) |

## 9. Documentation accuracy

| ID | Item | State | Finding |
|---|---|:---:|---|
| X-01 | README / status docs vs reality | ⚠️ | Claims "215 passing" (actual 212 + 3 failing), "CORS whitelist", "CI/CD verified", "`.github/workflows/ci.yml`", "`observability/rules.yml`", "`k8s/hpa.yaml`", "Cloud deployment NOT EXECUTED" (partially false — AWS base exists) |
| X-02 | Deployment runbook for the real AWS stack | ❌ | `docs/CLOUD_DEPLOYMENT.md` is a blueprint for MSK/EKS/Aura; nothing describes what is actually deployed |
