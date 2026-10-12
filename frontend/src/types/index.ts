/**
 * ChronosMesh — TypeScript Type Definitions
 * Directly matching Stage 2 Schemas (EVENT_SCHEMA, CAUSAL_DAG_SCHEMA, API_CONTRACT).
 * Author: Guru Sai Prasad Reddy
 */

export interface EventMetadata {
  trace_id?: string;
  span_id?: string;
  parent_span_id?: string;
  region?: string;
  zone?: string;
  cloud_provider?: string;
  clock_uncertainty_ms?: number;
  environment?: string;
  [key: string]: any;
}

export interface Event {
  event_id: string;
  service_id: string;
  event_type: string;
  timestamp_ms: number;
  lamport_ts: number;
  vector_clock: Record<string, number>;
  parent_event_ids: string[];
  payload: Record<string, any>;
  metadata: EventMetadata;
  arrival_time_ms?: number;
  region?: string;
}

export interface DAGNode {
  id: string;
  service_id: string;
  event_type: string;
  timestamp_ms: number;
  lamport_ts: number;
  vector_clock: Record<string, number>;
  region?: string;
  clock_uncertainty_ms?: number;
  parent_event_ids: string[];
}

export interface DAGEdge {
  source: string;
  target: string;
  explicit: boolean;
  confidence?: number;
  method?: string;
}

export interface DAGData {
  nodes: DAGNode[];
  edges: DAGEdge[];
  topological_order: string[];
  roots: string[];
  leaves: string[];
}

export interface Anomaly {
  anomaly_type:
    | 'CYCLE'
    | 'TIME_INVERSION'
    | 'DUPLICATE_EVENT'
    | 'CLOCK_DRIFT'
    | 'CONCURRENT_MUTATION'
    | 'CAUSAL_VIOLATION'
    | 'UNRESOLVED_PARENT'
    | 'ORPHAN_EVENT'
    | 'VECTOR_CLOCK_GAP'
    | 'RETRY_STORM'
    | 'LATE_ARRIVAL';
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  source_event_id?: string;
  target_event_id?: string;
  description: string;
  details?: Record<string, any>;
}

export interface AnomalyReport {
  anomalies: Anomaly[];
  total: number;
  severity_summary: {
    CRITICAL: number;
    WARNING: number;
    INFO: number;
  };
}

export interface RootCauseResult {
  failure_event_id: string;
  root_causes: Array<{
    event_id: string;
    service_id?: string;
    event_type?: string;
    depth: number;
    path: string[];
    confidence: number;
  }>;
  trace_paths: string[][];
  critical_path: string[];
  root_cause_count: number;
}

export interface WhatIfResult {
  removed_event_id: string;
  blast_radius_pct: number;
  cascade_depth: number;
  invalidated_events: string[];
  surviving_events: string[];
  affected_services: string[];
  invalidated_count: number;
}

export interface ClockBenchmarkResult {
  strategy: 'vector_clock' | 'lamport_clock' | 'physical_time';
  accuracy_pct: number;
  memory_kb: number;
  computation_time_ms: number;
  correct_orderings: number;
  total_orderings: number;
  false_positives: number;
  false_negatives: number;
}

export interface BenchmarkReport {
  parameters: {
    packet_loss_pct: number;
    clock_drift_ms: number;
    event_count: number;
  };
  results: ClockBenchmarkResult[];
  winner: string;
}

export interface ConfidenceReport {
  edge_scores: Array<{
    source: string;
    target: string;
    confidence: number;
    method: string;
    uncertainty_ms: number;
  }>;
  low_confidence_edges: Array<{
    source: string;
    target: string;
    confidence: number;
  }>;
  average_confidence: number;
}

export interface Scenario {
  id: string;
  trace_id: string;
  name: string;
  description: string;
  pattern: string;
  expected_nodes: number;
  services: string[];
}

