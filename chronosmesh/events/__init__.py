"""
Event Model — Core event data structures and simulation utilities.
"""

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.events.generator import EventGenerator, ScenarioBuilder
from chronosmesh.events.schemas import EventSchema, validate_event

__all__ = [
    "Event",
    "EventMetadata",
    "EventGenerator",
    "ScenarioBuilder",
    "EventSchema",
    "validate_event",
]
