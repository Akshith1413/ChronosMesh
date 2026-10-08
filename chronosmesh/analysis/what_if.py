from dataclasses import dataclass, field
from typing import Dict, List, Set, Any
import networkx as nx

@dataclass
class WhatIfResult:
    removed_event_id: str
    invalidated_events: Set[str] = field(default_factory=set)
    surviving_events: Set[str] = field(default_factory=set)
    blast_radius: float = 0.0
    affected_services: Set[str] = field(default_factory=set)
    cascade_depth: int = 0

class WhatIfSimulator:
    def simulate_removal(self, dag: nx.DiGraph, event_id: str) -> WhatIfResult:
        if event_id not in dag:
            return WhatIfResult(event_id)
            
        invalidated = {event_id}
        surviving = set()
        affected_services = {dag.nodes[event_id].get("service_id", "unknown")}
        
        # Traverse descendants in topological order
        descendants = list(nx.descendants(dag, event_id))
        subgraph = dag.subgraph(descendants).copy()
        
        try:
            topo_order = list(nx.topological_sort(subgraph))
        except nx.NetworkXUnfeasible:
            topo_order = descendants
            
        max_depth = 0
        depths = {event_id: 0}
            
        for node in topo_order:
            parents = list(dag.predecessors(node))
            if all(p in invalidated for p in parents):
                invalidated.add(node)
                affected_services.add(dag.nodes[node].get("service_id", "unknown"))
                node_depth = max(depths.get(p, 0) for p in parents) + 1
                depths[node] = node_depth
                max_depth = max(max_depth, node_depth)
            else:
                surviving.add(node)
                
        blast_radius = len(invalidated) / max(1, len(dag.nodes()))
        
        # surviving shouldn't include nodes that weren't descendants at all?
        # Based on specs: "event survives if at least one parent survives" 
        # This applies to descendants. Other nodes obviously survive.
        # We'll just include descendants that survive in the `surviving_events` set
        
        return WhatIfResult(
            removed_event_id=event_id,
            invalidated_events=invalidated,
            surviving_events=surviving,
            blast_radius=blast_radius,
            affected_services=affected_services,
            cascade_depth=max_depth
        )

    def simulate_delay(self, dag: nx.DiGraph, event_id: str, delay_ms: float) -> Dict[str, Any]:
        return {}

    def compare_scenarios(self, dag: nx.DiGraph, event_ids: List[str]) -> List[WhatIfResult]:
        return [self.simulate_removal(dag, e) for e in event_ids]
