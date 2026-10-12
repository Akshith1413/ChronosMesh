import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from '../components/Icon';
import { Segmented } from '../components/Segmented';
import { MetricCard } from '../components/MetricCard';
import { BarGroups } from '../components/BarGroups';
import { CausalGraph } from '../components/CausalGraph';
import { ErrorState, Loader } from '../components/LoadingState';
import api from '../services/api';
import {
  ExecutionGraph,
  ExecutionRecord,
  ExperimentOptions,
  ExperimentParams,
  ExperimentResult,
} from '../types';
import {
  ANOMALY_BLURBS,
  APPROACHES,
  DEFAULT_PARAMS,
  PRESETS,
  applyPreset,
  chartSeries,
  clampToLimits,
  formatCI,
  formatRate,
  isTerminal,
  pct,
  statusChip,
  validateParams,
} from '../utils/experiments';
import { PALETTE } from '../utils/colors';

interface Props {
  canRun: boolean;
  onOpenExplorer: (scenario: string) => void;
}

type Metric = 'f1' | 'precision' | 'recall';

const SliderField: React.FC<{
  label: string; value: number; min: number; max: number; step?: number; unit?: string; color?: string;
  format?: (v: number) => string; onChange: (v: number) => void; disabled?: boolean;
}> = ({ label, value, min, max, step = 1, unit = '', color = PALETTE.iris1, format, onChange, disabled }) => (
  <div className="dial" style={{ ['--c' as any]: color }}>
    <div className="spread">
      <span className="label">{label}</span>
      <b className="dial-val num">{format ? format(value) : value}<small>{unit}</small></b>
    </div>
    <input
      type="range" className="range" min={min} max={max} step={step} value={value} disabled={disabled}
      style={{ ['--p' as any]: `${((value - min) / (max - min || 1)) * 100}%`, ['--c' as any]: color }}
      onChange={(e) => onChange(parseFloat(e.target.value))} aria-label={label}
    />
    <div className="dial-ends"><span>{format ? format(min) : min}{unit}</span><span>{format ? format(max) : max}{unit}</span></div>
  </div>
);

