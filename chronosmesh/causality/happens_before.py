from enum import Enum
from typing import List, Tuple, Set, Dict

from chronosmesh.clocks.base import CausalRelation
from chronosmesh.events.event import Event

class HappensBeforeDetector:
    def detect(self, event_a: Event, event_b: Event) -> CausalRelation:
        if event_a.event_id == event_b.event_id:
            return CausalRelation.EQUAL

        a_vc = event_a.vector_clock
        b_vc = event_b.vector_clock

        if a_vc and b_vc:
            return self._compare_vector_clocks(a_vc, b_vc)
        
        return self._compare_lamport(event_a, event_b)

    def _compare_vector_clocks(self, vc_a: Dict[str, int], vc_b: Dict[str, int]) -> CausalRelation:
        keys = set(vc_a.keys()).union(set(vc_b.keys()))
        a_less_equal = True
        b_less_equal = True

        for k in keys:
            val_a = vc_a.get(k, 0)
            val_b = vc_b.get(k, 0)
            if val_a > val_b:
                a_less_equal = False
            if val_b > val_a:
                b_less_equal = False

        if a_less_equal and not b_less_equal:
            return CausalRelation.HAPPENS_BEFORE
        elif b_less_equal and not a_less_equal:
            return CausalRelation.HAPPENS_AFTER
        elif a_less_equal and b_less_equal:
            return CausalRelation.EQUAL
        else:
            return CausalRelation.CONCURRENT

    def _compare_lamport(self, event_a: Event, event_b: Event) -> CausalRelation:
        if event_a.lamport_ts < event_b.lamport_ts:
            return CausalRelation.HAPPENS_BEFORE
        elif event_a.lamport_ts > event_b.lamport_ts:
            return CausalRelation.HAPPENS_AFTER
        else:
            if event_a.event_id < event_b.event_id:
                return CausalRelation.HAPPENS_BEFORE
            elif event_a.event_id > event_b.event_id:
                return CausalRelation.HAPPENS_AFTER
            return CausalRelation.EQUAL

    def detect_all(self, events: List[Event]) -> List[Tuple[str, str, CausalRelation]]:
        results = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                rel = self.detect(events[i], events[j])
                results.append((events[i].event_id, events[j].event_id, rel))
        return results

    def build_relation_set(self, events: List[Event]) -> Set[Tuple[str, str]]:
        rel_set = set()
        for i in range(len(events)):
            for j in range(len(events)):
                if i != j:
                    if self.detect(events[i], events[j]) == CausalRelation.HAPPENS_BEFORE:
                        rel_set.add((events[i].event_id, events[j].event_id))
        return rel_set
