"""
ChronosMesh Neo4j Graph Database Integration.

Implements graph persistence for distributed events, causal relationships,
and transitive dependency traversal according to docs/NEO4J_SCHEMA.md.
Provides automatic in-memory fallback if the Neo4j instance is unreachable.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from chronosmesh.events.event import Event, EventMetadata

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase, Driver
    NEO4J_DRIVER_AVAILABLE = True
except ImportError:
    NEO4J_DRIVER_AVAILABLE = False


class Neo4jStore:
    """Production Neo4j persistence layer for ChronosMesh causal graphs."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "chronosmesh2026")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")

        self.driver: Optional[Any] = None
        self._connected = False
        
        # Local mirror cache / fallback store for offline resiliency
        self._in_memory_events: Dict[str, Dict[str, Any]] = {}
        self._in_memory_edges: List[Dict[str, Any]] = []

        force_in_memory = os.getenv("CHRONOSMESH_FORCE_IN_MEMORY_NEO4J", "false").lower() in ("true", "1")
        if force_in_memory or not NEO4J_DRIVER_AVAILABLE:
            logger.info("Using Neo4j in-memory simulation store.")
            return

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_lifetime=300,
            )
            # Test connectivity
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")
            self.init_schema()
        except Exception as exc:
            logger.warning(f"Could not connect to Neo4j ({exc}). Using in-memory graph fallback.")
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def init_schema(self) -> None:
        """Create indexes and constraints as defined in docs/NEO4J_SCHEMA.md."""
        if not self._connected or not self.driver:
            return

        queries = [
            "CREATE CONSTRAINT event_id_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
            "CREATE CONSTRAINT scenario_id_unique IF NOT EXISTS FOR (s:Scenario) REQUIRE s.scenario_id IS UNIQUE",
            "CREATE CONSTRAINT service_id_unique IF NOT EXISTS FOR (sv:Service) REQUIRE sv.service_id IS UNIQUE",
            "CREATE INDEX event_trace_idx IF NOT EXISTS FOR (e:Event) ON (e.trace_id)",
            "CREATE INDEX event_timestamp_idx IF NOT EXISTS FOR (e:Event) ON (e.timestamp_ms)",
            "CREATE INDEX event_service_idx IF NOT EXISTS FOR (e:Event) ON (e.service_id)",
        ]
        try:
            with self.driver.session(database=self.database) as session:
                for q in queries:
                    session.run(q)
            logger.info("Neo4j constraints and indexes ensured.")
        except Exception as e:
            logger.warning(f"Error applying Neo4j schema migrations: {e}")

    # ── Persistence Operations ───────────────────────────────────────────────────

    def save_event(self, event: Event) -> bool:
        """Persist a single event node in Neo4j."""
        hlc_pt = 0.0
        hlc_l = 0
        if event.hlc_ts:
            if isinstance(event.hlc_ts, dict):
                hlc_pt = float(event.hlc_ts.get("pt", 0.0))
                hlc_l = int(event.hlc_ts.get("l", 0))
            elif isinstance(event.hlc_ts, (tuple, list)) and len(event.hlc_ts) >= 2:
                hlc_pt = float(event.hlc_ts[0])
                hlc_l = int(event.hlc_ts[1])

        region = "unknown"
        uncertainty_ms = 5.0
        tags = {}
        if hasattr(event.metadata, "region"):
            region = event.metadata.region
            uncertainty_ms = event.metadata.clock_uncertainty_ms
            tags = event.metadata.tags
        elif isinstance(event.metadata, dict):
            region = event.metadata.get("region", "unknown")
            uncertainty_ms = event.metadata.get("clock_uncertainty_ms", 5.0)
            tags = event.metadata.get("tags", {})

        ev_dict = {
            "event_id": event.event_id,
            "service_id": event.service_id,
            "event_type": event.event_type,
            "timestamp_ms": float(event.timestamp_ms),
            "arrival_time_ms": float(event.arrival_time_ms),
            "lamport_ts": int(event.lamport_ts),
            "vector_clock": json.dumps(event.vector_clock),
            "hlc_pt": hlc_pt,
            "hlc_l": hlc_l,
            "trace_id": event.trace_id,
            "span_id": event.span_id,
            "region": region,
            "clock_uncertainty_ms": uncertainty_ms,
            "parent_event_ids": event.parent_event_ids,
            "payload": json.dumps(event.payload),
            "tags": json.dumps(tags),
        }

        # Keep in local mirror cache for fallback
        self._in_memory_events[event.event_id] = ev_dict

        if not self._connected or not self.driver:
            # Wire up explicit parent edges in memory
            for pid in event.parent_event_ids:
                self.save_causal_edge(pid, event.event_id, confidence=1.0, explicit=True)
            return True

        cypher = """
        MERGE (e:Event {event_id: $event_id})
        SET e.service_id = $service_id,
            e.event_type = $event_type,
            e.timestamp_ms = $timestamp_ms,
            e.arrival_time_ms = $arrival_time_ms,
            e.lamport_ts = $lamport_ts,
            e.vector_clock = $vector_clock,
            e.hlc_pt = $hlc_pt,
            e.hlc_l = $hlc_l,
            e.trace_id = $trace_id,
            e.span_id = $span_id,
            e.region = $region,
            e.clock_uncertainty_ms = $clock_uncertainty_ms,
            e.payload = $payload,
            e.tags = $tags
        RETURN e.event_id
        """
        try:
            with self.driver.session(database=self.database) as session:
                session.run(cypher, **ev_dict)
                
            # Connect explicit parent links
            for pid in event.parent_event_ids:
                self.save_causal_edge(pid, event.event_id, confidence=1.0, explicit=True)
            return True
        except Exception as e:
            logger.error(f"Neo4j save_event failed for {event.event_id}: {e}")
            return False

    def save_causal_edge(
        self,
        source_id: str,
        target_id: str,
        confidence: float = 1.0,
        explicit: bool = True,
        method: str = "vector_clock",
        uncertainty_ms: float = 0.0,
    ) -> bool:
        """Create a directed :HAPPENS_BEFORE relationship between events."""
        edge_data = {
            "source": source_id,
            "target": target_id,
            "confidence": float(confidence),
            "explicit": bool(explicit),
            "method": method,
            "uncertainty_ms": float(uncertainty_ms),
        }

        # Deduplicate in-memory edges
        if not any(e["source"] == source_id and e["target"] == target_id for e in self._in_memory_edges):
            self._in_memory_edges.append(edge_data)

        if not self._connected or not self.driver:
            return True

        cypher = """
        MATCH (a:Event {event_id: $source})
        MATCH (b:Event {event_id: $target})
        MERGE (a)-[r:HAPPENS_BEFORE]->(b)
        SET r.confidence = $confidence,
            r.explicit = $explicit,
            r.method = $method,
            r.uncertainty_ms = $uncertainty_ms
        RETURN count(r)
        """
        try:
            with self.driver.session(database=self.database) as session:
                session.run(cypher, **edge_data)
            return True
        except Exception as e:
            logger.error(f"Neo4j save_causal_edge failed ({source_id} -> {target_id}): {e}")
            return False

    # ── Query Operations ─────────────────────────────────────────────────────────

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an event by ID."""
        if not self._connected or not self.driver:
            raw = self._in_memory_events.get(event_id)
            if not raw:
                return None
            return self._format_node_dict(raw)

        cypher = "MATCH (e:Event {event_id: $event_id}) RETURN e"
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run(cypher, event_id=event_id)
                record = res.single()
                if record:
                    return self._format_node_dict(dict(record["e"]))
        except Exception as e:
            logger.error(f"Neo4j get_event failed: {e}")
        return self._format_node_dict(self._in_memory_events.get(event_id))

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Retrieve all events belonging to a trace, ordered by timestamp."""
        if not self._connected or not self.driver:
            matches = [
                self._format_node_dict(ev)
                for ev in self._in_memory_events.values()
                if ev.get("trace_id") == trace_id
            ]
            return sorted(matches, key=lambda x: x.get("timestamp_ms", 0.0))

        cypher = """
        MATCH (e:Event {trace_id: $trace_id})
        RETURN e ORDER BY e.timestamp_ms ASC
        """
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run(cypher, trace_id=trace_id)
                return [self._format_node_dict(dict(rec["e"])) for rec in res]
        except Exception as e:
            logger.error(f"Neo4j get_trace failed: {e}")
            return []

    def get_dag(self, trace_id: str) -> Dict[str, Any]:
        """Return the D3-compliant Causal DAG for a trace."""
        events = self.get_trace(trace_id)
        if not events:
            return {"nodes": [], "edges": [], "topological_order": [], "roots": [], "leaves": []}

        event_ids = {e["id"] for e in events}

        if not self._connected or not self.driver:
            edges = [
                e for e in self._in_memory_edges
                if e["source"] in event_ids and e["target"] in event_ids
            ]
        else:
            cypher = """
            MATCH (a:Event {trace_id: $trace_id})-[r:HAPPENS_BEFORE]->(b:Event {trace_id: $trace_id})
            RETURN a.event_id AS source, b.event_id AS target, r.confidence AS confidence, r.explicit AS explicit
            """
            try:
                with self.driver.session(database=self.database) as session:
                    res = session.run(cypher, trace_id=trace_id)
                    edges = [
                        {
                            "source": rec["source"],
                            "target": rec["target"],
                            "confidence": rec.get("confidence", 1.0),
                            "explicit": rec.get("explicit", True),
                        }
                        for rec in res
                    ]
            except Exception as e:
                logger.error(f"Neo4j get_dag edges failed: {e}")
                edges = [
                    e for e in self._in_memory_edges
                    if e["source"] in event_ids and e["target"] in event_ids
                ]

        # Calculate roots and leaves
        sources = {e["source"] for e in edges}
        targets = {e["target"] for e in edges}
        roots = [eid for eid in event_ids if eid not in targets]
        leaves = [eid for eid in event_ids if eid not in sources]

        # Basic topological order fallback
        topo_order = [e["id"] for e in events]

        return {
            "nodes": events,
            "edges": edges,
            "topological_order": topo_order,
            "roots": roots,
            "leaves": leaves,
        }

    def get_ancestors(self, event_id: str, max_depth: int = 15) -> List[Dict[str, Any]]:
        """Retrieve causal ancestors (events that happened-before this event)."""
        if not self._connected or not self.driver:
            visited = set()
            queue = [event_id]
            ancestors = []
            while queue:
                curr = queue.pop(0)
                parents = [e["source"] for e in self._in_memory_edges if e["target"] == curr]
                for p in parents:
                    if p not in visited:
                        visited.add(p)
                        if p in self._in_memory_events:
                            ancestors.append(self._format_node_dict(self._in_memory_events[p]))
                        queue.append(p)
            return ancestors

        cypher = f"""
        MATCH (ancestor:Event)-[:HAPPENS_BEFORE*1..{max_depth}]->(target:Event {{event_id: $event_id}})
        RETURN DISTINCT ancestor ORDER BY ancestor.timestamp_ms ASC
        """
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run(cypher, event_id=event_id)
                return [self._format_node_dict(dict(rec["ancestor"])) for rec in res]
        except Exception as e:
            logger.error(f"Neo4j get_ancestors failed: {e}")
            return []

    def get_descendants(self, event_id: str, max_depth: int = 15) -> List[Dict[str, Any]]:
        """Retrieve causal descendants (events caused by this event)."""
        if not self._connected or not self.driver:
            visited = set()
            queue = [event_id]
            descendants = []
            while queue:
                curr = queue.pop(0)
                children = [e["target"] for e in self._in_memory_edges if e["source"] == curr]
                for c in children:
                    if c not in visited:
                        visited.add(c)
                        if c in self._in_memory_events:
                            descendants.append(self._format_node_dict(self._in_memory_events[c]))
                        queue.append(c)
            return descendants

        cypher = f"""
        MATCH (target:Event {{event_id: $event_id}})-[:HAPPENS_BEFORE*1..{max_depth}]->(descendant:Event)
        RETURN DISTINCT descendant ORDER BY descendant.timestamp_ms ASC
        """
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run(cypher, event_id=event_id)
                return [self._format_node_dict(dict(rec["descendant"])) for rec in res]
        except Exception as e:
            logger.error(f"Neo4j get_descendants failed: {e}")
            return []

    def get_concurrent_events(self, event_id: str) -> List[Dict[str, Any]]:
        """Find events within the same trace that have no causal path to/from event_id."""
        target_event = self.get_event(event_id)
        if not target_event:
            return []

        trace_id = target_event.get("trace_id")
        trace_events = self.get_trace(trace_id)
        if not trace_events:
            return []

        ancestors = {a["id"] for a in self.get_ancestors(event_id)}
        descendants = {d["id"] for d in self.get_descendants(event_id)}
        causally_linked = ancestors | descendants | {event_id}

        return [e for e in trace_events if e["id"] not in causally_linked]

    def clear(self) -> None:
        """Clear local cache and Neo4j database (for testing)."""
        self._in_memory_events.clear()
        self._in_memory_edges.clear()
        if self._connected and self.driver:
            try:
                with self.driver.session(database=self.database) as session:
                    session.run("MATCH (n:Event) DETACH DELETE n")
            except Exception as e:
                logger.warning(f"Neo4j clear failed: {e}")

    # ── Formatting Helper ────────────────────────────────────────────────────────

    def _format_node_dict(self, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not data:
            return {}
        eid = data.get("event_id") or data.get("id", "")
        vc = data.get("vector_clock", {})
        if isinstance(vc, str):
            try:
                vc = json.loads(vc)
            except Exception:
                vc = {}

        payload = data.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        return {
            "id": eid,
            "event_id": eid,
            "service_id": data.get("service_id", "unknown"),
            "event_type": data.get("event_type", "unknown"),
            "timestamp_ms": float(data.get("timestamp_ms", 0.0)),
            "arrival_time_ms": float(data.get("arrival_time_ms", 0.0)),
            "lamport_ts": int(data.get("lamport_ts", 0)),
            "vector_clock": vc,
            "hlc_ts": {"pt": data.get("hlc_pt", 0.0), "l": data.get("hlc_l", 0)},
            "trace_id": data.get("trace_id", ""),
            "span_id": data.get("span_id", ""),
            "region": data.get("region", "unknown"),
            "clock_uncertainty_ms": float(data.get("clock_uncertainty_ms", 5.0)),
            "parent_event_ids": data.get("parent_event_ids", []),
            "payload": payload,
        }
