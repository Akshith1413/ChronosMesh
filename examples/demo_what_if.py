#!/usr/bin/env python3
"""
ChronosMesh Demo: What-If Causal Replay

Demonstrates simulating event removal and computing the blast radius —
which downstream events would be invalidated if a specific event
had never occurred.
"""
import networkx as nx
from chronosmesh.events.event import Event
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.analysis.what_if import WhatIfSimulator


def main():
    print("=" * 60)
    print("  ChronosMesh Demo: What-If Causal Replay")
    print("=" * 60)

    # Build the Order → Payment → Inventory → Shipping DAG
    events = [
        Event(event_id="E1", service_id="order-svc", event_type="OrderCreated",
              vector_clock={"order": 1}),
        Event(event_id="E2", service_id="payment-svc", event_type="PaymentStarted",
              vector_clock={"order": 1, "payment": 1}),
        Event(event_id="E3", service_id="inventory-svc", event_type="InventoryCheck",
              vector_clock={"order": 1, "inventory": 1}),
        Event(event_id="E4", service_id="payment-svc", event_type="PaymentSuccess",
              vector_clock={"order": 1, "payment": 2}),
        Event(event_id="E5", service_id="inventory-svc", event_type="InventoryReserved",
              vector_clock={"order": 1, "inventory": 2}),
        Event(event_id="E6", service_id="shipping-svc", event_type="ShippingStarted",
              vector_clock={"order": 1, "payment": 2, "inventory": 2, "shipping": 1}),
    ]

    builder = CausalDAGBuilder()
    builder.build(events)
    dag = builder.get_dag()

    print(f"\n📊 DAG built: {len(dag.nodes)} nodes, {len(dag.edges())} edges")
    print("\nCausal structure:")
    for u, v in sorted(dag.edges()):
        print(f"  {u} → {v}")

    # --- What-If: Remove E1 (OrderCreated) — the root ---
    simulator = WhatIfSimulator()

    print("\n" + "=" * 60)
    print("🔬 What-If Scenario 1: Remove E1 (OrderCreated)")
    print("-" * 45)
    result1 = simulator.simulate_removal(dag, "E1")
    print(f"  Invalidated events: {sorted(result1.invalidated_events)}")
    print(f"  Surviving events:   {sorted(result1.surviving_events)}")
    print(f"  Blast radius:       {result1.blast_radius:.1%}")
    print(f"  Affected services:  {sorted(result1.affected_services)}")
    print(f"  Cascade depth:      {result1.cascade_depth}")

    # --- What-If: Remove E3 (InventoryCheck) ---
    print("\n🔬 What-If Scenario 2: Remove E3 (InventoryCheck)")
    print("-" * 45)
    result2 = simulator.simulate_removal(dag, "E3")
    print(f"  Invalidated events: {sorted(result2.invalidated_events)}")
    print(f"  Surviving events:   {sorted(result2.surviving_events)}")
    print(f"  Blast radius:       {result2.blast_radius:.1%}")
    print(f"  Affected services:  {sorted(result2.affected_services)}")
    print(f"  Cascade depth:      {result2.cascade_depth}")

    # --- What-If: Remove E6 (ShippingStarted) — a leaf ---
    print("\n🔬 What-If Scenario 3: Remove E6 (ShippingStarted)")
    print("-" * 45)
    result3 = simulator.simulate_removal(dag, "E6")
    print(f"  Invalidated events: {sorted(result3.invalidated_events)}")
    print(f"  Surviving events:   {sorted(result3.surviving_events)}")
    print(f"  Blast radius:       {result3.blast_radius:.1%}")
    print(f"  Cascade depth:      {result3.cascade_depth}")

    # Compare scenarios
    print("\n📈 Scenario Comparison:")
    print("-" * 45)
    results = simulator.compare_scenarios(dag, ["E1", "E3", "E6"])
    for r in results:
        print(f"  Remove {r.removed_event_id}: blast_radius={r.blast_radius:.1%}, "
              f"cascade_depth={r.cascade_depth}, invalidated={len(r.invalidated_events)}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
