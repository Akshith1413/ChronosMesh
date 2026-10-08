import React, { useState } from 'react';
import { CausalGraph } from '../components/CausalGraph';
import { EventDetails } from '../components/EventDetails';
import { EmptyState } from '../components/LoadingState';
import { DAGData, DAGNode, DAGEdge, Anomaly } from '../types';

interface TracePageProps {
  dagData: DAGData | null;
  anomalies: Anomaly[];
  currentTrace: string | null;
  onRunWhatIf: (nodeId: string) => void;
  onTraceRootCause: (nodeId: string) => void;
}

export const TracePage: React.FC<TracePageProps> = ({
  dagData,
  anomalies,
  currentTrace,
  onRunWhatIf,
  onTraceRootCause,
}) => {
  const [selectedNode, setSelectedNode] = useState<DAGNode | null>(null);
  const [highlightedPath] = useState<string[]>([]);

  const handleSelectNode = React.useCallback((node: DAGNode) => {
    setSelectedNode(node);
  }, []);

  // Auto-select initial root node on load, or preserve active selection across trace changes
  React.useEffect(() => {
    if (dagData && dagData.nodes && dagData.nodes.length > 0) {
      setSelectedNode((prev) => {
        if (!prev) {
          const rootId = dagData.roots && dagData.roots[0];
          const rootNode = rootId ? dagData.nodes.find((n) => n.id === rootId) : null;
          return rootNode || dagData.nodes[0];
        }
        const match = dagData.nodes.find((n) => n.id === prev.id);
        return match || dagData.nodes[0];
      });
    } else {
      setSelectedNode(null);
    }
  }, [dagData]);

  const anomalyNodeIds = React.useMemo(() => {
    const ids = new Set<string>();
    anomalies.forEach((a) => {
      if (a.source_event_id) ids.add(a.source_event_id);
      if (a.target_event_id) ids.add(a.target_event_id);
    });
    return Array.from(ids);
  }, [anomalies]);

  if (!dagData || !dagData.nodes.length) {
    return (
      <EmptyState
        title="No active trace loaded"
        description="Select or load a trace from the dock or the overview to generate the reconstructed causal DAG."
      />
    );
  }

  const handleSelectEdge = (_: DAGEdge) => {};

  return (
    <div className="trace-grid">
      <div className="panel flush graph-panel">
        <div className="graph-stats">
          <span><b className="num">{dagData.nodes.length}</b> nodes</span>
          <i />
          <span><b className="num">{dagData.edges.length}</b> edges</span>
          <i />
          <span><b className="num">{dagData.roots?.length || 1}</b> root{(dagData.roots?.length || 1) === 1 ? '' : 's'}</span>
          {anomalyNodeIds.length > 0 && (
            <>
              <i />
              <span style={{ color: '#c3213f' }}><b className="num">{anomalyNodeIds.length}</b> flagged</span>
            </>
          )}
        </div>

        <CausalGraph
          dagData={dagData}
          selectedNodeId={selectedNode?.id}
          highlightedPath={highlightedPath}
          anomalyNodeIds={anomalyNodeIds}
          onSelectNode={handleSelectNode}
          onSelectEdge={handleSelectEdge}
        />
      </div>

      <EventDetails
        node={selectedNode}
        edges={dagData.edges}
        nodes={dagData.nodes}
        anomalies={anomalies}
        currentTrace={currentTrace}
        onRunWhatIf={onRunWhatIf}
        onTraceRootCause={onTraceRootCause}
        onSelectNeighbor={(id) => {
          const n = dagData.nodes.find((x) => x.id === id);
          if (n) setSelectedNode(n);
        }}
        onClose={() => setSelectedNode(null)}
      />
    </div>
  );
};
