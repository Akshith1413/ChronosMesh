"""
ChronosMesh Observability — Prometheus Metrics Exporter.

Exposes real-time application metrics for Prometheus scraping:
- Event ingestion & processing throughput
- Causal reconstruction & anomaly rates
- Kafka produce/consume message rates
- Neo4j graph persistence operations
- API latency histograms and HTTP status counters
- Live SSE active connection gauge
"""

import time
from typing import Any, Dict

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

# ── Metrics Definitions ────────────────────────────────────────────────────────

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


# ── Metrics Helpers ────────────────────────────────────────────────────────────

def record_event_received(service_id: str = "unknown", region: str = "unknown"):
    EVENTS_RECEIVED.labels(service_id=service_id, region=region).inc()


def record_event_processed(service_id: str = "unknown"):
    EVENTS_PROCESSED.labels(service_id=service_id).inc()


def record_anomaly(anomaly_type: str = "UNKNOWN", severity: str = "WARNING"):
    ANOMALIES_TOTAL.labels(anomaly_type=anomaly_type, severity=severity).inc()


def record_kafka_produced(topic: str = "events.raw"):
    KAFKA_MESSAGES_PRODUCED.labels(topic=topic).inc()


def record_kafka_consumed(topic: str = "events.causal"):
    KAFKA_MESSAGES_CONSUMED.labels(topic=topic).inc()


def record_neo4j_op(operation: str = "write_event"):
    NEO4J_OPERATIONS.labels(operation=operation).inc()


def get_prometheus_output() -> bytes:
    """Serialize all metrics in standard Prometheus text format."""
    return generate_latest(REGISTRY)
