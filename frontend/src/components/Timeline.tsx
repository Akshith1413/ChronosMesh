import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Event } from '../types';
import { Icon } from './Icon';
import { Segmented } from './Segmented';
import { EmptyState } from './LoadingState';
import { getServiceColor, getServiceLabel } from '../utils/colors';

interface TimelineProps {
  arrivalEvents: Event[];
  causalEvents: Event[];
  selectedEventId?: string | null;
  onSelectEvent?: (eventId: string) => void;
  onStepChange?: (step: number) => void;
}

const ROW = 70;      // vertical pitch of a row (card 58 + gap 12)
const CARD = 58;
const BRAID_W = 150; // width of the thread gutter between the two columns

type Speed = '0.5' | '1' | '2';
const INTERVAL: Record<Speed, number> = { '0.5': 1500, '1': 850, '2': 420 };

/**
 * Replay as a braid: every event has a thread from where it *arrived* to where it *happened*.
 * The tangle between the two columns is the reordering ChronosMesh performed.
 */
export const Timeline: React.FC<TimelineProps> = ({
  arrivalEvents,
  causalEvents,
  selectedEventId,
  onSelectEvent,
  onStepChange,
}) => {
  const totalEvents = Math.max(arrivalEvents.length, causalEvents.length);
  const [currentStep, setCurrentStep] = useState<number>(totalEvents);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<Speed>('1');
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [localSel, setLocalSel] = useState<string | null>(null);
  const timerRef = useRef<any>(null);
  const selected = selectedEventId ?? localSel;

  useEffect(() => {
    setCurrentStep(totalEvents);
  }, [totalEvents]);

  useEffect(() => {
    onStepChange?.(currentStep);
  }, [currentStep, onStepChange]);

  useEffect(() => {
    if (!isPlaying) return;
    timerRef.current = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= totalEvents) {
          setIsPlaying(false);
          return totalEvents;
        }
        return prev + 1;
      });
    }, INTERVAL[speed]);
    return () => clearInterval(timerRef.current);
  }, [isPlaying, totalEvents, speed]);

  const arrIdx = useMemo(() => Object.fromEntries(arrivalEvents.map((e, i) => [e.event_id, i])), [arrivalEvents]);
  const causIdx = useMemo(() => Object.fromEntries(causalEvents.map((e, i) => [e.event_id, i])), [causalEvents]);
  const nameOf = useMemo(() => Object.fromEntries(causalEvents.concat(arrivalEvents).map((e) => [e.event_id, e.event_type])), [arrivalEvents, causalEvents]);
  const moved = useMemo(
    () => arrivalEvents.filter((e) => arrIdx[e.event_id] !== causIdx[e.event_id]).length,
    [arrivalEvents, arrIdx, causIdx]
  );

  if (totalEvents === 0) {
    return (
      <EmptyState
        title="Nothing to replay yet"
        description="Load a trace from the overview or the dock, then come back to scrub through how its events arrived versus how they happened."
      />
    );
  }

  const handlePlayPause = () => {
    if (isPlaying) setIsPlaying(false);
    else {
      if (currentStep >= totalEvents) setCurrentStep(1);
      setIsPlaying(true);
    }
  };
  const reset = () => { setIsPlaying(false); setCurrentStep(1); };
  const step = (d: number) => { setIsPlaying(false); setCurrentStep((s) => Math.min(totalEvents, Math.max(1, s + d))); };
  const pick = (id: string) => { setLocalSel(id); onSelectEvent?.(id); };

  const pct = totalEvents ? currentStep / totalEvents : 0;
  const R = 27;
  const C = 2 * Math.PI * R;
  const focusId = hoverId || selected;
  const height = totalEvents * ROW;

  const sel = selected ? arrivalEvents.find((e) => e.event_id === selected) || causalEvents.find((e) => e.event_id === selected) : null;
  const selDelta = sel ? causIdx[sel.event_id] - arrIdx[sel.event_id] : 0;

  return (
    <>
      {/* Transport */}
      <div className="panel transport">
        <button className={`play-ring ${isPlaying ? 'on' : ''}`} onClick={handlePlayPause} aria-label={isPlaying ? 'Pause replay' : 'Play replay'}>
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <circle cx="32" cy="32" r={R} className="trk" />
            <circle cx="32" cy="32" r={R} className="prg" strokeDasharray={C} strokeDashoffset={C * (1 - pct)} />
          </svg>
          <Icon name={isPlaying ? 'pause' : 'play'} size={22} />
        </button>

        <div className="transport-main">
          <div className="spread">
            <div>
              <div className="eyebrow">Causal replay</div>
              <div className="transport-step num">
                Step <b>{currentStep}</b> <span>of {totalEvents}</span>
              </div>
            </div>
            <div className="row">
              <button className="btn btn-icon btn-sm" onClick={() => step(-1)} aria-label="Previous step"><Icon name="stepback" size={15} /></button>
              <button className="btn btn-icon btn-sm" onClick={() => step(1)} aria-label="Next step"><Icon name="stepfwd" size={15} /></button>
              <button className="btn btn-icon btn-sm" onClick={reset} aria-label="Reset replay"><Icon name="reset" size={15} /></button>
              <Segmented<Speed>
                ariaLabel="Playback speed"
                value={speed}
                onChange={setSpeed}
                options={[
                  { value: '0.5', label: '0.5×' },
                  { value: '1', label: '1×' },
                  { value: '2', label: '2×' },
                ]}
              />
            </div>
          </div>

          <div className="scrub">
            <input
              type="range"
              className="range"
              min={1}
              max={totalEvents || 1}
              value={currentStep}
              style={{ ['--p' as any]: `${totalEvents > 1 ? ((currentStep - 1) / (totalEvents - 1)) * 100 : 100}%` }}
              onChange={(e) => {
                setIsPlaying(false);
                setCurrentStep(parseInt(e.target.value, 10));
              }}
              aria-label="Replay progress"
            />
            <div className="scrub-ticks">
              {causalEvents.map((e, i) => (
                <i key={e.event_id} style={{ background: getServiceColor(e.service_id), opacity: i < currentStep ? 1 : 0.25 }} title={e.event_type} />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Braid */}
      <div className="panel braid-panel">
        <div className="panel-head" style={{ marginBottom: 14 }}>
          <div>
            <div className="eyebrow">Arrival vs causality</div>
            <h3 className="panel-title" style={{ marginTop: 10 }}>Where each event arrived — and where it really belongs</h3>
            <p className="panel-sub">Hover or click an event to follow its thread across the braid.</p>
          </div>
          <div className="row">
            <span className="chip chip-crit"><span className="dot" /> {moved} of {arrivalEvents.length} out of order</span>
            <span className="chip chip-ok"><span className="dot" /> topologically verified</span>
          </div>
        </div>

        <div className="braid" style={{ ['--w' as any]: `${BRAID_W}px` }}>
          <div className="braid-col">
            <div className="braid-head bad">
              <b>Raw arrival order</b>
              <span>Kafka · out-of-order &amp; jittered</span>
            </div>
            <div style={{ height }}>
              {arrivalEvents.map((e, i) => {
                const vis = i < currentStep;
                const delta = causIdx[e.event_id] - i;
                const isF = focusId === e.event_id;
                return (
                  <div
                    key={e.event_id}
                    className={`brow bad ${vis ? 'vis' : 'hid'} ${isF ? 'focus' : ''} ${focusId && !isF ? 'faded' : ''} ${isPlaying && i === currentStep - 1 ? 'fresh' : ''}`}
                    style={{ top: i * ROW, height: CARD, ['--c' as any]: getServiceColor(e.service_id) }}
                    onMouseEnter={() => setHoverId(e.event_id)}
                    onMouseLeave={() => setHoverId(null)}
                    onClick={() => pick(e.event_id)}
                  >
                    <span className="bseq num">#{i + 1}</span>
                    <div className="grow">
                      <b>{e.event_type}</b>
                      <small>
                        {getServiceLabel(e.service_id)} · arr {Math.round(e.arrival_time_ms ?? 0)}ms · L{e.lamport_ts}
                      </small>
                    </div>
                    {delta !== 0 && (
                      <span className={`chip lower ${delta < 0 ? 'chip-warn' : 'chip-info'}`}>
                        {delta < 0 ? '↑' : '↓'} {Math.abs(delta)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <svg className="braid-svg" width={BRAID_W} height={height + 62} viewBox={`0 0 ${BRAID_W} ${height + 62}`} aria-hidden="true">
            <g transform="translate(0,62)">
              {arrivalEvents.map((e) => {
                const a = arrIdx[e.event_id], c = causIdx[e.event_id];
                if (a === undefined || c === undefined) return null;
                const ya = a * ROW + CARD / 2, yc = c * ROW + CARD / 2;
                const vis = a < currentStep && c < currentStep;
                const isF = focusId === e.event_id;
                const color = getServiceColor(e.service_id);
                return (
                  <g key={e.event_id}>
                    <path
                      className={`thread ${vis ? 'on' : ''} ${a !== c ? 'cross' : ''} ${isF ? 'focus' : ''} ${focusId && !isF ? 'faded' : ''}`}
                      d={`M0,${ya} C${BRAID_W * 0.55},${ya} ${BRAID_W * 0.45},${yc} ${BRAID_W},${yc}`}
                      stroke={color}
                      pathLength={1}
                    />
                    <circle cx={0} cy={ya} r={4} fill={color} className={`tnode ${vis ? 'on' : ''}`} />
                    <circle cx={BRAID_W} cy={yc} r={4} fill={color} className={`tnode ${vis ? 'on' : ''}`} />
                  </g>
                );
              })}
            </g>
          </svg>

          <div className="braid-col">
            <div className="braid-head good">
              <b>Reconstructed causal order</b>
              <span>Topologically verified</span>
            </div>
            <div style={{ height }}>
              {causalEvents.map((e, i) => {
                const vis = i < currentStep;
                const isF = focusId === e.event_id;
                return (
                  <div
                    key={e.event_id}
                    className={`brow good ${vis ? 'vis' : 'hid'} ${isF ? 'focus' : ''} ${focusId && !isF ? 'faded' : ''} ${isPlaying && i === currentStep - 1 ? 'fresh' : ''}`}
                    style={{ top: i * ROW, height: CARD, ['--c' as any]: getServiceColor(e.service_id) }}
                    onMouseEnter={() => setHoverId(e.event_id)}
                    onMouseLeave={() => setHoverId(null)}
                    onClick={() => pick(e.event_id)}
                  >
                    <span className="bseq num">#{i + 1}</span>
                    <div className="grow">
                      <b>{e.event_type}</b>
                      <small>
                        {getServiceLabel(e.service_id)} · L{e.lamport_ts}
                        {e.parent_event_ids?.length > 0 && ` · ← ${e.parent_event_ids.map((p) => (nameOf[p] || p).replace(/_/g, ' ').toLowerCase()).join(', ')}`}
                      </small>
                    </div>
                    <span className="chip chip-ok lower num">L{e.lamport_ts}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {sel && (
          <div className="braid-inspect" key={sel.event_id}>
            <span className="svc-tag" style={{ ['--c' as any]: getServiceColor(sel.service_id) }}>{getServiceLabel(sel.service_id)}</span>
            <b className="mono">{sel.event_type}</b>
            <span className="muted">
              arrived <b>#{arrIdx[sel.event_id] + 1}</b> · happened <b>#{causIdx[sel.event_id] + 1}</b>
              {selDelta === 0 ? ' — already in order' : ` — moved ${Math.abs(selDelta)} place${Math.abs(selDelta) > 1 ? 's' : ''} ${selDelta < 0 ? 'earlier' : 'later'}`}
            </span>
          </div>
        )}
      </div>
    </>
  );
};
