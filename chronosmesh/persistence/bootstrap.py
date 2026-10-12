"""Create the DynamoDB tables, S3 bucket and SQS queues ChronosMesh needs.

Used by ``docker compose`` against a local AWS emulator (``AWS_ENDPOINT_URL``) and handy for a
throw-away dev account. Production infrastructure is created by ``infrastructure/`` (IaC), not this.

    python -m chronosmesh.persistence.bootstrap
"""

from __future__ import annotations

import json
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

from chronosmesh.config import get_settings
from chronosmesh.persistence.aws_schema import create_tables

log = logging.getLogger("chronosmesh.bootstrap")


def ensure_bucket(s3, name: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=name)
        return
    except ClientError:
        pass
    kwargs = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
    s3.create_bucket(Bucket=name, **kwargs)
    s3.put_public_access_block(Bucket=name, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})


def ensure_queues(sqs, events_name: str, max_receive: int = 5) -> str:
    dlq = sqs.create_queue(QueueName=f"{events_name}-dlq", Attributes={"MessageRetentionPeriod": "1209600"})["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    return sqs.create_queue(QueueName=events_name, Attributes={
        "VisibilityTimeout": "120",
        "MessageRetentionPeriod": "345600",
        "ReceiveMessageWaitTimeSeconds": "20",
        "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": str(max_receive)}),
    })["QueueUrl"]


def main() -> int:
    logging.basicConfig(level="INFO", format="%(message)s")
    s = get_settings()
    region = s.aws_region
    if not (s.ddb_executions_table and s.s3_data_bucket and s.sqs_events_queue_url):
        log.error("set DYNAMODB_*_TABLE, S3_DATA_BUCKET and SQS_EVENTS_QUEUE_URL")
        return 2
    created = create_tables(boto3.client("dynamodb", region_name=region), s)
    log.info("DynamoDB tables created: %s", created or "none (already present)")
    ensure_bucket(boto3.client("s3", region_name=region), s.s3_data_bucket, region)
    log.info("S3 bucket ready: %s", s.s3_data_bucket)
    queue = ensure_queues(boto3.client("sqs", region_name=region), s.sqs_events_queue_url.rstrip("/").rsplit("/", 1)[-1])
    log.info("SQS queue ready: %s", queue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
