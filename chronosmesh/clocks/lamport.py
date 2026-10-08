import copy
from typing import Any, Dict, Tuple
from chronosmesh.clocks.base import ClockStrategy, CausalRelation

class LamportClock(ClockStrategy):
    def __init__(self, node_id: str, **kwargs: Any) -> None:
        self._node_id = node_id
        self._counter = 0

    @property
    def node_id(self) -> str:
        return self._node_id

    def tick(self) -> Tuple[int, str]:
        self._counter += 1
        return self.current_timestamp()

    def send(self) -> Tuple[int, str]:
        self._counter += 1
        return self.current_timestamp()

    def receive(self, remote_timestamp: Any) -> Tuple[int, str]:
        if isinstance(remote_timestamp, tuple):
            remote_counter = remote_timestamp[0]
        else:
            remote_counter = remote_timestamp
        self._counter = max(self._counter, remote_counter) + 1
        return self.current_timestamp()

    @staticmethod
    def compare(ts1: Tuple[int, str], ts2: Tuple[int, str]) -> CausalRelation:
        c1, n1 = ts1
        c2, n2 = ts2
        if c1 < c2:
            return CausalRelation.HAPPENS_BEFORE
        elif c1 > c2:
            return CausalRelation.HAPPENS_AFTER
        else:
            if n1 < n2:
                return CausalRelation.HAPPENS_BEFORE
            elif n1 > n2:
                return CausalRelation.HAPPENS_AFTER
            else:
                return CausalRelation.EQUAL

    def current_timestamp(self) -> Tuple[int, str]:
        return (self._counter, self._node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self._node_id, "counter": self._counter}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LamportClock":
        clock = cls(node_id=data["node_id"])
        clock._counter = data["counter"]
        return clock

    def reset(self) -> None:
        self._counter = 0

    def copy(self) -> "LamportClock":
        clock = LamportClock(self._node_id)
        clock._counter = self._counter
        return clock
