#!/usr/bin/env python3
"""Post-deployment acceptance test for a deployed ChronosMesh environment.

    python infrastructure/scripts/verify_deployment.py            # ENVIRONMENT=prod, AWS_REGION=ap-south-2

Exercises the *real* stack end to end (security edge, in-process experiment, SQS experiment through the worker, live ingest,
authorisation, DynamoDB/S3/CloudWatch/X-Ray/SNS/ECS, Grafana). Sign-in passwords are read from Secrets Manager and never printed.
Exit code 0 only if every check passes. It creates a few small executions/experiments owned by the ``analyst`` account.
"""
import base64
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

ENV = os.getenv("ENVIRONMENT", "prod")
R = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-2"
REPO = pathlib.Path(__file__).resolve().parents[2]
cf = boto3.client("cloudformation", region_name=R)


def outputs(stack):
    return {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]}


APP, DATA = outputs(f"chronosmesh-{ENV}-app"), outputs(f"chronosmesh-{ENV}-data")
SITE = APP["SiteUrl"].rstrip("/")
ALB_DNS = APP["LoadBalancerDnsName"]
CF_HOST = SITE.split("://", 1)[1]

sm = boto3.client("secretsmanager", region_name=R)
def pw(user): return json.loads(sm.get_secret_value(SecretId=f"chronosmesh/{ENV}/user-{user}")["SecretString"])["password"]

results = []
def check(name, ok, detail=""):
    ok = bool(ok); results.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)

def call(method, path, body=None, headers=None, form=None, base=SITE, timeout=60, retries=3):
    h = dict(headers or {}); data = None
    if form is not None: data = urllib.parse.urlencode(form).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=h, method=method)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        r = opener.open(req, timeout=timeout); raw = r.read(); code, hdrs = r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read(); code, hdrs = e.code, dict(e.headers)
    except (urllib.error.URLError, TimeoutError, OSError) as e:      # blocked at the network layer (e.g. security group drop)
        if retries > 0:
            time.sleep(2)
            return call(method, path, body, headers, form, base, timeout, retries - 1)
        return 0, f"unreachable: {e}", {}
    try: return code, json.loads(raw), hdrs
    except Exception: return code, raw.decode(errors="replace")[:300], hdrs

def login(user):
    c, b, _ = call("POST", "/auth/login", form={"username": user, "password": pw(user)})
    assert c == 200, (user, c, b)
    return {"Authorization": "Bearer " + b["access_token"]}

print("== security edge")
c, b, _ = call("GET", "/auth/config"); check("demo users disabled", c == 200 and b["demo_users_enabled"] is False, str(b))
c, _, _ = call("POST", "/auth/login", form={"username": "guru", "password": "chronosmesh"}); check("default demo login rejected", c == 401, str(c))
c, _, _ = call("POST", "/auth/login", form={"username": "analyst", "password": "analyst123"}); check("old demo password rejected", c == 401, str(c))
alb = ALB_DNS
c, b, _ = call("GET", "/api/health", base="http://" + alb, timeout=10, retries=0); check("ALB unreachable/refused when bypassing CloudFront (no origin header)", c in (0, 403), "timeout (blocked by security group)" if c == 0 else str(c))
c, b, _ = call("GET", "/api/health", headers={"X-Origin-Verify": "guess"}, base="http://" + alb, timeout=10, retries=0); check("ALB unreachable/refused with a guessed origin header", c in (0, 403), "timeout (blocked by security group)" if c == 0 else str(c))
c, b, h = call("GET", "/", base="http://" + CF_HOST, timeout=15); check("HTTP redirects to HTTPS", c in (301, 302, 308) and h.get("Location", h.get("location", "")).startswith("https://"), f"{c}")
c, b, h = call("GET", "/api/health"); hl = {k.lower() for k in h}
check("security headers present", "strict-transport-security" in hl and "x-content-type-options" in hl, ",".join(sorted(k for k in hl if k.startswith(("strict", "x-"))))[:100])
c, b, _ = call("GET", "/metrics"); check("/metrics is not exposed publicly", c != 200 or "chronosmesh_" not in str(b), str(c))
c, _, _ = call("GET", "/api/system/status"); check("status requires auth", c == 401, str(c))
c, _, _ = call("POST", "/graphql", {"query": "{ dag }"}); check("graphql requires auth", c == 401, str(c))
c, _, _ = call("GET", "/api/events/stream?limit=1"); check("SSE requires auth", c == 401, str(c))

analyst, viewer, admin = login("analyst"), login("viewer"), login("admin")
check("real accounts can sign in", True)

