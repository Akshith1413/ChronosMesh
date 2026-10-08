import React, { useRef, useState } from 'react';
import { DAGData, DAGNode, DAGEdge } from '../types';
import { Graph2D } from './graph/Graph2D';
import { Dag3D } from './graph/Dag3D';
import { GraphHandle, HoverInfo } from './graph/types';
import { Segmented } from './Segmented';
import { Icon } from './Icon';
import { getServiceColor, getServiceLabel, PALETTE } from '../utils/colors';

interface CausalGraphProps {
  dagData: DAGData | null;
  selectedNodeId?: string | null;
  highlightedPath?: string[];
  invalidatedNodeIds?: string[];
  removedNodeId?: string | null;
  anomalyNodeIds?: string[];
  rootCauseNodeIds?: string[];
  onSelectNode: (node: DAGNode) => void;
  onSelectEdge?: (edge: DAGEdge) => void;
  defaultMode?: '2d' | '3d';
}

const NONE: string[] = [];

export const CausalGraph: React.FC<CausalGraphProps> = ({
  dagData,
  selectedNodeId,
  highlightedPath = NONE,
  invalidatedNodeIds = NONE,
  removedNodeId = null,
  anomalyNodeIds = NONE,
  rootCauseNodeIds = NONE,
  onSelectNode,
  onSelectEdge,
  defaultMode = '2d',
}) => {
  const [mode, setMode] = useState<'2d' | '3d'>(defaultMode);
  const [flow, setFlow] = useState(true);
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const handle = useRef<GraphHandle>(null);

  if (!dagData || !dagData.nodes.length) return null;

  const viewProps = {
    dagData,
    selectedNodeId,
    highlightedPath,
    invalidatedNodeIds,
    removedNodeId,
    anomalyNodeIds,
    rootCauseNodeIds,
    flow,
    onSelectNode,
    onSelectEdge,
    onHover: setHover,
  };

  return (
    <div className="graph-shell">
      {mode === '2d' ? <Graph2D key="2d" ref={handle} {...viewProps} /> : <Dag3D key="3d" ref={handle} {...viewProps} />}

      <div className="graph-toolbar">
        <Segmented
          ariaLabel="Graph view"
          value={mode}
          onChange={(m) => {
            setHover(null);
            setMode(m);
          }}
          options={[
            { value: '2d', label: '2D', icon: 'layers' },
            { value: '3d', label: '3D', icon: 'cube' },
          ]}
        />
        <span className="tb-sep" />
        <button className="btn btn-icon btn-sm btn-ghost" onClick={() => handle.current?.zoomIn()} title="Zoom in" aria-label="Zoom in">
          <Icon name="zoomin" size={16} />
        </button>
        <button className="btn btn-icon btn-sm btn-ghost" onClick={() => handle.current?.zoomOut()} title="Zoom out" aria-label="Zoom out">
          <Icon name="zoomout" size={16} />
        </button>
        <button className="btn btn-icon btn-sm btn-ghost" onClick={() => handle.current?.reset()} title="Fit to view" aria-label="Fit to view">
          <Icon name="fit" size={16} />
        </button>
        <span className="tb-sep" />
        <button className={`chip btn-chip ${flow ? 'is-on' : ''}`} onClick={() => setFlow((f) => !f)} title="Toggle causal flow animation">
          <Icon name="bolt" size={12} /> Flow
        </button>
      </div>

      {hover && (
        <div className="graph-tip" style={{ left: Math.min(hover.x + 16, 9999), top: hover.y + 16 }}>
          <div className="row" style={{ gap: 8, marginBottom: 6 }}>
            <span className="svc-tag" style={{ ['--c' as any]: getServiceColor(hover.node.service_id) }}>
              {getServiceLabel(hover.node.service_id)}
            </span>
            <span className="chip chip-iris">L{hover.node.lamport_ts}</span>
          </div>
          <b className="mono">{hover.node.event_type}</b>
          <small>
            {hover.node.region ? `${hover.node.region} · ` : ''}
            <span className="mono">{hover.node.id}</span>
          </small>
          <em>Hover isolates this event's causal lineage</em>
        </div>
      )}

      <div className="graph-legend">
        <span><i className="lg-line" style={{ background: PALETTE.iris1 }} /> Explicit</span>
        <span><i className="lg-line dashed" /> Inferred</span>
        <span><i className="lg-dot" style={{ background: PALETTE.warn }} /> Selected</span>
        {anomalyNodeIds.length > 0 && <span><i className="lg-dot" style={{ background: '#e11d48' }} /> Anomaly</span>}
        {rootCauseNodeIds.length > 0 && <span><i className="lg-dot" style={{ background: '#f43f5e' }} /> Root cause</span>}
        {invalidatedNodeIds.length > 0 && <span><i className="lg-dot" style={{ background: PALETTE.crit }} /> Invalidated</span>}
      </div>
    </div>
  );
};