export interface User {
  username: string;
  full_name: string;
  email?: string;
  role: 'admin' | 'analyst' | 'viewer';
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface SystemMetrics {
  event_count: number;
  dag_nodes: number;
  dag_edges: number;
  services_tracked: number;
  current_scenario: string | null;
  api_version: string;
}

// ── New Analysis Models (Strict Typing) ────────────────────────────────────────

export interface ServiceHealthItem {
  service_name: string;
  status: 'Healthy' | 'Degraded' | 'Critical' | 'Unavailable';
  event_count: number;
  anomaly_count: number;
  latest_activity_ms: number | null;
  avg_latency_ms: number | null;
  details: {
    critical_anomalies?: number;
    warning_anomalies?: number;
  };
}

export interface ServiceHealthReport {
  services: ServiceHealthItem[];
  total_services: number;
  healthy_count: number;
  degraded_count: number;
  critical_count: number;
  unavailable_count: number;
  timestamp_ms: number;
}

export interface ClockDriftPoint {
  event_id: string;
  service_id: string;
  timestamp_ms: number;
  arrival_time_ms: number;
  arrival_skew_ms: number;
  causal_skew_ms: number | null;
  is_inversion: boolean;
  clock_type: string;
}

export interface ClockDriftTimeline {
  trace_id: string | null;
  data_points: ClockDriftPoint[];
  max_arrival_skew_ms: number;
  inversion_count: number;
  skew_tolerance_ms: number;
  methodology: string;
}

export interface LatencyBin {
  bin_start_ms: number;
  bin_end_ms: number;
  count: number;
}

export interface LatencyHistogramReport {
  sample_size: number;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  min_ms: number | null;
  max_ms: number | null;
  mean_ms: number | null;
  bins: LatencyBin[];
  inversion_edge_count: number;
  note: string | null;
}

export interface LongestPathInfo {
  length: number;
  path: string[];
  duration_ms: number | null;
}

export interface TopologyStatsReport {
  node_count: number;
  edge_count: number;
  density: number;
  is_connected: boolean;
  connected_components: number;
  root_nodes: string[];
  leaf_nodes: string[];
  longest_causal_path: LongestPathInfo;
  coupling_metric: number;
  concurrency_pairs_count: number;
  concurrency_ratio: number;
}

export interface EventSummary {
  event_id: string;
  service_id: string;
  event_type: string;
  timestamp_ms: number;
  lamport_ts: number;
  parents: string[];
}

export interface ReplayLayer {
  layer_index: number;
  events: EventSummary[];
  concurrent_count: number;
}

export interface EventReplayReport {
  total_layers: number;
  total_events: number;
  max_parallelism: number;
  layers: ReplayLayer[];
}

export interface GraphDiffReport {
  diff: {
    added_nodes?: string[];
    removed_nodes?: string[];
    added_edges?: Array<[string, string]>;
    removed_edges?: Array<[string, string]>;
    summary?: {
      nodes_added: number;
      nodes_removed: number;
      edges_added: number;
      edges_removed: number;
    };
    note?: string;
  };
  scenario: string | null;
}



// ── Experiments, executions and platform status (blueprint §5 API contract) ─────────────
export type ApproachKey = 'arrival_order' | 'wall_clock' | 'declared_only' | 'chronosmesh';
export type ExecutionStatus = 'created' | 'queued' | 'running' | 'streaming' | 'succeeded' | 'failed';

export interface ExperimentParams {
  name: string;
  num_services: number;
  num_events: number;
  events_per_execution: number;
  network_delay_ms: number;
  duplicate_rate: number;
  missing_rate: number;
  clock_drift_ms: number;
  cross_region_delay_ms: number;
  metadata_loss_rate: number;
  retry_rate: number;
  retry_burst: number;
  delivery_mode: 'in_order' | 'randomized' | 'heavily_delayed';
  worker_failures: number;
  repeats: number;
  seed: number;
  transport: 'direct' | 'sqs';
  branching: number;
}

export interface ExperimentOptions {
  limits: Record<string, [number, number]>;
  delivery_modes: string[];
  transports: string[];
  max_experiment_events: number;
  defaults: ExperimentParams;
  approaches: ApproachKey[];
}

export interface CI {
  mean: number;
  std: number;
  ci95_low: number;
  ci95_high: number;
  n: number;
}

export interface ExperimentSummaryBrief {
  f1: Record<ApproachKey, number>;
  precision: Record<ApproachKey, number>;
  recall: Record<ApproachKey, number>;
  concurrency_accuracy: Record<ApproachKey, number>;
  ordering_accuracy: Record<ApproachKey, number>;
  recovery_rate: number;
  throughput_eps: number;
  reconstruction_seconds: number;
  events: number;
  executions: number;
  anomalies: Record<string, number>;
  repeats: number;
}

export interface ExecutionRecord {
  execution_id: string;
  owner: string;
  name: string;
  kind: 'experiment' | 'live' | 'sample';
  status: ExecutionStatus;
  progress: number;
  message?: string;
  error?: string;
  created_at: string;
  created_at_ms: number;
  config?: ExperimentParams;
  summary?: ExperimentSummaryBrief;
  samples?: string[];
  parent_id?: string;
  duration_seconds?: number;
  stats?: Record<string, number>;
  anomalies?: { total: number; by_type: Record<string, number>; by_severity: Record<string, number> };
}

export interface RunResult {
  seed: number;
  executions: number;
  events_generated: number;
  events_delivered_unique: number;
  deliveries_total: number;
  events_dropped: number;
  events_duplicated: number;
  events_metadata_lost: number;
  arrival_disorder: number;
  truth_edges: number;
  approaches: Record<ApproachKey, { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number; edges: number }>;
  concurrency: Record<ApproachKey, { accuracy: number; concurrent_precision: number; concurrent_recall: number; pairs_evaluated: number; ordering_accuracy: number }>;
  late_event_recovery: Record<ApproachKey, number | null>;
  late_edges: number;
  performance: { reconstruction_seconds: number; throughput_eps: number | null; cpu_seconds: number; peak_rss_mb: number };
  fault_tolerance: {
    worker_crashes_injected: number;
    recoveries: number;
    redelivered_messages: number;
    duplicates_suppressed: number;
    duplicate_detection_rate: number | null;
    state_consistent_after_recovery: boolean;
  };
  anomalies: { total: number; by_type: Record<string, number> };
  reconstruction: Record<string, number>;
}

export interface ExperimentResult {
  config: ExperimentParams;
  runs: RunResult[];
  transport?: string;
  summary: {
    approaches: Record<ApproachKey, { precision: CI; recall: CI; f1: CI }>;
    concurrency: Record<ApproachKey, { accuracy: CI; concurrent_precision: CI; concurrent_recall: CI }>;
    ordering: Record<ApproachKey, CI>;
    late_event_recovery: Record<ApproachKey, CI>;
    duplicate_detection_rate: CI | null;
    performance: Record<'reconstruction_seconds' | 'throughput_eps' | 'cpu_seconds' | 'peak_rss_mb', CI>;
    recovery_rate: number;
    recovery_f1_threshold: number;
    duplicates_suppressed_total: number;
    all_recoveries_consistent: boolean;
  };
}

export interface ExecutionGraph extends DAGData {
  execution_id: string;
  unresolved: Record<string, string[]>;
  truncated: boolean;
  total_nodes: number;
  total_edges: number;
  status?: ExecutionStatus;
}

export interface SystemStatus {
  environment: string;
  storage: { backend: string; ok: boolean; table?: string; bucket?: string; error?: string };
  ingest_mode: 'inline' | 'queue';
  queue: { queue: string; visible?: number; in_flight?: number; delayed?: number; oldest_message_age_seconds?: number | null } | null;
  worker: { status: 'healthy' | 'down' | 'unknown'; last_heartbeat_age_seconds: number | null } | null;
  limits: { max_experiment_events: number; max_execution_events: number; max_ingest_batch: number };
  grafana_url: string | null;
  links: { grafana: string | null; cloudwatch: string | null; xray: string | null };
  tracing: boolean;
  cached_engines: number;
}
