"""Entry point: ``python -m chronosmesh.worker`` (the ECS worker task runs this)."""

from __future__ import annotations

import logging
import os
import signal
import sys

from chronosmesh.config import get_settings
from chronosmesh.persistence import create_repository
from chronosmesh.transport.sqs import SqsTransport
from chronosmesh.worker.service import Worker


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
    settings = get_settings()
    if not settings.sqs_events_queue_url:
        logging.error("SQS_EVENTS_QUEUE_URL is not configured; nothing to consume")
        return 2

    publisher = None
    if os.getenv("CLOUDWATCH_METRICS", "false").lower() in ("1", "true", "yes"):
        from chronosmesh.observability.cloudwatch import CloudWatchPublisher

        publisher = CloudWatchPublisher(settings.metrics_namespace, settings.aws_region, dimensions={"Service": "worker"})

    port = os.getenv("WORKER_METRICS_PORT")
    if port:
        from prometheus_client import start_http_server

        start_http_server(int(port))

    worker = Worker(settings, create_repository(settings),
                    SqsTransport(settings.sqs_events_queue_url, settings.aws_region), publisher=publisher)
    signal.signal(signal.SIGTERM, lambda *_: worker.stop())      # ECS stop -> graceful drain
    signal.signal(signal.SIGINT, lambda *_: worker.stop())
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
