/**
 * ChronosMesh — Centralized API Service Layer
 * Author: Guru Sai Prasad Reddy
 * Conforms to Stage 2 docs/API_CONTRACT.md and docs/FRONTEND_DATA_CONTRACT.md
 */

import {
  AuthResponse,
  SystemMetrics,
  Scenario,
  DAGData,
  Event,
  AnomalyReport,
  ConfidenceReport,
  RootCauseResult,
  WhatIfResult,
  BenchmarkReport,
  User,
  DAGNode,
  ServiceHealthReport,
  ClockDriftTimeline,
  LatencyHistogramReport,
  TopologyStatsReport,
  EventReplayReport,
  GraphDiffReport,
} from '../types';

const getApiBase = (): string => {
  if (typeof window !== 'undefined') {
    if (window.location.port === '3000' || window.location.port === '5173') {
      return `http://${window.location.hostname}:8000`;
    }
    return '';
  }
  return 'http://localhost:8000';
};

const API_BASE = getApiBase();

class ApiService {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined' && window.localStorage) {
      this.token = localStorage.getItem('cm_token');
    }
  }

  public setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined' && window.localStorage) {
      if (token) {
        localStorage.setItem('cm_token', token);
      } else {
        localStorage.removeItem('cm_token');
      }
    }
  }

  public getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== 'undefined' && window.localStorage) {
      return localStorage.getItem('cm_token');
    }
    return null;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    const currentToken = this.getToken();
    if (currentToken && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${currentToken}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.setToken(null);
      localStorage.removeItem('cm_user');
      window.dispatchEvent(new CustomEvent('auth:expired'));
      throw new Error('Authentication expired. Please log in again.');
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Request failed with status ${response.status}`);
    }

    return response.json() as Promise<T>;
  }

  // ── Authentication ──────────────────────────────────────────────────────────
  async login(username: string, password: string): Promise<AuthResponse> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid username or password');
    }

    const data: AuthResponse = await response.json();
    this.setToken(data.access_token);
    localStorage.setItem('cm_user', JSON.stringify(data.user));
    return data;
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  logout() {
    this.setToken(null);
    if (typeof window !== 'undefined') {
      window.localStorage?.removeItem('cm_user');
      window.dispatchEvent(new CustomEvent('auth:logout'));
    }
  }

  // ── System ──────────────────────────────────────────────────────────────────
  async getHealth(): Promise<{ status: string; service: string; version: string }> {
    return this.request('/api/health');
  }

  async getMetrics(): Promise<SystemMetrics> {
    return this.request('/api/metrics');
  }

  // ── Scenarios / Traces ───────────────────────────────────────────────────────
  async getScenarios(): Promise<Scenario[]> {
    return this.request<Scenario[]>('/api/scenarios/');
  }

  async getTraces(): Promise<Scenario[]> {
    return this.request<Scenario[]>('/api/traces/');
  }

  async loadScenario(nameOrTraceId: string): Promise<{
    scenario: Scenario;
    dag: DAGData;
    arrival_order: Event[];
    causal_order: Event[];
    event_count: number;
  }> {
    return this.request(`/api/scenarios/${encodeURIComponent(nameOrTraceId)}/load`, {
      method: 'POST',
    });
  }

  async clearStore(): Promise<{ message: string }> {
    return this.request('/api/scenarios/', { method: 'DELETE' });
  }

  // ── Events ──────────────────────────────────────────────────────────────────
  async getEvents(): Promise<{ events: Event[]; count: number; scenario: string | null }> {
    return this.request('/api/events/');
  }

  async getArrivalEvents(): Promise<{ events: Event[]; count: number; scenario: string | null }> {
    return this.request('/api/events/arrival');
  }

  async getCausalEvents(): Promise<{ events: Event[]; count: number; topological_order: string[] }> {
    return this.request('/api/events/causal');
  }

  async getEvent(eventId: string): Promise<Event> {
    return this.request(`/api/events/${encodeURIComponent(eventId)}`);
  }

  // ── Causal DAG ──────────────────────────────────────────────────────────────
  async getDag(): Promise<DAGData> {
    return this.request<DAGData>('/api/dag/');
  }

  async getRoots(): Promise<{ roots: DAGNode[] }> {
    return this.request('/api/dag/roots');
  }

  async getLeaves(): Promise<{ leaves: DAGNode[] }> {
    return this.request('/api/dag/leaves');
  }

  async getAncestors(eventId: string): Promise<{ event_id: string; ancestors: DAGNode[]; count: number }> {
    return this.request(`/api/dag/ancestors/${encodeURIComponent(eventId)}`);
  }

  async getDescendants(eventId: string): Promise<{ event_id: string; descendants: DAGNode[]; count: number }> {
    return this.request(`/api/dag/descendants/${encodeURIComponent(eventId)}`);
  }

  // ── Analysis ────────────────────────────────────────────────────────────────
  async getAnomalies(): Promise<AnomalyReport> {
    return this.request<AnomalyReport>('/api/analysis/anomalies');
  }

  async getConfidence(): Promise<ConfidenceReport> {
    return this.request<ConfidenceReport>('/api/analysis/confidence');
  }

  async getRootCause(eventId: string): Promise<RootCauseResult> {
    return this.request<RootCauseResult>(`/api/analysis/rootcause/${encodeURIComponent(eventId)}`);
  }

  async runWhatIf(eventId: string): Promise<WhatIfResult> {
    return this.request<WhatIfResult>(`/api/analysis/whatif/${encodeURIComponent(eventId)}`, {
      method: 'POST',
    });
  }

  async getBenchmark(packetLossPct: number = 0, clockDriftMs: number = 0): Promise<BenchmarkReport> {
    return this.request<BenchmarkReport>(
      `/api/analysis/benchmark?packet_loss_pct=${packetLossPct}&clock_drift_ms=${clockDriftMs}`
    );
  }

  async getGraphDiff(): Promise<GraphDiffReport> {
    return this.request<GraphDiffReport>('/api/analysis/graphdiff');
  }

  async getServiceHealth(): Promise<ServiceHealthReport> {
    return this.request<ServiceHealthReport>('/api/analysis/service-health');
  }

  async getClockDriftTimeline(skewToleranceMs: number = 50.0): Promise<ClockDriftTimeline> {
    return this.request<ClockDriftTimeline>(
      `/api/analysis/clock-drift-timeline?skew_tolerance_ms=${skewToleranceMs}`
    );
  }

  async getLatencyHistogram(bins: number = 5): Promise<LatencyHistogramReport> {
    return this.request<LatencyHistogramReport>(`/api/analysis/latency-histogram?bins=${bins}`);
  }

  async getTopologyStats(): Promise<TopologyStatsReport> {
    return this.request<TopologyStatsReport>('/api/analysis/topology-stats');
  }

  async getEventReplay(): Promise<EventReplayReport> {
    return this.request<EventReplayReport>('/api/analysis/event-replay');
  }

  // ── SSE Live Event Stream ───────────────────────────────────────────────────
  createEventSource(): EventSource {
    const token = this.getToken();
    const url = token
      ? `${API_BASE}/api/events/stream?token=${encodeURIComponent(token)}`
      : `${API_BASE}/api/events/stream`;
    return new EventSource(url);
  }
}

export const api = new ApiService();
export default api;
