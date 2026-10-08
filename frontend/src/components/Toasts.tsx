import React from 'react';
import { Icon } from './Icon';

export interface ToastItem {
  id: number;
  msg: string;
  tone?: 'info' | 'warn' | 'error';
}

export const Toasts: React.FC<{ items: ToastItem[] }> = ({ items }) => (
  <div className="toasts" role="status" aria-live="polite">
    {items.map((t) => (
      <div key={t.id} className={`toast ${t.tone || 'info'}`}>
        <span className="ti">
          <Icon name={t.tone === 'error' ? 'alert' : t.tone === 'warn' ? 'warning' : 'check'} size={15} weight={2.2} />
        </span>
        <span>{t.msg}</span>
        <i className="bar" />
      </div>
    ))}
  </div>
);
