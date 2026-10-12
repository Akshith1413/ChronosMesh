"""Scoring primitives: edge precision / recall / F1, concurrency classification, statistics."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx

from chronosmesh.events.event import Event

# Two-sided 95 % Student-t critical values for df = 1..30 (df > 30 ~ 1.96).
_T95 = [
    12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
    2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
    2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
]


def prf(predicted: Set[Tuple[str, str]], truth: Set[Tuple[str, str]]) -> Dict[str, float]:
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    precision = tp / (tp + fp) if (tp + fp) else (1.0 if not truth else 0.0)
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "edges": len(predicted)}


def chain_edges(ordered_ids: Sequence[str]) -> Set[Tuple[str, str]]:
    """A total order claims every consecutive pair is a causal edge."""
    return {(ordered_ids[i], ordered_ids[i + 1]) for i in range(len(ordered_ids) - 1)}


def mean_ci(values: Sequence[float]) -> Dict[str, float]:
    values = [v for v in values if v is not None]
    n = len(values)
    if n == 0:
        return {"mean": float("nan"), "std": 0.0, "ci95_low": float("nan"), "ci95_high": float("nan"), "n": 0}
    mean = statistics.fmean(values)
    if n == 1:
        return {"mean": mean, "std": 0.0, "ci95_low": mean, "ci95_high": mean, "n": 1}
    std = statistics.stdev(values)
    t = _T95[n - 2] if n - 1 <= len(_T95) else 1.96
    half = t * std / math.sqrt(n)
    return {"mean": mean, "std": std, "ci95_low": mean - half, "ci95_high": mean + half, "n": n}


# ── Ground-truth relation helpers ─────────────────────────────────────────────
def true_precedes(a: Event, b: Event) -> bool:
    """a -> b using the simulator's *true* vector clocks."""
    ca = a.vector_clock.get(a.service_id, 0)
    return a.event_id != b.event_id and ca > 0 and b.vector_clock.get(a.service_id, 0) >= ca


def sample_pairs(n: int, budget: int, rng: random.Random) -> List[Tuple[int, int]]:
    total = n * (n - 1) // 2
    if total <= budget:
        return [(i, j) for i in range(n) for j in range(i + 1, n)]
    seen: Set[Tuple[int, int]] = set()
    while len(seen) < budget:
        i, j = rng.randrange(n), rng.randrange(n)
        if i != j:
            seen.add((i, j) if i < j else (j, i))
    return list(seen)


def reachability(dag: nx.DiGraph) -> Optional[Tuple[Dict[str, int], Dict[str, int]]]:
    """Ancestor bit-sets: ``anc[v]`` has bit ``idx[u]`` set iff ``u`` reaches ``v``."""
    try:
        order = list(nx.topological_sort(dag))
    except nx.NetworkXUnfeasible:
        return None
    idx = {n: i for i, n in enumerate(order)}
    anc: Dict[str, int] = {}
    for v in order:
        mask = 0
        for p in dag.predecessors(v):
            mask |= anc[p] | (1 << idx[p])
        anc[v] = mask
    return idx, anc


