import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { User, Scenario } from '../types';
import { Icon, LogoMark } from './Icon';
import { getServiceColor } from '../utils/colors';

export type ViewTab = 'overview' | 'dag' | 'timeline' | 'anomaly' | 'whatif' | 'benchmark' | 'analytics' | 'diff' | 'docs';

interface SidebarProps {
  currentView: ViewTab;
  onSelectView: (view: ViewTab) => void;
  user: User | null;
  currentScenario: string | null;
  anomalyCount: number;
  onLogout: () => void;
  onOpenLogin?: () => void;
  onSelectTrace?: (traceId: string) => void;
  scenarios?: Scenario[];
}

interface NavDef {
  id: ViewTab;
  label: string;
  icon: string;
}

const GROUPS: { label: string; items: NavDef[] }[] = [
  {
    label: 'Observe',
    items: [
      { id: 'overview', label: 'Overview', icon: 'overview' },
      { id: 'dag', label: 'Causal DAG', icon: 'dag' },
      { id: 'timeline', label: 'Timeline Replay', icon: 'timeline' },
    ],
  },
  {
    label: 'Analyse',
    items: [
      { id: 'anomaly', label: 'Anomaly Center', icon: 'anomaly' },
      { id: 'whatif', label: 'What-If Lab', icon: 'whatif' },
      { id: 'benchmark', label: 'Clock Benchmark', icon: 'benchmark' },
      { id: 'analytics', label: 'Analytics', icon: 'analytics' },
      { id: 'diff', label: 'Graph Diff', icon: 'diff' },
    ],
  },
  {
    label: 'Architecture',
    items: [{ id: 'docs', label: 'System Contracts', icon: 'docs' }],
  },
];

const FALLBACK_TRACES = [
  { id: 'ecommerce_demo', label: 'TRACE-DEMO-001 · E-Commerce' },
  { id: 'order_payment_flow', label: 'T-1001 · Order Flow (Chain)' },
  { id: 'concurrent_branches', label: 'T-1002 · Pay ∥ Inventory (Fork)' },
  { id: 'diamond_pattern', label: 'T-1003 · Diamond (Fork-Join)' },
];

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  user,
  currentScenario,
  anomalyCount,
  onLogout,
  onOpenLogin,
  onSelectTrace,
  scenarios,
}) => {
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [liq, setLiq] = useState({ top: 0, h: 46 });
  const [squish, setSquish] = useState(false);

  // The liquid highlight glides (with a little squash) to whichever item is active.
  useLayoutEffect(() => {
    const el = itemRefs.current[currentView];
    if (el) setLiq({ top: el.offsetTop, h: el.offsetHeight });
  }, [currentView]);

  useEffect(() => {
    setSquish(true);
    const t = setTimeout(() => setSquish(false), 680);
    return () => clearTimeout(t);
  }, [currentView]);

  const initials = (user?.full_name || user?.username || 'G')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const traceOptions =
    scenarios && scenarios.length
      ? scenarios.map((s) => ({ id: s.id, label: `${s.trace_id || s.pattern} · ${s.name.split(/[(→]/)[0].trim()}` }))
      : FALLBACK_TRACES;

  const current = scenarios?.find((s) => s.id === currentScenario || s.trace_id === currentScenario);
  const pearlColor = current ? getServiceColor(current.services?.[0]) : currentScenario ? '#6a4cff' : undefined;

  let idx = 0;

  return (
    <aside className="dock" aria-label="Primary navigation">
      <div className="dock-brand">
        <LogoMark size={40} />
        <span className="dock-word">
          Chronos<em>Mesh</em>
        </span>
      </div>

      <div className="dock-trace">
        <div className="collapsed" title={currentScenario ? `Active trace: ${currentScenario}` : 'No trace loaded'}>
          <span className={`pearl-ind ${currentScenario ? 'on' : ''}`} style={{ ['--c' as any]: pearlColor }} />
        </div>
        <div className="expanded">
          <div className="eyebrow bare">Active trace</div>
          <select
            className="select"
            value={currentScenario || ''}
            onChange={(e) => onSelectTrace && onSelectTrace(e.target.value)}
            aria-label="Active trace"
          >
            <option value="" disabled>
              Select a trace…
            </option>
            {traceOptions.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <nav className="dock-nav">
        <i className={`dock-liquid ${squish ? 'squish' : ''}`} style={{ ['--ly' as any]: `${liq.top}px`, ['--lh' as any]: `${liq.h}px` }} />
        {GROUPS.map((g) => (
          <React.Fragment key={g.label}>
            <div className="dock-label">
              <span>{g.label}</span>
            </div>
            {g.items.map((item) => {
              const i = idx++;
              return (
                <button
                  key={item.id}
                  ref={(el) => (itemRefs.current[item.id] = el)}
                  className={`dock-item ${currentView === item.id ? 'active' : ''}`}
                  style={{ ['--i' as any]: i }}
                  onClick={() => onSelectView(item.id)}
                  aria-current={currentView === item.id ? 'page' : undefined}
                  title={item.label}
                >
                  <span className="ic">
                    <Icon name={item.icon} size={21} />
                  </span>
                  <span className="tx">{item.label}</span>
                  {item.id === 'anomaly' && anomalyCount > 0 && <span className="badge">{anomalyCount}</span>}
                </button>
              );
            })}
          </React.Fragment>
        ))}
      </nav>

      <div className="dock-user">
        <div className="avatar">{initials}</div>
        <div className="meta">
          <b>{user?.full_name || user?.username || 'Guest'}</b>
          <span>{user ? user.role || 'operator' : 'viewer · guest'}</span>
        </div>
        {user ? (
          <button className="btn btn-ghost btn-icon btn-sm out" onClick={onLogout} title="Log out" aria-label="Log out">
            <Icon name="logout" size={17} />
          </button>
        ) : (
          <button className="btn btn-ghost btn-icon btn-sm out" onClick={onOpenLogin || onLogout} title="Log in" aria-label="Log in">
            <Icon name="login" size={17} />
          </button>
        )}
      </div>
    </aside>
  );
};
