import React, { useEffect, useRef } from 'react';
import {
  Cam, V3, clamp, lerp, smoothstep, easeInOut, easeOutExpo, mulberry32, project, fog,
  fitCanvas, drawPearl, drawPulse, quad, strokeCurve, rgba,
} from '../../fx/engine3d';
import { prefersReducedMotion, useVisibility } from '../../fx/hooks';

/** The six events of the demo order flow — shared by the hero and the landing "shuffler". */
export interface HeroEvent {
  id: string;
  name: string;
  svc: string;
  lane: string;
  color: string;
  lamport: number;
  parents: string[];
  arrival: number; // rank in the scrambled Kafka arrival order
  layer: number;   // causal layer (x position once reconstructed)
}

export const HERO_EVENTS: HeroEvent[] = [
  { id: 'E1', name: 'ORDER_CREATED',   svc: 'order-svc',     lane: 'ORDER',     color: '#4c6ef5', lamport: 1, parents: [],           arrival: 4, layer: 0 },
  { id: 'E2', name: 'PAYMENT_START',   svc: 'payment-svc',   lane: 'PAYMENT',   color: '#0fb98a', lamport: 2, parents: ['E1'],       arrival: 6, layer: 1 },
  { id: 'E3', name: 'STOCK_CHECK',     svc: 'inventory-svc', lane: 'INVENTORY', color: '#f59f00', lamport: 2, parents: ['E1'],       arrival: 5, layer: 1 },
  { id: 'E4', name: 'PAYMENT_SUCCESS', svc: 'payment-svc',   lane: 'PAYMENT',   color: '#0fb98a', lamport: 3, parents: ['E2'],       arrival: 2, layer: 2 },
  { id: 'E5', name: 'STOCK_RESERVED',  svc: 'inventory-svc', lane: 'INVENTORY', color: '#f59f00', lamport: 3, parents: ['E3'],       arrival: 1, layer: 2 },
  { id: 'E6', name: 'SHIPPING_START',  svc: 'shipping-svc',  lane: 'SHIPPING',  color: '#8f4cf0', lamport: 4, parents: ['E4', 'E5'], arrival: 3, layer: 3 },
];

const LANES = [
  { lane: 'ORDER', y: 1.5, color: '#4c6ef5' },
  { lane: 'PAYMENT', y: 0.5, color: '#0fb98a' },
  { lane: 'INVENTORY', y: -0.5, color: '#f59f00' },
  { lane: 'SHIPPING', y: -1.5, color: '#8f4cf0' },
];
const LAYER_X = [-3.3, -1.1, 1.1, 3.3];
const FLOOR_Y = -3.2;

interface SceneNode {
  hero?: HeroEvent;
  chaos: V3;
  order: V3;
  phase: V3;
  freq: V3;
  amp: number;
  k: number;          // 0 = chaos, 1 = ordered
  appear: number;     // intro stagger
  delay: number;
  r: number;          // world radius
  color: string;
  sx: number; sy: number; sr: number; sz: number; // last screen projection
  cx: number; cy: number;                          // chaos screen projection
  kA: number;         // fog-adjusted alpha
}

interface Props {
  /** 0 = scrambled arrival order, 1 = fully reconstructed. */
  order: number;
  onFocus?: (id: string | null) => void;
}

const PASTELS = ['#b9a8ff', '#8fc9ff', '#ffc2a6', '#9ee9cf', '#f2a9cb', '#c9c2e8', '#a7b6ff'];

