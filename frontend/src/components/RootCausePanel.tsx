import React from 'react';
import { RootCauseResult, DAGNode } from '../types';
import { getServiceColor, getServiceLabel, PALETTE } from '../utils/colors';
import { Icon } from './Icon';

interface RootCausePanelProps {
  nodes: DAGNode[];
  selectedFailureEventId: string;
  result: RootCauseResult | null;
  loading: boolean;
  onSelectFailureEvent: (eventId: string) => void;
  onRunTrace: () => void;
  onHighlightPath?: (path: string[]) => void;
}

export const RootCausePanel: React.FC<RootCausePanelProps> = ({
  nodes,
  selectedFailureEventId,
  result,
  loading,
  onSelectFailureEvent,
  onRunTrace,
  onHighlightPath,
}) => {
  // Extract affected services along the critical path
  const affectedServices = React.useMemo(() => {
    if (!result || !result.critical_path) return [];
    const svcs = new Set<string>();
    result.critical_path.forEach((id) => {
      const node = nodes.find((n) => n.id === id);
      if (node?.service_id) svcs.add(node.service_id);
    });
    return Array.from(svcs);
  }, [result, nodes]);

  const rootCauseNode = React.useMemo(() => {
    if (!result || !result.root_causes.length) return null;
    const rootId = result.root_causes[0]?.event_id;
    return nodes.find((n) => n.id === rootId) || null;
  }, [result, nodes]);

  const failureNode = React.useMemo(() => {
    if (!selectedFailureEventId) return null;
    return nodes.find((n) => n.id === selectedFailureEventId) || null;
  }, [selectedFailureEventId, nodes]);

  return (
    <div className="panel rc-panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Backward DAG traversal</div>
          <h3 className="panel-title" style={{ marginTop: 10 }}>Root-cause tracing</h3>
          <p className="panel-sub">Walk back through happens-before edges to find the event that set a failure in motion.</p>
        </div>
      </div>

      <div className="rc-controls">
        <div className="field grow" style={{ minWidth: 260 }}>
          <label htmlFor="rc-sel">Target failure event</label>
          <select id="rc-sel" className="select" value={selectedFailureEventId} onChange={(e) => onSelectFailureEvent(e.target.value)}>
            <option value="" disabled>Select a target event to trace…</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.event_type} ({getServiceLabel(n.service_id)}) — L{n.lamport_ts} [{n.id.slice(0, 12)}…]
              </option>
            ))}
          </select>
        </div>
        <button className="btn btn-primary" style={{ height: 42 }} onClick={onRunTrace} disabled={!selectedFailureEventId || loading}>
          {loading ? 'Traversing DAG…' : <><Icon name="link" size={16} /> Trace root cause</>}
        </button>
      </div>

      {result && (
        <div className="rc-result stack" style={{ gap: 18, marginTop: 22 }}>
          <div className="rc-cards stagger">
            <div className="rc-card-s" style={{ ['--c' as any]: PALETTE.warn, ['--i' as any]: 0 }}>
              <span className="eyebrow bare">1 · Root cause origin</span>
              <b>{rootCauseNode ? rootCauseNode.event_type.replace(/_/g, ' ') : result.root_causes[0]?.event_id || 'N/A'}</b>
              <small>
                Service {rootCauseNode ? getServiceLabel(rootCauseNode.service_id) : 'unknown'} · {result.root_causes[0]?.depth ?? 0} hops upstream
              </small>
            </div>
            <div className="rc-card-s" style={{ ['--c' as any]: '#8f4cf0', ['--i' as any]: 1 }}>
              <span className="eyebrow bare">2 · Traversed services</span>
              <div className="row" style={{ gap: 6, marginTop: 8 }}>
                {affectedServices.map((svc) => (
                  <span key={svc} className="svc-tag" style={{ ['--c' as any]: getServiceColor(svc) }}>{getServiceLabel(svc)}</span>
                ))}
              </div>
            </div>
            <div className="rc-card-s" style={{ ['--c' as any]: PALETTE.crit, ['--i' as any]: 2 }}>
              <span className="eyebrow bare">3 · Downstream failure</span>
              <b>{failureNode ? failureNode.event_type.replace(/_/g, ' ') : selectedFailureEventId}</b>
              <small>{result.critical_path?.length || 0} critical steps</small>
            </div>
          </div>

          {result.critical_path && result.critical_path.length > 0 && (
            <div className="chain-box">
              <div className="label" style={{ marginBottom: 14 }}>Causal propagation chain · origin → terminal impact</div>
              <div className="chain">
                {result.critical_path.map((stepId, i) => {
                  const node = nodes.find((n) => n.id === stepId);
                  const isRoot = i === 0;
                  const isFailure = i === result.critical_path.length - 1;
                  const tone = isRoot ? 'root' : isFailure ? 'fail' : 'mid';
                  return (
                    <React.Fragment key={stepId}>
                      <div className={`chain-node ${tone}`} style={{ ['--k' as any]: i, ['--c' as any]: node ? getServiceColor(node.service_id) : PALETTE.mute }}>
                        <span className="cn-badge">{isRoot ? 'origin' : isFailure ? 'impact' : `+${i}`}</span>
                        <i className="cn-pearl" />
                        <b>{node?.event_type.replace(/_/g, ' ') || stepId.slice(0, 8)}</b>
                        {node?.service_id && <small>{getServiceLabel(node.service_id)}</small>}
                      </div>
                      {i < result.critical_path.length - 1 && (
                        <span className="chain-link" style={{ ['--k' as any]: i }}><i /></span>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
              {onHighlightPath && (
                <button className="btn btn-sm" onClick={() => onHighlightPath(result.critical_path)} style={{ marginTop: 16 }}>
                  Highlight causal chain in graph
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
