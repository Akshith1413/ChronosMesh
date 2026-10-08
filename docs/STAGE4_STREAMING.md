# ChronosMesh — Stage 4 Streaming & Distributed Infrastructure
**Apache Kafka, Apache Flink, Neo4j, and Distributed Event Ingestion**

- **Engineer:** B. Guru Sai Prasad Reddy
- **Role:** Backend API, Full-Stack Integration, Frontend Dashboard, Visualization, Documentation
- **Status:** Complete & Verified
- **Date:** September 2026

---

## 1. System Architecture

ChronosMesh Stage 4 connects the core causal engine and FastAPI service to a real distributed streaming pipeline:

```
┌────────────────────────────────────────────────────────┐
│             Mock Multi-Cloud Services                  │
│  Order  •  Payment  •  Inventory  •  Shipping  •  SMS  │
│  (AWS Mumbai, AWS Singapore, GCP Mumbai, GCP Singapore)│
└───────────────────────────┬────────────────────────────┘
                            │
              Canonical Distributed Events
             (Injected skew, delay, inversion)
                            ▼
┌────────────────────────────────────────────────────────┐
│                     Apache Kafka                       │
│             Topic: [events.raw] (3 partitions)         │
└───────────────────────────┬────────────────────────────┘
                            │
               Continuous Event-Time Stream
                            ▼
┌────────────────────────────────────────────────────────┐
│             Apache Flink Streaming Pipeline            │
│  • Event-Time Watermarking (Bounded Out-of-Orderness)  │
│  • Session & Tumbling Window Causal Buffering          │
│  • Happens-Before & Transitive Reduction DAG Engine    │
│  • Causal Anomaly Detection & Confidence Scoring       │
└───────────────────────────┬────────────────────────────┘
                            │
             Reconstructed Enriched Events
                            ▼
┌────────────────────────────────────────────────────────┐
│                     Apache Kafka                       │
│           Topic: [events.causal] (3 partitions)        │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────────┐ ┌──────────────────────┐
│     Neo4j Graph Database     │ │   FastAPI Backend    │
│  • :Event nodes              │ │  • Background worker │
│  • :HAPPENS_BEFORE edges     │ │  • Dual-mode store   │
│  • Subgraph Cypher traversal │ │  • In-memory mirror  │
└──────────────┬───────────────┘ └──────────┬───────────┘
               │                            │
               └──────────────┬─────────────┘
                              ▼
                 Live SSE Event Stream
                 GET /api/events/stream
                              ▼
┌────────────────────────────────────────────────────────┐
│        React Dashboard & D3.js Causal Graph            │
│  • Live stream reception without page refresh          │
│  • Out-of-order arrival vs causal order comparison     │
│  • Interactive graph inspection & root-cause traversal │
└────────────────────────────────────────────────────────┘
```

---

## 2. Apache Kafka Integration

### Topics
1. **`events.raw`**: Ingests raw, uncoordinated event envelopes emitted by microservices across multi-cloud regions.
2. **`events.causal`**: Emits statefully reconstructed causal events enriched with upstream parents, topological depths, anomaly indicators, and TrueTime-style confidence metrics.

### Producer (`chronosmesh/stream/producer.py`)
- **Class:** `KafkaEventProducer` with `InMemoryEventProducer` fallback.
- **Capabilities:**
  - Automatic JSON serialization validation against the Stage 2 canonical event schema.
  - Delivery callbacks, retry backoffs, and metrics tracking (`published`, `successes`, `failures`).
  - Seamless failover: if Kafka is unreachable or `CHRONOSMESH_FORCE_IN_MEMORY_KAFKA=true`, routes messages into the local in-memory event bus.

### Consumer (`chronosmesh/stream/consumer.py`)
- **Class:** `KafkaEventConsumer` with `InMemoryEventConsumer` fallback.
- **Capabilities:**
  - Deserialization with schema validation into `Event` dataclass.
  - Polling with configurable timeouts, batch consumption, and callback dispatching.

---

## 3. Apache Flink Stream Processing (`chronosmesh/stream/flink_pipeline.py`)

### Processing Model
- **Event-Time Watermarks:**
  $$\text{Watermark}(t) = \max_{e \in \text{stream}}(e.\text{timestamp\_ms}) - \Delta_{\text{out\_of\_order}}$$
  Default bounded out-of-orderness tolerance $\Delta_{\text{out\_of\_order}} = 500\,\text{ms}$ (configurable via `FLINK_OUT_OF_ORDERNESS_MS`).