export const Loom3D: React.FC<Props> = ({ order, onFocus }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { ref: hostRef, visible } = useVisibility<HTMLDivElement>();
  const orderRef = useRef(order);
  const focusCb = useRef(onFocus);
  orderRef.current = order;
  focusCb.current = onFocus;

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const reduced = prefersReducedMotion();
    const rnd = mulberry32(11);
    const stageEl = canvas.closest('.hero')?.querySelector('.hero-stage') as HTMLElement | null;

    // ---------- build the scene ----------
    const nodes: SceneNode[] = [];
    const heroNodes: SceneNode[] = [];
    const byId: Record<string, SceneNode> = {};

    HERO_EVENTS.forEach((h, i) => {
      const lane = LANES.find((l) => l.lane === h.lane)!;
      const zJit = h.id === 'E2' || h.id === 'E4' ? -0.5 : h.id === 'E3' || h.id === 'E5' ? 0.5 : 0;
      const n: SceneNode = {
        hero: h,
        order: [LAYER_X[h.layer], lane.y, zJit],
        chaos: [(rnd() - 0.5) * 11, (rnd() - 0.5) * 5.4, (rnd() - 0.5) * 6],
        phase: [rnd() * 6.28, rnd() * 6.28, rnd() * 6.28],
        freq: [0.28 + rnd() * 0.3, 0.24 + rnd() * 0.3, 0.2 + rnd() * 0.3],
        amp: 0.55,
        k: 0, appear: 0, delay: 0.2 + i * 0.12,
        r: 0.46, color: h.color,
        sx: 0, sy: 0, sr: 0, sz: 0, cx: 0, cy: 0, kA: 1,
      };
      nodes.push(n);
      heroNodes.push(n);
      byId[h.id] = n;
    });

    const AMB = 46;
    for (let i = 0; i < AMB; i++) {
      const col = i % 12;
      const row = Math.floor(i / 12);
      nodes.push({
        chaos: [(rnd() - 0.5) * 17, (rnd() - 0.5) * 8, (rnd() - 0.5) * 12],
        order: [-6.6 + col * 1.2, 3.1 - row * 1.1, 5.8],
        phase: [rnd() * 6.28, rnd() * 6.28, rnd() * 6.28],
        freq: [0.15 + rnd() * 0.3, 0.15 + rnd() * 0.3, 0.12 + rnd() * 0.25],
        amp: 0.5 + rnd() * 0.7,
        k: 0, appear: 0, delay: 0.5 + rnd() * 1.1,
        r: 0.09 + rnd() * 0.15,
        color: PASTELS[i % PASTELS.length],
        sx: 0, sy: 0, sr: 0, sz: 0, cx: 0, cy: 0, kA: 1,
      });
    }

    const edges: [SceneNode, SceneNode, number][] = [];
    HERO_EVENTS.forEach((h) => h.parents.forEach((p, j) => edges.push([byId[p], byId[h.id], (h.layer * 0.31 + j * 0.47) % 1])));
    const arrivalChain = [...heroNodes].sort((a, b) => a.hero!.arrival - b.hero!.arrival);

    // ---------- state ----------
    const cam: Cam = { yaw: 0, pitch: 0.2, dist: 12, focal: 900, cx: 0, cy: 0 };
    const ptr = { x: -9999, y: -9999, inside: false, moved: false, lastMove: -99 };
    let lensT = 0;
    let yawT = 0, pitchT = 0.2;
    let hover: string | null = null;
    let selected: string | null = null;
    let emitted: string | null = null;
    let W = 800, H = 600, unit = 80, lensR = 160;
    let raf = 0;
    let last = performance.now();
    const t0 = last;

    const emit = () => {
      const f = selected || hover;
      if (f !== emitted) {
        emitted = f;
        focusCb.current?.(f);
      }
    };

    // ---------- input ----------
    const onMove = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      ptr.x = e.clientX - r.left;
      ptr.y = e.clientY - r.top;
      ptr.inside = ptr.x >= 0 && ptr.y >= 0 && ptr.x <= r.width && ptr.y <= r.height;
      ptr.moved = true;
      ptr.lastMove = performance.now();
    };
    const onLeave = () => { ptr.inside = false; };
    const onClick = (e: MouseEvent) => {
      if ((e.target as HTMLElement | null)?.closest?.('a,button,input,select,textarea,[data-nopick]')) return;
      const r = canvas.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return;
      selected = hover && hover !== selected ? hover : null;
      emit();
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('click', onClick);
    document.addEventListener('pointerleave', onLeave);
    window.addEventListener('blur', onLeave);

    // ---------- helpers ----------
    const pos = (n: SceneNode, t: number, k: number): V3 => {
      const e = easeInOut(k);
      const a = n.amp * (1 - e * 0.92) * (reduced ? 0 : 1);
      const cx = n.chaos[0] + Math.sin(t * n.freq[0] + n.phase[0]) * a;
      const cy = n.chaos[1] + Math.sin(t * n.freq[1] + n.phase[1]) * a;
      const cz = n.chaos[2] + Math.sin(t * n.freq[2] + n.phase[2]) * a;
      const bob = n.hero && !reduced ? Math.sin(t * 1.3 + n.phase[0]) * 0.05 * e : 0;
      return [lerp(cx, n.order[0], e), lerp(cy, n.order[1], e) + bob, lerp(cz, n.order[2], e)];
    };

    const label = (text: string, x: number, y: number, a: number, color = '#47456a', size = 10.5, weight = 600, align: CanvasTextAlign = 'center') => {
      if (a <= 0.02) return;
      ctx.save();
      ctx.globalAlpha = clamp(a, 0, 1);
      ctx.font = `${weight} ${size}px "JetBrains Mono", ui-monospace, monospace`;
      ctx.textAlign = align;
      ctx.textBaseline = 'middle';
      ctx.fillStyle = color;
      ctx.fillText(text, x, y);
      ctx.restore();
    };

    const pill = (text: string, x: number, y: number, a: number, fill: string, ink: string) => {
      if (a <= 0.02) return;
      ctx.save();
      ctx.globalAlpha = clamp(a, 0, 1);
      ctx.font = '700 10px "JetBrains Mono", ui-monospace, monospace';
      const w = ctx.measureText(text).width + 14;
      const h = 18;
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.roundRect?.(x - w / 2, y - h / 2, w, h, 9);
      if (!ctx.roundRect) ctx.rect(x - w / 2, y - h / 2, w, h);
      ctx.fill();
      ctx.fillStyle = ink;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, x, y + 0.5);
      ctx.restore();
    };

    const line3 = (a: V3, b: V3, color: string, alpha: number, width = 1) => {
      const pa = project(a, cam), pb = project(b, cam);
      if (!pa.vis || !pb.vis) return;
      ctx.strokeStyle = rgba(color, alpha);
      ctx.lineWidth = width;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    };

    // ---------- frame ----------
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (document.hidden || !visible.current) { last = now; return; }
      const dt = clamp((now - last) / 1000, 0, 0.05);
      last = now;
      const t = (now - t0) / 1000;

      const fit = fitCanvas(canvas);
      W = fit.w; H = fit.h;
      // The scene lives in the page's `.hero-stage` slot (right side on desktop, its own band on mobile).
      if (stageEl) {
        const cr = canvas.getBoundingClientRect();
        const sr = stageEl.getBoundingClientRect();
        cam.cx = sr.left - cr.left + sr.width / 2;
        cam.cy = sr.top - cr.top + sr.height / 2;
        unit = clamp(Math.min(sr.width / 12.4, sr.height / 7.0), 22, 84);
      } else {
        unit = clamp(Math.min(W / 19.5, H / 9.8), 28, 84);
        cam.cx = W * (W > 900 ? 0.7 : 0.5);
        cam.cy = H * 0.5;
      }
      cam.focal = unit * cam.dist;
      lensR = clamp(unit * 2.5, 110, 230);

      // camera parallax follows the pointer, with a slow idle sway
      const nx = ptr.inside ? ptr.x / W - 0.5 : 0;
      const ny = ptr.inside ? ptr.y / H - 0.5 : 0;
      yawT = reduced ? 0 : nx * 0.6 + Math.sin(t * 0.22) * 0.07;
      pitchT = reduced ? 0.2 : 0.2 - ny * 0.28 + Math.sin(t * 0.17) * 0.025;
      cam.yaw += (yawT - cam.yaw) * (1 - Math.exp(-dt * 3.2));
      cam.pitch += (pitchT - cam.pitch) * (1 - Math.exp(-dt * 3.2));

      // the lens: follows the pointer; drifts on its own when the user is idle
      const idle = !ptr.moved || now - ptr.lastMove > 3800 || !ptr.inside;
      let lx = ptr.x, ly = ptr.y, lensTarget = ptr.inside ? 1 : 0;
      if (idle && !reduced) {
        lx = cam.cx + Math.sin(t * 0.55) * unit * 3.6;
        ly = cam.cy + Math.sin(t * 0.83 + 1) * unit * 1.5;
        lensTarget = t > 1.6 ? 0.9 : 0;
      }
      if (reduced) lensTarget = 0;
      lensT += (lensTarget - lensT) * (1 - Math.exp(-dt * 4));
      const lensRad = lensR * easeOutExpo(clamp(lensT, 0, 1));

      const globalK = orderRef.current;

      // ---------- update nodes ----------
      let kHero = 0;
      for (const n of nodes) {
        n.appear = clamp((t - n.delay) / 0.9, 0, 1);
        const cp = pos(n, t, 0);
        const pc = project(cp, cam);
        n.cx = pc.x; n.cy = pc.y;
        // distance from the lens to where the node is, or where it came from — no flicker at the rim
        const d = Math.min(Math.hypot(n.sx - lx, n.sy - ly), Math.hypot(n.cx - lx, n.cy - ly));
        const influence = lensRad > 4 ? smoothstep(lensRad, lensRad * 0.5, d) * clamp(lensT, 0, 1) : 0;
        const target = clamp(Math.max(globalK, influence), 0, 1);
        n.k += (target - n.k) * (1 - Math.exp(-dt * (target > n.k ? 4.2 : 2.6)));
        if (n.hero) kHero += n.k;
        const p = project(pos(n, t, n.k), cam);
        n.sx = p.x; n.sy = p.y; n.sz = p.z;
        n.sr = n.r * p.s * easeOutExpo(n.appear);
        n.kA = fog(p.z, cam.dist, n.hero ? 12 : 9) * n.appear;
      }
      kHero /= heroNodes.length;

      // hover (heroes only)
      let newHover: string | null = null;
      if (ptr.inside && !reduced) {
        let best = 1e9;
        for (const n of heroNodes) {
          const d = Math.hypot(n.sx - ptr.x, n.sy - ptr.y);
          if (d < Math.max(n.sr * 1.35, 22) && d < best) { best = d; newHover = n.hero!.id; }
        }
      }
      if (newHover !== hover) {
        hover = newHover;
        canvas.style.cursor = hover ? 'pointer' : 'default';
        emit();
      }

      // ---------- draw ----------
      ctx.clearRect(0, 0, W, H);

      // floor grid + time ripples
      ctx.lineCap = 'round';
      for (let i = -6; i <= 6; i++) line3([i * 1.5, FLOOR_Y, -8], [i * 1.5, FLOOR_Y, 8], '#6a4cff', 0.07 * (1 - Math.abs(i) / 8));
      for (let j = -5; j <= 5; j++) line3([-9.5, FLOOR_Y, j * 1.6], [9.5, FLOOR_Y, j * 1.6], '#6a4cff', 0.07 * (1 - Math.abs(j) / 7));
      if (!reduced) {
        for (let r = 0; r < 3; r++) {
          const prog = ((t * 0.16 + r / 3) % 1);
          const rad = prog * 8.5;
          ctx.strokeStyle = rgba('#6a4cff', (1 - prog) * 0.2);
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          for (let s = 0; s <= 72; s++) {
            const a = (s / 72) * Math.PI * 2;
            const p = project([Math.cos(a) * rad + 0.5, FLOOR_Y, Math.sin(a) * rad], cam);
            s === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
          }
          ctx.stroke();
        }
      }

      // lane floors (appear as events are reconstructed)
      const laneA = smoothstep(0.08, 0.9, kHero);
      if (laneA > 0.01) {
        for (const l of LANES) {
          const q: V3[] = [[-4.9, l.y + 0.44, 0], [4.9, l.y + 0.44, 0], [4.9, l.y - 0.44, 0], [-4.9, l.y - 0.44, 0]];
          const pq = q.map((v) => project(v, cam));
          ctx.fillStyle = rgba(l.color, 0.07 * laneA);
          ctx.strokeStyle = rgba(l.color, 0.22 * laneA);
          ctx.lineWidth = 1;
          ctx.beginPath();
          pq.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
          const lp = project([4.78, l.y + 0.27, 0], cam);
          label(l.lane, lp.x, lp.y, laneA * 0.9, l.color, 9, 700, 'right');
        }
        // lamport time axis
        const ay = -2.35;
        const a0 = project([-4.6, ay, 0], cam), a1 = project([4.7, ay, 0], cam);
        ctx.strokeStyle = rgba('#15132b', 0.28 * laneA);
        ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(a0.x, a0.y); ctx.lineTo(a1.x, a1.y); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(a1.x, a1.y); ctx.lineTo(a1.x - 7, a1.y - 4); ctx.lineTo(a1.x - 7, a1.y + 4); ctx.closePath(); ctx.fillStyle = rgba('#15132b', 0.35 * laneA); ctx.fill();
        LAYER_X.forEach((x, i) => {
          const tp = project([x, ay, 0], cam);
          ctx.strokeStyle = rgba('#15132b', 0.35 * laneA);
          ctx.beginPath(); ctx.moveTo(tp.x, tp.y - 4); ctx.lineTo(tp.x, tp.y + 4); ctx.stroke();
          label(`L${i + 1}`, tp.x, tp.y + 16, laneA * 0.8, '#47456a', 10, 600);
        });
        label('LAMPORT TIME', a1.x - 4, a1.y + 32, laneA * 0.55, '#7f7da1', 9, 600, 'right');
      }

      // arrival spaghetti: what the raw log claims happened, in the order it arrived
      const chaosA = 1 - kHero;
      if (chaosA > 0.05) {
        for (let i = 0; i < arrivalChain.length - 1; i++) {
          const a = arrivalChain[i], b = arrivalChain[i + 1];
          const al = chaosA * 0.5 * Math.min(a.kA, b.kA) * (1 - Math.max(a.k, b.k));
          if (al < 0.02) continue;
          const mx = (a.sx + b.sx) / 2 + Math.sin(t * 0.8 + i) * 26, my = (a.sy + b.sy) / 2 + Math.cos(t * 0.7 + i) * 26;
          strokeCurve(ctx, a.sx, a.sy, mx, my, b.sx, b.sy, '#f0405f', '#f0405f', 1.3, al, [2, 5]);
          const pt = quad(a.sx, a.sy, mx, my, b.sx, b.sy, (t * 0.35 + i * 0.2) % 1);
          drawPulse(ctx, pt[0], pt[1], 2.2, '#f0405f', al * 1.4);
        }
      }

      // causal edges
      for (const [a, b, off] of edges) {
        const kk = Math.min(a.k, b.k);
        const al = smoothstep(0.45, 1, kk) * Math.min(a.kA, b.kA);
        if (al < 0.02) continue;
        const dx = b.sx - a.sx, dy = b.sy - a.sy;
        const len = Math.hypot(dx, dy) || 1;
        const bend = Math.min(60, len * 0.2);
        const cxp = (a.sx + b.sx) / 2 - (dy / len) * bend;
        const cyp = (a.sy + b.sy) / 2 + (dx / len) * bend;
        // ink the thread, then add a luminous core
        strokeCurve(ctx, a.sx, a.sy, cxp, cyp, b.sx, b.sy, a.color, b.color, 3.4, al * 0.22);
        strokeCurve(ctx, a.sx, a.sy, cxp, cyp, b.sx, b.sy, a.color, b.color, 1.8, al * 0.95);
        // arrow head
        const ex = b.sx - dx / len * (b.sr + 6), ey = b.sy - dy / len * (b.sr + 6);
        const ang = Math.atan2(b.sy - cyp, b.sx - cxp);
        ctx.save();
        ctx.translate(ex, ey); ctx.rotate(ang);
        ctx.fillStyle = rgba(b.color, al);
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-9, -4.5); ctx.lineTo(-9, 4.5); ctx.closePath(); ctx.fill();
        ctx.restore();
        if (!reduced) {
          for (let q = 0; q < 2; q++) {
            const tt = (t * 0.28 + off + q * 0.5) % 1;
            const pt = quad(a.sx, a.sy, cxp, cyp, b.sx, b.sy, tt);
            drawPulse(ctx, pt[0], pt[1], 2.8, '#ffffff', al * Math.sin(tt * Math.PI));
          }
        }
      }

      // pearls — far to near
      const sorted = [...nodes].sort((a, b) => b.sz - a.sz);
      for (const n of sorted) {
        if (n.sr < 0.6 || n.kA < 0.02) continue;
        const h = n.hero;
        const isF = h && (h.id === selected || h.id === hover);
        const alpha = h ? Math.max(0.55, n.kA) : n.kA * lerp(0.55, 0.28, n.k);
        drawPearl(ctx, n.sx, n.sy, n.sr * (isF ? 1.1 : 1), n.color, alpha, {
          glow: h ? 2.6 : 2.0,
          glowAlpha: h ? 0.3 + n.k * 0.1 : 0.2,
        });
        if (h) {
          label(h.id, n.sx, n.sy + 0.5, n.kA, '#ffffff', Math.max(10, n.sr * 0.34), 700);
          const labA = n.kA * smoothstep(0.1, 0.5, n.appear);
          label(h.name, n.sx, n.sy + n.sr + 20, labA * 0.95, '#15132b', 10.5, 600);
          // badge: arrival rank while scrambled, Lamport once reconstructed
          const by = n.sy - n.sr - 16;
          pill(`#${h.arrival}`, n.sx, by, labA * (1 - smoothstep(0.2, 0.7, n.k)), 'rgba(240,64,95,0.14)', '#c3213f');
          pill(`L${h.lamport}`, n.sx, by, labA * smoothstep(0.3, 0.9, n.k), 'rgba(15,185,138,0.16)', '#087a5a');
          if (isF) {
            ctx.strokeStyle = rgba(n.color, 0.9);
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.lineDashOffset = -t * 18;
            ctx.beginPath(); ctx.arc(n.sx, n.sy, n.sr + 10, 0, Math.PI * 2); ctx.stroke();
            ctx.setLineDash([]);
          }
        }
      }

      // the order lens — a clock bezel that reveals causal order
      if (lensRad > 6) {
        const a = clamp(lensT, 0, 1);
        const g = ctx.createRadialGradient(lx, ly, lensRad * 0.2, lx, ly, lensRad);
        g.addColorStop(0, `rgba(255,255,255,${0.1 * a})`);
        g.addColorStop(0.85, `rgba(255,255,255,${0.24 * a})`);
        g.addColorStop(1, `rgba(255,255,255,${0.5 * a})`);
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(lx, ly, lensRad, 0, Math.PI * 2); ctx.fill();
        const rg = ctx.createLinearGradient(lx - lensRad, ly - lensRad, lx + lensRad, ly + lensRad);
        rg.addColorStop(0, `rgba(106,76,255,${0.7 * a})`);
        rg.addColorStop(0.5, `rgba(47,155,255,${0.55 * a})`);
        rg.addColorStop(1, `rgba(20,209,176,${0.7 * a})`);
        ctx.strokeStyle = rg;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(lx, ly, lensRad, 0, Math.PI * 2); ctx.stroke();
        for (let i = 0; i < 60; i++) {
          const ang = (i / 60) * Math.PI * 2 + t * 0.12;
          const major = i % 5 === 0;
          const r0 = lensRad + 5, r1 = lensRad + (major ? 14 : 9);
          ctx.strokeStyle = `rgba(21,19,43,${(major ? 0.5 : 0.22) * a})`;
          ctx.lineWidth = major ? 1.6 : 1;
          ctx.beginPath();
          ctx.moveTo(lx + Math.cos(ang) * r0, ly + Math.sin(ang) * r0);
          ctx.lineTo(lx + Math.cos(ang) * r1, ly + Math.sin(ang) * r1);
          ctx.stroke();
        }
        // sweeping second-hand
        const sh = t * 1.1;
        ctx.strokeStyle = `rgba(106,76,255,${0.55 * a})`;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(lx, ly);
        ctx.lineTo(lx + Math.cos(sh) * lensRad * 0.96, ly + Math.sin(sh) * lensRad * 0.96);
        ctx.stroke();
        ctx.fillStyle = `rgba(106,76,255,${0.9 * a})`;
        ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2); ctx.fill();
        label('ORDER LENS', lx, ly + lensRad + 30, a * 0.6, '#47456a', 9.5, 700);
      }
    };

    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('click', onClick);
      document.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('blur', onLeave);
    };
  }, [visible]);

  return (
    <div ref={hostRef} className="loom-host" aria-hidden="true">
      <canvas ref={canvasRef} className="loom-canvas" />
    </div>
  );
};
