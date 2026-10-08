import React, { useEffect, useRef, useState } from 'react';
import { Icon, LogoMark } from '../components/Icon';
import { Loom3D, HERO_EVENTS } from '../components/scenes/Loom3D';
import { Shuffler } from '../components/landing/Shuffler';
import { ClockLab } from '../components/landing/ClockLab';
import { Pipeline } from '../components/landing/Pipeline';
import { Features } from '../components/landing/Features';
import { Reveal, Tilt } from '../fx/Reveal';
import { prefersReducedMotion, useMagnetic } from '../fx/hooks';

interface HomeProps {
  onOpenDashboard: () => void;
  onOpenLogin: () => void;
  isAuthenticated: boolean;
}

const NAV = [
  { href: '#problem', label: 'The Problem' },
  { href: '#clocks', label: 'Clocks' },
  { href: '#architecture', label: 'Architecture' },
  { href: '#features', label: 'Capabilities' },
];

const SCRAMBLED_L = [4, 1, 3, 2, 6, 5, 2, 4, 1, 3];
const TICK_NAMES = [
  ...HERO_EVENTS,
  { id: 'E7', name: 'NOTIFY_CUSTOMER', color: '#e64980' },
  { id: 'E8', name: 'INVENTORY_SYNC', color: '#f59f00' },
  { id: 'E9', name: 'ORDER_AUDITED', color: '#4c6ef5' },
  { id: 'E10', name: 'REFUND_ISSUED', color: '#0fb98a' },
] as { id: string; name: string; color: string }[];

const TickerRow: React.FC<{ kind: 'bad' | 'good'; reverse?: boolean }> = ({ kind, reverse }) => {
  const chips = TICK_NAMES.map((e, i) => {
    const l = kind === 'bad' ? SCRAMBLED_L[i % SCRAMBLED_L.length] : Math.floor(i / 2) + 1;
    return (
      <div className="tick-chip" key={`${e.id}-${i}`}>
        <i style={{ ['--c' as any]: e.color }} />
        {e.name}
        <span>{kind === 'bad' ? `arrived #${l}` : `L${l}`}</span>
      </div>
    );
  });
  return (
    <div className={`tick-row ${kind} ${reverse ? 'rev' : ''}`}>
      {chips}
      {chips.map((c, i) => React.cloneElement(c, { key: `dup-${i}` }))}
    </div>
  );
};

const SectionHead: React.FC<{ idx: string; eyebrow: string; title: React.ReactNode; lede?: string; center?: boolean }> = ({
  idx, eyebrow, title, lede, center,
}) => (
  <Reveal className={`sec-head ${center ? 'center' : ''}`}>
    <div className="eyebrow">{idx} — {eyebrow}</div>
    <h2 className="sec-title">{title}</h2>
    {lede && <p className="sec-lede">{lede}</p>}
  </Reveal>
);

const CLOCKS = [
  { icon: 'clock', color: '#4c6ef5', title: 'Lamport', text: 'One counter per process. If A caused B then L(A) < L(B) — but a smaller number never proves independence.', code: 'L = max(L_local, L_msg) + 1', pros: ['O(1) memory', 'Total order'], cons: ['No concurrency'] },
  { icon: 'cube', color: '#8f4cf0', title: 'Vector', text: 'One counter per node. Compare two vectors and you know for certain: before, after, or concurrent.', code: 'V[i] = max(V_local[i], V_msg[i])\nV[self] += 1', pros: ['Exact causality', 'Detects concurrency'], cons: ['O(N) memory'] },
  { icon: 'globe', color: '#0fb98a', title: 'Hybrid Logical', text: 'Physical time plus a logical counter. Stays near wall-clock while preserving causality across regions with skew.', code: 'HLC = (physical_ms, counter)\nbounded by clock uncertainty', pros: ['Human-readable', 'Skew-bounded'], cons: ['Approximate order'] },
];

