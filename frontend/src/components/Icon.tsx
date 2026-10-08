import React from 'react';

/** Hand-drawn 24px line icons. Stroke follows currentColor so they theme for free. */
const PATHS: Record<string, React.ReactNode> = {
  overview: (
    <>
      <circle cx="6" cy="6.5" r="2.4" />
      <circle cx="18" cy="8" r="2.4" />
      <circle cx="11.5" cy="18" r="2.4" />
      <path d="M8.2 7l7.5.8M7.2 8.6l3.2 7.2M16.9 10.2l-4 5.9" />
    </>
  ),
  dag: (
    <>
      <circle cx="5" cy="12" r="2.1" />
      <circle cx="12.5" cy="5.8" r="2.1" />
      <circle cx="12.5" cy="18.2" r="2.1" />
      <circle cx="19.5" cy="12" r="2.1" />
      <path d="M6.7 10.8l4.2-3.8M6.7 13.2l4.2 3.8M14.2 7l3.6 3.8M14.2 17l3.6-3.8" />
    </>
  ),
  timeline: (
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.7-6.2" />
      <path d="M3.2 4.2v4.2h4.2" />
      <path d="M12 7.8V12l3 1.8" />
    </>
  ),
  anomaly: <path d="M3 12h4l2.6-6.5 4.2 13 2.6-6.5H21" />,
  whatif: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.2" />
      <circle cx="12" cy="12" r="0.9" fill="currentColor" />
    </>
  ),
  benchmark: (
    <>
      <path d="M4.2 17a8.2 8.2 0 1 1 15.6 0" />
      <path d="M12 14.2l4-4.4" />
      <circle cx="12" cy="14.4" r="1.3" />
    </>
  ),
  analytics: <path d="M5 20v-8.5M12 20V4M19 20v-6" />,
  diff: (
    <>
      <circle cx="7" cy="5.5" r="2" />
      <circle cx="17" cy="18.5" r="2" />
      <path d="M7 7.5v6a4 4 0 0 0 4 4h4M17 16.5v-6a4 4 0 0 0-4-4H9.5" />
    </>
  ),
  docs: (
    <>
      <path d="M5 4.7A1.7 1.7 0 0 1 6.7 3H19v14.5H6.7A1.7 1.7 0 0 0 5 19.2z" />
      <path d="M5 19.2A1.8 1.8 0 0 0 6.7 21H19v-3.5M9 7.5h6M9 11h4" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.6" />
      <path d="M16 16l4.5 4.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11.2A8 8 0 1 0 17.7 17" />
      <path d="M20.2 4.2v7h-7" />
    </>
  ),
  logout: (
    <>
      <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" />
      <path d="M9.5 8L5.5 12l4 4M5.5 12H15" />
    </>
  ),
  login: (
    <>
      <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4" />
      <path d="M14.5 8l4 4-4 4M18.5 12H9" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.2" r="3.8" />
      <path d="M4.5 20c.8-4 4-6 7.5-6s6.7 2 7.5 6" />
    </>
  ),
  play: <path d="M8 5.2v13.6L19 12z" fill="currentColor" />,
  pause: (
    <>
      <rect x="6.5" y="5" width="4" height="14" rx="1.4" fill="currentColor" />
      <rect x="13.5" y="5" width="4" height="14" rx="1.4" fill="currentColor" />
    </>
  ),
  reset: (
    <>
      <path d="M4 12a8 8 0 1 1 2.5 5.8" />
      <path d="M4 18.4v-5.2h5.2" />
    </>
  ),
  stepback: <path d="M18 5.5v13L8.5 12zM6 5.5v13" />,
  stepfwd: <path d="M6 5.5v13L15.5 12zM18 5.5v13" />,
  zoomin: (
    <>
      <circle cx="11" cy="11" r="6.6" />
      <path d="M16 16l4.5 4.5M11 8v6M8 11h6" />
    </>
  ),
  zoomout: (
    <>
      <circle cx="11" cy="11" r="6.6" />
      <path d="M16 16l4.5 4.5M8 11h6" />
    </>
  ),
  fit: <path d="M4 9V5h4M20 9V5h-4M4 15v4h4M20 15v4h-4" />,
  cube: (
    <>
      <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
      <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
    </>
  ),
  layers: (
    <>
      <path d="M12 4l9 5-9 5-9-5z" />
      <path d="M3 14l9 5 9-5" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6L6 18" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowup: <path d="M12 19V5M6 11l6-6 6 6" />,
  bolt: <path d="M13 3L5 13.6h6L10 21l9-11h-6z" />,
  check: <path d="M5 12.6l4.5 4.5L19 7.6" />,
  command: (
    <path d="M9 9h6v6H9zM9 9V6.5A2.5 2.5 0 1 0 6.5 9H9zM15 9V6.5A2.5 2.5 0 1 1 17.5 9H15zM9 15v2.5A2.5 2.5 0 1 1 6.5 15H9zM15 15v2.5A2.5 2.5 0 1 0 17.5 15H15z" />
  ),
  shield: (
    <>
      <path d="M12 3l7 3v5.2c0 4.8-3 8.3-7 9.8-4-1.5-7-5-7-9.8V6z" />
      <path d="M9 12l2.2 2.2L15.2 10.2" />
    </>
  ),
  inbox: <path d="M4 13l2-8h12l2 8M4 13v6h16v-6M4 13h5l1 2.2h4L15 13h5" />,
  globe: (
    <>
      <circle cx="12" cy="12" r="8.6" />
      <path d="M3.4 12h17.2M12 3.4c3.2 3.2 3.2 14 0 17.2M12 3.4c-3.2 3.2-3.2 14 0 17.2" />
    </>
  ),
  gauge: (
    <>
      <circle cx="12" cy="12" r="8.6" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  alert: (
    <>
      <path d="M12 3.5l9 16H3z" />
      <path d="M12 10v4.2M12 17.2v.1" />
    </>
  ),
  warning: (
    <>
      <circle cx="12" cy="12" r="8.6" />
      <path d="M12 7.8v5M12 16v.1" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.6" />
      <path d="M12 11v5.2M12 7.8v.1" />
    </>
  ),
  spark: <path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6zM18.5 16l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z" />,
  flask: (
    <>
      <path d="M9.5 3.5h5M10.5 3.5v5.8L5 19a1.6 1.6 0 0 0 1.4 2.4h11.2A1.6 1.6 0 0 0 19 19l-5.5-9.7V3.5" />
      <path d="M7.5 15.5h9" />
    </>
  ),
  link: (
    <>
      <path d="M10 14a4 4 0 0 0 5.6 0l3-3a4 4 0 0 0-5.6-5.6l-1 1" />
      <path d="M14 10a4 4 0 0 0-5.6 0l-3 3a4 4 0 0 0 5.6 5.6l1-1" />
    </>
  ),
  chevron: <path d="M9 5l7 7-7 7" />,
  external: <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />,
  drag: (
    <>
      <circle cx="9" cy="6" r="1.2" fill="currentColor" />
      <circle cx="15" cy="6" r="1.2" fill="currentColor" />
      <circle cx="9" cy="12" r="1.2" fill="currentColor" />
      <circle cx="15" cy="12" r="1.2" fill="currentColor" />
      <circle cx="9" cy="18" r="1.2" fill="currentColor" />
      <circle cx="15" cy="18" r="1.2" fill="currentColor" />
    </>
  ),
  pin: <path d="M12 21v-7M8 4h8l-1.2 5.4 2.7 3.1H6.5l2.7-3.1z" />,
  kafka: (
    <>
      <circle cx="6" cy="12" r="2.2" />
      <circle cx="17.5" cy="6" r="2.2" />
      <circle cx="17.5" cy="18" r="2.2" />
      <path d="M8 11l7.5-4M8 13l7.5 4" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.6" />
      <path d="M12 7v5l3.2 2" />
    </>
  ),
  db: (
    <>
      <ellipse cx="12" cy="6" rx="7" ry="2.8" />
      <path d="M5 6v6c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8V6M5 12v6c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8v-6" />
    </>
  ),
  server: (
    <>
      <rect x="4" y="4" width="16" height="6.5" rx="2" />
      <rect x="4" y="13.5" width="16" height="6.5" rx="2" />
      <path d="M8 7.2h.1M8 16.8h.1" />
    </>
  ),
  trash: <path d="M5 7h14M10 4h4M7 7l.8 12h8.4L17 7M10.5 11v5M13.5 11v5" />,
};

interface IconProps extends React.SVGProps<SVGSVGElement> {
  name: string;
  size?: number;
  weight?: number;
}

export const Icon: React.FC<IconProps> = ({ name, size = 18, weight = 1.7, ...rest }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={weight}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...rest}
  >
    {PATHS[name] ?? PATHS.spark}
  </svg>
);

