#!/usr/bin/env bash
# Create/update the monthly cost budget (global service, so managed here rather than in CloudFormation).
#   BUDGET_USD=100 ./budget.sh
source "$(dirname "$0")/common.sh"
need aws
BUDGET_USD="${BUDGET_USD:-100}"
ACCOUNT="$(account_id)"
TOPIC="$(stack_output "$DATA_STACK" AlertsTopicArn)"
NAME="chronosmesh-${ENVIRONMENT}-monthly"

budget=$(cat <<JSON
{"BudgetName":"$NAME","BudgetType":"COST","TimeUnit":"MONTHLY","BudgetLimit":{"Amount":"$BUDGET_USD","Unit":"USD"}}
JSON
)
notifications=$(cat <<JSON
[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80,"ThresholdType":"PERCENTAGE"},"Subscribers":[{"SubscriptionType":"SNS","Address":"$TOPIC"}]},
 {"Notification":{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"},"Subscribers":[{"SubscriptionType":"SNS","Address":"$TOPIC"}]}]
JSON
)
if aws budgets describe-budget --account-id "$ACCOUNT" --budget-name "$NAME" >/dev/null 2>&1; then
  log "updating budget $NAME to \$$BUDGET_USD/month"
  aws budgets update-budget --account-id "$ACCOUNT" --new-budget "$budget"
else
  log "creating budget $NAME (\$$BUDGET_USD/month, alerts at 80% actual and 100% forecast)"
  aws budgets create-budget --account-id "$ACCOUNT" --budget "$budget" --notifications-with-subscribers "$notifications"
fi
