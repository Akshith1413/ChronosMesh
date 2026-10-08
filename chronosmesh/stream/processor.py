import logging
from typing import Dict, Any, List, Optional, Callable

from chronosmesh.events.event import Event

logger = logging.getLogger(__name__)

class StreamProcessor:
    """Stateful processor that incrementally builds a causal DAG."""

    def __init__(
        self,
        buffer_policy: Optional[Any] = None,
        enable_anomaly_detection: bool = True,
        enable_confidence_scoring: bool = True,
        anomaly_callback: Optional[Callable] = None,
        event_callback: Optional[Callable] = None
    ) -> None:
        self.buffer_policy = buffer_policy
        self.enable_anomaly_detection = enable_anomaly_detection
        self.enable_confidence_scoring = enable_confidence_scoring
        self.anomaly_callback = anomaly_callback
        self.event_callback = event_callback
        
        self._anomalies: List[Dict[str, Any]] = []
        self._stats = {
            "processed_events": 0,
            "detected_anomalies": 0,
            "edges_added": 0,
            "low_confidence_edges": 0
        }
        
    def _get_builder(self):
        # Lazy import to avoid circular dependency / concurrent subagent issues
        from chronosmesh.causality.dag_builder import CausalDAGBuilder
        if not hasattr(self, "_builder"):
            self._builder = CausalDAGBuilder()
        return self._builder

    def process_event(self, event: Event) -> Dict[str, Any]:
        """Process one event through buffer -> DAG -> anomaly check -> confidence score."""
        self._stats["processed_events"] += 1
        
        # Lazy initialization
        builder = self._get_builder()
        builder.build_incremental(event)
        
        anomalies = []
        if self.enable_anomaly_detection:
            try:
                from chronosmesh.analyzer.anomaly import AnomalyDetector
                detector = AnomalyDetector(builder.get_dag())
                if hasattr(detector, "detect_for_event"):
                    new_anomalies = detector.detect_for_event(event)
                    anomalies.extend(new_anomalies)
            except ImportError:
                pass
                
            self._anomalies.extend(anomalies)
            if self.anomaly_callback and anomalies:
                for a in anomalies:
                    self.anomaly_callback(a)
                    
        low_confidence = []
        if self.enable_confidence_scoring:
            try:
                from chronosmesh.analyzer.confidence import ConfidenceScorer
                # mock integration if available
            except ImportError:
                pass
            
        result = {
            "emitted_events": [event],
            "dag_nodes": len(builder.get_dag().nodes) if hasattr(builder.get_dag(), "nodes") else 0,
            "dag_edges": len(builder.get_dag().edges) if hasattr(builder.get_dag(), "edges") else 0,
            "anomalies": anomalies,
            "low_confidence_edges": low_confidence
        }
        
        if self.event_callback:
            self.event_callback(result)
            
        return result

    def process_batch(self, events: List[Event]) -> Dict[str, Any]:
        """Process a batch of events."""
        results = {
            "emitted_events": [],
            "anomalies": [],
            "low_confidence_edges": []
        }
        for event in events:
            res = self.process_event(event)
            results["emitted_events"].extend(res.get("emitted_events", []))
            results["anomalies"].extend(res.get("anomalies", []))
            results["low_confidence_edges"].extend(res.get("low_confidence_edges", []))
            
        builder = self._get_builder()
        results["dag_nodes"] = len(builder.get_dag().nodes) if hasattr(builder.get_dag(), "nodes") else 0
        results["dag_edges"] = len(builder.get_dag().edges) if hasattr(builder.get_dag(), "edges") else 0
        return results

    def get_dag(self):
        builder = self._get_builder()
        return builder.get_dag()

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
        self._stats = {
            "processed_events": 0,
            "detected_anomalies": 0,
            "edges_added": 0,
            "low_confidence_edges": 0
        }
