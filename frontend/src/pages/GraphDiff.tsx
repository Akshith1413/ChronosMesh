import React, { useState, useEffect, useCallback } from 'react';
import api from '../services/api';
import { GraphDiffReport } from '../types';
import { Icon } from '../components/Icon';
import { Loader, EmptyState, ErrorState } from '../components/LoadingState';
import { useCountUp } from '../fx/hooks';
import { PALETTE } from '../utils/colors';

const Delta: React.FC<{ label: string; n: number; sign: '+' | '-'; icon: string }> = ({ label, n, sign, icon }) => {
  const shown = useCountUp(n, 900, 0);
  const good = sign === '+';
  return (
    <div className="stat">
      <span className="stat-l"><Icon name={icon} size={13} /> {label}</span>
      <b className="num" style={{ color: n === 0 ? PALETTE.mute : good ? PALETTE.ok : PALETTE.crit }}>{n === 0 ? '0' : `${sign}${shown}`}</b>
    </div>
  );
};

export const GraphDiffPage: React.FC = () => {
  const [diffReport, setDiffReport] = useState<GraphDiffReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDiff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDiffReport(await api.getGraphDiff());
    } catch (e: any) {
      setError(e.message || 'Failed to fetch graph diff');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDiff();
  }, [fetchDiff]);

  const diff = diffReport?.diff;
  const addedN = diff?.added_nodes?.length || 0;
  const removedN = diff?.removed_nodes?.length || 0;
  const addedE = diff?.added_edges?.length || 0;
  const removedE = diff?.removed_edges?.length || 0;
  const changes = addedN + removedN + addedE + removedE;

  return (
    <>
      <div className="panel tight toolbar">
        <div>
          <div className="eyebrow">Baseline comparison</div>
          <p className="muted small" style={{ marginTop: 6 }}>Compares the current runtime DAG against the reference topology for structural change.</p>
        </div>
        <button className="btn btn-primary" onClick={fetchDiff} disabled={loading}>
          <Icon name="refresh" size={16} className={loading ? 'spin-icon' : ''} /> Recompute diff
        </button>
      </div>

      {loading && !diff ? (
        <div className="panel"><Loader message="Computing graph differential…" /></div>
      ) : error ? (
        <ErrorState message={error} onRetry={fetchDiff} />
      ) : diff ? (
        <>
          <div className={`verdict ${changes === 0 ? 'same' : 'drift'}`}>
            <span className="verdict-ico"><Icon name={changes === 0 ? 'check' : 'alert'} size={26} weight={2} /></span>
            <div>
              <b>{changes === 0 ? 'Runtime graph matches the baseline' : `${changes} structural change${changes === 1 ? '' : 's'} from baseline`}</b>
              <span>{changes === 0 ? 'No unexpected divergence in nodes or causal edges.' : 'Review the added and removed elements below.'}</span>
            </div>
            <span className={`chip ${changes === 0 ? 'chip-ok' : 'chip-warn'}`}>{changes === 0 ? 'Identical' : 'Drift detected'}</span>
          </div>

          <div className="stat-grid stagger" style={{ ['--cols' as any]: 4 }}>
            <Delta label="Added nodes" n={addedN} sign="+" icon="spark" />
            <Delta label="Removed nodes" n={removedN} sign="-" icon="close" />
            <Delta label="Added edges" n={addedE} sign="+" icon="link" />
            <Delta label="Removed edges" n={removedE} sign="-" icon="close" />
          </div>

          <div className="grid-2">
            <div className="panel">
              <div className="panel-head" style={{ marginBottom: 12 }}>
                <div className="panel-title">Node changes</div>
                <span className="chip">{addedN + removedN}</span>
              </div>
              {addedN + removedN === 0 ? (
                <EmptyState compact title="Nodes match" description="All nodes match the baseline topology exactly." />
              ) : (
                <div className="stack stagger" style={{ gap: 7 }}>
                  {diff.added_nodes?.map((n, i) => <div key={n} className="diff-row add" style={{ ['--i' as any]: i }}><b>+</b> added node <code>{n}</code></div>)}
                  {diff.removed_nodes?.map((n, i) => <div key={n} className="diff-row del" style={{ ['--i' as any]: i }}><b>−</b> removed node <code>{n}</code></div>)}
                </div>
              )}
            </div>

            <div className="panel">
              <div className="panel-head" style={{ marginBottom: 12 }}>
                <div className="panel-title">Causal edge changes</div>
                <span className="chip">{addedE + removedE}</span>
              </div>
              {addedE + removedE === 0 ? (
                <EmptyState compact title="Edges match" description="No added or removed causal edges detected." />
              ) : (
                <div className="stack stagger" style={{ gap: 7 }}>
                  {diff.added_edges?.map((e, i) => <div key={i} className="diff-row add" style={{ ['--i' as any]: i }}><b>+</b> <code>{e[0]}</code> <Icon name="arrow" size={12} /> <code>{e[1]}</code></div>)}
                  {diff.removed_edges?.map((e, i) => <div key={i} className="diff-row del" style={{ ['--i' as any]: i }}><b>−</b> <code>{e[0]}</code> <Icon name="arrow" size={12} /> <code>{e[1]}</code></div>)}
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <EmptyState title="No graph diff available" description="Load a scenario trace to run the baseline vs runtime comparison." />
      )}
    </>
  );
};
