from typing import List, Tuple, Set
import networkx as nx

from chronosmesh.events.event import Event
from chronosmesh.causality.happens_before import HappensBeforeDetector
from chronosmesh.clocks.base import CausalRelation

class ConcurrencyDetector:
    def __init__(self):
        self.detector = HappensBeforeDetector()

    def is_concurrent(self, event_a: Event, event_b: Event) -> bool:
        return self.detector.detect(event_a, event_b) == CausalRelation.CONCURRENT

    def detect_concurrent_pairs(self, events: List[Event]) -> List[Tuple[str, str]]:
        pairs = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                if self.is_concurrent(events[i], events[j]):
                    pairs.append((events[i].event_id, events[j].event_id))
        return pairs

    def find_concurrent_groups(self, events: List[Event]) -> List[Set[str]]:
        G = nx.Graph()
        for e in events:
            G.add_node(e.event_id)
        
        pairs = self.detect_concurrent_pairs(events)
        for a, b in pairs:
            G.add_edge(a, b)
            
        cliques = list(nx.find_cliques(G))
        return [set(c) for c in cliques if len(c) > 1]
