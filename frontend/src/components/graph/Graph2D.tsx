import React, { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import * as d3 from 'd3';
import { DAGNode, DAGEdge } from '../../types';
import { GraphHandle, GraphViewProps } from './types';
import { getServiceColor, getServiceLabel, PALETTE } from '../../utils/colors';
import { indexDag, lineage, abbreviate } from '../../utils/dagLayout';
import { shade } from '../../fx/engine3d';

const NODE_R = 24;
const COL_W = 210;
const ROW_H = 118;
const PAD = 84;

interface Scene {
  apply: () => void;
  hover: () => void;
}

/** Edge geometry: time flows downward, so edges leave a node's bottom and enter the next node's top. */
function edgePath(sx: number, sy: number, tx: number, ty: number) {
  if (Math.abs(ty - sy) < 6) {
    const dir = tx >= sx ? 1 : -1;
    const x1 = sx + dir * (NODE_R + 3), y1 = sy;
    const x2 = tx - dir * (NODE_R + 10), y2 = ty;
    const my = sy - 46;
    return { d: `M${x1},${y1} C${(x1 + x2) / 2},${my} ${(x1 + x2) / 2},${my} ${x2},${y2}`, x2, y2, ang: dir > 0 ? 25 : 155 };
  }
  const down = ty > sy;
  const k = down ? 1 : -1;
  const x1 = sx, y1 = sy + k * (NODE_R + 3);
  const x2 = tx, y2 = ty - k * (NODE_R + 10);
  const my = (y1 + y2) / 2;
  return { d: `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`, x2, y2, ang: down ? 90 : -90 };
}

const colorKey = (c: string) => c.replace('#', '');

export const Graph2D = forwardRef<GraphHandle, GraphViewProps>((props, ref) => {
  const hostRef = useRef<HTMLDivElement>(null);
  const latest = useRef(props);
  latest.current = props;
  const scene = useRef<Scene | null>(null);
  const hoverId = useRef<string | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const initialRef = useRef<d3.ZoomTransform | null>(null);
  const currentRef = useRef<d3.ZoomTransform | null>(null);

  useImperativeHandle(ref, () => ({
    zoomIn: () => svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().duration(280).call(zoomRef.current.scaleBy, 1.3),
    zoomOut: () => svgRef.current && zoomRef.current && d3.select(svgRef.current).transition().duration(280).call(zoomRef.current.scaleBy, 0.75),
    reset: () => svgRef.current && zoomRef.current && initialRef.current && d3.select(svgRef.current).transition().duration(600).ease(d3.easeCubicInOut).call(zoomRef.current.transform, initialRef.current),
  }));

  // ───────────────────────── Build the scene whenever the DAG changes ─────────────────────────
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    host.innerHTML = '';
    const idx = indexDag(props.dagData);
    const { nodes, edges, depth, services, maxDepth } = idx;
    if (!nodes.length) return;

    const w = host.clientWidth || 900;
    const h = host.clientHeight || 600;

    // Positions: one column per service, one row per causal depth
    const colOf: Record<string, number> = {};
    services.forEach((s, i) => (colOf[s] = i));
    const bucket: Record<string, number> = {};
    const pos: Record<string, { x: number; y: number }> = {};
    nodes.forEach((n) => {
      const col = colOf[n.service_id] ?? 0;
      const row = depth[n.id] ?? 0;
      const key = `${col}_${row}`;
      const slot = bucket[key] || 0;
      bucket[key] = slot + 1;
      pos[n.id] = { x: PAD + col * COL_W + slot * 40, y: PAD + 20 + row * ROW_H };
    });

    const svg = d3.select(host).append('svg').attr('class', 'g2d').attr('width', '100%').attr('height', '100%');
    svgRef.current = svg.node();
    const defs = svg.append('defs');

    // Pearl gradients, one per service hue (plus crimson for invalidated events)
    const hues = Array.from(new Set([...services.map(getServiceColor), PALETTE.crit, '#ff8a3d']));
    hues.forEach((c) => {
      const g = defs.append('radialGradient').attr('id', `pg-${colorKey(c)}`).attr('cx', '34%').attr('cy', '28%').attr('r', '78%');
      g.append('stop').attr('offset', '0%').attr('stop-color', shade(c, 0.78));
      g.append('stop').attr('offset', '38%').attr('stop-color', shade(c, 0.12));
      g.append('stop').attr('offset', '78%').attr('stop-color', c);
      g.append('stop').attr('offset', '100%').attr('stop-color', shade(c, -0.26));
    });
    services.forEach((s) => {
      const c = getServiceColor(s);
      const lg = defs.append('linearGradient').attr('id', `lane-${colorKey(c)}`).attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
      lg.append('stop').attr('offset', '0%').attr('stop-color', c).attr('stop-opacity', 0.14);
      lg.append('stop').attr('offset', '100%').attr('stop-color', c).attr('stop-opacity', 0.02);
    });

    const g = svg.append('g').attr('class', 'main-group');

    // ── Swimlanes
    const laneH = maxDepth * ROW_H + 150;
    const lanes = g.append('g').attr('class', 'lanes');
    services.forEach((s, i) => {
      const c = getServiceColor(s);
      const lx = PAD + i * COL_W - COL_W / 2 + 8;
      const ly = PAD - 64;
      lanes.append('rect').attr('class', 'lane').attr('x', lx).attr('y', ly).attr('width', COL_W - 16).attr('height', laneH).attr('rx', 28)
        .attr('fill', `url(#lane-${colorKey(c)})`).attr('stroke', c).attr('stroke-opacity', 0.2)
        .style('animation-delay', `${i * 90}ms`);
      lanes.append('circle').attr('cx', lx + 26).attr('cy', ly + 24).attr('r', 5).attr('fill', c);
      lanes.append('text').attr('class', 'lane-label').attr('x', lx + 38).attr('y', ly + 28).attr('fill', c).text(getServiceLabel(s));
    });

    // ── Edges
    const edgeData = edges.filter((e) => pos[e.source] && pos[e.target]);
    const edgeLayer = g.append('g').attr('class', 'edges');
    const edgeSel = edgeLayer
      .selectAll<SVGGElement, DAGEdge>('g.edge-g')
      .data(edgeData)
      .enter()
      .append('g')
      .attr('class', (e) => `edge-g ${e.explicit ? 'explicit' : 'inferred'}`)
      .style('--d', (e) => `${(depth[e.source] ?? 0) * 0.16 + 0.35}s`);

    edgeSel.each(function (e, i) {
      const el = d3.select(this);
      const s = pos[e.source], t = pos[e.target];
      const geo = edgePath(s.x, s.y, t.x, t.y);
      const ca = getServiceColor(idx.byId[e.source]?.service_id);
      const cb = getServiceColor(idx.byId[e.target]?.service_id);
      const gid = `eg-${i}`;
      const lg = defs.append('linearGradient').attr('id', gid).attr('gradientUnits', 'userSpaceOnUse').attr('x1', s.x).attr('y1', s.y).attr('x2', t.x).attr('y2', t.y === s.y ? t.y + 0.01 : t.y);
      lg.append('stop').attr('offset', '0%').attr('stop-color', ca);
      lg.append('stop').attr('offset', '100%').attr('stop-color', cb);
      el.append('path').attr('class', 'edge').attr('d', geo.d).attr('stroke', `url(#${gid})`);
      el.append('path').attr('class', 'edge-flow').attr('d', geo.d);
      el.append('path').attr('class', 'arrow').attr('d', 'M0,0 L-10,-5.5 L-10,5.5 Z').attr('fill', cb)
        .attr('transform', `translate(${geo.x2},${geo.y2}) rotate(${geo.ang})`);
      el.append('path').attr('class', 'edge-hit').attr('d', geo.d);
    });
    if (props.onSelectEdge) edgeSel.on('click', (_, e) => latest.current.onSelectEdge?.(e));

    // ── Nodes
    const nodeLayer = g.append('g').attr('class', 'nodes');
    const nodeSel = nodeLayer
      .selectAll<SVGGElement, (typeof nodes)[number]>('g.node-item')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node-item')
      .attr('transform', (d) => `translate(${pos[d.id].x},${pos[d.id].y})`)
      .style('--d', (d) => `${(depth[d.id] ?? 0) * 0.14}s`);

    const body = nodeSel.append('g').attr('class', 'node-body');
    body.append('circle').attr('class', 'shock').attr('r', NODE_R + 4);
    body.append('circle').attr('class', 'halo').attr('r', NODE_R + 12).attr('fill', (d) => getServiceColor(d.service_id));
    body.append('circle').attr('class', 'ring').attr('r', NODE_R + 6);
    body.append('circle').attr('class', 'pearl').attr('r', NODE_R).attr('fill', (d) => `url(#pg-${colorKey(getServiceColor(d.service_id))})`);
    body.append('ellipse').attr('class', 'spec').attr('cx', -7).attr('cy', -9).attr('rx', 8).attr('ry', 4.6).attr('transform', 'rotate(-35 -7 -9)');
    body.append('text').attr('class', 'abbr').attr('dy', '0.35em').text((d) => abbreviate(d.event_type));
    body.append('text').attr('class', 'x-mark').attr('dy', '0.38em').text('✕');
    const pill = body.append('g').attr('class', 'pill').attr('transform', `translate(${NODE_R - 4},${NODE_R - 6})`);
    pill.append('rect').attr('x', -13).attr('y', -9).attr('width', 26).attr('height', 17).attr('rx', 8.5);
    pill.append('text').attr('dy', '0.35em').text((d) => `L${d.lamport_ts}`);
    body.append('text').attr('class', 'name').attr('y', NODE_R + 22).text((d) => d.event_type.replace(/_/g, ' '));
    body.append('circle').attr('class', 'hit').attr('r', NODE_R + 14);

    // ── Interaction
    const moveTip = (event: MouseEvent, d: DAGNode) => {
      const r = host.getBoundingClientRect();
      latest.current.onHover({ node: d, x: event.clientX - r.left, y: event.clientY - r.top });
    };
    nodeSel
      .on('click', (event, d) => {
        event.stopPropagation();
        latest.current.onSelectNode(d);
      })
      .on('mouseenter', (event, d) => {
        hoverId.current = d.id;
        scene.current?.hover();
        moveTip(event, d);
      })
      .on('mousemove', (event, d) => moveTip(event, d))
      .on('mouseleave', () => {
        hoverId.current = null;
        scene.current?.hover();
        latest.current.onHover(null);
      });

    // ── Zoom & fit
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 3])
      .clickDistance(8)
      .filter((event) => {
        const target = event.target as Element | null;
        if (target && target.closest('.node-item')) return false;
        return (!event.ctrlKey || event.type === 'wheel') && !event.button;
      })
      .on('zoom', (event) => {
        currentRef.current = event.transform;
        g.attr('transform', event.transform.toString());
      });
    zoomRef.current = zoom;
    svg.call(zoom);

    const bb = (g.node() as SVGGElement).getBBox();
    const scale = Math.min((w - 80) / bb.width, (h - 100) / bb.height, 1.15);
    const tx = w / 2 - (bb.x + bb.width / 2) * scale;
    const ty = h / 2 - (bb.y + bb.height / 2) * scale + 10;
    const initial = d3.zoomIdentity.translate(tx, ty).scale(scale);
    initialRef.current = initial;
    svg.call(zoom.transform, initial);

    // ── Style application (selection, anomalies, cascade, lineage focus) ──
    const apply = () => {
      const P = latest.current;
      const anom = new Set(P.anomalyNodeIds);
      const root = new Set(P.rootCauseNodeIds);
      const inv = new Set(P.invalidatedNodeIds);
      const onPath = new Set(P.highlightedPath);
      nodeSel.each(function (d) {
        const el = d3.select(this);
        const isInv = inv.has(d.id);
        el.classed('sel', d.id === P.selectedNodeId)
          .classed('anom', anom.has(d.id))
          .classed('root', root.has(d.id))
          .classed('inv', isInv)
          .classed('rm', d.id === P.removedNodeId)
          .classed('onpath', onPath.has(d.id));
        const base = P.removedNodeId ? depth[P.removedNodeId] ?? 0 : 0;
        el.style('--delay', `${isInv ? Math.max(0, (depth[d.id] ?? 0) - base) * 0.32 : 0}s`);
        const hue = d.id === P.removedNodeId ? PALETTE.crit : isInv ? '#ff8a3d' : getServiceColor(d.service_id);
        el.select('.pearl').attr('fill', `url(#pg-${colorKey(hue)})`);
      });
      edgeSel.each(function (e) {
        const el = d3.select(this);
        const bad = inv.has(e.target) || e.source === P.removedNodeId;
        const path = onPath.has(e.source) && onPath.has(e.target);
        el.classed('inv', bad).classed('path', path && !bad);
      });
      svg.classed('flow-off', !P.flow);
      scene.current?.hover();
    };

    const applyHover = () => {
      const P = latest.current;
      const id = hoverId.current;
      const focus = id || P.selectedNodeId;
      const lin = focus ? lineage(idx, focus) : null;
      nodeSel.classed('dim', (d) => !!id && !lin!.has(d.id));
      edgeSel
        .classed('dim', (e) => !!id && !(lin!.has(e.source) && lin!.has(e.target)))
        .classed('lit', (e) => !!lin && lin.has(e.source) && lin.has(e.target));
    };

    scene.current = { apply, hover: applyHover };
    apply();

    return () => {
      scene.current = null;
      host.innerHTML = '';
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.dagData]);

  // ───────────────────────── Re-style without rebuilding ─────────────────────────
  const key = [
    props.selectedNodeId,
    props.highlightedPath.join('|'),
    props.invalidatedNodeIds.join('|'),
    props.removedNodeId,
    props.anomalyNodeIds.join('|'),
    props.rootCauseNodeIds.join('|'),
    props.flow,
  ].join('::');
  useEffect(() => {
    scene.current?.apply();
  }, [key]);

  return <div ref={hostRef} className="g2d-host" />;
});
Graph2D.displayName = 'Graph2D';
