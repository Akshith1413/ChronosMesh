import { describe, it, expect } from 'vitest';
import {
  ANOMALY_BLURBS, APPROACHES, DEFAULT_PARAMS, PRESETS, applyPreset, chartSeries, clampToLimits,
  formatCI, formatRate, isTerminal, pct, statusChip, validateParams,
} from '../utils/experiments';
import type { CI, ExperimentOptions } from '../types';

const OPTIONS: ExperimentOptions = {
  limits: {
    num_services: [2, 50], num_events: [10, 100000], events_per_execution: [5, 100000], network_delay_ms: [0, 2000],
    duplicate_rate: [0, 0.1], missing_rate: [0, 0.05], clock_drift_ms: [0, 5000], metadata_loss_rate: [0, 1],
    worker_failures: [0, 10], repeats: [1, 30], retry_rate: [0, 0.1], retry_burst: [2, 20], cross_region_delay_ms: [0, 2000],
  },
  delivery_modes: ['in_order', 'randomized', 'heavily_delayed'],
  transports: ['direct'],
  max_experiment_events: 20000,
  defaults: DEFAULT_PARAMS,
  approaches: ['arrival_order', 'wall_clock', 'declared_only', 'chronosmesh'],
};

const ci = (mean: number, half = 0, n = 3): CI => ({ mean, std: 0, ci95_low: mean - half, ci95_high: mean + half, n });

describe('presets', () => {
  it('every preset yields parameters the server would accept', () => {
    for (const p of PRESETS) {
      const params = clampToLimits(applyPreset(DEFAULT_PARAMS, p), OPTIONS);
      expect(validateParams(params, OPTIONS), p.id).toEqual([]);
    }
  });

  it('applying a preset resets unrelated knobs but keeps the seed and transport', () => {
    const dirty = { ...DEFAULT_PARAMS, seed: 7, transport: 'sqs' as const, missing_rate: 0.05, clock_drift_ms: 900 };
    const out = applyPreset(dirty, PRESETS.find((p) => p.id === 'lossy')!);
    expect(out.seed).toBe(7);
    expect(out.transport).toBe('sqs');
    expect(out.missing_rate).toBe(0);
    expect(out.metadata_loss_rate).toBe(0.3);
  });
});

describe('parameter validation', () => {
  it('clamps values into the published ranges and the deployment event cap', () => {
    const out = clampToLimits({ ...DEFAULT_PARAMS, num_events: 99999, duplicate_rate: 0.5, num_services: 1, events_per_execution: 50000 }, OPTIONS);
    expect(out.num_events).toBe(20000);
    expect(out.duplicate_rate).toBe(0.1);
    expect(out.num_services).toBe(2);
    expect(out.events_per_execution).toBeLessThanOrEqual(out.num_events);
  });

  it('reports every violated constraint', () => {
    const errs = validateParams({ ...DEFAULT_PARAMS, missing_rate: 0.2, num_events: 50000, transport: 'sqs', repeats: 3, delivery_mode: 'chaotic' as any }, OPTIONS);
    expect(errs.join(' | ')).toMatch(/missing_rate/);
    expect(errs.join(' | ')).toMatch(/limited to 20000/);
    expect(errs.join(' | ')).toMatch(/single repeat/);
    expect(errs.join(' | ')).toMatch(/delivery mode/);
  });

  it('is permissive until the options have loaded', () => {
    expect(validateParams({ ...DEFAULT_PARAMS, missing_rate: 9 }, null)).toEqual([]);
  });
});

describe('formatting', () => {
  it('formats confidence intervals as mean ± half-width and omits it for one sample', () => {
    expect(formatCI(ci(0.9876, 0.0042))).toBe('0.988 ± 0.004');
    expect(formatCI(ci(0.5, 0, 1))).toBe('0.500');
    expect(formatCI(undefined)).toBe('—');
    expect(formatCI({ ...ci(NaN), mean: NaN })).toBe('—');
  });

  it('formats percentages and rates defensively', () => {
    expect(pct(0.1234)).toBe('12.3%');
    expect(pct(1, 0)).toBe('100%');
    expect(pct(null)).toBe('—');
    expect(formatRate(5242.7)).toBe('5.2k ev/s');
    expect(formatRate(312.4)).toBe('312 ev/s');
    expect(formatRate(null)).toBe('—');
  });

  it('maps every status to a chip and knows which are terminal', () => {
    expect(statusChip('succeeded').cls).toBe('chip-ok');
    expect(statusChip('failed').cls).toBe('chip-crit');
    expect(statusChip('streaming').label).toBe('Streaming');
    expect(isTerminal('succeeded') && isTerminal('failed')).toBe(true);
    expect(['created', 'queued', 'running', 'streaming'].some((s) => isTerminal(s as any))).toBe(false);
  });
});

describe('chart series', () => {
  const summary: any = Object.fromEntries(APPROACHES.map((a, i) => [a.key, {
    precision: ci(0.1 * (i + 1)), recall: ci(0.2 * (i + 1)), f1: ci(0.9, 0.05),
  }]));

  it('returns one bar per approach in presentation order with CI bounds', () => {
    const s = chartSeries(summary, 'f1');
    expect(s.map((x) => x.key)).toEqual(['arrival_order', 'wall_clock', 'declared_only', 'chronosmesh']);
    expect(s[3].value).toBeCloseTo(0.9);
    expect(s[3].low).toBeCloseTo(0.85);
    expect(s[3].high).toBeCloseTo(0.95);
  });

  it('survives a missing approach', () => {
    const s = chartSeries({ chronosmesh: summary.chronosmesh } as any, 'precision');
    expect(s).toHaveLength(4);
    expect(s[0].value).toBe(0);
  });
});

describe('anomaly vocabulary', () => {
  it('documents every anomaly type the engine can emit', () => {
    const emitted = ['CYCLE', 'CAUSAL_VIOLATION', 'CLOCK_DRIFT', 'TIME_INVERSION', 'DUPLICATE_EVENT', 'UNRESOLVED_PARENT',
      'ORPHAN_EVENT', 'VECTOR_CLOCK_GAP', 'CONCURRENT_MUTATION', 'RETRY_STORM', 'LATE_ARRIVAL'];
    for (const t of emitted) expect(ANOMALY_BLURBS[t], t).toBeTruthy();
  });
});
