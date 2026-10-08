import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './Icon';

export interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: string;
  keywords?: string;
  run: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '');

export const CommandPalette: React.FC<Props> = ({ open, onClose, commands }) => {
  const [query, setQuery] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    const tokens = q.split(/\s+/);
    return commands.filter((c) => {
      const hay = `${c.label} ${c.hint || ''} ${c.group} ${c.keywords || ''}`.toLowerCase();
      return tokens.every((t) => hay.includes(t));
    });
  }, [commands, query]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSel(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => setSel(0), [query]);

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [sel]);

  if (!open) return null;

  const run = (c?: Command) => {
    if (!c) return;
    onClose();
    // let the overlay unmount before the action runs
    setTimeout(c.run, 30);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((s) => (s + 1) % Math.max(1, results.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((s) => (s - 1 + results.length) % Math.max(1, results.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      run(results[sel]);
    }
  };

  let lastGroup = '';
  return (
    <div className="cmdk-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()} onKeyDown={onKey}>
      <div className="cmdk" role="dialog" aria-label="Command palette">
        <div className="cmdk-input">
          <Icon name="search" size={20} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a view, load a trace, run an action…"
            aria-label="Search commands"
          />
          <span className="kbd">esc</span>
        </div>
        <div className="cmdk-list" ref={listRef}>
          {results.length === 0 && <div className="cmdk-empty">Nothing matches “{query}”.</div>}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? <div className="cmdk-group" key={`g-${c.group}`}>{c.group}</div> : null;
            lastGroup = c.group;
            return (
              <React.Fragment key={c.id}>
                {header}
                <button
                  data-i={i}
                  className={`cmdk-item ${i === sel ? 'sel' : ''}`}
                  onMouseMove={() => setSel(i)}
                  onClick={() => run(c)}
                >
                  <span className="ci">
                    <Icon name={c.icon} size={18} />
                  </span>
                  <span className="ct">
                    {c.label}
                    {c.hint && <small>{c.hint}</small>}
                  </span>
                  {i === sel && <Icon name="arrow" size={16} />}
                </button>
              </React.Fragment>
            );
          })}
        </div>
        <div className="cmdk-foot">
          <span><span className="kbd">↑</span><span className="kbd">↓</span> navigate</span>
          <span><span className="kbd">↵</span> select</span>
          <span style={{ marginLeft: 'auto' }}>
            <span className="kbd">{isMac ? '⌘' : 'Ctrl'}</span><span className="kbd">K</span> toggle
          </span>
        </div>
      </div>
    </div>
  );
};
