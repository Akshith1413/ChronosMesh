"""Generate the ChronosMesh Grafana dashboards (blueprint §8: A system health, B causal engine, C fault injection).

Run:  python observability/grafana/build_dashboards.py
The JSON files in ``dashboards/`` are committed; a unit test asserts every metric they query exists.
"""

from __future__ import annotations

import json
import pathlib

OUT = pathlib.Path(__file__).parent / "dashboards"
PROM = {"type": "prometheus", "uid": "prometheus"}
CW = {"type": "cloudwatch", "uid": "cloudwatch"}


def _panel(pid, kind, title, targets, x, y, w, h, ds, unit=None, desc=None, extra=None):
    p = {
        "id": pid, "type": kind, "title": title, "datasource": ds,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [dict(t, datasource=ds, refId=chr(65 + i)) for i, t in enumerate(targets)],
        "fieldConfig": {"defaults": ({"unit": unit} if unit else {}), "overrides": []},
        "options": {},
    }
    if desc:
        p["description"] = desc
    if kind == "stat":
        p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "value", "graphMode": "area", "textMode": "auto"}
    if extra:
        p.update(extra)
    return p


def stat(pid, title, expr, x, y, w=4, h=4, ds=PROM, unit=None, desc=None, thresholds=None):
    extra = None
    if thresholds:
        extra = {"fieldConfig": {"defaults": {"unit": unit, "thresholds": {"mode": "absolute", "steps": thresholds}},
                                 "overrides": []}}
    return _panel(pid, "stat", title, [{"expr": expr}], x, y, w, h, ds, unit, desc, extra)


def series(pid, title, exprs, x, y, w=12, h=8, ds=PROM, unit=None, desc=None):
    targets = [{"expr": e, "legendFormat": legend} for e, legend in exprs]
    return _panel(pid, "timeseries", title, targets, x, y, w, h, ds, unit, desc)


def cw_series(pid, title, queries, x, y, w=12, h=8, namespace="ChronosMesh", dims=None, stat_="Average", desc=None):
    targets = [{
        "queryMode": "Metrics", "namespace": namespace, "metricName": m, "dimensions": dims or {"Service": "worker"},
        "statistic": stat_, "period": "60", "region": "default", "id": "", "expression": "", "matchExact": True,
        "label": label,
    } for m, label in queries]
    return _panel(pid, "timeseries", title, targets, x, y, w, h, CW, desc=desc)


def row(pid, title, y):
    return {"id": pid, "type": "row", "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
            "panels": []}


def dashboard(uid, title, panels, tags):
    return {
        "uid": uid, "title": title, "tags": ["chronosmesh"] + tags, "timezone": "browser", "schemaVersion": 39,
        "version": 1, "refresh": "10s", "editable": False, "graphTooltip": 1,
        "time": {"from": "now-1h", "to": "now"}, "panels": panels, "templating": {"list": []},
        "annotations": {"list": []}, "links": [],
    }


def system_health():
    ok_warn_crit = [{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 5}]
    return dashboard("chronosmesh-system-health", "ChronosMesh — A · System Health", [
        row(1, "Is the platform healthy?", 0),
        stat(2, "Events / second", "sum(rate(chronosmesh_events_received_total[1m]))", 0, 1, unit="ops"),
        stat(3, "Reconstruction p95", "histogram_quantile(0.95, sum(rate(chronosmesh_reconstruction_duration_seconds_bucket[5m])) by (le))", 4, 1, unit="s"),
        stat(4, "Processing errors (5m)", "sum(increase(chronosmesh_processing_errors_total[5m]))", 8, 1, thresholds=ok_warn_crit),
        stat(5, "Queue backlog age", "max(chronosmesh_queue_oldest_message_age_seconds)", 12, 1, unit="s",
             thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 60}, {"color": "red", "value": 300}]),
        stat(6, "Queue depth", "max(chronosmesh_queue_depth)", 16, 1),
        stat(7, "Worker last seen", "time() - max(chronosmesh_worker_heartbeat_timestamp_seconds)", 20, 1, unit="s",
             desc="Seconds since the worker last completed a poll loop.",
             thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 60}, {"color": "red", "value": 120}]),
        series(8, "Ingestion vs processing rate", [
            ("sum(rate(chronosmesh_events_received_total[1m]))", "received"),
            ("sum(rate(chronosmesh_events_processed_total[1m]))", "processed")], 0, 5, unit="ops"),
        series(9, "API latency (p50 / p95 / p99)", [
            ("histogram_quantile(0.50, sum(rate(chronosmesh_api_request_duration_seconds_bucket[5m])) by (le))", "p50"),
            ("histogram_quantile(0.95, sum(rate(chronosmesh_api_request_duration_seconds_bucket[5m])) by (le))", "p95"),
            ("histogram_quantile(0.99, sum(rate(chronosmesh_api_request_duration_seconds_bucket[5m])) by (le))", "p99")],
               12, 5, unit="s"),
        series(10, "HTTP status codes", [
            ("sum by (status) (rate(chronosmesh_api_requests_total[1m]))", "{{status}}")], 0, 13),
        series(11, "Queue backlog and oldest message age", [
            ("max(chronosmesh_queue_depth)", "visible messages"),
            ("max(chronosmesh_queue_oldest_message_age_seconds)", "oldest age (s)")], 12, 13),
    ], ["health"])


