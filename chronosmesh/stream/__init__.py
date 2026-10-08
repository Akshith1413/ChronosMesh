"""
Stream Processing — Kafka consumer, stateful DAG construction processor,
and event windowing logic for real-time causal reconstruction.
"""

from chronosmesh.stream.consumer import KafkaEventConsumer
from chronosmesh.stream.processor import StreamProcessor
from chronosmesh.stream.windowing import (
    WindowStrategy,
    TumblingWindow,
    SlidingWindow,
    SessionWindow,
)

__all__ = [
    "KafkaEventConsumer",
    "StreamProcessor",
    "WindowStrategy",
    "TumblingWindow",
    "SlidingWindow",
    "SessionWindow",
]
