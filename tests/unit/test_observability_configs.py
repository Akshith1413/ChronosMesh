"""Configuration consistency: dashboards, alert rules, Prometheus, compose and CI must match the code.

These checks exist because the original configs silently pointed at things that did not exist
(a Prometheus target for a non-existent service, a Grafana dashboard that was mounted but never loaded).
"""

import json
import pathlib
import re
import subprocess

import pytest
import yaml
from prometheus_client import REGISTRY

import chronosmesh.observability.metrics  # noqa: F401  (registers the metrics)

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOKEN = re.compile(r"chronosmesh_[a-z0-9_]+")


def known_metric_names():
    names = set()
    for fam in REGISTRY.collect():
        if not fam.name.startswith("chronosmesh_"):
            continue
        if fam.type == "counter":
            names |= {f"{fam.name}_total", f"{fam.name}_created", fam.name}
        elif fam.type == "histogram":
            names |= {f"{fam.name}_{s}" for s in ("bucket", "count", "sum", "created")} | {fam.name}
        else:
            names.add(fam.name)
    return names


def yaml_file(path):
    return yaml.safe_load((ROOT / path).read_text())


def tokens_in(text):
    return set(TOKEN.findall(text))


def test_blueprint_metric_names_are_exported():
    expected = {
        "chronosmesh_events_received_total", "chronosmesh_events_processed_total", "chronosmesh_events_duplicate_total",
        "chronosmesh_unresolved_dependencies", "chronosmesh_reconstruction_duration_seconds_bucket",
        "chronosmesh_queue_oldest_message_age_seconds", "chronosmesh_graph_nodes", "chronosmesh_graph_edges",
        "chronosmesh_processing_errors_total",
    }
    assert expected <= known_metric_names()


def test_alert_rules_only_reference_exported_metrics():
    rules = yaml_file("observability/alert_rules.yml")
    known = known_metric_names()
    seen = set()
    for group in rules["groups"]:
        for rule in group["rules"]:
            used = tokens_in(rule["expr"])
            assert used, rule["alert"]
            assert used <= known, f"{rule['alert']} uses unknown metric(s): {used - known}"
            assert rule["labels"]["severity"] in ("warning", "critical")
            assert rule["annotations"]["summary"] and rule["annotations"]["description"]
            seen.add(rule["alert"])
    # the blueprint's signals each have an alert
    assert {"ChronosMeshWorkerDown", "ChronosMeshQueueBacklogAge", "ChronosMeshUnresolvedDependenciesHigh",
            "ChronosMeshReconstructionLatencyHigh", "ChronosMeshProcessingErrors"} <= seen


def test_dashboards_only_query_exported_metrics_and_provisioned_datasources():
    known = known_metric_names()
    ds_uids = {d["uid"] for d in yaml_file("observability/grafana/provisioning/datasources/datasources.yml")["datasources"]}
    files = sorted((ROOT / "observability/grafana/dashboards").glob("*.json"))
    assert len(files) >= 5
    uids = set()
    for f in files:
        dash = json.loads(f.read_text())
        assert dash["uid"] not in uids, f"duplicate dashboard uid {dash['uid']}"
        uids.add(dash["uid"])
        for panel in dash["panels"]:
            if panel["type"] == "row":
                continue
            for target in panel.get("targets", []):
                ds = (target.get("datasource") or panel.get("datasource") or {})
                if isinstance(ds, dict) and ds.get("uid"):
                    assert ds["uid"] in ds_uids, f"{f.name}: unknown datasource {ds}"
                used = tokens_in(target.get("expr", ""))
                assert used <= known, f"{f.name} / {panel['title']}: unknown metric(s) {used - known}"


def test_blueprint_dashboards_exist():
    uids = {json.loads(p.read_text())["uid"] for p in (ROOT / "observability/grafana/dashboards").glob("*.json")}
    assert {"chronosmesh-system-health", "chronosmesh-causal-engine", "chronosmesh-fault-injection"} <= uids


def test_grafana_dashboard_provider_points_at_the_mounted_directory():
    prov = yaml_file("observability/grafana/provisioning/dashboards/dashboards.yml")["providers"][0]
    compose = yaml_file("docker-compose.yml")
    mounts = " ".join(compose["services"]["grafana"]["volumes"])
    assert prov["options"]["path"] == "/var/lib/grafana/dashboards"
    assert "/var/lib/grafana/dashboards" in mounts and "/etc/grafana/provisioning" in mounts


def test_dashboard_generator_output_is_committed_and_current():
    out = subprocess.run(["python3", str(ROOT / "observability/grafana/build_dashboards.py")], capture_output=True, text=True,
                         check=True, cwd=ROOT)
    assert out.stdout.count("wrote") == 4
    status = subprocess.run(["git", "status", "--porcelain", "observability/grafana/dashboards"], capture_output=True,
                            text=True, cwd=ROOT).stdout
    # regenerating must not change committed files once they are tracked (untracked/new files are fine pre-commit)
    assert not any(line.startswith(" M") for line in status.splitlines()), status


