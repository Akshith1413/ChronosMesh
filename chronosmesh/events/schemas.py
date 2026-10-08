import json
from typing import Tuple, List, Any, Dict, Optional
from pydantic import BaseModel, Field

from chronosmesh.events.event import Event, EventMetadata

class EventMetadataSchema(BaseModel):
    region: str = "unknown"
    availability_zone: str = "unknown"
    clock_uncertainty_ms: float = 5.0
    tags: Dict[str, str] = Field(default_factory=dict)

class EventSchema(BaseModel):
    event_id: str
    service_id: str
    event_type: str
    timestamp_ms: float
    lamport_ts: int
    vector_clock: Dict[str, int]
    hlc_ts: Optional[Dict[str, Any]] = None
    trace_id: str
    span_id: str
    parent_event_ids: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: EventMetadataSchema = Field(default_factory=EventMetadataSchema)
    arrival_time_ms: float

def validate_event(event_or_dict: Any) -> Tuple[bool, List[str]]:
    if isinstance(event_or_dict, Event):
        data = event_or_dict.to_dict()
    else:
        data = event_or_dict
    try:
        EventSchema(**data)
        return True, []
    except Exception as e:
        return False, [str(e)]

def serialize_event(event: Event) -> bytes:
    return json.dumps(event.to_dict()).encode("utf-8")

def deserialize_event(data: bytes) -> Event:
    d = json.loads(data.decode("utf-8"))
    return Event.from_dict(d)
