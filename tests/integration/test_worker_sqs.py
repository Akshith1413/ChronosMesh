"""SQS worker: durable-before-ack, idempotent redelivery, crash recovery, DLQ, queue-mode experiments."""

import json
import time

import boto3
import pytest
from moto import mock_aws

from api.services.execution_service import ExecutionService
from chronosmesh.config import Settings
from chronosmesh.experiments import new_record
from chronosmesh.observability.cloudwatch import CloudWatchPublisher
from chronosmesh.persistence import MemoryRepository
from chronosmesh.persistence.aws import AwsRepository
from chronosmesh.persistence.aws_schema import create_tables
from chronosmesh.reconstruction import reconstruct
from chronosmesh.events.event import Event
from chronosmesh.simulator import ExperimentConfig, generate_workload, inject_faults
from chronosmesh.transport.sqs import SqsTransport
from chronosmesh.worker import Worker

REGION = "ap-south-2"


@pytest.fixture
def cloud():
    with mock_aws():
        sqs = boto3.client("sqs", region_name=REGION)
        dlq = sqs.create_queue(QueueName="events-dlq")["QueueUrl"]
        dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        q = sqs.create_queue(QueueName="events", Attributes={
            "VisibilityTimeout": "30",
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "2"})})["QueueUrl"]
        settings = Settings(aws_region=REGION, ddb_executions_table="t-exec", ddb_events_table="t-events",
                            ddb_anomalies_table="t-anom", ddb_graphs_table="t-graph", s3_data_bucket="b-data",
                            sqs_events_queue_url=q, ingest_mode="queue", max_experiment_events=5000)
        create_tables(boto3.client("dynamodb", region_name=REGION), settings)
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket="b-data", CreateBucketConfiguration={"LocationConstraint": REGION})
        yield {"settings": settings, "repo": AwsRepository(settings), "transport": SqsTransport(q, REGION),
               "sqs": sqs, "queue_url": q, "dlq_url": dlq}


class ImmediateRedelivery(SqsTransport):
    """Same transport, but failed messages become visible again immediately (no 30 s wait in tests)."""

    def receive(self, max_messages=10, wait_seconds=20, visibility_timeout=0):
        return super().receive(max_messages, wait_seconds, visibility_timeout)


def make_worker(cloud, **kw):
    transport = ImmediateRedelivery(cloud["queue_url"], REGION)
    return Worker(cloud["settings"], cloud["repo"], transport, **kw)


def pump(worker, rounds=20):
    total = 0
    for _ in range(rounds):
        n = worker.poll_once(wait_seconds=0)
        total += n
        if n == 0:
            break
    return total


def events_for(execution_id, n=40, seed=3):
    cfg = ExperimentConfig(num_services=4, num_events=n, events_per_execution=n).validate()
    gt = generate_workload(cfg, seed)
    evs = next(iter(gt.executions.values()))
    out = []
    for e in evs:
        d = e.to_dict()
        d["execution_id"] = execution_id
        out.append(d)
    return evs, out


def live_record(repo, eid="live-1"):
    repo.put_execution(new_record("alice", "live", "live", execution_id=eid))
    return eid


def test_live_stream_end_to_end_with_snapshot(cloud):
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    originals, raw = events_for(eid)
    transport.publish_events(eid, raw, kind="live", start_seq=100)
    worker = make_worker(cloud)
    assert pump(worker) > 0
    worker.flush_all()

    graph = repo.get_graph(eid)
    expected = reconstruct([Event.from_dict(d) for d in raw]).dag
    assert {(e["source"], e["target"]) for e in graph["edges"]} == set(expected.edges())
    rec = repo.get_execution(eid)
    assert rec["status"] == "streaming" and rec["stats"]["events"] == len(raw)
    assert repo.get_anomalies(eid) is not None
    assert transport.depth()["visible"] == 0                      # everything was acknowledged


def test_messages_are_durable_before_they_are_acknowledged(cloud):
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid)
    next_seq = transport.publish_events(eid, raw, kind="live", start_seq=0)
    pump(make_worker(cloud))
    assert repo.list_segments(eid) == list(range(next_seq))
    assert sum(len(repo.get_segment(eid, s)) for s in repo.list_segments(eid)) == len(raw)


def test_redelivered_message_is_skipped_by_sequence_number(cloud):
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid, n=10)
    transport.publish_events(eid, raw, kind="live", start_seq=5)
    transport.publish_events(eid, raw, kind="live", start_seq=5)       # same seq published twice (at-least-once)
    worker = make_worker(cloud)
    pump(worker)
    assert worker.stats["duplicate_messages"] == 1 and worker.stats["events"] == 10
    assert worker.streams[eid].router.engines[eid].event_count == 10


def test_event_level_duplicates_are_counted_not_double_applied(cloud):
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid, n=10)
    transport.publish_events(eid, raw, kind="live", start_seq=1)
    transport.publish_events(eid, raw[:4], kind="live", start_seq=2)   # a different message re-sending 4 events
    worker = make_worker(cloud)
    pump(worker)
    eng = worker.streams[eid].router.engines[eid]
    assert eng.event_count == 10 and worker.stats["duplicate_events"] == 4


