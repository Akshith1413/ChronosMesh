import React, { useEffect, useState } from 'react';
import { Icon, LogoMark } from './Icon';
import { useTilt } from '../fx/hooks';

interface Props {
  open: boolean;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (username: string, password: string) => void;
}

const ORBS = [
  { c: '#9d8cff', s: 90, x: '8%', y: '14%', d: '0s' },
  { c: '#6fc3ff', s: 54, x: '84%', y: '18%', d: '-2s' },
  { c: '#ffb69a', s: 70, x: '14%', y: '74%', d: '-4s' },
  { c: '#5fe3c0', s: 46, x: '80%', y: '70%', d: '-1s' },
  { c: '#f59bc2', s: 28, x: '48%', y: '8%', d: '-3s' },
];

export const LoginModal: React.FC<Props> = ({ open, loading, error, onClose, onSubmit }) => {
  const [username, setUsername] = useState('guru');
  const [password, setPassword] = useState('chronosmesh');
  const [shake, setShake] = useState(false);
  const tiltRef = useTilt<HTMLDivElement>(4);

  useEffect(() => {
    if (!error) return;
    setShake(true);
    const t = setTimeout(() => setShake(false), 520);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-orbs" aria-hidden="true">
        {ORBS.map((o, i) => (
          <i key={i} style={{ ['--c' as any]: o.c, width: o.s, height: o.s, left: o.x, top: o.y, animationDelay: o.d }} />
        ))}
      </div>

      <div ref={tiltRef} className={`modal-card tilt ${shake ? 'shake' : ''}`} role="dialog" aria-label="Sign in">
        <button className="btn btn-ghost btn-icon btn-sm modal-close" onClick={onClose} aria-label="Close">
          <Icon name="close" size={16} />
        </button>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <LogoMark size={52} />
        </div>
        <h2 className="modal-title">
          Welcome <em className="gradient-text">back</em>
        </h2>
        <p className="modal-sub">Sign in to read the causal order of your distributed system.</p>

        {error && <div className="login-error">{error}</div>}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit(username, password);
          }}
          className="stack"
          style={{ gap: 14 }}
        >
          <div className="field">
            <label htmlFor="cm-user">Username</label>
            <input id="cm-user" className="input" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </div>
          <div className="field">
            <label htmlFor="cm-pass">Password</label>
            <input id="cm-pass" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button type="submit" className="btn btn-primary btn-lg" disabled={loading} style={{ marginTop: 6 }}>
            {loading ? 'Signing in…' : (<>Sign in <Icon name="arrow" size={17} /></>)}
          </button>
        </form>

        <div className="demo-access">
          <div className="eyebrow bare">Quick demo access</div>
          <div className="demo-pair">
            <button type="button" className="demo-btn" onClick={() => onSubmit('guru', 'chronosmesh')}>
              <span className="avatar" style={{ width: 32, height: 32 }}>G</span>
              <span><b>Admin</b><small>guru</small></span>
            </button>
            <button type="button" className="demo-btn" onClick={() => onSubmit('demo', 'demo123')}>
              <span className="avatar" style={{ width: 32, height: 32, background: 'linear-gradient(135deg,#8b89a8,#b4b2cc)' }}>D</span>
              <span><b>Viewer</b><small>demo</small></span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