def test_prometheus_scrapes_services_that_exist_in_compose():
    prom = yaml_file("observability/prometheus.yml")
    services = yaml_file("docker-compose.yml")["services"]
    for job in prom["scrape_configs"]:
        for sc in job["static_configs"]:
            for target in sc["targets"]:
                host, _, _port = target.partition(":")
                assert host == "localhost" or host in services, f"job {job['job_name']}: no service '{host}'"
    assert yaml_file("observability/prometheus.yml")["rule_files"] == ["alert_rules.yml"]


def test_compose_services_are_consistent():
    compose = yaml_file("docker-compose.yml")
    services = compose["services"]
    dockerfile = (ROOT / "api/Dockerfile").read_text()
    stages = set(re.findall(r"^FROM .* AS (\w+)", dockerfile, flags=re.M))
    for name, svc in services.items():
        build = svc.get("build")
        if build:
            assert build["target"] in stages, f"{name}: Dockerfile has no stage {build['target']}"
        deps = svc.get("depends_on", [])
        for dep in (deps if isinstance(deps, list) else deps.keys()):
            assert dep in services, f"{name} depends on unknown service {dep}"
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name}: port {port} must bind to localhost"
    assert {"prometheus", "grafana", "otel-collector", "chronosmesh-api", "chronosmesh-worker"} <= set(services)
    # the heavy streaming stack is opt-in
    for name in ("kafka", "zookeeper", "neo4j", "flink-jobmanager", "flink-taskmanager"):
        assert services[name]["profiles"] == ["full"]


def test_runtime_images_do_not_run_as_root():
    dockerfile = (ROOT / "api/Dockerfile").read_text()
    for stage in ("api", "worker"):
        body = dockerfile.split(f"AS {stage}")[1].split("\nFROM ")[0]
        assert re.search(r"^USER\s+(?!root)\S+", body, flags=re.M), f"stage {stage} runs as root"


def test_ci_workflows_live_where_github_reads_them():
    assert not (ROOT / "ChronosMesh-main").exists()
    workflows = sorted(p.name for p in (ROOT / ".github/workflows").glob("*.yml"))
    assert {"backend.yml", "frontend.yml", "docker.yml", "integration.yml"} <= set(workflows)
    for name in workflows:
        wf = yaml_file(f".github/workflows/{name}")
        assert wf["permissions"] == {"contents": "read"} or "permissions" in wf, name
        assert True in wf or "on" in wf, name       # PyYAML parses the key `on` as boolean True


def test_no_committed_secrets_or_known_leaked_values():
    leaked = ["chronosmesh2026", "chronosmesh-prod-k8s-cluster-secret-key", "chronosmesh-secret-key-guru-2024"]
    allowed = {"api/auth.py", "docs/GAP_ANALYSIS.md", "docs/COMPLETION_STATUS.md"}
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, cwd=ROOT,
                           check=True).stdout.splitlines()
    for rel in files:
        if rel in allowed or rel.startswith(("tests/", "venv/", "frontend/node_modules/", "frontend/dist/")):
            continue
        path = ROOT / rel
        if not path.is_file() or path.suffix in (".docx", ".png", ".jpg", ".ico", ".lock", ".json") and "package" in rel:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for needle in leaked:
            assert needle not in text, f"{rel} contains a previously committed secret ({needle})"
    assert not [f for f in files if f.endswith(".pyc")], "compiled files must not be tracked"


def test_otel_collector_configs_are_valid_pipelines():
    for name in ("otel-collector.yaml", "otel-collector-aws.yaml"):
        cfg = yaml_file(f"observability/{name}")
        for pipe in cfg["service"]["pipelines"].values():
            for kind in ("receivers", "exporters"):
                for comp in pipe[kind]:
                    top = {"receivers": "receivers", "exporters": "exporters"}[kind]
                    defined = set(cfg.get(top, {})) | set(cfg.get("connectors", {}))
                    assert comp in defined, f"{name}: {comp} not defined"


