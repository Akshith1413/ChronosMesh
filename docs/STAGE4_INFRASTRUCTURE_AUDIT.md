# ChronosMesh — Stage 4 Infrastructure Audit
**Distributed Data & Streaming Infrastructure Audit**

- **Engineer:** B. Guru Sai Prasad Reddy
- **Role:** Backend API, Full-Stack Integration, Frontend Dashboard, Visualization, Documentation
- **Status:** Completed
- **Date:** September 2026

---

## 1. Executive Summary

This audit establishes the baseline infrastructure of the ChronosMesh repository prior to Stage 4 implementation. In Stages 1 to 3, the core causal reconstruction algorithms, REST API, interactive D3.js causal graph, and React dashboard were completed and verified with 175 backend tests and 4 frontend tests. 

Stage 4 connects the deterministic, in-memory development layer to real distributed streaming and persistence infrastructure: **Apache Kafka**, **Apache Flink**, and **Neo4j Graph Database**, while maintaining complete backward compatibility with the Stage 3 React UI and REST API.

---

## 2. Infrastructure Inventory & Status

| Component | Existing? | Current Location | Current Configuration | Current Status | Stage 4 Action |
|---|---|---|---|---|---|
| **Kafka Broker** | Partial | `chronosmesh/stream/` | `confluent-kafka` library installed; `localhost:9092` default in `consumer.py` | Library installed; broker not running locally in Docker | Add Kafka + Zookeeper to `docker-compose.yml`; provide automated connection with graceful in-memory fallback |
| **Kafka Topics** | Partial | `docs/EVENT_SCHEMA.md` | Target: `events.raw`, `events.causal` documented in Stage 2/3 contracts | Conceptual definition only | Implement `chronosmesh/stream/topics.py` to auto-provision topics with partitions and retention |
| **Kafka Producer** | No | Missing | N/A | No dedicated producer wrapper | Create `chronosmesh/stream/producer.py` (`KafkaEventProducer`) with retry, validation, and in-memory fallback |
| **Kafka Consumer** | Yes | `chronosmesh/stream/consumer.py` | `KafkaEventConsumer` with fallback to `InMemoryEventConsumer` | Unit tested; reads raw messages | Extend to handle batch ingestion, deserialization validation, and background thread execution |
| **Schema Registry** | Partial | `docs/EVENT_SCHEMA.md` | JSON / Avro / Protobuf specs documented | Client-side Pydantic models in `chronosmesh/events/schemas.py` | Enforce canonical Pydantic validation on producer emission and consumer receipt |
| **Apache Flink** | Partial | `chronosmesh/stream/processor.py`, `windowing.py` | `StreamProcessor`, `TumblingWindow`, `SlidingWindow`, `SessionWindow` in Python | Core stream algorithms implemented; no PyFlink runner script | Implement `chronosmesh/stream/flink_pipeline.py` streaming pipeline with watermarks, bounded out-of-orderness buffering, and causal DAG emission; add Flink to `docker-compose.yml` |
| **Neo4j Database** | Partial | `docs/NEO4J_SCHEMA.md` | Cypher DDL, indexing, labels (`:Event`, `:Scenario`, `:Service`), relationships (`:HAPPENS_BEFORE`) | Driver installed; no connection/query logic in API | Create `chronosmesh/storage/neo4j_store.py` with Cypher queries for nodes, edges, ancestors, descendants; add Neo4j container to `docker-compose.yml` |
| **PostgreSQL / TimescaleDB** | No | `docs/NEO4J_SCHEMA.md` | Mentioned as optional audit store | Not implemented | Document as future phase expansion; Neo4j + Kafka provides complete causal graph + event log |
| **Docker / Compose** | Partial | `docker-compose.guru.yml` | FastAPI container only (`chronosmesh-api`) | Minimal single-service compose | Create unified `docker-compose.yml` orchestrating Kafka, Zookeeper, Flink JobManager, Flink TaskManager, Neo4j, FastAPI, and Frontend with healthchecks |
| **Mock Microservices** | Partial | `chronosmesh/events/generator.py` | `EventGenerator` and `ScenarioBuilder` generate synthetic chains | Generates static lists of events | Create `chronosmesh/services/mock_services.py` with 5 services (`Order`, `Payment`, `Inventory`, `Shipping`, `Notification`) across multi-cloud regions |
| **Fault Injection** | Partial | `chronosmesh/events/generator.py` | `inject_network_delay` method exists | Manual method calls only | Build automated fault injector: network delay, clock skew, out-of-order delivery, and event drop/failure |
| **API Data Store** | Yes | `api/store.py` | In-memory `ChronosMeshStore` using NetworkX | Active; serves all API endpoints | Refactor to dual-mode store supporting `DATA_SOURCE=live` (Neo4j) and `DATA_SOURCE=demo` (In-memory catalogue) |
| **SSE Live Stream** | Yes | `api/routers/events_router.py` | `GET /api/events/stream` with test limit support | Active with simulated ping/events | Connect to background Kafka consumer queue for live streaming of processed causal events |

---

## 3. Architecture Transition Plan

```
Current (Stage 3):
ScenarioBuilder / API Store ──> FastAPI In-Memory ──> React UI / D3 DAG

Target (Stage 4):
Mock Services (Order, Payment, Inventory, Shipping, Notification)
       │ (Canonical JSON events with multi-region metadata & injected faults)
       ▼
Kafka Topic: [events.raw]
       │
       ▼
Flink Streaming Pipeline (Watermarking, Bounded Out-of-Order Buffering, Causal Reconstruction, Anomaly Detection)
       │
       ▼
Kafka Topic: [events.causal]
       ├──> Neo4j Graph Database (Events, Causal DAG Edges, Cypher Traversal)
       │         │
       │         ▼
       └───> FastAPI Ingestion / SSE Consumer Queue
                 │
                 ▼
            React Dashboard & D3 Causal Graph (Live Real-Time Updates)
```

---

## 4. Key Decisions & Safeguards

1. **Dual-Mode Persistence (`DATA_SOURCE`):**
   - When `DATA_SOURCE=live`, the API queries the live Neo4j store and streams from Kafka.
   - When `DATA_SOURCE=demo` (or when Neo4j/Kafka are unreachable), the API gracefully falls back to the deterministic in-memory scenarios without breaking frontend functionality or tests.
2. **Zero Breaking Changes:**
   - Existing REST API contracts (`/api/traces/`, `/api/traces/{id}/dag`, `/api/analysis/*`) remain 100% identical.
   - Frontend TypeScript models and React components require zero modifications.
3. **Deterministic Integration Testing:**
   - End-to-end integration tests verify the complete pipeline using both live infrastructure and in-memory mock buses to guarantee test suite execution in any CI/CD environment.
