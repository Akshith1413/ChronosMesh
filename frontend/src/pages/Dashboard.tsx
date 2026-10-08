import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { MetricCard } from '../components/MetricCard';
import { ServiceHealthMap } from '../components/ServiceHealthMap';
import { ServiceOrbit } from '../components/scenes/ServiceOrbit';
import { PatternGlyph } from '../components/PatternGlyph';
import { Loader, EmptyState } from '../components/LoadingState';
import { Icon } from '../components/Icon';
import { Tilt } from '../fx/Reveal';
import { useCountUp } from '../fx/hooks';
import { SystemMetrics, Event, Scenario, ServiceHealthReport, LatencyHistogramReport, AnomalyReport } from '../types';
import { getServiceColor, getServiceLabel, PALETTE } from '../utils/colors';
import api from '../services/api';

interface DashboardPageProps {
  metrics: SystemMetrics | null;
  scenarios: Scenario[];
  currentScenario: string | null;
  events: Event[];
  liveEvents: Event[];
  onLoadScenario: (scenarioId: string) => void;
  onNavigateToDag: () => void;
  loading: boolean;
  anomalyReport?: AnomalyReport | null;
}

const Ms: React.FC<{ v: number | null; color: string; label: string }> = ({ v, color, label }) => {
  const shown = useCountUp(v ?? 0, 900, 1);
  return (
    <div className="lat-tile">
      <span>{label}</span>
      <b className="num" style={{ color }}>{v !== null ? shown : 'N/A'}{v !== null && <small> ms</small>}</b>
    </div>
  );
};

/** A min→max track with p50 / p95 markers placed by real measured values. */
const LatencyBand: React.FC<{ d: LatencyHistogramReport }> = ({ d }) => {
  if (d.min_ms === null || d.max_ms === null || d.max_ms <= d.min_ms) return null;
  const span = d.max_ms - d.min_ms;
  const pos = (v: number | null) => (v === null ? null : Math.min(100, Math.max(0, ((v - d.min_ms!) / span) * 100)));
  const marks = [
    { k: 'min', v: d.min_ms, c: PALETTE.ok },
    { k: 'p50', v: d.p50_ms, c: PALETTE.iris1 },
    { k: 'p95', v: d.p95_ms, c: PALETTE.warn },
    { k: 'max', v: d.max_ms, c: PALETTE.crit },
  ];
  return (
    <div className="lat-band">
      <div className="lat-track"><i style={{ background: `linear-gradient(90deg, ${PALETTE.ok}, ${PALETTE.iris2} 55%, ${PALETTE.crit})` }} /></div>
      {marks.map((m) => {
        const p = pos(m.v);
        return p === null ? null : (
          <span key={m.k} className="lat-mark" style={{ left: `${p}%`, ['--c' as any]: m.c }}>
            <em>{m.k}</em>
          </span>
        );
      })}
    </div>
  );
};

