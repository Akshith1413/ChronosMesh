import React, { useState } from 'react';
import { BenchmarkReport, ClockBenchmarkResult } from '../types';
import { Icon } from './Icon';
import { Ring } from './Ring';
import { Tilt } from '../fx/Reveal';
import { PALETTE } from '../utils/colors';

interface BenchmarkPanelProps {
  report: BenchmarkReport | null;
  loading: boolean;
  onRunBenchmark: (packetLossPct: number, clockDriftMs: number) => void;
}

const META: Record<string, { name: string; color: string; desc: string; icon: string }> = {
  vector_clock: {
    name: 'Vector clocks',
    color: PALETTE.iris1,
    desc: 'Full causal precision with concurrent-event detection. Memory scales O(N) per node.',
    icon: 'cube',
  },
  lamport_clock: {
    name: 'Lamport clocks',
    color: PALETTE.iris2,
    desc: 'A compact counter giving total causal order, but unable to distinguish concurrency.',
    icon: 'clock',
  },
  physical_time: {
    name: 'Physical clock / NTP',
    color: PALETTE.warn,
    desc: 'Wall-clock timestamps — vulnerable to network jitter, drift and time inversions.',
    icon: 'globe',
  },
};

export const BenchmarkPanel: React.FC<BenchmarkPanelProps> = ({ report, loading, onRunBenchmark }) => {
  const [packetLoss, setPacketLoss] = useState<number>(0);
  const [clockDrift, setClockDrift] = useState<number>(0);

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <div>
            <div className="eyebrow">Empirical benchmark</div>
            <h3 className="panel-title" style={{ marginTop: 10 }}>Clock strategy comparison</h3>
            <p className="panel-sub">Lamport vs vector vs physical clocks under simulated network degradation. Dial in the conditions, then race them.</p>
          </div>
          <button className="btn btn-primary" onClick={() => onRunBenchmark(packetLoss, clockDrift)} disabled={loading}>
            {loading ? 'Benchmarking…' : <><Icon name="bolt" size={16} /> Run benchmark</>}
          </button>
        </div>

        <div className="dials">
          <div className="dial" style={{ ['--c' as any]: PALETTE.crit }}>
            <div className="spread">
              <span className="label">Simulated packet loss</span>
              <b className="dial-val num">{packetLoss}<small>%</small></b>
            </div>
            <input
              type="range"
              className="range"
              min={0}
              max={30}
              value={packetLoss}
              style={{ ['--p' as any]: `${(packetLoss / 30) * 100}%`, ['--c' as any]: PALETTE.crit }}
              onChange={(e) => setPacketLoss(parseInt(e.target.value))}
              aria-label="Packet loss percent"
            />
            <div className="dial-ends"><span>0%</span><span>30%</span></div>
          </div>
          <div className="dial" style={{ ['--c' as any]: PALETTE.warn }}>
            <div className="spread">
              <span className="label">Simulated clock drift</span>
              <b className="dial-val num">{clockDrift}<small>ms</small></b>
            </div>
            <input
              type="range"
              className="range"
              min={0}
              max={200}
              step={10}
              value={clockDrift}
              style={{ ['--p' as any]: `${(clockDrift / 200) * 100}%`, ['--c' as any]: PALETTE.warn }}
              onChange={(e) => setClockDrift(parseInt(e.target.value))}
              aria-label="Clock drift milliseconds"
            />
            <div className="dial-ends"><span>0 ms</span><span>200 ms</span></div>
          </div>
        </div>
      </div>

      {report && (
        <div className="grid-3 stagger bench-cards" key={`${report.parameters?.packet_loss_pct}-${report.parameters?.clock_drift_ms}-${report.winner}`}>
          {report.results.map((res: ClockBenchmarkResult, i) => {
            const meta = META[res.strategy] || { name: res.strategy, color: PALETTE.mute, desc: '', icon: 'gauge' };
            const isWinner = res.strategy === report.winner;
            return (
              <Tilt key={res.strategy} className={`bench panel ${isWinner ? 'winner' : ''}`} style={{ ['--c' as any]: meta.color, ['--i' as any]: i }} max={6}>
                {isWinner && <span className="crown lift"><Icon name="spark" size={13} /> Top strategy</span>}
                <div className="bench-head lift">
                  <span className="bench-ico"><Icon name={meta.icon} size={20} /></span>
                  <div>
                    <b>{meta.name}</b>
                    <small>{meta.desc}</small>
                  </div>
                </div>

                <div className="bench-ring lift">
                  <Ring pct={res.accuracy_pct} color={meta.color} size={132} label="accuracy" />
                </div>

                <div className="bench-metrics">
                  <div><span>Memory</span><b className="num">{res.memory_kb} KB</b></div>
                  <div><span>Compute</span><b className="num">{res.computation_time_ms} ms</b></div>
                  <div><span>Correct pairs</span><b className="num" style={{ color: '#087a5a' }}>{res.correct_orderings}/{res.total_orderings}</b></div>
                  <div><span>False positives</span><b className="num" style={{ color: res.false_positives > 0 ? '#c3213f' : undefined }}>{res.false_positives}</b></div>
                </div>
              </Tilt>
            );
          })}
        </div>
      )}
    </>
  );
};
