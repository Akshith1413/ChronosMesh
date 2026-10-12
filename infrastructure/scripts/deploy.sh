#!/usr/bin/env bash
# Build, push and deploy ChronosMesh to AWS (ECS Fargate + ALB + CloudFront/S3).
#
#   ALERT_EMAIL=you@example.com ./infrastructure/scripts/deploy.sh
#
# Environment: ENVIRONMENT (prod) AWS_REGION (ap-south-2) ALERT_EMAIL BUDGET_USD (100)
#              IMAGE_TAG (default: <git sha>-<timestamp>)   SKIP_BUILD=1 (reuse IMAGE_TAG already in ECR)
# Idempotent: safe to re-run; only changed resources are updated.
source "$(dirname "$0")/common.sh"
need aws; need docker; need curl

ALERT_EMAIL="${ALERT_EMAIL:-}"
BUDGET_USD="${BUDGET_USD:-100}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo dev)-$(date +%Y%m%d%H%M%S)}"
ACCOUNT="$(account_id)"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
BUILD_DIR="$REPO_ROOT/infrastructure/.build"
mkdir -p "$BUILD_DIR"

log "account $ACCOUNT, region $REGION, environment $ENVIRONMENT, image tag $IMAGE_TAG"

# 1 ── data plane ------------------------------------------------------------------------------
log "deploying data stack $DATA_STACK"
aws cloudformation deploy --stack-name "$DATA_STACK" --template-file "$CFN_DIR/data.yaml" \
  --parameter-overrides "Environment=$ENVIRONMENT" "AlertEmail=$ALERT_EMAIL" \
  --tags Project=ChronosMesh "Environment=$ENVIRONMENT" --no-fail-on-empty-changeset
BUDGET_USD="$BUDGET_USD" "$(dirname "$0")/budget.sh" || warn "budget step failed (non-fatal)"

API_REPO="$(stack_output "$DATA_STACK" ApiRepositoryUri)"
WORKER_REPO="$(stack_output "$DATA_STACK" WorkerRepositoryUri)"
GRAFANA_REPO="$(stack_output "$DATA_STACK" GrafanaRepositoryUri)"

# 2 ── images ----------------------------------------------------------------------------------
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  log "logging in to ECR"
  aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
  for target in api worker grafana; do
    case $target in api) repo=$API_REPO;; worker) repo=$WORKER_REPO;; grafana) repo=$GRAFANA_REPO;; esac
    log "building and pushing $target -> $repo:$IMAGE_TAG"
    docker build -f "$REPO_ROOT/api/Dockerfile" --target "$target" -t "$repo:$IMAGE_TAG" "$REPO_ROOT"
    docker push "$repo:$IMAGE_TAG"
  done
fi

# 3 ── static front end (taken from the very image that will serve the API) -------------------
rm -rf "$BUILD_DIR/frontend-dist"
cid="$(docker create "$API_REPO:$IMAGE_TAG" 2>/dev/null || docker create "$API_REPO:$IMAGE_TAG")"
docker cp "$cid:/app/frontend/dist" "$BUILD_DIR/frontend-dist"
docker rm "$cid" >/dev/null

# 4 ── network discovery (default VPC, public subnets; no NAT gateway) -------------------------
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
[[ "$VPC_ID" != "None" ]] || die "no default VPC in $REGION; pass your own VPC via the template parameters"
SUBNETS="$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" Name=default-for-az,Values=true \
  --query 'Subnets[].SubnetId' --output text | tr '\t' ',')"
PREFIX_LIST="$(aws ec2 describe-managed-prefix-lists --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' --output text)"
[[ "$PREFIX_LIST" != "None" ]] || die "CloudFront origin-facing prefix list not found in $REGION"
ORIGIN_SECRET_ARN="$(stack_output "$DATA_STACK" OriginVerifySecretArn)"

# 5 ── application plane -----------------------------------------------------------------------
log "deploying application stack $APP_STACK"
aws cloudformation deploy --stack-name "$APP_STACK" --template-file "$CFN_DIR/app.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides "Environment=$ENVIRONMENT" "DataStackName=$DATA_STACK" \
    "OriginVerifySecretArn=$ORIGIN_SECRET_ARN" "VpcId=$VPC_ID" "SubnetIds=$SUBNETS" "CloudFrontPrefixListId=$PREFIX_LIST" \
    "ApiImage=$API_REPO:$IMAGE_TAG" "WorkerImage=$WORKER_REPO:$IMAGE_TAG" "GrafanaImage=$GRAFANA_REPO:$IMAGE_TAG" \
  --tags Project=ChronosMesh "Environment=$ENVIRONMENT" --no-fail-on-empty-changeset

SITE="$(stack_output "$APP_STACK" SiteUrl)"
FRONTEND_BUCKET="$(stack_output "$APP_STACK" FrontendBucketName)"
DISTRIBUTION="$(stack_output "$APP_STACK" DistributionId)"
CLUSTER="$(stack_output "$APP_STACK" ClusterName)"

# 6 ── publish the React build (hashed assets cache for a year; index.html is never cached) ---
log "publishing front end to s3://$FRONTEND_BUCKET"
aws s3 sync "$BUILD_DIR/frontend-dist" "s3://$FRONTEND_BUCKET" --delete --exclude index.html \
  --cache-control "public,max-age=31536000,immutable" --only-show-errors
aws s3 cp "$BUILD_DIR/frontend-dist/index.html" "s3://$FRONTEND_BUCKET/index.html" \
  --cache-control "no-cache" --content-type "text/html; charset=utf-8" --only-show-errors
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION" --paths "/*" >/dev/null

# 7 ── wait for health, then smoke test --------------------------------------------------------
log "waiting for ECS services to become stable (up to ~10 min)"
aws ecs wait services-stable --cluster "$CLUSTER" --services \
  "$(stack_output "$APP_STACK" ApiServiceName)" "$(stack_output "$APP_STACK" WorkerServiceName)" \
  "$(stack_output "$APP_STACK" GrafanaServiceName)"

log "smoke test: $SITE"
curl -fsS "$SITE/api/health"; echo
curl -fsS "$SITE/api/health/ready"; echo
curl -fsS -o /dev/null -w "front end: HTTP %{http_code}\n" "$SITE/"

cat <<MSG

ChronosMesh is live:
  Dashboard : $SITE
  Grafana   : $SITE/grafana/
  API docs  : $SITE/docs
  CloudWatch: $(stack_output "$APP_STACK" DashboardUrl)

Sign-in accounts (admin / analyst / viewer) have generated passwords:  infrastructure/scripts/credentials.sh
Alert email subscription must be confirmed from the message AWS sends to: ${ALERT_EMAIL:-<none>}
Stop paying for compute when you are not demoing:                       infrastructure/scripts/scale.sh down
MSG
