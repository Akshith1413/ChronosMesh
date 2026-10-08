import pytest
import networkx as nx
from chronosmesh.analysis.anomaly import CausalAnomalyDetector

def test_detect_time_inversion():
    detector = CausalAnomalyDetector(clock_skew_tolerance_ms=10.0)
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=200)
    dag.add_node("2", event_id="2", timestamp_ms=100)
    dag.add_edge("1", "2")
    res = detector.detect_time_inversions(dag)
    assert len(res) == 1
    assert res[0].anomaly_type == "TIME_INVERSION"

def test_no_anomalies_in_valid_dag():
    detector = CausalAnomalyDetector()
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=100)
    dag.add_node("2", event_id="2", timestamp_ms=200)
    dag.add_edge("1", "2")
    res = detector.detect_all(dag)
    assert len(res) == 0

def test_detect_duplicate_events():
    detector = CausalAnomalyDetector()
    events = [{"event_id": "1"}, {"event_id": "1"}]
    res = detector.detect_duplicate_events(events)
    assert len(res) == 1
    assert res[0].anomaly_type == "DUPLICATE_EVENT"

def test_detect_vector_clock_gaps():
    detector = CausalAnomalyDetector()
    res = detector.detect_vector_clock_gaps([])
    assert isinstance(res, list)

def test_detect_all_aggregates_results():
    detector = CausalAnomalyDetector()
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=200)
    dag.add_node("2", event_id="2", timestamp_ms=100)
    dag.add_edge("1", "2")
    dag.add_edge("2", "1")  # Cycle
    res = detector.detect_all(dag)
    types = [r.anomaly_type for r in res]
    assert "TIME_INVERSION" in types
    assert "CYCLE" in types

def test_severity_levels():
    detector = CausalAnomalyDetector()
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=200)
    dag.add_node("2", event_id="2", timestamp_ms=100)
    dag.add_edge("1", "2")
    dag.add_edge("2", "1")
    res = detector.detect_all(dag)
    severities = [r.severity for r in res]
    assert "WARNING" in severities
    assert "CRITICAL" in severities
