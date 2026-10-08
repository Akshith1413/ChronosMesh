import { describe, it, expect } from 'vitest';
import { ServiceHealthReport, LatencyHistogramReport, TopologyStatsReport, EventReplayReport } from '../types';

describe('Advanced Observability & Analysis Types & Contracts', () => {
  it('correctly models ServiceHealthReport structure', () => {
    const report: ServiceHealthReport = {
      services: [
        {
          service_name: 'order-svc',
          status: 'Healthy',
          event_count: 5,
          anomaly_count: 0,
          latest_activity_ms: 1711929600000,
          avg_latency_ms: 45.2,
          details: { critical_anomalies: 0, warning_anomalies: 0 },
        },
        {
          service_name: 'payment-svc',
          status: 'Degraded',
          event_count: 3,
          anomaly_count: 1,
          latest_activity_ms: 1711929650000,
          avg_latency_ms: 120.5,
          details: { critical_anomalies: 0, warning_anomalies: 1 },
        },
      ],
      total_services: 2,
      healthy_count: 1,
      degraded_count: 1,
      critical_count: 0,
      unavailable_count: 0,
      timestamp_ms: 1711929700000,
    };

    expect(report.total_services).toBe(2);
    expect(report.healthy_count).toBe(1);
    expect(report.services[0].status).toBe('Healthy');
    expect(report.services[1].status).toBe('Degraded');
  });

  it('correctly models LatencyHistogramReport with percentiles', () => {
    const report: LatencyHistogramReport = {
      sample_size: 10,
      p50_ms: 32.5,
      p95_ms: 88.0,
      p99_ms: 95.0,
      min_ms: 12.0,
      max_ms: 98.0,
      mean_ms: 42.1,
      bins: [
        { bin_start_ms: 10.0, bin_end_ms: 50.0, count: 7 },
        { bin_start_ms: 50.0, bin_end_ms: 100.0, count: 3 },
      ],
      inversion_edge_count: 0,
      note: null,
    };

    expect(report.sample_size).toBe(10);
    expect(report.p50_ms).toBe(32.5);
    expect(report.bins.reduce((acc, b) => acc + b.count, 0)).toBe(10);
  });

  it('correctly models TopologyStatsReport and critical paths', () => {
    const report: TopologyStatsReport = {
      node_count: 6,
      edge_count: 5,
      density: 0.1667,
      is_connected: true,
      connected_components: 1,
      root_nodes: ['E1'],
      leaf_nodes: ['E6'],
      longest_causal_path: {
        length: 4,
        path: ['E1', 'E2', 'E4', 'E6'],
        duration_ms: 250.0,
      },
      coupling_metric: 1.667,
      concurrency_pairs_count: 3,
      concurrency_ratio: 0.2,
    };

    expect(report.node_count).toBe(6);
    expect(report.longest_causal_path.path).toContain('E1');
    expect(report.longest_causal_path.path).toContain('E6');
    expect(report.concurrency_pairs_count).toBe(3);
  });

  it('correctly models EventReplayReport causal layers', () => {
    const report: EventReplayReport = {
      total_layers: 3,
      total_events: 5,
      max_parallelism: 2,
      layers: [
        {
          layer_index: 1,
          events: [
            {
              event_id: 'E1',
              service_id: 'order-svc',
              event_type: 'ORDER_CREATED',
              timestamp_ms: 1000,
              lamport_ts: 1,
              parents: [],
            },
          ],
          concurrent_count: 1,
        },
        {
          layer_index: 2,
          events: [
            {
              event_id: 'E2',
              service_id: 'payment-svc',
              event_type: 'PAYMENT_PROCESSED',
              timestamp_ms: 1050,
              lamport_ts: 2,
              parents: ['E1'],
            },
            {
              event_id: 'E3',
              service_id: 'inventory-svc',
              event_type: 'STOCK_RESERVED',
              timestamp_ms: 1060,
              lamport_ts: 2,
              parents: ['E1'],
            },
          ],
          concurrent_count: 2,
        },
      ],
    };

    expect(report.total_layers).toBe(3);
    expect(report.layers[1].concurrent_count).toBe(2);
    expect(report.layers[1].events.map((e) => e.event_id)).toEqual(['E2', 'E3']);
  });
});
