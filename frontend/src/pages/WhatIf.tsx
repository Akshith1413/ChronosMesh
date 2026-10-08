import React, { useState } from 'react';
import { WhatIfPanel } from '../components/WhatIfPanel';
import { CausalGraph } from '../components/CausalGraph';
import { EmptyState } from '../components/LoadingState';
import { WhatIfResult, DAGData, DAGNode } from '../types';

interface WhatIfPageProps {
  dagData: DAGData | null;
  nodes: DAGNode[];
  onRunWhatIfSimulation: (eventId: string) => Promise<WhatIfResult>;
}

export const WhatIfPage: React.FC<WhatIfPageProps> = ({
  dagData,
  nodes,
  onRunWhatIfSimulation,
}) => {
  const [selectedEventId, setSelectedEventId] = useState<string>('');
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const handleRunSimulation = async (eventId: string) => {
    setLoading(true);
    try {
      const res = await onRunWhatIfSimulation(eventId);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <WhatIfPanel
        nodes={nodes}
        selectedEventId={selectedEventId}
        result={result}
        loading={loading}
        onSelectEvent={(id) => setSelectedEventId(id)}
        onRunSimulation={handleRunSimulation}
      />

      {dagData && dagData.nodes.length > 0 ? (
        <div className="panel flush graph-panel fixed">
          <div className="graph-title">
            <div className="eyebrow">Blast radius overlay</div>
            <span className="muted small">Invalidated events turn crimson and shake in cascade order.</span>
          </div>
          <CausalGraph
            dagData={dagData}
            selectedNodeId={selectedEventId || null}
            removedNodeId={result?.removed_event_id}
            invalidatedNodeIds={result?.invalidated_events}
            onSelectNode={(n) => setSelectedEventId(n.id)}
          />
        </div>
      ) : (
        <EmptyState compact title="No trace loaded" description="Load a scenario to see the blast radius drawn on its causal graph." />
      )}
    </>
  );
};
