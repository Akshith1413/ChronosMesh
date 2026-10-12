#!/usr/bin/env bash
# Stop (or resume) the billable compute without destroying anything.
#   ./scale.sh down        API, worker and Grafana tasks -> 0   (ALB/CloudFront still bill a little)
#   ./scale.sh up [api=1] [worker=1] [grafana=1]
source "$(dirname "$0")/common.sh"
need aws
action="${1:-}"; shift || true
CLUSTER="$(stack_output "$APP_STACK" ClusterName)"
API="$(stack_output "$APP_STACK" ApiServiceName)"
WORKER="$(stack_output "$APP_STACK" WorkerServiceName)"
GRAFANA="$(stack_output "$APP_STACK" GrafanaServiceName)"
scalable() { echo "service/$CLUSTER/$API"; }

case "$action" in
  down)
    # Pin autoscaling at 0 first, otherwise it scales the API straight back up.
    aws application-autoscaling register-scalable-target --service-namespace ecs --scalable-dimension ecs:service:DesiredCount \
      --resource-id "$(scalable)" --min-capacity 0 --max-capacity 0 >/dev/null
    for s in "$API" "$WORKER" "$GRAFANA"; do aws ecs update-service --cluster "$CLUSTER" --service "$s" --desired-count 0 >/dev/null; done
    log "all tasks stopping; the site returns 503 until you run: scale.sh up" ;;
  up)
    api=1; worker=1; grafana=1
    for kv in "$@"; do eval "${kv%%=*}=${kv#*=}"; done
    aws application-autoscaling register-scalable-target --service-namespace ecs --scalable-dimension ecs:service:DesiredCount \
      --resource-id "$(scalable)" --min-capacity 1 --max-capacity 3 >/dev/null
    aws ecs update-service --cluster "$CLUSTER" --service "$API" --desired-count "$api" >/dev/null
    aws ecs update-service --cluster "$CLUSTER" --service "$WORKER" --desired-count "$worker" >/dev/null
    aws ecs update-service --cluster "$CLUSTER" --service "$GRAFANA" --desired-count "$grafana" >/dev/null
    log "services starting; allow ~2 minutes" ;;
  *) die "usage: scale.sh down | up [api=N] [worker=N] [grafana=N]" ;;
esac
