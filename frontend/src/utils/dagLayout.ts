/**
 * ChronosMesh — shared DAG indexing used by both the 2D (D3) and 3D (canvas) graph views.
 */
import { DAGData, DAGNode, DAGEdge } from '../types';

export interface DagIndex {
  nodes: DAGNode[];
  edges: DAGEdge[];
  byId: Record<string, DAGNode>;
  depth: Record<string, number>;
  maxDepth: number;
  services: string[];
  parents: Record<string, string[]>;
  children: Record<string, string[]>;
}

/** Kahn-style longest-path depth, plus adjacency maps. */
export function indexDag(dag: DAGData): DagIndex {
  const nodes = dag.nodes;
  const edges = dag.edges;
  const byId: Record<string, DAGNode> = {};
  const inDeg: Record<string, number> = {};
  const parents: Record<string, string[]> = {};
  const children: Record<string, string[]> = {};
  nodes.forEach((n) => {
    byId[n.id] = n;
    inDeg[n.id] = 0;
    parents[n.id] = [];
    children[n.id] = [];
  });
  edges.forEach((e) => {
    if (!(e.source in byId) || !(e.target in byId)) return;
    inDeg[e.target] += 1;
    children[e.source].push(e.target);
    parents[e.target].push(e.source);
  });

  const depth: Record<string, number> = {};
  const queue = nodes.filter((n) => inDeg[n.id] === 0).map((n) => n.id);
  queue.forEach((id) => (depth[id] = 0));
  const work = { ...inDeg };
  while (queue.length) {
    const cur = queue.shift()!;
    for (const nxt of children[cur]) {
      depth[nxt] = Math.max(depth[nxt] || 0, (depth[cur] || 0) + 1);
      work[nxt] -= 1;
      if (work[nxt] === 0) queue.push(nxt);
    }
  }
  nodes.forEach((n) => {
    if (depth[n.id] === undefined) depth[n.id] = 0; // cycle members fall back to the top row
  });

  return {
    nodes,
    edges,
    byId,
    depth,
    maxDepth: Math.max(0, ...Object.values(depth)),
    services: Array.from(new Set(nodes.map((n) => n.service_id))),
    parents,
    children,
  };
}

function walk(start: string, next: Record<string, string[]>): Set<string> {
  const seen = new Set<string>();
  const stack = [start];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const n of next[cur] || []) {
      if (!seen.has(n)) {
        seen.add(n);
        stack.push(n);
      }
    }
  }
  return seen;
}

/** Everything causally upstream and downstream of a node, plus the node itself. */
export function lineage(idx: DagIndex, id: string): Set<string> {
  const out = walk(id, idx.parents);
  walk(id, idx.children).forEach((n) => out.add(n));
  out.add(id);
  return out;
}

export function abbreviate(eventType: string): string {
  const parts = eventType.split('_');
  if (parts.length === 1) return eventType.slice(0, 5);
  return parts.map((p) => p[0]).join('').slice(0, 4);
}
