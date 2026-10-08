import React from 'react';
import { ServiceHealthItem } from '../types';
import { Icon } from './Icon';
import { Loader, EmptyState } from './LoadingState';
import { Tilt } from '../fx/Reveal';
import { getServiceColor, getServiceLabel } from '../utils/colors';

interface ServiceHealthMapProps {
  services: ServiceHealthItem[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

const TONE: Record<string, string> = { Healthy: 'ok', Degraded: 'warn', Critical: 'crit', Unavailable: '' };

export const ServiceHealthMap: React.FC<ServiceHealthMapProps> = ({
  services,
  loading = false,
  error = null,
  onRetry,
}) => {
  if (loading && services.length === 0) {
    return <Loader message="Evaluating deterministic service health…" />;
  }

  if (error) {
    const isAuthError = /authentication|log in|unauthorized|401/i.test(error);
    return (
      <div className="errorbox">
        <span>Failed to load service health: {error}</span>
        <div className="row">
          {isAuthError && (
            <button className="btn btn-primary btn-sm" onClick={() => window.dispatchEvent(new CustomEvent('auth:open-login'))}>
              <Icon name="login" size={14} /> Log in now
            </button>
          )}
          {onRetry && (
            <button className="btn btn-sm" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  if (services.length === 0) {
    return (
      <EmptyState
        compact
        title="No active services tracked"
        description="Load a scenario trace (e.g. TRACE-DEMO-001) to evaluate distributed service health."
      />
    );
  }

  const maxEv = Math.max(...services.map((s) => s.event_count), 1);

  return (
    <div className="grid-auto stagger" style={{ ['--min' as any]: '215px' }}>
      {services.map((svc, i) => {
        const color = getServiceColor(svc.service_name);
        const tone = TONE[svc.status] ?? '';
        return (
          <Tilt key={svc.service_name} className="svc-card panel tight" max={6} style={{ ['--c' as any]: color, ['--i' as any]: i }}>
            <div className="svc-card-head lift">
              <span className="svc-tag" style={{ ['--c' as any]: color }}>
                {getServiceLabel(svc.service_name)}
              </span>
              <span className={`chip lower ${tone ? `chip-${tone}` : ''}`}>
                <span className="dot" />
                {svc.status}
              </span>
            </div>

            <div className="svc-stats">
              <div><span>Events</span><b className="num">{svc.event_count}</b></div>
              <div><span>Anomalies</span><b className="num" style={{ color: svc.anomaly_count > 0 ? '#c3213f' : undefined }}>{svc.anomaly_count}</b></div>
              <div><span>Avg latency</span><b className="num">{svc.avg_latency_ms !== null ? `${svc.avg_latency_ms} ms` : 'n/a'}</b></div>
              <div><span>Activity</span><b>{svc.latest_activity_ms ? <><i className="live-dot" style={{ marginRight: 6 }} />live</> : 'n/a'}</b></div>
            </div>

            <div className="svc-bar" title="Share of busiest service">
              <i style={{ width: `${(svc.event_count / maxEv) * 100}%` }} />
            </div>
            <div className="svc-foot">
              {svc.details.critical_anomalies
                ? `${svc.details.critical_anomalies} critical issue(s)`
                : svc.details.warning_anomalies
                ? `${svc.details.warning_anomalies} warning(s)`
                : '0 anomalies detected'}
            </div>
          </Tilt>
        );
      })}
    </div>
  );
};