export const ExperimentsPage: React.FC<Props> = ({ canRun, onOpenExplorer }) => {
  const [options, setOptions] = useState<ExperimentOptions | null>(null);
  const [params, setParams] = useState<ExperimentParams>(DEFAULT_PARAMS);
  const [presetId, setPresetId] = useState<string>('baseline');
  const [experiments, setExperiments] = useState<ExecutionRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [result, setResult] = useState<ExperimentResult | null>(null);
  const [samples, setSamples] = useState<ExecutionRecord[]>([]);
  const [graph, setGraph] = useState<{ id: string; data: ExecutionGraph; truth: Set<string> } | null>(null);
  const [metric, setMetric] = useState<Metric>('f1');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const selected = useMemo(() => experiments.find((e) => e.execution_id === selectedId) || null, [experiments, selectedId]);
  const problems = useMemo(() => validateParams(params, options), [params, options]);

  const refreshList = useCallback(async () => {
    const r = await api.listExperiments();
    setExperiments(r.experiments);
    return r.experiments;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [opts] = await Promise.all([api.getExperimentOptions(), refreshList()]);
        setOptions(opts);
        setParams(clampToLimits({ ...opts.defaults, ...PRESETS[0].params }, opts));
      } catch (e: any) {
        setError(e.message || 'Could not reach the experiment API');
      }
    })();
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [refreshList]);

  const loadResult = useCallback(async (id: string) => {
    setResult(null); setSamples([]); setGraph(null);
    try {
      const [res, ex] = await Promise.all([api.getExperimentResult(id), api.getExperimentExecutions(id)]);
      setResult(res);
      setSamples([...ex.executions].sort((a, b) => a.execution_id.localeCompare(b.execution_id)));
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  // Poll the selected experiment until it reaches a terminal state, then fetch the full result.
  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const rec = await api.getExperiment(selectedId);
        if (cancelled) return;
        setExperiments((list) => list.map((e) => (e.execution_id === rec.execution_id ? rec : e)));
        if (isTerminal(rec.status)) {
          if (rec.status === 'succeeded') await loadResult(selectedId);
          else setError(rec.error || 'Experiment failed');
          return;
        }
        timer.current = window.setTimeout(tick, 1000);
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      }
    };
    tick();
    return () => { cancelled = true; if (timer.current) window.clearTimeout(timer.current); };
  }, [selectedId, loadResult]);

  const set = <K extends keyof ExperimentParams>(key: K, value: ExperimentParams[K]) =>
    setParams((p) => ({ ...p, [key]: value }));

  const choosePreset = (id: string) => {
    const preset = PRESETS.find((p) => p.id === id);
    if (!preset) return;
    setPresetId(id);
    setParams((p) => clampToLimits(applyPreset(p, preset), options));
  };

  const run = async () => {
    setBusy(true); setError(null);
    try {
      const created = await api.createExperiment(params);
      await api.startExperiment(created.execution_id);
      await refreshList();
      setSelectedId(created.execution_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const openSample = async (id: string) => {
    try {
      const [g, t] = await Promise.all([api.getExecutionGraph(id), api.getExecutionTruth(id).catch(() => ({ edges: [] as [string, string][] }))]);
      setGraph({ id, data: g, truth: new Set(t.edges.map(([a, b]) => `${a}>${b}`)) });
    } catch (e: any) {
      setError(e.message);
    }
  };

  const explore = async (id: string) => {
    try {
      const r = await api.exploreExecution(id);
      onOpenExplorer(r.scenario);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const L = options?.limits;
  const running = selected && !isTerminal(selected.status);
  const run0 = result?.runs[0];

  return (
    <>
      {error && <ErrorState message={error} onRetry={() => { setError(null); refreshList().catch(() => {}); }} />}

      <div className="panel">
        <div className="panel-head">
          <div>
            <div className="eyebrow">Fault-injection lab</div>
            <h3 className="panel-title" style={{ marginTop: 10 }}>Does the reconstruction survive real distributed failures?</h3>
            <p className="panel-sub">
              A simulator emits many causal executions across your services with an independent ground truth, then the
              platform's delivery is degraded. ChronosMesh is scored edge-by-edge against that truth, next to the arrival-order
              and wall-clock approaches most tools use.
            </p>
          </div>
          <button className="btn btn-primary" onClick={run} disabled={!canRun || busy || !options || problems.length > 0 || !!running}
            title={canRun ? undefined : 'Requires the analyst or admin role'}>
            {busy || running ? 'Running…' : <><Icon name="bolt" size={16} /> Run experiment</>}
          </button>
        </div>

        <div className="row" style={{ gap: 10, flexWrap: 'wrap', margin: '4px 0 18px' }}>
          <Segmented
            ariaLabel="Scenario preset"
            value={presetId}
            onChange={choosePreset}
            options={PRESETS.map((p) => ({ value: p.id, label: p.label }))}
          />
        </div>
        <p className="small muted" style={{ marginTop: -6 }}>{PRESETS.find((p) => p.id === presetId)?.description}</p>

        {L && (
          <div className="dials">
            <SliderField label="Services" value={params.num_services} min={L.num_services[0]} max={L.num_services[1]} onChange={(v) => set('num_services', v)} />
            <SliderField label="Events" value={params.num_events} min={100} max={Math.min(L.num_events[1], options!.max_experiment_events)} step={100} onChange={(v) => set('num_events', v)} color={PALETTE.iris2} />
            <SliderField label="Network delay (max)" value={params.network_delay_ms} min={0} max={L.network_delay_ms[1]} step={50} unit=" ms" onChange={(v) => set('network_delay_ms', v)} color={PALETTE.iris3} />
            <SliderField label="Clock drift (± per service)" value={params.clock_drift_ms} min={0} max={1000} step={25} unit=" ms" onChange={(v) => set('clock_drift_ms', v)} color={PALETTE.warn} />
            <SliderField label="Cross-region delay" value={params.cross_region_delay_ms} min={0} max={L.cross_region_delay_ms[1]} step={50} unit=" ms" onChange={(v) => set('cross_region_delay_ms', v)} color={PALETTE.iris3} />
            <SliderField label="Duplicate deliveries" value={params.duplicate_rate} min={0} max={L.duplicate_rate[1]} step={0.01} format={(v) => (v * 100).toFixed(0)} unit="%" onChange={(v) => set('duplicate_rate', v)} color={PALETTE.info} />
            <SliderField label="Lost events" value={params.missing_rate} min={0} max={L.missing_rate[1]} step={0.01} format={(v) => (v * 100).toFixed(0)} unit="%" onChange={(v) => set('missing_rate', v)} color={PALETTE.crit} />
            <SliderField label="Lost clock metadata" value={params.metadata_loss_rate} min={0} max={1} step={0.05} format={(v) => (v * 100).toFixed(0)} unit="%" onChange={(v) => set('metadata_loss_rate', v)} color={PALETTE.crit} />
            <SliderField label="Retry storms" value={params.retry_rate} min={0} max={L.retry_rate[1]} step={0.01} format={(v) => (v * 100).toFixed(0)} unit="%" onChange={(v) => set('retry_rate', v)} color={PALETTE.crit} />
            <SliderField label="Worker crashes" value={params.worker_failures} min={0} max={L.worker_failures[1]} onChange={(v) => set('worker_failures', v)} color={PALETTE.warn} />
            <SliderField label="Repeats (for CIs)" value={params.repeats} min={1} max={10} onChange={(v) => set('repeats', v)} color={PALETTE.ok} disabled={params.transport === 'sqs'} />
          </div>
        )}

        <div className="row" style={{ gap: 14, flexWrap: 'wrap', marginTop: 14 }}>
          <div className="field">
            <label htmlFor="mode">Delivery</label>
            <select id="mode" className="select" value={params.delivery_mode} onChange={(e) => set('delivery_mode', e.target.value as any)}>
              {(options?.delivery_modes || []).map((m) => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="transport">Transport</label>
            <select id="transport" className="select" value={params.transport} onChange={(e) => set('transport', e.target.value as any)}>
              {(options?.transports || ['direct']).map((t) => <option key={t} value={t}>{t === 'sqs' ? 'Amazon SQS → worker' : 'In-process'}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="seed">Seed</label>
            <input id="seed" className="input" type="number" value={params.seed} min={0} onChange={(e) => set('seed', Math.max(0, parseInt(e.target.value || '0', 10)))} style={{ width: 110 }} />
          </div>
          <div className="field grow" style={{ minWidth: 200 }}>
            <label htmlFor="ename">Name</label>
            <input id="ename" className="input" value={params.name} maxLength={80} onChange={(e) => set('name', e.target.value)} />
          </div>
        </div>
        {problems.length > 0 && <ul className="small" style={{ color: PALETTE.crit, marginTop: 10 }}>{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
      </div>

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div className="panel">
          <div className="panel-head"><div><div className="eyebrow">History</div><h3 className="panel-title" style={{ marginTop: 10 }}>My experiments</h3></div>
            <button className="btn btn-sm" onClick={() => refreshList().catch((e) => setError(e.message))}><Icon name="refresh" size={14} /> Refresh</button></div>
          {experiments.length === 0 ? <p className="muted small">No experiments yet — pick a scenario above and run one.</p> : (
            <table className="table">
              <thead><tr><th>Name</th><th>Status</th><th>Events</th><th>F1</th></tr></thead>
              <tbody>
                {experiments.map((e) => {
                  const chip = statusChip(e.status);
                  return (
                    <tr key={e.execution_id} onClick={() => setSelectedId(e.execution_id)} style={{ cursor: 'pointer', background: e.execution_id === selectedId ? 'rgba(106,76,255,0.08)' : undefined }}>
                      <td><b>{e.name}</b><div className="small muted mono">{e.execution_id}</div></td>
                      <td><span className={`chip ${chip.cls}`}>{chip.label}</span></td>
                      <td className="num">{e.config?.num_events ?? '—'}</td>
                      <td className="num">{e.summary ? e.summary.f1.chronosmesh.toFixed(3) : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <div className="eyebrow">Selected run</div>
          {!selected && <p className="muted small" style={{ marginTop: 12 }}>Select an experiment to see its evaluation.</p>}
          {selected && running && (
            <div style={{ marginTop: 14 }}>
              <Loader message={`${selected.message || selected.status}… ${Math.round((selected.progress || 0) * 100)}%`} />
            </div>
          )}
          {selected?.status === 'failed' && <p style={{ color: PALETTE.crit }}>{selected.error}</p>}
          {selected?.status === 'succeeded' && run0 && result && (
            <div className="grid-2" style={{ marginTop: 14, gap: 12 }}>
              <MetricCard icon="layers" label="Executions" value={run0.executions} color={PALETTE.iris1} subValue={`${run0.events_delivered_unique} events`} />
              <MetricCard icon="shield" label="Recovery rate" value={pct(result.summary.recovery_rate, 0)} color={PALETTE.ok} subValue={`F1 ≥ ${result.summary.recovery_f1_threshold}`} />
              <MetricCard icon="bolt" label="Throughput" value={formatRate(result.summary.performance.throughput_eps.mean)} color={PALETTE.iris2} subValue={`${result.summary.performance.reconstruction_seconds.mean.toFixed(2)} s`} />
              <MetricCard icon="anomaly" label="Anomalies" value={run0.anomalies.total} color={PALETTE.warn} subValue={`${run0.events_dropped} lost · ${run0.events_duplicated} dup`} />
            </div>
          )}
        </div>
      </div>

      {result && run0 && (
        <>
          <div className="panel">
            <div className="panel-head">
              <div>
                <div className="eyebrow">Edge-level accuracy vs ground truth</div>
                <h3 className="panel-title" style={{ marginTop: 10 }}>Reconstruction quality by approach</h3>
                <p className="panel-sub">{result.summary.approaches.chronosmesh.f1.n} run(s), bars show the mean with 95 % confidence whiskers. Disorder of the arrival stream: {pct(run0.arrival_disorder, 0)}.</p>
              </div>
              <Segmented<Metric> ariaLabel="Metric" value={metric} onChange={setMetric}
                options={[{ value: 'f1', label: 'F1' }, { value: 'precision', label: 'Precision' }, { value: 'recall', label: 'Recall' }]} />
            </div>
            <BarGroups title={`${metric} by approach`} data={chartSeries(result.summary.approaches, metric)} />

            <table className="table" style={{ marginTop: 18 }}>
              <thead><tr><th>Approach</th><th>Precision</th><th>Recall</th><th>F1</th><th>Event-ordering acc.</th><th>Late-edge recovery</th><th>Concurrent recall</th></tr></thead>
              <tbody>
                {APPROACHES.map((a) => (
                  <tr key={a.key} style={a.key === 'chronosmesh' ? { fontWeight: 700 } : undefined}>
                    <td title={a.blurb}><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 5, background: a.color, marginRight: 8 }} />{a.label}</td>
                    <td className="num">{formatCI(result.summary.approaches[a.key].precision)}</td>
                    <td className="num">{formatCI(result.summary.approaches[a.key].recall)}</td>
                    <td className="num">{formatCI(result.summary.approaches[a.key].f1)}</td>
                    <td className="num">{formatCI(result.summary.ordering?.[a.key])}</td>
                    <td className="num">{formatCI(result.summary.late_event_recovery?.[a.key])}</td>
                    <td className="num">{formatCI(result.summary.concurrency[a.key].concurrent_recall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="small muted" style={{ marginTop: 10 }}>
              Total-order approaches can never report two events as concurrent, so their concurrent recall is 0 by construction. With intact
              vector clocks ChronosMesh's concurrency classification is exact; the lab quantifies how it degrades when clock metadata is lost.
            </p>
          </div>

          <div className="grid-2" style={{ alignItems: 'start' }}>
            <div className="panel">
              <div className="eyebrow">Fault tolerance</div>
              <table className="table" style={{ marginTop: 10 }}>
                <tbody>
                  <tr><td>Duplicate deliveries suppressed</td><td className="num">{run0.fault_tolerance.duplicates_suppressed}</td></tr>
                  <tr><td>Duplicate detection rate</td><td className="num">{formatCI(result.summary.duplicate_detection_rate ?? undefined)}</td></tr>
                  <tr><td>Worker crashes injected / recovered</td><td className="num">{run0.fault_tolerance.worker_crashes_injected} / {run0.fault_tolerance.recoveries}</td></tr>
                  <tr><td>Messages redelivered after crashes</td><td className="num">{run0.fault_tolerance.redelivered_messages}</td></tr>
                  <tr><td>Graph identical after recovery</td><td className="num">{run0.fault_tolerance.state_consistent_after_recovery ? 'yes' : 'NO'}</td></tr>
                  <tr><td>Edges bridging lost events</td><td className="num">{run0.reconstruction.gap_edges ?? 0}</td></tr>
                  <tr><td>Declared edges rejected (clock mismatch)</td><td className="num">{run0.reconstruction.rejected_declared ?? 0}</td></tr>
                  <tr><td>CPU time / peak RSS</td><td className="num">{run0.performance.cpu_seconds.toFixed(2)} s / {run0.performance.peak_rss_mb.toFixed(0)} MB</td></tr>
                </tbody>
              </table>
            </div>
            <div className="panel">
              <div className="eyebrow">Anomaly Lab</div>
              <table className="table" style={{ marginTop: 10 }}>
                <tbody>
                  {Object.entries(run0.anomalies.by_type).sort((a, b) => b[1] - a[1]).map(([type, n]) => (
                    <tr key={type} title={ANOMALY_BLURBS[type]}>
                      <td><b>{type.replace(/_/g, ' ')}</b><div className="small muted">{ANOMALY_BLURBS[type]}</div></td>
                      <td className="num">{n}</td>
                    </tr>
                  ))}
                  {run0.anomalies.total === 0 && <tr><td className="muted">No anomalies detected.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head"><div>
              <div className="eyebrow">Drill-down</div>
              <h3 className="panel-title" style={{ marginTop: 10 }}>Sampled executions</h3>
              <p className="panel-sub">Open one execution to see its reconstructed graph (solid = declared parent, dashed = inferred from vector clocks). The summary line compares it with the ground truth.</p>
            </div></div>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              {samples.slice(0, 12).map((s) => (
                <button key={s.execution_id} className={`btn btn-sm ${graph?.id === s.execution_id ? 'btn-primary' : ''}`} onClick={() => openSample(s.execution_id)}>
                  {s.execution_id.split('-').slice(-1)[0]} · {s.stats?.events ?? '?'} ev
                </button>
              ))}
            </div>
            {graph && (
              <div style={{ marginTop: 16 }}>
                <div className="row spread" style={{ marginBottom: 8 }}>
                  <span className="small muted">
                    {graph.data.total_nodes} nodes · {graph.data.total_edges} edges · {Object.keys(graph.data.unresolved).length} unresolved parent(s)
                    {graph.truth.size > 0 && ` · ground truth: ${graph.truth.size} edges (${graph.data.edges.filter((e) => !graph.truth.has(`${e.source}>${e.target}`)).length} extra, ${[...graph.truth].filter((k) => !graph.data.edges.some((e) => `${e.source}>${e.target}` === k)).length} missing)`}
                  </span>
                  <button className="btn btn-sm" onClick={() => explore(graph.id)} disabled={!canRun}>
                    <Icon name="dag" size={14} /> Analyse in Trace Explorer
                  </button>
                </div>
                <div className="graph-panel" style={{ height: 560, borderRadius: 18, overflow: 'hidden', border: '1px solid var(--line)' }}>
                  <CausalGraph dagData={graph.data} onSelectNode={() => {}} />
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
};