def test_new_worker_recovers_acknowledged_state_from_segments(cloud):
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid, n=60)
    half = len(raw) // 2
    transport.publish_events(eid, raw[:half], kind="live", start_seq=0)
    first = make_worker(cloud)
    pump(first)                                                         # these messages are now DELETED from SQS
    assert transport.depth()["visible"] == 0
    del first                                                           # the worker process dies; memory is gone

    transport.publish_events(eid, raw[half:], kind="live", start_seq=1000)
    second = make_worker(cloud)
    pump(second)
    engine = second.streams[eid].router.engines[eid]
    assert engine.event_count == len(raw)                               # first half came back from S3 segments
    clean = reconstruct([Event.from_dict(d) for d in raw]).dag
    assert set(engine.dag.edges()) == set(clean.edges())


def test_a_failing_message_is_left_in_the_queue_and_retried(cloud, monkeypatch):
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid, n=10)
    transport.publish_events(eid, raw, kind="live", start_seq=0)
    worker = make_worker(cloud)

    real = repo.put_segment
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("S3 hiccup")
        return real(*a, **k)

    monkeypatch.setattr(repo, "put_segment", flaky)
    assert worker.poll_once(wait_seconds=0) == 0 and worker.stats["errors"] == 1
    assert worker.poll_once(wait_seconds=0) == 1                        # redelivered and now succeeds
    assert worker.streams[eid].router.engines[eid].event_count == 10


def test_poison_message_ends_up_in_the_dead_letter_queue(cloud):
    sqs = cloud["sqs"]
    sqs.send_message(QueueUrl=cloud["queue_url"], MessageBody=json.dumps({"type": "garbage"}))
    sqs.send_message(QueueUrl=cloud["queue_url"], MessageBody="{not json")
    worker = make_worker(cloud)
    for _ in range(4):
        worker.poll_once(wait_seconds=0)
    in_dlq = sqs.get_queue_attributes(QueueUrl=cloud["dlq_url"],
                                      AttributeNames=["ApproximateNumberOfMessages"])["Attributes"]
    assert int(in_dlq["ApproximateNumberOfMessages"]) == 2
    assert worker.stats["messages"] == 0