def causal_engine():
    return dashboard("chronosmesh-causal-engine", "ChronosMesh — B · Causal Engine Performance", [
        row(1, "Reconstruction latency and throughput", 0),
        series(2, "Reconstruction latency p50 / p95 / p99", [
            ("histogram_quantile(0.50, sum(rate(chronosmesh_reconstruction_duration_seconds_bucket[5m])) by (le))", "p50"),
            ("histogram_quantile(0.95, sum(rate(chronosmesh_reconstruction_duration_seconds_bucket[5m])) by (le))", "p95"),
            ("histogram_quantile(0.99, sum(rate(chronosmesh_reconstruction_duration_seconds_bucket[5m])) by (le))", "p99")],
               0, 1, unit="s"),
        series(3, "Throughput (events processed / s)", [("sum(rate(chronosmesh_events_processed_total[1m]))", "events/s")],
               12, 1, unit="ops"),
        row(4, "Graph size and data quality", 9),
        series(5, "Graph size (last reconstructed execution)", [
            ("chronosmesh_graph_nodes", "nodes"), ("chronosmesh_graph_edges", "edges")], 0, 10),
        series(6, "Unresolved dependencies", [("chronosmesh_unresolved_dependencies", "unresolved links")], 12, 10,
               desc="Declared parents not yet observed. Climbs when events are lost or delayed; falls as late parents arrive."),
        series(7, "Duplicate rate", [
            ("rate(chronosmesh_events_duplicate_total[5m]) / clamp_min(rate(chronosmesh_events_received_total[5m]), 1e-9)",
             "duplicates / received")], 0, 18, unit="percentunit"),
        series(8, "Anomalies by type", [("sum by (anomaly_type) (rate(chronosmesh_anomalies_total[5m]))", "{{anomaly_type}}")],
               12, 18),
    ], ["engine"])


def fault_injection():
    return dashboard("chronosmesh-fault-injection", "ChronosMesh — C · Fault Injection & Recovery", [
        row(1, "Experiments", 0),
        stat(2, "Experiments succeeded", "sum(chronosmesh_experiments_total{status=\"succeeded\"})", 0, 1),
        stat(3, "Experiments failed", "sum(chronosmesh_experiments_total{status=\"failed\"})", 4, 1,
             thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        series(4, "Experiment duration p50 / p95", [
            ("histogram_quantile(0.50, sum(rate(chronosmesh_experiment_duration_seconds_bucket[15m])) by (le))", "p50"),
            ("histogram_quantile(0.95, sum(rate(chronosmesh_experiment_duration_seconds_bucket[15m])) by (le))", "p95")],
               8, 1, w=16, h=6, unit="s"),
        row(5, "Resilience under injected faults", 7),
        series(6, "Normal vs. fault-injected: duplicate deliveries / s", [
            ("rate(chronosmesh_events_duplicate_total[1m])", "duplicates")], 0, 8),
        series(7, "Processing errors by stage", [("sum by (stage) (rate(chronosmesh_processing_errors_total[1m]))", "{{stage}}")],
               12, 8),
        series(8, "Time to recover after a worker restart (heartbeat gap)", [
            ("time() - max(chronosmesh_worker_heartbeat_timestamp_seconds)", "seconds since last heartbeat")], 0, 16, unit="s"),
        series(9, "Rejected events by reason", [("sum by (reason) (rate(chronosmesh_events_failed_total[5m]))", "{{reason}}")],
               12, 16),
    ], ["faults"])


def aws_cloudwatch():
    return dashboard("chronosmesh-aws", "ChronosMesh — AWS (CloudWatch)", [
        row(1, "Worker custom metrics (namespace ChronosMesh)", 0),
        cw_series(2, "Events processed / duplicates / errors", [
            ("EventsProcessed", "processed"), ("DuplicateEvents", "duplicates"), ("ProcessingErrors", "errors")], 0, 1,
                  stat_="Maximum"),
        cw_series(3, "Queue depth and oldest message age", [
            ("QueueDepth", "depth"), ("QueueOldestMessageAge", "oldest age (s)")], 12, 1, stat_="Maximum"),
        cw_series(4, "Unresolved dependencies", [("UnresolvedDependencies", "unresolved")], 0, 9, stat_="Maximum"),
        cw_series(5, "Worker heartbeat", [("WorkerHeartbeat", "heartbeat")], 12, 9, stat_="Sum"),
        row(6, "AWS service metrics", 17),
        cw_series(7, "ECS CPU / memory (API service)", [("CPUUtilization", "cpu %"), ("MemoryUtilization", "memory %")],
                  0, 18, namespace="AWS/ECS", dims={"ClusterName": "chronosmesh-prod", "ServiceName": "chronosmesh-prod-api"}),
        cw_series(8, "SQS visible / in-flight messages", [
            ("ApproximateNumberOfMessagesVisible", "visible"), ("ApproximateNumberOfMessagesNotVisible", "in flight")],
                  12, 18, namespace="AWS/SQS", dims={"QueueName": "chronosmesh-prod-events"}),
    ], ["aws"])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, build in {"chronosmesh-system-health": system_health, "chronosmesh-causal-engine": causal_engine,
                        "chronosmesh-fault-injection": fault_injection, "chronosmesh-aws": aws_cloudwatch}.items():
        (OUT / f"{name}.json").write_text(json.dumps(build(), indent=2) + "\n")
        print("wrote", OUT / f"{name}.json")
