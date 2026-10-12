/**
 * ChronosMesh — Experiment Lab helpers (pure functions, unit-tested).
 */
import type { ApproachKey, CI, ExperimentOptions, ExperimentParams, ExecutionStatus } from '../types';
import { PALETTE } from './colors';

export const APPROACHES: { key: ApproachKey; label: string; color: string; blurb: string }[] = [
  { key: 'arrival_order', label: 'Arrival order', color: PALETTE.mute, blurb: 'Treats the order events reached the platform as the execution order.' },
  { key: 'wall_clock', label: 'Wall clock', color: PALETTE.warn, blurb: 'Sorts by each service\'s local timestamp (breaks under clock drift).' },
  { key: 'declared_only', label: 'Declared parents', color: PALETTE.iris2, blurb: 'Trusts OpenTelemetry-style parent links, no logical clocks.' },
  { key: 'chronosmesh', label: 'ChronosMesh', color: PALETTE.iris1, blurb: 'Vector clocks + verified parent links, with gaps bridged and unresolved parents reported.' },
];

export const DEFAULT_PARAMS: ExperimentParams = {
  name: 'experiment',
  num_services: 4,
  num_events: 1000,
  events_per_execution: 20,
  network_delay_ms: 200,
  duplicate_rate: 0,
  missing_rate: 0,
  clock_drift_ms: 0,
  cross_region_delay_ms: 0,
  metadata_loss_rate: 0,
  retry_rate: 0,
  retry_burst: 6,
  delivery_mode: 'randomized',
  worker_failures: 0,
  repeats: 1,
  seed: 42,
  transport: 'direct',
  branching: 0.7,
};

export interface Preset {
  id: string;
  label: string;
  description: string;
  params: Partial<ExperimentParams>;
}

export const PRESETS: Preset[] = [
  { id: 'baseline', label: 'Out-of-order only', description: 'Random delivery delay, nothing else.', params: { name: 'Out-of-order delivery', network_delay_ms: 400, delivery_mode: 'randomized' } },
  { id: 'chaos', label: 'Multi-cloud chaos', description: 'Heavy-tailed latency, 100 ms clock drift, 5 % duplicates, 2 % lost events.', params: { name: 'Multi-cloud chaos', network_delay_ms: 500, delivery_mode: 'heavily_delayed', clock_drift_ms: 100, cross_region_delay_ms: 300, duplicate_rate: 0.05, missing_rate: 0.02, num_services: 10 } },
  { id: 'lossy', label: 'Lossy metadata', description: '30 % of events lose their vector clock (un-instrumented hops).', params: { name: 'Lossy metadata', metadata_loss_rate: 0.3, network_delay_ms: 300 } },
  { id: 'retries', label: 'Retry storm', description: '5 % of operations are retried in bursts of 6 (a retry storm).', params: { name: 'Retry storm', retry_rate: 0.05, retry_burst: 6, network_delay_ms: 300 } },
  { id: 'crashes', label: 'Worker crashes', description: 'Three worker crash/restarts with at-least-once redelivery.', params: { name: 'Worker crashes', worker_failures: 3, duplicate_rate: 0.05 } },
  { id: 'scale', label: 'Scale-out', description: '25 services, 10 000 events, 3 repeats with confidence intervals.', params: { name: 'Scale-out', num_services: 25, num_events: 10000, repeats: 3, network_delay_ms: 500 } },
];

export function applyPreset(base: ExperimentParams, preset: Preset): ExperimentParams {
  return { ...DEFAULT_PARAMS, seed: base.seed, transport: base.transport, ...preset.params };
}

/** Clamp every numeric parameter into the server's published range. */
export function clampToLimits(p: ExperimentParams, opts: ExperimentOptions | null): ExperimentParams {
  if (!opts) return p;
  const out: any = { ...p };
  for (const [key, [lo, hi]] of Object.entries(opts.limits)) {
    if (typeof out[key] === 'number') out[key] = Math.min(hi, Math.max(lo, out[key]));
  }
  out.num_events = Math.min(out.num_events, opts.max_experiment_events);
  out.events_per_execution = Math.min(out.events_per_execution, out.num_events);
  return out as ExperimentParams;
}

