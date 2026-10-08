from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import networkx as nx

@dataclass
class AnomalyReport:
    anomaly_type: str
    severity: str
    source_event_id: str
    target_event_id: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

class CausalAnomalyDetector:
    def __init__(self, clock_skew_tolerance_ms: float = 50.0, max_clock_drift_ms: float = 500.0):
        self.clock_skew_tolerance_ms = clock_skew_tolerance_ms
        self.max_clock_drift_ms = max_clock_drift_ms

    def detect_all(self, dag: nx.DiGraph, events: Optional[List[Any]] = None) -> List[AnomalyReport]:
        if events is None:
            events = [dag.nodes[n] for n in dag.nodes()]
        
        anomalies = []
        anomalies.extend(self.detect_cycles(dag))
        anomalies.extend(self.detect_time_inversions(dag))
        anomalies.extend(self.detect_vector_clock_gaps(events))
        anomalies.extend(self.detect_clock_drift(events))
        anomalies.extend(self.detect_duplicate_events(events))
        anomalies.extend(self.detect_concurrent_mutations(dag, events))
        return anomalies

    def detect_cycles(self, dag: nx.DiGraph) -> List[AnomalyReport]:
        anomalies = []
        try:
            cycles = list(nx.simple_cycles(dag))
            for cycle in cycles:
                anomalies.append(AnomalyReport(
                    anomaly_type="CYCLE",
                    severity="CRITICAL",
                    source_event_id=cycle[0],
                    target_event_id=cycle[-1],
                    description="Cycle detected in causal graph",
                    details={"cycle": cycle}
                ))
        except nx.NetworkXNoCycle:
            pass
        return anomalies

    def detect_time_inversions(self, dag: nx.DiGraph) -> List[AnomalyReport]:
        anomalies = []
        for u, v in dag.edges():
            u_ts = dag.nodes[u].get("timestamp_ms", 0.0)
            v_ts = dag.nodes[v].get("timestamp_ms", 0.0)
            if u_ts > v_ts + self.clock_skew_tolerance_ms:
                anomalies.append(AnomalyReport(
                    anomaly_type="TIME_INVERSION",
                    severity="WARNING",
                    source_event_id=u,
                    target_event_id=v,
                    description="Causal child has older physical timestamp",
                    details={"parent_ts": u_ts, "child_ts": v_ts, "diff": u_ts - v_ts}
                ))
        return anomalies

    def detect_vector_clock_gaps(self, events: List[Any]) -> List[AnomalyReport]:
        anomalies = []
        # Basic implementation, can be expanded
        return anomalies

    def detect_clock_drift(self, events: List[Any]) -> List[AnomalyReport]:
        anomalies = []
        return anomalies

    def detect_duplicate_events(self, events: List[Any]) -> List[AnomalyReport]:
        anomalies = []
        seen = set()
        for ev in events:
            ev_id = getattr(ev, "event_id", None) or (ev.get("event_id") if isinstance(ev, dict) else None)
            if ev_id is None:
                continue
            if ev_id in seen:
                anomalies.append(AnomalyReport(
                    anomaly_type="DUPLICATE_EVENT",
                    severity="WARNING",
                    source_event_id=ev_id,
                    target_event_id=None,
                    description=f"Duplicate event ID detected: {ev_id}",
                    details={}
                ))
            seen.add(ev_id)
        return anomalies

    def detect_concurrent_mutations(self, dag: nx.DiGraph, events: List[Any]) -> List[AnomalyReport]:
        anomalies = []
        return anomalies
