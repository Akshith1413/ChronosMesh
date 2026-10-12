import React, { useEffect, useState } from 'react';
import { Icon } from './Icon';
import api from '../services/api';
import { SystemStatus } from '../types';
import { PALETTE } from '../utils/colors';

const age = (s: number | null | undefined) => (s === null || s === undefined ? '—' : s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`);

/** One-line pipeline health for the overview: persistence, queue backlog and the reconstruction worker. */
export const PlatformStrip: React.FC = () => {
  const [st, setSt] = useState<SystemStatus | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.getSystemStatus().then((s) => alive && setSt(s)).catch(() => {});
    load();
    const t = window.setInterval(load, 10000);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  if (!st) return null;
  const worker = st.worker;
  const items = [
    { icon: 'shield', label: 'Storage', value: st.storage.ok ? (st.storage.backend === 'aws' ? 'DynamoDB · S3' : 'in-memory') : 'degraded', tone: st.storage.ok ? PALETTE.ok : PALETTE.crit },
    { icon: 'layers', label: 'Queue backlog', value: st.queue ? `${st.queue.visible ?? 0} msgs · oldest ${age(st.queue.oldest_message_age_seconds)}` : 'inline ingest', tone: st.queue && (st.queue.visible ?? 0) > 100 ? PALETTE.warn : PALETTE.iris2 },
    { icon: 'bolt', label: 'Reconstruction worker', value: worker ? (worker.status === 'healthy' ? `healthy · seen ${age(worker.last_heartbeat_age_seconds)} ago` : worker.status) : 'not used', tone: worker ? (worker.status === 'healthy' ? PALETTE.ok : worker.status === 'down' ? PALETTE.crit : PALETTE.mute) : PALETTE.mute },
  ];
  return (
    <div className="panel" style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'center', padding: '14px 22px' }} aria-label="Pipeline health">
      {items.map((i) => (
        <div key={i.label} className="row" style={{ gap: 10 }}>
          <span className="kpi-ico" style={{ ['--c' as any]: i.tone }}><Icon name={i.icon} size={16} /></span>
          <span><b style={{ display: 'block', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.6 }}>{i.label}</b>
            <span style={{ color: i.tone, fontWeight: 600 }}>{i.value}</span></span>
        </div>
      ))}
    </div>
  );
};
