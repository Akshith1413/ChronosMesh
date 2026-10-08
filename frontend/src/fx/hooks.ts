/**
 * ChronosMesh — interaction primitives (tilt, magnetic, count-up, in-view, ripple)
 * All pointer-driven effects write CSS variables directly so React never re-renders.
 */
import { useEffect, useRef, useState } from 'react';

export const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const isTouchOnly = (): boolean =>
  typeof window !== 'undefined' && window.matchMedia?.('(hover: none)').matches;

/** 3D tilt + glare + spotlight border. Attach the returned ref to any element with class "tilt". */
export function useTilt<T extends HTMLElement = HTMLDivElement>(max = 7) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || isTouchOnly()) return;
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.setProperty('--rx', `${((0.5 - py) * max * 2).toFixed(2)}deg`);
        el.style.setProperty('--ry', `${((px - 0.5) * max * 2).toFixed(2)}deg`);
        el.style.setProperty('--gx', `${(px * 100).toFixed(1)}%`);
        el.style.setProperty('--gy', `${(py * 100).toFixed(1)}%`);
        el.style.setProperty('--glare', '1');
      });
    };
    const onLeave = () => {
      cancelAnimationFrame(raf);
      el.style.setProperty('--rx', '0deg');
      el.style.setProperty('--ry', '0deg');
      el.style.setProperty('--glare', '0');
    };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
    };
  }, [max]);
  return ref;
}

/** Elements drift toward the cursor when it is near. */
export function useMagnetic<T extends HTMLElement = HTMLElement>(strength = 0.32, radius = 90) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || isTouchOnly()) return;
    let raf = 0;
    let active = false;
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const dx = e.clientX - cx;
        const dy = e.clientY - cy;
        const dist = Math.hypot(dx, dy);
        const reach = Math.max(r.width, r.height) / 2 + radius;
        if (dist < reach) {
          active = true;
          el.style.transition = 'transform 0.18s ease-out';
          el.style.transform = `translate(${(dx * strength).toFixed(1)}px, ${(dy * strength).toFixed(1)}px)`;
        } else if (active) {
          active = false;
          el.style.transition = 'transform 0.7s cubic-bezier(0.34,1.56,0.64,1)';
          el.style.transform = '';
        }
      });
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onMove);
      el.style.transform = '';
    };
  }, [strength, radius]);
  return ref;
}

/** Animated number — eases from the previously displayed value to the new target. */
export function useCountUp(target: number, duration = 1100, decimals = 0): string {
  const [display, setDisplay] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (!Number.isFinite(target)) return;
    if (prefersReducedMotion()) {
      setDisplay(target);
      from.current = target;
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 4);
      const v = origin + (target - origin) * eased;
      setDisplay(v);
      from.current = v;
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return display.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** True once the element has scrolled into view. */
export function useInView<T extends HTMLElement = HTMLDivElement>(threshold = 0.18, once = true) {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          if (once) io.disconnect();
        } else if (!once) {
          setSeen(false);
        }
      },
      { threshold, rootMargin: '0px 0px -6% 0px' }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold, once]);
  return [ref, seen] as const;
}

/** Tracks whether a canvas host is visible so render loops can pause off-screen. */
export function useVisibility<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const visible = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => (visible.current = e.isIntersecting), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return { ref, visible };
}

/** Global pointer position -> CSS vars for the aurora spotlight. */
export function initPointerSpotlight() {
  if (typeof window === 'undefined' || prefersReducedMotion()) return () => {};
  let raf = 0;
  const root = document.documentElement;
  const onMove = (e: PointerEvent) => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      root.style.setProperty('--mx', `${e.clientX}px`);
      root.style.setProperty('--my', `${e.clientY}px`);
    });
  };
  window.addEventListener('pointermove', onMove, { passive: true });
  return () => window.removeEventListener('pointermove', onMove);
}

/** Delegated click ripple for anything with .btn or .rip */
export function initRipple() {
  if (typeof document === 'undefined') return () => {};
  const onDown = (e: PointerEvent) => {
    const host = (e.target as HTMLElement | null)?.closest?.('.btn, .rip') as HTMLElement | null;
    if (!host || (host as HTMLButtonElement).disabled) return;
    const r = host.getBoundingClientRect();
    const size = Math.max(r.width, r.height) * 2.2;
    const wave = document.createElement('span');
    wave.className = 'rip-wave';
    wave.style.width = wave.style.height = `${size}px`;
    wave.style.left = `${e.clientX - r.left - size / 2}px`;
    wave.style.top = `${e.clientY - r.top - size / 2}px`;
    host.appendChild(wave);
    wave.addEventListener('animationend', () => wave.remove());
  };
  document.addEventListener('pointerdown', onDown);
  return () => document.removeEventListener('pointerdown', onDown);
}
