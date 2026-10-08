"""
ChronosMesh PostgreSQL / DynamoDB Metadata Store.

Provides relational and document-oriented storage for microservice configurations,
multi-region topology, clock uncertainty parameters, and trace configurations.
"""

import json
import logging
import sqlite3
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetadataStore:
    """
    CRUD repository for service topology, cloud regions, clock settings,
    and trace execution metadata. Operates as an in-memory SQL store for
    standalone testing and maps to PostgreSQL / AWS DynamoDB in cloud deployments.
    """

    def __init__(self, connection_uri: Optional[str] = None) -> None:
        self.connection_uri = connection_uri
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        self._seed_default_topology()

    def _init_tables(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            # Service topology table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS service_configs (
                    service_id TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    availability_zone TEXT NOT NULL,
                    clock_uncertainty_ms REAL NOT NULL,
                    max_allowed_drift_ms REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at REAL NOT NULL,
                    metadata_json TEXT
                )
                """
            )
            # Trace configuration table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_configs (
                    trace_id TEXT PRIMARY KEY,
                    scenario_name TEXT NOT NULL,
                    clock_strategy TEXT NOT NULL,
                    expected_node_count INTEGER,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    completed_at REAL
                )
                """
            )
            self._conn.commit()

    def _seed_default_topology(self) -> None:
        """Seeds default multi-cloud microservices (AWS Mumbai/Singapore, GCP Mumbai/Singapore)."""
        defaults = [
            ("order-svc", "aws-mumbai", "ap-south-1a", 4.0, 50.0),
            ("payment-svc", "aws-singapore", "ap-southeast-1a", 8.0, 100.0),
            ("inventory-svc", "gcp-mumbai", "asia-south1-a", 6.0, 60.0),
            ("shipping-svc", "gcp-singapore", "asia-southeast1-a", 9.0, 120.0),
            ("notification-svc", "aws-mumbai", "ap-south-1b", 5.0, 50.0),
        ]
        import time
        now = time.time()
        for svc_id, region, az, uncertainty, drift in defaults:
            self.upsert_service_config(
                service_id=svc_id,
                region=region,
                availability_zone=az,
                clock_uncertainty_ms=uncertainty,
                max_allowed_drift_ms=drift,
                status="ACTIVE",
                metadata={"seeded": True},
            )

    # ------------------ CRUD for Service Configs ------------------ #

    def upsert_service_config(
        self,
        service_id: str,
        region: str,
        availability_zone: str,
        clock_uncertainty_ms: float,
        max_allowed_drift_ms: float = 50.0,
        status: str = "ACTIVE",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create or Update service metadata."""
        import time
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO service_configs (
                    service_id, region, availability_zone,
                    clock_uncertainty_ms, max_allowed_drift_ms, status,
                    created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(service_id) DO UPDATE SET
                    region = excluded.region,
                    availability_zone = excluded.availability_zone,
                    clock_uncertainty_ms = excluded.clock_uncertainty_ms,
                    max_allowed_drift_ms = excluded.max_allowed_drift_ms,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json
                """,
                (
                    service_id,
                    region,
                    availability_zone,
                    clock_uncertainty_ms,
                    max_allowed_drift_ms,
                    status,
                    now,
                    json.dumps(metadata or {}),
                ),
            )
            self._conn.commit()

        return self.get_service_config(service_id)  # type: ignore

    def get_service_config(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Read single service metadata."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM service_configs WHERE service_id = ?", (service_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
            return data

    def list_all_services(self) -> List[Dict[str, Any]]:
        """List all registered microservices in the topology."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM service_configs ORDER BY service_id ASC")
            rows = cur.fetchall()
            results = []
            for row in rows:
                data = dict(row)
                data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
                results.append(data)
            return results

    def delete_service_config(self, service_id: str) -> bool:
        """Delete service config."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM service_configs WHERE service_id = ?", (service_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # ------------------ CRUD for Trace Configs ------------------ #

    def save_trace_config(
        self,
        trace_id: str,
        scenario_name: str,
        clock_strategy: str = "vector",
        expected_node_count: int = 0,
        status: str = "IN_PROGRESS",
    ) -> None:
        """Store trace execution metadata."""
        import time
        now = time.time()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO trace_configs (
                    trace_id, scenario_name, clock_strategy,
                    expected_node_count, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (trace_id, scenario_name, clock_strategy, expected_node_count, status, now),
            )
            self._conn.commit()

    def get_trace_config(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve trace configuration and status."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM trace_configs WHERE trace_id = ?", (trace_id,))
            row = cur.fetchone()
            return dict(row) if row else None
