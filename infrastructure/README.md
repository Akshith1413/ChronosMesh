# Infrastructure

```
infrastructure/
├── cloudformation/
│   ├── data.yaml          long-lived: DynamoDB, S3, SQS (+DLQ), SNS, Secrets Manager, ECR
│   ├── app.yaml           replaceable: ECS Fargate (API, worker, Grafana), ALB, CloudFront + S3, IAM, alarms, dashboard
│   └── github-oidc.yaml   optional: role for the GitHub Actions deploy workflow (no stored keys)
├── scripts/
│   ├── deploy.sh          build + push images, deploy both stacks, publish the front end, smoke test
│   ├── budget.sh          monthly cost budget (global service, not available as a CloudFormation resource here)
│   ├── credentials.sh     how to read the generated sign-in passwords
│   ├── scale.sh           `down` / `up`: stop or resume billable compute
│   ├── destroy.sh         tear down (data is kept unless --include-data)
│   └── common.sh
├── task-definition.json   LEGACY: hand-written ECS task definition that referenced an image that was never pushed
├── trust.json             LEGACY: trust policy of the hand-made ECS roles
└── userdata.sh            LEGACY: bootstrap of the original single EC2 instance (`docker-compose.guru.yml`)
```

See [`docs/CLOUD_DEPLOYMENT.md`](../docs/CLOUD_DEPLOYMENT.md) for the architecture, costs and the runbook.
The templates are linted in CI (`cfn-lint`) and were validated against AWS before deployment.
