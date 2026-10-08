from dataclasses import dataclass, field
from typing import List, Tuple, Any
import networkx as nx

@dataclass
class GraphDiffResult:
    added_edges: List[Tuple[str, str]] = field(default_factory=list)
    removed_edges: List[Tuple[str, str]] = field(default_factory=list)
    added_nodes: List[str] = field(default_factory=list)
    removed_nodes: List[str] = field(default_factory=list)
    modified_nodes: List[str] = field(default_factory=list)
    structural_similarity: float = 0.0
    behavioral_drift_score: float = 0.0

class CausalGraphDiffer:
    def diff(self, dag_a: nx.DiGraph, dag_b: nx.DiGraph) -> GraphDiffResult:
        nodes_a = set(dag_a.nodes())
        nodes_b = set(dag_b.nodes())
        
        edges_a = set(dag_a.edges())
        edges_b = set(dag_b.edges())
        
        added_nodes = list(nodes_b - nodes_a)
        removed_nodes = list(nodes_a - nodes_b)
        
        added_edges = list(edges_b - edges_a)
        removed_edges = list(edges_a - edges_b)
        
        common_nodes = nodes_a.intersection(nodes_b)
        modified_nodes = []
        for n in common_nodes:
            if dag_a.nodes[n] != dag_b.nodes[n]:
                modified_nodes.append(n)
                
        # Jaccard similarity for edges
        union_edges = edges_a.union(edges_b)
        intersection_edges = edges_a.intersection(edges_b)
        sim = len(intersection_edges) / max(1, len(union_edges))
        
        drift = 1.0 - sim
        
        return GraphDiffResult(
            added_edges=added_edges,
            removed_edges=removed_edges,
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            modified_nodes=modified_nodes,
            structural_similarity=sim,
            behavioral_drift_score=drift
        )

    def is_structurally_equivalent(self, dag_a: nx.DiGraph, dag_b: nx.DiGraph) -> bool:
        diff_res = self.diff(dag_a, dag_b)
        return diff_res.structural_similarity == 1.0

    def get_change_summary(self, result: GraphDiffResult) -> str:
        return (f"Added {len(result.added_nodes)} nodes, {len(result.added_edges)} edges. "
                f"Removed {len(result.removed_nodes)} nodes, {len(result.removed_edges)} edges. "
                f"Similarity: {result.structural_similarity:.2f}")
