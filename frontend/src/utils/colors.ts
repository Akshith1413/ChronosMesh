/**
 * ChronosMesh — Color tokens and style helpers
 * Author: Guru Sai Prasad Reddy
 *
 * All values are concrete hex colours (not CSS variables) so callers can safely
 * derive alpha variants (`${color}20`), feed them to canvas, or build SVG gradients.
 */

export const PALETTE = {
  ink: '#15132b',
  ink2: '#47456a',
  ink3: '#7f7da1',
  ink4: '#b4b2cc',
  iris1: '#6a4cff',
  iris2: '#2f9bff',
  iris3: '#14d1b0',
  ok: '#0fb98a',
  warn: '#f59f00',
  crit: '#f0405f',
  info: '#4c6ef5',
  mute: '#8b89a8',
};

export const SERVICE_COLORS: Record<string, string> = {
  'order-svc': '#4c6ef5',
  'payment-svc': '#0fb98a',
  'inventory-svc': '#f59f00',
  'shipping-svc': '#8f4cf0',
  'notification-svc': '#e64980',
};

export function getServiceColor(serviceId?: string): string {
  if (!serviceId) return PALETTE.mute;
  for (const [key, color] of Object.entries(SERVICE_COLORS)) {
    if (serviceId.toLowerCase().includes(key.split('-')[0])) {
      return color;
    }
  }
  return PALETTE.mute;
}

export function getServiceLabel(serviceId?: string): string {
  if (!serviceId) return 'UNKNOWN';
  return serviceId.replace(/-svc$/i, '').toUpperCase();
}

/** `#rrggbb` + alpha (0..1) -> `rgba(...)`. Falls back to the input for non-hex strings. */
export function withAlpha(color: string, alpha: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export const SEVERITY_COLORS: Record<string, { bg: string; text: string; border: string; icon: string }> = {
  CRITICAL: {
    bg: 'rgba(240, 64, 95, 0.12)',
    text: PALETTE.crit,
    border: 'rgba(240, 64, 95, 0.4)',
    icon: 'alert',
  },
  WARNING: {
    bg: 'rgba(245, 159, 0, 0.14)',
    text: PALETTE.warn,
    border: 'rgba(245, 159, 0, 0.4)',
    icon: 'warning',
  },
  INFO: {
    bg: 'rgba(76, 110, 245, 0.12)',
    text: PALETTE.info,
    border: 'rgba(76, 110, 245, 0.4)',
    icon: 'info',
  },
};

export function getConfidenceBadge(confidence: number): { label: string; color: string; bg: string } {
  if (confidence >= 0.9) {
    return { label: 'High Confidence', color: PALETTE.ok, bg: 'rgba(15, 185, 138, 0.14)' };
  }
  if (confidence >= 0.7) {
    return { label: 'Medium Confidence', color: PALETTE.warn, bg: 'rgba(245, 159, 0, 0.14)' };
  }
  return { label: 'Low Confidence (Uncertain)', color: PALETTE.crit, bg: 'rgba(240, 64, 95, 0.12)' };
}
