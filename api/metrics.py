"""ChronosMesh Observability — Prometheus Metrics Exporter.

The definitions live in :mod:`chronosmesh.observability.metrics` so the API and the queue worker
export identical series; this module re-exports them for backwards compatibility.
"""

from chronosmesh.observability.metrics import *  # noqa: F401,F403
from chronosmesh.observability.metrics import (  # noqa: F401  (explicit for static analysers)
    ANOMALIES_TOTAL,
    API_REQUEST_DURATION,
    API_REQUESTS,
    CAUSAL_PROCESSING_DURATION,
    CONTENT_TYPE_LATEST,
    EVENTS_FAILED,
    EVENTS_PROCESSED,
    EVENTS_RECEIVED,
    KAFKA_MESSAGES_CONSUMED,
    KAFKA_MESSAGES_PRODUCED,
    NEO4J_OPERATIONS,
    SSE_CONNECTIONS,
    get_prometheus_output,
    record_anomaly,
    record_event_processed,
    record_event_received,
    record_kafka_consumed,
    record_kafka_produced,
    record_neo4j_op,
)
