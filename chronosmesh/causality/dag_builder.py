from collections import defaultdict
from typing import List, Dict, Any, Set
import networkx as nx

from chronosmesh.events.event import Event
from chronosmesh.causality.happens_before import HappensBeforeDetector
from chronosmesh.causality.transitive_reduction import compute_transitive_reduction, incremental_transitive_reduction

class CausalDAGBuilder:
    def __init__(self):
        self.dag = nx.DiGraph()
        self.detector = HappensBeforeDetector()
        self.events_map = {}
        # Declared parents that have not been observed yet: parent_id -> {waiting child ids}.
        # Nothing is invented for them; the edge is added if/when the parent shows up.
        self.unresolved_children: Dict[str, Set[str]] = defaultdict(set)
        # Event ids delivered more than once (ignored after the first delivery).
        self.duplicates: List[str] = []
        # Declared edges rejected because they would have closed a cycle.
        self.rejected_edges: List[tuple] = []

    def build(self, events: List[Event]) -> nx.DiGraph:
        self.dag = nx.DiGraph()
        self.unresolved_children = defaultdict(set)
        self.duplicates = []
        self.rejected_edges = []
        self.events_map = {}
        for e in events:
            if e.event_id in self.events_map:
                self.duplicates.append(e.event_id)
            else:
                self.events_map[e.event_id] = e
        events = list(self.events_map.values())

        for e in events:
            self._add_node(e)
            for pid in e.parent_event_ids:
                if pid not in self.events_map:
                    self.unresolved_children[pid].add(e.event_id)
            
        for i in range(len(events)):
            for j in range(len(events)):
                if i != j:
                    rel = self.detector.detect(events[i], events[j])
                    if rel == rel.HAPPENS_BEFORE:
                        self.dag.add_edge(events[i].event_id, events[j].event_id)
                        
        self.dag = compute_transitive_reduction(self.dag)
        for e in events:
            self._refresh_unresolved(e.event_id)
        return self.dag

    def build_incremental(self, event: Event) -> nx.DiGraph:
        # Idempotent: a re-delivered event never alters the graph.
        if event.event_id in self.events_map:
            self.duplicates.append(event.event_id)
            return self.dag

        self.events_map[event.event_id] = event
        self._add_node(event)

        # Late-arriving parent: link every child that was waiting for this event.
        for child_id in sorted(self.unresolved_children.pop(event.event_id, set())):
            if child_id in self.dag and self._add_edge_safe(event.event_id, child_id):
                self._refresh_unresolved(child_id)
                self.dag = incremental_transitive_reduction(self.dag, child_id)

        # Fast-path: When explicit parent_event_ids are declared
        if event.parent_event_ids:
            for pid in event.parent_event_ids:
                if pid in self.events_map:
                    self._add_edge_safe(pid, event.event_id)
                else:
                    self.unresolved_children[pid].add(event.event_id)
            self._refresh_unresolved(event.event_id)
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

    # ── Unresolved-dependency bookkeeping ───────────────────────────────────
    def _add_edge_safe(self, u: str, v: str) -> bool:
        """Add u -> v unless it would close a cycle (bad metadata); record rejections."""
        if u == v or (v in self.dag and u in self.dag and nx.has_path(self.dag, v, u)):
            self.rejected_edges.append((u, v))
            return False
        self.dag.add_edge(u, v, explicit=True)
        return True

    def _refresh_unresolved(self, event_id: str) -> None:
        event = self.events_map[event_id]
        missing = [p for p in event.parent_event_ids if p not in self.events_map]
        self.dag.nodes[event_id]["unresolved_parents"] = missing

    def get_unresolved_parents(self) -> Dict[str, List[str]]:
        """Missing parent id -> ids of the events still waiting on it."""
        return {pid: sorted(children) for pid, children in self.unresolved_children.items() if children}

    def unresolved_count(self) -> int:
        return sum(len(c) for c in self.unresolved_children.values())

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
            arrival_time_ms=event.arrival_time_ms,
            payload=event.payload,
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
