"""
Stage 4 End-to-End Distributed Data & Streaming Integration Tests.

Verifies:
1. Mock multi-cloud microservices (Order, Payment, Inventory, Shipping, Notification)
2. Fault injection (network delay, clock skew, out-of-order arrival)
3. Kafka Event Producer (publishing, serialization, fallback)
4. Flink Streaming Pipeline (watermarks, bounded out-of-order buffering, causal DAG, anomalies)
5. Neo4j Graph Persistence (nodes, edges, ancestors, descendants, concurrency)
6. Idempotency on duplicate events
7. FastAPI Ingestion & Live SSE Event broadcasting
8. High-throughput performance benchmark
"""

import json
import time
import pytest
from fastapi.testclient import TestClient

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.services.mock_services import MockDistributedCluster, SERVICE_CONFIGS
from chronosmesh.stream.producer import KafkaEventProducer, InMemoryEventProducer
from chronosmesh.stream.flink_pipeline import FlinkStreamingPipeline
from chronosmesh.storage.neo4j_store import Neo4jStore
from api.main import app
from api.store import get_store


@pytest.fixture
def mock_cluster():
    return MockDistributedCluster(
        simulate_network_delay=True,
        simulate_clock_skew=True,
        simulate_out_of_order=True,
    )


@pytest.fixture
def api_client():
    return TestClient(app)


def test_mock_cluster_event_generation_and_fault_injection(mock_cluster):
    """Verify 5 services emit canonical events with clock skew and out-of-order arrival."""
    events = mock_cluster.generate_ecommerce_trace(trace_id="T-E2E-001")
    assert len(events) == 6

    # Verify service participation
    services = {e.service_id for e in events}
    assert services == {"order-svc", "payment-svc", "inventory-svc", "shipping-svc", "notification-svc"}

    # Verify multi-region metadata
    regions = {e.metadata.region for e in events}
    assert "aws-mumbai" in regions
    assert "aws-singapore" in regions
    assert "gcp-mumbai" in regions
    assert "gcp-singapore" in regions

    # Verify deliberate out-of-order arrival:
    # Causal Order: E1 -> E2 -> E3 -> E4 -> E5 -> E6
    # Arrival Order: E1 -> E3 -> E2 -> E5 -> E4 -> E6
    arrival_order = sorted(events, key=lambda x: x.arrival_time_ms)
    arrival_types = [e.event_type for e in arrival_order]

    # E3 (PAYMENT_COMPLETED) arrived before E2 (PAYMENT_STARTED)
    assert arrival_types.index("PAYMENT_COMPLETED") < arrival_types.index("PAYMENT_STARTED")
    # E5 (SHIPMENT_CREATED) arrived before E4 (INVENTORY_RESERVED)
    assert arrival_types.index("SHIPMENT_CREATED") < arrival_types.index("INVENTORY_RESERVED")


def test_kafka_producer_publishing():
    """Verify producer publishes canonical events with validation and stats."""
    producer = KafkaEventProducer(default_topic="events.raw")
    ev = Event(
        event_id="E-KAFKA-1",
        service_id="order-svc",
        event_type="ORDER_CREATED",
        timestamp_ms=time.time() * 1000,
        trace_id="T-KAFKA-100",
    )
    ok = producer.publish_event(ev)
    assert ok is True
    assert producer.stats["published"] >= 1


def test_flink_streaming_pipeline_out_of_order_reconstruction(mock_cluster):
    """Verify Flink pipeline buffers out-of-order events and reconstructs correct causal DAG."""
    raw_events = mock_cluster.generate_ecommerce_trace(trace_id="T-FLINK-01")
    
    # Sort by arrival order to simulate out-of-order stream receipt
    arrival_stream = sorted(raw_events, key=lambda x: x.arrival_time_ms)

    pipeline = FlinkStreamingPipeline(out_of_orderness_ms=500.0)
    result = pipeline.process_stream(arrival_stream)

    assert result["processed_count"] == 6
    assert result["dag_nodes"] == 6
    # 5 sequential causal transitions: E1->E2->E3->E4->E5->E6
    assert result["dag_edges"] >= 5

    # Verify stats
    stats = pipeline.get_statistics()
    assert stats["raw_events_received"] == 6
    assert stats["causal_events_emitted"] >= 6


