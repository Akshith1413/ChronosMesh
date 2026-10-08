import React, { useEffect, useRef, useState } from 'react';
import {
  Cam, V3, clamp, fitCanvas, project, fog, drawPearl, drawPulse, rgba, quad, easeOutExpo,
} from '../../fx/engine3d';
import { prefersReducedMotion, useVisibility } from '../../fx/hooks';
import { ServiceHealthItem } from '../../types';
import { getServiceColor, getServiceLabel } from '../../utils/colors';

const STATUS_COLOR: Record<string, string> = {
  Healthy: '#0fb98a',
  Degraded: '#f59f00',
  Critical: '#f0405f',
  Unavailable: '#8b89a8',
};

interface Props {
  services: ServiceHealthItem[];
  loading?: boolean;
}

interface Tip { i: number; x: number; y: number }

/** Services as pearls orbiting the mesh core. Drag to rotate; hover for detail. */
export const ServiceOrbit: React.FC<Props> = ({ services, loading }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { ref: hostRef, visible } = useVisibility<HTMLDivElement>();
  const svcRef = useRef(services);
  const [tip, setTip] = useState<Tip | null>(null);
  svcRef.current = services;

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const reduced = prefersReducedMotion();
    const cam: Cam = { yaw: 0.5, pitch: 0.42, dist: 15, focal: 900, cx: 0, cy: 0 };
    let yawV = 0, pitchV = 0;
    let dragging = false;
    let lastX = 0, lastY = 0;
    let lastInteract = -99;
    let hoverIdx = -1;
    let W = 600, H = 400;
    let raf = 0;
    let last = performance.now();
    const t0 = last;
    let born = 0;
    const screen: { x: number; y: number; r: number }[] = [];

    const onDown = (e: PointerEvent) => {
      dragging = true;
      lastX = e.clientX; lastY = e.clientY;
      lastInteract = performance.now();
      canvas.setPointerCapture(e.pointerId);
      canvas.style.cursor = 'grabbing';
    };
    const onMove = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      const px = e.clientX - r.left, py = e.clientY - r.top;
      if (dragging) {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        lastX = e.clientX; lastY = e.clientY;
        cam.yaw += dx * 0.008;
        cam.pitch = clamp(cam.pitch + dy * 0.006, -0.25, 1.1);
        yawV = dx * 0.008; pitchV = 0;
        lastInteract = performance.now();
        return;
      }
      let best = -1, bd = 1e9;
      screen.forEach((s, i) => {
        const d = Math.hypot(s.x - px, s.y - py);
        if (d < Math.max(s.r * 1.5, 24) && d < bd) { bd = d; best = i; }
      });
      if (best !== hoverIdx) {
        hoverIdx = best;
        canvas.style.cursor = best >= 0 ? 'pointer' : 'grab';
        if (best < 0) setTip(null);
      }
      if (best >= 0) setTip({ i: best, x: px, y: py });
    };
    const onUp = (e: PointerEvent) => {
      dragging = false;
      canvas.style.cursor = hoverIdx >= 0 ? 'pointer' : 'grab';
      try { canvas.releasePointerCapture(e.pointerId); } catch { /* noop */ }
    };
    const onLeave = () => { hoverIdx = -1; setTip(null); };
    canvas.style.cursor = 'grab';
    canvas.addEventListener('pointerdown', onDown);
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerup', onUp);
    canvas.addEventListener('pointercancel', onUp);
    canvas.addEventListener('pointerleave', onLeave);

    const ringPoly = (radius: number, y: number, a: number, color: string, width: number, dash?: number[], spin = 0) => {
      ctx.strokeStyle = rgba(color, a);
      ctx.lineWidth = width;
      ctx.setLineDash(dash || []);
      ctx.beginPath();
      for (let s = 0; s <= 90; s++) {
        const ang = (s / 90) * Math.PI * 2 + spin;
        const p = project([Math.cos(ang) * radius, y, Math.sin(ang) * radius], cam);
        s === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };

    const text = (s: string, x: number, y: number, size: number, weight: number, color: string, a = 1, align: CanvasTextAlign = 'center') => {
      ctx.save();
      ctx.globalAlpha = clamp(a, 0, 1);
      ctx.font = `${weight} ${size}px "JetBrains Mono", ui-monospace, monospace`;
      ctx.textAlign = align;
      ctx.textBaseline = 'middle';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = 'rgba(255,255,255,0.92)';
      ctx.lineWidth = 4;
      ctx.strokeText(s, x, y);
      ctx.fillStyle = color;
      ctx.fillText(s, x, y);
      ctx.restore();
    };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (document.hidden || !visible.current) { last = now; return; }
      const dt = clamp((now - last) / 1000, 0, 0.05);
      last = now;
      const t = (now - t0) / 1000;
      born = reduced ? 1 : clamp(t / 1.1, 0, 1);

      const fit = fitCanvas(canvas);
      W = fit.w; H = fit.h;
      cam.cx = W / 2;
      cam.cy = H * 0.52;
      cam.focal = clamp(Math.min(W / 9.8, H / 5.4), 38, 96) * cam.dist;

      // inertia + idle auto-rotation
      if (!dragging) {
        cam.yaw += yawV;
        yawV *= Math.pow(0.04, dt);
        const idle = now - lastInteract > 2500;
        if (idle && !reduced) cam.yaw += dt * 0.16;
      }

      const svcs = svcRef.current;
      const ghost = svcs.length === 0;
      const list: { name: string; color: string; status: string; ev: number; an: number }[] = ghost
        ? Array.from({ length: 5 }, (_, i) => ({ name: '', color: '#b4b2cc', status: 'Unavailable', ev: 0, an: 0 }))
        : svcs.map((s) => ({ name: s.service_name, color: getServiceColor(s.service_name), status: s.status, ev: s.event_count, an: s.anomaly_count }));
      const n = list.length;
      const R = 3.5;

      ctx.clearRect(0, 0, W, H);

      // orbit rings & floor glow
      ringPoly(R, 0, 0.2, '#6a4cff', 1.4);
      ringPoly(R * 1.5, 0, 0.12, '#6a4cff', 1.2, [3, 8]);
      ringPoly(R * 0.55, 0, 0.12, '#2f9bff', 1.2);
      ringPoly(R * 1.22, -1.1, 0.07, '#6a4cff', 1, [2, 6], t * 0.05);
      const floor = project([0, -1.8, 0], cam);
      const fg = ctx.createRadialGradient(floor.x, floor.y, 0, floor.x, floor.y, cam.focal / cam.dist * R * 1.8);
      fg.addColorStop(0, 'rgba(106,76,255,0.10)');
      fg.addColorStop(1, 'rgba(106,76,255,0)');
      ctx.fillStyle = fg;
      ctx.beginPath();
      ctx.ellipse(floor.x, floor.y, cam.focal / cam.dist * R * 1.8, cam.focal / cam.dist * R * 0.8, 0, 0, Math.PI * 2);
      ctx.fill();

      // service positions
      type Item = { i: number; p: ReturnType<typeof project>; w: V3; d: typeof list[number] };
      const items: Item[] = list.map((d, i) => {
        const ang = (i / n) * Math.PI * 2 + Math.PI / 6;
        const wob = reduced ? 0 : Math.sin(t * 0.9 + i * 1.7) * 0.18;
        const w: V3 = [Math.cos(ang) * R, wob + Math.sin(ang * 2 + i) * 0.25, Math.sin(ang) * R];
        return { i, p: project(w, cam), w, d };
      });

      const coreP = project([0, 0, 0], cam);

      // threads core <-> service + travelling pulses
      items.forEach(({ p, d, i }) => {
        const a = (ghost ? 0.18 : 0.5) * fog(p.z, cam.dist, 9) * easeOutExpo(born);
        const g = ctx.createLinearGradient(coreP.x, coreP.y, p.x, p.y);
        g.addColorStop(0, rgba('#6a4cff', a));
        g.addColorStop(1, rgba(d.color, a));
        ctx.strokeStyle = g;
        ctx.lineWidth = 1.8;
        ctx.setLineDash(ghost ? [4, 6] : []);
        ctx.beginPath(); ctx.moveTo(coreP.x, coreP.y); ctx.lineTo(p.x, p.y); ctx.stroke();
        ctx.setLineDash([]);
        if (!ghost && d.status !== 'Unavailable' && !reduced) {
          const count = 1 + Math.min(3, Math.floor(d.ev / 2));
          for (let q = 0; q < count; q++) {
            const tt = (t * (0.3 + (d.status === 'Critical' ? 0.3 : 0)) + q / count + i * 0.13) % 1;
            const pt = quad(p.x, p.y, (p.x + coreP.x) / 2, (p.y + coreP.y) / 2, coreP.x, coreP.y, tt);
            drawPulse(ctx, pt[0], pt[1], 2.6, d.color, Math.sin(tt * Math.PI) * 0.95);
          }
        }
      });

      // draw core + services sorted by depth
      type Drawable = { z: number; draw: () => void };
      const out: Drawable[] = [];
      out.push({
        z: coreP.z,
        draw: () => {
          const r = 0.95 * coreP.s * easeOutExpo(born);
          // halo
          const hg = ctx.createRadialGradient(coreP.x, coreP.y, r * 0.5, coreP.x, coreP.y, r * 3.2);
          hg.addColorStop(0, 'rgba(106,76,255,0.28)');
          hg.addColorStop(0.5, 'rgba(47,155,255,0.10)');
          hg.addColorStop(1, 'rgba(47,155,255,0)');
          ctx.fillStyle = hg;
          ctx.beginPath(); ctx.arc(coreP.x, coreP.y, r * 3.2, 0, Math.PI * 2); ctx.fill();
          drawPearl(ctx, coreP.x, coreP.y, r, '#6a4cff', 1, { glow: 1.8, glowAlpha: 0.35 });
          // bezel rings tilted in 3D
          for (let k = 0; k < 2; k++) {
            ctx.strokeStyle = k ? rgba('#14d1b0', 0.7) : rgba('#2f9bff', 0.75);
            ctx.lineWidth = 1.8;
            ctx.beginPath();
            for (let s = 0; s <= 80; s++) {
              const ang = (s / 80) * Math.PI * 2;
              const rad = 1.55 + k * 0.28;
              const x = Math.cos(ang) * rad, z = Math.sin(ang) * rad;
              const tilt = t * (0.5 + k * 0.3) + k * 1.2;
              const pt = project([x, z * Math.sin(tilt) * 0.55, z * Math.cos(tilt)], cam);
              s === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y);
            }
            ctx.stroke();
          }
          ctx.save();
          ctx.fillStyle = '#fff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.font = `italic ${Math.max(11, r * 0.5)}px "Instrument Serif", Georgia, serif`;
          ctx.fillText('mesh', coreP.x, coreP.y + 1);
          ctx.restore();
        },
      });

      screen.length = 0;
      items.forEach(({ p, d, i }) => {
        const r = 0.56 * p.s * easeOutExpo(clamp(born * 1.4 - i * 0.07, 0, 1));
        screen[i] = { x: p.x, y: p.y, r };
        out.push({
          z: p.z,
          draw: () => {
            const f = fog(p.z, cam.dist, 10);
            const sc = STATUS_COLOR[d.status] || '#8b89a8';
            const hot = hoverIdx === i;
            if (!ghost && d.status !== 'Healthy' && d.status !== 'Unavailable' && !reduced) {
              const speed = d.status === 'Critical' ? 1.4 : 0.8;
              const ph = (t * speed + i * 0.3) % 1;
              ctx.strokeStyle = rgba(sc, (1 - ph) * 0.7 * f);
              ctx.lineWidth = 2.2;
              ctx.beginPath(); ctx.arc(p.x, p.y, r * (1.15 + ph * 1.1), 0, Math.PI * 2); ctx.stroke();
            }
            drawPearl(ctx, p.x, p.y, r * (hot ? 1.12 : 1), d.color, ghost ? 0.35 : Math.max(0.6, f), {
              glow: 2.4, glowAlpha: ghost ? 0.1 : 0.26,
              hollow: false,
            });
            if (!ghost) {
              // status ring + dot
              ctx.strokeStyle = rgba(sc, 0.95 * f);
              ctx.lineWidth = d.status === 'Critical' ? 3 : 2.2;
              ctx.beginPath(); ctx.arc(p.x, p.y, r + 6, 0, Math.PI * 2); ctx.stroke();
              ctx.fillStyle = sc;
              ctx.strokeStyle = '#fff';
              ctx.lineWidth = 2;
              ctx.beginPath(); ctx.arc(p.x + r * 0.78, p.y - r * 0.78, 5.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
              text(getServiceLabel(d.name), p.x, p.y + r + 22, 11, 700, '#15132b', f);
              text(`${d.ev} ev · ${d.an} anom`, p.x, p.y + r + 37, 9.5, 500, '#7f7da1', f * 0.95);
            }
          },
        });
      });
      out.sort((a, b) => b.z - a.z).forEach((o) => o.draw());
    };

    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      canvas.removeEventListener('pointerdown', onDown);
      canvas.removeEventListener('pointermove', onMove);
      canvas.removeEventListener('pointerup', onUp);
      canvas.removeEventListener('pointercancel', onUp);
      canvas.removeEventListener('pointerleave', onLeave);
    };
  }, [visible]);

  const hovered = tip ? services[tip.i] : null;

  return (
    <div ref={hostRef} className="orbit-host">
      <canvas ref={canvasRef} className="orbit-canvas" aria-label="3D orbit of tracked services" role="img" />
      {services.length === 0 && (
        <div className="orbit-empty">
          {loading ? (
            <>
              <span className="live-dot warn" /> Reading the mesh…
            </>
          ) : (
            <>
              <b>Awaiting a trace</b>
              <span>Load a scenario to light up the services.</span>
            </>
          )}
        </div>
      )}
      {hovered && tip && (
        <div className="orbit-tip" style={{ left: tip.x + 16, top: tip.y + 14 }}>
          <div className="row" style={{ gap: 8, marginBottom: 6 }}>
            <span className="svc-tag" style={{ ['--c' as any]: getServiceColor(hovered.service_name) }}>
              {getServiceLabel(hovered.service_name)}
            </span>
            <span className={`chip lower chip-${hovered.status === 'Healthy' ? 'ok' : hovered.status === 'Degraded' ? 'warn' : hovered.status === 'Critical' ? 'crit' : ''}`}>
              {hovered.status}
            </span>
          </div>
          <div className="orbit-tip-grid">
            <span>Events</span><b>{hovered.event_count}</b>
            <span>Anomalies</span><b>{hovered.anomaly_count}</b>
            <span>Avg latency</span><b>{hovered.avg_latency_ms !== null ? `${hovered.avg_latency_ms} ms` : 'n/a'}</b>
          </div>
        </div>
      )}
      <div className="orbit-hint"><span>drag to orbit</span></div>
    </div>
  );
};
