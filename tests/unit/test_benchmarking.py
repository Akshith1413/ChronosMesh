import pytest
import networkx as nx
from chronosmesh.analysis.benchmarking import ClockBenchmark

def test_benchmark_all_strategies():
    bench = ClockBenchmark()
    dag = nx.DiGraph()
    dag.add_edge("1", "2")
    res = bench.benchmark(dag, [{}, {}])
    assert len(res) == 3

def test_vector_clock_highest_accuracy():
    bench = ClockBenchmark()
    dag = nx.DiGraph()
    dag.add_edge("1", "2")
    res = bench.benchmark(dag, [{}, {}])
    accs = {r.strategy_name: r.reconstruction_accuracy for r in res}
    assert accs["vector_clock"] == 1.0

def test_packet_loss_reduces_accuracy():
    bench = ClockBenchmark()
    dag = nx.DiGraph()
    for i in range(10):
        dag.add_edge(str(i), str(i+1))
    res1 = bench.benchmark(dag, [], packet_loss_pct=0.0)
    res2 = bench.benchmark(dag, [], packet_loss_pct=0.5)
    acc1 = {r.strategy_name: r.reconstruction_accuracy for r in res1}
    acc2 = {r.strategy_name: r.reconstruction_accuracy for r in res2}
    assert acc2["vector_clock"] < acc1["vector_clock"]

def test_benchmark_result_fields():
    bench = ClockBenchmark()
    dag = nx.DiGraph()
    dag.add_edge("1", "2")
    res = bench.benchmark(dag, [{}, {}])[0]
    assert hasattr(res, "memory_bytes")
    assert hasattr(res, "computation_time_ms")
    assert hasattr(res, "false_positives")

def test_compare_strategies():
    bench = ClockBenchmark()
    dag = nx.DiGraph()
    dag.add_edge("1", "2")
    res = bench.benchmark(dag, [{}, {}])
    comp = bench.compare_strategies(res)
    assert "vector_clock" in comp
    assert "lamport_clock" in comp
