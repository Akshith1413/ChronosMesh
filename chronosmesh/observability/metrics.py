"""Prometheus metrics for ChronosMesh (API and worker share these definitions).

Names follow the ChronosMesh blueprint (§8): ``chronosmesh_events_received_total``,
``..._events_processed_total``, ``..._events_duplicate_total``, ``..._unresolved_dependencies``,
``..._reconstruction_duration_seconds``, ``..._queue_oldest_message_age_seconds``,
``..._graph_nodes``, ``..._graph_edges``, ``..._processing_errors_total``.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── Pipeline (spec §8) ────────────────────────────────────────────────────────
EVENTS_RECEIVED = Counter(
    "chronosmesh_events_received_total",
    "Total number of raw events ingested into ChronosMesh",
    ["service_id", "region"],
)
EVENTS_PROCESSED = Counter(
    "chronosmesh_events_processed_total",
    "Total number of events successfully processed into the causal DAG",
    ["service_id"],
)
EVENTS_DUPLICATE = Counter(
    "chronosmesh_events_duplicate_total",
    "Total number of duplicate event deliveries detected and ignored (idempotent processing)",
)
UNRESOLVED_DEPENDENCIES = Gauge(
    "chronosmesh_unresolved_dependencies",
    "Declared parent dependencies that have not been observed yet (across active executions)",
)
RECONSTRUCTION_DURATION = Histogram(
    "chronosmesh_reconstruction_duration_seconds",
    "Time spent reconstructing an execution's causal graph",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
QUEUE_OLDEST_MESSAGE_AGE = Gauge(
    "chronosmesh_queue_oldest_message_age_seconds",
    "Age of the oldest message waiting in the event queue",
)
QUEUE_DEPTH = Gauge(
    "chronosmesh_queue_depth",
    "Approximate number of visible messages in the event queue",
)
GRAPH_NODES = Gauge("chronosmesh_graph_nodes", "Nodes in the most recently reconstructed execution graph")
GRAPH_EDGES = Gauge("chronosmesh_graph_edges", "Causal edges in the most recently reconstructed execution graph")
PROCESSING_ERRORS = Counter(
    "chronosmesh_processing_errors_total",
    "Processing failures (a failed queue message is retried and eventually dead-lettered)",
    ["stage"],
)
WORKER_HEARTBEAT = Gauge(
    "chronosmesh_worker_heartbeat_timestamp_seconds",
    "Unix time of the worker's last completed poll loop",
)

# ── Experiments ───────────────────────────────────────────────────────────────
EXPERIMENTS = Counter("chronosmesh_experiments_total", "Experiments by terminal status", ["status"])
EXPERIMENT_DURATION = Histogram(
    "chronosmesh_experiment_duration_seconds",
    "Wall time of a complete experiment",
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600],
)

# ── Pre-existing application metrics (kept for dashboards / alert rules) ──────
EVENTS_FAILED = Counter(
    "chronosmesh_events_failed_total",
    "Total number of malformed or dropped events",
    ["reason"],
)
API_REQUESTS = Counter(
    "chronosmesh_api_requests_total",
    "Total API requests processed by FastAPI",
    ["method", "endpoint", "status"],
)
API_REQUEST_DURATION = Histogram(
    "chronosmesh_api_request_duration_seconds",
    "API request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)
SSE_CONNECTIONS = Gauge(
    "chronosmesh_sse_connections",
    "Current active live Server-Sent Events (SSE) subscriber connections",
)
ANOMALIES_TOTAL = Counter(
    "chronosmesh_anomalies_total",
    "Total number of causal anomalies detected",
    ["anomaly_type", "severity"],
)
KAFKA_MESSAGES_PRODUCED = Counter(
    "chronosmesh_kafka_messages_produced_total",
    "Total messages published to Kafka topics",
    ["topic"],
)
KAFKA_MESSAGES_CONSUMED = Counter(
    "chronosmesh_kafka_messages_consumed_total",
    "Total messages consumed from Kafka topics",
    ["topic"],
)
NEO4J_OPERATIONS = Counter(
    "chronosmesh_neo4j_operations_total",
    "Total Neo4j graph database read/write operations",
    ["operation"],
)
CAUSAL_PROCESSING_DURATION = Histogram(
    "chronosmesh_causal_processing_duration_seconds",
    "Latency of causal DAG reconstruction and transitive reduction per event/window",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.5, 1.0],
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def record_event_received(service_id: str = "unknown", region: str = "unknown") -> None:
    EVENTS_RECEIVED.labels(service_id=service_id, region=region).inc()


def record_event_processed(service_id: str = "unknown") -> None:
    EVENTS_PROCESSED.labels(service_id=service_id).inc()


def record_duplicate(n: int = 1) -> None:
    EVENTS_DUPLICATE.inc(n)


def record_error(stage: str) -> None:
    PROCESSING_ERRORS.labels(stage=stage).inc()


def record_anomaly(anomaly_type: str = "UNKNOWN", severity: str = "WARNING") -> None:
    ANOMALIES_TOTAL.labels(anomaly_type=anomaly_type, severity=severity).inc()


def record_kafka_produced(topic: str = "events.raw") -> None:
    KAFKA_MESSAGES_PRODUCED.labels(topic=topic).inc()


def record_kafka_consumed(topic: str = "events.causal") -> None:
    KAFKA_MESSAGES_CONSUMED.labels(topic=topic).inc()


def record_neo4j_op(operation: str = "write_event") -> None:
    NEO4J_OPERATIONS.labels(operation=operation).inc()


def observe_reconstruction(seconds: float, result) -> None:
    """Engine ``on_rebuild`` hook: record latency and size of the graph just rebuilt."""
    RECONSTRUCTION_DURATION.observe(seconds)
    GRAPH_NODES.set(result.dag.number_of_nodes())
    GRAPH_EDGES.set(result.dag.number_of_edges())


def get_prometheus_output() -> bytes:
    """Serialize all metrics in standard Prometheus text format."""
    return generate_latest(REGISTRY)
