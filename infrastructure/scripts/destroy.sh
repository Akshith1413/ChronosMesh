#!/usr/bin/env bash
# Tear everything down. The data stack holds your data: it is only removed with --include-data.
#   ./destroy.sh                 removes the application stack (compute, ALB, CloudFront, front-end bucket)
#   ./destroy.sh --include-data  also removes tables, queues, secrets, ECR repos and the data bucket
source "$(dirname "$0")/common.sh"
need aws

empty_bucket() {  # empty_bucket <bucket>  (versioned buckets need every version and delete marker removed)
  local b="$1"
  aws s3api head-bucket --bucket "$b" 2>/dev/null || return 0
  log "emptying s3://$b"
  python3 - "$b" <<'PY'
import sys, boto3
b = sys.argv[1]
s3 = boto3.client("s3")
for page in s3.get_paginator("list_object_versions").paginate(Bucket=b):
    objs = [{"Key": v["Key"], "VersionId": v["VersionId"]} for v in page.get("Versions", []) + page.get("DeleteMarkers", [])]
    for i in range(0, len(objs), 1000):
        s3.delete_objects(Bucket=b, Delete={"Objects": objs[i:i + 1000], "Quiet": True})
PY
}

if aws cloudformation describe-stacks --stack-name "$APP_STACK" >/dev/null 2>&1; then
  empty_bucket "$(stack_output "$APP_STACK" FrontendBucketName)"
  log "deleting $APP_STACK"
  aws cloudformation delete-stack --stack-name "$APP_STACK"
  aws cloudformation wait stack-delete-complete --stack-name "$APP_STACK"
fi
if [[ "${1:-}" == "--include-data" ]]; then
  empty_bucket "$(stack_output "$DATA_STACK" DataBucketName)"
  for repo in api worker grafana; do
    aws ecr batch-delete-image --repository-name "chronosmesh-${ENVIRONMENT}/$repo" \
      --image-ids "$(aws ecr list-images --repository-name "chronosmesh-${ENVIRONMENT}/$repo" --query 'imageIds[*]' --output json)" >/dev/null 2>&1 || true
  done
  aws budgets delete-budget --account-id "$(account_id)" --budget-name "chronosmesh-${ENVIRONMENT}-monthly" 2>/dev/null || true
  log "deleting $DATA_STACK"
  aws cloudformation delete-stack --stack-name "$DATA_STACK"
  aws cloudformation wait stack-delete-complete --stack-name "$DATA_STACK"
else
  log "data stack kept (tables, queues, secrets, ECR). Use --include-data to remove it."
fi
