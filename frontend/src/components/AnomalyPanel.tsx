import React, { useState, useMemo } from 'react';
import { Anomaly } from '../types';
import { SEVERITY_COLORS, PALETTE } from '../utils/colors';
import { Icon } from './Icon';
import { Loader, EmptyState } from './LoadingState';

interface AnomalyPanelProps {
  anomalies: Anomaly[];
  total: number;
  severitySummary?: {
    CRITICAL: number;
    WARNING: number;
    INFO: number;
  };
  loading?: boolean;
  error?: string | null;
  onSelectAnomalyEvent?: (eventId: string) => void;
}

type Sev = 'ALL' | 'CRITICAL' | 'WARNING' | 'INFO';

const SEV_HEX: Record<string, string> = { CRITICAL: PALETTE.crit, WARNING: PALETTE.warn, INFO: PALETTE.info };

/** Severity donut — arcs sweep in on mount. */
const Donut: React.FC<{ counts: Record<string, number>; total: number }> = ({ counts, total }) => {
  const R = 46;
  const C = 2 * Math.PI * R;
  let offset = 0;
  const arcs = (['CRITICAL', 'WARNING', 'INFO'] as const)
    .map((k) => ({ k, n: counts[k] || 0 }))
    .filter((a) => a.n > 0)
    .map((a) => {
      const len = (a.n / Math.max(total, 1)) * C;
      const arc = { ...a, len, off: offset };
      offset += len;
      return arc;
    });
  return (
    <div className="donut" aria-label={`${total} anomalies`}>
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={R} className="donut-track" />
        {total === 0 && <circle cx="60" cy="60" r={R} className="donut-ok" />}
        {arcs.map((a, i) => (
          <circle
            key={a.k}
            cx="60" cy="60" r={R}
            className="donut-arc"
            stroke={SEV_HEX[a.k]}
            strokeDasharray={`${Math.max(a.len - 4, 0.1)} ${C}`}
            strokeDashoffset={-a.off}
            style={{ animationDelay: `${i * 160}ms`, ['--len' as any]: `${Math.max(a.len - 4, 0.1)}` }}
          />
        ))}
      </svg>
      <div className="donut-center">
        <b className="num">{total}</b>
        <span>{total === 1 ? 'anomaly' : 'anomalies'}</span>
      </div>
    </div>
  );
};

