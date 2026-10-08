import React, { useState, useEffect } from 'react';
import { BenchmarkPanel } from '../components/BenchmarkPanel';
import { BenchmarkReport } from '../types';
import { ErrorState } from '../components/LoadingState';
import api from '../services/api';

export const BenchmarkPage: React.FC = () => {
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBenchmark = async (packetLoss: number = 0, clockDrift: number = 0) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getBenchmark(packetLoss, clockDrift);
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to execute clock benchmark');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBenchmark(0, 0);
  }, []);

  return (
    <>
      {error && <ErrorState message={error} onRetry={() => fetchBenchmark(0, 0)} />}
      <BenchmarkPanel
        report={report}
        loading={loading}
        onRunBenchmark={(loss, drift) => fetchBenchmark(loss, drift)}
      />
    </>
  );
};
