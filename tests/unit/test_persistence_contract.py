"""Both repository backends must behave identically (memory vs. DynamoDB + S3 under moto)."""

import boto3
import pytest
from moto import mock_aws

from chronosmesh.config import Settings
from chronosmesh.persistence import MemoryRepository
from chronosmesh.persistence.aws import AwsRepository
from chronosmesh.persistence.aws_schema import create_tables, table_specs

REGION = "ap-south-2"


def aws_settings(**kw) -> Settings:
    base = dict(aws_region=REGION, ddb_executions_table="t-exec", ddb_events_table="t-events",
                ddb_anomalies_table="t-anom", ddb_graphs_table="t-graph", s3_data_bucket="b-data")
    base.update(kw)
    return Settings(**base)


@pytest.fixture(params=["memory", "aws"])
def repo(request):
    if request.param == "memory":
        yield MemoryRepository()
        return
    with mock_aws():
        settings = aws_settings()
        create_tables(boto3.client("dynamodb", region_name=REGION), settings)
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket="b-data", CreateBucketConfiguration={"LocationConstraint": REGION})
        yield AwsRepository(settings)


def rec(eid, owner="alice", ts=1, **kw):
    r = {"execution_id": eid, "owner": owner, "name": eid, "kind": "live", "status": "created",
         "created_at_ms": ts, "progress": 0.0, "config": {"nested": {"a": [1, 2.5]}}}
    r.update(kw)
    return r


def test_execution_roundtrip_and_update(repo):
    repo.put_execution(rec("e1"))
    got = repo.get_execution("e1")
    assert got["owner"] == "alice" and got["config"] == {"nested": {"a": [1, 2.5]}}
    upd = repo.update_execution("e1", status="running", progress=0.5, stats={"events": 3})
    assert upd["status"] == "running" and upd["stats"] == {"events": 3} and upd["progress"] == 0.5
    assert repo.get_execution("e1")["config"] == {"nested": {"a": [1, 2.5]}}   # untouched fields survive
    assert repo.get_execution("missing") is None and repo.update_execution("missing", status="x") is None


def test_list_executions_filters_owner_children_and_order(repo):
    repo.put_execution(rec("old", ts=1))
    repo.put_execution(rec("new", ts=3))
    repo.put_execution(rec("bobs", owner="bob", ts=2))
    repo.put_execution(rec("child", ts=4, parent_id="new", kind="sample"))
    assert [r["execution_id"] for r in repo.list_executions("alice")] == ["new", "old"]
    assert [r["execution_id"] for r in repo.list_executions("bob")] == ["bobs"]
    assert {r["execution_id"] for r in repo.list_executions(None)} == {"old", "new", "bobs"}
    assert [r["execution_id"] for r in repo.list_executions("alice", parent_id="new")] == ["child"]
    assert [r["execution_id"] for r in repo.list_executions("alice", limit=1)] == ["new"]


def test_events_are_idempotent_by_event_id(repo):
    ev = lambda i: {"event_id": f"e{i}", "service_id": "svc", "event_type": "T", "timestamp_ms": 1000.5 + i}
    repo.put_events("x", [ev(1), ev(2)])
    repo.put_events("x", [ev(2), ev(3)])           # e2 re-sent
    assert sorted(e["event_id"] for e in repo.get_events("x")) == ["e1", "e2", "e3"]
    assert len(repo.get_events("x", limit=2)) == 2
    assert repo.get_events("nothing") == []


def test_segments_are_ordered_and_replayable(repo):
    repo.put_segment("s", 7, [{"event_id": "a"}])
    repo.put_segment("s", 2, [{"event_id": "b"}, {"event_id": "c"}])
    assert repo.list_segments("s") == [2, 7]
    assert [e["event_id"] for e in repo.get_segment("s", 2)] == ["b", "c"]
    assert repo.get_segment("s", 99) == [] and repo.list_segments("other") == []
    repo.put_segment("s", 2, [{"event_id": "b"}, {"event_id": "c"}])    # rewriting is harmless
    assert repo.list_segments("s") == [2, 7]


def test_anomalies_replace_not_accumulate(repo):
    a = lambda t, s: {"anomaly_type": t, "severity": "WARNING", "source_event_id": s, "target_event_id": None,
                      "description": f"{t} {s}", "details": {}}
    repo.put_anomalies("x", [a("UNRESOLVED_PARENT", "e1"), a("DUPLICATE_EVENT", "e2")])
    repo.put_anomalies("x", [a("DUPLICATE_EVENT", "e2")])       # the unresolved parent has since arrived
    assert [r["anomaly_type"] for r in repo.get_anomalies("x")] == ["DUPLICATE_EVENT"]
    assert repo.get_anomalies("nobody") == []


