"""
ChronosMesh Apache Flink Streaming Pipeline.

Implements stateful stream processing with event-time watermarking,
bounded out-of-orderness windowing, causal reconstruction, anomaly detection,
and confidence scoring, bridging Kafka 'events.raw' to 'events.causal'.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from chronosmesh.events.event import Event
from chronosmesh.causality.buffer import EventBuffer, BufferPolicy
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.analysis.anomaly import CausalAnomalyDetector, AnomalyReport
from chronosmesh.analysis.confidence import ConfidenceScorer

logger = logging.getLogger(__name__)


class FlinkStreamingPipeline:
    """Stateful streaming pipeline representing Flink causal event processing."""

    def __init__(
        self,
        out_of_orderness_ms: Optional[float] = None,
        window_size_ms: Optional[float] = None,
        enable_anomaly_detection: bool = True,
        enable_confidence_scoring: bool = True,
        on_causal_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.out_of_orderness_ms = float(
            out_of_orderness_ms
            or os.getenv("FLINK_OUT_OF_ORDERNESS_MS", "500.0")
        )
        self.window_size_ms = float(
            window_size_ms
            or os.getenv("FLINK_WINDOW_MS", "1000.0")
        )
        self.enable_anomaly_detection = enable_anomaly_detection
        self.enable_confidence_scoring = enable_confidence_scoring
        self.on_causal_event = on_causal_event

        # Stateful components
        self.buffer_policy = BufferPolicy(
            max_buffer_size=5000,
            max_wait_time_ms=self.out_of_orderness_ms,
            watermark_interval_ms=100.0,
        )
        self.buffer = EventBuffer(self.buffer_policy)
        self.builder = CausalDAGBuilder()
        self.anomaly_detector = CausalAnomalyDetector(clock_skew_tolerance_ms=50.0)
        self.confidence_scorer = ConfidenceScorer()

        self.watermark_ms: float = 0.0
        self.max_observed_timestamp: float = 0.0
        self.processed_events: List[Event] = []
        self.causal_events_emitted: List[Dict[str, Any]] = []
        self.detected_anomalies: List[Dict[str, Any]] = []

        # Background thread state
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._stats = {
            "raw_events_received": 0,
            "out_of_order_events": 0,
            "causal_events_emitted": 0,
            "anomalies_detected": 0,
            "watermark_advancements": 0,
        }

    def process_event(self, event: Event) -> List[Dict[str, Any]]:
        """Process a single event through the Flink pipeline.
        
        Applies event-time watermarking, buffer reordering, causal DAG updates,
        anomaly detection, and confidence scoring.
        """
        self._stats["raw_events_received"] += 1

        # 1. Watermark tracking (Event Time with Bounded Out-of-Orderness)
        if event.timestamp_ms > self.max_observed_timestamp:
            self.max_observed_timestamp = event.timestamp_ms
            new_watermark = self.max_observed_timestamp - self.out_of_orderness_ms
            if new_watermark > self.watermark_ms:
                self.watermark_ms = new_watermark
                self._stats["watermark_advancements"] += 1

        # Check if event arrived out-of-order relative to the watermark
        is_out_of_order = event.timestamp_ms < self.watermark_ms
        if is_out_of_order:
            self._stats["out_of_order_events"] += 1

        # 2. Add to out-of-order event buffer
        ready_events = self.buffer.add(event)
        
        # Advance watermark on buffer
        timed_out = self.buffer.advance_watermark(self.watermark_ms)
        ready_events.extend(timed_out)

        # If buffer holds the event, we also emit an incremental representation
        if not ready_events:
            ready_events = [event]

        emitted_causal_payloads = []
        for ready in ready_events:
            self.processed_events.append(ready)
            # Incremental DAG build
            self.builder.build_incremental(ready)
            dag = self.builder.get_dag()

            # 3. Anomaly detection
            event_anomalies = []
            if self.enable_anomaly_detection:
                try:
                    all_anomalies = self.anomaly_detector.detect_all(dag, self.processed_events)
                    # Filter for anomalies involving this event
                    for a in all_anomalies:
                        if a.source_event_id == ready.event_id or a.target_event_id == ready.event_id:
                            a_dict = {
                                "anomaly_type": a.anomaly_type,
                                "severity": a.severity,
                                "source_event_id": a.source_event_id,
                                "target_event_id": a.target_event_id,
                                "description": a.description,
                                "details": a.details,
                            }
                            event_anomalies.append(a_dict)
                            self.detected_anomalies.append(a_dict)
                            self._stats["anomalies_detected"] += 1
                except Exception as exc:
                    logger.debug(f"Anomaly detection non-critical failure: {exc}")

            # 4. Confidence scoring for parent edges
            scored_parents = []
            if self.enable_confidence_scoring and ready.parent_event_ids:
                for pid in ready.parent_event_ids:
                    p_event = next((e for e in self.processed_events if e.event_id == pid), None)
                    if p_event:
                        edge_conf = self.confidence_scorer.score_edge(
                            source_event=p_event.to_dict(),
                            target_event=ready.to_dict(),
                            has_explicit_link=True,
                        )
                        scored_parents.append({
                            "parent_id": pid,
                            "confidence": edge_conf.confidence,
                            "method": edge_conf.method,
                        })
                    else:
                        scored_parents.append({"parent_id": pid, "confidence": 0.9, "method": "explicit"})

            # 5. Build enriched causal event payload
            causal_payload = {
                "event_id": ready.event_id,
                "trace_id": ready.trace_id,
                "service_id": ready.service_id,
                "event_type": ready.event_type,
                "timestamp_ms": ready.timestamp_ms,
                "arrival_time_ms": ready.arrival_time_ms,
                "watermark_ms": self.watermark_ms,
                "lamport_ts": ready.lamport_ts,
                "vector_clock": ready.vector_clock,
                "hlc_ts": ready.hlc_ts,
                "parent_event_ids": ready.parent_event_ids,
                "scored_parents": scored_parents,
                "is_out_of_order": is_out_of_order,
                "anomalies": event_anomalies,
                "payload": ready.payload,
                "metadata": ready.metadata.to_dict() if hasattr(ready.metadata, "to_dict") else dict(ready.metadata),
                "dag_node_count": dag.number_of_nodes(),
                "dag_edge_count": dag.number_of_edges(),
            }

            self.causal_events_emitted.append(causal_payload)
            self._stats["causal_events_emitted"] += 1
            emitted_causal_payloads.append(causal_payload)

            if self.on_causal_event:
                try:
                    self.on_causal_event(causal_payload)
                except Exception as e:
                    logger.error(f"Error in on_causal_event callback: {e}")

        return emitted_causal_payloads

    def process_stream(self, events: List[Event]) -> Dict[str, Any]:
        """Process a sequence of raw events through the pipeline."""
        results = []
        for ev in events:
            emitted = self.process_event(ev)
            results.extend(emitted)

        # Flush remaining buffer at end of stream
        flushed = self.buffer.flush()
        for ev in flushed:
            if ev.event_id not in [p["event_id"] for p in results]:
                emitted = self.process_event(ev)
                results.extend(emitted)

        return {
            "processed_count": len(events),
            "causal_events": results,
            "dag_nodes": self.builder.get_dag().number_of_nodes(),
            "dag_edges": self.builder.get_dag().number_of_edges(),
            "anomalies": self.detected_anomalies,
            "stats": self.get_statistics(),
        }

    def start_background_loop(self, consumer, producer, raw_topic="events.raw", causal_topic="events.causal"):
        """Run continuous stream processing in a daemon thread."""
        if self._running:
            return

        def _worker():
            self._running = True
            logger.info("FlinkStreamingPipeline background worker started.")
            while self._running:
                try:
                    event = consumer.consume(timeout=0.2)
                    if event:
                        emitted = self.process_event(event)
                        for item in emitted:
                            # Re-encode to Event or publish JSON dict
                            producer.publish_event(event, topic=causal_topic)
                except Exception as e:
                    logger.error(f"Pipeline worker loop error: {e}")
                    time.sleep(0.5)

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def stop_background_loop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def get_statistics(self) -> Dict[str, Any]:
        return dict(self._stats)

    def reset(self) -> None:
        self.buffer = EventBuffer(self.buffer_policy)
        self.builder = CausalDAGBuilder()
        self.watermark_ms = 0.0
        self.max_observed_timestamp = 0.0
        self.processed_events.clear()
        self.causal_events_emitted.clear()
        self.detected_anomalies.clear()
        for k in self._stats:
            self._stats[k] = 0