- **Out-of-Order Buffering:**
  Events arriving before their causal predecessors are held in `EventBuffer`. When predecessors arrive or the watermark advances beyond the maximum wait time, events are emitted in topological causal sequence.
- **Stateful Intelligence:**
  Integrates directly with Akshith's Stage 1 `CausalDAGBuilder`, `CausalAnomalyDetector`, and `ConfidenceScorer` without code duplication.

---

## 4. Neo4j Graph Database Integration (`chronosmesh/storage/neo4j_store.py`)

### Cypher Schema Implementation
Follows [`docs/NEO4J_SCHEMA.md`](file:///c:/Users/gurus/OneDrive/Desktop/FOURTH%20YEAR%20SEMESTER-7%20PPTS/Cloud%20Computing%20PE-5/Project-Case-Study/ChronosMesh/docs/NEO4J_SCHEMA.md):
- **Nodes:**
  - `(:Event {event_id, service_id, event_type, timestamp_ms, arrival_time_ms, lamport_ts, vector_clock, hlc_pt, hlc_l, region, clock_uncertainty_ms, trace_id})`
- **Edges:**
  - `(:Event)-[:HAPPENS_BEFORE {confidence, explicit, method, uncertainty_ms}]->(:Event)`
- **Constraints & Indexes:**
  - Unique constraint on `Event.event_id` ensuring strict idempotency.
  - Indexes on `trace_id`, `timestamp_ms`, and `service_id`.
- **Query APIs:**
  - `get_event(event_id)`
  - `get_trace(trace_id)`
  - `get_dag(trace_id)`
  - `get_ancestors(event_id, max_depth)` (backward Cypher traversal)
  - `get_descendants(event_id, max_depth)` (forward Cypher traversal)
  - `get_concurrent_events(event_id)`

---

## 5. Mock Microservices & Controlled Fault Injection (`chronosmesh/services/mock_services.py`)

Simulates a real-world multi-cloud e-commerce workflow:
1. `order-svc` (AWS Mumbai) $\rightarrow$ `ORDER_CREATED`
2. `payment-svc` (AWS Singapore) $\rightarrow$ `PAYMENT_STARTED`
3. `payment-svc` (AWS Singapore) $\rightarrow$ `PAYMENT_COMPLETED`
4. `inventory-svc` (GCP Mumbai) $\rightarrow$ `INVENTORY_RESERVED`
5. `shipping-svc` (GCP Singapore) $\rightarrow$ `SHIPMENT_CREATED`
6. `notification-svc` (AWS Mumbai) $\rightarrow$ `NOTIFICATION_SENT`

### Controlled Fault Parameters
- `SIMULATE_NETWORK_DELAY=true`: Cross-region delays ($15\,\text{ms} - 110\,\text{ms}$).
- `SIMULATE_CLOCK_SKEW=true`: Skews physical clocks across regions (e.g. Singapore $+65\,\text{ms}$, GCP Mumbai $-40\,\text{ms}$).
- `SIMULATE_OUT_OF_ORDER=true`: Deliberately inverts network delivery timestamps such that arrival sequence is:
  $$E_1 \rightarrow E_3 \rightarrow E_2 \rightarrow E_5 \rightarrow E_4 \rightarrow E_6$$
  where child events ($E_3, E_5$) arrive before their causal parents ($E_2, E_4$).

---

## 6. Live API & Server-Sent Events (SSE)

- **Dual-Mode Data Layer:**
  - `DATA_SOURCE=demo`: Serves deterministic scenario catalog (`T-1001`, `T-1002`, `T-1003`).
  - `DATA_SOURCE=live`: Reads directly from Neo4j graph storage and streams live events from the Kafka consumer queue.
- **Real-Time SSE (`GET /api/events/stream`):**
  - Asynchronous event dispatcher queues incoming events to connected browser sessions with automatic heartbeats every 2 seconds.

---

## 7. Docker Orchestration (`docker-compose.yml`)

Unified local stack containing:
- `zookeeper` (port 2181)
- `kafka` (ports 9092, 29092)
- `neo4j` (HTTP 7474, Bolt 7687)
- `flink-jobmanager` (web dashboard 8081)
- `flink-taskmanager`
- `chronosmesh-api` (FastAPI backend + React Dashboard on port 8000)

Run stack:
```bash
docker compose up -d
```

---

## 8. Verification Results

- **Python Tests:** **182 passing** (162 core engine + 8 API + 5 Stage 3 features + 7 Stage 4 E2E)
- **Frontend Tests:** **4 passing** (Vitest UI & contract tests)
- **Throughput:** ~72 events/sec with full incremental transitive reduction in Python; over 2,000 events/sec for windowed batch processing.
