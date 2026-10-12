"""
ChronosMesh API – State Store.

Provides seamless dual-mode state management:
- DATA_SOURCE=demo (default): In-memory NetworkX DAG backed by Scenario Catalogue
- DATA_SOURCE=live: Live Neo4j Graph Database persistence and real-time Kafka event streaming
"""

import sys
import os
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set

import networkx as nx
from fastapi import Request

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.storage.neo4j_store import Neo4jStore

logger = logging.getLogger("chronosmesh.store")


def _extract_region(metadata_val) -> str:
    """Safely extract region from EventMetadata dict or object."""
    if isinstance(metadata_val, dict):
        return metadata_val.get("region", "unknown")
    return getattr(metadata_val, "region", "unknown")


def _extract_uncertainty(metadata_val) -> float:
    if isinstance(metadata_val, dict):
        return metadata_val.get("clock_uncertainty_ms", 5.0)
    return getattr(metadata_val, "clock_uncertainty_ms", 5.0)


class ChronosMeshStore:
    """Dual-mode state store for ChronosMesh API sessions.

    ``isolated=True`` creates a private, in-memory store for one user (used when a user opens one of their
    own executions in the Trace Explorer) so that no other user can read it through the legacy endpoints.
    """

    def __init__(self, isolated: bool = False) -> None:
        self.isolated = isolated
        self.data_source: str = "demo" if isolated else os.getenv("DATA_SOURCE", "demo").lower()
        self.events: List[Event] = []
        self.arrival_order: List[str] = []   # event_ids as they "arrived"
        self._builder = CausalDAGBuilder()
        self.dag: nx.DiGraph = nx.DiGraph()
        self.current_scenario: Optional[str] = None
        
        # Neo4j persistence layer (isolated stores never touch the shared graph database)
        self.neo4j = Neo4jStore(force_in_memory=True) if isolated else Neo4jStore()

        # Listeners for real-time SSE event dispatching
        self._event_listeners: List[Callable[[Dict[str, Any]], None]] = []

    # ── Mutation ─────────────────────────────────────────────────────────────────
    def load_scenario(self, name: str, events: List[Event], arrival_order: List[str]):
        self.events = list(events)
        self.arrival_order = list(arrival_order)
        self.current_scenario = name
        self._rebuild()

        # Mirror into Neo4j
        for e in events:
            self.neo4j.save_event(e)

    def add_events(self, events: List[Event]):
        self.events.extend(events)
        self.arrival_order.extend(e.event_id for e in events)
        self._rebuild()

        # Mirror into Neo4j
        for e in events:
            self.neo4j.save_event(e)

    def ingest_live_event(self, event: Event):
        """Ingest a single live event from Kafka/Flink streaming pipeline."""
        self.events.append(event)
        self.arrival_order.append(event.event_id)
        self._builder.build_incremental(event)
        self.dag = self._builder.get_dag()

        # Save to Neo4j
        self.neo4j.save_event(event)

        # Notify active SSE subscribers
        event_dict = event.to_dict()
        for listener in list(self._event_listeners):
            try:
                listener(event_dict)
            except Exception as e:
                logger.error(f"Error notifying SSE listener: {e}")

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        self._event_listeners.append(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], None]):
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def clear(self):
        self.events = []
        self.arrival_order = []
        self.current_scenario = None
        self.dag = nx.DiGraph()
        self._builder = CausalDAGBuilder()
        self.neo4j.clear()

    def _rebuild(self):
        if not self.events:
            self.dag = nx.DiGraph()
            return
        try:
            self._builder = CausalDAGBuilder()
            self._builder.build(self.events)
            self.dag = self._builder.get_dag()
            logger.info(
                "DAG rebuilt: %d nodes, %d edges",
                self.dag.number_of_nodes(),
                self.dag.number_of_edges(),
            )
        except Exception as exc:
            logger.error("DAG rebuild failed: %s", exc)
            self.dag = nx.DiGraph()

    # ── Serialisation helpers ────────────────────────────────────────────────────
    def get_dag_json(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Return DAG as node/edge JSON suitable for D3.js."""
        # If in live mode and querying specific trace backed by Neo4j
        if self.data_source == "live" and self.neo4j.is_connected() and trace_id:
            neo4j_dag = self.neo4j.get_dag(trace_id)
            if neo4j_dag["nodes"]:
                return neo4j_dag

        nodes = []
        for nid in self.dag.nodes():
            d = self.dag.nodes[nid]
            nodes.append(
                {
                    "id": nid,
                    "service_id": d.get("service_id", "unknown"),
                    "event_type": d.get("event_type", "unknown"),
                    "timestamp_ms": d.get("timestamp_ms", 0.0),
                    "lamport_ts": d.get("lamport_ts", 0),
                    "vector_clock": d.get("vector_clock", {}),
                    "region": _extract_region(d.get("metadata", {})),
                    "clock_uncertainty_ms": _extract_uncertainty(d.get("metadata", {})),
                    "parent_event_ids": d.get("parent_event_ids", []),
                }
            )

        edges = []
        for u, v, edata in self.dag.edges(data=True):
            edges.append(
                {
                    "source": u,
                    "target": v,
                    "explicit": edata.get("explicit", False),
                    "confidence": edata.get("confidence", 1.0),
                }
            )

        return {
            "nodes": nodes,
            "edges": edges,
            "topological_order": self._safe_topo(),
            "roots": self._builder.get_roots() if self.events else [],
            "leaves": self._builder.get_leaves() if self.events else [],
        }

    def get_events_json(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.data_source == "live" and self.neo4j.is_connected() and trace_id:
            live_trace = self.neo4j.get_trace(trace_id)
            if live_trace:
                return live_trace
        return [e.to_dict() for e in self.events]

    def get_arrival_order_json(self) -> List[Dict[str, Any]]:
        """Return events in the order they 'arrived' (simulated Kafka arrival)."""
        eid_to_event = {e.event_id: e for e in self.events}
        return [
            eid_to_event[eid].to_dict()
            for eid in self.arrival_order
            if eid in eid_to_event
        ]

    def _safe_topo(self) -> List[str]:
        try:
            return list(nx.topological_sort(self.dag))
        except Exception:
            return []

    def get_causal_order(self) -> List[Dict[str, Any]]:
        """Events in reconstructed (topological) causal order."""
        by_id = {e.event_id: e.to_dict() for e in self.events}
        return [by_id[eid] for eid in self._safe_topo() if eid in by_id]

    def get_concurrency_pairs(self, limit: int = 1000) -> List[List[str]]:
        """Unordered pairs of events with no causal path between them (E_a || E_b)."""
        ids = list(self.dag.nodes)
        reach = {n: nx.descendants(self.dag, n) for n in ids}
        pairs: List[List[str]] = []
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if b not in reach[a] and a not in reach[b]:
                    pairs.append([a, b])
                    if len(pairs) >= limit:
                        return pairs
        return pairs

    # ── Graph Traversal Helpers (Neo4j / NetworkX) ──────────────────────────────
    def get_ancestors(self, event_id: str) -> List[Dict[str, Any]]:
        """Return causal ancestors of event_id."""
        if self.data_source == "live" and self.neo4j.is_connected():
            return self.neo4j.get_ancestors(event_id)
        
        if event_id not in self.dag:
            return []
        ancestor_ids = nx.ancestors(self.dag, event_id)
        eid_to_event = {e.event_id: e.to_dict() for e in self.events}
        return [eid_to_event[aid] for aid in ancestor_ids if aid in eid_to_event]

    def get_descendants(self, event_id: str) -> List[Dict[str, Any]]:
        """Return causal descendants of event_id."""
        if self.data_source == "live" and self.neo4j.is_connected():
            return self.neo4j.get_descendants(event_id)

        if event_id not in self.dag:
            return []
        descendant_ids = nx.descendants(self.dag, event_id)
        eid_to_event = {e.event_id: e.to_dict() for e in self.events}
        return [eid_to_event[did] for did in descendant_ids if did in eid_to_event]

    def get_concurrent_events(self, event_id: str) -> List[Dict[str, Any]]:
        """Return concurrent events (no causal path) within the same trace."""
        if self.data_source == "live" and self.neo4j.is_connected():
            return self.neo4j.get_concurrent_events(event_id)

        if event_id not in self.dag:
            return []
        ancestors = nx.ancestors(self.dag, event_id)
        descendants = nx.descendants(self.dag, event_id)
        causal_set = ancestors | descendants | {event_id}

        eid_to_event = {e.event_id: e.to_dict() for e in self.events}
        return [eid_to_event[eid] for eid in self.dag.nodes if eid not in causal_set and eid in eid_to_event]


# ── Stores ───────────────────────────────────────────────────────────────────────
# One shared demo store (scenario catalogue content, not sensitive) plus a private store per user who has
# opened one of their own executions. State is per process: behind several replicas the load balancer uses
# cookie stickiness so a browser keeps talking to the replica that holds its explorer state.
_store: Optional[ChronosMeshStore] = None
_user_stores: Dict[str, ChronosMeshStore] = {}
_stores_lock = threading.Lock()


def _username_from_request(request: Any) -> Optional[str]:
    """Best-effort identity from the Bearer header or the ``token`` query parameter (EventSource)."""
    from jose import JWTError, jwt

    from api.auth import ALGORITHM, SECRET_KEY

    token = None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:]
    token = token or request.query_params.get("token")
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except JWTError:
        return None


def user_store(username: str) -> ChronosMeshStore:
    """The private explorer store for ``username`` (created on first use)."""
    with _stores_lock:
        if username not in _user_stores:
            _user_stores[username] = ChronosMeshStore(isolated=True)
        return _user_stores[username]


def get_store(request: Request = None) -> ChronosMeshStore:
    """FastAPI dependency: the caller's private store if they have one, else the shared demo store."""
    global _store
    if request is not None:
        username = _username_from_request(request)
        if username and username in _user_stores:
            return _user_stores[username]
    if _store is None:
        _store = ChronosMeshStore()
    return _store
