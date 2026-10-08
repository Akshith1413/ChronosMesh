import React from 'react';
import { User } from '../types';
import { Icon } from './Icon';

interface NavbarProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  user: User | null;
  currentScenario: string | null;
  onRefresh?: () => void;
  onOpenLogin?: () => void;
  onLogout?: () => void;
  onOpenPalette?: () => void;
  sseStatus?: 'connecting' | 'connected' | 'disconnected';
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '');

export const Navbar: React.FC<NavbarProps> = ({
  title,
  subtitle,
  eyebrow,
  user,
  currentScenario,
  onRefresh,
  onOpenLogin,
  onOpenPalette,
  sseStatus = 'connected',
}) => {
  const words = title.split(' ');
  const last = words.pop();
  const head = words.join(' ');

  const streamLabel = sseStatus === 'connected' ? 'Live stream' : sseStatus === 'connecting' ? 'Connecting' : 'Offline';
  const eqClass = sseStatus === 'connected' ? '' : sseStatus === 'connecting' ? 'warn' : 'off';

  return (
    <header className="topbar">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1 className="page-title" key={title}>
          {head && <>{head} </>}
          <em>{last}</em>
        </h1>
        {subtitle && (
          <div className="page-sub">
            {currentScenario && <span className="live-dot" />}
            {subtitle}
          </div>
        )}
      </div>

      <div className="topbar-actions">
        <button className="cmdk-btn" onClick={onOpenPalette} aria-label="Open command palette">
          <Icon name="search" size={16} />
          <span className="hint">Search or jump to…</span>
          <span className="keys">
            <span className="kbd">{isMac ? '⌘' : 'Ctrl'}</span>
            <span className="kbd">K</span>
          </span>
        </button>

        <div className="stream-pill" title={`Event stream: ${sseStatus}`}>
          <span className={`eq ${eqClass}`}>
            <i /><i /><i /><i /><i />
          </span>
          {streamLabel}
        </div>

        {onRefresh && (
          <button className="btn btn-icon" onClick={onRefresh} title="Refresh metrics" aria-label="Refresh metrics">
            <Icon name="refresh" size={17} />
          </button>
        )}

        <a className="btn" href="/api/docs" target="_blank" rel="noreferrer">
          API Docs <Icon name="external" size={14} />
        </a>

        {!user && (
          <button className="btn btn-primary" onClick={onOpenLogin}>
            <Icon name="login" size={16} /> Log in
          </button>
        )}
      </div>
    </header>
  );
};
