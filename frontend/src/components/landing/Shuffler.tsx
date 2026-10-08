import React, { useEffect, useRef, useState } from 'react';
import { HERO_EVENTS } from '../scenes/Loom3D';
import { useInView } from '../../fx/hooks';
import { Segmented } from '../Segmented';

const ROW = 62;

const ARRIVAL = [...HERO_EVENTS].sort((a, b) => a.arrival - b.arrival).map((e) => e.id);
const CAUSAL = [...HERO_EVENTS].sort((a, b) => a.lamport - b.lamport || a.id.localeCompare(b.id)).map((e) => e.id);

// Graph layout (viewBox 300 x 270)
const GX = [34, 108, 182, 256];
const GY: Record<string, number> = { ORDER: 38, PAYMENT: 100, INVENTORY: 162, SHIPPING: 224 };
const causalPos = (id: string) => {
  const e = HERO_EVENTS.find((x) => x.id === id)!;
  return { x: GX[e.layer], y: GY[e.lane] };
};
// Scattered "as received" positions
const SCATTER: Record<string, { x: number; y: number }> = {
  E1: { x: 214, y: 196 }, E2: { x: 262, y: 70 }, E3: { x: 60, y: 214 },
  E4: { x: 96, y: 54 }, E5: { x: 40, y: 120 }, E6: { x: 160, y: 120 },
};

/** A single list that physically re-sorts itself from arrival order to causal order. */
export const Shuffler: React.FC = () => {
  const [mode, setMode] = useState<'arrival' | 'causal'>('arrival');
  const [ref, seen] = useInView<HTMLDivElement>(0.35);
  const auto = useRef(true);

  // First time it scrolls into view, play the reconstruction once for the audience.
  useEffect(() => {
    if (!seen) return;
    const t = setTimeout(() => auto.current && setMode('causal'), 1400);
    return () => clearTimeout(t);
  }, [seen]);

  const choose = (m: 'arrival' | 'causal') => {
    auto.current = false;
    setMode(m);
  };

  const order = mode === 'arrival' ? ARRIVAL : CAUSAL;
  const causal = mode === 'causal';

  return (
    <div ref={ref} className="shuf panel solid">
      <div className="shuf-head">
        <Segmented
          ariaLabel="Event ordering"
          value={mode}
          onChange={choose}
          options={[
            { value: 'arrival', label: 'As received · Kafka' },
            { value: 'causal', label: 'As happened · ChronosMesh' },
          ]}
        />
        <span className={`chip ${causal ? 'chip-ok' : 'chip-crit'}`}>
          <span className="dot" /> {causal ? 'Topologically verified' : 'Out-of-order · jittered'}
        </span>
      </div>

      <div className="shuf-body">
        <div className="shuf-list" style={{ height: ROW * order.length }}>
          {HERO_EVENTS.map((e) => {
            const idx = order.indexOf(e.id);
            const concurrent = e.id === 'E2' || e.id === 'E3';
            return (
              <div
                key={e.id}
                className={`shuf-row ${causal ? 'is-causal' : ''}`}
                style={{
                  transform: `translateY(${idx * ROW}px)`,
                  transitionDelay: `${(causal ? idx : 5 - idx) * 55}ms`,
                  ['--c' as any]: e.color,
                }}
              >
                <span className="pos num">{idx + 1}</span>
                <span className="pearl" />
                <span className="grow">
                  <b>{e.name}</b>
                  <small>
                    {e.svc} · {e.id}
                  </small>
                </span>
                <span className="meta">
                  <span className={`chip lower ${causal ? 'chip-ok' : 'chip-crit'} swap`}>
                    {causal ? `L${e.lamport}` : `arrived #${e.arrival}`}
                  </span>
                  <span className={`parents ${causal ? 'on' : ''}`}>
                    {e.parents.length ? `← ${e.parents.join(', ')}` : 'root'}
                    {concurrent && <em> ∥ {e.id === 'E2' ? 'E3' : 'E2'}</em>}
                  </span>
                </span>
              </div>
            );
          })}
        </div>

        <svg className="shuf-dag" viewBox="0 0 300 270" aria-hidden="true">
          {HERO_EVENTS.flatMap((e) =>
            e.parents.map((p, j) => {
              const a = causalPos(p);
              const b = causalPos(e.id);
              const mx = (a.x + b.x) / 2;
              return (
                <path
                  key={`${p}-${e.id}`}
                  className={`dag-edge ${causal ? 'on' : ''}`}
                  d={`M${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`}
                  pathLength={1}
                  style={{ transitionDelay: causal ? `${700 + e.layer * 160 + j * 60}ms` : '0ms', stroke: e.color }}
                />
              );
            })
          )}
          {HERO_EVENTS.map((e) => {
            const p = causal ? causalPos(e.id) : SCATTER[e.id];
            return (
              <g key={e.id} className="dag-node" style={{ transform: `translate(${p.x}px, ${p.y}px)`, ['--c' as any]: e.color, transitionDelay: `${e.layer * 70}ms` }}>
                <circle r="19" className="halo" />
                <circle r="14" className="body" />
                <text textAnchor="middle" dy="3.5">{e.id}</text>
              </g>
            );
          })}
          {Object.entries(GY).map(([lane, y]) => (
            <text key={lane} className={`dag-lane ${causal ? 'on' : ''}`} x="4" y={y + 28} fontSize="7.5">
              {lane}
            </text>
          ))}
        </svg>
      </div>

      <p className="shuf-foot">
        {causal
          ? 'Lamport and vector clocks recover the happens-before edges. E2 and E3 are concurrent — neither caused the other — which no wall-clock can tell you.'
          : 'Network jitter and asynchronous messaging deliver events scrambled: PAYMENT_SUCCESS arrives before the order that triggered it.'}
      </p>
    </div>
  );
};