def _confusion(pred_conc: Iterable[Optional[bool]], truth_conc: Iterable[bool]) -> Dict[str, Any]:
    tp = fp = tn = fn = skipped = 0
    for p, t in zip(pred_conc, truth_conc):
        if p is None:
            skipped += 1
        elif p and t:
            tp += 1
        elif p and not t:
            fp += 1
        elif not p and t:
            fn += 1
        else:
            tn += 1
    evaluated = tp + fp + tn + fn
    return {
        "pairs_evaluated": evaluated,
        "pairs_skipped": skipped,
        "accuracy": (tp + tn) / evaluated if evaluated else float("nan"),
        "concurrent_precision": tp / (tp + fp) if (tp + fp) else (1.0 if not (tp + fn) else 0.0),
        "concurrent_recall": tp / (tp + fn) if (tp + fn) else 1.0,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


@dataclass
class ExecutionView:
    """What each approach knows about one execution (ids in first-arrival order)."""

    ids: List[str]
    seen: Dict[str, Event]          # events as delivered (clocks possibly lost)
    chronos_dag: nx.DiGraph
    declared_dag: nx.DiGraph


def concurrency_scores(
    views: Dict[str, ExecutionView],
    truth_events: Dict[str, Event],
    *,
    rng: random.Random,
    budget: int = 20_000,
    reach_limit: int = 20_000,
) -> Dict[str, Dict[str, Any]]:
    """Classify sampled event pairs *within an execution* as ordered vs. concurrent.

    Total-order baselines (arrival order, wall clock) can only ever answer "ordered".
    """
    pool = [(eid, v) for eid, v in views.items() if len(v.ids) >= 2]
    weights = [len(v.ids) * (len(v.ids) - 1) // 2 for _, v in pool]
    total = sum(weights)
    pairs: List[Tuple[str, str, str]] = []  # (execution, a, b)
    if total <= budget:
        for eid, v in pool:
            for i in range(len(v.ids)):
                for j in range(i + 1, len(v.ids)):
                    pairs.append((eid, v.ids[i], v.ids[j]))
    else:
        by_id = dict(pool)
        for _ in range(budget):
            eid = rng.choices([p[0] for p in pool], weights=weights)[0]
            ids = by_id[eid].ids
            i, j = rng.sample(range(len(ids)), 2)
            pairs.append((eid, ids[i], ids[j]))

    truth = [
        not (true_precedes(truth_events[a], truth_events[b]) or true_precedes(truth_events[b], truth_events[a]))
        for _, a, b in pairs
    ]

    reach_cache: Dict[Tuple[str, str], Any] = {}

    def reach_for(eid: str, kind: str):
        key = (eid, kind)
        if key not in reach_cache:
            v = views[eid]
            dag = v.chronos_dag if kind == "chronos" else v.declared_dag
            reach_cache[key] = reachability(dag) if len(v.ids) <= reach_limit else None
        return reach_cache[key]

    def ordered_by_reach(reach, a: str, b: str) -> Optional[bool]:
        if reach is None:
            return None
        idx, anc = reach
        if a not in idx or b not in idx:
            return None
        return bool((anc[b] >> idx[a]) & 1 or (anc[a] >> idx[b]) & 1)

    chronos_pred: List[Optional[bool]] = []
    declared_pred: List[Optional[bool]] = []
    for eid, a, b in pairs:
        ea, eb = views[eid].seen[a], views[eid].seen[b]
        if ea.vector_clock and eb.vector_clock:
            chronos_pred.append(not (true_precedes(ea, eb) or true_precedes(eb, ea)))
        else:
            o = ordered_by_reach(reach_for(eid, "chronos"), a, b)
            chronos_pred.append(None if o is None else not o)
        o = ordered_by_reach(reach_for(eid, "declared"), a, b)
        declared_pred.append(None if o is None else not o)

    total_order = [False] * len(pairs)
    out = {
        "arrival_order": _confusion(total_order, truth),
        "wall_clock": _confusion(total_order, truth),
        "declared_only": _confusion(declared_pred, truth),
        "chronosmesh": _confusion(chronos_pred, truth),
    }

    # ── Event-ordering accuracy: for truly ordered pairs (a -> b), does the approach put a before b? ──
    arrival_pos = {eid: {i: k for k, i in enumerate(v.ids)} for eid, v in views.items()}
    wall_pos = {eid: {i: k for k, i in enumerate(sorted(v.ids, key=lambda x: v.seen[x].timestamp_ms))}
                for eid, v in views.items()}
    right = {k: 0 for k in out}
    seen_pairs = {k: 0 for k in out}
    for (eid, a, b), is_conc in zip(pairs, truth):
        if is_conc:
            continue
        first, second = (a, b) if true_precedes(truth_events[a], truth_events[b]) else (b, a)
        ap, wp = arrival_pos[eid], wall_pos[eid]
        right["arrival_order"] += ap[first] < ap[second]
        right["wall_clock"] += wp[first] < wp[second]
        seen_pairs["arrival_order"] += 1
        seen_pairs["wall_clock"] += 1
        for key, kind in (("declared_only", "declared"), ("chronosmesh", "chronos")):
            reach = reach_for(eid, kind)
            ordered = ordered_by_reach(reach, first, second)
            if ordered is None:
                continue
            idx, anc = reach
            right[key] += bool((anc[second] >> idx[first]) & 1)       # first reaches second
            seen_pairs[key] += 1
    for key in out:
        out[key]["ordering_pairs"] = seen_pairs[key]
        out[key]["ordering_accuracy"] = right[key] / seen_pairs[key] if seen_pairs[key] else float("nan")
    return out