/** The ChronosMesh mark: an iridescent ring being re-wound, with a ticking hand. */
export const LogoMark: React.FC<{ size?: number; spin?: boolean }> = ({ size = 34, spin = true }) => {
  const id = React.useId().replace(/:/g, '');
  return (
    <svg className={`logo-mark ${spin ? 'spin' : ''}`} width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id={`lg${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6a4cff" />
          <stop offset="0.55" stopColor="#2f9bff" />
          <stop offset="1" stopColor="#14d1b0" />
        </linearGradient>
        <radialGradient id={`lp${id}`} cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#fff" />
          <stop offset="0.5" stopColor="#d9d2ff" />
          <stop offset="1" stopColor="#6a4cff" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="15" fill="rgba(255,255,255,0.7)" stroke="rgba(21,19,43,0.08)" />
      <g className="logo-ring" style={{ transformOrigin: '20px 20px' }}>
        <path d="M20 5.5a14.5 14.5 0 1 1-13.6 9.4" fill="none" stroke={`url(#lg${id})`} strokeWidth="3" strokeLinecap="round" />
        <path d="M3.6 11.2l3 4.9 4.9-2.6" fill="none" stroke={`url(#lg${id})`} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <g className="logo-hand" style={{ transformOrigin: '20px 20px' }}>
        <path d="M20 20V11.5" stroke="#15132b" strokeWidth="2.2" strokeLinecap="round" />
      </g>
      <circle cx="20" cy="20" r="3.4" fill={`url(#lp${id})`} stroke="#fff" strokeWidth="1" />
    </svg>
  );
};
