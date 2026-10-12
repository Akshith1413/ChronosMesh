import logging
from typing import Dict, Any, List, Optional, Callable

import networkx as nx

from chronosmesh.analysis.anomaly import AnomalyReport, CausalAnomalyDetector
from chronosmesh.analysis.confidence import ConfidenceScorer
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.events.event import Event

logger = logging.getLogger(__name__)

LOW_CONFIDENCE_THRESHOLD = 0.7


class StreamProcessor:
    """Stateful processor that incrementally builds a causal DAG.

    For every event it updates the DAG, runs the anomaly checks that are local to the event
    (duplicate delivery, unresolved parents, clock/causal violations on its edges, late parents)
    and scores the confidence of its incoming edges.
    """

    def __init__(
        self,
        buffer_policy: Optional[Any] = None,
        enable_anomaly_detection: bool = True,
        enable_confidence_scoring: bool = True,
        anomaly_callback: Optional[Callable] = None,
        event_callback: Optional[Callable] = None,
        detector: Optional[CausalAnomalyDetector] = None,
        scorer: Optional[ConfidenceScorer] = None,
    ) -> None:
        self.buffer_policy = buffer_policy
        self.enable_anomaly_detection = enable_anomaly_detection
        self.enable_confidence_scoring = enable_confidence_scoring
        self.anomaly_callback = anomaly_callback
        self.event_callback = event_callback
        self.detector = detector or CausalAnomalyDetector()
        self.scorer = scorer or ConfidenceScorer()

        self._anomalies: List[Dict[str, Any]] = []
        self._stats = self._fresh_stats()

    @staticmethod
    def _fresh_stats() -> Dict[str, int]:
        return {
            "processed_events": 0,
            "detected_anomalies": 0,
            "edges_added": 0,
            "low_confidence_edges": 0,
            "duplicates": 0,
        }

    def _get_builder(self) -> CausalDAGBuilder:
        if not hasattr(self, "_builder"):
            self._builder = CausalDAGBuilder()
        return self._builder

    # ── Local anomaly checks ────────────────────────────────────────────────────
    def _local_anomalies(self, event: Event, builder: CausalDAGBuilder, duplicate: bool) -> List[AnomalyReport]:
        found: List[AnomalyReport] = []
        if duplicate:
            found.append(AnomalyReport(
                "DUPLICATE_EVENT", "WARNING", event.event_id, None,
                f"Duplicate event ID detected: {event.event_id}", {}))
            return found

        known = builder.events_map
        parents = [known[p] for p in event.parent_event_ids if p in known]
        children = [known[c] for c in builder.get_dag().successors(event.event_id)] if event.event_id in builder.get_dag() else []
        neighbourhood = [event] + parents + children

        found.extend(self.detector.detect_unresolved_parents(neighbourhood)
                     if any(p not in known for p in event.parent_event_ids) else [])
        found.extend(self.detector.detect_orphans([event]) if event.parent_event_ids and not parents else [])
        found.extend(self.detector.detect_causal_violations(neighbourhood))
        found.extend(self.detector.detect_late_arrivals(neighbourhood))

        sub = nx.DiGraph()
        for e in neighbourhood:
            sub.add_node(e.event_id, timestamp_ms=e.timestamp_ms)
        for p in parents:
            sub.add_edge(p.event_id, event.event_id)
        for c in children:
            sub.add_edge(event.event_id, c.event_id)
        found.extend(self.detector.detect_time_inversions(sub))

        # Keep only anomalies that involve this event so each is reported once.
        return [a for a in found if event.event_id in (a.source_event_id, a.target_event_id)]

    def process_event(self, event: Event) -> Dict[str, Any]:
        """Process one event through DAG -> anomaly check -> confidence score."""
        self._stats["processed_events"] += 1

        builder = self._get_builder()
        dup_before = len(builder.duplicates)
        edges_before = builder.get_dag().number_of_edges()
        builder.build_incremental(event)
        duplicate = len(builder.duplicates) > dup_before
        dag = builder.get_dag()
        self._stats["duplicates"] += int(duplicate)
        self._stats["edges_added"] += max(0, dag.number_of_edges() - edges_before)

        anomalies: List[Dict[str, Any]] = []
        if self.enable_anomaly_detection:
            try:
                for report in self._local_anomalies(event, builder, duplicate):
                    d = report.to_dict()
                    anomalies.append(d)
                    self._stats["detected_anomalies"] += 1
                    if self.anomaly_callback:
                        self.anomaly_callback(d)
            except Exception as exc:  # detection must never break ingestion
                logger.warning("Anomaly detection failed for %s: %s", event.event_id, exc)
            self._anomalies.extend(anomalies)

        low_confidence: List[Dict[str, Any]] = []
        if self.enable_confidence_scoring and not duplicate:
            for pid in event.parent_event_ids:
                parent = builder.events_map.get(pid)
                if parent is None:
                    continue
                has_edge = dag.has_edge(pid, event.event_id)
                score = self.scorer.score_edge(parent.to_dict(), event.to_dict(), has_explicit_link=has_edge)
                if score.confidence < LOW_CONFIDENCE_THRESHOLD:
                    low_confidence.append({"source": pid, "target": event.event_id,
                                           "confidence": score.confidence, "method": score.method})
                    self._stats["low_confidence_edges"] += 1

        result = {
            "emitted_events": [event],
            "dag_nodes": dag.number_of_nodes(),
            "dag_edges": dag.number_of_edges(),
            "anomalies": anomalies,
            "low_confidence_edges": low_confidence,
            "duplicate": duplicate,
            "unresolved_parents": builder.unresolved_count(),
        }

        if self.event_callback:
            self.event_callback(result)

        return result

    def process_batch(self, events: List[Event]) -> Dict[str, Any]:
        """Process a batch of events."""
        results: Dict[str, Any] = {
            "emitted_events": [],
            "anomalies": [],
            "low_confidence_edges": [],
        }
        for event in events:
            res = self.process_event(event)
            results["emitted_events"].extend(res.get("emitted_events", []))
            results["anomalies"].extend(res.get("anomalies", []))
            results["low_confidence_edges"].extend(res.get("low_confidence_edges", []))

        dag = self._get_builder().get_dag()
        results["dag_nodes"] = dag.number_of_nodes()
        results["dag_edges"] = dag.number_of_edges()
        return results

    def get_dag(self):
        return self._get_builder().get_dag()

    def get_anomalies(self) -> List[Dict[str, Any]]:
        return self._anomalies

    def get_statistics(self) -> Dict[str, Any]:
        return self._stats

    def flush(self) -> None:
        pass

    def reset(self) -> None:
        if hasattr(self, "_builder"):
            del self._builder
        self._anomalies.clear()
        self._stats = self._fresh_stats()
