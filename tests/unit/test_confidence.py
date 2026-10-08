import pytest
import networkx as nx
from chronosmesh.analysis.confidence import ConfidenceScorer

def test_explicit_link_confidence_is_one():
    scorer = ConfidenceScorer()
    ev1 = {"event_id": "1", "timestamp_ms": 100}
    ev2 = {"event_id": "2", "timestamp_ms": 110}
    res = scorer.score_edge(ev1, ev2, has_explicit_link=True)
    assert res.confidence == 1.0
    assert res.method == "explicit"

def test_vector_clock_confirmed_confidence():
    scorer = ConfidenceScorer()
    ev1 = {"event_id": "1", "vector_clock": {"A": 1}}
    ev2 = {"event_id": "2", "vector_clock": {"A": 2}}
    res = scorer.score_edge(ev1, ev2)
    assert res.confidence == 1.0
    assert res.method == "vector_clock"

def test_well_separated_timestamps_high_confidence():
    scorer = ConfidenceScorer()
    ev1 = {"event_id": "1", "timestamp_ms": 100, "metadata": {"clock_uncertainty_ms": 5}}
    ev2 = {"event_id": "2", "timestamp_ms": 200, "metadata": {"clock_uncertainty_ms": 5}}
    res = scorer.score_edge(ev1, ev2)
    assert res.confidence > 0.99
    assert res.method == "physical_time"

def test_overlapping_timestamps_lower_confidence():
    scorer = ConfidenceScorer()
    ev1 = {"event_id": "1", "timestamp_ms": 100, "metadata": {"clock_uncertainty_ms": 10}}
    ev2 = {"event_id": "2", "timestamp_ms": 101, "metadata": {"clock_uncertainty_ms": 10}}
    res = scorer.score_edge(ev1, ev2)
    assert 0.5 < res.confidence < 0.9

def test_reversed_timestamps_near_zero_confidence():
    scorer = ConfidenceScorer()
    ev1 = {"event_id": "1", "timestamp_ms": 200, "metadata": {"clock_uncertainty_ms": 5}}
    ev2 = {"event_id": "2", "timestamp_ms": 100, "metadata": {"clock_uncertainty_ms": 5}}
    res = scorer.score_edge(ev1, ev2)
    assert res.confidence < 0.01

def test_cross_region_uncertainty():
    scorer = ConfidenceScorer(region_uncertainties={("aws-1", "aws-2"): 20.0})
    ev1 = {"event_id": "1", "timestamp_ms": 100, "metadata": {"region": "aws-1"}}
    ev2 = {"event_id": "2", "timestamp_ms": 105, "metadata": {"region": "aws-2"}}
    res = scorer.score_edge(ev1, ev2)
    assert res.uncertainty_ms == 40.0

def test_score_all_edges():
    scorer = ConfidenceScorer()
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=100)
    dag.add_node("2", event_id="2", timestamp_ms=200)
    dag.add_edge("1", "2")
    res = scorer.score_all_edges(dag)
    assert len(res) == 1
    assert res[("1", "2")].confidence > 0.9

def test_low_confidence_edge_detection():
    scorer = ConfidenceScorer()
    dag = nx.DiGraph()
    dag.add_node("1", event_id="1", timestamp_ms=100)
    dag.add_node("2", event_id="2", timestamp_ms=90)
    dag.add_edge("1", "2")
    res = scorer.get_low_confidence_edges(dag)
    assert len(res) == 1
