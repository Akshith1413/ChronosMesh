import React from 'react';
import { Icon } from './Icon';
import { useCountUp, useTilt } from '../fx/hooks';

interface MetricCardProps {
  icon: string;
  label: string;
  value: string | number;
  color?: string;
  subValue?: string;
  decimals?: number;
}

/** A stat tile that counts up, leans toward the cursor and glows in its accent colour. */
export const MetricCard: React.FC<MetricCardProps> = ({
  icon,
  label,
  value,
  color = '#6a4cff',
  subValue,
  decimals = 0,
}) => {
  const ref = useTilt<HTMLDivElement>(8);
  const numeric = typeof value === 'number' && Number.isFinite(value);
  const counted = useCountUp(numeric ? (value as number) : 0, 1100, decimals);

  return (
    <div ref={ref} className="kpi tilt spot" style={{ ['--c' as any]: color }}>
      <i className="kpi-glow" />
      <div className="kpi-top lift">
        <span className="kpi-ico">
          <Icon name={icon} size={17} />
        </span>
      </div>
      <div className={`kpi-val num ${numeric ? '' : 'word'}`} style={!numeric ? { color } : undefined}>
        {numeric ? counted : value}
      </div>
      <div className="kpi-label">{label}</div>
      {subValue && <div className="kpi-sub">{subValue}</div>}
    </div>
  );
};
