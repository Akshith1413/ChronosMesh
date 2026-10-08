import React, { useState } from 'react';
import { AnomalyPanel } from '../components/AnomalyPanel';
import { RootCausePanel } from '../components/RootCausePanel';
import { AnomalyReport, RootCauseResult, DAGNode } from '../types';

interface AnomaliesPageProps {
  anomalyReport: AnomalyReport | null;
  nodes: DAGNode[];
  onSelectAnomalyEvent: (eventId: string) => void;
  onTraceRootCause: (eventId: string) => Promise<RootCauseResult>;
}

export const AnomaliesPage: React.FC<AnomaliesPageProps> = ({
  anomalyReport,
  nodes,
  onSelectAnomalyEvent,
  onTraceRootCause,
}) => {
  const [selectedFailureEventId, setSelectedFailureEventId] = useState<string>('');
  const [rootCauseResult, setRootCauseResult] = useState<RootCauseResult | null>(null);
  const [tracing, setTracing] = useState<boolean>(false);

  const handleRunTrace = async () => {
    if (!selectedFailureEventId) return;
    setTracing(true);
    try {
      const res = await onTraceRootCause(selectedFailureEventId);
      setRootCauseResult(res);
    } finally {
      setTracing(false);
    }
  };

  return (
    <>
      <AnomalyPanel
        anomalies={anomalyReport?.anomalies || []}
        total={anomalyReport?.total || 0}
        severitySummary={anomalyReport?.severity_summary}
        onSelectAnomalyEvent={onSelectAnomalyEvent}
      />

      <RootCausePanel
        nodes={nodes}
        selectedFailureEventId={selectedFailureEventId}
        result={rootCauseResult}
        loading={tracing}
        onSelectFailureEvent={(id) => setSelectedFailureEventId(id)}
        onRunTrace={handleRunTrace}
      />
    </>
  );
};
