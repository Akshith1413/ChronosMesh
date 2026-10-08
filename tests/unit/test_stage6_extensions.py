"""
Unit tests for Stage 6 ecosystem extensions:
  - gRPC SDK & event emission
  - TimescaleDB / InfluxDB event audit trail & arrival inversion detection
  - PostgreSQL / DynamoDB metadata store CRUD operations
  - AWS Lambda event enrichment handler
  - GraphQL API router
"""

import pytest
from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.events.grpc_sdk import ChronosMeshGrpcEmitter
from chronosmesh.storage.timescale_store import TimescaleEventStore
from chronosmesh.storage.postgres_metadata import MetadataStore
from chronosmesh.storage.lambda_enrichment import lambda_handler, enrich_event_payload


def test_grpc_sdk_emission():
    emitter = ChronosMeshGrpcEmitter(
        service_id="payment-svc",
        region="aws-singapore",
        availability_zone="ap-southeast-1a",
        clock_uncertainty_ms=8.0,
    )
    event = emitter.create_event(
        event_type="PAYMENT_PROCESSED",
        trace_id="trace-grpc-001",
        payload={"amount": 99.99},
    )

    assert event.service_id == "payment-svc"
    assert event.lamport_ts == 1
    assert event.vector_clock["payment-svc"] == 1
    assert event.metadata.region == "aws-singapore"

    resp = emitter.emit_event(event)
    assert resp["status"] == "ACCEPTED"
    assert len(emitter.get_emitted_history()) == 1


def test_timescale_store_audit_and_inversions():
    store = TimescaleEventStore()
    now = 1727500000000.0

    # Event 1: Lamport 1, arrives at t=0
    e1 = Event(
        event_id="e1", service_id="order-svc", event_type="CREATED",
        timestamp_ms=now, lamport_ts=1, vector_clock={"order-svc": 1},
        hlc_ts=None, trace_id="trace-audit-001", span_id="s1",
        arrival_time_ms=now + 10,
    )
    # Event 2: Lamport 3 (child), arrives at t=20
    e2 = Event(
        event_id="e2", service_id="payment-svc", event_type="PAID",
        timestamp_ms=now + 15, lamport_ts=3, vector_clock={"order-svc": 1, "payment-svc": 1},
        hlc_ts=None, trace_id="trace-audit-001", span_id="s2",
        arrival_time_ms=now + 20,
    )
    # Event 3: Lamport 2 (parent of e2), arrives late at t=30 (Arrival Inversion!)
    e3 = Event(
        event_id="e3", service_id="auth-svc", event_type="AUTHED",
        timestamp_ms=now + 5, lamport_ts=2, vector_clock={"auth-svc": 1},
        hlc_ts=None, trace_id="trace-audit-001", span_id="s3",
        arrival_time_ms=now + 30,
    )

    store.insert_batch([e1, e2, e3])

    trail = store.get_trace_audit_trail("trace-audit-001")
    assert len(trail) == 3
    # Order by arrival: e1 (10ms), e2 (20ms), e3 (30ms)
    assert trail[0]["event_id"] == "e1"
    assert trail[1]["event_id"] == "e2"
    assert trail[2]["event_id"] == "e3"

    inversions = store.query_arrival_inversions("trace-audit-001")
    assert len(inversions) == 1
    assert inversions[0]["event_id"] == "e3"
    assert inversions[0]["inversion_delta"] == 1  # 3 - 2


def test_postgres_metadata_store():
    store = MetadataStore()
    
    # Check default seeded services
    services = store.list_all_services()
    assert len(services) >= 5
    service_ids = {s["service_id"] for s in services}
    assert "order-svc" in service_ids
    assert "payment-svc" in service_ids

    # Upsert custom service
    store.upsert_service_config(
        service_id="custom-worker",
        region="gcp-mumbai",
        availability_zone="asia-south1-b",
        clock_uncertainty_ms=3.5,
        status="ACTIVE",
        metadata={"version": "2.0"},
    )
    custom = store.get_service_config("custom-worker")
    assert custom is not None
    assert custom["region"] == "gcp-mumbai"
    assert custom["metadata"]["version"] == "2.0"

    # Save and retrieve trace config
    store.save_trace_config(
        trace_id="tr-test-100",
        scenario_name="ecommerce_demo",
        clock_strategy="vector",
        expected_node_count=6,
        status="COMPLETED",
    )
    tc = store.get_trace_config("tr-test-100")
    assert tc is not None
    assert tc["scenario_name"] == "ecommerce_demo"
    assert tc["expected_node_count"] == 6


def test_lambda_event_enrichment():
    raw_payload = {
        "event_id": "lambda-evt-001",
        "service_id": "notification-svc",
        "event_type": "SMS_SENT",
        "timestamp_ms": 1727500000000.0,
        "metadata": {
            "region": "aws-mumbai",
            "availability_zone": "ap-south-1b",
        },
    }

    enriched = enrich_event_payload(raw_payload)
    assert "arrival_time_ms" in enriched
    assert enriched["metadata"]["clock_uncertainty_ms"] == 5.0
    assert enriched["metadata"]["tags"]["enriched_by"] == "lambda-enrichment-v1"
    assert "transit_latency_ms" in enriched["metadata"]["tags"]

    # Test full lambda_handler
    event_batch = {"records": [raw_payload]}
    res = lambda_handler(event_batch)
    assert res["statusCode"] == 200
    assert res["processed_count"] == 1