def test_experiment_over_sqs_matches_the_in_process_result(cloud):
    settings, repo, transport = cloud["settings"], cloud["repo"], cloud["transport"]
    svc = ExecutionService(settings, repo, transport)
    user = {"username": "alice", "role": "analyst"}
    params = {"name": "via-queue", "num_services": 4, "num_events": 400, "events_per_execution": 20,
              "network_delay_ms": 300, "duplicate_rate": 0.05, "missing_rate": 0.02, "transport": "sqs"}
    exp = svc.create_experiment(user, params)["execution_id"]
    svc.start_experiment(user, exp)

    worker = make_worker(cloud)
    deadline = time.time() + 60
    rec = {}
    while time.time() < deadline:
        worker.poll_once(wait_seconds=0)
        rec = repo.get_execution(exp)
        if rec["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    svc.shutdown()
    assert rec["status"] == "succeeded", rec

    direct = svc.repo  # same repo; run the identical config in-process for comparison
    from chronosmesh.evaluation import run_experiment
    ref = run_experiment(ExperimentConfig.from_dict({**params, "transport": "direct"}))
    result = repo.get_blob(exp, "result")
    assert result["transport"] == "sqs"
    got, want = result["runs"][0]["approaches"], ref["runs"][0]["approaches"]
    for ap in ("arrival_order", "wall_clock", "declared_only", "chronosmesh"):
        assert got[ap]["f1"] == pytest.approx(want[ap]["f1"], abs=1e-9), ap
    assert result["runs"][0]["events_dropped"] == ref["runs"][0]["events_dropped"]
    assert rec["samples"] and repo.get_graph(rec["samples"][0])["edges"]
    assert transport.depth()["visible"] == 0


def test_queue_experiment_requires_a_queue_and_single_repeat(cloud):
    svc = ExecutionService(cloud["settings"], cloud["repo"], cloud["transport"])
    user = {"username": "alice", "role": "analyst"}
    with pytest.raises(Exception, match="repeats=1"):
        svc.create_experiment(user, {"num_events": 100, "transport": "sqs", "repeats": 2})
    plain = ExecutionService(Settings(), MemoryRepository())
    with pytest.raises(Exception, match="queue"):
        plain.create_experiment(user, {"num_events": 100, "transport": "sqs"})
    svc.shutdown(); plain.shutdown()


def test_api_queue_mode_publishes_and_worker_serves_snapshot(cloud):
    settings, repo = cloud["settings"], cloud["repo"]
    svc = ExecutionService(settings, repo, cloud["transport"])
    user = {"username": "alice", "role": "analyst"}
    ex = svc.create_execution(user, "q")["execution_id"]
    _, raw = events_for(ex, n=30)
    res = svc.ingest(user, ex, raw)
    assert res["mode"] == "queue" and res["accepted"] == 30
    worker = make_worker(cloud)
    pump(worker)
    worker.flush_all()
    graph = svc.graph(user, ex)
    assert graph["total_nodes"] == 30 and graph["edges"]
    other = {"username": "mallory", "role": "analyst"}
    with pytest.raises(Exception, match="not found"):
        svc.graph(other, ex)
    svc.shutdown()


def test_queue_status_reports_depth(cloud):
    svc = ExecutionService(cloud["settings"], cloud["repo"], cloud["transport"])
    cloud["transport"].publish_events("s", [{"event_id": "a", "service_id": "x"}], kind="live", start_seq=0)
    st = svc.queue_status()
    assert st["queue"] == "events" and st["visible"] == 1
    svc.shutdown()


def test_cloudwatch_publisher_roundtrip(cloud):
    cw = CloudWatchPublisher("ChronosMesh", REGION, dimensions={"Service": "worker"})
    assert cw.put({"EventsProcessed": 5, "QueueOldestMessageAge": 1.5, "Skipped": None}) is True
    names = {m["MetricName"] for m in boto3.client("cloudwatch", region_name=REGION).list_metrics(Namespace="ChronosMesh")["Metrics"]}
    assert names == {"EventsProcessed", "QueueOldestMessageAge"}
    assert isinstance(cw.queue_age_seconds("events"), float)


def test_cloudwatch_publisher_never_raises(monkeypatch):
    class Broken:
        def put_metric_data(self, **_): raise RuntimeError("throttled")
    assert CloudWatchPublisher(client=Broken()).put({"A": 1}) is False


def test_publisher_splits_large_batches_into_valid_sqs_messages(cloud):
    transport = cloud["transport"]
    big = [{"event_id": f"e{i}", "service_id": "s", "pad": "x" * 900} for i in range(400)]
    next_seq = transport.publish_events("big", big, kind="live", start_seq=0)
    assert next_seq > 5                                                  # chunked, not one oversized message
    worker = make_worker(cloud)
    pump(worker, rounds=100)
    assert worker.stats["events"] == 400


def test_worker_publishes_interval_deltas_not_running_totals(cloud):
    sent = []

    class Capture:
        def put(self, metrics):
            sent.append(dict(metrics))
            return True

    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid, n=10)
    worker = make_worker(cloud, publisher=Capture())
    transport.publish_events(eid, raw, kind="live", start_seq=0)
    pump(worker)
    worker._last_publish = 0                       # force a publish now
    worker._maybe_publish_metrics()
    transport.publish_events(eid, raw[:3], kind="live", start_seq=1)   # 3 duplicate events
    pump(worker)
    worker._last_publish = 0
    worker._maybe_publish_metrics()
    assert len(sent) >= 2
    # Deltas sum to the true totals; if running totals were reported the sum would overshoot (10 + 13 > 13).
    assert sum(m["EventsProcessed"] for m in sent) == 13
    assert sum(m["DuplicateEvents"] for m in sent) == 3
    assert max(m["EventsProcessed"] for m in sent) <= 10
    assert all(m["WorkerHeartbeat"] == 1 for m in sent)


def test_worker_health_reads_the_cloudwatch_heartbeat(cloud):
    svc = ExecutionService(cloud["settings"], cloud["repo"], cloud["transport"])
    assert svc.worker_health()["status"] == "down"                    # no heartbeat has ever been published
    svc._worker_cache = (0.0, None)
    CloudWatchPublisher("ChronosMesh", REGION, dimensions={"Service": "worker"}).put({"WorkerHeartbeat": 1})
    health = svc.worker_health()
    assert health["status"] == "healthy" and health["last_heartbeat_age_seconds"] < 300
    assert svc.system_status()["worker"]["status"] == "healthy"
    plain = ExecutionService(Settings(), MemoryRepository())
    assert plain.worker_health() is None                              # no queue -> no worker to report on
    svc.shutdown(); plain.shutdown()


def test_small_live_batch_becomes_visible_without_further_messages_or_shutdown(cloud):
    """Regression: snapshots used to be written only when another message arrived (or on shutdown)."""
    repo, transport = cloud["repo"], cloud["transport"]
    eid = live_record(repo)
    _, raw = events_for(eid, n=10)
    transport.publish_events(eid, raw, kind="live", start_seq=0)
    worker = make_worker(cloud)
    worker.poll_once(wait_seconds=0)                    # processes the message; < 500 events, nothing else queued
    assert repo.get_graph(eid) is None                  # (not yet: debounce)
    time.sleep(IDLE_WAIT)
    worker.poll_once(wait_seconds=0)                    # an idle poll alone must publish the snapshot
    graph = repo.get_graph(eid)
    assert graph is not None and graph["total_nodes"] == 10
    assert repo.get_execution(eid)["stats"]["events"] == 10
    time.sleep(IDLE_WAIT)
    worker.poll_once(wait_seconds=0)
    assert not worker._dirty_live_streams()             # nothing left to publish


IDLE_WAIT = 1.2
