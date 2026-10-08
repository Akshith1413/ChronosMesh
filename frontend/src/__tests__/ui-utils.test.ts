import { describe, it, expect } from 'vitest';
import { indexDag, lineage, abbreviate } from '../utils/dagLayout';
import { project, easeOutExpo, easeInOut, mulberry32, fog, rgba, Cam } from '../fx/engine3d';
import type { DAGData, DAGNode } from '../types';

const node = (id: string, svc = 'order-svc'): DAGNode => ({
  id,
  service_id: svc,
  event_type: id.toUpperCase(),
  timestamp_ms: 0,
  lamport_ts: 1,
  vector_clock: {},
  parent_event_ids: [],
});

// root -> a, root -> b, a -> join, b -> join   (the "diamond" pattern)
const diamond: DAGData = {
  nodes: [node('root'), node('a', 'payment-svc'), node('b', 'inventory-svc'), node('join', 'shipping-svc')],
  edges: [
    { source: 'root', target: 'a', explicit: false },
    { source: 'root', target: 'b', explicit: false },
    { source: 'a', target: 'join', explicit: false },
    { source: 'b', target: 'join', explicit: false },
  ],
  topological_order: ['root', 'a', 'b', 'join'],
  roots: ['root'],
  leaves: ['join'],
};

describe('DAG indexing (shared by the 2D and 3D graph views)', () => {
  it('computes longest-path depth and adjacency', () => {
    const idx = indexDag(diamond);
    expect(idx.depth).toEqual({ root: 0, a: 1, b: 1, join: 2 });
    expect(idx.maxDepth).toBe(2);
    expect(idx.parents.join.sort()).toEqual(['a', 'b']);
    expect(idx.children.root.sort()).toEqual(['a', 'b']);
    expect(idx.services).toEqual(['order-svc', 'payment-svc', 'inventory-svc', 'shipping-svc']);
  });

  it('isolates a branch lineage and excludes its concurrent sibling', () => {
    const idx = indexDag(diamond);
    const lin = lineage(idx, 'a');
    expect([...lin].sort()).toEqual(['a', 'join', 'root']);
    expect(lin.has('b')).toBe(false); // b is concurrent with a — neither cause nor effect
  });

  it('survives edges that reference unknown nodes and cyclic input', () => {
    const cyclic: DAGData = {
      ...diamond,
      edges: [...diamond.edges, { source: 'join', target: 'root', explicit: false }, { source: 'ghost', target: 'a', explicit: false }],
    };
    expect(() => indexDag(cyclic)).not.toThrow();
    const idx = indexDag(cyclic);
    Object.values(idx.depth).forEach((d) => expect(Number.isFinite(d)).toBe(true));
  });

  it('abbreviates event types for node glyphs', () => {
    expect(abbreviate('PAYMENT_COMPLETED')).toBe('PC');
    expect(abbreviate('ORDER_CREATED')).toBe('OC');
    expect(abbreviate('SHIP')).toBe('SHIP');
  });
});

describe('3D engine math', () => {
  const cam: Cam = { yaw: 0, pitch: 0, dist: 10, focal: 500, cx: 400, cy: 300 };

  it('projects the origin to the screen centre and shrinks with distance', () => {
    const o = project([0, 0, 0], cam);
    expect(o.x).toBeCloseTo(400);
    expect(o.y).toBeCloseTo(300);
    const near = project([0, 0, -4], cam);
    const far = project([0, 0, 6], cam);
    expect(near.s).toBeGreaterThan(o.s);
    expect(far.s).toBeLessThan(o.s);
  });

  it('flags points behind the camera as not visible', () => {
    expect(project([0, 0, -20], cam).vis).toBe(false);
  });

  it('clamps easing so intro animations can never produce a negative radius', () => {
    // Regression: the first rAF timestamp can precede performance.now(), making dt (and progress) negative.
    expect(easeOutExpo(-0.3)).toBe(0);
    expect(easeOutExpo(0)).toBe(0);
    expect(easeOutExpo(1.4)).toBe(1);
    expect(easeInOut(-1)).toBe(0);
    expect(easeInOut(2)).toBe(1);
  });

  it('is deterministic for a given seed', () => {
    const a = mulberry32(11), b = mulberry32(11), c = mulberry32(12);
    const seqA = [a(), a(), a()], seqB = [b(), b(), b()];
    expect(seqA).toEqual(seqB);
    expect(c()).not.toBe(seqA[0]);
    seqA.forEach((v) => {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    });
  });

  it('fogs distant geometry and parses hex colours', () => {
    expect(fog(10, 12)).toBeGreaterThan(fog(30, 12));
    expect(rgba('#4c6ef5', 0.5)).toBe('rgba(76,110,245,0.500)');
  });
});
