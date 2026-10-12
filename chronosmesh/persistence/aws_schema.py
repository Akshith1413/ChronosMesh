"""DynamoDB table definitions -- the single source of truth used by tests, local bootstrap and docs.

The Terraform/CloudFormation templates in ``infrastructure/`` declare the same keys and indexes.
"""

from __future__ import annotations

from typing import Any, Dict, List

from chronosmesh.config import Settings


def table_specs(settings: Settings) -> List[Dict[str, Any]]:
    def s(name: str) -> Dict[str, str]:
        return {"AttributeName": name, "AttributeType": "S"}

    def n(name: str) -> Dict[str, str]:
        return {"AttributeName": name, "AttributeType": "N"}

    def key(name: str, kind: str) -> Dict[str, str]:
        return {"AttributeName": name, "KeyType": kind}

    def gsi(name: str, hash_key: str, range_key: str) -> Dict[str, Any]:
        return {"IndexName": name, "KeySchema": [key(hash_key, "HASH"), key(range_key, "RANGE")],
                "Projection": {"ProjectionType": "ALL"}}

    return [
        {"TableName": settings.ddb_executions_table, "BillingMode": "PAY_PER_REQUEST",
         "KeySchema": [key("execution_id", "HASH")],
         "AttributeDefinitions": [s("execution_id"), s("owner"), n("created_at_ms")],
         "GlobalSecondaryIndexes": [gsi("owner-created-index", "owner", "created_at_ms")]},
        {"TableName": settings.ddb_events_table, "BillingMode": "PAY_PER_REQUEST",
         "KeySchema": [key("execution_id", "HASH"), key("event_id", "RANGE")],
         "AttributeDefinitions": [s("execution_id"), s("event_id"), s("service_id"), n("event_time_ms")],
         "GlobalSecondaryIndexes": [gsi("service-time-index", "service_id", "event_time_ms")]},
        {"TableName": settings.ddb_anomalies_table, "BillingMode": "PAY_PER_REQUEST",
         "KeySchema": [key("execution_id", "HASH"), key("anomaly_id", "RANGE")],
         "AttributeDefinitions": [s("execution_id"), s("anomaly_id")]},
        {"TableName": settings.ddb_graphs_table, "BillingMode": "PAY_PER_REQUEST",
         "KeySchema": [key("graph_id", "HASH")],
         "AttributeDefinitions": [s("graph_id")]},
    ]


def create_tables(client, settings: Settings) -> List[str]:
    """Create any missing tables (idempotent). Returns names created."""
    existing = set()
    for page in client.get_paginator("list_tables").paginate():
        existing.update(page["TableNames"])
    created = []
    for spec in table_specs(settings):
        if not spec["TableName"] or spec["TableName"] in existing:
            continue
        client.create_table(**spec)
        client.get_waiter("table_exists").wait(TableName=spec["TableName"])
        client.update_time_to_live(TableName=spec["TableName"],
                                  TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"})
        created.append(spec["TableName"])
    return created
