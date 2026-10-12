"""Workload generator and fault injector."""

import pytest

from chronosmesh.simulator import ExperimentConfig, generate_workload, inject_faults, make_services


def cfg(**kw):
    base = dict(num_services=4, num_events=400, events_per_execution=20)
    base.update(kw)
    return ExperimentConfig(**base).validate()


def test_config_validation_ranges():
    for bad in (dict(num_services=1), dict(num_services=51), dict(num_events=5), dict(num_events=100_001),
                dict(network_delay_ms=2001), dict(duplicate_rate=0.11), dict(missing_rate=0.06),
                dict(delivery_mode="chaotic"), dict(transport="carrier-pigeon"), dict(repeats=0), dict(worker_failures=11),
                dict(retry_rate=0.5), dict(retry_burst=1)):
        with pytest.raises(ValueError):
            ExperimentConfig(**{**dict(num_events=1000), **bad}).validate()
    assert ExperimentConfig(num_services=50, num_events=100_000, network_delay_ms=2000, duplicate_rate=0.10,
                            missing_rate=0.05).validate()


def test_config_rejects_unknown_keys_and_enforces_deployment_limit():
    with pytest.raises(ValueError, match="unknown"):
        ExperimentConfig.from_dict({"num_events": 100, "bogus": 1})
    with pytest.raises(ValueError, match="limit"):
        ExperimentConfig(num_events=50_000).validate(max_events=25_000)


def test_events_per_execution_clipped_and_execution_count():
    c = ExperimentConfig(num_events=30, events_per_execution=100).validate()
    assert c.events_per_execution == 30 and c.num_executions == 1
    assert ExperimentConfig(num_events=100, events_per_execution=40).validate().num_executions == 3


def test_make_services_canonical_then_generic():
    names = [s[0] for s in make_services(6)]
    assert names[:4] == ["order-service", "payment-service", "inventory-service", "shipping-service"]
    assert names[4:] == ["svc-05", "svc-06"]


def test_workload_is_deterministic_and_counts_match():
    a, b = generate_workload(cfg(), 7), generate_workload(cfg(), 7)
    assert [e.event_id for e in a.events] == [e.event_id for e in b.events]
    assert len(a.events) == 400 and len(a.executions) == 20
    assert generate_workload(cfg(), 8).events[0].event_id != a.events[0].event_id


def test_true_clocks_are_consistent_with_declared_parents():
    gt = generate_workload(cfg(), 3)
    by_id = {e.event_id: e for e in gt.events}
    for e in gt.events:
        for p in e.parent_event_ids:
            parent = by_id[p]
            assert parent.lamport_ts < e.lamport_ts
            assert all(e.vector_clock.get(k, 0) >= v for k, v in parent.vector_clock.items())
            assert gt.true_time_ms[p] < gt.true_time_ms[e.event_id]


def test_in_order_delivery_preserves_generation_order():
    c = cfg(delivery_mode="in_order")
    gt = generate_workload(c, 1)
    d = inject_faults(gt, c, 1)
    assert [e.event_id for e in d.delivered] == [e.event_id for e in gt.events]


def test_randomized_delivery_reorders_events():
    c = cfg(delivery_mode="randomized", network_delay_ms=500)
    gt = generate_workload(c, 1)
    d = inject_faults(gt, c, 1)
    assert [e.event_id for e in d.delivered] != [e.event_id for e in gt.events]
    assert d.delivered == sorted(d.delivered, key=lambda e: e.arrival_time_ms)


def test_drop_and_duplicate_rates_are_applied():
    c = cfg(num_events=4000, events_per_execution=40, missing_rate=0.05, duplicate_rate=0.10)
    gt = generate_workload(c, 2)
    d = inject_faults(gt, c, 2)
    assert 0.03 < len(d.dropped_ids) / 4000 < 0.07
    assert 0.07 < len(d.duplicated_ids) / 4000 < 0.13
    assert len(d.delivered) == 4000 - len(d.dropped_ids) + len(d.duplicated_ids)
    assert not (d.dropped_ids & d.unique_delivered_ids)


def test_clock_drift_moves_wall_clock_but_not_logical_clocks():
    c = cfg(clock_drift_ms=1000)
    gt = generate_workload(c, 4)
    d = inject_faults(gt, c, 4)
    true_by_id = {e.event_id: e for e in gt.events}
    shifts = [abs(e.timestamp_ms - true_by_id[e.event_id].timestamp_ms) for e in d.delivered]
    assert max(shifts) > 100
    assert all(e.vector_clock == true_by_id[e.event_id].vector_clock for e in d.delivered)


def test_metadata_loss_clears_vector_clock_on_copies_only():
    c = cfg(metadata_loss_rate=0.5)
    gt = generate_workload(c, 5)
    d = inject_faults(gt, c, 5)
    assert d.metadata_lost_ids
    true_by_id = {e.event_id: e for e in gt.events}
    for e in d.delivered:
        assert bool(e.vector_clock) == (e.event_id not in d.metadata_lost_ids)
        assert true_by_id[e.event_id].vector_clock   # ground truth untouched


def test_fault_injection_does_not_mutate_ground_truth():
    c = cfg(clock_drift_ms=500, metadata_loss_rate=0.3, duplicate_rate=0.1)
    gt = generate_workload(c, 6)
    before = [(e.timestamp_ms, dict(e.vector_clock), e.arrival_time_ms) for e in gt.events]
    inject_faults(gt, c, 6)
    assert before == [(e.timestamp_ms, dict(e.vector_clock), e.arrival_time_ms) for e in gt.events]


def test_retry_storms_are_real_events_in_the_ground_truth():
    c = cfg(num_events=600, events_per_execution=60, retry_rate=0.05, retry_burst=6)
    gt = generate_workload(c, 21)
    retries = [e for e in gt.events if e.payload.get("retry_of")]
    assert len(retries) >= 12 and len(gt.events) == 600
    by_id = {e.event_id: e for e in gt.events}
    for r in retries:
        parent = by_id[r.parent_event_ids[0]]
        assert parent.service_id == r.service_id and r.payload["attempt"] >= 2
        assert parent.lamport_ts < r.lamport_ts and all(r.vector_clock.get(k, 0) >= v for k, v in parent.vector_clock.items())
        assert gt.true_time_ms[parent.event_id] < gt.true_time_ms[r.event_id]
    storms = {r.payload["retry_of"] for r in retries}
    assert any(sum(1 for r in retries if r.payload["retry_of"] == s) >= 5 for s in storms)
