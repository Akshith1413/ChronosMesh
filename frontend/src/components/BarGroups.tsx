import React from 'react';

export interface BarDatum {
  key: string;
  label: string;
  color: string;
  value: number; // 0..1
  low?: number;
  high?: number;
}

interface Props {
  data: BarDatum[];
  title: string;
  height?: number;
}

/** Horizontal bars on a fixed 0–100 % axis with optional 95 % CI whiskers. Pure SVG, no dependencies. */
export const BarGroups: React.FC<Props> = ({ data, title, height }) => {
  const rowH = 38;
  const H = height ?? data.length * rowH + 34;
  const left = 132;
  const W = 560;
  const plot = W - left - 64;
  const x = (v: number) => left + Math.max(0, Math.min(1, v)) * plot;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} style={{ width: '100%', height: 'auto', display: 'block' }}>
      <title>{title}</title>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={6} y2={H - 24} stroke="currentColor" strokeOpacity={0.12} />
          <text x={x(t)} y={H - 8} textAnchor="middle" fontSize={10} fill="currentColor" fillOpacity={0.55}>{Math.round(t * 100)}%</text>
        </g>
      ))}
      {data.map((d, i) => {
        const y = 10 + i * rowH;
        return (
          <g key={d.key}>
            <text x={left - 10} y={y + 15} textAnchor="end" fontSize={12} fontWeight={d.key === 'chronosmesh' ? 700 : 500} fill="currentColor">{d.label}</text>
            <rect x={left} y={y + 3} width={plot} height={18} rx={9} fill="currentColor" fillOpacity={0.06} />
            <rect x={left} y={y + 3} width={Math.max(2, x(d.value) - left)} height={18} rx={9} fill={d.color}>
              <title>{`${d.label}: ${(d.value * 100).toFixed(1)}%`}</title>
            </rect>
            {d.low !== undefined && d.high !== undefined && d.high > d.low && (
              <g stroke="currentColor" strokeOpacity={0.7}>
                <line x1={x(d.low)} x2={x(d.high)} y1={y + 12} y2={y + 12} />
                <line x1={x(d.low)} x2={x(d.low)} y1={y + 7} y2={y + 17} />
                <line x1={x(d.high)} x2={x(d.high)} y1={y + 7} y2={y + 17} />
              </g>
            )}
            <text x={x(d.value) + 8} y={y + 16} fontSize={12} fontWeight={600} fill="currentColor">{(d.value * 100).toFixed(1)}%</text>
          </g>
        );
      })}
    </svg>
  );
};