def test_graph_and_blobs_roundtrip_including_large_payloads(repo):
    g = {"nodes": [{"id": "a"}], "edges": [], "total_nodes": 1, "total_edges": 0}
    repo.put_graph("x", g)
    assert repo.get_graph("x") == g and repo.get_graph("nope") is None
    big = [{"event_id": f"evt-{i}", "pad": "x" * 50} for i in range(5000)]       # > 100 KB -> gzip on S3
    repo.put_blob("x", "ground_truth", big)
    assert repo.get_blob("x", "ground_truth") == big and repo.get_blob("x", "absent") is None


def test_health(repo):
    assert repo.health()["ok"] is True


# ── AWS-specific guarantees ───────────────────────────────────────────────────
@pytest.fixture
def aws_repo():
    with mock_aws():
        settings = aws_settings()
        create_tables(boto3.client("dynamodb", region_name=REGION), settings)
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket="b-data", CreateBucketConfiguration={"LocationConstraint": REGION})
        yield AwsRepository(settings), settings


def test_every_item_carries_a_ttl_and_tables_enable_ttl(aws_repo):
    repo, settings = aws_repo
    repo.put_execution(rec("e1"))
    repo.put_events("e1", [{"event_id": "a", "service_id": "s", "timestamp_ms": 1.0}])
    repo.put_anomalies("e1", [{"anomaly_type": "T", "severity": "INFO", "source_event_id": "a", "description": "d"}])
    assert "expires_at" in repo.executions.get_item(Key={"execution_id": "e1"})["Item"]
    assert "expires_at" in repo.events.scan()["Items"][0] and "expires_at" in repo.anomalies.scan()["Items"][0]
    ddb = boto3.client("dynamodb", region_name=REGION)
    for spec in table_specs(settings):
        ttl = ddb.describe_time_to_live(TableName=spec["TableName"])["TimeToLiveDescription"]
        assert ttl["TimeToLiveStatus"] in ("ENABLED", "ENABLING") and ttl["AttributeName"] == "expires_at"


def test_gsis_exist_for_owner_and_service_queries(aws_repo):
    _, settings = aws_repo
    ddb = boto3.client("dynamodb", region_name=REGION)
    ex = ddb.describe_table(TableName=settings.ddb_executions_table)["Table"]["GlobalSecondaryIndexes"]
    ev = ddb.describe_table(TableName=settings.ddb_events_table)["Table"]["GlobalSecondaryIndexes"]
    assert ex[0]["IndexName"] == "owner-created-index" and ev[0]["IndexName"] == "service-time-index"


def test_objects_are_written_with_server_side_encryption(aws_repo):
    repo, _ = aws_repo
    repo.put_graph("x", {"nodes": [], "edges": []})
    head = boto3.client("s3", region_name=REGION).head_object(Bucket="b-data", Key="executions/x/graph.json")
    assert head["ServerSideEncryption"] == "AES256"


def test_float_fields_survive_dynamodb(aws_repo):
    repo, _ = aws_repo
    repo.put_execution(rec("f", progress=0.375))
    assert repo.get_execution("f")["progress"] == 0.375


def test_create_tables_is_idempotent(aws_repo):
    _, settings = aws_repo
    assert create_tables(boto3.client("dynamodb", region_name=REGION), settings) == []


def test_finished_executions_cannot_be_dragged_back_to_in_progress(repo):
    """Regression: the API's publishing thread used to overwrite the worker's 'succeeded' with 'streaming'."""
    repo.put_execution(rec("e1", status="running"))
    repo.update_execution("e1", status="succeeded", progress=1.0)
    late = repo.update_execution("e1", status="streaming", progress=0.5, message="stale writer")
    assert late["status"] == "succeeded" and late["progress"] == 1.0
    repo.update_execution("e1", summary={"f1": 1.0})                       # non-status updates still land
    assert repo.get_execution("e1")["summary"] == {"f1": 1.0}
    repo.put_execution(rec("e2", status="running"))
    repo.update_execution("e2", status="failed", error="boom")
    assert repo.update_execution("e2", status="running")["status"] == "failed"


def test_concurrent_writers_to_different_fields_do_not_clobber_each_other(aws_repo):
    repo, _ = aws_repo
    repo.put_execution(rec("e1", status="running"))
    # two "processes" each do a read-modify-write of different fields; with per-field updates both land
    repo.update_execution("e1", stats={"events": 10})
    repo.update_execution("e1", anomalies={"total": 2})
    got = repo.get_execution("e1")
    assert got["stats"] == {"events": 10} and got["anomalies"] == {"total": 2} and got["config"]["nested"]["a"] == [1, 2.5]
