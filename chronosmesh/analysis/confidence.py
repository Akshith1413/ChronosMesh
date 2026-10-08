import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

@dataclass
class EdgeConfidence:
    source_id: str
    target_id: str
    confidence: float
    method: str
    uncertainty_ms: float

class ConfidenceScorer:
    def __init__(self, default_uncertainty_ms: float = 5.0, region_uncertainties: Dict[Tuple[str, str], float] = None):
        self.default_uncertainty_ms = default_uncertainty_ms
        self.region_uncertainties = region_uncertainties or {}

    def score_edge(self, source_event: Dict[str, Any], target_event: Dict[str, Any], has_explicit_link: bool = False) -> EdgeConfidence:
        source_id = source_event.get("event_id")
        target_id = target_event.get("event_id")

        # Explicit link
        if has_explicit_link:
            return EdgeConfidence(source_id, target_id, 1.0, "explicit", 0.0)

        # Vector clock check
        vc_source = source_event.get("vector_clock", {})
        vc_target = target_event.get("vector_clock", {})
        if vc_source and vc_target:
            # Check if source happens before target using vector clock
            is_less_or_equal = all(vc_source.get(k, 0) <= vc_target.get(k, 0) for k in vc_source)
            is_strictly_less = any(vc_source.get(k, 0) < vc_target.get(k, 0) for k in vc_target if vc_target.get(k, 0) > 0) or any(vc_source.get(k, 0) < vc_target.get(k, 0) for k in vc_source)
            if is_less_or_equal and is_strictly_less:
                return EdgeConfidence(source_id, target_id, 1.0, "vector_clock", 0.0)

        # Physical time check
        t_a = source_event.get("timestamp_ms", 0.0)
        t_b = target_event.get("timestamp_ms", 0.0)

        # Get uncertainties
        def get_uncertainty(ev):
            meta = ev.get("metadata")
            if hasattr(meta, "clock_uncertainty_ms"):
                return meta.clock_uncertainty_ms
            elif isinstance(meta, dict):
                return meta.get("clock_uncertainty_ms", self.default_uncertainty_ms)
            return self.default_uncertainty_ms
        
        unc_a = get_uncertainty(source_event)
        unc_b = get_uncertainty(target_event)

        # Check region uncertainty override
        def get_region(ev):
            meta = ev.get("metadata")
            if hasattr(meta, "region"):
                return meta.region
            elif isinstance(meta, dict):
                return meta.get("region", "unknown")
            return "unknown"

        reg_a = get_region(source_event)
        reg_b = get_region(target_event)
        pair = (reg_a, reg_b)
        if pair in self.region_uncertainties:
            unc_a = self.region_uncertainties[pair]
            unc_b = self.region_uncertainties[pair]

        # Calculate CDF
        sigma_a = unc_a / 3.0
        sigma_b = unc_b / 3.0
        variance_sum = sigma_a**2 + sigma_b**2
        
        if variance_sum == 0:
            prob = 1.0 if t_a < t_b else (0.5 if t_a == t_b else 0.0)
        else:
            x = (t_b - t_a) / math.sqrt(variance_sum)
            prob = 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        return EdgeConfidence(source_id, target_id, prob, "physical_time", unc_a + unc_b)

    def score_all_edges(self, dag: Any) -> Dict[Tuple[str, str], EdgeConfidence]:
        results = {}
        for u, v in dag.edges():
            u_data = dag.nodes[u]
            v_data = dag.nodes[v]
            # Assumes edge data might contain explicit link info
            edge_data = dag.get_edge_data(u, v, default={})
            has_explicit = edge_data.get("explicit", False)
            results[(u, v)] = self.score_edge(u_data, v_data, has_explicit)
        return results

    def get_low_confidence_edges(self, dag: Any, threshold: float = 0.7) -> List[EdgeConfidence]:
        scores = self.score_all_edges(dag)
        return [score for score in scores.values() if score.confidence < threshold]
