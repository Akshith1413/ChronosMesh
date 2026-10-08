"""
ChronosMesh Kafka Topic Management.

Provides utilities for ensuring target topics ('events.raw', 'events.causal')
exist with proper partitioning and replication settings.
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

RAW_EVENTS_TOPIC = os.getenv("KAFKA_RAW_TOPIC", "events.raw")
CAUSAL_EVENTS_TOPIC = os.getenv("KAFKA_CAUSAL_TOPIC", "events.causal")
DEFAULT_TOPICS = [RAW_EVENTS_TOPIC, CAUSAL_EVENTS_TOPIC]

try:
    from confluent_kafka.admin import AdminClient, NewTopic
    KAFKA_ADMIN_AVAILABLE = True
except ImportError:
    KAFKA_ADMIN_AVAILABLE = False


def ensure_topics_exist(
    bootstrap_servers: Optional[str] = None,
    topics: Optional[List[str]] = None,
    num_partitions: int = 3,
    replication_factor: int = 1,
) -> bool:
    """Ensure target Kafka topics exist, creating them if necessary."""
    servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    target_topics = topics or DEFAULT_TOPICS

    if not KAFKA_ADMIN_AVAILABLE:
        logger.info("confluent_kafka admin client unavailable. Topic check skipped.")
        return False

    try:
        admin_client = AdminClient({"bootstrap.servers": servers, "socket.timeout.ms": 2000})
        cluster_metadata = admin_client.list_topics(timeout=2.0)
        existing_topics = set(cluster_metadata.topics.keys())

        missing_topics = [t for t in target_topics if t not in existing_topics]
        if not missing_topics:
            logger.info(f"All target Kafka topics exist: {target_topics}")
            return True

        new_topics = [
            NewTopic(t, num_partitions=num_partitions, replication_factor=replication_factor)
            for t in missing_topics
        ]
        futures = admin_client.create_topics(new_topics)
        for topic, f in futures.items():
            try:
                f.result()
                logger.info(f"Created Kafka topic: {topic}")
            except Exception as e:
                logger.warning(f"Topic creation for {topic} resulted in: {e}")

        return True
    except Exception as exc:
        logger.warning(f"Could not connect to Kafka AdminClient at {servers}: {exc}")
        return False
