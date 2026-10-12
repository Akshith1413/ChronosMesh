"""Runtime configuration, read from the environment (12-factor).

Everything AWS-related is optional: with no variables set the platform runs entirely
in memory, so the test-suite and a laptop need no cloud account.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    environment: str = "local"                       # local | production
    aws_region: str = "ap-south-2"
    storage_backend: str = "auto"                    # auto | memory | aws
    ddb_events_table: Optional[str] = None
    ddb_executions_table: Optional[str] = None
    ddb_anomalies_table: Optional[str] = None
    ddb_graphs_table: Optional[str] = None
    s3_data_bucket: Optional[str] = None
    sqs_events_queue_url: Optional[str] = None
    sqs_results_queue_url: Optional[str] = None
    ingest_mode: str = "inline"                      # inline | queue
    execution_ttl_days: int = 30
    max_experiment_events: int = 25_000
    max_execution_events: int = 100_000
    event_persist_max: int = 5_000                   # per-event DynamoDB writes up to this many events
    sample_executions_kept: int = 25
    metrics_namespace: str = "ChronosMesh"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("ENVIRONMENT", "local").lower(),
            aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-2",
            storage_backend=os.getenv("STORAGE_BACKEND", "auto").lower(),
            ddb_events_table=os.getenv("DYNAMODB_EVENTS_TABLE"),
            ddb_executions_table=os.getenv("DYNAMODB_EXEC_TABLE"),
            ddb_anomalies_table=os.getenv("DYNAMODB_ANOMALY_TABLE"),
            ddb_graphs_table=os.getenv("DYNAMODB_GRAPH_TABLE"),
            s3_data_bucket=os.getenv("S3_DATA_BUCKET"),
            sqs_events_queue_url=os.getenv("SQS_EVENTS_QUEUE_URL"),
            sqs_results_queue_url=os.getenv("SQS_RESULTS_QUEUE_URL"),
            ingest_mode=os.getenv("INGEST_MODE", "inline").lower(),
            execution_ttl_days=_int("EXECUTION_TTL_DAYS", 30),
            max_experiment_events=_int("MAX_EXPERIMENT_EVENTS", 25_000),
            max_execution_events=_int("MAX_EXECUTION_EVENTS", 100_000),
            event_persist_max=_int("EVENT_PERSIST_MAX", 5_000),
            sample_executions_kept=_int("SAMPLE_EXECUTIONS_KEPT", 25),
            metrics_namespace=os.getenv("METRICS_NAMESPACE", "ChronosMesh"),
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def use_aws_storage(self) -> bool:
        if self.storage_backend == "memory":
            return False
        if self.storage_backend == "aws":
            return True
        return bool(self.ddb_executions_table and self.s3_data_bucket)

    @property
    def use_queue(self) -> bool:
        return bool(self.sqs_events_queue_url) and self.ingest_mode == "queue"


def get_settings() -> Settings:
    return Settings.from_env()
