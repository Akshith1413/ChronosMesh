import React from 'react';
import { Icon } from './Icon';

/** A pulse hopping across three pearls — the app-wide loading indicator. */
export const Loader: React.FC<{ message?: string }> = ({ message = 'Loading causal data…' }) => (
  <div className="loader" role="status" aria-live="polite">
    <div className="loader-track"><i /><i /><i /><b /></div>
    <span>{message}</span>
  </div>
);

export const LoadingState: React.FC<{ message?: string }> = ({ message }) => <Loader message={message} />;

export const ErrorState: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div className="errorbox" role="alert">
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
      <Icon name="alert" size={18} />
      {message}
    </span>
    {onRetry && (
      <button className="btn btn-sm" onClick={onRetry}>
        <Icon name="refresh" size={14} /> Retry
      </button>
    )}
  </div>
);

/** Three dim nodes joined by a dashed thread — the glyph for “nothing here yet”. */
export const EmptyGlyph: React.FC = () => (
  <svg className="empty-glyph" viewBox="0 0 76 48" aria-hidden="true">
    <path className="t" d="M12 30 L38 12 L64 30" fill="none" stroke="#b4b2cc" strokeWidth="2" strokeLinecap="round" />
    <circle className="n" cx="12" cy="30" r="7" fill="#c9c2e8" />
    <circle className="n" cx="38" cy="12" r="7" fill="#b9d6ff" />
    <circle className="n" cx="64" cy="30" r="7" fill="#b6ecd8" />
  </svg>
);

export const EmptyState: React.FC<{
  icon?: string;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  compact?: boolean;
}> = ({ title, description, actionText, onAction, compact }) => (
  <div className={`empty ${compact ? 'compact' : ''}`}>
    <EmptyGlyph />
    <h4>{title}</h4>
    <p>{description}</p>
    {actionText && onAction && (
      <button onClick={onAction} className="btn btn-primary btn-sm" style={{ marginTop: 10 }}>
        {actionText}
      </button>
    )}
  </div>
);
