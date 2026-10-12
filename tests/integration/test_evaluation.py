"""End-to-end experiment runs: ChronosMesh vs. baselines against the independent ground truth."""

import pytest

from chronosmesh.evaluation import APPROACHES, mean_ci, prf, run_experiment, run_single
from chronosmesh.evaluation.metrics import chain_edges
from chronosmesh.simulator import ExperimentConfig


def run(**kw):
    base = dict(num_services=4, num_events=600, events_per_execution=20, repeats=1)
    base.update(kw)
    return run_experiment(ExperimentConfig(**base))


def test_prf_math():
    m = prf({("a", "b"), ("b", "c"), ("x", "y")}, {("a", "b"), ("b", "c"), ("c", "d")})
    assert (m["tp"], m["fp"], m["fn"]) == (2, 1, 1)
    assert m["precision"] == pytest.approx(2 / 3) and m["recall"] == pytest.approx(2 / 3) and m["f1"] == pytest.approx(2 / 3)
    empty = prf(set(), set())
    assert empty["precision"] == empty["recall"] == empty["f1"] == 1.0


def test_chain_edges_and_ci():
    assert chain_edges(["a", "b", "c"]) == {("a", "b"), ("b", "c")}
    ci = mean_ci([1.0, 2.0, 3.0])
    assert ci["mean"] == 2.0 and ci["ci95_low"] < 2.0 < ci["ci95_high"] and ci["n"] == 3
    assert mean_ci([5.0])["ci95_low"] == 5.0


def test_clean_run_reconstructs_the_truth_exactly_and_beats_baselines():
    r = run(delivery_mode="randomized", network_delay_ms=400)["runs"][0]
    a = r["approaches"]
    assert a["chronosmesh"]["f1"] == pytest.approx(1.0)
    assert a["chronosmesh"]["f1"] > a["declared_only"]["f1"] > a["wall_clock"]["f1"] > a["arrival_order"]["f1"]
    assert r["recovered"]
    assert r["arrival_disorder"] > 0.2          # the stream really is out of order


def test_concurrency_baselines_can_never_detect_concurrency():
    c = run()["runs"][0]["concurrency"]
    for ap in ("arrival_order", "wall_clock"):
        assert c[ap]["concurrent_recall"] == 0.0
    assert c["chronosmesh"]["concurrent_recall"] == pytest.approx(1.0)
    assert c["chronosmesh"]["accuracy"] == pytest.approx(1.0)


def test_lost_events_are_bridged_by_vector_clocks():
    r = run(missing_rate=0.05)["runs"][0]
    assert r["events_dropped"] > 0
    assert r["approaches"]["chronosmesh"]["f1"] == pytest.approx(1.0)
    assert r["reconstruction"]["gap_edges"] > 0


def test_metadata_loss_degrades_gracefully():
    r = run(metadata_loss_rate=0.3, num_events=1000)["runs"][0]
    f1 = r["approaches"]["chronosmesh"]["f1"]
    assert 0.5 < f1 < 1.0
    assert f1 >= r["approaches"]["declared_only"]["f1"] - 0.02


def test_duplicates_are_suppressed_and_reported():
    r = run(duplicate_rate=0.10)["runs"][0]
    assert r["deliveries_total"] > r["events_delivered_unique"]
    assert r["fault_tolerance"]["duplicates_suppressed"] >= r["events_duplicated"] - 1
    assert r["approaches"]["chronosmesh"]["f1"] == pytest.approx(1.0)
    assert r["anomalies"]["by_type"].get("DUPLICATE_EVENT", 0) > 0


def test_worker_crash_recovery_yields_identical_graph():
    r = run(num_events=1000, worker_failures=3, duplicate_rate=0.05)["runs"][0]
    ft = r["fault_tolerance"]
    assert ft["recoveries"] == 3 and ft["redelivered_messages"] > 0
    assert ft["state_consistent_after_recovery"] is True
    assert r["approaches"]["chronosmesh"]["f1"] == pytest.approx(1.0)


