"""Thread-safe in-memory repository (tests, laptops, and the demo mode)."""

from __future__ import annotations

import copy
import threading
from typing import Any, Dict, List, Optional

from chronosmesh.persistence.base import blocked_by_terminal_state


class MemoryRepository:
    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executions: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._segments: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        self._anomalies: Dict[str, List[Dict[str, Any]]] = {}
        self._graphs: Dict[str, Dict[str, Any]] = {}
        self._blobs: Dict[tuple, Any] = {}

    # executions
    def put_execution(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._executions[record["execution_id"]] = copy.deepcopy(record)

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._executions.get(execution_id)
            return copy.deepcopy(rec) if rec else None

    def update_execution(self, execution_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._executions.get(execution_id)
            if rec is None:
                return None
            if not blocked_by_terminal_state(rec, fields):
                rec.update(copy.deepcopy(fields))
            return copy.deepcopy(rec)

    def list_executions(self, owner=None, *, limit=50, parent_id=None, include_children=False):
        with self._lock:
            rows = list(self._executions.values())
        if owner is not None:
            rows = [r for r in rows if r.get("owner") == owner]
        if parent_id is not None:
            rows = [r for r in rows if r.get("parent_id") == parent_id]
        elif not include_children:
            rows = [r for r in rows if not r.get("parent_id")]
        rows.sort(key=lambda r: r.get("created_at_ms", 0), reverse=True)
        return copy.deepcopy(rows[:limit])

    # events
    def put_events(self, execution_id: str, events: List[Dict[str, Any]]) -> int:
        with self._lock:
            bucket = self._events.setdefault(execution_id, {})
            for e in events:
                bucket[e["event_id"]] = copy.deepcopy(e)
            return len(events)

    def get_events(self, execution_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            rows = list(self._events.get(execution_id, {}).values())
        return copy.deepcopy(rows[:limit] if limit else rows)

    # segments
    def put_segment(self, execution_id: str, seq: int, events: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._segments.setdefault(execution_id, {})[seq] = copy.deepcopy(events)

    def list_segments(self, execution_id: str) -> List[int]:
        with self._lock:
            return sorted(self._segments.get(execution_id, {}))

    def get_segment(self, execution_id: str, seq: int) -> List[Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._segments.get(execution_id, {}).get(seq, []))

    # derived
    def put_anomalies(self, execution_id: str, anomalies: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._anomalies[execution_id] = copy.deepcopy(anomalies)

    def get_anomalies(self, execution_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._anomalies.get(execution_id, [])
            return copy.deepcopy(rows[:limit] if limit else rows)

    def put_graph(self, execution_id: str, graph: Dict[str, Any]) -> str:
        with self._lock:
            self._graphs[execution_id] = copy.deepcopy(graph)
        return f"memory://graphs/{execution_id}"

    def get_graph(self, execution_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            g = self._graphs.get(execution_id)
            return copy.deepcopy(g) if g else None

    def put_blob(self, execution_id: str, name: str, payload: Any) -> str:
        with self._lock:
            self._blobs[(execution_id, name)] = copy.deepcopy(payload)
        return f"memory://{execution_id}/{name}"

    def get_blob(self, execution_id: str, name: str) -> Optional[Any]:
        with self._lock:
            v = self._blobs.get((execution_id, name))
            return copy.deepcopy(v) if v is not None else None

    def health(self) -> Dict[str, Any]:
        return {"backend": self.backend, "ok": True, "executions": len(self._executions)}
