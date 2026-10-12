"""Causal anomaly detection.

Distinguishes what the engine can *prove* from what it merely suspects:

========================  ========  ====================================================
Type                      Severity  Meaning
========================  ========  ====================================================
CYCLE                     CRITICAL  The reconstructed graph is not acyclic (bad metadata)
CAUSAL_VIOLATION          CRITICAL  A declared parent is not covered by the child's clocks
CLOCK_DRIFT               CRITICAL  Wall clocks of two services disagree beyond tolerance
TIME_INVERSION            WARNING   A causal child carries an older wall-clock timestamp
DUPLICATE_EVENT           WARNING   The same event id was delivered more than once
UNRESOLVED_PARENT         WARNING   A declared parent has not (yet) been observed
ORPHAN_EVENT              WARNING   Every declared parent of the event is unresolved
VECTOR_CLOCK_GAP          WARNING   A service's own counter skips values (lost events)
CONCURRENT_MUTATION       WARNING   Concurrent writes to the same resource
RETRY_STORM               WARNING   Many retries of the same operation
LATE_ARRIVAL              INFO      A parent arrived after its causal child
========================  ========  ====================================================
"""

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import networkx as nx

_MUTATING_OPS = {"write", "update", "delete", "mutate", "set"}


@dataclass
class AnomalyReport:
    anomaly_type: str
    severity: str
    source_event_id: str
    target_event_id: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get(ev: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from an Event object or a plain dict (DAG node attributes)."""
    if isinstance(ev, dict):
        return ev.get(name, default)
    return getattr(ev, name, default)


def _payload(ev: Any) -> Dict[str, Any]:
    p = _get(ev, "payload", None)
    return p if isinstance(p, dict) else {}


class CausalAnomalyDetector:
    def __init__(
        self,
        clock_skew_tolerance_ms: float = 50.0,
        max_clock_drift_ms: float = 500.0,
        retry_storm_threshold: int = 5,
    ):
        self.clock_skew_tolerance_ms = clock_skew_tolerance_ms
        self.max_clock_drift_ms = max_clock_drift_ms
        self.retry_storm_threshold = retry_storm_threshold

    # ── Aggregate ────────────────────────────────────────────────────────────
    def detect_all(self, dag: nx.DiGraph, events: Optional[List[Any]] = None) -> List[AnomalyReport]:
        if events is None:
            events = [dag.nodes[n] for n in dag.nodes()]

        anomalies: List[AnomalyReport] = []
        anomalies.extend(self.detect_cycles(dag))
        anomalies.extend(self.detect_time_inversions(dag))
        anomalies.extend(self.detect_vector_clock_gaps(events))
        anomalies.extend(self.detect_clock_drift(events))
        anomalies.extend(self.detect_duplicate_events(events))
        anomalies.extend(self.detect_concurrent_mutations(dag, events))
        anomalies.extend(self.detect_unresolved_parents(events))
        anomalies.extend(self.detect_orphans(events))
        anomalies.extend(self.detect_causal_violations(events))
        anomalies.extend(self.detect_retry_storms(events))
        anomalies.extend(self.detect_late_arrivals(events))
        return anomalies

    # ── Graph-level ──────────────────────────────────────────────────────────
    def detect_cycles(self, dag: nx.DiGraph) -> List[AnomalyReport]:
        anomalies = []
        if nx.is_directed_acyclic_graph(dag):
            return anomalies
        try:
            cycles = list(nx.simple_cycles(dag))
            for cycle in cycles:
                anomalies.append(AnomalyReport(
                    anomaly_type="CYCLE",
                    severity="CRITICAL",
                    source_event_id=cycle[0],
                    target_event_id=cycle[-1],
                    description="Cycle detected in causal graph",
                    details={"cycle": cycle}
                ))
        except nx.NetworkXNoCycle:
            pass
        return anomalies

    def detect_time_inversions(self, dag: nx.DiGraph) -> List[AnomalyReport]:
        anomalies = []
        for u, v in dag.edges():
            u_ts = dag.nodes[u].get("timestamp_ms", 0.0)
            v_ts = dag.nodes[v].get("timestamp_ms", 0.0)
            if u_ts > v_ts + self.clock_skew_tolerance_ms:
                anomalies.append(AnomalyReport(
                    anomaly_type="TIME_INVERSION",
                    severity="WARNING",
                    source_event_id=u,
                    target_event_id=v,
                    description="Causal child has older physical timestamp",
                    details={"parent_ts": u_ts, "child_ts": v_ts, "diff": u_ts - v_ts}
                ))
        return anomalies

    # ── Event-level ──────────────────────────────────────────────────────────
    def detect_vector_clock_gaps(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """A service's own vector-clock counter must advance by exactly one per event.

        A hole means an event of that service was lost (or never delivered).
        """
        counters: Dict[str, Dict[int, str]] = defaultdict(dict)
        for ev in events:
            sid = _get(ev, "service_id")
            vc = _get(ev, "vector_clock") or {}
            if sid and sid in vc and vc[sid] > 0:
                counters[sid][int(vc[sid])] = _get(ev, "event_id", "")

        anomalies: List[AnomalyReport] = []
        for sid, seen in counters.items():
            expected = set(range(1, max(seen) + 1))
            missing = sorted(expected - set(seen))
            if missing:
                anomalies.append(AnomalyReport(
                    anomaly_type="VECTOR_CLOCK_GAP",
                    severity="WARNING",
                    source_event_id=seen[max(seen)],
                    target_event_id=None,
                    description=f"{sid} skipped {len(missing)} vector-clock value(s): events likely lost",
                    details={"service_id": sid, "missing_count": len(missing), "missing_counters": missing[:50]},
                ))
        return anomalies

    def detect_clock_drift(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """Lower-bound estimate of the wall-clock offset between two services.

        For a cross-service causal link ``parent -> child`` the observed delta
        ``child.ts - parent.ts`` equals transit time (>= 0) plus the clock offset.
        A negative delta therefore *proves* the child's clock lags the parent's by at
        least ``-delta``. Flagged when that proven lower bound exceeds
        ``max_clock_drift_ms``.
        """
        events = list(events)
        by_id = {_get(e, "event_id"): e for e in events if _get(e, "event_id") is not None}
        min_delta: Dict[tuple, tuple] = {}
        for ev in events:
            for pid in _get(ev, "parent_event_ids", []) or []:
                parent = by_id.get(pid)
                if parent is None:
                    continue
                ps, cs = _get(parent, "service_id"), _get(ev, "service_id")
                if not ps or not cs or ps == cs:
                    continue
                delta = float(_get(ev, "timestamp_ms", 0.0)) - float(_get(parent, "timestamp_ms", 0.0))
                key = (ps, cs)
                if key not in min_delta or delta < min_delta[key][0]:
                    min_delta[key] = (delta, pid, _get(ev, "event_id"))

        anomalies = []
        for (ps, cs), (delta, pid, cid) in min_delta.items():
            lag = -delta
            if lag > self.max_clock_drift_ms:
                anomalies.append(AnomalyReport(
                    anomaly_type="CLOCK_DRIFT",
                    severity="CRITICAL",
                    source_event_id=pid,
                    target_event_id=cid,
                    description=f"Clock of {cs} lags {ps} by at least {lag:.0f} ms",
                    details={"from_service": ps, "to_service": cs, "min_offset_ms": lag},
                ))
        return anomalies

    def detect_duplicate_events(self, events: Iterable[Any]) -> List[AnomalyReport]:
        anomalies = []
        seen = set()
        for ev in events:
            ev_id = getattr(ev, "event_id", None) or (ev.get("event_id") if isinstance(ev, dict) else None)
            if ev_id is None:
                continue
            if ev_id in seen:
                anomalies.append(AnomalyReport(
                    anomaly_type="DUPLICATE_EVENT",
                    severity="WARNING",
                    source_event_id=ev_id,
                    target_event_id=None,
                    description=f"Duplicate event ID detected: {ev_id}",
                    details={}
                ))
            seen.add(ev_id)
        return anomalies

    def detect_concurrent_mutations(self, dag: nx.DiGraph, events: Iterable[Any]) -> List[AnomalyReport]:
        """Two services writing the same resource with no causal order between them."""
        groups: Dict[str, List[Any]] = defaultdict(list)
        for ev in events:
            p = _payload(ev)
            resource = p.get("resource") or p.get("entity_id")
            if resource and str(p.get("op", "write")).lower() in _MUTATING_OPS:
                groups[str(resource)].append(ev)

        anomalies = []
        for resource, evs in groups.items():
            if len(evs) < 2 or len(evs) > 200:
                continue
            for i in range(len(evs)):
                for j in range(i + 1, len(evs)):
                    a, b = evs[i], evs[j]
                    ia, ib = _get(a, "event_id"), _get(b, "event_id")
                    if _get(a, "service_id") == _get(b, "service_id") or ia not in dag or ib not in dag:
                        continue
                    if not nx.has_path(dag, ia, ib) and not nx.has_path(dag, ib, ia):
                        anomalies.append(AnomalyReport(
                            anomaly_type="CONCURRENT_MUTATION",
                            severity="WARNING",
                            source_event_id=ia,
                            target_event_id=ib,
                            description=f"Concurrent writes to resource '{resource}'",
                            details={"resource": resource,
                                     "services": [_get(a, "service_id"), _get(b, "service_id")]},
                        ))
        return anomalies

    def detect_unresolved_parents(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """A declared parent was never observed: report it instead of inventing an edge."""
        events = list(events)
        known = {_get(e, "event_id") for e in events}
        anomalies = []
        for ev in events:
            for pid in _get(ev, "parent_event_ids", []) or []:
                if pid not in known:
                    anomalies.append(AnomalyReport(
                        anomaly_type="UNRESOLVED_PARENT",
                        severity="WARNING",
                        source_event_id=_get(ev, "event_id", ""),
                        target_event_id=pid,
                        description=f"Declared parent {pid} has not been observed",
                        details={"missing_parent": pid, "service_id": _get(ev, "service_id")},
                    ))
        return anomalies

    def detect_orphans(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """Events that declare parents, none of which are known: causally disconnected."""
        events = list(events)
        known = {_get(e, "event_id") for e in events}
        anomalies = []
        for ev in events:
            parents = _get(ev, "parent_event_ids", []) or []
            if parents and not any(p in known for p in parents):
                anomalies.append(AnomalyReport(
                    anomaly_type="ORPHAN_EVENT",
                    severity="WARNING",
                    source_event_id=_get(ev, "event_id", ""),
                    target_event_id=None,
                    description="All declared parents are unresolved; event is causally disconnected",
                    details={"parents": list(parents)},
                ))
        return anomalies

    def detect_causal_violations(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """A declared parent must be covered by the child's vector clock and Lamport time."""
        events = list(events)
        by_id = {_get(e, "event_id"): e for e in events}
        anomalies = []
        for ev in events:
            cvc = _get(ev, "vector_clock") or {}
            for pid in _get(ev, "parent_event_ids", []) or []:
                parent = by_id.get(pid)
                if parent is None:
                    continue
                pvc = _get(parent, "vector_clock") or {}
                reason = None
                if pvc and cvc and any(v > cvc.get(k, 0) for k, v in pvc.items()):
                    reason = "parent vector clock is not dominated by child's"
                else:
                    plt, clt = _get(parent, "lamport_ts"), _get(ev, "lamport_ts")
                    if plt is not None and clt is not None and plt and clt and plt >= clt:
                        reason = "parent Lamport time is not smaller than child's"
                if reason:
                    anomalies.append(AnomalyReport(
                        anomaly_type="CAUSAL_VIOLATION",
                        severity="CRITICAL",
                        source_event_id=pid,
                        target_event_id=_get(ev, "event_id", ""),
                        description=f"Declared dependency contradicts logical clocks: {reason}",
                        details={"reason": reason},
                    ))
        return anomalies

    def detect_retry_storms(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """Many retries (``payload.attempt`` > 1 or ``payload.retry_of``) of one operation."""
        groups: Dict[tuple, List[str]] = defaultdict(list)
        for ev in events:
            p = _payload(ev)
            attempt = p.get("attempt", 1)
            retry_of = p.get("retry_of")
            if retry_of or (isinstance(attempt, int) and attempt > 1):
                key = (_get(ev, "service_id"), _get(ev, "event_type"), retry_of or p.get("idempotency_key"))
                groups[key].append(_get(ev, "event_id", ""))

        anomalies = []
        for (sid, etype, _op), ids in groups.items():
            if len(ids) >= self.retry_storm_threshold:
                anomalies.append(AnomalyReport(
                    anomaly_type="RETRY_STORM",
                    severity="CRITICAL" if len(ids) >= 3 * self.retry_storm_threshold else "WARNING",
                    source_event_id=ids[0],
                    target_event_id=None,
                    description=f"{len(ids)} retries of {etype} on {sid}",
                    details={"service_id": sid, "event_type": etype, "retries": len(ids)},
                ))
        return anomalies

    def detect_late_arrivals(self, events: Iterable[Any]) -> List[AnomalyReport]:
        """A causal parent was ingested *after* its child (out-of-order delivery)."""
        events = list(events)
        by_id = {_get(e, "event_id"): e for e in events}
        anomalies = []
        for ev in events:
            c_arr = _get(ev, "arrival_time_ms")
            if c_arr is None:
                continue
            for pid in _get(ev, "parent_event_ids", []) or []:
                parent = by_id.get(pid)
                p_arr = _get(parent, "arrival_time_ms") if parent is not None else None
                if p_arr is not None and p_arr > c_arr:
                    anomalies.append(AnomalyReport(
                        anomaly_type="LATE_ARRIVAL",
                        severity="INFO",
                        source_event_id=pid,
                        target_event_id=_get(ev, "event_id", ""),
                        description="Parent arrived after its causal child",
                        details={"lateness_ms": p_arr - c_arr},
                    ))
        return anomalies
