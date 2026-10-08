"""
ChronosMesh High-Throughput Load Testing Suite (10,000+ events/sec).

Simulates high-velocity event ingestion into the ChronosMesh streaming pipeline,
exercising out-of-order buffering, windowing, and causal DAG construction under
burst and sustained stress conditions.
"""

import argparse
import logging
import os
import sys
import time
from typing import Dict, List

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.stream.processor import StreamProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LoadTest")


def generate_synthetic_load_batch(batch_size: int, trace_id: str) -> List[Event]:
    """Generates a batch of causal synthetic events with multi-region tags."""
    events = []
    services = ["order-svc", "payment-svc", "inventory-svc", "shipping-svc", "notification-svc"]
    regions = ["aws-mumbai", "aws-singapore", "gcp-mumbai", "gcp-singapore"]

    now = time.time() * 1000.0
    for i in range(batch_size):
        svc = services[i % len(services)]
        reg = regions[i % len(regions)]
        event = Event(
            event_id=f"load-{trace_id}-{i}",
            service_id=svc,
            event_type="BATCH_METRIC_EVENT",
            timestamp_ms=now + (i * 0.1),
            lamport_ts=i + 1,
            vector_clock={svc: i + 1},
            hlc_ts={"pt": (now + i) / 1000.0, "l": i + 1},
            trace_id=trace_id,
            span_id=f"spn-{i:06d}",
            parent_event_ids=[f"load-{trace_id}-{i-1}"] if i > 0 else [],
            payload={"load_seq": i, "data": "load_stress_payload"},
            metadata=EventMetadata(region=reg, clock_uncertainty_ms=4.0),
            arrival_time_ms=now + (i * 0.1) + 2.0,
        )
        events.append(event)
    return events


def run_load_test(target_events: int = 10000, batch_size: int = 500) -> Dict[str, float]:
    """
    Executes high-throughput stream processing benchmark.
    Target: 10,000+ events processed efficiently.
    """
    processor = StreamProcessor(window_size_ms=1000, max_lateness_ms=5000)
    logger.info(f"Starting High-Throughput Load Test: {target_events} events (batch_size={batch_size})")

    start_time = time.perf_counter()
    processed_count = 0
    latencies = []

    batches = target_events // batch_size
    for b in range(batches):
        trace_id = f"stress-trace-{b}"
        batch = generate_synthetic_load_batch(batch_size, trace_id)

        b_start = time.perf_counter()
        processor.process_batch(batch)
        b_duration = time.perf_counter() - b_start

        processed_count += len(batch)
        latencies.append((b_duration / len(batch)) * 1000.0)  # ms per event

    total_time = time.perf_counter() - start_time
    throughput = processed_count / total_time if total_time > 0 else 0

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    logger.info("================ LOAD TEST RESULTS ================")
    logger.info(f"Total Events Processed : {processed_count:,}")
    logger.info(f"Total Duration         : {total_time:.3f} seconds")
    logger.info(f"Ingestion Throughput   : {throughput:,.1f} events/sec")
    logger.info(f"Event Latency p50      : {p50:.3f} ms")
    logger.info(f"Event Latency p95      : {p95:.3f} ms")
    logger.info(f"Event Latency p99      : {p99:.3f} ms")
    logger.info("===================================================")

    return {
        "total_events": processed_count,
        "duration_seconds": total_time,
        "throughput_eps": throughput,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChronosMesh 10k+ Load Tester")
    parser.add_argument("--events", type=int, default=10000, help="Total events to process")
    parser.add_argument("--batch", type=int, default=500, help="Batch size")
    args = parser.parse_args()

    run_load_test(target_events=args.events, batch_size=args.batch)