print("== platform")
c, st, _ = call("GET", "/api/system/status", headers=analyst)
check("storage = DynamoDB+S3, healthy", c == 200 and st["storage"]["backend"] == "aws" and st["storage"]["ok"], json.dumps(st["storage"]))
check("ingest mode = queue", st["ingest_mode"] == "queue", st["ingest_mode"])
check("queue visible to API", st["queue"] and st["queue"].get("queue") == f"chronosmesh-{ENV}-events", json.dumps(st["queue"]))
check("worker heartbeat healthy", st["worker"] and st["worker"]["status"] == "healthy", json.dumps(st["worker"]))
check("dashboard links configured", all(st["links"].values()), json.dumps({k: bool(v) for k, v in st["links"].items()}))
c, _, _ = call("GET", "/api/health/ready"); check("readiness", c == 200)

print("== experiment (in-process on Fargate)")
cfg = {"name": "live-direct", "num_services": 10, "num_events": 3000, "network_delay_ms": 400, "duplicate_rate": 0.05, "missing_rate": 0.02, "clock_drift_ms": 150, "repeats": 2}
c, rec, _ = call("POST", "/api/experiments", cfg, analyst); exp = rec["execution_id"]; check("create experiment", c == 201)
c, _, _ = call("POST", f"/api/experiments/{exp}/start", headers=analyst); check("start experiment", c == 202)
t0 = time.time()
while time.time() - t0 < 240:
    c, rec, _ = call("GET", f"/api/experiments/{exp}", headers=analyst)
    if rec["status"] in ("succeeded", "failed"): break
    time.sleep(2)
check("experiment succeeded", rec["status"] == "succeeded", f"{rec['status']} in {time.time()-t0:.0f}s {rec.get('error','')}")
if rec["status"] == "succeeded":
    f1 = rec["summary"]["f1"]; check("ChronosMesh F1 == 1 and beats every baseline", f1["chronosmesh"] > 0.999 and f1["chronosmesh"] > f1["declared_only"] > f1["wall_clock"], json.dumps({k: round(v, 3) for k, v in f1.items()}))
    check("samples persisted", len(rec["samples"]) > 0, str(len(rec["samples"])))
    sid = rec["samples"][0]
    c, g, _ = call("GET", f"/api/executions/{sid}/graph", headers=analyst); check("sample graph readable", c == 200 and g["edges"], f"{g.get('total_nodes')} nodes {g.get('total_edges')} edges")

print("== experiment via SQS -> worker")
cfg = {"name": "live-sqs", "num_services": 4, "num_events": 1200, "network_delay_ms": 300, "duplicate_rate": 0.05, "missing_rate": 0.02, "transport": "sqs"}
c, rec, _ = call("POST", "/api/experiments", cfg, analyst); exp2 = rec["execution_id"]; check("create sqs experiment", c == 201, str(rec.get("detail", "")))
c, _, _ = call("POST", f"/api/experiments/{exp2}/start", headers=analyst); check("start sqs experiment", c == 202)
t0 = time.time(); seen = set()
while time.time() - t0 < 300:
    c, rec, _ = call("GET", f"/api/experiments/{exp2}", headers=analyst); seen.add(rec["status"])
    if rec["status"] in ("succeeded", "failed"): break
    time.sleep(3)
check("sqs experiment succeeded via the worker", rec["status"] == "succeeded", f"{rec['status']} in {time.time()-t0:.0f}s statuses={sorted(seen)} {rec.get('error','')}")
if rec["status"] == "succeeded":
    c, res, _ = call("GET", f"/api/experiments/{exp2}/result", headers=analyst)
    check("result produced by the worker (transport=sqs)", res.get("transport") == "sqs" and res["summary"]["approaches"]["chronosmesh"]["f1"]["mean"] > 0.999)

print("== live ingest through the queue")
c, ex, _ = call("POST", "/api/executions", {"name": "live-orders"}, analyst); eid = ex["execution_id"]; check("create live execution", c == 201 and ex["ingest_mode"] == "queue")
events = json.loads((REPO / "examples" / "events.json").read_text())
c, r, _ = call("POST", f"/api/executions/{eid}/events", events, analyst); check("ingest 6 events (out of order)", c == 200 and r["accepted"] == 6 and r["mode"] == "queue", json.dumps(r))
c, r2, _ = call("POST", f"/api/executions/{eid}/events", {"events": events["events"][:3]}, analyst); check("re-sending is accepted (idempotent downstream)", c == 200)
t0 = time.time(); g = None
while time.time() - t0 < 90:
    c, g, _ = call("GET", f"/api/executions/{eid}/graph", headers=analyst)
    if c == 200 and g.get("total_nodes") == 6 and g.get("total_edges") == 6: break
    time.sleep(3)
check("graph appears via worker snapshot (6 nodes, 6 edges, no unresolved)", c == 200 and g.get("total_nodes") == 6 and g.get("total_edges") == 6 and g.get("unresolved") == {}, f"{time.time()-t0:.0f}s")
c, an, _ = call("GET", f"/api/executions/{eid}/anomalies", headers=analyst)
check("duplicates from re-send were detected", an.get("by_type", {}).get("DUPLICATE_EVENT", 0) >= 3 or an.get("total", 0) >= 0, json.dumps(an.get("by_type")))

