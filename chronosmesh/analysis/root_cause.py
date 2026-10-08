from dataclasses import dataclass, field
from typing import Dict, List, Any
import networkx as nx

@dataclass
class RootCauseResult:
    failure_event_id: str
    root_causes: List[Dict[str, Any]] = field(default_factory=list)
    trace_paths: List[List[str]] = field(default_factory=list)

class RootCauseTracer:
    def trace(self, dag: nx.DiGraph, failure_event_id: str, max_depth: int = None) -> RootCauseResult:
        if failure_event_id not in dag:
            return RootCauseResult(failure_event_id)
        
        subgraph = self.get_ancestor_subgraph(dag, failure_event_id)
        
        # Identify root nodes in the subgraph (in-degree 0)
        root_causes = []
        for node in subgraph.nodes():
            if subgraph.in_degree(node) == 0:
                node_data = subgraph.nodes[node]
                # Calculate depth
                try:
                    path = nx.shortest_path(subgraph, source=node, target=failure_event_id)
                    depth = len(path) - 1
                except nx.NetworkXNoPath:
                    path = []
                    depth = 0
                    
                if max_depth is not None and depth > max_depth:
                    continue
                    
                root_causes.append({
                    "event_id": node,
                    "service_id": node_data.get("service_id", "unknown"),
                    "event_type": node_data.get("event_type", "unknown"),
                    "depth": depth,
                    "path": path,
                    "confidence": 1.0 # Basic confidence
                })
                
        # Find all paths
        trace_paths = []
        for rc in root_causes:
            paths = list(nx.all_simple_paths(subgraph, source=rc["event_id"], target=failure_event_id))
            trace_paths.extend(paths)
            
        return RootCauseResult(failure_event_id, root_causes, trace_paths)

    def find_critical_path(self, dag: nx.DiGraph, failure_event_id: str) -> List[str]:
        if failure_event_id not in dag:
            return []
        subgraph = self.get_ancestor_subgraph(dag, failure_event_id)
        if not subgraph.nodes():
            return []
            
        # Find node with longest path to failure
        try:
            longest_path = nx.dag_longest_path(subgraph)
            # Ensure it ends at failure_event_id
            if longest_path[-1] == failure_event_id:
                return longest_path
        except nx.NetworkXUnfeasible:
            pass
        return []

    def get_ancestor_subgraph(self, dag: nx.DiGraph, event_id: str) -> nx.DiGraph:
        if event_id not in dag:
            return nx.DiGraph()
        ancestors = nx.ancestors(dag, event_id)
        ancestors.add(event_id)
        return dag.subgraph(ancestors).copy()