export const Home: React.FC<HomeProps> = ({ onOpenDashboard, onOpenLogin, isAuthenticated }) => {
  const [orderK, setOrderK] = useState<number>(() => (prefersReducedMotion() ? 1 : 0));
  const [focus, setFocus] = useState<string | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const [progress, setProgress] = useState(0);
  const [blob, setBlob] = useState<{ x: number; w: number; on: boolean }>({ x: 0, w: 0, on: false });
  const linksRef = useRef<HTMLDivElement>(null);
  const ctaRef = useMagnetic<HTMLDivElement>(0.28, 70);
  const cta2Ref = useMagnetic<HTMLDivElement>(0.28, 70);

  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const y = window.scrollY;
        setScrolled(y > 40);
        const max = document.documentElement.scrollHeight - window.innerHeight;
        setProgress(max > 0 ? Math.min(1, y / max) : 0);
      });
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  const hoverLink = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const el = e.currentTarget;
    setBlob({ x: el.offsetLeft, w: el.offsetWidth, on: true });
  };

  const f = focus ? HERO_EVENTS.find((h) => h.id === focus) : null;
  const arrivedAt = f ? f.arrival : 0;
  const happenedAt = f ? [...HERO_EVENTS].sort((a, b) => a.lamport - b.lamport || a.id.localeCompare(b.id)).findIndex((h) => h.id === f.id) + 1 : 0;

  const titleWords = (txt: string, offset: number, em?: boolean) =>
    txt.split(' ').map((w, i) => (
      <span className="w" key={`${txt}-${i}`} style={{ ['--k' as any]: offset + i }}>
        {em ? <em>{w}</em> : w}
        {' '}
      </span>
    ));

  return (
    <div className="landing">
      {/* ── Nav ─────────────────────────────────────────────────────── */}
      <nav className={`lnav ${scrolled ? 'scrolled' : ''}`}>
        <a href="#top" className="brand-link" aria-label="ChronosMesh home">
          <LogoMark size={38} />
          <span>Chronos<em>Mesh</em></span>
        </a>
        <div className="lnav-links" ref={linksRef} onMouseLeave={() => setBlob((b) => ({ ...b, on: false }))}>
          <i className="nav-blob" style={{ left: blob.x, width: blob.w, opacity: blob.on ? 1 : 0 }} />
          {NAV.map((n) => (
            <a key={n.href} href={n.href} onMouseEnter={hoverLink} onFocus={hoverLink as any}>
              {n.label}
            </a>
          ))}
          <a href="/api/docs" target="_blank" rel="noreferrer" onMouseEnter={hoverLink}>
            API Docs
          </a>
        </div>
        <div className="lnav-end">
          {isAuthenticated ? (
            <button className="btn btn-primary" onClick={onOpenDashboard}>
              Open dashboard <Icon name="arrow" size={16} />
            </button>
          ) : (
            <button className="btn btn-primary" onClick={onOpenLogin}>
              <Icon name="login" size={16} /> Sign in
            </button>
          )}
        </div>
      </nav>

      {/* ── Lamport scroll rail ─────────────────────────────────────── */}
      <div className="rail" aria-hidden="true">
        <div className="rail-line">
          <i className="rail-fill" style={{ height: `${progress * 100}%` }} />
          <i className="rail-dot" style={{ top: `${progress * 100}%` }} />
        </div>
        <span className="rail-num num">L:{String(Math.round(progress * 99)).padStart(3, '0')}</span>
      </div>

      {/* ── Hero ────────────────────────────────────────────────────── */}
      <header className="hero" id="top">
        <Loom3D order={orderK} onFocus={setFocus} />
        <div className="hero-scrim" />

        <div className="hero-inner">
          <div className="hero-copy">
            <span className="hero-badge">
              <span className="live-dot" /> Cloud Computing PE-5 · Distributed Causality Engine
            </span>
            <h1 className="hero-title">
              <span className="line">{titleWords('Time lies.', 0)}</span>
              <span className="line">
                {titleWords('Causality', 2, true)}
                {titleWords("doesn't.", 3)}
              </span>
            </h1>
            <p className="hero-lede">
              ChronosMesh reconstructs the <b>true causal execution graph</b> from disordered event streams — using Lamport, vector and hybrid logical clocks — so you can see what happened, when, and <b>why</b>.
            </p>
            <div className="hero-cta">
              <div ref={ctaRef}>
                <button className="btn btn-primary btn-lg" onClick={onOpenDashboard}>
                  Open live dashboard <Icon name="arrow" size={18} />
                </button>
              </div>
              <div ref={cta2Ref}>
                <a className="btn btn-lg" href="#problem">
                  Why order matters
                </a>
              </div>
            </div>
            <div className="hero-hint">
              <i />
              <span className="hint-pointer">Sweep your cursor across the scattered events — watch causality reassemble.</span>
              <span className="hint-touch">Drag a finger across the scattered events — watch causality reassemble.</span>
            </div>
          </div>

          <div className="hero-stage" aria-hidden="true" />

          <div className="hero-foot">
            <div className="reconstruct" data-nopick>
              <div className="rc-top">
                <span className="eyebrow bare">Reconstruction</span>
                <b className="num">{Math.round(orderK * 100)}%</b>
              </div>
              <input
                type="range"
                className="range"
                min={0}
                max={100}
                value={Math.round(orderK * 100)}
                style={{ ['--p' as any]: `${orderK * 100}%` }}
                onChange={(e) => setOrderK(parseInt(e.target.value, 10) / 100)}
                aria-label="Reconstruct causal order"
              />
              <div className="rc-ends">
                <span>Kafka arrival</span>
                <span>Causal order</span>
              </div>
            </div>

            <div className={`focus-card ${f ? 'has' : ''}`} key={focus || 'idle'} data-nopick>
              {f ? (
                <>
                  <div className="fc-top">
                    <span className="svc-tag" style={{ ['--c' as any]: f.color }}>{f.svc}</span>
                    <span className="chip chip-ok">Lamport {f.lamport}</span>
                  </div>
                  <h4 className="mono" style={{ fontFamily: 'var(--f-mono)', fontSize: 19, fontWeight: 600 }}>{f.name}</h4>
                  <p>
                    Arrived <b>#{arrivedAt}</b> but actually happened <b>#{happenedAt}</b>
                    {f.parents.length ? <> — caused by <b>{f.parents.join(' + ')}</b>.</> : <> — the root of the whole flow.</>}
                  </p>
                </>
              ) : (
                <div className="idle">
                  <Icon name="spark" size={22} />
                  <span>Hover or click any event to see where it really belongs in time.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="scroll-cue"><span>scroll</span><i /></div>
      </header>

      {/* ── Ticker ──────────────────────────────────────────────────── */}
      <section className="ticker" aria-hidden="true">
        <div className="tick-tag"><span className="chip chip-crit">What your logs say</span></div>
        <TickerRow kind="bad" />
        <div className="tick-tag" style={{ marginTop: 22 }}><span className="chip chip-ok">What actually happened</span></div>
        <TickerRow kind="good" reverse />
      </section>

      {/* ── 01 Problem ──────────────────────────────────────────────── */}
      <section className="lsec" id="problem">
        <div className="problem-grid">
          <div>
            <Reveal className="sec-head" style={{ marginBottom: 0 }}>
              <div className="eyebrow">01 — The dilemma</div>
              <h2 className="sec-title">
                Arrival order <em>≠</em> causal order.
              </h2>
              <p className="sec-lede">
                Logs tell you when events <i className="serif">arrived</i> — not why they happened. Retries, jitter and clock skew scramble the sequence, so a child can look older than its parent.
              </p>
            </Reveal>
            <Reveal delay={120} className="facts">
              {[
                ['kafka', 'Networks reorder messages', 'Partitions, retries and latency deliver events out of sequence.'],
                ['clock', 'Physical clocks drift', 'Wall-clock time differs across machines and regions — it can’t be compared.'],
                ['dag', 'Concurrency has no order', 'Independent events are neither before nor after each other.'],
              ].map(([ic, t, d]) => (
                <div className="fact" key={t}>
                  <span className="fi"><Icon name={ic} size={18} /></span>
                  <div><b>{t}</b><span>{d}</span></div>
                </div>
              ))}
            </Reveal>
          </div>
          <Reveal delay={150}>
            <Shuffler />
          </Reveal>
        </div>
      </section>

      {/* ── 02 Clocks ───────────────────────────────────────────────── */}
      <section className="lsec" id="clocks">
        <SectionHead
          idx="02"
          eyebrow="Logical time"
          title={<>Three clocks. <em>One truth.</em></>}
          lede="Build a distributed execution yourself: add events, send messages between processes, then hover any event. Vector clocks tell you exactly what happened-before it, what came after, and what ran concurrently."
        />
        <Reveal delay={80}>
          <ClockLab />
        </Reveal>
        <div className="clock-cards">
          {CLOCKS.map((c, i) => (
            <Reveal key={c.title} delay={i * 110}>
              <Tilt className="cc panel solid" style={{ ['--c' as any]: c.color }}>
                <div className="cc-ico lift"><Icon name={c.icon} size={22} /></div>
                <h4>{c.title}</h4>
                <p>{c.text}</p>
                <pre>{c.code}</pre>
                <div className="tradeoff">
                  {c.pros.map((p) => <span key={p} className="chip chip-ok lower">{p}</span>)}
                  {c.cons.map((p) => <span key={p} className="chip chip-warn lower">{p}</span>)}
                </div>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── 03 Architecture ─────────────────────────────────────────── */}
      <section className="lsec" id="architecture">
        <SectionHead
          idx="03"
          eyebrow="System architecture"
          title={<>From raw stream to <em>causal insight.</em></>}
          lede="A seven-stage pipeline turns scrambled microservice events into a queryable causal graph. Hover a stage to see what it does."
        />
        <Reveal delay={80}>
          <Pipeline />
        </Reveal>
      </section>

      {/* ── 04 Capabilities ─────────────────────────────────────────── */}
      <section className="lsec" id="features">
        <SectionHead
          idx="04"
          eyebrow="Capabilities"
          title={<>Everything you need to <em>debug time.</em></>}
          center
        />
        <Reveal delay={60}>
          <Features />
        </Reveal>
      </section>

      {/* ── Closing ─────────────────────────────────────────────────── */}
      <section className="closing">
        <Reveal>
          <div className="closing-card">
            <div className="orbit-deco" aria-hidden="true">
              <i style={{ ['--c' as any]: '#9d8cff', width: 74, height: 74, left: '7%', top: '16%' }} />
              <i style={{ ['--c' as any]: '#5fe3c0', width: 40, height: 40, right: '10%', top: '20%', animationDelay: '-2s' }} />
              <i style={{ ['--c' as any]: '#ffb69a', width: 54, height: 54, right: '16%', bottom: '14%', animationDelay: '-4s' }} />
              <i style={{ ['--c' as any]: '#6fc3ff', width: 30, height: 30, left: '16%', bottom: '18%', animationDelay: '-1s' }} />
            </div>
            <h2>
              See the order <em>beneath</em> the chaos.
            </h2>
            <p>Load a trace, reconstruct its causal DAG, and step through exactly how a distributed workflow unfolded.</p>
            <div className="btns">
              <button className="btn btn-light btn-lg" onClick={onOpenDashboard}>
                Open live dashboard <Icon name="arrow" size={18} />
              </button>
              <a className="btn btn-lg" href="/api/docs" target="_blank" rel="noreferrer">
                Read the API docs <Icon name="external" size={16} />
              </a>
            </div>
          </div>
        </Reveal>
      </section>

      <footer className="lfoot">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <LogoMark size={28} spin={false} />
          <span>ChronosMesh — Cloud Computing PE-5 Project</span>
        </div>
        <div className="team">
          <span><i style={{ ['--c' as any]: '#4c6ef5' }} /> Akshith · Core Engine</span>
          <span><i style={{ ['--c' as any]: '#0fb98a' }} /> Surya · Data Layer</span>
          <span style={{ color: 'var(--ink)', fontWeight: 600 }}><i style={{ ['--c' as any]: '#6a4cff' }} /> Guru · API &amp; Frontend</span>
        </div>
      </footer>
    </div>
  );
};