export const DashboardPage: React.FC<DashboardPageProps> = ({
  metrics,
  scenarios,
  currentScenario,
  events,
  liveEvents,
  onLoadScenario,
  onNavigateToDag,
  loading,
  anomalyReport,
}) => {
  const [serviceHealth, setServiceHealth] = useState<ServiceHealthReport | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(false);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [latencyData, setLatencyData] = useState<LatencyHistogramReport | null>(null);
  const [latencyLoading, setLatencyLoading] = useState<boolean>(false);
  const [pending, setPending] = useState<string | null>(null);

  const fetchHealthAndLatency = useCallback(async () => {
    setHealthLoading(true);
    setLatencyLoading(true);
    setHealthError(null);
    try {
      const [h, l] = await Promise.allSettled([
        api.getServiceHealth(),
        api.getLatencyHistogram(5),
      ]);
      if (h.status === 'fulfilled') {
        setServiceHealth(h.value);
      } else {
        setHealthError((h.reason as Error)?.message || 'Failed to fetch service health');
      }
      if (l.status === 'fulfilled') {
        setLatencyData(l.value);
      }
    } finally {
      setHealthLoading(false);
      setLatencyLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealthAndLatency();
  }, [fetchHealthAndLatency, currentScenario, events.length]);

  useEffect(() => {
    if (!loading) setPending(null);
  }, [loading]);

  const displayEvents = liveEvents.length > 0 ? liveEvents : events;

  // Rows that were not in the previous render flash in (and cascade, via --i)
  const prevIds = useRef<Set<string> | null>(null);
  const freshIds = useMemo(() => {
    const prev = prevIds.current;
    if (!prev) return new Set<string>();
    return new Set(displayEvents.filter((e) => !prev.has(e.event_id)).map((e) => e.event_id));
  }, [displayEvents]);
  useEffect(() => {
    prevIds.current = new Set(displayEvents.map((e) => e.event_id));
  }, [displayEvents]);

  // Determine overall system health deterministically from real data
  const overallHealth = serviceHealth
    ? serviceHealth.critical_count > 0
      ? 'Critical'
      : serviceHealth.degraded_count > 0
      ? 'Degraded'
      : serviceHealth.total_services > 0
      ? 'Healthy'
      : 'N/A'
    : 'N/A';

  const healthColor =
    overallHealth === 'Healthy' ? PALETTE.ok : overallHealth === 'Degraded' ? PALETTE.warn : overallHealth === 'Critical' ? PALETTE.crit : PALETTE.mute;

  const headline =
    overallHealth === 'N/A' ? (
      <>The mesh is <em>idle</em></>
    ) : (
      <>The mesh is <em style={{ color: healthColor }}>{overallHealth.toLowerCase()}</em></>
    );

  const anomalyTotal = anomalyReport?.total ?? 0;

  return (
    <>
      {/* ── Mesh pulse + KPIs ──────────────────────────────────────── */}
      <section className="dash-top">
        <div className="panel flush orbit-panel">
          <div className="orbit-head">
            <div>
              <div className="eyebrow">Mesh pulse</div>
              <h2 className="orbit-title">{headline}</h2>
              <div className="row" style={{ marginTop: 12, gap: 8 }}>
                <span className="chip chip-ok lower"><span className="dot" />{serviceHealth?.healthy_count ?? 0} healthy</span>
                <span className="chip chip-warn lower"><span className="dot" />{serviceHealth?.degraded_count ?? 0} degraded</span>
                <span className="chip chip-crit lower"><span className="dot" />{serviceHealth?.critical_count ?? 0} critical</span>
              </div>
            </div>
            <div className="row">
              <button className="btn btn-primary" onClick={() => onLoadScenario('TRACE-DEMO-001')} disabled={loading}>
                <Icon name="bolt" size={16} /> Load TRACE-DEMO-001
              </button>
              <button className="btn btn-icon" onClick={fetchHealthAndLatency} disabled={healthLoading} title="Refresh health" aria-label="Refresh health">
                <Icon name="refresh" size={17} className={healthLoading ? 'spin-icon' : ''} />
              </button>
            </div>
          </div>
          <ServiceOrbit services={serviceHealth?.services || []} loading={healthLoading} />
        </div>

        <div className="kpi-grid stagger">
          <MetricCard icon="shield" label="System health" value={overallHealth} color={healthColor} />
          <MetricCard icon="dag" label="Active traces" value={currentScenario ? 1 : 0} color={PALETTE.iris1} />
          <MetricCard icon="inbox" label="Events ingested" value={metrics?.event_count ?? events.length} color={PALETTE.info} />
          <MetricCard icon="alert" label="Anomalies" value={anomalyTotal} color={anomalyTotal > 0 ? PALETTE.crit : PALETTE.ok} />
          <MetricCard icon="globe" label="Services tracked" value={serviceHealth?.total_services ?? metrics?.services_tracked ?? 0} color="#8f4cf0" />
          <MetricCard icon="bolt" label="Processing rate" value="N/A" color={PALETTE.mute} />
        </div>
      </section>

      {/* ── Scenarios ──────────────────────────────────────────────── */}
      <section className="panel">
        <div className="panel-head">
          <div>
            <div className="eyebrow">Scenarios & traces</div>
            <h3 className="panel-title" style={{ marginTop: 10 }}>Pick a workflow to reconstruct</h3>
            <p className="panel-sub">Select a trace to rebuild its causal DAG, inspect clock drift, and evaluate anomalies.</p>
          </div>
        </div>
        {scenarios.length === 0 ? (
          <EmptyState compact title="No scenarios available" description="Scenarios appear once the API responds." />
        ) : (
          <div className="grid-auto stagger" style={{ ['--min' as any]: '270px' }}>
            {scenarios.map((sc, i) => {
              const isCurrent = currentScenario === sc.id || currentScenario === sc.trace_id;
              const busy = loading && pending === sc.id;
              return (
                <Tilt
                  as="button"
                  key={sc.id}
                  max={7}
                  className={`scn ${isCurrent ? 'is-current' : ''} ${busy ? 'is-busy' : ''}`}
                  style={{ ['--i' as any]: i }}
                  onClick={() => {
                    setPending(sc.id);
                    onLoadScenario(sc.id);
                  }}
                  disabled={loading}
                >
                  <div className="scn-glyph lift">
                    <PatternGlyph pattern={sc.pattern} services={sc.services} nodes={sc.expected_nodes} />
                  </div>
                  <div className="spread" style={{ marginTop: 14 }}>
                    <span className="chip chip-iris">{sc.trace_id || sc.pattern}</span>
                    {isCurrent && (
                      <span className="chip chip-ok lower"><span className="live-dot" style={{ width: 6, height: 6 }} /> Active</span>
                    )}
                  </div>
                  <h4 className="scn-name">{sc.name}</h4>
                  <p className="scn-desc">{sc.description}</p>
                  <div className="scn-meta">
                    <span>~{sc.expected_nodes} nodes</span>
                    <span className="dots">
                      {(sc.services || []).map((s) => (
                        <i key={s} title={getServiceLabel(s)} style={{ background: getServiceColor(s) }} />
                      ))}
                    </span>
                    <span className="go">{busy ? 'Reconstructing…' : 'Reconstruct'} <Icon name="arrow" size={14} /></span>
                  </div>
                </Tilt>
              );
            })}
          </div>
        )}
      </section>

      {/* ── Service detail ─────────────────────────────────────────── */}
      <section className="panel">
        <div className="panel-head">
          <div>
            <div className="eyebrow">Service health</div>
            <h3 className="panel-title" style={{ marginTop: 10 }}>Deterministic service health map</h3>
            <p className="panel-sub">Derived in real time from active DAG events and detected anomalies.</p>
          </div>
        </div>
        <ServiceHealthMap
          services={serviceHealth?.services || []}
          loading={healthLoading}
          error={healthError}
          onRetry={fetchHealthAndLatency}
        />
      </section>

      {/* ── Latency & anomalies ────────────────────────────────────── */}
      <section className="grid-2">
        <div className="panel">
          <div className="panel-head" style={{ marginBottom: 14 }}>
            <div>
              <div className="eyebrow">Latency</div>
              <h3 className="panel-title" style={{ marginTop: 10 }}>Causal transit summary</h3>
              <p className="panel-sub">Real edge transit timings across causal parent→child dependencies.</p>
            </div>
          </div>
          {latencyLoading && !latencyData ? (
            <Loader message="Computing edge latencies…" />
          ) : latencyData && latencyData.sample_size > 0 ? (
            <>
              <div className="lat-grid">
                <Ms label="p50 · median" v={latencyData.p50_ms} color={PALETTE.iris1} />
                <Ms label="p95" v={latencyData.p95_ms} color="#c27b00" />
                <Ms label="max" v={latencyData.max_ms} color={PALETTE.crit} />
              </div>
              <LatencyBand d={latencyData} />
              <div className="muted xs" style={{ marginTop: 26 }}>
                Sample size: {latencyData.sample_size} valid causal edge(s)
                {latencyData.inversion_edge_count > 0 && ` · ${latencyData.inversion_edge_count} time-inversion edge(s) detected`}
              </div>
            </>
          ) : (
            <EmptyState compact title="No edge latencies yet" description="Causal edge timings appear when a multi-node workflow is loaded." />
          )}
        </div>

        <div className="panel">
          <div className="panel-head" style={{ marginBottom: 14 }}>
            <div>
              <div className="eyebrow">Integrity</div>
              <h3 className="panel-title" style={{ marginTop: 10 }}>Recent causal anomalies</h3>
              <p className="panel-sub">Cycles, physical clock inversions and vector clock inconsistencies.</p>
            </div>
            <span className={`chip ${anomalyTotal ? 'chip-crit' : 'chip-ok'}`}>{anomalyTotal ? `${anomalyTotal} anomal${anomalyTotal === 1 ? 'y' : 'ies'}` : 'Clean'}</span>
          </div>
          {anomalyReport && anomalyReport.anomalies.length > 0 ? (
            <div className="stack stagger" style={{ gap: 8 }}>
              {anomalyReport.anomalies.slice(0, 4).map((a, i) => (
                <div key={i} className={`mini-anom sev-${a.severity.toLowerCase()}`} style={{ ['--i' as any]: i }}>
                  <span className="mini-anom-ic"><Icon name={a.severity === 'CRITICAL' ? 'alert' : 'warning'} size={16} /></span>
                  <div className="grow">
                    <b>{a.anomaly_type.replace(/_/g, ' ')}</b>
                    <small className="mono">{a.source_event_id}{a.target_event_id ? ` → ${a.target_event_id}` : ''}</small>
                  </div>
                  <span className={`chip lower ${a.severity === 'CRITICAL' ? 'chip-crit' : a.severity === 'WARNING' ? 'chip-warn' : 'chip-info'}`}>{a.severity}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState compact title="No anomalies" description="The active DAG satisfies causal consistency constraints." />
          )}
        </div>
      </section>

      {/* ── Event stream + explore ─────────────────────────────────── */}
      <section className="grid-2 dash-bottom">
        <div className="panel">
          <div className="panel-head" style={{ marginBottom: 14 }}>
            <div>
              <div className="eyebrow">Stream</div>
              <h3 className="panel-title" style={{ marginTop: 10 }}>Ingested event stream</h3>
            </div>
            <span className="chip chip-iris">{liveEvents.length > 0 && <span className="live-dot" style={{ width: 6, height: 6 }} />}{displayEvents.length} events</span>
          </div>
          <div className="ev-list">
            {displayEvents.length === 0 ? (
              <EmptyState compact title="No events in stream" description="Load a scenario above to watch events arrive." />
            ) : (
              displayEvents.map((e, idx) => (
                <div
                  key={e.event_id || idx}
                  className={`ev-row ${freshIds.has(e.event_id) ? 'fresh' : ''}`}
                  style={{ ['--c' as any]: getServiceColor(e.service_id), ['--i' as any]: Math.min(idx, 12) }}
                >
                  <i className="pearl" />
                  <div className="grow">
                    <b>{e.event_type}</b>
                    <small>{getServiceLabel(e.service_id)}</small>
                  </div>
                  <span className="chip chip-iris num">L{e.lamport_ts}</span>
                  <small className="ev-region">{e.region || e.metadata?.region || 'local'}</small>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="panel explore">
          <div>
            <div className="eyebrow">Next</div>
            <h3 className="explore-title">Step into the <em className="serif gradient-text">causal graph</em></h3>
            <p className="muted" style={{ marginTop: 12, fontSize: 13.5 }}>
              ChronosMesh processes out-of-order event streams across distributed cloud services, computing happens-before relations and transitive reductions to reconstruct true causality.
            </p>
            <ul className="explore-list">
              <li><Icon name="cube" size={16} /><span><b>Vector clocks</b> disambiguate causal order from genuine concurrency</span></li>
              <li><Icon name="clock" size={16} /><span><b>Hybrid logical clocks</b> bound physical clock skew across regions</span></li>
              <li><Icon name="anomaly" size={16} /><span><b>Anomaly detection</b> flags cycles, inversions and duplicates</span></li>
            </ul>
          </div>
          <button className="btn btn-primary btn-lg" onClick={onNavigateToDag} disabled={loading || !currentScenario}>
            Explore the reconstructed graph <Icon name="arrow" size={18} />
          </button>
        </div>
      </section>
    </>
  );
};
