import pytest
from chronosmesh.events.event import Event
from chronosmesh.stream.consumer import InMemoryEventConsumer

def test_consume_single_event():
    e = Event()
    consumer = InMemoryEventConsumer([e])
    res = consumer.consume()
    assert res == e
    assert consumer.consume(timeout=0) is None

def test_consume_batch():
    events = [Event() for _ in range(5)]
    consumer = InMemoryEventConsumer(events)
    batch = consumer.consume_batch(max_messages=3)
    assert len(batch) == 3
    batch2 = consumer.consume_batch(max_messages=3)
    assert len(batch2) == 2

def test_subscribe_topics():
    consumer = InMemoryEventConsumer()
    consumer.subscribe(["test_topic"])
    assert consumer.consume(timeout=0) is None

def test_event_handler_callback():
    e = Event()
    consumer = InMemoryEventConsumer([e])
    handled = []
    consumer.set_event_handler(lambda x: handled.append(x))
    consumer.run()
    assert len(handled) == 1
    assert handled[0] == e

def test_empty_consume_returns_none():
    consumer = InMemoryEventConsumer()
    assert consumer.consume(timeout=0.1) is None

def test_commit_and_close():
    consumer = InMemoryEventConsumer()
    consumer.commit()
    consumer.close()