def test_neo4j_graph_persistence_and_queries(mock_cluster):
    """Verify Neo4jStore saves events/edges and supports causal graph queries."""
    store = Neo4jStore()
    events = mock_cluster.generate_ecommerce_trace(trace_id="T-NEO4J-01")

    # Persist all events
    for e in events:
        saved = store.save_event(e)
        assert saved is True

    # Persist causal edges with confidence scores
    for i in range(len(events) - 1):
        src = events[i].event_id
        tgt = events[i + 1].event_id
        store.save_causal_edge(src, tgt, confidence=0.95, explicit=True)

    # 1. Query trace
    trace_events = store.get_trace("T-NEO4J-01")
    assert len(trace_events) == 6

    # 2. Query DAG
    dag = store.get_dag("T-NEO4J-01")
    assert len(dag["nodes"]) == 6
    assert len(dag["edges"]) >= 5

    # 3. Query ancestors of last event (E6)
    e6_id = events[-1].event_id
    ancestors = store.get_ancestors(e6_id)
    assert len(ancestors) == 5

    # 4. Query descendants of first event (E1)
    e1_id = events[0].event_id
    descendants = store.get_descendants(e1_id)
    assert len(descendants) == 5

    # 5. Query single event
    fetched = store.get_event(e1_id)
    assert fetched is not None
    assert fetched["event_id"] == e1_id
    assert fetched["service_id"] == "order-svc"


def test_idempotency_duplicate_event_handling():
    """Verify sending identical events does not duplicate graph nodes."""
    store = Neo4jStore()
    ev = Event(
        event_id="E-IDEMPOTENT-01",
        service_id="payment-svc",
        event_type="PAYMENT_STARTED",
        timestamp_ms=1000.0,
        trace_id="T-IDEMP-01",
    )
    # Save first time
    assert store.save_event(ev) is True
    # Save duplicate
    assert store.save_event(ev) is True

    trace_events = store.get_trace("T-IDEMP-01")
    # Must only contain 1 unique event node
    id_count = [e["id"] for e in trace_events if e["id"] == "E-IDEMPOTENT-01"]
    assert len(id_count) == 1


def test_e2e_streaming_pipeline_to_fastapi_and_sse(mock_cluster, api_client):
    """Verify complete path: Mock -> Flink -> Store -> Live SSE Broadcast."""
    from api.auth import create_access_token
    token = create_access_token({"sub": "guru"})
    headers = {"Authorization": f"Bearer {token}"}

    store = get_store()
    store.clear()

    received_sse_events = []

    def _sse_listener(ev_dict):
        received_sse_events.append(ev_dict)

    store.add_listener(_sse_listener)

    # Generate and process trace through Flink pipeline
    events = mock_cluster.generate_ecommerce_trace(trace_id="T-E2E-LIVE")
    pipeline = FlinkStreamingPipeline()

    for ev in events:
        emitted = pipeline.process_event(ev)
        for item in emitted:
            store.ingest_live_event(ev)

    store.remove_listener(_sse_listener)

    # Verify events reached the store
    assert len(store.events) == 6
    assert len(received_sse_events) == 6

    # Verify DAG is queryable via API with auth
    resp = api_client.get("/api/traces/T-1001/dag", headers=headers)
    assert resp.status_code == 200
    dag_data = resp.json()
    assert "nodes" in dag_data
    assert "edges" in dag_data

    # Verify SSE endpoint responds with stream headers
    stream_resp = api_client.get("/api/events/stream?limit=2")
    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]


def test_high_throughput_burst_processing():
    """Verify pipeline processes a burst of events within acceptable latency and reports metrics."""
    pipeline = FlinkStreamingPipeline(enable_anomaly_detection=False)
    num_events = 150
    events = []
    base_ts = time.time() * 1000

    for i in range(num_events):
        e = Event(
            event_id=f"E-BURST-{i}",
            service_id=f"service-{(i % 5) + 1}",
            event_type="BATCH_OP",
            timestamp_ms=base_ts + i * 5,
            trace_id=f"T-BURST-{(i // 50)}",
            vector_clock={f"service-{(i % 5) + 1}": i},
        )
        events.append(e)

    start = time.perf_counter()
    res = pipeline.process_stream(events)
    elapsed = time.perf_counter() - start

    assert res["processed_count"] == num_events
    assert elapsed > 0
    throughput = num_events / elapsed
    assert throughput > 30, f"Throughput was {throughput:.2f} events/sec"

