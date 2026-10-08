import React, { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { GraphHandle, GraphViewProps } from './types';
import {
  Cam, V3, clamp, easeOutExpo, fitCanvas, project, fog, drawPearl, drawPulse, quad, rgba, strokeCurve,
} from '../../fx/engine3d';
import { prefersReducedMotion, useVisibility } from '../../fx/hooks';
import { getServiceColor, getServiceLabel, PALETTE } from '../../utils/colors';
import { indexDag, lineage, abbreviate } from '../../utils/dagLayout';

const DX = 3.0;   // world distance per causal layer
const DY = 2.5;   // world distance per service slab
const DEFAULT = { yaw: -0.62, pitch: 0.4, zoom: 1 };

/**
 * The causal DAG as floating glass slabs — one per service, time running left to right.
 * Drag to orbit, scroll to zoom, hover to isolate a lineage, click to select.
 */
export const Dag3D = forwardRef<GraphHandle, GraphViewProps>((props, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { ref: hostRef, visible } = useVisibility<HTMLDivElement>();
  const latest = useRef(props);
  latest.current = props;
  const ctl = useRef({ zoom: 1, tYaw: DEFAULT.yaw, tPitch: DEFAULT.pitch, tZoom: 1, tween: false });

  useImperativeHandle(ref, () => ({
    zoomIn: () => { ctl.current.tZoom = clamp(ctl.current.tZoom * 1.25, 0.5, 2.8); ctl.current.tween = true; },
    zoomOut: () => { ctl.current.tZoom = clamp(ctl.current.tZoom / 1.25, 0.5, 2.8); ctl.current.tween = true; },
    reset: () => { ctl.current.tYaw = DEFAULT.yaw; ctl.current.tPitch = DEFAULT.pitch; ctl.current.tZoom = 1; ctl.current.tween = true; },
  }));

  // Only the DAG shape rebuilds the scene; states are read live from `latest`.
  const dag = props.dagData;
  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const reduced = prefersReducedMotion();
    const idx = indexDag(dag);
    const { nodes, edges, depth, services, maxDepth } = idx;
    const S = services.length;

    // ── layout
    const slot: Record<string, number> = {};
    const bucketCount: Record<string, number> = {};
    nodes.forEach((n) => {
      const k = `${n.service_id}_${depth[n.id]}`;
      slot[n.id] = bucketCount[k] || 0;
      bucketCount[k] = slot[n.id] + 1;
    });
    const laneY = (svc: string) => ((S - 1) / 2 - services.indexOf(svc)) * DY;
    const world: Record<string, V3> = {};
    nodes.forEach((n) => {
      const cnt = bucketCount[`${n.service_id}_${depth[n.id]}`];
      world[n.id] = [(depth[n.id] - maxDepth / 2) * DX, laneY(n.service_id), (slot[n.id] - (cnt - 1) / 2) * 1.5];
    });
    const x0 = -maxDepth / 2 * DX - 1.8, x1 = maxDepth / 2 * DX + 1.8;

    // Fit: project every slab corner and node at the default orientation, then size the camera to the result.
    let fitKey = '';
    let baseFocal = 900;
    const refit = (W: number, H: number) => {
      const key = `${Math.round(W)}x${Math.round(H)}`;
      if (key === fitKey) return;
      fitKey = key;
      const c0: Cam = { yaw: DEFAULT.yaw, pitch: DEFAULT.pitch, dist: 18, focal: 1000, cx: 0, cy: 0 };
      const pts: V3[] = [];
      services.forEach((sv) => {
        const y = laneY(sv) - 0.85;
        pts.push([x0, y, -2.4], [x1, y, -2.4], [x1, y, 2.4], [x0, y, 2.4]);
      });
      nodes.forEach((n) => pts.push(world[n.id]));
      let mx = 1, my = 1;
      pts.forEach((pt) => {
        const q = project(pt, c0);
        mx = Math.max(mx, Math.abs(q.x));
        my = Math.max(my, Math.abs(q.y));
      });
      baseFocal = 1000 * Math.min((W / 2 - 34) / mx, (H / 2 - 48) / my);
    };

    const cam: Cam = { yaw: DEFAULT.yaw, pitch: DEFAULT.pitch, dist: 18, focal: 900, cx: 0, cy: 0 };
    ctl.current.zoom = 1; ctl.current.tZoom = 1; ctl.current.tYaw = DEFAULT.yaw; ctl.current.tPitch = DEFAULT.pitch;
    let yawV = 0;
    let dragging = false, moved = 0, lastX = 0, lastY = 0, lastInteract = -99;
    let hover: string | null = null;
    let raf = 0;
    let last = performance.now();
    const t0 = last;
    let born = reduced ? 1 : 0;
    let invKey = '';
    let invStart = 0;
    const scr: Record<string, { x: number; y: number; r: number; z: number }> = {};
    const lineageCache: Record<string, Set<string>> = {};
    const lin = (id: string) => (lineageCache[id] ||= lineage(idx, id));

    const hoverEmit = (e: PointerEvent | null) => {
      if (!hover || !e) { latest.current.onHover(null); return; }
      const r = canvas.getBoundingClientRect();
      latest.current.onHover({ node: idx.byId[hover], x: e.clientX - r.left, y: e.clientY - r.top });
    };

    const onDown = (e: PointerEvent) => {
      dragging = true; moved = 0; lastX = e.clientX; lastY = e.clientY; lastInteract = performance.now();
      ctl.current.tween = false;
      canvas.setPointerCapture(e.pointerId);
      canvas.style.cursor = 'grabbing';
    };
    const onMove = (e: PointerEvent) => {
      if (dragging) {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        lastX = e.clientX; lastY = e.clientY;
        moved += Math.abs(dx) + Math.abs(dy);
        cam.yaw += dx * 0.008;
        cam.pitch = clamp(cam.pitch + dy * 0.006, -0.1, 1.25);
        ctl.current.tYaw = cam.yaw; ctl.current.tPitch = cam.pitch;
        yawV = dx * 0.008;
        lastInteract = performance.now();
        return;
      }
      const r = canvas.getBoundingClientRect();
      const px = e.clientX - r.left, py = e.clientY - r.top;
      let best: string | null = null, bd = 1e9;
      for (const n of nodes) {
        const s = scr[n.id];
        if (!s) continue;
        const d = Math.hypot(s.x - px, s.y - py);
        if (d < Math.max(s.r * 1.4, 20) && d < bd && s.z < 1e8) { bd = d; best = n.id; }
      }
      if (best !== hover) {
        hover = best;
        canvas.style.cursor = best ? 'pointer' : 'grab';
      }
      hoverEmit(e);
    };
    const onUp = (e: PointerEvent) => {
      const wasClick = dragging && moved < 5;
      dragging = false;
      try { canvas.releasePointerCapture(e.pointerId); } catch { /* noop */ }
      canvas.style.cursor = hover ? 'pointer' : 'grab';
      if (wasClick && hover) latest.current.onSelectNode(idx.byId[hover]);
    };
    const onLeave = () => { hover = null; latest.current.onHover(null); };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      ctl.current.tZoom = clamp(ctl.current.tZoom * Math.exp(-e.deltaY * 0.0012), 0.5, 2.8);
      ctl.current.tween = true;
    };
    canvas.style.cursor = 'grab';
    canvas.addEventListener('pointerdown', onDown);
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerup', onUp);
    canvas.addEventListener('pointercancel', onUp);
    canvas.addEventListener('pointerleave', onLeave);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    const halo = (txt: string, x: number, y: number, size: number, weight: number, color: string, a: number, align: CanvasTextAlign = 'center', family = '"JetBrains Mono", ui-monospace, monospace') => {
      ctx.save();
      ctx.globalAlpha = clamp(a, 0, 1);
      ctx.font = `${weight} ${size}px ${family}`;
      ctx.textAlign = align; ctx.textBaseline = 'middle';
      ctx.lineJoin = 'round'; ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 4;
      ctx.strokeText(txt, x, y);
      ctx.fillStyle = color; ctx.fillText(txt, x, y);
      ctx.restore();
    };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (document.hidden || !visible.current) { last = now; return; }
      const dt = clamp((now - last) / 1000, 0, 0.05);
      last = now;
      const t = (now - t0) / 1000;
      born = reduced ? 1 : clamp(t / 1.2, 0, 1);
      const P = latest.current;

      const fit = fitCanvas(canvas);
      const W = fit.w, H = fit.h;

      // camera easing (toolbar / wheel / reset)
      const c = ctl.current;
      if (c.tween) {
        const k = 1 - Math.exp(-dt * 7);
        c.zoom += (c.tZoom - c.zoom) * k;
        cam.yaw += (c.tYaw - cam.yaw) * k;
        cam.pitch += (c.tPitch - cam.pitch) * k;
        if (Math.abs(c.tZoom - c.zoom) < 0.001 && Math.abs(c.tYaw - cam.yaw) < 0.001) c.tween = false;
      }
      if (!dragging && !c.tween) {
        cam.yaw += yawV;
        yawV *= Math.pow(0.04, dt);
        c.tYaw = cam.yaw;
      }
      const idle = now - lastInteract > 3000;
      const sway = reduced || !idle ? 0 : Math.sin(t * 0.35) * 0.09;

      refit(W, H);
      cam.focal = baseFocal * c.zoom;
      cam.cx = W / 2;
      cam.cy = H / 2 + 8;
      const camDraw: Cam = { ...cam, yaw: cam.yaw + sway };

      ctx.clearRect(0, 0, W, H);

      // state sets
      const sel = P.selectedNodeId;
      const anom = new Set(P.anomalyNodeIds);
      const root = new Set(P.rootCauseNodeIds);
      const inv = new Set(P.invalidatedNodeIds);
      const onPath = new Set(P.highlightedPath);
      const k2 = P.invalidatedNodeIds.join('|');
      if (k2 !== invKey) { invKey = k2; invStart = t; }
      const focus = hover || sel;
      const L = focus ? lin(focus) : null;
      const dimming = !!hover;

      // slabs
      services.forEach((s) => {
        const col = getServiceColor(s);
        const y = laneY(s) - 0.85;
        const q: V3[] = [[x0, y, -2.4], [x1, y, -2.4], [x1, y, 2.4], [x0, y, 2.4]];
        const pq = q.map((v) => project(v, camDraw));
        const fa = easeOutExpo(born);
        const g = ctx.createLinearGradient(pq[0].x, pq[0].y, pq[2].x, pq[2].y);
        g.addColorStop(0, rgba(col, 0.2 * fa));
        g.addColorStop(1, rgba(col, 0.06 * fa));
        ctx.fillStyle = g;
        ctx.strokeStyle = rgba(col, 0.38 * fa);
        ctx.lineWidth = 1.3;
        ctx.beginPath();
        pq.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
        ctx.closePath(); ctx.fill(); ctx.stroke();
        // time ticks
        for (let d = 0; d <= maxDepth; d++) {
          const a = project([(d - maxDepth / 2) * DX, y, -2.4], camDraw);
          const b = project([(d - maxDepth / 2) * DX, y, 2.4], camDraw);
          ctx.strokeStyle = rgba(col, 0.14 * fa);
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 5]);
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          ctx.setLineDash([]);
        }
        const lp = project([x0 + 0.3, y, 2.4], camDraw);
        halo(getServiceLabel(s), lp.x, lp.y - 11, 10, 700, col, 0.95 * fa, 'left');
      });

      // projected positions
      type Item = { id: string; p: ReturnType<typeof project>; w: V3; r: number; app: number };
      const items: Record<string, Item> = {};
      nodes.forEach((n) => {
        const w = world[n.id];
        const p = project(w, camDraw);
        const app = easeOutExpo(clamp(born * 1.6 - depth[n.id] * 0.12, 0, 1));
        items[n.id] = { id: n.id, p, w, r: 0.62 * p.s * app, app };
        scr[n.id] = { x: p.x, y: p.y, r: 0.62 * p.s, z: p.vis ? p.z : 1e9 };
      });

      // drop lines and slab shadows
      nodes.forEach((n) => {
        const it = items[n.id];
        const ground = project([it.w[0], laneY(n.service_id) - 0.85, it.w[2]], camDraw);
        const a = 0.28 * it.app * fog(it.p.z, cam.dist, 14);
        ctx.strokeStyle = rgba(getServiceColor(n.service_id), a);
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 4]);
        ctx.beginPath(); ctx.moveTo(it.p.x, it.p.y); ctx.lineTo(ground.x, ground.y); ctx.stroke();
        ctx.setLineDash([]);
        const sh = ctx.createRadialGradient(ground.x, ground.y, 0, ground.x, ground.y, it.r * 1.3);
        sh.addColorStop(0, `rgba(21,19,43,${0.2 * it.app})`);
        sh.addColorStop(1, 'rgba(21,19,43,0)');
        ctx.fillStyle = sh;
        ctx.beginPath();
        ctx.ellipse(ground.x, ground.y, it.r * 1.3, it.r * 0.5 * Math.max(0.35, Math.cos(cam.pitch)), 0, 0, Math.PI * 2);
        ctx.fill();
      });

      // edges
      edges.forEach((e, ei) => {
        const a = items[e.source], b = items[e.target];
        if (!a || !b) return;
        const ctrl = project([(a.w[0] + b.w[0]) / 2, (a.w[1] + b.w[1]) / 2 + 0.9, (a.w[2] + b.w[2]) / 2], camDraw);
        const inLin = !L || (L.has(e.source) && L.has(e.target));
        const bad = inv.has(e.target) || e.source === P.removedNodeId;
        const path = onPath.has(e.source) && onPath.has(e.target);
        const dim = dimming && !inLin;
        const lit = !!L && inLin;
        const ca = bad ? PALETTE.crit : path ? PALETTE.warn : getServiceColor(idx.byId[e.source].service_id);
        const cb = bad ? PALETTE.crit : path ? PALETTE.warn : getServiceColor(idx.byId[e.target].service_id);
        const al = (dim ? 0.1 : lit || bad || path ? 0.95 : 0.6) * Math.min(a.app, b.app) * fog((a.p.z + b.p.z) / 2, cam.dist, 14);
        // stop short of the target pearl
        const dx = b.p.x - ctrl.x, dy = b.p.y - ctrl.y;
        const dl = Math.hypot(dx, dy) || 1;
        const ex = b.p.x - (dx / dl) * (b.r + 6), ey = b.p.y - (dy / dl) * (b.r + 6);
        strokeCurve(ctx, a.p.x, a.p.y, ctrl.x, ctrl.y, ex, ey, ca, cb, lit || path || bad ? 3.2 : 2.2, al, e.explicit ? undefined : [7, 6]);
        ctx.save();
        ctx.translate(ex, ey); ctx.rotate(Math.atan2(dy, dx));
        ctx.fillStyle = rgba(cb, al);
        ctx.beginPath(); ctx.moveTo(4, 0); ctx.lineTo(-8, -5); ctx.lineTo(-8, 5); ctx.closePath(); ctx.fill();
        ctx.restore();
        if (P.flow && !reduced && !dim) {
          for (let q = 0; q < 2; q++) {
            const tt = (t * 0.32 + (ei * 0.23) + q * 0.5) % 1;
            const pt = quad(a.p.x, a.p.y, ctrl.x, ctrl.y, ex, ey, tt);
            drawPulse(ctx, pt[0], pt[1], 2.6, bad ? PALETTE.crit : '#ffffff', al * Math.sin(tt * Math.PI));
          }
        }
      });

      // nodes — far to near
      Object.values(items).sort((a, b) => b.p.z - a.p.z).forEach((it) => {
        const n = idx.byId[it.id];
        if (it.r < 0.6) return;
        const f = fog(it.p.z, cam.dist, 14);
        const dim = dimming && L && !L.has(it.id);
        const isInv = inv.has(it.id);
        const isRm = it.id === P.removedNodeId;
        const hue = isRm ? PALETTE.crit : isInv ? '#ff8a3d' : getServiceColor(n.service_id);
        const alpha = (dim ? 0.2 : 1) * Math.max(0.65, f);

        // cascade shock wave
        if (isInv && !reduced) {
          const base = P.removedNodeId ? depth[P.removedNodeId] : 0;
          const delay = Math.max(0, depth[it.id] - base) * 0.32;
          const ph = (t - invStart - delay) / 1.1;
          if (ph > 0 && ph < 1) {
            ctx.strokeStyle = rgba(PALETTE.crit, (1 - ph) * 0.8);
            ctx.lineWidth = 3;
            ctx.beginPath(); ctx.arc(it.p.x, it.p.y, it.r * (1.1 + ph * 1.8), 0, Math.PI * 2); ctx.stroke();
          }
        }
        if (anom.has(it.id) && !reduced) {
          const ph = (t * 0.9 + depth[it.id] * 0.2) % 1;
          ctx.strokeStyle = rgba('#e11d48', (1 - ph) * 0.75 * alpha);
          ctx.lineWidth = 2.4;
          ctx.beginPath(); ctx.arc(it.p.x, it.p.y, it.r * (1.2 + ph * 0.9), 0, Math.PI * 2); ctx.stroke();
        }

        drawPearl(ctx, it.p.x, it.p.y, it.r * (it.id === hover ? 1.1 : 1), hue, alpha, {
          glow: 2.4, glowAlpha: 0.26, hollow: isRm,
        });
        if (!isRm) {
          ctx.save();
          ctx.globalAlpha = clamp(alpha, 0, 1);
          ctx.font = `700 ${Math.max(9, it.r * 0.4)}px "JetBrains Mono", monospace`;
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillStyle = 'rgba(21,19,43,0.35)';
          ctx.fillText(abbreviate(n.event_type), it.p.x + 0.6, it.p.y + 1.2);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(abbreviate(n.event_type), it.p.x, it.p.y + 0.5);
          ctx.restore();
        }

        if (root.has(it.id) || anom.has(it.id) || it.id === sel) {
          ctx.strokeStyle = it.id === sel ? PALETTE.warn : root.has(it.id) ? '#f43f5e' : '#e11d48';
          ctx.lineWidth = 2.4;
          ctx.setLineDash([6, 5]);
          ctx.lineDashOffset = -t * 20;
          ctx.beginPath(); ctx.arc(it.p.x, it.p.y, it.r + 9, 0, Math.PI * 2); ctx.stroke();
          ctx.setLineDash([]);
        }

        // Lamport pill and name
        const px = it.p.x + it.r * 0.8, py = it.p.y + it.r * 0.78;
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.fillStyle = '#ffffff'; ctx.strokeStyle = rgba('#15132b', 0.14); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(px, py, 10, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.fillStyle = PALETTE.iris1; ctx.font = '700 8.5px "JetBrains Mono", monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(`L${n.lamport_ts}`, px, py + 0.5);
        ctx.restore();
        halo(n.event_type.replace(/_/g, ' '), it.p.x, it.p.y + it.r + 17, 10, 600, '#15132b', alpha * 0.9);
      });
    };

    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      canvas.removeEventListener('pointerdown', onDown);
      canvas.removeEventListener('pointermove', onMove);
      canvas.removeEventListener('pointerup', onUp);
      canvas.removeEventListener('pointercancel', onUp);
      canvas.removeEventListener('pointerleave', onLeave);
      canvas.removeEventListener('wheel', onWheel);
    };
  }, [dag, visible]);

  return (
    <div ref={hostRef} className="g3d-host">
      <canvas ref={canvasRef} className="g3d-canvas" role="img" aria-label="Interactive 3D causal graph" />
      <div className="g3d-hint"><span>drag to orbit · scroll to zoom</span></div>
    </div>
  );
});
Dag3D.displayName = 'Dag3D';

