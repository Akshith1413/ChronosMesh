/**
 * ChronosMesh — tiny 3D engine for canvas scenes.
 * Perspective projection, depth fog and "pearl" rendering tuned for a light theme.
 */

export type V3 = [number, number, number];

export interface Cam {
  yaw: number;
  pitch: number;
  dist: number;
  focal: number;
  cx: number;
  cy: number;
}

export interface P2 {
  x: number;
  y: number;
  s: number;
  z: number;
  vis: boolean;
}

export const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smoothstep = (e0: number, e1: number, x: number) => {
  const t = clamp((x - e0) / (e1 - e0 || 1e-6), 0, 1);
  return t * t * (3 - 2 * t);
};
export const easeInOut = (t: number) => {
  const x = clamp(t, 0, 1);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
export const easeOutExpo = (t: number) => (t >= 1 ? 1 : t <= 0 ? 0 : 1 - Math.pow(2, -10 * t));

/** Deterministic PRNG so scenes look the same on every load. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function rotate(p: V3, yaw: number, pitch: number): V3 {
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const x = p[0] * cy + p[2] * sy;
  let z = -p[0] * sy + p[2] * cy;
  const y = p[1] * cp - z * sp;
  z = p[1] * sp + z * cp;
  return [x, y, z];
}

export function project(p: V3, cam: Cam): P2 {
  const r = rotate(p, cam.yaw, cam.pitch);
  const zc = r[2] + cam.dist;
  if (zc < 0.2) return { x: 0, y: 0, s: 0, z: zc, vis: false };
  const s = cam.focal / zc;
  return { x: cam.cx + r[0] * s, y: cam.cy - r[1] * s, s, z: zc, vis: true };
}

/** 0..1 where 1 is nearest. Used to fog distant geometry into the white backdrop. */
export function fog(z: number, dist: number, spread = 9): number {
  return clamp(1 - (z - (dist - spread * 0.5)) / (spread * 1.6), 0.08, 1);
}

export function hexToRgb(hex: string): [number, number, number] {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export const rgba = (hex: string, a: number) => {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r},${g},${b},${clamp(a, 0, 1).toFixed(3)})`;
};

export function mix(hexA: string, hexB: string, t: number): string {
  const a = hexToRgb(hexA), b = hexToRgb(hexB);
  const c = a.map((v, i) => Math.round(lerp(v, b[i], t)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function shade(hex: string, amt: number): string {
  // amt > 0 lightens toward white, < 0 darkens toward ink
  return amt >= 0 ? mix(hex, '#ffffff', amt) : mix(hex, '#1a1640', -amt);
}

export interface FitResult {
  w: number;
  h: number;
  dpr: number;
}

/** Sizes a canvas to its CSS box at (capped) device pixel ratio. */
export function fitCanvas(canvas: HTMLCanvasElement, maxDpr = 2): FitResult {
  const dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
  const w = Math.max(1, canvas.clientWidth);
  const h = Math.max(1, canvas.clientHeight);
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { w, h, dpr };
}

export interface PearlOpts {
  glow?: number;       // glow radius multiplier (0 = none)
  glowAlpha?: number;
  ring?: string;       // outer ring colour
  ringWidth?: number;
  hollow?: boolean;
}

/** A glassy, lit sphere: soft halo, body gradient, specular highlight and rim light. */
export function drawPearl(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  r: number,
  color: string,
  alpha = 1,
  o: PearlOpts = {}
) {
  if (r < 0.5 || alpha <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = clamp(alpha, 0, 1);

  if (o.glow) {
    const gr = r * o.glow;
    const g = ctx.createRadialGradient(x, y, r * 0.6, x, y, gr);
    g.addColorStop(0, rgba(color, o.glowAlpha ?? 0.28));
    g.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, gr, 0, Math.PI * 2);
    ctx.fill();
  }

  // soft contact shadow
  const sh = ctx.createRadialGradient(x + r * 0.15, y + r * 0.95, 0, x + r * 0.15, y + r * 0.95, r * 1.05);
  sh.addColorStop(0, 'rgba(21,19,43,0.16)');
  sh.addColorStop(1, 'rgba(21,19,43,0)');
  ctx.fillStyle = sh;
  ctx.beginPath();
  ctx.ellipse(x + r * 0.15, y + r * 0.95, r * 1.05, r * 0.32, 0, 0, Math.PI * 2);
  ctx.fill();

  if (o.hollow) {
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(1.5, r * 0.12);
    ctx.setLineDash([r * 0.4, r * 0.3]);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
    return;
  }

  const body = ctx.createRadialGradient(x - r * 0.38, y - r * 0.45, r * 0.05, x - r * 0.1, y - r * 0.1, r * 1.25);
  body.addColorStop(0, shade(color, 0.82));
  body.addColorStop(0.38, shade(color, 0.18));
  body.addColorStop(0.78, color);
  body.addColorStop(1, shade(color, -0.28));
  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();

  // rim light (lower-right crescent)
  const rim = ctx.createRadialGradient(x + r * 0.5, y + r * 0.6, r * 0.2, x + r * 0.5, y + r * 0.6, r * 1.1);
  rim.addColorStop(0, 'rgba(255,255,255,0.0)');
  rim.addColorStop(0.75, 'rgba(255,255,255,0.0)');
  rim.addColorStop(1, 'rgba(255,255,255,0.35)');
  ctx.fillStyle = rim;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();

  // specular
  ctx.fillStyle = 'rgba(255,255,255,0.78)';
  ctx.beginPath();
  ctx.ellipse(x - r * 0.34, y - r * 0.42, r * 0.28, r * 0.17, -0.7, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = 'rgba(255,255,255,0.9)';
  ctx.lineWidth = Math.max(1, r * 0.06);
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.stroke();

  if (o.ring) {
    ctx.strokeStyle = o.ring;
    ctx.lineWidth = o.ringWidth ?? 2;
    ctx.beginPath();
    ctx.arc(x, y, r + 5, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

/** Point on a quadratic bezier. */
export function quad(
  ax: number, ay: number, cx: number, cy: number, bx: number, by: number, t: number
): [number, number] {
  const u = 1 - t;
  return [u * u * ax + 2 * u * t * cx + t * t * bx, u * u * ay + 2 * u * t * cy + t * t * by];
}

/** Draws a gradient line along a quadratic curve. */
export function strokeCurve(
  ctx: CanvasRenderingContext2D,
  ax: number, ay: number, cx: number, cy: number, bx: number, by: number,
  colA: string, colB: string, width: number, alpha: number, dash?: number[]
) {
  if (alpha <= 0.01) return;
  const g = ctx.createLinearGradient(ax, ay, bx, by);
  g.addColorStop(0, rgba(colA, alpha));
  g.addColorStop(1, rgba(colB, alpha));
  ctx.strokeStyle = g;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.setLineDash(dash || []);
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.quadraticCurveTo(cx, cy, bx, by);
  ctx.stroke();
  ctx.setLineDash([]);
}

/** Draws a small glowing travelling pulse. */
export function drawPulse(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, alpha: number) {
  if (alpha <= 0.01) return;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r * 3.4);
  g.addColorStop(0, rgba(color, 0.55 * alpha));
  g.addColorStop(1, rgba(color, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x, y, r * 3.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = `rgba(255,255,255,${0.95 * alpha})`;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = rgba(color, alpha);
  ctx.lineWidth = Math.max(1, r * 0.55);
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.stroke();
}
