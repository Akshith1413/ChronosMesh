import time
from dataclasses import dataclass
from typing import Any, Dict, Callable, Union
from chronosmesh.clocks.base import ClockStrategy, CausalRelation

class ClockDriftError(Exception):
    pass

@dataclass
class HLCTimestamp:
    l: int
    c: int
    node_id: str

    def __lt__(self, other: "HLCTimestamp") -> bool:
        if self.l != other.l: return self.l < other.l
        if self.c != other.c: return self.c < other.c
        return self.node_id < other.node_id

    def __gt__(self, other: "HLCTimestamp") -> bool:
        if self.l != other.l: return self.l > other.l
        if self.c != other.c: return self.c > other.c
        return self.node_id > other.node_id

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, HLCTimestamp): return False
        return self.l == other.l and self.c == other.c and self.node_id == other.node_id

class HybridLogicalClock(ClockStrategy):
    def __init__(self, node_id: str, max_skew_ns: int = 500_000_000, time_fn: Callable[[], int] = time.time_ns, **kwargs: Any) -> None:
        self._node_id = node_id
        self._l = 0
        self._c = 0
        self.max_skew_ns = max_skew_ns
        self._time_fn = time_fn

    @property
    def node_id(self) -> str:
        return self._node_id

    def tick(self) -> HLCTimestamp:
        pt = self._time_fn()
        l_old = self._l
        self._l = max(l_old, pt)
        if self._l == l_old:
            self._c += 1
        else:
            self._c = 0
        return self.current_timestamp()

    def send(self) -> HLCTimestamp:
        return self.tick()

    def receive(self, remote_timestamp: Union[HLCTimestamp, Dict[str, Any]]) -> HLCTimestamp:
        if isinstance(remote_timestamp, dict):
            remote_timestamp = HLCTimestamp(remote_timestamp['l'], remote_timestamp['c'], remote_timestamp['node_id'])
            
        pt = self._time_fn()
        if (remote_timestamp.l - pt) > self.max_skew_ns:
            raise ClockDriftError(f"Clock drift too large: {remote_timestamp.l - pt} ns")
            
        l_old = self._l
        self._l = max(l_old, remote_timestamp.l, pt)
        
        if self._l == l_old and self._l == remote_timestamp.l:
            self._c = max(self._c, remote_timestamp.c) + 1
        elif self._l == l_old:
            self._c += 1
        elif self._l == remote_timestamp.l:
            self._c = remote_timestamp.c + 1
        else:
            self._c = 0
            
        return self.current_timestamp()

    @staticmethod
    def compare(ts1: HLCTimestamp, ts2: HLCTimestamp) -> CausalRelation:
        if ts1 < ts2:
            return CausalRelation.HAPPENS_BEFORE
        elif ts1 > ts2:
            return CausalRelation.HAPPENS_AFTER
        else:
            return CausalRelation.EQUAL

    def current_timestamp(self) -> HLCTimestamp:
        return HLCTimestamp(self._l, self._c, self._node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self._node_id,
            "l": self._l,
            "c": self._c,
            "max_skew_ns": self.max_skew_ns
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HybridLogicalClock":
        clock = cls(node_id=data["node_id"], max_skew_ns=data.get("max_skew_ns", 500_000_000))
        clock._l = data["l"]
        clock._c = data["c"]
        return clock

    def reset(self) -> None:
        self._l = 0
        self._c = 0

    def copy(self) -> "HybridLogicalClock":
        clock = HybridLogicalClock(self._node_id, max_skew_ns=self.max_skew_ns, time_fn=self._time_fn)
        clock._l = self._l
        clock._c = self._c
        return clock
