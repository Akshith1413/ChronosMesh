import pytest
from chronosmesh.events.event import Event
from chronosmesh.stream.windowing import TumblingWindow, SlidingWindow, SessionWindow

def test_tumbling_window_assignment():
    win = TumblingWindow(100)
    e1 = Event(timestamp_ms=50)
    e2 = Event(timestamp_ms=150)
    assert win.add_event(e1) == ["tumb_0"]
    assert win.add_event(e2) == ["tumb_1"]

def test_tumbling_window_completeness():
    win = TumblingWindow(100)
    e1 = Event(timestamp_ms=50)
    win.add_event(e1)
    assert e1 in win.get_window_events("tumb_0")

def test_sliding_window_overlap():
    win = SlidingWindow(window_size_ms=100, slide_ms=50)
    e1 = Event(timestamp_ms=75)
    keys = win.add_event(e1)
    assert "slide_0" in keys
    assert "slide_1" in keys

def test_session_window_grouping():
    win = SessionWindow(gap_ms=100)
    e1 = Event(trace_id="t1", timestamp_ms=0)
    e2 = Event(trace_id="t1", timestamp_ms=50)
    win.add_event(e1)
    win.add_event(e2)
    assert len(win.get_window_events("t1")) == 2

def test_session_window_gap_split():
    win = SessionWindow(gap_ms=100)
    e1 = Event(trace_id="t1", timestamp_ms=0)
    e2 = Event(trace_id="t1", timestamp_ms=150)
    win.add_event(e1)
    win.add_event(e2)
    assert len(win.get_window_events("t1")) == 1

def test_expire_old_windows():
    win = TumblingWindow(100)
    e1 = Event(timestamp_ms=50)
    win.add_event(e1)
    expired = win.expire_windows(150)
    assert "tumb_0" in expired
    assert "tumb_0" not in win.get_all_windows()

def test_get_all_windows():
    win = TumblingWindow(100)
    e1 = Event(timestamp_ms=50)
    win.add_event(e1)
    assert "tumb_0" in win.get_all_windows()