export const AnomalyPanel: React.FC<AnomalyPanelProps> = ({
  anomalies,
  total,
  severitySummary,
  loading = false,
  error = null,
  onSelectAnomalyEvent,
}) => {
  const [filterSeverity, setFilterSeverity] = useState<Sev>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);

  const filtered = useMemo(() => {
    return anomalies.filter((a) => {
      const matchSev = filterSeverity === 'ALL' || a.severity === filterSeverity;
      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        a.anomaly_type.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        (a.source_event_id || '').toLowerCase().includes(q) ||
        (a.target_event_id && a.target_event_id.toLowerCase().includes(q));
      return matchSev && matchSearch;
    });
  }, [anomalies, filterSeverity, searchQuery]);

  if (loading) {
    return (
      <div className="panel">
        <Loader message="Analyzing causal graph for anomalies…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel">
        <div className="errorbox"><span>Failed to load anomalies: {error}</span></div>
      </div>
    );
  }

  const counts = {
    CRITICAL: severitySummary?.CRITICAL || 0,
    WARNING: severitySummary?.WARNING || 0,
    INFO: severitySummary?.INFO || 0,
  };

  const chips: { k: Sev; label: string; n: number; tone: string }[] = [
    { k: 'ALL', label: 'All', n: total, tone: 'iris' },
    { k: 'CRITICAL', label: 'Critical', n: counts.CRITICAL, tone: 'crit' },
    { k: 'WARNING', label: 'Warning', n: counts.WARNING, tone: 'warn' },
    { k: 'INFO', label: 'Info', n: counts.INFO, tone: 'info' },
  ];

  return (
    <div className="panel anom-panel">
      <div className="anom-top">
        <Donut counts={counts} total={total} />
        <div className="grow">
          <div className="eyebrow">Causal anomaly center</div>
          <h3 className="anom-title">
            {total === 0 ? <>All events satisfy <em className="serif gradient-text">happens-before</em></> : <>Causality violations <em className="serif gradient-text">detected</em></>}
          </h3>
          <p className="panel-sub">Cycles, temporal inversions, clock drift and concurrent mutations across the loaded trace.</p>
          <div className="row" style={{ marginTop: 14, gap: 8 }}>
            {chips.map((c) => (
              <button
                key={c.k}
                className={`chip btn-chip chip-${c.tone} ${filterSeverity === c.k ? 'is-sel' : ''}`}
                onClick={() => setFilterSeverity(c.k)}
              >
                {c.label} <b className="num">{c.n}</b>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="searchbar">
        <Icon name="search" size={17} />
        <input
          type="text"
          placeholder="Search by anomaly type, description, or event ID…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          aria-label="Search anomalies"
        />
        {searchQuery && (
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setSearchQuery('')} aria-label="Clear search">
            <Icon name="close" size={15} />
          </button>
        )}
      </div>

      <div className="anom-grid" style={{ gridTemplateColumns: selectedAnomaly ? 'minmax(0,1.25fr) minmax(0,1fr)' : '1fr' }}>
        {filtered.length === 0 ? (
          <EmptyState
            compact
            title={anomalies.length === 0 ? 'No anomalies' : 'Nothing matches'}
            description={anomalies.length === 0 ? 'All loaded events satisfy happens-before invariants.' : 'No anomalies match the current search or severity filter.'}
          />
        ) : (
          <div className="anom-list stagger">
            {filtered.map((anom, idx) => {
              const sev = SEVERITY_COLORS[anom.severity] || SEVERITY_COLORS.INFO;
              const isSelected = selectedAnomaly === anom;
              return (
                <button
                  key={idx}
                  onClick={() => setSelectedAnomaly(isSelected ? null : anom)}
                  className={`anom-item ${isSelected ? 'sel' : ''}`}
                  style={{ ['--c' as any]: sev.text, ['--i' as any]: Math.min(idx, 10) }}
                >
                  <span className="anom-ic"><Icon name={sev.icon} size={18} /></span>
                  <span className="grow">
                    <b>{anom.anomaly_type.replace(/_/g, ' ')}</b>
                    <span className="anom-desc">{anom.description}</span>
                    <span className="anom-ids">
                      <code className="code">{anom.source_event_id}</code>
                      {anom.target_event_id && (<><Icon name="arrow" size={12} /><code className="code">{anom.target_event_id}</code></>)}
                    </span>
                  </span>
                  <span className={`chip lower chip-${anom.severity === 'CRITICAL' ? 'crit' : anom.severity === 'WARNING' ? 'warn' : 'info'}`}>{anom.severity}</span>
                </button>
              );
            })}
          </div>
        )}

        {selectedAnomaly && (
          <div className="anom-detail" key={selectedAnomaly.description + selectedAnomaly.source_event_id}>
            <div className="spread">
              <div className="eyebrow">Diagnosis</div>
              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setSelectedAnomaly(null)} aria-label="Close diagnosis">
                <Icon name="close" size={15} />
              </button>
            </div>
            <h4 className="anom-detail-title">{selectedAnomaly.anomaly_type.replace(/_/g, ' ').toLowerCase()}</h4>
            <p className="muted" style={{ fontSize: 13 }}>{selectedAnomaly.description}</p>
            <div className="kv" style={{ marginTop: 14 }}>
              <span>Severity</span>
              <b><span className={`chip lower chip-${selectedAnomaly.severity === 'CRITICAL' ? 'crit' : selectedAnomaly.severity === 'WARNING' ? 'warn' : 'info'}`}>{selectedAnomaly.severity}</span></b>
              <span>Source event</span>
              <b className="mono">{selectedAnomaly.source_event_id}</b>
              {selectedAnomaly.target_event_id && (<><span>Target event</span><b className="mono">{selectedAnomaly.target_event_id}</b></>)}
            </div>

            {selectedAnomaly.details && Object.keys(selectedAnomaly.details).length > 0 && (
              <div className="tech">
                <div className="label" style={{ marginBottom: 8 }}>Technical details</div>
                <pre>{JSON.stringify(selectedAnomaly.details, null, 2)}</pre>
              </div>
            )}

            {onSelectAnomalyEvent && selectedAnomaly.source_event_id && (
              <button className="btn btn-primary" style={{ marginTop: 'auto' }} onClick={() => onSelectAnomalyEvent(selectedAnomaly.source_event_id!)}>
                Inspect in causal graph <Icon name="arrow" size={16} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
