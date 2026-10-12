#!/usr/bin/env bash
# Print how to read the generated sign-in credentials, or (with --show) print them.
#   ./credentials.sh           prints the commands
#   ./credentials.sh --show    prints usernames and passwords to the terminal (do not paste them into chats/tickets)
source "$(dirname "$0")/common.sh"
need aws
for user in admin analyst viewer; do
  id="chronosmesh/${ENVIRONMENT}/user-${user}"
  if [[ "${1:-}" == "--show" ]]; then
    pw="$(aws secretsmanager get-secret-value --secret-id "$id" --query SecretString --output text | python3 -c 'import json,sys;print(json.load(sys.stdin)["password"])')"
    printf '%-8s %s\n' "$user" "$pw"
  else
    echo "aws secretsmanager get-secret-value --secret-id $id --query SecretString --output text   # username: $user"
  fi
done
echo
echo "Grafana admin: aws secretsmanager get-secret-value --secret-id chronosmesh/${ENVIRONMENT}/grafana-admin --query SecretString --output text"
