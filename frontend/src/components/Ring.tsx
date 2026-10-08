import React from 'react';
import { useCountUp } from '../fx/hooks';

interface RingProps {
  pct: number;
  color: string;
  size?: number;
  label?: string;
  decimals?: number;
}

/** A progress ring whose arc sweeps in and whose number counts up. */
export const Ring: React.FC<RingProps> = ({ pct, color, size = 112, label, decimals = 1 }) => {
  const R = 44;
  const C = 2 * Math.PI * R;
  const shown = useCountUp(pct, 1100, decimals);
  return (
    <div className="ringw" style={{ width: size, height: size }} key={pct}>
      <svg viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={R} className="ring-track" />
        <circle
          cx="50" cy="50" r={R}
          className="ring-arc"
          stroke={color}
          strokeDasharray={C}
          style={{ ['--from' as any]: C, ['--to' as any]: C * (1 - Math.min(100, Math.max(0, pct)) / 100) }}
        />
      </svg>
      <div className="ring-center">
        <b className="num" style={{ color }}>{shown}<small>%</small></b>
        {label && <span>{label}</span>}
      </div>
    </div>
  );
};