export function validateParams(p: ExperimentParams, opts: ExperimentOptions | null): string[] {
  const errors: string[] = [];
  if (!opts) return errors;
  for (const [key, [lo, hi]] of Object.entries(opts.limits)) {
    const v = (p as any)[key];
    if (typeof v === 'number' && (v < lo || v > hi)) errors.push(`${key} must be between ${lo} and ${hi}`);
  }
  if (p.num_events > opts.max_experiment_events) errors.push(`num_events is limited to ${opts.max_experiment_events} on this deployment`);
  if (p.transport === 'sqs' && p.repeats !== 1) errors.push('queue transport supports a single repeat');
  if (!opts.delivery_modes.includes(p.delivery_mode)) errors.push(`unknown delivery mode ${p.delivery_mode}`);
  return errors;
}

export const pct = (x: number | null | undefined, digits = 1): string =>
  x === null || x === undefined || !Number.isFinite(x) ? '—' : `${(x * 100).toFixed(digits)}%`;

/** "0.988 ± 0.004" (95 % CI half-width); single samples show just the mean. */
export function formatCI(ci: CI | undefined, digits = 3): string {
  if (!ci || !Number.isFinite(ci.mean)) return '—';
  if (ci.n <= 1) return ci.mean.toFixed(digits);
  const half = (ci.ci95_high - ci.ci95_low) / 2;
  return `${ci.mean.toFixed(digits)} ± ${half.toFixed(digits)}`;
}

export function formatRate(eps: number | null | undefined): string {
  if (eps === null || eps === undefined || !Number.isFinite(eps)) return '—';
  return eps >= 1000 ? `${(eps / 1000).toFixed(1)}k ev/s` : `${eps.toFixed(0)} ev/s`;
}

export const isTerminal = (s: ExecutionStatus): boolean => s === 'succeeded' || s === 'failed';

export function statusChip(s: ExecutionStatus): { label: string; cls: string } {
  switch (s) {
    case 'succeeded': return { label: 'Completed', cls: 'chip-ok' };
    case 'failed': return { label: 'Failed', cls: 'chip-crit' };
    case 'running': return { label: 'Running', cls: 'chip-iris' };
    case 'streaming': return { label: 'Streaming', cls: 'chip-iris' };
    case 'queued': return { label: 'Queued', cls: 'chip-info' };
    default: return { label: 'Created', cls: 'chip-info' };
  }
}

/** Series for the grouped bar chart: one entry per approach, values in [0, 1]. */
export function chartSeries(
  summary: Record<ApproachKey, { precision: CI; recall: CI; f1: CI }>,
  metric: 'precision' | 'recall' | 'f1',
): { key: ApproachKey; label: string; color: string; value: number; low: number; high: number }[] {
  return APPROACHES.map((a) => {
    const ci = summary[a.key]?.[metric];
    return { key: a.key, label: a.label, color: a.color, value: ci?.mean ?? 0, low: ci?.ci95_low ?? ci?.mean ?? 0, high: ci?.ci95_high ?? ci?.mean ?? 0 };
  });
}

export const ANOMALY_BLURBS: Record<string, string> = {
  CYCLE: 'The reconstructed graph is not acyclic — the metadata is inconsistent.',
  CAUSAL_VIOLATION: 'A declared dependency contradicts the logical clocks.',
  CLOCK_DRIFT: 'Two services\' wall clocks provably disagree beyond tolerance.',
  TIME_INVERSION: 'A causal child carries an older wall-clock time than its parent.',
  DUPLICATE_EVENT: 'The same event id was delivered more than once (ignored after the first).',
  UNRESOLVED_PARENT: 'A declared parent has not been observed — no edge is invented for it.',
  ORPHAN_EVENT: 'Every declared parent is unresolved; the event is causally disconnected.',
  VECTOR_CLOCK_GAP: 'A service\'s own counter skips values: events were lost.',
  CONCURRENT_MUTATION: 'Two services wrote the same resource with no causal order.',
  RETRY_STORM: 'Many retries of the same operation.',
  LATE_ARRIVAL: 'A parent reached the platform after its causal child.',
};
