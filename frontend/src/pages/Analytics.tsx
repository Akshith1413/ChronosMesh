import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { LatencyHistogramReport, TopologyStatsReport, EventReplayReport } from '../types';
import { getServiceColor, getServiceLabel, PALETTE } from '../utils/colors';
import { Segmented } from '../components/Segmented';
import { Icon } from '../components/Icon';
import { Ring } from '../components/Ring';
import { Loader, EmptyState, ErrorState } from '../components/LoadingState';
import { useCountUp } from '../fx/hooks';

type Tab = 'latency' | 'topology' | 'replay';

/** A stat tile; numeric values count up. */
const Stat: React.FC<{ label: string; value: number | null | string; suffix?: string; color?: string; decimals?: number; sub?: string }> = ({
  label, value, suffix = '', color, decimals = 1, sub,
}) => {
  const numeric = typeof value === 'number';
  const shown = useCountUp(numeric ? (value as number) : 0, 1000, decimals);
  return (
    <div className="stat">
      <span className="stat-l">{label}</span>
      <b className="num" style={{ color }}>
        {value === null ? 'N/A' : numeric ? shown : value}
        {numeric && suffix && <small>{suffix}</small>}
      </b>
      {sub && <em>{sub}</em>}
    </div>
  );
};

export const AnalyticsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('latency');

  const [latencyData, setLatencyData] = useState<LatencyHistogramReport | null>(null);
  const [latencyLoading, setLatencyLoading] = useState<boolean>(false);
  const [latencyError, setLatencyError] = useState<string | null>(null);

  const [topologyData, setTopologyData] = useState<TopologyStatsReport | null>(null);
  const [topologyLoading, setTopologyLoading] = useState<boolean>(false);
  const [topologyError, setTopologyError] = useState<string | null>(null);

  const [replayData, setReplayData] = useState<EventReplayReport | null>(null);
  const [replayLoading, setReplayLoading] = useState<boolean>(false);
  const [replayError, setReplayError] = useState<string | null>(null);

  const [selectedLayerIndex, setSelectedLayerIndex] = useState<number>(0);
  const [layerPlaying, setLayerPlaying] = useState(false);

  const fetchLatency = useCallback(async () => {
    setLatencyLoading(true);
    setLatencyError(null);
    try {
      setLatencyData(await api.getLatencyHistogram(6));
    } catch (e: any) {
      setLatencyError(e.message || 'Failed to fetch latency data');
    } finally {
      setLatencyLoading(false);
    }
  }, []);

  const fetchTopology = useCallback(async () => {
    setTopologyLoading(true);
    setTopologyError(null);
    try {
      setTopologyData(await api.getTopologyStats());
    } catch (e: any) {
      setTopologyError(e.message || 'Failed to fetch topology stats');
    } finally {
      setTopologyLoading(false);
    }
  }, []);

  const fetchReplay = useCallback(async () => {
    setReplayLoading(true);
    setReplayError(null);
    try {
      setReplayData(await api.getEventReplay());
      setSelectedLayerIndex(0);
    } catch (e: any) {
      setReplayError(e.message || 'Failed to fetch replay data');
    } finally {
      setReplayLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'latency') fetchLatency();
    else if (activeTab === 'topology') fetchTopology();
    else if (activeTab === 'replay') fetchReplay();
  }, [activeTab, fetchLatency, fetchTopology, fetchReplay]);

  // auto-step through causal layers
  useEffect(() => {
    if (!layerPlaying || !replayData) return;
    const t = setInterval(() => {
      setSelectedLayerIndex((i) => {
        if (i >= replayData.layers.length - 1) {
          setLayerPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 1300);
    return () => clearInterval(t);
  }, [layerPlaying, replayData]);

  const refresh = () => {
    if (activeTab === 'latency') fetchLatency();
    else if (activeTab === 'topology') fetchTopology();
    else fetchReplay();
  };

  return (
    <>
      <div className="panel tight toolbar">
        <Segmented<Tab>
          ariaLabel="Analytics view"
          value={activeTab}
          onChange={setActiveTab}
          options={[
            { value: 'latency', label: 'Latency', icon: 'gauge' },
            { value: 'topology', label: 'Topology', icon: 'dag' },
            { value: 'replay', label: 'Causal layers', icon: 'layers' },
          ]}
        />
        <button className="btn btn-sm" onClick={refresh}>
          <Icon name="refresh" size={15} /> Refresh analysis
        </button>
      </div>

      {/* ── Latency ───────────────────────────────────────────────── */}
      {activeTab === 'latency' && (
        <div className="stack" key="latency">
          {latencyLoading && !latencyData ? (
            <div className="panel"><Loader message="Calculating edge latency distribution…" /></div>
          ) : latencyError ? (
            <ErrorState message={latencyError} onRetry={fetchLatency} />
          ) : latencyData && latencyData.sample_size > 0 ? (
            <>
              <div className="stat-grid stagger">
                <Stat label="p50 · median" value={latencyData.p50_ms} suffix=" ms" color={PALETTE.iris1} />
                <Stat label="p95" value={latencyData.p95_ms} suffix=" ms" color="#c27b00" />
                <Stat label="p99" value={latencyData.p99_ms} suffix=" ms" color={PALETTE.crit} />
                <Stat label="min" value={latencyData.min_ms} suffix=" ms" color={PALETTE.ok} />
                <Stat label="max" value={latencyData.max_ms} suffix=" ms" color="#c2185b" />
                <Stat label="mean" value={latencyData.mean_ms} suffix=" ms" />
              </div>

              <div className="panel">
                <div className="panel-head">
                  <div>
                    <div className="eyebrow">Distribution</div>
                    <h3 className="panel-title" style={{ marginTop: 10 }}>Edge latency histogram</h3>
                    <p className="panel-sub">
                      Positive edge transit times across {latencyData.sample_size} causal edges
                      {latencyData.inversion_edge_count > 0 && ` · ${latencyData.inversion_edge_count} inverted edge(s) excluded`}
                    </p>
                  </div>
                </div>
                <Histogram d={latencyData} />
              </div>
            </>
          ) : (
            <EmptyState title="No latency measurements" description="Load a trace or workflow to calculate causal edge transit latencies." />
          )}
        </div>
      )}

      {/* ── Topology ──────────────────────────────────────────────── */}
      {activeTab === 'topology' && (
        <div className="stack" key="topology">
          {topologyLoading && !topologyData ? (
            <div className="panel"><Loader message="Analyzing DAG topology…" /></div>
          ) : topologyError ? (
            <ErrorState message={topologyError} onRetry={fetchTopology} />
          ) : topologyData && topologyData.node_count > 0 ? (
            <>
              <div className="stat-grid stagger">
                <Stat label="Nodes" value={topologyData.node_count} decimals={0} color={PALETTE.iris1} />
                <Stat label="Edges" value={topologyData.edge_count} decimals={0} color={PALETTE.iris1} />
                <Stat label="Graph density" value={topologyData.density} decimals={2} />
                <Stat label="Coupling" value={topologyData.coupling_metric} decimals={2} sub="avg degree (2E/V)" />
                <Stat label="Components" value={topologyData.is_connected ? 'Connected' : `${topologyData.connected_components}`} color={topologyData.is_connected ? PALETTE.ok : PALETTE.warn} sub="weakly connected" />
                <div className="stat stat-ring">
                  <Ring pct={topologyData.concurrency_ratio * 100} color={PALETTE.info} size={84} decimals={0} />
                  <div>
                    <span className="stat-l">Concurrency</span>
                    <em>{topologyData.concurrency_pairs_count} concurrent pair(s)</em>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <div>
                    <div className="eyebrow">Critical path</div>
                    <h3 className="panel-title" style={{ marginTop: 10 }}>Longest causal path</h3>
                    <p className="panel-sub">The sequential dependency chain that sets the minimum execution latency.</p>
                  </div>
                  <span className="chip chip-iris">
                    {topologyData.longest_causal_path.length} hops
                    {topologyData.longest_causal_path.duration_ms !== null && ` · ${topologyData.longest_causal_path.duration_ms} ms`}
                  </span>
                </div>
                <div className="train">
                  {topologyData.longest_causal_path.path.map((nodeId, idx, arr) => (
                    <React.Fragment key={nodeId}>
                      <span className="train-node" style={{ ['--k' as any]: idx }}>
                        <i />{nodeId}
                      </span>
                      {idx < arr.length - 1 && <span className="train-link" style={{ ['--k' as any]: idx }}><i /></span>}
                    </React.Fragment>
                  ))}
                </div>
              </div>

              <div className="grid-2">
                <div className="panel">
                  <div className="label" style={{ marginBottom: 12 }}>Root events · in-degree 0</div>
                  <div className="row" style={{ gap: 7 }}>
                    {topologyData.root_nodes.map((r) => <span key={r} className="chip chip-ok" style={{ textTransform: 'none' }}>{r}</span>)}
                  </div>
                </div>
                <div className="panel">
                  <div className="label" style={{ marginBottom: 12 }}>Leaf events · out-degree 0</div>
                  <div className="row" style={{ gap: 7 }}>
                    {topologyData.leaf_nodes.map((l) => <span key={l} className="chip chip-warn" style={{ textTransform: 'none' }}>{l}</span>)}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <EmptyState title="No DAG topology" description="Load a trace to analyze graph metrics." />
          )}
        </div>
      )}

      {/* ── Replay layers ─────────────────────────────────────────── */}
      {activeTab === 'replay' && (
        <div className="stack" key="replay">
          {replayLoading && !replayData ? (
            <div className="panel"><Loader message="Constructing topological causal layers…" /></div>
          ) : replayError ? (
            <ErrorState message={replayError} onRetry={fetchReplay} />
          ) : replayData && replayData.layers.length > 0 ? (
            <>
              <div className="stat-grid three stagger">
                <Stat label="Causal layers" value={replayData.total_layers} decimals={0} color={PALETTE.iris1} />
                <Stat label="Total events" value={replayData.total_events} decimals={0} />
                <Stat label="Max parallelism" value={replayData.max_parallelism} decimals={0} suffix=" concurrent" color={PALETTE.info} />
              </div>

              <div className="panel">
                <div className="panel-head">
                  <div>
                    <div className="eyebrow">Topological generations</div>
                    <h3 className="panel-title" style={{ marginTop: 10 }}>Layer-by-layer replay</h3>
                    <p className="panel-sub">Events in the same layer share no happens-before dependency — they ran concurrently.</p>
                  </div>
                  <button
                    className="btn btn-sm"
                    onClick={() => {
                      if (!layerPlaying && selectedLayerIndex >= replayData.layers.length - 1) setSelectedLayerIndex(0);
                      setLayerPlaying((p) => !p);
                    }}
                  >
                    <Icon name={layerPlaying ? 'pause' : 'play'} size={14} /> {layerPlaying ? 'Pause' : 'Play layers'}
                  </button>
                </div>

                <div className="layer-rail">
                  {replayData.layers.map((layer, idx) => (
                    <button
                      key={idx}
                      className={`layer-btn ${selectedLayerIndex === idx ? 'on' : ''} ${idx <= selectedLayerIndex ? 'past' : ''}`}
                      onClick={() => { setLayerPlaying(false); setSelectedLayerIndex(idx); }}
                    >
                      <span className="layer-dots">
                        {Array.from({ length: Math.min(layer.concurrent_count, 8) }).map((_, i) => <i key={i} style={{ animationDelay: `${i * 90}ms` }} />)}
                      </span>
                      <b>Layer {layer.layer_index}</b>
                      <small>{layer.concurrent_count} event{layer.concurrent_count === 1 ? '' : 's'}</small>
                    </button>
                  ))}
                </div>

                {replayData.layers[selectedLayerIndex] && (
                  <div className="layer-body" key={selectedLayerIndex}>
                    <div className="spread" style={{ marginBottom: 14 }}>
                      <b style={{ fontSize: 14 }}>
                        Layer {replayData.layers[selectedLayerIndex].layer_index} · {replayData.layers[selectedLayerIndex].concurrent_count} concurrent event(s)
                      </b>
                      <span className="chip chip-info"><Icon name="bolt" size={12} /> parallel execution</span>
                    </div>
                    <div className="grid-auto stagger" style={{ ['--min' as any]: '250px' }}>
                      {replayData.layers[selectedLayerIndex].events.map((evt, i) => (
                        <div key={evt.event_id} className="lay-ev" style={{ ['--c' as any]: getServiceColor(evt.service_id), ['--i' as any]: i }}>
                          <div className="spread">
                            <b className="mono">{evt.event_type}</b>
                            <span className="chip chip-iris num">L{evt.lamport_ts}</span>
                          </div>
                          <span className="svc-tag" style={{ ['--c' as any]: getServiceColor(evt.service_id), marginTop: 8 }}>{getServiceLabel(evt.service_id)}</span>
                          <small className="mono muted" style={{ display: 'block', marginTop: 8 }}>{evt.event_id}</small>
                          {evt.parents.length > 0 && <small className="muted" style={{ display: 'block', marginTop: 3 }}>parents: {evt.parents.join(', ')}</small>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <EmptyState title="No replay data" description="Load a scenario trace to reconstruct its topological generations." />
          )}
        </div>
      )}
    </>
  );
};

/** Vertical histogram with percentile flags placed from the measured values. */
const Histogram: React.FC<{ d: LatencyHistogramReport }> = ({ d }) => {
  const maxCount = Math.max(...d.bins.map((b) => b.count), 1);
  const lo = d.bins[0]?.bin_start_ms ?? 0;
  const hi = d.bins[d.bins.length - 1]?.bin_end_ms ?? 1;
  const pos = (v: number | null) => (v === null || hi <= lo ? null : Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100)));
  const flags = [
    { k: 'p50', v: d.p50_ms, c: PALETTE.iris1 },
    { k: 'p95', v: d.p95_ms, c: PALETTE.warn },
    { k: 'p99', v: d.p99_ms, c: PALETTE.crit },
  ];
  return (
    <div className="hist">
      <div className="hist-plot">
        <div className="hist-grid" aria-hidden="true"><i /><i /><i /><i /></div>
        <div className="hist-bars">
          {d.bins.map((b, i) => (
            <div key={i} className="hist-col" title={`${b.bin_start_ms}–${b.bin_end_ms} ms: ${b.count} edge(s)`}>
              <span className="hist-n num">{b.count}</span>
              <i style={{ height: `${(b.count / maxCount) * 100}%`, animationDelay: `${i * 90}ms` }} />
            </div>
          ))}
        </div>
        {flags.map((f, i) => {
          const p = pos(f.v);
          return p === null ? null : (
            <span
              key={f.k}
              className={`hist-flag ${p > 62 ? 'flip' : ''}`}
              style={{ left: `calc(10px + (100% - 20px) * ${p / 100})`, ['--c' as any]: f.c, ['--r' as any]: i }}
            >
              <em>{f.k} · {f.v} ms</em>
            </span>
          );
        })}
      </div>
      <div className="hist-axis">
        {d.bins.map((b, i) => <span key={i}>{b.bin_start_ms}–{b.bin_end_ms}</span>)}
      </div>
    </div>
  );
};
