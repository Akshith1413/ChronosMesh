import networkx as nx

def compute_transitive_reduction(dag: nx.DiGraph) -> nx.DiGraph:
    if not nx.is_directed_acyclic_graph(dag):
        raise ValueError("Graph is not a DAG, cycle detected")
    
    tr = nx.transitive_reduction(dag)
    result = nx.DiGraph()
    result.add_nodes_from(dag.nodes(data=True))
    result.add_edges_from((u, v) for u, v in tr.edges() if dag.has_edge(u, v))
    return result

def is_transitively_reduced(dag: nx.DiGraph) -> bool:
    if not nx.is_directed_acyclic_graph(dag):
        raise ValueError("Graph is not a DAG, cycle detected")
        
    tr = nx.transitive_reduction(dag)
    return set(dag.edges()) == set(tr.edges())


def incremental_transitive_reduction(dag: nx.DiGraph, new_node: str) -> nx.DiGraph:
    """
    Perform fast localized transitive reduction around a newly added node.
    Assumes the graph prior to new_node was already transitively reduced.
    Prunes:
    1. Redundant incoming edges (u -> new_node) where u is an ancestor of another predecessor v.
    2. Redundant outgoing edges (new_node -> w) where w is a descendant of another successor v.
    """
    if not dag.has_node(new_node):
        return dag

    # Check incoming edges to new_node
    in_neighbors = list(dag.predecessors(new_node))
    if len(in_neighbors) > 1:
        redundant_in = set()
        for v in in_neighbors:
            if v not in redundant_in:
                v_ancestors = nx.ancestors(dag, v)
                for u in in_neighbors:
                    if u != v and u in v_ancestors:
                        redundant_in.add(u)
        for u in redundant_in:
            dag.remove_edge(u, new_node)

    # Check outgoing edges from new_node
    out_neighbors = list(dag.successors(new_node))
    if len(out_neighbors) > 1:
        redundant_out = set()
        for v in out_neighbors:
            if v not in redundant_out:
                v_descendants = nx.descendants(dag, v)
                for w in out_neighbors:
                    if w != v and w in v_descendants:
                        redundant_out.add(w)
        for w in redundant_out:
            dag.remove_edge(new_node, w)

    return dag

