import React, { useEffect, useState } from 'react';

const KEY = 'cm_splash_seen';

const alreadySeen = () => {
  try {
    return sessionStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
};

/** A one-time, ~2.6s intro: the ring winds itself, the wordmark rises, a circular wipe reveals the page. */
export const Splash: React.FC = () => {
  const [show, setShow] = useState(() => !alreadySeen() && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

  useEffect(() => {
    if (!show) return;
    try {
      sessionStorage.setItem(KEY, '1');
    } catch {
      /* ignore */
    }
    const t = setTimeout(() => setShow(false), 2900);
    return () => clearTimeout(t);
  }, [show]);

  if (!show) return null;

  const letters = 'ChronosMesh'.split('');
  return (
    <div className="splash" aria-hidden="true">
      <div className="splash-core">
        <svg width="96" height="96" viewBox="0 0 80 80">
          <defs>
            <linearGradient id="spl" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#6a4cff" />
              <stop offset="0.55" stopColor="#2f9bff" />
              <stop offset="1" stopColor="#14d1b0" />
            </linearGradient>
          </defs>
          <circle cx="40" cy="40" r="30" fill="rgba(255,255,255,0.8)" stroke="rgba(21,19,43,0.08)" />
          <path className="ring" pathLength={100} d="M40 11a29 29 0 1 1-27.2 18.8" fill="none" stroke="url(#spl)" strokeWidth="5" strokeLinecap="round" />
          <path className="ring" pathLength={100} d="M7.2 22.4l6 9.8 9.8-5.2" fill="none" stroke="url(#spl)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          <g className="hand"><path d="M40 40V22" stroke="#15132b" strokeWidth="4.2" strokeLinecap="round" /></g>
          <circle cx="40" cy="40" r="6.4" fill="#fff" stroke="#6a4cff" strokeWidth="2" />
        </svg>
        <div className="splash-word">
          {letters.map((c, i) => (
            <span key={i} style={{ ['--k' as any]: i }}>
              {i >= 7 ? <em>{c}</em> : c}
            </span>
          ))}
        </div>
        <div className="splash-bar"><i /></div>
      </div>
    </div>
  );
};
