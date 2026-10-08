import React, { useMemo, useReducer, useState } from 'react';
import { Icon } from '../Icon';

const PROCS = [
  { name: 'P1', color: '#4c6ef5', y: 62 },
  { name: 'P2', color: '#0fb98a', y: 150 },
  { name: 'P3', color: '#8f4cf0', y: 238 },
];
const X0 = 118;
const DX = 62;
const MAXCOL = 12;

interface Ev {
  id: number;
  p: number;
  col: number;
  lam: number;
  vc: number[];
  kind: 'local' | 'send' | 'recv';
}
interface Msg { from: number; to: number; id: number }
interface State { events: Ev[]; msgs: Msg[]; col: number; lam: number[]; vc: number[][]; nextId: number }

const empty = (): State => ({ events: [], msgs: [], col: 0, lam: [0, 0, 0], vc: [[0, 0, 0], [0, 0, 0], [0, 0, 0]], nextId: 1 });

type Action = { t: 'local'; p: number } | { t: 'send'; p: number; q: number } | { t: 'reset' };

function slide(s: State): State {
  let { events, msgs } = s;
  while (events.some((e) => e.col > MAXCOL)) {
    events = events.filter((e) => e.col > 0).map((e) => ({ ...e, col: e.col - 1 }));
    const ids = new Set(events.map((e) => e.id));
    msgs = msgs.filter((m) => ids.has(m.from) && ids.has(m.to));
  }
  return { ...s, events, msgs, col: Math.min(s.col, MAXCOL + 1) };
}

function reduce(s: State, a: Action): State {
  if (a.t === 'reset') return seed();
  const lam = [...s.lam];
  const vc = s.vc.map((v) => [...v]);
  let id = s.nextId;
  const events = [...s.events];
  const msgs = [...s.msgs];
  let col = s.col;

  if (a.t === 'local') {
    lam[a.p] += 1;
    vc[a.p][a.p] += 1;
    events.push({ id: id++, p: a.p, col: col++, lam: lam[a.p], vc: [...vc[a.p]], kind: 'local' });
  } else {
    // send event on p
    lam[a.p] += 1;
    vc[a.p][a.p] += 1;
    const sendEv: Ev = { id: id++, p: a.p, col: col++, lam: lam[a.p], vc: [...vc[a.p]], kind: 'send' };
    events.push(sendEv);
    // receive on q merges the message clock
    lam[a.q] = Math.max(lam[a.q], sendEv.lam) + 1;
    vc[a.q] = vc[a.q].map((v, i) => Math.max(v, sendEv.vc[i]));
    vc[a.q][a.q] += 1;
    const recvEv: Ev = { id: id++, p: a.q, col: col++, lam: lam[a.q], vc: [...vc[a.q]], kind: 'recv' };
    events.push(recvEv);
    msgs.push({ from: sendEv.id, to: recvEv.id, id: sendEv.id });
  }
  return slide({ events, msgs, col, lam, vc, nextId: id });
}

function seed(): State {
  let s = empty();
  const script: Action[] = [
    { t: 'local', p: 0 },
    { t: 'send', p: 0, q: 1 },
    { t: 'local', p: 2 },
    { t: 'send', p: 1, q: 2 },
    { t: 'local', p: 0 },
  ];
  for (const a of script) s = reduce(s, a);
  return s;
}

const leq = (a: number[], b: number[]) => a.every((v, i) => v <= b[i]);
const rel = (e: Ev, h: Ev): 'self' | 'before' | 'after' | 'concurrent' => {
  if (e.id === h.id) return 'self';
  if (leq(e.vc, h.vc)) return 'before';
  if (leq(h.vc, e.vc)) return 'after';
  return 'concurrent';
};
const REL_COLOR = { self: '#15132b', before: '#2f9bff', after: '#8f4cf0', concurrent: '#f59f00' } as const;

const xOf = (col: number) => X0 + col * DX;

