from typing import Dict, Type, Any, List
from chronosmesh.clocks.base import ClockStrategy
from chronosmesh.clocks.lamport import LamportClock
from chronosmesh.clocks.vector import VectorClock
from chronosmesh.clocks.hlc import HybridLogicalClock

class ClockFactory:
    _registry: Dict[str, Type[ClockStrategy]] = {
        'lamport': LamportClock,
        'vector': VectorClock,
        'hlc': HybridLogicalClock
    }

    @classmethod
    def create(cls, strategy: str, node_id: str, **kwargs: Any) -> ClockStrategy:
        if strategy not in cls._registry:
            raise ValueError(f"Unknown clock strategy: {strategy}")
        return cls._registry[strategy](node_id=node_id, **kwargs)

    @classmethod
    def register(cls, name: str, clock_class: Type[ClockStrategy]) -> None:
        cls._registry[name] = clock_class

    @classmethod
    def available_strategies(cls) -> List[str]:
        return list(cls._registry.keys())
