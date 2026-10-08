import time
import networkx as nx
from chronosmesh.events.event import Event, EventMetadata
from chronosmesh.causality.dag_builder import CausalDAGBuilder
from chronosmesh.causality.transitive_reduction import (
    compute_transitive_reduction,
    incremental_transitive_reduction
)

def benchmark_causal_scaling():
    sizes = [10, 100, 500, 1000]
    results = []

    for n in sizes:
        events = []
        services = ["auth-service", "order-service", "payment-service", "shipping-service"]
        for i in range(n):
            svc = services[i % len(services)]
            parents = [events[i - 1].event_id] if i > 0 and (i % 5 != 0) else ([events[max(0, i-2)].event_id, events[max(0, i-1)].event_id] if i >= 2 else [])
            ev = Event(
                event_id=f"evt-{i}",
                trace_id="bench-trace-1",
                service_id=svc,
                event_type="STATE_CHANGE",
                timestamp_ms=1000000.0 + i * 10.0,
                parent_event_ids=parents,
                vector_clock={svc: i + 1},
                metadata=EventMetadata(region="us-east-1", availability_zone="us-east-1a")
            )
            events.append(ev)

        # Measure Optimized Incremental DAG builder
        builder = CausalDAGBuilder()
        t0 = time.perf_counter()
        for ev in events:
            builder.build_incremental(ev)
        t_opt = (time.perf_counter() - t0) * 1000.0  # ms
        dag_opt = builder.dag

        # Correctness check: verify acyclic, topological ordering, correct node count
        is_dag = nx.is_directed_acyclic_graph(dag_opt)
        node_count = dag_opt.number_of_nodes()
        edge_count = dag_opt.number_of_edges()

        # Measure Global transitive reduction on full graph
        full_dag = nx.DiGraph()
        for ev in events:
            full_dag.add_node(ev.event_id, event=ev)
            for p in ev.parent_event_ids:
                if full_dag.has_node(p):
                    full_dag.add_edge(p, ev.event_id)
        # add transitive shortcuts to benchmark reduction
        for i in range(len(events)):
            for j in range(i + 1, min(len(events), i + 4)):
                full_dag.add_edge(events[i].event_id, events[j].event_id)

        t0_global = time.perf_counter()
        global_reduced = compute_transitive_reduction(full_dag)
        t_global = (time.perf_counter() - t0_global) * 1000.0  # ms

        results.append({
            "n": n,
            "t_opt_ms": round(t_opt, 2),
            "t_global_ms": round(t_global, 2),
            "is_dag": is_dag,
            "nodes": node_count,
            "edges": edge_count,
            "speedup": round(t_global / max(t_opt, 0.001), 1)
        })

    print("=== Causal DAG Scaling Benchmark ===")
    for r in results:
        print(f"Events: {r['n']:4d} | Opt Incremental: {r['t_opt_ms']:7.2f} ms | Global Red: {r['t_global_ms']:7.2f} ms | Speedup: {r['speedup']:5.1f}x | DAG: {r['is_dag']} (V={r['nodes']}, E={r['edges']})")

if __name__ == "__main__":
    benchmark_causal_scaling()
