import pytest
from chronosmesh.events.event import Event
from chronosmesh.stream.processor import StreamProcessor

def test_stream_processor_process_event():
    processor = StreamProcessor()
    e = Event(event_id="E1", vector_clock={"a":1})
    res = processor.process_event(e)
    assert res["dag_nodes"] == 1
    assert processor.get_statistics()["processed_events"] == 1

def test_stream_processor_process_batch():
    processor = StreamProcessor()
    events = [Event(event_id=f"E{i}", vector_clock={"a":i}) for i in range(1, 4)]
    res = processor.process_batch(events)
    assert res["dag_nodes"] == 3
    assert processor.get_statistics()["processed_events"] == 3

def test_stream_processor_get_dag():
    processor = StreamProcessor()
    processor.process_event(Event(event_id="E1", vector_clock={"a":1}))
    dag = processor.get_dag()
    assert len(dag.nodes) == 1

def test_stream_processor_get_anomalies():
    processor = StreamProcessor()
    assert processor.get_anomalies() == []

def test_stream_processor_flush():
    processor = StreamProcessor()
    processor.flush()
    # just testing that it doesn't raise exception

def test_stream_processor_reset():
    processor = StreamProcessor()
    processor.process_event(Event(event_id="E1", vector_clock={"a":1}))
    processor.reset()
    assert processor.get_statistics()["processed_events"] == 0
    
def test_stream_processor_callbacks():
    handled = []
    processor = StreamProcessor(event_callback=lambda x: handled.append(x))
    processor.process_event(Event(event_id="E1", vector_clock={"a":1}))
    assert len(handled) == 1
