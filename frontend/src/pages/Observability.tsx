import React, { useCallback, useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { MetricCard } from '../components/MetricCard';
import { ErrorState, Loader } from '../components/LoadingState';
import api from '../services/api';
import { SystemMetrics, SystemStatus } from '../types';
import { PALETTE } from '../utils/colors';

interface Props {
  metrics: SystemMetrics | null;
}

const ageLabel = (s: number | null | undefined) =>
  s === null || s === undefined ? '—' : s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`;

export const ObservabilityPage: React.FC<Props> = ({ metrics }) => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [embed, setEmbed] = useState(false);

  const load = useCallback(async () => {
    try {
      setStatus(await api.getSystemStatus());
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Status unavailable');
    }
  }, []);

  useEffect(() => {
    load();
    const t = window.setInterval(load, 5000);
    return () => window.clearInterval(t);
  }, [load]);

  if (!status && !error) return <Loader message="Reading platform status…" />;

  const q = status?.queue;
  const backlog = q?.visible;
  const healthy = status?.storage.ok;
  const links = [
    { key: 'grafana', label: 'Grafana dashboards', desc: 'System health · causal-engine performance · fault injection', href: status?.links.grafana, icon: 'analytics' },
    { key: 'cloudwatch', label: 'CloudWatch dashboard', desc: 'AWS-native metrics, alarms and queue age', href: status?.links.cloudwatch, icon: 'gauge' },
    { key: 'xray', label: 'AWS X-Ray traces', desc: 'Distributed request traces', href: status?.links.xray, icon: 'timeline' },
    { key: 'prom', label: 'Prometheus metrics', desc: 'Text exposition format (bearer token when configured)', href: '/metrics', icon: 'cube' },
    { key: 'docs', label: 'REST API (OpenAPI)', desc: 'Interactive documentation of every endpoint', href: '/docs', icon: 'docs' },
    { key: 'gql', label: 'GraphQL explorer', desc: 'Ancestors, descendants, concurrency, timeline', href: '/graphql', icon: 'dag' },
  ];

  return (
    <>
      {error && <ErrorState message={error} onRetry={load} />}
      {status && (
        <>
          <div className="grid-3 stagger">
            <MetricCard icon="shield" label="Storage" value={healthy ? 'healthy' : 'degraded'} color={healthy ? PALETTE.ok : PALETTE.crit}
              subValue={status.storage.backend === 'aws' ? `DynamoDB · S3 (${status.environment})` : 'in-memory (not durable)'} />
            <MetricCard icon="layers" label="Queue backlog" value={backlog ?? 'n/a'} color={backlog && backlog > 100 ? PALETTE.warn : PALETTE.iris2}
              subValue={q ? `${q.in_flight ?? 0} in flight · oldest ${ageLabel(q.oldest_message_age_seconds)}` : `ingest mode: ${status.ingest_mode} (no queue configured)`} />
            <MetricCard icon="bolt" label="Events tracked" value={metrics?.event_count ?? 0} color={PALETTE.iris1}
              subValue={`${metrics?.dag_edges ?? 0} causal edges in the explorer`} />
          </div>

          <div className="panel">
            <div className="panel-head"><div>
              <div className="eyebrow">Operate</div>
              <h3 className="panel-title" style={{ marginTop: 10 }}>Dashboards &amp; telemetry</h3>
              <p className="panel-sub">React is the product interface; Grafana, CloudWatch and X-Ray are the operations interfaces for the platform itself.</p>
            </div></div>
            <div className="grid-3">
              {links.map((l) => (
                <div key={l.key} className="panel" style={{ opacity: l.href ? 1 : 0.55, margin: 0 }}>
                  <div className="row" style={{ gap: 10 }}>
                    <span className="kpi-ico"><Icon name={l.icon} size={17} /></span>
                    <b>{l.label}</b>
                  </div>
                  <p className="small muted" style={{ margin: '8px 0 12px' }}>{l.desc}</p>
                  {l.href
                    ? <a className="btn btn-sm" href={l.href} target="_blank" rel="noopener noreferrer"><Icon name="arrow" size={14} /> Open</a>
                    : <span className="small muted">Not configured on this deployment</span>}
                </div>
              ))}
            </div>
            {status.links.grafana && (
              <div style={{ marginTop: 16 }}>
                <button className="btn btn-sm" onClick={() => setEmbed((v) => !v)}>{embed ? 'Hide embedded dashboard' : 'Embed Grafana here'}</button>
                {embed && (
                  <iframe title="Grafana" src={status.links.grafana} style={{ width: '100%', height: 640, border: 0, marginTop: 12, borderRadius: 14 }} />
                )}
              </div>
            )}
          </div>

          <div className="grid-2" style={{ alignItems: 'start' }}>
            <div className="panel">
              <div className="eyebrow">Deployment</div>
              <table className="table" style={{ marginTop: 10 }}>
                <tbody>
                  <tr><td>Environment</td><td className="num">{status.environment}</td></tr>
                  <tr><td>Persistence</td><td className="num">{status.storage.backend}{status.storage.table ? ` · ${status.storage.table}` : ''}</td></tr>
                  <tr><td>Ingest path</td><td className="num">{status.ingest_mode === 'queue' ? 'API → SQS → worker' : 'API (in-process)'}</td></tr>
                  <tr><td>Tracing (OpenTelemetry)</td><td className="num">{status.tracing ? 'exporting' : 'off'}</td></tr>
                  <tr><td>Execution engines in memory</td><td className="num">{status.cached_engines}</td></tr>
                </tbody>
              </table>
            </div>
            <div className="panel">
              <div className="eyebrow">Limits</div>
              <table className="table" style={{ marginTop: 10 }}>
                <tbody>
                  <tr><td>Max events per experiment</td><td className="num">{status.limits.max_experiment_events.toLocaleString()}</td></tr>
                  <tr><td>Max events per live execution</td><td className="num">{status.limits.max_execution_events.toLocaleString()}</td></tr>
                  <tr><td>Max events per ingest request</td><td className="num">{status.limits.max_ingest_batch}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
};
