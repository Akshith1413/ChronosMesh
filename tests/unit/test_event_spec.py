"""Published event contract: names, ISO times, round trip, backwards compatibility."""

from chronosmesh.events.event import Event, iso_to_ms, ms_to_iso


def test_iso_conversion_roundtrip():
    ms = 1_760_000_000_123.0
    assert ms_to_iso(ms) == "2025-10-09T08:53:20.123Z"
    assert abs(iso_to_ms(ms_to_iso(ms)) - ms) < 1
    assert iso_to_ms(1234.5) == 1234.5
    assert iso_to_ms("2026-10-09T11:00:02Z") == iso_to_ms("2026-10-09T11:00:02+00:00")


def test_spec_dict_uses_published_field_names():
    e = Event(event_id="evt-104", service_id="payment-service", event_type="PAYMENT_COMPLETED",
              trace_id="trace-abc", span_id="span-payment-02", parent_event_ids=["evt-102"], lamport_ts=7,
              vector_clock={"order-service": 2, "payment-service": 4}, timestamp_ms=1_760_000_002_000.0,
              arrival_time_ms=1_760_000_004_000.0, execution_id="exec-001")
    d = e.to_spec_dict()
    for key in ("event_id", "execution_id", "service", "event_type", "trace_id", "span_id",
                "parent_event_ids", "lamport_clock", "vector_clock", "event_time", "ingestion_time"):
        assert key in d
    assert d["service"] == "payment-service" and d["lamport_clock"] == 7
    assert d["event_time"] < d["ingestion_time"]


def test_from_dict_accepts_spec_names_and_roundtrips():
    spec = {"event_id": "evt-1", "execution_id": "exec-9", "service": "order-service", "event_type": "ORDER_CREATED",
            "trace_id": "t", "span_id": "s", "parent_event_ids": [], "lamport_clock": 1, "vector_clock": {"order-service": 1},
            "event_time": "2026-10-09T11:00:02Z", "ingestion_time": "2026-10-09T11:00:04Z"}
    e = Event.from_dict(spec)
    assert e.service_id == "order-service" and e.lamport_ts == 1 and e.execution_id == "exec-9"
    assert e.arrival_time_ms - e.timestamp_ms == 2000.0
    again = Event.from_spec_dict(e.to_spec_dict())
    assert again.event_id == e.event_id and again.timestamp_ms == e.timestamp_ms


def test_internal_dict_roundtrip_keeps_execution_id():
    e = Event(event_id="x", service_id="s", trace_id="t1")
    assert e.effective_execution_id == "t1"            # falls back to trace id
    d = e.to_dict()
    assert d["execution_id"] == "t1"
    assert Event.from_dict(d).effective_execution_id == "t1"
    assert Event(event_id="x", service_id="s", execution_id="e1", trace_id="t1").effective_execution_id == "e1"
