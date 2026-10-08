import React, { useState } from 'react';
import { WhatIfResult, DAGNode } from '../types';
import { getServiceColor, getServiceLabel, PALETTE } from '../utils/colors';
import { Icon } from './Icon';
import { useCountUp } from '../fx/hooks';

interface WhatIfPanelProps {
  nodes: DAGNode[];
  selectedEventId: string;
  result: WhatIfResult | null;
  loading: boolean;
  onSelectEvent: (eventId: string) => void;
  onRunSimulation: (eventId: string) => void;
}

/** Radial gauge — the arc sweeps to the blast radius percentage. */
const Gauge: React.FC<{ pct: number }> = ({ pct }) => {
  const R = 54;
  const C = 2 * Math.PI * R;
  const shown = useCountUp(pct, 1200, 1);
  const hue = pct >= 66 ? PALETTE.crit : pct >= 33 ? PALETTE.warn : PALETTE.ok;
  return (
    <div className="gauge" key={pct}>
      <svg viewBox="0 0 140 140">
        <defs>
          <linearGradient id="gg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={PALETTE.warn} />
            <stop offset="1" stopColor={hue} />
          </linearGradient>
        </defs>
        <circle cx="70" cy="70" r={R} className="g-track" />
        <circle
          cx="70" cy="70" r={R}
          className="g-arc"
          stroke="url(#gg)"
          strokeDasharray={C}
          style={{ ['--from' as any]: C, ['--to' as any]: C * (1 - Math.min(100, pct) / 100) }}
        />
        {Array.from({ length: 40 }).map((_, i) => {
          const a = (i / 40) * Math.PI * 2 - Math.PI / 2;
          return <line key={i} x1={70 + Math.cos(a) * 64} y1={70 + Math.sin(a) * 64} x2={70 + Math.cos(a) * (i % 5 === 0 ? 70 : 67)} y2={70 + Math.sin(a) * (i % 5 === 0 ? 70 : 67)} className="g-tick" />;
        })}
      </svg>
      <div className="gauge-center">
        <b className="num" style={{ color: hue }}>{shown}<small>%</small></b>
        <span>blast radius</span>
      </div>
    </div>
  );
};

export const WhatIfPanel: React.FC<WhatIfPanelProps> = ({
  nodes,
  selectedEventId,
  result,
  loading,
  onSelectEvent,
  onRunSimulation,
}) => {
  const [modificationType, setModificationType] = useState<'remove' | 'delay'>('remove');
  const [delayMs, setDelayMs] = useState<number>(500);

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Counterfactual evaluation</div>
          <h3 className="panel-title" style={{ marginTop: 10 }}>What-if causal blast radius lab</h3>
          <p className="panel-sub">“If event X had <i className="serif">not</i> occurred, which downstream effects would cascade?”</p>
        </div>
        <span className="chip chip-warn"><Icon name="flask" size={13} /> Simulation mode · non-destructive</span>
      </div>

      <div className="whatif-grid">
        <div className="stack" style={{ gap: 18 }}>
          <div className="field">
            <label htmlFor="wi-ev">Event to modify</label>
            <select id="wi-ev" className="select" value={selectedEventId} onChange={(e) => onSelectEvent(e.target.value)}>
              <option value="" disabled>Choose an event…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.event_type} ({n.service_id}) — L{n.lamport_ts}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>Modification strategy</label>
            <div className="opt-cards">
              <button type="button" className={`opt ${modificationType === 'remove' ? 'on' : ''}`} onClick={() => setModificationType('remove')}>
                <Icon name="trash" size={18} />
                <b>Remove event</b>
                <small>Measure the blast radius</small>
              </button>
              <button type="button" className={`opt ${modificationType === 'delay' ? 'on' : ''}`} onClick={() => setModificationType('delay')}>
                <Icon name="clock" size={18} />
                <b>Clock drift / delay</b>
                <small>Inject latency</small>
              </button>
            </div>
          </div>

          {modificationType === 'delay' && (
            <div className="field">
              <label>Injected latency · <b className="num" style={{ color: 'var(--ink)' }}>{delayMs} ms</b></label>
              <input
                type="range"
                className="range"
                min={50}
                max={2000}
                step={50}
                value={delayMs}
                style={{ ['--p' as any]: `${((delayMs - 50) / 1950) * 100}%`, ['--c' as any]: PALETTE.warn }}
                onChange={(e) => setDelayMs(parseInt(e.target.value))}
              />
            </div>
          )}

          <button className="btn btn-primary btn-lg" onClick={() => onRunSimulation(selectedEventId)} disabled={!selectedEventId || loading}>
            {loading ? 'Simulating…' : <><Icon name="whatif" size={18} /> Run simulation</>}
          </button>
        </div>

        {result ? (
          <div className="outcome" key={result.removed_event_id + result.invalidated_count}>
            <div className="outcome-top">
              <Gauge pct={result.blast_radius_pct} />
              <div className="outcome-stats">
                <div>
                  <span>Cascade depth</span>
                  <b className="num">{result.cascade_depth}<small> hops</small></b>
                </div>
                <div>
                  <span>Invalidated</span>
                  <b className="num" style={{ color: PALETTE.crit }}>{result.invalidated_count}</b>
                </div>
                <div>
                  <span>Surviving</span>
                  <b className="num" style={{ color: PALETTE.ok }}>{result.surviving_events?.length ?? 0}</b>
                </div>
              </div>
            </div>

            <div className="label" style={{ marginTop: 18, marginBottom: 8 }}>Affected services ({result.affected_services.length})</div>
            <div className="row" style={{ gap: 6 }}>
              {result.affected_services.map((svc) => (
                <span key={svc} className="svc-tag" style={{ ['--c' as any]: getServiceColor(svc) }}>{getServiceLabel(svc)}</span>
              ))}
            </div>

            <div className="label" style={{ marginTop: 18, marginBottom: 8 }}>Invalidated events ({result.invalidated_count})</div>
            <div className="inv-list stagger">
              {result.invalidated_events.map((id, i) => {
                const node = nodes.find((n) => n.id === id);
                return (
                  <div key={id} className="inv-row" style={{ ['--i' as any]: i }}>
                    <Icon name="close" size={13} weight={2.4} />
                    <b>{node?.event_type.replace(/_/g, ' ') || id.slice(0, 8)}</b>
                    <small>{node ? getServiceLabel(node.service_id) : ''}</small>
                  </div>
                );
              })}
              {result.invalidated_events.length === 0 && <span className="muted small">No downstream events depend on this one.</span>}
            </div>
          </div>
        ) : (
          <div className="outcome idle">
            <Icon name="flask" size={30} />
            <b>Awaiting simulation</b>
            <span>Pick an event and run the simulation to see how far its absence ripples.</span>
          </div>
        )}
      </div>
    </div>
  );
};