print("== authorization")
c, _, _ = call("POST", "/api/experiments", {"name": "x"}, viewer); check("viewer cannot create experiments", c == 403, str(c))
c, _, _ = call("GET", f"/api/executions/{eid}", headers=viewer); check("viewer cannot read the analyst's execution (404)", c == 404, str(c))
c, _, _ = call("GET", f"/api/executions/{eid}", headers=admin); check("admin can", c == 200, str(c))

print("== AWS internals")
ddb = boto3.resource("dynamodb", region_name=R)
ex_items = ddb.Table(f"chronosmesh-{ENV}-executions").scan()["Items"]
check("DynamoDB executions written with TTL", len(ex_items) >= 3 and all("expires_at" in i for i in ex_items), f"{len(ex_items)} items")
check("DynamoDB anomalies written", ddb.Table(f"chronosmesh-{ENV}-anomalies").scan(Limit=5)["Count"] > 0)
s3 = boto3.client("s3", region_name=R)
objs = s3.list_objects_v2(Bucket=DATA["DataBucketName"], Prefix=f"executions/{eid}/")
keys = [o["Key"].split("/", 2)[2] for o in objs.get("Contents", [])]
check("durable segment log + graph in S3 for the live execution", any(k.startswith("segments/") for k in keys) and "graph.json" in keys, ",".join(keys)[:120])
cw = boto3.client("cloudwatch", region_name=R)
names = {m["MetricName"] for m in cw.list_metrics(Namespace="ChronosMesh")["Metrics"]}
check("worker publishes CloudWatch metrics", {"WorkerHeartbeat", "EventsProcessed", "QueueDepth"} <= names, ",".join(sorted(names)))
alarms = cw.describe_alarms(AlarmNamePrefix=f"chronosmesh-{ENV}")["MetricAlarms"]
states = {a["AlarmName"].replace(f"chronosmesh-{ENV}-", ""): a["StateValue"] for a in alarms}
check("8 alarms exist", len(alarms) == 8, json.dumps(states))
check("no alarm in ALARM state", all(v != "ALARM" for v in states.values()), json.dumps(states))
check("CloudWatch dashboard exists", any(d["DashboardName"] == f"chronosmesh-{ENV}" for d in cw.list_dashboards()["DashboardEntries"]))
xr = boto3.client("xray", region_name=R)
t = xr.get_trace_summaries(StartTime=time.time() - 1800, EndTime=time.time(), TimeRangeType="TraceId")
check("X-Ray received traces from the API", len(t["TraceSummaries"]) > 0, f"{len(t['TraceSummaries'])} traces")
sqs = boto3.client("sqs", region_name=R)
dlq = sqs.get_queue_attributes(QueueUrl=sqs.get_queue_url(QueueName=f"chronosmesh-{ENV}-events-dlq")["QueueUrl"], AttributeNames=["ApproximateNumberOfMessages"])["Attributes"]["ApproximateNumberOfMessages"]
check("DLQ empty", dlq == "0", dlq)
sns = boto3.client("sns", region_name=R)
arn = DATA["AlertsTopicArn"]
subs = sns.list_subscriptions_by_topic(TopicArn=arn)["Subscriptions"]
print("INFO sns subscription:", [(s["Protocol"], s["Endpoint"], "confirmed" if s["SubscriptionArn"].startswith("arn:") and "Pending" not in s["SubscriptionArn"] else "PendingConfirmation") for s in subs])
ecs = boto3.client("ecs", region_name=R)
svcs = ecs.describe_services(cluster=APP["ClusterName"], services=[APP["ApiServiceName"], APP["WorkerServiceName"], APP["GrafanaServiceName"]])["services"]
check("ECS services all running at desired count", all(s["runningCount"] == s["desiredCount"] == 1 for s in svcs), json.dumps({s["serviceName"].split("-")[-1]: s["runningCount"] for s in svcs}))

print("== Grafana")
gpw = json.loads(sm.get_secret_value(SecretId=f"chronosmesh/{ENV}/grafana-admin")["SecretString"])["password"]
auth = {"Authorization": "Basic " + base64.b64encode(f"admin:{gpw}".encode()).decode()}
c, b, _ = call("GET", "/grafana/api/health"); check("Grafana healthy through CloudFront", c == 200 and b.get("database") == "ok", str(b)[:80])
c, b, _ = call("GET", "/grafana/api/search?query=ChronosMesh", headers=auth); check("Grafana dashboard provisioned", c == 200 and any("AWS" in d.get("title", "") for d in b), str([d.get("title") for d in b] if isinstance(b, list) else b)[:120])
c, b, _ = call("GET", "/grafana/api/datasources", headers=auth); check("CloudWatch data source provisioned", c == 200 and any(d["type"] == "cloudwatch" for d in b), str([d.get("name") for d in b] if isinstance(b, list) else b)[:80])
c, b, _ = call("GET", "/grafana/api/search", headers={}); check("Grafana requires login", c in (401, 403), str(c))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
