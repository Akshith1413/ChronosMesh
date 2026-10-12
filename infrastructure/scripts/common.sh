#!/usr/bin/env bash
# Shared settings for the ChronosMesh deployment scripts. Source this file; do not execute it.
# Credentials come from the standard AWS environment/profile -- nothing is stored in the repo.
set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-prod}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-south-2}}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""

DATA_STACK="chronosmesh-${ENVIRONMENT}-data"
APP_STACK="chronosmesh-${ENVIRONMENT}-app"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CFN_DIR="$REPO_ROOT/infrastructure/cloudformation"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "'$1' is required but not installed"; }

stack_output() {  # stack_output <stack> <OutputKey>
  aws cloudformation describe-stacks --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text
}

account_id() { aws sts get-caller-identity --query Account --output text; }
