import pytest
from chronosmesh.events.event import Event
from chronosmesh.causality.buffer import EventBuffer, BufferPolicy

def test_add_event_with_no_parents_emits_immediately():
    buf = EventBuffer()
    e = Event(event_id="1")
    emitted = buf.add(e)
    assert len(emitted) == 1
    assert emitted[0].event_id == "1"

def test_add_event_with_missing_parent_buffers():
    buf = EventBuffer()
    e = Event(event_id="2", parent_event_ids=["1"])
    emitted = buf.add(e)
    assert len(emitted) == 0
    assert buf.pending_count() == 1

def test_parent_arrival_releases_child():
    buf = EventBuffer()
    e2 = Event(event_id="2", parent_event_ids=["1"])
    e1 = Event(event_id="1")
    buf.add(e2)
    emitted = buf.add(e1)
    assert len(emitted) == 2
    ids = {e.event_id for e in emitted}
    assert ids == {"1", "2"}
    assert buf.pending_count() == 0

def test_flush_releases_all():
    buf = EventBuffer()
    e = Event(event_id="2", parent_event_ids=["1"])
    buf.add(e)
    emitted = buf.flush()
    assert len(emitted) == 1
    assert buf.pending_count() == 0

def test_watermark_advancement():
    buf = EventBuffer()
    e = Event(event_id="2", parent_event_ids=["1"], arrival_time_ms=1000)
    buf.add(e)
    emitted = buf.advance_watermark(7000) # max_wait_time_ms is 5000 by default, 7000 - 5000 = 2000 >= 1000
    assert len(emitted) == 1

def test_max_buffer_size_policy():
    policy = BufferPolicy(max_buffer_size=1)
    buf = EventBuffer(policy=policy)
    e1 = Event(event_id="2", parent_event_ids=["1"])
    e2 = Event(event_id="3", parent_event_ids=["1"])
    buf.add(e1)
    buf.add(e2)
    assert buf.pending_count() == 2

def test_pending_count():
    buf = EventBuffer()
    assert buf.pending_count() == 0
    buf.add(Event(event_id="2", parent_event_ids=["1"]))
    assert buf.pending_count() == 1
