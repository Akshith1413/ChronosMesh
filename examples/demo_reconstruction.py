#!/usr/bin/env python3
"""
ChronosMesh Demo: Causal DAG Reconstruction

Demonstrates reconstructing the actual causal timeline from scrambled
out-of-order events using vector clocks and DAG construction.
"""
import random
from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder
import networkx as nx


def main():
    print("=" * 60)
    print("  ChronosMesh Demo: Causal DAG Reconstruction")
    print("=" * 60)

    # Create events with proper vector clocks representing the
    # Order → Payment → Inventory → Shipping scenario
    e1 = Event(event_id="E1", service_id="order-svc", event_type="OrderCreated",
               vector_clock={"order": 1}, timestamp_ms=1000)
    e2 = Event(event_id="E2", service_id="payment-svc", event_type="PaymentStarted",
               vector_clock={"order": 1, "payment": 1}, timestamp_ms=2000)
    e3 = Event(event_id="E3", service_id="inventory-svc", event_type="InventoryCheck",
               vector_clock={"order": 1, "inventory": 1}, timestamp_ms=2100)
    e4 = Event(event_id="E4", service_id="payment-svc", event_type="PaymentSuccess",
               vector_clock={"order": 1, "payment": 2}, timestamp_ms=3000)
    e5 = Event(event_id="E5", service_id="inventory-svc", event_type="InventoryReserved",
               vector_clock={"order": 1, "inventory": 2}, timestamp_ms=3200)
    e6 = Event(event_id="E6", service_id="shipping-svc", event_type="ShippingStarted",
               vector_clock={"order": 1, "payment": 2, "inventory": 2, "shipping": 1},
               timestamp_ms=4000)

    events = [e1, e2, e3, e4, e5, e6]

    # Simulate out-of-order arrival (network disorder)
    random.seed(42)
    scrambled = list(events)
    random.shuffle(scrambled)

    print("\n📡 Scrambled Arrival Order (as received by cloud):")
    print("-" * 45)
    for i, e in enumerate(scrambled, 1):
        print(f"  {i}. {e.event_id}: {e.event_type} (service: {e.service_id})")

    # Reconstruct the causal DAG
    print("\n🔄 Reconstructing Causal DAG using Vector Clocks...")
    builder = CausalDAGBuilder()
    builder.build(scrambled)
    dag = builder.get_dag()

    # Show reconstructed edges
    print("\n📊 Reconstructed Causal Edges (happens-before):")
    print("-" * 45)
    for u, v in sorted(dag.edges()):
        u_type = dag.nodes[u].get("event_type", u)
        v_type = dag.nodes[v].get("event_type", v)
        print(f"  {u} ({u_type}) → {v} ({v_type})")

    # Detect concurrent events
    print("\n⚡ Concurrent Event Pairs (causally independent):")
    print("-" * 45)
    event_ids = [e.event_id for e in events]
    for i in range(len(event_ids)):
        for j in range(i + 1, len(event_ids)):
            a, b = event_ids[i], event_ids[j]
            if a in dag and b in dag:
                if not nx.has_path(dag, a, b) and not nx.has_path(dag, b, a):
                    a_type = dag.nodes[a].get("event_type", a)
                    b_type = dag.nodes[b].get("event_type", b)
                    print(f"  {a} ({a_type}) ∥ {b} ({b_type})")

    # Show topological order
    print("\n✅ Reconstructed Causal Order (topological sort):")
    print("-" * 45)
    order = list(nx.topological_sort(dag))
    for i, eid in enumerate(order, 1):
        etype = dag.nodes[eid].get("event_type", eid)
        print(f"  {i}. {eid}: {etype}")

    print(f"\n📈 DAG Statistics: {len(dag.nodes)} nodes, {len(dag.edges())} edges")
    print("=" * 60)


if __name__ == "__main__":
    main()
