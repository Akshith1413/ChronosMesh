"""Scalable causal-graph reconstruction from vector clocks plus declared parents.

Why this exists
---------------
``CausalDAGBuilder.build`` compares every pair of events (O(n^2)). With vector
clocks that is unnecessary: for an event ``b`` the *direct* causal predecessors are
the maximal elements of ``{z : z -> b}``. For every service ``s`` the latest known
event ``z`` of ``s`` that ``b`` has seen has counter ``<= b.vector_clock[s]``, and
any other event of ``s`` that precedes ``b`` precedes ``z`` too. So only one
candidate per service needs to be considered -> O(n * S) candidates, O(n * S^2)
dominance checks, with ``S`` the number of services in the clock.

Properties
----------
* The result is the **transitive reduction of the happens-before relation restricted
  to the delivered events**. Edges that bridge lost events are flagged
  ``via_gap=True`` and ``inferred=True`` (proven by clocks, not declared).
* Declared parents (``parent_event_ids``) are accepted when consistent with the
  clocks (``verified=True``); a declaration the clocks contradict is rejected and
  reported, never silently turned into an edge.
* Declared parents that have not been observed are returned in ``unresolved``;
  nothing is invented for them.
* Events without a vector clock fall back to their declared parents only.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx

from chronosmesh.events.event import Event


@dataclass
class ReconstructionResult:
    dag: nx.DiGraph
    events: Dict[str, Event]
    unresolved: Dict[str, List[str]] = field(default_factory=dict)  # missing parent -> waiting children
    duplicates: List[str] = field(default_factory=list)
    rejected_declared: List[Tuple[str, str, str]] = field(default_factory=list)  # (parent, child, reason)
    stats: Dict[str, int] = field(default_factory=dict)


def _own_counter(ev: Event) -> int:
    return int(ev.vector_clock.get(ev.service_id, 0)) if ev.vector_clock else 0


def _precedes(x: Event, y: Event) -> bool:
    """True iff ``x`` happens-before ``y`` according to their vector clocks (x != y)."""
    cx = _own_counter(x)
    if cx <= 0 or not y.vector_clock:
        return False
    return y.vector_clock.get(x.service_id, 0) >= cx and x.event_id != y.event_id


def _vc_leq(a: Dict[str, int], b: Dict[str, int]) -> bool:
    return all(v <= b.get(k, 0) for k, v in a.items())


def reconstruct(
    events: Iterable[Event],
    *,
    use_explicit: bool = True,
    use_vector_clocks: bool = True,
) -> ReconstructionResult:
    """Build the causal DAG for ``events`` (see module docstring)."""
    unique: Dict[str, Event] = {}
    duplicates: List[str] = []
    for ev in events:
        if ev.event_id in unique:
            duplicates.append(ev.event_id)
        else:
            unique[ev.event_id] = ev

    dag = nx.DiGraph()
    for ev in unique.values():
        dag.add_node(
            ev.event_id,
            event_id=ev.event_id,
            service_id=ev.service_id,
            event_type=ev.event_type,
            timestamp_ms=ev.timestamp_ms,
            lamport_ts=ev.lamport_ts,
            vector_clock=ev.vector_clock,
            parent_event_ids=ev.parent_event_ids,
            arrival_time_ms=ev.arrival_time_ms,
            payload=ev.payload,
            metadata=ev.metadata.to_dict(),
        )

    # Per-service index: own counter -> event id (sorted counters for bisect).
    by_service: Dict[str, Dict[int, str]] = defaultdict(dict)
    if use_vector_clocks:
        for ev in unique.values():
            c = _own_counter(ev)
            if c > 0:
                by_service[ev.service_id][c] = ev.event_id
    sorted_counters = {s: sorted(m) for s, m in by_service.items()}

    unresolved: Dict[str, List[str]] = defaultdict(list)
    rejected: List[Tuple[str, str, str]] = []
    n_explicit = n_inferred = n_unverified = n_gap = 0

    for b in unique.values():
        # candidate predecessor id -> attributes
        cands: Dict[str, Dict[str, bool]] = {}

        for pid in b.parent_event_ids:
            p = unique.get(pid)
            if p is None:
                unresolved[pid].append(b.event_id)
                continue
            if not use_explicit or pid == b.event_id:
                continue
            if p.vector_clock and b.vector_clock:
                if _vc_leq(p.vector_clock, b.vector_clock) and p.vector_clock != b.vector_clock:
                    cands[pid] = {"explicit": True, "verified": True, "inferred": False, "via_gap": False}
                else:
                    rejected.append((pid, b.event_id, "declared parent not covered by child's vector clock"))
            else:
                cands[pid] = {"explicit": True, "verified": False, "inferred": False, "via_gap": False}

        if use_vector_clocks and b.vector_clock:
            for s, c in b.vector_clock.items():
                c_eff = c - 1 if s == b.service_id else c
                if c_eff <= 0:
                    continue
                counters = sorted_counters.get(s)
                if not counters:
                    continue
                idx = bisect_right(counters, c_eff) - 1
                if idx < 0:
                    continue
                known = counters[idx]
                pid = by_service[s][known]
                if pid == b.event_id:
                    continue
                gap = known < c_eff
                if pid in cands:
                    cands[pid]["inferred"] = True
                else:
                    cands[pid] = {"explicit": False, "verified": True, "inferred": True, "via_gap": gap}

        if not cands:
            continue

        # Transitive reduction among b's predecessors (x is redundant if x -> y for another pred y).
        pred_events = {pid: unique[pid] for pid in cands}
        keep = []
        for pid, x in pred_events.items():
            if any(other != pid and _precedes(x, y) for other, y in pred_events.items()):
                continue
            keep.append(pid)
        for pid in keep:
            attrs = cands[pid]
            dag.add_edge(pid, b.event_id, **attrs, confidence=1.0 if attrs["verified"] else 0.9)
            if attrs["explicit"]:
                n_explicit += 1
            if attrs["inferred"] and not attrs["explicit"]:
                n_inferred += 1
            if not attrs["verified"]:
                n_unverified += 1
            if attrs["via_gap"]:
                n_gap += 1

    # Bad metadata can still close a cycle among *unverified* declarations: break it, report it.
    guard = 0
    while not nx.is_directed_acyclic_graph(dag) and guard < 1000:
        guard += 1
        cycle = nx.find_cycle(dag)
        victim = next(((u, v) for u, v in cycle if not dag.edges[u, v].get("verified", False)), cycle[0])
        rejected.append((victim[0], victim[1], "edge closes a cycle"))
        dag.remove_edge(*victim)

    return ReconstructionResult(
        dag=dag,
        events=unique,
        unresolved={k: v for k, v in unresolved.items()},
        duplicates=duplicates,
        rejected_declared=rejected,
        stats={
            "events": len(unique),
            "edges": dag.number_of_edges(),
            "explicit_edges": n_explicit,
            "inferred_edges": n_inferred,
            "unverified_edges": n_unverified,
            "gap_edges": n_gap,
            "duplicates": len(duplicates),
            "unresolved_parents": len(unresolved),
            "unresolved_links": sum(len(v) for v in unresolved.values()),
            "rejected_declared": len(rejected),
        },
    )


def edge_set(dag: nx.DiGraph) -> set:
    return set(dag.edges())
