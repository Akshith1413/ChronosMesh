import React from 'react';
import { Tilt } from '../../fx/Reveal';
import { Icon } from '../Icon';

/** Six capability tiles, each with its own looping micro-animation. */

const DagArt = () => (
  <svg viewBox="0 0 200 110" className="art">
    <g fill="none" strokeWidth="2" strokeLinecap="round">
      <path className="flow" d="M28 55 C 60 55, 60 28, 92 28" stroke="#4c6ef5" />
      <path className="flow" d="M28 55 C 60 55, 60 82, 92 82" stroke="#4c6ef5" />
      <path className="flow" d="M92 28 C 124 28, 124 55, 156 55" stroke="#0fb98a" />
      <path className="flow" d="M92 82 C 124 82, 124 55, 156 55" stroke="#f59f00" />
    </g>
    {[[28, 55, '#4c6ef5'], [92, 28, '#0fb98a'], [92, 82, '#f59f00'], [156, 55, '#8f4cf0']].map(([x, y, c], i) => (
      <g key={i} className="pearl" style={{ animationDelay: `${i * 0.3}s` }}>
        <circle cx={x as number} cy={y as number} r="13" fill={c as string} opacity="0.18" />
        <circle cx={x as number} cy={y as number} r="8.5" fill={c as string} />
        <circle cx={(x as number) - 2.5} cy={(y as number) - 3} r="2.2" fill="#fff" opacity="0.8" />
      </g>
    ))}
  </svg>
);

const AnomalyArt = () => (
  <svg viewBox="0 0 200 110" className="art">
    <path className="ecg" d="M4 62 H44 L54 62 L62 30 L74 92 L84 62 H116 L124 62 L132 48 L140 70 L148 62 H196" fill="none" stroke="#f0405f" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" pathLength={1} />
    <path d="M4 62 H196" stroke="#15132b" strokeOpacity="0.08" strokeDasharray="3 5" />
    <circle className="blip" cx="68" cy="61" r="5" fill="#f0405f" />
  </svg>
);

const WhatIfArt = () => (
  <svg viewBox="0 0 200 110" className="art">
    {[[100, 18], [60, 54], [140, 54], [40, 92], [80, 92], [120, 92], [160, 92]].map(([x, y], i) => (
      <g key={i} className={`cascade ${i === 0 ? 'src' : ''}`} style={{ ['--d' as any]: `${(i === 0 ? 0 : i < 3 ? 1 : 2) * 0.45}s` }}>
        {i > 0 && <line x1={i < 3 ? 100 : i < 5 ? 60 : 140} y1={i < 3 ? 18 : 54} x2={x} y2={y} stroke="#b4b2cc" strokeWidth="1.6" />}
        <circle cx={x} cy={y} r="9" className="n" />
      </g>
    ))}
  </svg>
);

const RootArt = () => (
  <svg viewBox="0 0 200 110" className="art">
    <g fill="none" strokeWidth="2.2" strokeLinecap="round">
      <path d="M20 55 H180" stroke="#b4b2cc" strokeDasharray="2 6" />
      <path className="rewind" d="M180 55 H20" stroke="#f59f00" pathLength={1} />
    </g>
    {[20, 65, 110, 155, 180].map((x, i) => (
      <circle key={x} cx={x} cy="55" r={i === 4 ? 9 : 7} className={`rc ${i === 0 ? 'root' : ''}`} style={{ ['--d' as any]: `${(4 - i) * 0.28}s` }} />
    ))}
  </svg>
);

const BenchArt = () => (
  <svg viewBox="0 0 200 110" className="art">
    {[['#6a4cff', 30, 84], ['#8f4cf0', 82, 70], ['#f59f00', 134, 46]].map(([c, x, h], i) => (
      <g key={i}>
        <rect x={x as number} y={100 - (h as number)} width="36" height={h as number} rx="9" fill="#15132b" opacity="0.06" />
        <rect className="bar" x={x as number} y={100 - (h as number)} width="36" height={h as number} rx="9" fill={c as string} style={{ ['--d' as any]: `${i * 0.25}s` }} />
      </g>
    ))}
  </svg>
);

const DiffArt = () => (
  <svg viewBox="0 0 200 110" className="art">
    {[0, 1].map((side) => (
      <g key={side} transform={`translate(${side * 100}, 0)`}>
        <path d="M20 55 L50 28 M20 55 L50 82 M50 28 L80 55 M50 82 L80 55" stroke="#b4b2cc" strokeWidth="1.8" fill="none" />
        {[[20, 55], [50, 28], [80, 55], [50, 82]].map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="7" fill={side === 1 && i === 3 ? '#0fb98a' : '#4c6ef5'} className={side === 1 && i === 3 ? 'added' : ''} />
        ))}
      </g>
    ))}
    <path d="M100 18V92" stroke="#15132b" strokeOpacity="0.12" strokeDasharray="3 4" />
  </svg>
);

const TILES = [
  { art: <DagArt />, icon: 'dag', title: 'Causal DAG reconstruction', text: 'Out-of-order events become the true happens-before graph — rendered in 2D swimlanes or an orbitable 3D slab view.', span: 'wide' },
  { art: <AnomalyArt />, icon: 'anomaly', title: 'Anomaly detection', text: 'Cycles, time inversions, clock drift and duplicate events — surfaced with severity.' },
  { art: <WhatIfArt />, icon: 'whatif', title: 'What-if blast radius', text: 'Remove an event and watch the failure cascade through its descendants.' },
  { art: <RootArt />, icon: 'link', title: 'Root-cause tracing', text: 'Walk the DAG backwards from any failure to the event that started it.' },
  { art: <BenchArt />, icon: 'benchmark', title: 'Clock benchmarks', text: 'Lamport vs vector vs physical time under packet loss and drift.', span: 'wide' },
  { art: <DiffArt />, icon: 'diff', title: 'Graph diff & drift', text: 'Compare runtime topology against a baseline to catch behavioural change.' },
];

export const Features: React.FC = () => (
  <div className="feat-grid">
    {TILES.map((t, i) => (
      <Tilt key={t.title} className={`feat panel ${t.span || ''}`} max={6} style={{ ['--i' as any]: i }}>
        <div className="feat-art lift">{t.art}</div>
        <div className="feat-body">
          <div className="feat-ico"><Icon name={t.icon} size={16} /></div>
          <h4>{t.title}</h4>
          <p>{t.text}</p>
        </div>
      </Tilt>
    ))}
  </div>
);
