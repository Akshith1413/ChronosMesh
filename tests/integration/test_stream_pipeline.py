import pytest
from chronosmesh.events.event import Event
from chronosmesh.stream.processor import StreamProcessor

def test_stream_pipeline():
    processor = StreamProcessor()
    
    events = []
    # Create a linear chain of 20 events
    for i in range(1, 21):
        vc = {"service": i}
        e = Event(event_id=f"E{i}", event_type="PipelineEvent", vector_clock=vc)
        events.append(e)
        
    result = processor.process_batch(events)
    assert result["dag_nodes"] == 20
    assert result["dag_edges"] == 19
    
    stats = processor.get_statistics()
    assert stats["processed_events"] == 20
