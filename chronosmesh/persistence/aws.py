"""DynamoDB + S3 repository.

Layout
------
* ``executions`` table  -- one item per experiment/execution (status, owner, config, summary).
  GSI ``owner-created-index`` serves "my executions, newest first".
* ``events`` table      -- raw events (kept for small executions); GSI ``service-time-index``
  serves per-service timelines. High-volume runs are archived to S3 only.
* ``anomalies`` table   -- one item per anomaly.
* ``graphs`` table      -- pointer + summary for the reconstructed graph.
* S3 ``executions/<id>/...`` -- graph JSON, experiment result, ground truth, ingest segments.

Every table carries an ``expires_at`` TTL attribute; S3 lifecycle rules (see IaC) expire objects.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from chronosmesh.config import Settings
from chronosmesh.persistence.base import TERMINAL_STATUSES
from chronosmesh.utils import dumps, to_jsonable

# Fields stored as first-class attributes (indexable / cheap to list). Every other field is stored as its
# own ``j_<name>`` attribute holding JSON, so concurrent writers (API thread, worker) can update different
# fields atomically instead of overwriting each other.
_CORE = ("execution_id", "owner", "name", "kind", "status", "parent_id", "progress", "message", "error",
         "created_at", "created_at_ms", "updated_at", "updated_at_ms")


def _num(v: Any) -> Any:
    if isinstance(v, float):
        return Decimal(str(v))
    return v


def _from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {}
    for k, v in item.items():
        if k == "expires_at":
            continue
        if k.startswith("j_"):
            rec[k[2:]] = json.loads(v)
        else:
            rec[k] = to_jsonable(v)
    return rec


class AwsRepository:
    backend = "aws"

    def __init__(self, settings: Settings, *, ddb=None, s3=None) -> None:
        self.settings = settings
        region = settings.aws_region
        self._ddb = ddb or boto3.resource("dynamodb", region_name=region)
        self._s3 = s3 or boto3.client("s3", region_name=region)
        self._bucket = settings.s3_data_bucket
        self.executions = self._ddb.Table(settings.ddb_executions_table)
        self.events = self._ddb.Table(settings.ddb_events_table) if settings.ddb_events_table else None
        self.anomalies = self._ddb.Table(settings.ddb_anomalies_table) if settings.ddb_anomalies_table else None
        self.graphs = self._ddb.Table(settings.ddb_graphs_table) if settings.ddb_graphs_table else None

    def _expires(self) -> int:
        return int(time.time()) + self.settings.execution_ttl_days * 86400

    # ── S3 helpers ───────────────────────────────────────────────────────────
    def _put_json(self, key: str, payload: Any, *, gz: Optional[bool] = None) -> str:
        body = dumps(payload).encode()
        extra: Dict[str, Any] = {"ContentType": "application/json", "ServerSideEncryption": "AES256"}
        if gz is None:                      # compress anything bigger than 100 KB
            gz = len(body) > 100_000
        if gz:
            body = gzip.compress(body)
            extra["ContentEncoding"] = "gzip"
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=body, **extra)
        return f"s3://{self._bucket}/{key}"

    def _get_json(self, key: str) -> Optional[Any]:
        try:
            body = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        return json.loads(body)

    # ── executions ───────────────────────────────────────────────────────────
    def put_execution(self, record: Dict[str, Any]) -> None:
        rec = to_jsonable(record)
        item: Dict[str, Any] = {k: _num(rec[k]) for k in _CORE if rec.get(k) is not None}
        for k, v in rec.items():
            if k not in _CORE:
                item[f"j_{k}"] = dumps(v)
        item["expires_at"] = self._expires()
        self.executions.put_item(Item=item)

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        item = self.executions.get_item(Key={"execution_id": execution_id}).get("Item")
        return _from_item(item) if item else None

    def update_execution(self, execution_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Atomic per-field update. Never resurrects a finished execution into an in-progress state."""
        fields = to_jsonable(fields)
        names: Dict[str, str] = {}
        values: Dict[str, Any] = {":exp": self._expires()}
        sets = ["expires_at = :exp"]
        for i, (k, v) in enumerate(fields.items()):
            names[f"#f{i}"] = k if k in _CORE else f"j_{k}"
            values[f":v{i}"] = _num(v) if k in _CORE else dumps(v)
            sets.append(f"#f{i} = :v{i}")
        condition = "attribute_exists(execution_id)"
        new_status = fields.get("status")
        if new_status is not None and new_status not in TERMINAL_STATUSES:
            names["#st"] = "status"
            values[":t1"], values[":t2"] = TERMINAL_STATUSES
            condition += " AND (attribute_not_exists(#st) OR NOT (#st IN (:t1, :t2)))"
        try:
            self.executions.update_item(Key={"execution_id": execution_id}, ConditionExpression=condition,
                                        UpdateExpression="SET " + ", ".join(sets),
                                        ExpressionAttributeNames=names, ExpressionAttributeValues=values)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
        return self.get_execution(execution_id)

    def list_executions(self, owner=None, *, limit=50, parent_id=None, include_children=False):
        if owner is not None:
            resp = self.executions.query(IndexName="owner-created-index",
                                         KeyConditionExpression=Key("owner").eq(owner),
                                         ScanIndexForward=False, Limit=max(limit * 4, 100))
            items = resp.get("Items", [])
        else:
            items, start = [], None
            while len(items) < 1000:
                kw = {"ExclusiveStartKey": start} if start else {}
                resp = self.executions.scan(Limit=500, **kw)
                items += resp.get("Items", [])
                start = resp.get("LastEvaluatedKey")
                if not start:
                    break
        rows = [_from_item(i) for i in items]
        if parent_id is not None:
            rows = [r for r in rows if r.get("parent_id") == parent_id]
        elif not include_children:
            rows = [r for r in rows if not r.get("parent_id")]
        rows.sort(key=lambda r: r.get("created_at_ms", 0), reverse=True)
        return rows[:limit]

    # ── events ───────────────────────────────────────────────────────────────
    def put_events(self, execution_id: str, events: List[Dict[str, Any]]) -> int:
        if self.events is None or not events:
            return 0
        expires = self._expires()
        with self.events.batch_writer(overwrite_by_pkeys=["execution_id", "event_id"]) as batch:
            for e in events:
                batch.put_item(Item={
                    "execution_id": execution_id,
                    "event_id": e["event_id"],
                    "service_id": e.get("service_id") or "unknown",
                    "event_type": e.get("event_type", ""),
                    "event_time_ms": Decimal(str(e.get("timestamp_ms", 0))),
                    "body": dumps(e),
                    "expires_at": expires,
                })
        return len(events)

    def get_events(self, execution_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.events is None:
            return []
        out: List[Dict[str, Any]] = []
        start = None
        while True:
            kw: Dict[str, Any] = {"KeyConditionExpression": Key("execution_id").eq(execution_id)}
            if start:
                kw["ExclusiveStartKey"] = start
            resp = self.events.query(**kw)
            out += [json.loads(i["body"]) for i in resp.get("Items", [])]
            start = resp.get("LastEvaluatedKey")
            if not start or (limit and len(out) >= limit):
                break
        return out[:limit] if limit else out

    # ── segments (durable ingest log) ────────────────────────────────────────
    def _seg_key(self, execution_id: str, seq: int) -> str:
        return f"executions/{execution_id}/segments/{seq:08d}.json.gz"

    def put_segment(self, execution_id: str, seq: int, events: List[Dict[str, Any]]) -> None:
        self._put_json(self._seg_key(execution_id, seq), events, gz=True)

    def list_segments(self, execution_id: str) -> List[int]:
        prefix = f"executions/{execution_id}/segments/"
        seqs: List[int] = []
        for page in self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                name = obj["Key"].rsplit("/", 1)[-1].split(".")[0]
                if name.isdigit():
                    seqs.append(int(name))
        return sorted(seqs)

    def get_segment(self, execution_id: str, seq: int) -> List[Dict[str, Any]]:
        return self._get_json(self._seg_key(execution_id, seq)) or []

    # ── derived artefacts ────────────────────────────────────────────────────
    @staticmethod
    def _anomaly_id(a: Dict[str, Any]) -> str:
        raw = f"{a.get('anomaly_type')}|{a.get('source_event_id')}|{a.get('target_event_id')}|{a.get('description')}"
        return hashlib.sha1(raw.encode()).hexdigest()[:20]

    def put_anomalies(self, execution_id: str, anomalies: List[Dict[str, Any]]) -> None:
        if self.anomalies is None:
            self.put_blob(execution_id, "anomalies", anomalies)
            return
        new = {self._anomaly_id(a): a for a in anomalies}
        existing: List[str] = []
        start = None
        while True:
            kw: Dict[str, Any] = {"KeyConditionExpression": Key("execution_id").eq(execution_id),
                                  "ProjectionExpression": "anomaly_id"}
            if start:
                kw["ExclusiveStartKey"] = start
            resp = self.anomalies.query(**kw)
            existing += [i["anomaly_id"] for i in resp.get("Items", [])]
            start = resp.get("LastEvaluatedKey")
            if not start:
                break
        expires = self._expires()
        with self.anomalies.batch_writer(overwrite_by_pkeys=["execution_id", "anomaly_id"]) as batch:
            for aid in existing:                      # drop anomalies that no longer apply (e.g. resolved parents)
                if aid not in new:
                    batch.delete_item(Key={"execution_id": execution_id, "anomaly_id": aid})
            for aid, a in new.items():
                batch.put_item(Item={"execution_id": execution_id, "anomaly_id": aid,
                                     "anomaly_type": a.get("anomaly_type", ""), "severity": a.get("severity", ""),
                                     "body": dumps(a), "expires_at": expires})

    def get_anomalies(self, execution_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.anomalies is None:
            return (self.get_blob(execution_id, "anomalies") or [])[:limit]
        out: List[Dict[str, Any]] = []
        start = None
        while True:
            kw: Dict[str, Any] = {"KeyConditionExpression": Key("execution_id").eq(execution_id)}
            if start:
                kw["ExclusiveStartKey"] = start
            resp = self.anomalies.query(**kw)
            out += [json.loads(i["body"]) for i in resp.get("Items", [])]
            start = resp.get("LastEvaluatedKey")
            if not start or (limit and len(out) >= limit):
                break
        return out[:limit] if limit else out

    def put_graph(self, execution_id: str, graph: Dict[str, Any]) -> str:
        key = f"executions/{execution_id}/graph.json"
        ref = self._put_json(key, graph)
        if self.graphs is not None:
            self.graphs.put_item(Item={
                "graph_id": execution_id, "s3_key": key,
                "nodes": graph.get("total_nodes", len(graph.get("nodes", []))),
                "edges": graph.get("total_edges", len(graph.get("edges", []))),
                "truncated": bool(graph.get("truncated")),
                "updated_at_ms": int(time.time() * 1000), "expires_at": self._expires(),
            })
        return ref

    def get_graph(self, execution_id: str) -> Optional[Dict[str, Any]]:
        return self._get_json(f"executions/{execution_id}/graph.json")

    def put_blob(self, execution_id: str, name: str, payload: Any) -> str:
        return self._put_json(f"executions/{execution_id}/{name}.json", payload)

    def get_blob(self, execution_id: str, name: str) -> Optional[Any]:
        return self._get_json(f"executions/{execution_id}/{name}.json")

    def health(self) -> Dict[str, Any]:
        try:
            self.executions.load()
            self._s3.head_bucket(Bucket=self._bucket)
            return {"backend": self.backend, "ok": True, "table": self.settings.ddb_executions_table,
                    "bucket": self._bucket}
        except Exception as exc:  # health must report, not raise
            return {"backend": self.backend, "ok": False, "error": type(exc).__name__}
