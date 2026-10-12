"""Per-execution causal reconstruction engine.

``ingest`` is cheap and idempotent (duplicate event ids are counted and ignored,
parents that have not arrived yet are tracked as *unresolved* and linked
automatically when they show up). The graph is rebuilt lazily from the retained
events the first time it is read after a change, which keeps ingestion O(1) and
makes the result independent of arrival order by construction.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from typing import Any, Callable, Dict, Iterable, List, Optional

import networkx as nx

from chronosmesh.analysis.anomaly import AnomalyReport, CausalAnomalyDetector
from chronosmesh.events.event import Event
from chronosmesh.reconstruction.fast import ReconstructionResult, reconstruct

ACCEPTED = "accepted"
DUPLICATE = "duplicate"


class CapacityError(RuntimeError):
    """Raised when an execution exceeds its configured event capacity."""


class ReconstructionEngine:
    def __init__(
        self,
        execution_id: str,
        *,
        detector: Optional[CausalAnomalyDetector] = None,
        on_rebuild: Optional[Callable[[float, "ReconstructionResult"], None]] = None,
        max_events: int = 0,
    ) -> None:
        self.execution_id = execution_id
        self.detector = detector or CausalAnomalyDetector()
        self._on_rebuild = on_rebuild
        self._max_events = max_events
        self._events: Dict[str, Event] = {}
        self._duplicates: List[str] = []
        # declared parent id -> ids of events still waiting for it (maintained incrementally, O(1) to read)
        self._waiting: Dict[str, set] = {}
        self._result: Optional[ReconstructionResult] = None
        self._anomalies: Optional[List[AnomalyReport]] = None
        self._lock = threading.RLock()
        self.counters: Counter = Counter()
        self.created_at = time.time()
        self.last_rebuild_seconds = 0.0

    # ── Ingestion ────────────────────────────────────────────────────────────
    def ingest(self, event: Event) -> str:
        """Add one event. Returns ``accepted`` or ``duplicate``; raises on invalid input."""
        if not event.event_id or not event.service_id:
            self.counters["rejected"] += 1
            raise ValueError("event_id and service_id are required")
        with self._lock:
            self.counters["received"] += 1
            if event.event_id in self._events:
                self._duplicates.append(event.event_id)
                self.counters["duplicate"] += 1
                self._anomalies = None
                return DUPLICATE
            if self._max_events and len(self._events) >= self._max_events:
                self.counters["rejected"] += 1
                raise CapacityError(
                    f"execution {self.execution_id} reached its limit of {self._max_events} events"
                )
            self._events[event.event_id] = event
            self._waiting.pop(event.event_id, None)          # a late parent has arrived: its children resolve
            for pid in event.parent_event_ids:
                if pid not in self._events:
                    self._waiting.setdefault(pid, set()).add(event.event_id)
            self.counters["processed"] += 1
            self._result = None
            self._anomalies = None
            return ACCEPTED

    def ingest_many(self, events: Iterable[Event]) -> Counter:
        outcome: Counter = Counter()
        for ev in events:
            outcome[self.ingest(ev)] += 1
        return outcome

    # ── Reconstruction ───────────────────────────────────────────────────────
    @property
    def events(self) -> List[Event]:
        with self._lock:
            return list(self._events.values())

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def unresolved_links(self) -> int:
        """Declared (parent, child) links whose parent has not been observed yet. O(#missing parents)."""
        return sum(len(children) for children in self._waiting.values())

    @property
    def duplicate_count(self) -> int:
        return len(self._duplicates)

    def result(self) -> ReconstructionResult:
        with self._lock:
            if self._result is None:
                t0 = time.perf_counter()
                self._result = reconstruct(self._events.values())
                self.last_rebuild_seconds = time.perf_counter() - t0
                if self._on_rebuild:
                    try:
                        self._on_rebuild(self.last_rebuild_seconds, self._result)
                    except Exception:  # metrics must never break reconstruction
                        pass
            return self._result

    @property
    def dag(self) -> nx.DiGraph:
        return self.result().dag

    # ── Anomalies ────────────────────────────────────────────────────────────
    def anomalies(self, *, types: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> List[AnomalyReport]:
        with self._lock:
            if self._anomalies is None:
                res = self.result()
                found = self.detector.detect_all(res.dag, list(res.events.values()))
                for eid, n in Counter(self._duplicates).items():
                    found.append(AnomalyReport(
                        anomaly_type="DUPLICATE_EVENT",
                        severity="WARNING",
                        source_event_id=eid,
                        target_event_id=None,
                        description=f"Event {eid} was delivered {n + 1} times; extra deliveries ignored",
                        details={"deliveries": n + 1},
                    ))
                self._anomalies = found
            out = self._anomalies
        if types:
            wanted = set(types)
            out = [a for a in out if a.anomaly_type in wanted]
        return out[:limit] if limit else out

    def anomaly_summary(self) -> Dict[str, Any]:
        found = self.anomalies()
        by_type = Counter(a.anomaly_type for a in found)
        by_sev = Counter(a.severity for a in found)
        return {"total": len(found), "by_type": dict(by_type), "by_severity": dict(by_sev)}

    # ── Views ────────────────────────────────────────────────────────────────
    def stats(self) -> Dict[str, Any]:
        res = self.result()
        return {
            "execution_id": self.execution_id,
            "events": len(res.events),
            "edges": res.dag.number_of_edges(),
            "duplicates": len(self._duplicates),
            "unresolved_parents": res.stats["unresolved_parents"],
            "unresolved_links": res.stats["unresolved_links"],
            "inferred_edges": res.stats["inferred_edges"],
            "explicit_edges": res.stats["explicit_edges"],
            "gap_edges": res.stats["gap_edges"],
            "rejected_declared": res.stats["rejected_declared"],
            "services": len({e.service_id for e in res.events.values()}),
            "last_rebuild_seconds": self.last_rebuild_seconds,
            **{f"counter_{k}": v for k, v in self.counters.items()},
        }

    def snapshot(self, max_nodes: Optional[int] = None) -> Dict[str, Any]:
        """Graph in the node/edge JSON shape the dashboard already consumes."""
        res = self.result()
        dag = res.dag
        try:
            topo = list(nx.topological_sort(dag))
        except nx.NetworkXUnfeasible:
            topo = []
        keep = None
        truncated = False
        if max_nodes and dag.number_of_nodes() > max_nodes:
            keep = set(topo[:max_nodes]) if topo else set(list(dag.nodes)[:max_nodes])
            truncated = True

        nodes = []
        for nid, d in dag.nodes(data=True):
            if keep is not None and nid not in keep:
                continue
            meta = d.get("metadata", {}) or {}
            nodes.append({
                "id": nid,
                "service_id": d.get("service_id", "unknown"),
                "event_type": d.get("event_type", "unknown"),
                "timestamp_ms": d.get("timestamp_ms", 0.0),
                "arrival_time_ms": d.get("arrival_time_ms", 0.0),
                "lamport_ts": d.get("lamport_ts", 0),
                "vector_clock": d.get("vector_clock", {}),
                "region": meta.get("region", "unknown"),
                "clock_uncertainty_ms": meta.get("clock_uncertainty_ms", 5.0),
                "parent_event_ids": d.get("parent_event_ids", []),
                "unresolved": [p for p in d.get("parent_event_ids", []) if p not in res.events],
            })
        edges = [
            {
                "source": u, "target": v,
                "explicit": bool(a.get("explicit")), "inferred": bool(a.get("inferred")),
                "verified": bool(a.get("verified", True)), "via_gap": bool(a.get("via_gap")),
                "confidence": a.get("confidence", 1.0),
            }
            for u, v, a in dag.edges(data=True)
            if keep is None or (u in keep and v in keep)
        ]
        return {
            "execution_id": self.execution_id,
            "nodes": nodes,
            "edges": edges,
            "topological_order": [t for t in topo if keep is None or t in keep],
            "roots": [n for n, deg in dag.in_degree() if deg == 0 and (keep is None or n in keep)],
            "leaves": [n for n, deg in dag.out_degree() if deg == 0 and (keep is None or n in keep)],
            "unresolved": res.unresolved,
            "truncated": truncated,
            "total_nodes": dag.number_of_nodes(),
            "total_edges": dag.number_of_edges(),
        }

    # ── Checkpoint / restore (worker crash recovery) ─────────────────────────
    def checkpoint(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events.values()]

    @classmethod
    def restore(cls, execution_id: str, checkpoint: Iterable[Dict[str, Any]], **kwargs: Any) -> "ReconstructionEngine":
        engine = cls(execution_id, **kwargs)
        for d in checkpoint:
            engine.ingest(Event.from_dict(d))
        return engine
