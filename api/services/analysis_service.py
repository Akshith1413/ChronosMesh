"""
ChronosMesh API — Analysis Service Layer.

Provides deterministic calculations for:
1. Service Health (status: Healthy, Degraded, Critical, Unavailable)
2. Clock Drift Timeline (physical timestamps & causal edge skews; never subtracting Lamport integers from ms)
3. Latency Histogram (edge transit latency percentiles & bins)
4. Topology Stats (NetworkX DAG metrics, critical paths, concurrency)
5. Event Replay (causal layers via topological generations preserving concurrency)
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Set
import networkx as nx

from api.store import ChronosMeshStore
from api.schemas.analysis_models import (
    ServiceHealthItem,
    ServiceHealthReport,
    ClockDriftPoint,
    ClockDriftTimeline,
    LatencyBin,
    LatencyHistogramReport,
    LongestPathInfo,
    TopologyStatsReport,
    EventSummary,
    ReplayLayer,
    EventReplayReport,
)
from chronosmesh.analysis.anomaly import CausalAnomalyDetector


class AnalysisService:
    """Orchestrates analytics engines across DAG and event state."""

    @staticmethod
    def get_service_health(store: ChronosMeshStore) -> ServiceHealthReport:
        """
        Derives service health deterministically from loaded DAG events and detected anomalies.
        Statuses:
          - 'Critical': Service has at least 1 CRITICAL anomaly (e.g. cycle or severe drift).
          - 'Degraded': Service has WARNING anomalies (e.g. time inversion, duplicate) or low edge confidence.
          - 'Healthy': Service has events and 0 critical/warning anomalies.
          - 'Unavailable': Service has 0 recorded events.
        """
        events = store.events
        dag = store.dag

        # Collect distinct services from events and from node attributes
        service_names: Set[str] = set()
        for e in events:
            if e.service_id:
                service_names.add(e.service_id)
        for n, data in dag.nodes(data=True):
            svc = data.get("service_id")
            if svc:
                service_names.add(svc)

        # Detect anomalies on current state
        detector = CausalAnomalyDetector(clock_skew_tolerance_ms=50.0, max_clock_drift_ms=500.0)
        anomalies = detector.detect_all(dag, events) if events else []

        # Map anomalies by service
        event_service_map = {e.event_id: e.service_id for e in events}
        service_critical_count: Dict[str, int] = {s: 0 for s in service_names}
        service_warning_count: Dict[str, int] = {s: 0 for s in service_names}
        service_total_anomalies: Dict[str, int] = {s: 0 for s in service_names}

        for a in anomalies:
            source_svc = event_service_map.get(a.source_event_id)
            target_svc = event_service_map.get(a.target_event_id) if a.target_event_id else None
            affected = set(filter(None, [source_svc, target_svc]))

            for s in affected:
                if s in service_names:
                    service_total_anomalies[s] = service_total_anomalies.get(s, 0) + 1
                    if a.severity == "CRITICAL":
                        service_critical_count[s] = service_critical_count.get(s, 0) + 1
                    elif a.severity == "WARNING":
                        service_warning_count[s] = service_warning_count.get(s, 0) + 1

        # Calculate transit latencies touching each service
        event_dict = {e.event_id: e for e in events}
        service_latencies: Dict[str, List[float]] = {s: [] for s in service_names}
        for u, v in dag.edges():
            u_evt = event_dict.get(u)
            v_evt = event_dict.get(v)
            if u_evt and v_evt and v_evt.timestamp_ms >= u_evt.timestamp_ms:
                edge_lat = v_evt.timestamp_ms - u_evt.timestamp_ms
                if u_evt.service_id in service_latencies:
                    service_latencies[u_evt.service_id].append(edge_lat)
                if v_evt.service_id in service_latencies:
                    service_latencies[v_evt.service_id].append(edge_lat)

        items: List[ServiceHealthItem] = []
        healthy_count = 0
        degraded_count = 0
        critical_count = 0
        unavailable_count = 0

        for svc in sorted(service_names):
            svc_events = [e for e in events if e.service_id == svc]
            evt_count = len(svc_events)
            crit = service_critical_count.get(svc, 0)
            warn = service_warning_count.get(svc, 0)
            tot_anoms = service_total_anomalies.get(svc, 0)

            latest_activity: Optional[float] = (
                max(e.timestamp_ms for e in svc_events) if svc_events else None
            )

            lats = service_latencies.get(svc, [])
            avg_lat = round(sum(lats) / len(lats), 2) if lats else None

            if crit > 0:
                status = "Critical"
                critical_count += 1
            elif warn > 0:
                status = "Degraded"
                degraded_count += 1
            elif evt_count == 0:
                status = "Unavailable"
                unavailable_count += 1
            else:
                status = "Healthy"
                healthy_count += 1

            items.append(
                ServiceHealthItem(
                    service_name=svc,
                    status=status,
                    event_count=evt_count,
                    anomaly_count=tot_anoms,
                    latest_activity_ms=latest_activity,
                    avg_latency_ms=avg_lat,
                    details={
                        "critical_anomalies": crit,
                        "warning_anomalies": warn,
                    },
                )
            )

        return ServiceHealthReport(
            services=items,
            total_services=len(items),
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            critical_count=critical_count,
            unavailable_count=unavailable_count,
            timestamp_ms=time.time() * 1000.0,
        )

    @staticmethod
    def get_clock_drift_timeline(
        store: ChronosMeshStore, skew_tolerance_ms: float = 50.0
    ) -> ClockDriftTimeline:
        """
        Evaluates physical clock drift and arrival skew over the event sequence.
        NOTE: Lamport/Vector logical counters are NEVER subtracted from physical milliseconds.
        """
        events = store.events
        event_dict = {e.event_id: e for e in events}
        data_points: List[ClockDriftPoint] = []
        inversion_count = 0

        for e in events:
            arrival_skew = e.arrival_time_ms - e.timestamp_ms

            # Causal skew relative to immediate parents in DAG
            causal_skew: Optional[float] = None
            is_inv = False

            if e.parent_event_ids:
                parent_skews: List[float] = []
                for pid in e.parent_event_ids:
                    p_evt = event_dict.get(pid)
                    if p_evt:
                        # Transit delta: child - parent
                        delta = e.timestamp_ms - p_evt.timestamp_ms
                        parent_skews.append(delta)
                        if delta < -skew_tolerance_ms:
                            is_inv = True
                if parent_skews:
                    causal_skew = round(sum(parent_skews) / len(parent_skews), 3)

            if is_inv:
                inversion_count += 1

            data_points.append(
                ClockDriftPoint(
                    event_id=e.event_id,
                    service_id=e.service_id,
                    timestamp_ms=e.timestamp_ms,
                    arrival_time_ms=e.arrival_time_ms,
                    arrival_skew_ms=round(arrival_skew, 3),
                    causal_skew_ms=causal_skew,
                    is_inversion=is_inv,
                    clock_type="physical",
                )
            )

        max_skew = (
            max(abs(dp.arrival_skew_ms) for dp in data_points) if data_points else 0.0
        )

        return ClockDriftTimeline(
            trace_id=store.current_scenario,
            data_points=data_points,
            max_arrival_skew_ms=round(max_skew, 3),
            inversion_count=inversion_count,
            skew_tolerance_ms=skew_tolerance_ms,
        )

    @staticmethod
    def get_latency_histogram(
        store: ChronosMeshStore, num_bins: int = 5
    ) -> LatencyHistogramReport:
        """
        Computes the distribution of positive edge transit latencies across causal edges.
        Safely isolates negative time inversions and handles single-node or empty DAGs.
        """
        dag = store.dag
        events = store.events
        event_dict = {e.event_id: e for e in events}

        valid_latencies: List[float] = []
        inversion_edge_count = 0

        for u, v in dag.edges():
            u_ts = (
                dag.nodes[u].get("timestamp_ms")
                or (event_dict[u].timestamp_ms if u in event_dict else None)
            )
            v_ts = (
                dag.nodes[v].get("timestamp_ms")
                or (event_dict[v].timestamp_ms if v in event_dict else None)
            )

            if u_ts is not None and v_ts is not None:
                delta = v_ts - u_ts
                if delta >= 0:
                    valid_latencies.append(round(delta, 3))
                else:
                    inversion_edge_count += 1

        if not valid_latencies:
            return LatencyHistogramReport(
                sample_size=0,
                inversion_edge_count=inversion_edge_count,
                bins=[],
                note=(
                    "No valid forward causal edges with timestamp pairs found."
                    if dag.number_of_edges() > 0
                    else "DAG has no edges."
                ),
            )

        valid_latencies.sort()
        n = len(valid_latencies)

        def percentile(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            idx = max(0, min(idx, n - 1))
            return valid_latencies[idx]

        min_val = valid_latencies[0]
        max_val = valid_latencies[-1]
        mean_val = round(sum(valid_latencies) / n, 3)

        # Build histogram bins
        bins: List[LatencyBin] = []
        if min_val == max_val:
            bins.append(
                LatencyBin(bin_start_ms=min_val, bin_end_ms=max_val, count=n)
            )
        else:
            bin_width = (max_val - min_val) / num_bins
            for i in range(num_bins):
                b_start = round(min_val + i * bin_width, 3)
                b_end = (
                    round(max_val, 3)
                    if i == num_bins - 1
                    else round(min_val + (i + 1) * bin_width, 3)
                )
                if i == num_bins - 1:
                    c = sum(1 for x in valid_latencies if b_start <= x <= b_end)
                else:
                    c = sum(1 for x in valid_latencies if b_start <= x < b_end)
                bins.append(LatencyBin(bin_start_ms=b_start, bin_end_ms=b_end, count=c))

        return LatencyHistogramReport(
            sample_size=n,
            p50_ms=percentile(0.50),
            p95_ms=percentile(0.95),
            p99_ms=percentile(0.99),
            min_ms=min_val,
            max_ms=max_val,
            mean_ms=mean_val,
            bins=bins,
            inversion_edge_count=inversion_edge_count,
        )

    @staticmethod
    def get_topology_stats(store: ChronosMeshStore) -> TopologyStatsReport:
        """
        NetworkX graph-theoretic analysis of the causal DAG.
        Handles empty, disconnected, and single-node DAGs gracefully.
        """
        dag = store.dag
        node_count = dag.number_of_nodes()
        edge_count = dag.number_of_edges()

        if node_count == 0:
            return TopologyStatsReport(
                node_count=0,
                edge_count=0,
                density=0.0,
                is_connected=False,
                connected_components=0,
                root_nodes=[],
                leaf_nodes=[],
                longest_causal_path=LongestPathInfo(length=0, path=[], duration_ms=0.0),
                coupling_metric=0.0,
                concurrency_pairs_count=0,
                concurrency_ratio=0.0,
            )

        density = round(nx.density(dag), 4) if node_count > 1 else 0.0
        is_conn = nx.is_weakly_connected(dag) if node_count > 0 else False
        comp_count = nx.number_weakly_connected_components(dag) if node_count > 0 else 0

        roots = [n for n, d in dag.in_degree() if d == 0]
        leaves = [n for n, d in dag.out_degree() if d == 0]

        # Longest causal path
        path: List[str] = []
        duration_ms: Optional[float] = None
        if nx.is_directed_acyclic_graph(dag) and node_count > 0:
            try:
                path = nx.dag_longest_path(dag)
                if len(path) > 1:
                    first_node_ts = dag.nodes[path[0]].get("timestamp_ms", 0.0)
                    last_node_ts = dag.nodes[path[-1]].get("timestamp_ms", 0.0)
                    if last_node_ts >= first_node_ts:
                        duration_ms = round(last_node_ts - first_node_ts, 3)
            except Exception:
                path = []

        # Coupling metric: 2 * E / V
        coupling = round(2.0 * edge_count / max(1, node_count), 3)

        # Concurrency pairs detection (unordered pairs without reachability)
        nodes_list = list(dag.nodes())
        n = len(nodes_list)
        total_possible_pairs = n * (n - 1) // 2
        concurrency_pairs = 0

        if total_possible_pairs > 0 and nx.is_directed_acyclic_graph(dag):
            # Compute transitive closure or reachability
            for i in range(n):
                u = nodes_list[i]
                desc_u = nx.descendants(dag, u)
                for j in range(i + 1, n):
                    v = nodes_list[j]
                    if v not in desc_u and u not in nx.descendants(dag, v):
                        concurrency_pairs += 1

        concurrency_ratio = (
            round(concurrency_pairs / total_possible_pairs, 4)
            if total_possible_pairs > 0
            else 0.0
        )

        return TopologyStatsReport(
            node_count=node_count,
            edge_count=edge_count,
            density=density,
            is_connected=is_conn,
            connected_components=comp_count,
            root_nodes=roots,
            leaf_nodes=leaves,
            longest_causal_path=LongestPathInfo(
                length=len(path), path=path, duration_ms=duration_ms
            ),
            coupling_metric=coupling,
            concurrency_pairs_count=concurrency_pairs,
            concurrency_ratio=concurrency_ratio,
        )

    @staticmethod
    def get_event_replay(store: ChronosMeshStore) -> EventReplayReport:
        """
        Reconstructs execution in causal layers via DAG topological generations.
        Events within the same layer are causally concurrent and execute in parallel.
        """
        dag = store.dag
        events = store.events
        event_dict = {e.event_id: e for e in events}

        if dag.number_of_nodes() == 0 or not nx.is_directed_acyclic_graph(dag):
            # Fallback for empty or non-DAG
            return EventReplayReport(
                total_layers=0,
                total_events=0,
                max_parallelism=0,
                layers=[],
            )

        generations = list(nx.topological_generations(dag))
        layers: List[ReplayLayer] = []
        max_parallelism = 0
        total_evts = 0

        for idx, gen in enumerate(generations):
            layer_events: List[EventSummary] = []
            for nid in gen:
                evt = event_dict.get(nid)
                if evt:
                    summary = EventSummary(
                        event_id=evt.event_id,
                        service_id=evt.service_id,
                        event_type=evt.event_type,
                        timestamp_ms=evt.timestamp_ms,
                        lamport_ts=evt.lamport_ts,
                        parents=evt.parent_event_ids,
                    )
                else:
                    node_data = dag.nodes[nid]
                    summary = EventSummary(
                        event_id=nid,
                        service_id=node_data.get("service_id", "unknown"),
                        event_type=node_data.get("event_type", "EVENT"),
                        timestamp_ms=node_data.get("timestamp_ms", 0.0),
                        lamport_ts=node_data.get("lamport_ts", 0),
                        parents=list(dag.predecessors(nid)),
                    )
                layer_events.append(summary)

            count = len(layer_events)
            total_evts += count
            if count > max_parallelism:
                max_parallelism = count

            layers.append(
                ReplayLayer(
                    layer_index=idx + 1,
                    events=layer_events,
                    concurrent_count=count,
                )
            )

        return EventReplayReport(
            total_layers=len(layers),
            total_events=total_evts,
            max_parallelism=max_parallelism,
            layers=layers,
        )
