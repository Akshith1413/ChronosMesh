"""
ChronosMesh Kafka Event Producer.

Provides reliable publishing of canonical distributed events to Kafka topics
(e.g., 'events.raw', 'events.causal') with validation, retries, and transparent
in-memory fallback when Kafka broker is unreachable.
"""

import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

from chronosmesh.events.event import Event

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Producer, KafkaException
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False


class InMemoryEventProducer:
    """In-memory event producer for local testing and decoupled execution."""

    def __init__(self) -> None:
        self.published_events: Dict[str, List[Event]] = {}
        self.subscribers: Dict[str, List[Callable[[Event], None]]] = {}

    def publish_event(self, event: Event, topic: str = "events.raw") -> bool:
        if topic not in self.published_events:
            self.published_events[topic] = []
        self.published_events[topic].append(event)
        
        # Notify subscribers
        for sub in self.subscribers.get(topic, []):
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Error in subscriber callback for topic {topic}: {e}")
        return True

    def publish_events(self, events: List[Event], topic: str = "events.raw") -> int:
        count = 0
        for ev in events:
            if self.publish_event(ev, topic):
                count += 1
        return count

    def subscribe(self, topic: str, callback: Callable[[Event], None]) -> None:
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    def get_events(self, topic: str = "events.raw") -> List[Event]:
        return list(self.published_events.get(topic, []))

    def flush(self, timeout: float = 1.0) -> None:
        pass

    def clear(self) -> None:
        self.published_events.clear()


class KafkaEventProducer:
    """Production Kafka event producer with automatic in-memory fallback."""

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        default_topic: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.default_topic = default_topic or os.getenv("KAFKA_RAW_TOPIC", "events.raw")
        self.fallback: Optional[InMemoryEventProducer] = None
        self.producer = None
        self._delivery_failures = 0
        self._delivery_successes = 0
        self._published_count = 0

        force_in_memory = os.getenv("CHRONOSMESH_FORCE_IN_MEMORY_KAFKA", "false").lower() in ("true", "1")
        if force_in_memory or not KAFKA_AVAILABLE:
            if not KAFKA_AVAILABLE:
                logger.info("confluent_kafka not installed. Using InMemoryEventProducer fallback.")
            else:
                logger.info("CHRONOSMESH_FORCE_IN_MEMORY_KAFKA=true. Using InMemoryEventProducer.")
            self.fallback = InMemoryEventProducer()
            return

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": "chronosmesh-producer",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 100,
        }
        if config:
            conf.update(config)

        try:
            self.producer = Producer(conf)
            logger.info(f"KafkaEventProducer connected to {self.bootstrap_servers}")
        except Exception as exc:
            logger.warning(f"Failed to initialize Kafka Producer ({exc}). Falling back to in-memory producer.")
            self.fallback = InMemoryEventProducer()

    def _delivery_callback(self, err, msg):
        if err is not None:
            self._delivery_failures += 1
            logger.error(f"Message delivery failed: {err}")
        else:
            self._delivery_successes += 1

    def publish_event(self, event: Event, topic: Optional[str] = None) -> bool:
        """Publish a single event to Kafka topic with validation."""
        target_topic = topic or self.default_topic
        self._published_count += 1

        if self.fallback:
            return self.fallback.publish_event(event, target_topic)

        try:
            payload_dict = event.to_dict()
            # Ensure JSON serializable
            payload_bytes = json.dumps(payload_dict).encode("utf-8")
            key_bytes = event.event_id.encode("utf-8") if event.event_id else None

            self.producer.produce(
                topic=target_topic,
                key=key_bytes,
                value=payload_bytes,
                callback=self._delivery_callback,
            )
            # Poll non-blocking to trigger callbacks
            self.producer.poll(0)
            return True
        except Exception as exc:
            logger.warning(f"Kafka produce error ({exc}). Routing to fallback.")
            if not self.fallback:
                self.fallback = InMemoryEventProducer()
            return self.fallback.publish_event(event, target_topic)

    def publish_events(self, events: List[Event], topic: Optional[str] = None) -> int:
        """Publish a batch of events."""
        target_topic = topic or self.default_topic
        count = 0
        for ev in events:
            if self.publish_event(ev, target_topic):
                count += 1
        self.flush()
        return count

    def flush(self, timeout: float = 2.0) -> None:
        if self.producer:
            try:
                self.producer.flush(timeout)
            except Exception as e:
                logger.error(f"Error flushing Kafka producer: {e}")
        elif self.fallback:
            self.fallback.flush(timeout)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "published": self._published_count,
            "successes": self._delivery_successes,
            "failures": self._delivery_failures,
            "in_memory": len(self.fallback.published_events.get(self.default_topic, [])) if self.fallback else 0,
        }