def test_kubernetes_manifests_parse_and_keep_secrets_out_of_configmaps():
    docs = []
    for name in ("deployment.yaml", "service.yaml", "configmap.yaml", "hpa.yaml", "secret.example.yaml"):
        docs += [d for d in yaml.safe_load_all((ROOT / "k8s" / name).read_text()) if d]
    kinds = {d["kind"] for d in docs}
    assert {"Deployment", "StatefulSet", "Service", "ConfigMap", "HorizontalPodAutoscaler", "Secret"} <= kinds
    cfg = next(d for d in docs if d["kind"] == "ConfigMap")
    for key in cfg["data"]:
        assert not re.search(r"SECRET|PASSWORD|TOKEN|KEY", key), f"secret-like key {key} in a ConfigMap"
    for d in docs:
        if d["kind"] == "Deployment":
            pod = d["spec"]["template"]["spec"]
            assert pod["securityContext"]["runAsNonRoot"] is True
            assert pod["containers"][0]["securityContext"]["allowPrivilegeEscalation"] is False
    assert {d["metadata"]["name"] for d in docs if d["kind"] == "Deployment"} == {"chronosmesh-api", "chronosmesh-worker"}


class _CfnLoader(yaml.SafeLoader):
    """SafeLoader that tolerates CloudFormation short-form tags (!Ref, !Sub, ...)."""


def _cfn_tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node, deep=True)}
    return {suffix: loader.construct_mapping(node, deep=True)}


_CfnLoader.add_multi_constructor("!", _cfn_tag)


def _template(name):
    return yaml.load((ROOT / "infrastructure/cloudformation" / name).read_text(), Loader=_CfnLoader)


def test_alb_listener_rules_respect_the_five_condition_value_limit():
    """AWS rejects a rule with more than 5 condition values in total; cfn-lint does not catch it."""
    rules = [(n, r) for n, r in _template("app.yaml")["Resources"].items()
             if r["Type"] == "AWS::ElasticLoadBalancingV2::ListenerRule"]
    assert len(rules) >= 4
    priorities = []
    for name, r in rules:
        total = 0
        for cond in r["Properties"]["Conditions"]:
            for key in ("HttpHeaderConfig", "PathPatternConfig", "HostHeaderConfig", "QueryStringConfig"):
                if key in cond:
                    total += len(cond[key].get("Values", []))
        assert total <= 5, f"{name} has {total} condition values (limit 5)"
        priorities.append(r["Properties"]["Priority"])
    assert len(priorities) == len(set(priorities)), "duplicate listener rule priorities"


def test_every_cloudfront_path_forwarded_to_the_alb_has_a_listener_rule():
    t = _template("app.yaml")["Resources"]
    behaviours = [b["PathPattern"] for b in t["Distribution"]["Properties"]["DistributionConfig"]["CacheBehaviors"]]
    rule_paths = []
    for r in t.values():
        if r["Type"] == "AWS::ElasticLoadBalancingV2::ListenerRule":
            for cond in r["Properties"]["Conditions"]:
                rule_paths += cond.get("PathPatternConfig", {}).get("Values", [])
    import fnmatch

    def probes(pattern):
        """Concrete paths CloudFront could send for this behaviour."""
        if pattern.endswith("/*"):
            return [pattern[:-2] + "/x"]
        if pattern.endswith("*"):
            return [pattern[:-1], pattern[:-1] + "/x"]
        return [pattern]

    for pattern in behaviours:
        for probe in probes(pattern):
            assert any(fnmatch.fnmatch(probe, p) for p in rule_paths), \
                f"CloudFront forwards {pattern} (e.g. {probe}) but the ALB has no rule for it"


def test_task_definitions_inject_secrets_not_plaintext():
    t = _template("app.yaml")["Resources"]
    api = t["ApiTaskDefinition"]["Properties"]["ContainerDefinitions"][0]
    secret_names = {s["Name"] for s in api["Secrets"]}
    assert {"JWT_SECRET_KEY", "METRICS_TOKEN", "AUTH_PASSWORD_ADMIN", "AUTH_PASSWORD_ANALYST", "AUTH_PASSWORD_VIEWER"} <= secret_names
    must_be_secret = {"JWT_SECRET_KEY", "METRICS_TOKEN", "AUTH_PASSWORD_ADMIN", "AUTH_PASSWORD_ANALYST", "AUTH_PASSWORD_VIEWER"}
    for env in api["Environment"]:
        assert env["Name"] not in must_be_secret and not env["Name"].startswith("AUTH_PASSWORD_"), \
            f"secret {env['Name']} must be injected from Secrets Manager, not set as plaintext"
    assert api["ReadonlyRootFilesystem"] is True


def test_every_cloudfront_behaviour_applies_the_security_headers_policy():
    """HSTS & friends must apply to API/Grafana responses too, not only to the S3 default behaviour."""
    cfg = _template("app.yaml")["Resources"]["Distribution"]["Properties"]["DistributionConfig"]
    behaviours = [cfg["DefaultCacheBehavior"]] + cfg["CacheBehaviors"]
    missing = [b.get("PathPattern", "default") for b in behaviours if "ResponseHeadersPolicyId" not in b]
    assert not missing, f"no security-headers policy on: {missing}"