def test_repeats_aggregate_with_confidence_intervals_and_distinct_seeds():
    out = run(repeats=3, num_events=300)
    assert len(out["runs"]) == 3 and len({r["seed"] for r in out["runs"]}) == 3
    s = out["summary"]
    assert set(s["approaches"]) == set(APPROACHES)
    assert s["approaches"]["chronosmesh"]["f1"]["n"] == 3
    assert 0.0 <= s["recovery_rate"] <= 1.0 and s["all_recoveries_consistent"]
    assert s["performance"]["throughput_eps"]["mean"] > 0


def test_run_is_reproducible():
    cfg = ExperimentConfig(num_events=300, seed=99, duplicate_rate=0.05, missing_rate=0.02)
    a, b = run_single(cfg, 99), run_single(cfg, 99)
    assert a["approaches"] == b["approaches"] and a["anomalies"] == b["anomalies"]


def test_progress_callback_reports_monotonic_fractions():
    seen = []
    run_experiment(ExperimentConfig(num_events=100, repeats=2), progress=lambda f, m: seen.append(f))
    assert seen[-1] == 1.0 and all(0.0 <= f <= 1.0 for f in seen)


def test_retry_storms_are_detected_and_do_not_hurt_reconstruction():
    r = run(num_events=800, retry_rate=0.05, retry_burst=6)["runs"][0]
    assert r["anomalies"]["by_type"].get("RETRY_STORM", 0) >= 1
    assert r["approaches"]["chronosmesh"]["f1"] == pytest.approx(1.0)


def test_event_ordering_accuracy_separates_clock_drift_from_delivery_disorder():
    clean_clock = run(num_events=800, network_delay_ms=500, clock_drift_ms=0)["runs"][0]["concurrency"]
    drifting = run(num_events=800, network_delay_ms=500, clock_drift_ms=300)["runs"][0]["concurrency"]
    # arrival order is wrong about half the time whenever delivery is shuffled
    assert clean_clock["arrival_order"]["ordering_accuracy"] < 0.7
    # an accurate wall clock orders causal pairs well; drift destroys that
    assert clean_clock["wall_clock"]["ordering_accuracy"] > 0.95
    assert drifting["wall_clock"]["ordering_accuracy"] < clean_clock["wall_clock"]["ordering_accuracy"] - 0.05
    # logical clocks are immune to both
    assert clean_clock["chronosmesh"]["ordering_accuracy"] == pytest.approx(1.0)
    assert drifting["chronosmesh"]["ordering_accuracy"] == pytest.approx(1.0)


def test_late_event_recovery_and_duplicate_detection_rate():
    r = run(num_events=800, network_delay_ms=500, duplicate_rate=0.10)["runs"][0]
    assert r["late_edges"] > 50
    rec = r["late_event_recovery"]
    assert rec["chronosmesh"] == pytest.approx(1.0) and rec["arrival_order"] < 0.1
    assert rec["declared_only"] < rec["chronosmesh"]
    assert r["fault_tolerance"]["duplicate_detection_rate"] == pytest.approx(1.0)


def test_cross_region_delay_degrades_arrival_order_but_not_logical_clocks():
    near = run(num_events=1500, network_delay_ms=20, cross_region_delay_ms=0)["runs"][0]["concurrency"]
    far = run(num_events=1500, network_delay_ms=20, cross_region_delay_ms=1500)["runs"][0]["concurrency"]
    assert near["arrival_order"]["ordering_accuracy"] > 0.9
    assert far["arrival_order"]["ordering_accuracy"] < near["arrival_order"]["ordering_accuracy"] - 0.15
    assert near["chronosmesh"]["ordering_accuracy"] == pytest.approx(1.0)
    assert far["chronosmesh"]["ordering_accuracy"] == pytest.approx(1.0)