/** An interactive space-time diagram: build a distributed execution and read its causality. */
export const ClockLab: React.FC = () => {
  const [state, dispatch] = useReducer(reduce, undefined, seed);
  const [hoverId, setHoverId] = useState<number | null>(null);
  const hovered = state.events.find((e) => e.id === hoverId) || null;

  const stats = useMemo(() => {
    if (!hovered) return null;
    const out = { before: 0, after: 0, concurrent: 0 };
    state.events.forEach((e) => {
      const r = rel(e, hovered);
      if (r !== 'self') out[r] += 1;
    });
    return out;
  }, [hovered, state.events]);

  const byId = (id: number) => state.events.find((e) => e.id === id);

  return (
    <div className="lab panel solid">
      <div className="lab-controls">
        {PROCS.map((p, i) => (
          <div className="lab-proc" key={p.name} style={{ ['--c' as any]: p.color }}>
            <span className="svc-tag" style={{ ['--c' as any]: p.color }}>{p.name}</span>
            <button className="btn btn-sm" onClick={() => dispatch({ t: 'local', p: i })} title="Local event">
              <Icon name="spark" size={14} /> Event
            </button>
            {PROCS.map((q, j) =>
              j === i ? null : (
                <button key={q.name} className="btn btn-sm" onClick={() => dispatch({ t: 'send', p: i, q: j })} title={`Send a message from ${p.name} to ${q.name}`}>
                  <Icon name="arrow" size={14} /> {q.name}
                </button>
              )
            )}
          </div>
        ))}
        <button className="btn btn-sm btn-ghost" onClick={() => dispatch({ t: 'reset' })}>
          <Icon name="reset" size={14} /> Reset
        </button>
      </div>

      <svg className="lab-svg" viewBox="0 0 940 300" role="img" aria-label="Space-time diagram of three processes exchanging messages">
        <defs>
          <marker id="lab-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill="#47456a" />
          </marker>
        </defs>

        {PROCS.map((p) => (
          <g key={p.name}>
            <line x1={X0 - 30} x2={920} y1={p.y} y2={p.y} stroke={p.color} strokeOpacity="0.28" strokeWidth="2" strokeDasharray="2 7" strokeLinecap="round" />
            <text x="30" y={p.y + 4} className="lab-plabel" fill={p.color}>{p.name}</text>
          </g>
        ))}
        <text x="926" y="290" textAnchor="end" className="lab-axis">physical time →</text>

        {state.msgs.map((m) => {
          const a = byId(m.from);
          const b = byId(m.to);
          if (!a || !b) return null;
          const ax = xOf(a.col), ay = PROCS[a.p].y, bx = xOf(b.col), by = PROCS[b.p].y;
          const dim = hovered && rel(a, hovered) === 'concurrent' && rel(b, hovered) === 'concurrent';
          const sg = Math.sign(by - ay) || 1;
          const d = `M${ax} ${ay} C ${ax + 28} ${(ay + by) / 2 - 20 * sg}, ${bx - 28} ${(ay + by) / 2 + 20 * sg}, ${bx} ${by}`;
          return (
            <g key={m.id} className="lab-msg" style={{ opacity: dim ? 0.25 : 1 }}>
              <path d={d} fill="none" stroke="#47456a" strokeWidth="1.6" markerEnd="url(#lab-arrow)" pathLength={1} className="lab-msg-path" />
              <circle r="4.5" className="lab-packet">
                <animateMotion dur="2.6s" repeatCount="indefinite" path={d} keyPoints="0;1" keyTimes="0;1" calcMode="linear" />
              </circle>
            </g>
          );
        })}

        {state.events.map((e) => {
          const r = hovered ? rel(e, hovered) : null;
          const col = r ? REL_COLOR[r] : PROCS[e.p].color;
          const y = PROCS[e.p].y;
          return (
            <g
              key={e.id}
              className={`lab-ev ${r ? `r-${r}` : ''}`}
              style={{ transform: `translate(${xOf(e.col)}px, ${y}px)` }}
              onMouseEnter={() => setHoverId(e.id)}
              onMouseLeave={() => setHoverId(null)}
              onFocus={() => setHoverId(e.id)}
              onBlur={() => setHoverId(null)}
              tabIndex={0}
            >
              <g className="lab-ev-in">
                <circle r="19" fill="transparent" />
                {r === 'concurrent' && <circle r="15" className="lab-conc" stroke={col} />}
                <circle r="9.5" fill={col} className="lab-dot" />
                <ellipse cx="-3" cy="-3.5" rx="3.2" ry="2" fill="rgba(255,255,255,0.75)" transform="rotate(-35 -3 -3.5)" />
                <text y="27" textAnchor="middle" className="lab-lam">L{e.lam}</text>
                <text y="40" textAnchor="middle" className="lab-vc">[{e.vc.join(',')}]</text>
              </g>
            </g>
          );
        })}
      </svg>

      <div className="lab-legend">
        <span><i style={{ background: '#2f9bff' }} /> happened-before</span>
        <span><i style={{ background: '#8f4cf0' }} /> happened-after</span>
        <span><i style={{ background: '#f59f00' }} /> concurrent</span>
        <span className="lab-read">
          {hovered && stats ? (
            <>
              <b>{PROCS[hovered.p].name}</b> · Lamport <b>{hovered.lam}</b> · vector <code className="code">[{hovered.vc.join(', ')}]</code> — {stats.before} before · {stats.after} after ·{' '}
              <b style={{ color: '#a16300' }}>{stats.concurrent} concurrent</b>
            </>
          ) : (
            'Add events and messages, then hover any event to read its causal past, future and concurrent set.'
          )}
        </span>
      </div>
    </div>
  );
};
