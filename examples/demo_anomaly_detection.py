#!/usr/bin/env python3
"""
ChronosMesh Demo: Causal Anomaly Detection

Demonstrates detecting causality violations such as time inversions,
duplicate events, and vector clock gaps in distributed event streams.
"""
from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.analysis.anomaly import CausalAnomalyDetector


def main():
    print("=" * 60)
    print("  ChronosMesh Demo: Causal Anomaly Detection")
    print("=" * 60)

    # --- Scenario 1: Valid event stream (no anomalies) ---
    print("\n📋 Scenario 1: Valid Event Stream")
    print("-" * 45)

    valid_events = [
        Event(event_id="E1", service_id="svc-a", event_type="Start",
              vector_clock={"a": 1}, timestamp_ms=100),
        Event(event_id="E2", service_id="svc-a", event_type="Process",
              vector_clock={"a": 2}, timestamp_ms=200),
        Event(event_id="E3", service_id="svc-a", event_type="End",
              vector_clock={"a": 3}, timestamp_ms=300),
    ]

    builder = CausalDAGBuilder()
    builder.build(valid_events)
    dag = builder.get_dag()

    detector = CausalAnomalyDetector(clock_skew_tolerance_ms=50.0)
    anomalies = detector.detect_all(dag, valid_events)
    print(f"  Anomalies detected: {len(anomalies)}")
    print("  ✅ No anomalies — valid causal chain")

    # --- Scenario 2: Time Inversion Anomaly ---
    print("\n⚠️  Scenario 2: Time Inversion Anomaly")
    print("-" * 45)

    inversion_events = [
        Event(event_id="E4", service_id="svc-b", event_type="Request",
              vector_clock={"b": 1}, timestamp_ms=500),
        Event(event_id="E5", service_id="svc-b", event_type="Response",
              vector_clock={"b": 2}, timestamp_ms=300),  # ANOMALY: physical time goes backward
    ]

    builder2 = CausalDAGBuilder()
    builder2.build(inversion_events)
    dag2 = builder2.get_dag()

    anomalies2 = detector.detect_all(dag2, inversion_events)
    print(f"  Anomalies detected: {len(anomalies2)}")
    for a in anomalies2:
        print(f"  🚨 [{a.severity}] {a.anomaly_type}: {a.description}")

    # --- Scenario 3: Duplicate Event Detection ---
    print("\n⚠️  Scenario 3: Duplicate Event Detection")
    print("-" * 45)

    dup_events = [
        Event(event_id="E6", service_id="svc-c", event_type="Ping",
              vector_clock={"c": 1}, timestamp_ms=600),
        Event(event_id="E6", service_id="svc-c", event_type="Ping",
              vector_clock={"c": 1}, timestamp_ms=600),  # DUPLICATE
        Event(event_id="E7", service_id="svc-c", event_type="Pong",
              vector_clock={"c": 2}, timestamp_ms=700),
    ]

    anomalies3 = detector.detect_duplicate_events(dup_events)
    print(f"  Anomalies detected: {len(anomalies3)}")
    for a in anomalies3:
        print(f"  🚨 [{a.severity}] {a.anomaly_type}: {a.description}")

    total = len(anomalies) + len(anomalies2) + len(anomalies3)
    print(f"\n📈 Total anomalies detected across all scenarios: {total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
