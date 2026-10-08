"""
ChronosMesh Load & Performance Benchmark Suite.

Simulates high-volume distributed event streams across 5 microservices,
measuring:
- Events generated, accepted, processed, and persisted
- Processing latency (p50, p95, p99)
- Effective throughput (events/second)
- Memory footprint before and after
- Dropped/duplicate event counts
"""

import os
import sys
import time
import tracemalloc
from typing import Any, Dict, List

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.stream.flink_pipeline import FlinkStreamingPipeline
from chronosmesh.storage.neo4j_store import Neo4jStore
from chronosmesh.services.mock_services import MockDistributedCluster


def generate_load_stream(total_events: int = 1000) -> List[Event]:
    """Generate high-concurrency event stream simulating e-commerce order workflows."""
    cluster = MockDistributedCluster(
        simulate_network_delay=True,
        simulate_clock_skew=True,
        simulate_out_of_order=True,
    )
    events = []
    traces_count = max(1, total_events // 6)
    for t in range(traces_count):
        trace_events = cluster.generate_ecommerce_trace(trace_id=f"T-LOAD-{t:04d}")
        events.extend(trace_events)
        if len(events) >= total_events:
            break
    return events[:total_events]


def run_load_test(target_events: int = 600) -> Dict[str, Any]:
    """Execute end-to-end performance load test."""
    print(f"=== Starting ChronosMesh Load Test: {target_events} events ===")
    
    tracemalloc.start()
    mem_before = tracemalloc.get_traced_memory()[0]

    # 1. Ingestion / Generation Phase
    t_gen_start = time.perf_counter()
    raw_events = generate_load_stream(target_events)
    t_gen_elapsed = time.perf_counter() - t_gen_start
    gen_rate = len(raw_events) / t_gen_elapsed if t_gen_elapsed > 0 else 0

    # 2. Flink Streaming Pipeline Processing
    pipeline = FlinkStreamingPipeline(
        out_of_orderness_ms=500.0,
        enable_anomaly_detection=False,
    )
    latencies_ms = []
    t_proc_start = time.perf_counter()
    processed_count = 0
    errors = 0

    for ev in raw_events:
        t0 = time.perf_counter()
        try:
            emitted = pipeline.process_event(ev)
            if emitted:
                processed_count += 1
        except Exception:
            errors += 1
        dt = (time.perf_counter() - t0) * 1000
        latencies_ms.append(dt)

    t_proc_elapsed = time.perf_counter() - t_proc_start
    proc_throughput = processed_count / t_proc_elapsed if t_proc_elapsed > 0 else 0

    # 3. Persistence Throughput (Neo4j / In-memory Mirror)
    store = Neo4jStore()
    t_store_start = time.perf_counter()
    persisted_count = 0
    for ev in raw_events:
        if store.save_event(ev):
            persisted_count += 1
    t_store_elapsed = time.perf_counter() - t_store_start
    store_throughput = persisted_count / t_store_elapsed if t_store_elapsed > 0 else 0

    mem_after, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(len(latencies_sorted) * 0.50)]
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]

    stats = pipeline.get_statistics()

    summary = {
        "events_generated": len(raw_events),
        "events_processed": processed_count,
        "events_persisted": persisted_count,
        "generation_rate_ev_sec": round(gen_rate, 1),
        "processing_throughput_ev_sec": round(proc_throughput, 1),
        "persistence_throughput_ev_sec": round(store_throughput, 1),
        "latency_p50_ms": round(p50, 3),
        "latency_p95_ms": round(p95, 3),
        "latency_p99_ms": round(p99, 3),
        "out_of_order_events": stats.get("out_of_order_events", 0),
        "errors": errors,
        "dropped_events": len(raw_events) - processed_count,
        "memory_growth_mb": round((mem_after - mem_before) / (1024 * 1024), 2),
        "peak_memory_mb": round(mem_peak / (1024 * 1024), 2),
    }

    print("\n--- Load Test Results ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("-------------------------\n")
    return summary


if __name__ == "__main__":
    run_load_test(600)
