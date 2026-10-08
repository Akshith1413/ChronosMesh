import React, { useState } from 'react';
import { DAGNode, DAGEdge, Anomaly } from '../types';
import { getServiceColor, getServiceLabel } from '../utils/colors';
import { Icon } from './Icon';
import { EmptyGlyph } from './LoadingState';

interface EventDetailsProps {
  node: DAGNode | null;
  edges: DAGEdge[];
  nodes?: DAGNode[];
  anomalies?: Anomaly[];
  currentTrace?: string | null;
  onRunWhatIf?: (nodeId: string) => void;
  onTraceRootCause?: (nodeId: string) => void;
  onSelectNeighbor?: (nodeId: string) => void;
  onClose?: () => void;
}

export const EventDetails: React.FC<EventDetailsProps> = ({
  node,
  edges,
  nodes = [],
  anomalies = [],
  currentTrace,
  onRunWhatIf,
  onTraceRootCause,
  onSelectNeighbor,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);

  if (!node) {
    return (
      <div className="panel details empty-details">
        <EmptyGlyph />
        <h4>Select an event</h4>
        <p className="muted small">Click any pearl in the graph to inspect its clocks, parents and children.</p>
      </div>
    );
  }

  const svcColor = getServiceColor(node.service_id);
  const parents = edges.filter((e) => e.target === node.id).map((e) => e.source);
  const children = edges.filter((e) => e.source === node.id).map((e) => e.target);
  const nodeAnomalies = anomalies.filter((a) => a.source_event_id === node.id || a.target_event_id === node.id);

  const vectorClock = node.vector_clock || {};
  const maxClockVal = Math.max(...Object.values(vectorClock), 1);
  const label = (id: string) => nodes.find((n) => n.id === id)?.event_type.replace(/_/g, ' ') || id;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(node.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable */
    }
  };

  const Neighbors: React.FC<{ ids: string[]; empty: string; tone: string }> = ({ ids, empty, tone }) =>
    ids.length === 0 ? (
      <span className="muted small">{empty}</span>
    ) : (
      <div className="row" style={{ gap: 6 }}>
        {ids.map((id) => (
          <button key={id} className={`nb nb-${tone}`} onClick={() => onSelectNeighbor?.(id)} title={id}>
            {label(id)}
          </button>
        ))}
      </div>
    );

  return (
    <div className="panel details" key={node.id} style={{ ['--c' as any]: svcColor }}>
      <div className="details-head">
        <div className="eyebrow">Event</div>
        {onClose && (
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Close details">
            <Icon name="close" size={16} />
          </button>
        )}
      </div>

      <div className="details-scroll">
        <h3 className="details-title">{node.event_type.replace(/_/g, ' ')}</h3>
        <div className="row" style={{ gap: 6, marginTop: 10 }}>
          <span className="svc-tag" style={{ ['--c' as any]: svcColor }}>{getServiceLabel(node.service_id)}</span>
          {node.region && <span className="chip lower"><Icon name="globe" size={12} /> {node.region}</span>}
          {currentTrace && <span className="chip chip-iris lower">{currentTrace}</span>}
        </div>

        {nodeAnomalies.length > 0 && (
          <div className="anom-banner">
            <Icon name="alert" size={16} />
            <div>
              <b>Anomaly flagged</b>
              <ul>
                {nodeAnomalies.map((a, i) => (
                  <li key={i}>{a.description} <span className="mono">({a.anomaly_type})</span></li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <div className="d-sec">
          <div className="label">Logical clocks</div>
          <div className="clock-tiles">
            <div className="clock-tile">
              <span>Lamport</span>
              <b className="num">L{node.lamport_ts}</b>
            </div>
            <div className="clock-tile warn">
              <span>Uncertainty</span>
              <b className="num">±{node.clock_uncertainty_ms ?? 5}<small>ms</small></b>
            </div>
          </div>
        </div>

        <div className="d-sec">
          <div className="label">Vector clock</div>
          <div className="vc-box">
            {Object.keys(vectorClock).length === 0 ? (
              <span className="muted small">No vector clock data</span>
            ) : (
              Object.entries(vectorClock).map(([svc, count], i) => (
                <div key={svc} className="vc-row">
                  <span>{getServiceLabel(svc)}</span>
                  <div className="vc-track">
                    <i style={{ width: `${Math.round((count / maxClockVal) * 100)}%`, background: getServiceColor(svc), animationDelay: `${i * 80}ms` }} />
                  </div>
                  <b className="num">{count}</b>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="d-sec">
          <div className="label">Physical time</div>
          <div className="kv">
            <span>Event time</span>
            <b className="mono">{new Date(node.timestamp_ms).toISOString().replace('T', ' ').slice(0, 23)}</b>
            <span>Epoch (ms)</span>
            <b className="mono muted">{Math.round(node.timestamp_ms)}</b>
          </div>
        </div>

        <div className="d-sec">
          <div className="label">Causal neighbours</div>
          <div className="nb-block">
            <span className="nb-lbl">Caused by</span>
            <Neighbors ids={parents} empty="None — root event" tone="in" />
          </div>
          <div className="nb-block">
            <span className="nb-lbl">Leads to</span>
            <Neighbors ids={children} empty="None — leaf event" tone="out" />
          </div>
        </div>

        <div className="d-sec">
          <div className="label">Event ID</div>
          <div className="idrow">
            <code className="code">{node.id}</code>
            <button className="btn btn-ghost btn-icon btn-sm" onClick={copy} aria-label="Copy event ID" title="Copy">
              <Icon name={copied ? 'check' : 'link'} size={15} />
            </button>
          </div>
        </div>
      </div>

      <div className="details-actions">
        {onRunWhatIf && (
          <button className="btn btn-primary" onClick={() => onRunWhatIf(node.id)}>
            <Icon name="whatif" size={16} /> Run what-if simulation
          </button>
        )}
        {onTraceRootCause && (
          <button className="btn" onClick={() => onTraceRootCause(node.id)}>
            <Icon name="link" size={16} /> Trace root cause
          </button>
        )}
      </div>
    </div>
  );
};
