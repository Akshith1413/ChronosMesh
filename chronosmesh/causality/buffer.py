from dataclasses import dataclass
from typing import List, Dict, Set

from chronosmesh.events.event import Event

@dataclass
class BufferPolicy:
    max_buffer_size: int = 1000
    max_wait_time_ms: float = 5000.0
    watermark_interval_ms: float = 1000.0

class EventBuffer:
    def __init__(self, policy: BufferPolicy = None):
        self.policy = policy or BufferPolicy()
        self.buffer: Dict[str, Event] = {}
        self.emitted: Set[str] = set()
        self.watermark_ms = 0.0

    def add(self, event: Event) -> List[Event]:
        if self._is_safe_to_emit(event):
            self.emitted.add(event.event_id)
            ready = [event]
            ready.extend(self._check_buffer_for_ready())
            return ready
        else:
            self.buffer[event.event_id] = event
            if len(self.buffer) > self.policy.max_buffer_size:
                pass
            return []

    def _is_safe_to_emit(self, event: Event) -> bool:
        if not event.parent_event_ids:
            return True
        return all(pid in self.emitted for pid in event.parent_event_ids)

    def _check_buffer_for_ready(self) -> List[Event]:
        ready = []
        changed = True
        while changed:
            changed = False
            for eid, event in list(self.buffer.items()):
                if self._is_safe_to_emit(event):
                    ready.append(event)
                    self.emitted.add(eid)
                    del self.buffer[eid]
                    changed = True
        return ready

    def flush(self) -> List[Event]:
        ready = list(self.buffer.values())
        for e in ready:
            self.emitted.add(e.event_id)
        self.buffer.clear()
        return ready

    def advance_watermark(self, watermark_ms: float) -> List[Event]:
        self.watermark_ms = watermark_ms
        ready = []
        for eid, event in list(self.buffer.items()):
            if event.arrival_time_ms <= watermark_ms - self.policy.max_wait_time_ms:
                ready.append(event)
                self.emitted.add(eid)
                del self.buffer[eid]
        ready.extend(self._check_buffer_for_ready())
        return ready

    def pending_count(self) -> int:
        return len(self.buffer)

    def is_empty(self) -> bool:
        return len(self.buffer) == 0
