# ChronosMesh — End-to-End System Architecture

## 1. System Overview
ChronosMesh is a distributed causal tracing, anomaly detection, and reconstruction engine designed for multi-region microservices operating under network delay, physical clock skew, and out-of-order event delivery.

```mermaid
flowchart TB
    subgraph Emitting Services
        S1[Auth Service - AWS Mumbai]
        S2[Order Service - GCP Singapore]
        S3[Payment Service - AWS Mumbai]
        S4[Shipping Service - GCP Singapore]
    end

    subgraph Messaging & Ingestion
        K_RAW[Kafka Topic: events.raw]
        FallbackProd[In-Memory Producer Fallback]
    end

    subgraph Stateful Stream Engine - Apache Flink
        Watermark[Event-Time Watermarking Engine]
        Buffer[Bounded Out-of-Order Buffer]
        DAG_Engine[Incremental Causal DAG Builder]
        Anomaly[Anomaly & TrueTime Scorer]
        K_CAUSAL[Kafka Topic: events.causal]
    end

    subgraph Persistence Layer - Neo4j
        GraphStore[(Neo4j Graph Database: Event & CAUSED)]
        FallbackStore[(In-Memory Graph Store Mirror)]
    end

    subgraph Application & Gateway - FastAPI
        Auth[JWT / RBAC Guard: Viewer, Analyst, Admin]
        REST[REST API: Traces, Scenarios, DAG]
        SSE_Server[Server-Sent Events SSE Broadcaster]
        Metrics_Exp[Prometheus Exporter /metrics]
    end

    subgraph Telemetry & Operations
        Prom[Prometheus Server]
        Graf[Grafana Production Dashboards]
    end

    subgraph Presentation - React & D3
        UI[React 18 Dashboard]
        D3_DAG[D3.js Interactive Force DAG]
        Timeline[Arrival vs Causal Timeline]
    end

    S1 & S2 & S3 & S4 -->|Events with Logical/Vector Clocks| K_RAW
    K_RAW --> Watermark --> Buffer --> DAG_Engine --> Anomaly --> K_CAUSAL
    Anomaly --> GraphStore
    GraphStore <--> REST
    SSE_Server <--> UI
    REST <--> UI
    D3_DAG <--> UI
    Metrics_Exp --> Prom --> Graf
```

---

## 2. Architectural Layers

### 2.1 Logical Clock Foundations (Stage 1)
- **Lamport Clocks:** Scalar logical clock guaranteeing strict partial ordering ($a \to b \implies C(a) < C(b)$).
- **Vector Clocks:** Dimensional clock capturing causal dependency across independent microservices and detecting concurrent operations ($u \parallel v$).
- **Hybrid Logical Clocks (HLC):** Combines physical wall-clock time with logical counters, ensuring monotonic progression and TrueTime-bounded error margins.

### 2.2 Streaming & Causal Engine (Stage 4 & 5)
- **Bounded Out-of-Order Watermarking:** Flink tumbling windows with delay slack allow out-of-order arrivals to be sorted before DAG construction.
- **Incremental Transitive Reduction:** Localized neighbor pruning reduces per-event complexity from $O(N^3)$ to $O(k \cdot |V|)$, eliminating transitive bypass edges.

### 2.3 Persistence & Resiliency (Stage 2 & 5)
- **Neo4j Property Graph:** Stores events as `:Event` nodes and causal relationships as `[:CAUSED {confidence, explicit}]` edges.
- **Dual-Mode Resiliency:** When external Kafka or Neo4j brokers are unreachable, the system automatically activates in-memory fallbacks without dropping events or crashing.

### 2.4 Security & Observability (Stage 5)
- **Role-Based Access Control:** Strict JWT token enforcement across `ROLE_VIEWER`, `ROLE_ANALYST`, and `ROLE_ADMIN`.
- **Telemetry:** Built-in Prometheus `/metrics` scraper, pre-configured Grafana dashboard, alert rules, and structured JSON logging with secret sanitization.
