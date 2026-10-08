import logging
import time
from typing import List, Optional, Callable, Dict, Any

from chronosmesh.events.event import Event

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False


class InMemoryEventConsumer:
    """In-memory event consumer for testing and local development without Kafka."""

    def __init__(self, events: Optional[List[Event]] = None) -> None:
        self.events = events or []
        self.handlers: List[Callable[[Event], None]] = []
        self._running = False
        self._position = 0

    def add_events(self, events: List[Event]) -> None:
        self.events.extend(events)

    def add_event(self, event: Event) -> None:
        self.events.append(event)

    def subscribe(self, topics: List[str]) -> None:
        pass  # topics ignored for in-memory

    def commit(self) -> None:
        pass  # offset commit is a no-op

    def close(self) -> None:
        self._running = False

    def consume(self, timeout: float = 1.0) -> Optional[Event]:
        if self._position < len(self.events):
            event = self.events[self._position]
            self._position += 1
            return event
        time.sleep(min(timeout, 0.1))
        return None

    def consume_batch(self, max_messages: int = 100, timeout: float = 5.0) -> List[Event]:
        batch = []
        start = time.time()
        while len(batch) < max_messages and (time.time() - start) < timeout:
            event = self.consume(timeout=0.1)
            if event:
                batch.append(event)
            else:
                break
        return batch

    def set_event_handler(self, handler: Callable[[Event], None]) -> None:
        self.handlers.append(handler)

    def run(self, handler: Optional[Callable[[Event], None]] = None) -> None:
        self._running = True
        cb = handler or (self.handlers[0] if self.handlers else None)
        while self._running:
            event = self.consume(timeout=0.1)
            if event and cb:
                cb(event)
            elif not event:
                break


class KafkaEventConsumer:
    """Kafka-based event consumer with fallback to InMemoryEventConsumer."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "chronosmesh",
        topics: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        self.fallback = None
        if not KAFKA_AVAILABLE:
            logger.warning("confluent_kafka not installed, falling back to InMemoryEventConsumer")
            self.fallback = InMemoryEventConsumer()
            if topics:
                self.fallback.subscribe(topics)
            return

        conf = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
        if config:
            conf.update(config)

        self.consumer = Consumer(conf)
        self.handlers: List[Callable[[Event], None]] = []
        self._running = False
        
        if topics:
            self.subscribe(topics)

    def subscribe(self, topics: List[str]) -> None:
        if self.fallback:
            return self.fallback.subscribe(topics)
        self.consumer.subscribe(topics)

    def commit(self) -> None:
        if self.fallback:
            return self.fallback.commit()
        self.consumer.commit()

    def close(self) -> None:
        self._running = False
        if self.fallback:
            return self.fallback.close()
        self.consumer.close()

    def consume(self, timeout: float = 1.0) -> Optional[Event]:
        if self.fallback:
            return self.fallback.consume(timeout)

        msg = self.consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            else:
                raise KafkaException(msg.error())
        
        import json
        payload = json.loads(msg.value().decode("utf-8"))
        return Event.from_dict(payload)

    def consume_batch(self, max_messages: int = 100, timeout: float = 5.0) -> List[Event]:
        if self.fallback:
            return self.fallback.consume_batch(max_messages, timeout)

        batch = []
        start = time.time()
        while len(batch) < max_messages and (time.time() - start) < timeout:
            msg = self.consumer.poll(0.1)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    raise KafkaException(msg.error())
            import json
            payload = json.loads(msg.value().decode("utf-8"))
            batch.append(Event.from_dict(payload))
        return batch

    def set_event_handler(self, handler: Callable[[Event], None]) -> None:
        if self.fallback:
            return self.fallback.set_event_handler(handler)
        self.handlers.append(handler)

    def run(self, handler: Optional[Callable[[Event], None]] = None) -> None:
        if self.fallback:
            return self.fallback.run(handler)
            
        self._running = True
        cb = handler or (self.handlers[0] if self.handlers else None)
        try:
            while self._running:
                event = self.consume(timeout=1.0)
                if event and cb:
                    cb(event)
        finally:
            self.close()
