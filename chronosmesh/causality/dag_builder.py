from typing import List, Dict, Any
import networkx as nx

from chronosmesh.events.event import Event
from chronosmesh.causality.happens_before import HappensBeforeDetector
from chronosmesh.causality.transitive_reduction import compute_transitive_reduction, incremental_transitive_reduction

class CausalDAGBuilder:
    def __init__(self):
        self.dag = nx.DiGraph()
        self.detector = HappensBeforeDetector()
        self.events_map = {}

    def build(self, events: List[Event]) -> nx.DiGraph:
        self.dag = nx.DiGraph()
        self.events_map = {e.event_id: e for e in events}
        
        for e in events:
            self._add_node(e)
            
        for i in range(len(events)):
            for j in range(len(events)):
                if i != j:
                    rel = self.detector.detect(events[i], events[j])
                    if rel == rel.HAPPENS_BEFORE:
                        self.dag.add_edge(events[i].event_id, events[j].event_id)
                        
        self.dag = compute_transitive_reduction(self.dag)
        return self.dag

    def build_incremental(self, event: Event) -> nx.DiGraph:
        self.events_map[event.event_id] = event
        self._add_node(event)

        # Fast-path: When explicit parent_event_ids are declared
        if event.parent_event_ids:
            for pid in event.parent_event_ids:
                if pid in self.events_map:
                    self.dag.add_edge(pid, event.event_id)
            self.dag = incremental_transitive_reduction(self.dag, event.event_id)
            return self.dag

        # Fallback: Happens-before detection against active nodes
        for node in list(self.dag.nodes):
            if node != event.event_id:
                other = self.events_map[node]
                rel = self.detector.detect(other, event)
                if rel == rel.HAPPENS_BEFORE:
                    self.dag.add_edge(node, event.event_id)
                elif rel == rel.HAPPENS_AFTER:
                    self.dag.add_edge(event.event_id, node)

        self.dag = incremental_transitive_reduction(self.dag, event.event_id)
        return self.dag

    def _add_node(self, event: Event):
        self.dag.add_node(
            event.event_id,
            event_id=event.event_id,
            service_id=event.service_id,
            event_type=event.event_type,
            timestamp_ms=event.timestamp_ms,
            lamport_ts=event.lamport_ts,
            vector_clock=event.vector_clock,
            parent_event_ids=event.parent_event_ids,
            metadata=event.metadata.to_dict()
        )

    def get_dag(self) -> nx.DiGraph:
        return self.dag

    def get_roots(self) -> List[str]:
        return [n for n, d in self.dag.in_degree() if d == 0]

    def get_leaves(self) -> List[str]:
        return [n for n, d in self.dag.out_degree() if d == 0]

    def get_ancestors(self, event_id: str) -> List[str]:
        return list(nx.ancestors(self.dag, event_id))

    def get_descendants(self, event_id: str) -> List[str]:
        return list(nx.descendants(self.dag, event_id))

    def get_immediate_parents(self, event_id: str) -> List[str]:
        return list(self.dag.predecessors(event_id))

    def get_immediate_children(self, event_id: str) -> List[str]:
        return list(self.dag.successors(event_id))

    def topological_order(self) -> List[str]:
        return list(nx.topological_sort(self.dag))

    def to_dict(self) -> Dict[str, Any]:
        return nx.node_link_data(self.dag)

    def from_dict(self, data: Dict[str, Any]):
        self.dag = nx.node_link_graph(data)
