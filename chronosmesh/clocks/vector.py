import copy
from typing import Any, Dict
from chronosmesh.clocks.base import ClockStrategy, CausalRelation

class VectorClock(ClockStrategy):
    def __init__(self, node_id: str, **kwargs: Any) -> None:
        self._node_id = node_id
        self._clock: Dict[str, int] = {node_id: 0}

    @property
    def node_id(self) -> str:
        return self._node_id

    def tick(self) -> Dict[str, int]:
        self._clock[self._node_id] = self._clock.get(self._node_id, 0) + 1
        return self.current_timestamp()

    def send(self) -> Dict[str, int]:
        self._clock[self._node_id] = self._clock.get(self._node_id, 0) + 1
        return self.current_timestamp()

    def receive(self, remote_timestamp: Dict[str, int]) -> Dict[str, int]:
        for node, counter in remote_timestamp.items():
            self._clock[node] = max(self._clock.get(node, 0), counter)
        self._clock[self._node_id] = self._clock.get(self._node_id, 0) + 1
        return self.current_timestamp()

    @staticmethod
    def compare(v1: Dict[str, int], v2: Dict[str, int]) -> CausalRelation:
        if v1 == v2:
            return CausalRelation.EQUAL
        
        v1_le_v2 = True
        v2_le_v1 = True
        
        all_keys = set(v1.keys()).union(v2.keys())
        for k in all_keys:
            val1 = v1.get(k, 0)
            val2 = v2.get(k, 0)
            if val1 > val2:
                v1_le_v2 = False
            if val2 > val1:
                v2_le_v1 = False
                
        if v1_le_v2 and not v2_le_v1:
            return CausalRelation.HAPPENS_BEFORE
        elif v2_le_v1 and not v1_le_v2:
            return CausalRelation.HAPPENS_AFTER
        else:
            return CausalRelation.CONCURRENT

    def current_timestamp(self) -> Dict[str, int]:
        return self._clock.copy()

    def merge(self, other_vector: Dict[str, int]) -> None:
        for node, counter in other_vector.items():
            self._clock[node] = max(self._clock.get(node, 0), counter)

    @staticmethod
    def dominates(v1: Dict[str, int], v2: Dict[str, int]) -> bool:
        all_keys = set(v1.keys()).union(v2.keys())
        for k in all_keys:
            if v1.get(k, 0) < v2.get(k, 0):
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self._node_id, "clock": self._clock.copy()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorClock":
        clock = cls(node_id=data["node_id"])
        clock._clock = data["clock"].copy()
        return clock

    def reset(self) -> None:
        self._clock = {self._node_id: 0}

    def copy(self) -> "VectorClock":
        clock = VectorClock(self._node_id)
        clock._clock = self._clock.copy()
        return clock
