import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar, ViewTab } from './components/Sidebar';
import { Timeline } from './components/Timeline';
import { Aurora } from './components/Aurora';
import { Splash } from './components/Splash';
import { Toasts, ToastItem } from './components/Toasts';
import { LoginModal } from './components/LoginModal';
import { CommandPalette, Command } from './components/CommandPalette';
import { Home } from './pages/Home';
import { DashboardPage } from './pages/Dashboard';
import { TracePage } from './pages/Trace';
import { AnomaliesPage } from './pages/Anomalies';
import { WhatIfPage } from './pages/WhatIf';
import { BenchmarkPage } from './pages/Benchmark';
import { AnalyticsPage } from './pages/Analytics';
import { GraphDiffPage } from './pages/GraphDiff';
import { DocsPage } from './pages/Docs';
import { ExperimentsPage } from './pages/Experiments';
import { ObservabilityPage } from './pages/Observability';
import { useAuth } from './hooks/useAuth';
import { useSSE } from './hooks/useSSE';
import api from './services/api';
import {
  DAGData,
  Event,
  Scenario,
  SystemMetrics,
  AnomalyReport,
} from './types';

const VIEWS: Record<ViewTab, { title: string; eyebrow: string; icon: string }> = {
  overview: { title: 'Cluster Overview', eyebrow: 'Observe', icon: 'overview' },
  dag: { title: 'Reconstructed Causal Graph', eyebrow: 'Observe · Graph', icon: 'dag' },
  timeline: { title: 'Timeline Replay & Verification', eyebrow: 'Observe · Replay', icon: 'timeline' },
  experiments: { title: 'Fault-Injection Experiment Lab', eyebrow: 'Observe · Experiments', icon: 'flask' },
  anomaly: { title: 'Anomaly Detection Center', eyebrow: 'Analyse · Integrity', icon: 'anomaly' },
  whatif: { title: 'What-If Blast Radius Lab', eyebrow: 'Analyse · Simulation', icon: 'whatif' },
  benchmark: { title: 'Clock Strategy Benchmarks', eyebrow: 'Analyse · Clocks', icon: 'benchmark' },
  analytics: { title: 'Latency, Topology & Causal Replay Analytics', eyebrow: 'Analyse · Metrics', icon: 'analytics' },
  diff: { title: 'Causal Graph Diff & Behavioral Drift', eyebrow: 'Analyse · Drift', icon: 'diff' },
  observe: { title: 'Platform Observability', eyebrow: 'Operate · Telemetry', icon: 'gauge' },
  docs: { title: 'Architecture Documentation', eyebrow: 'Architecture', icon: 'docs' },
};

export const App: React.FC = () => {
  const { user, isAuthenticated, login, logout, loading: authLoading } = useAuth();
  const { events: liveEvents, status: sseStatus } = useSSE(isAuthenticated);

  // Navigation State
  const [currentView, setCurrentView] = useState<ViewTab>('overview');
  const [showLanding, setShowLanding] = useState<boolean>(!isAuthenticated);
  const [showLoginModal, setShowLoginModal] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState<boolean>(false);
  const [demoEnabled, setDemoEnabled] = useState<boolean>(false);

  useEffect(() => {
    api.getAuthConfig().then((c) => setDemoEnabled(c.demo_users_enabled)).catch(() => setDemoEnabled(false));
  }, []);

  // Application Data State
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [currentScenario, setCurrentScenario] = useState<string | null>(null);
  const [dagData, setDagData] = useState<DAGData | null>(null);
  const [arrivalEvents, setArrivalEvents] = useState<Event[]>([]);
  const [causalEvents, setCausalEvents] = useState<Event[]>([]);
  const [anomalyReport, setAnomalyReport] = useState<AnomalyReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastId = useRef(0);

  const showToast = useCallback((msg: string, tone: ToastItem['tone'] = 'info') => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-2), { id, msg, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3700);
  }, []);

  // Fetch initial metadata
  const refreshMetrics = useCallback(async () => {
    try {
      const m = await api.getMetrics();
      setMetrics(m);
      if (m.current_scenario) {
        setCurrentScenario(m.current_scenario);
      }
    } catch (e) {
      console.warn('Metrics unavailable:', e);
    }
  }, []);

  const refreshScenarios = useCallback(async () => {
    try {
      const list = await api.getScenarios();
      setScenarios(list);
    } catch (e) {
      console.warn('Scenarios unavailable:', e);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      setShowLanding(false);
      refreshMetrics();
      refreshScenarios();
    }
  }, [isAuthenticated, refreshMetrics, refreshScenarios]);

  // Load a scenario / trace
  const handleLoadScenario = useCallback(async (nameOrTraceId: string) => {
    setLoading(true);
    try {
      const res = await api.loadScenario(nameOrTraceId);
      setDagData(res.dag);
      setArrivalEvents(res.arrival_order || []);
      setCausalEvents(res.causal_order || []);
      setCurrentScenario(res.scenario.id);
      showToast(`Reconstructed ${res.event_count} events for ${res.scenario.name}`);

      // Fetch anomalies for this scenario
      const anoms = await api.getAnomalies();
      setAnomalyReport(anoms);
      refreshMetrics();
    } catch (err: any) {
      showToast(err.message || 'Failed to load scenario', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast, refreshMetrics]);

  // After the server's store was filled from elsewhere (e.g. an experiment execution), pull it into the views.
  const refreshAfterLoad = useCallback(async (scenario: string) => {
    setLoading(true);
    try {
      const [dag, arrival, causal, anoms] = await Promise.all([
        api.getDag(), api.getArrivalEvents(), api.getCausalEvents(), api.getAnomalies(),
      ]);
      setDagData(dag);
      setArrivalEvents(arrival.events || []);
      setCausalEvents(causal.events || []);
      setAnomalyReport(anoms);
      setCurrentScenario(scenario);
      showToast(`Loaded ${arrival.count} events from ${scenario}`);
      refreshMetrics();
    } catch (err: any) {
      showToast(err.message || 'Failed to load execution', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast, refreshMetrics]);

  // The server keeps the active trace between page loads — rehydrate the local view from it.
  const hydrated = useRef(false);
  useEffect(() => {
    if (!isAuthenticated || hydrated.current || dagData || !metrics?.current_scenario) return;
    hydrated.current = true;
    (async () => {
      try {
        const [dag, arrival, causal, anoms] = await Promise.all([
          api.getDag(),
          api.getArrivalEvents(),
          api.getCausalEvents(),
          api.getAnomalies(),
        ]);
        setDagData(dag);
        setArrivalEvents(arrival.events || []);
        setCausalEvents(causal.events || []);
        setAnomalyReport(anoms);
      } catch (e) {
        console.warn('Could not rehydrate active trace:', e);
      }
    })();
  }, [isAuthenticated, metrics, dagData]);

  useEffect(() => {
    const handleAuthExpired = () => {
      setShowLoginModal(false);
      setShowLanding(true);
      showToast('Authentication expired. Please sign in again.', 'warn');
    };
    const handleOpenLogin = () => {
      setShowLoginModal(true);
    };

    window.addEventListener('auth:expired', handleAuthExpired);
    window.addEventListener('auth:open-login', handleOpenLogin);

    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
      window.removeEventListener('auth:open-login', handleOpenLogin);
    };
  }, [showToast]);

  const handleLogout = useCallback(() => {
    logout();
    setShowLoginModal(false);
    setShowLanding(true);
    setPaletteOpen(false);
    showToast('Logged out of ChronosMesh');
  }, [logout, showToast]);

  const handleOpenDashboardDirectly = async () => {
    if (!isAuthenticated) {
      // Auto sign-in is a convenience for demo deployments only; real deployments always ask.
      if (!demoEnabled) {
        setShowLoginModal(true);
        return;
      }
      try {
        await login('guru', 'chronosmesh');
        setShowLanding(false);
        showToast('Logged in as Guru (Admin) — Welcome to ChronosMesh!');
      } catch (err: any) {
        setShowLoginModal(true);
      }
    } else {
      setShowLanding(false);
    }
  };

  const handleLoginSubmit = async (username: string, password: string) => {
    setLoginError(null);
    try {
      await login(username, password);
      setShowLoginModal(false);
      setShowLanding(false);
      refreshMetrics();
      refreshScenarios();
      showToast('Logged in successfully as ' + username);
    } catch (err: any) {
      setLoginError(err.message || 'Login failed');
    }
  };

  // ⌘K / Ctrl+K command palette (dashboard only)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (!showLanding) setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showLanding]);

  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [];
    (Object.keys(VIEWS) as ViewTab[]).forEach((v) =>
      list.push({
        id: `view-${v}`,
        group: 'Go to',
        label: VIEWS[v].title,
        hint: VIEWS[v].eyebrow,
        icon: VIEWS[v].icon,
        keywords: v,
        run: () => setCurrentView(v),
      })
    );
    scenarios.forEach((s) =>
      list.push({
        id: `trace-${s.id}`,
        group: 'Load a trace',
        label: `${s.trace_id || s.id} — ${s.name}`,
        hint: s.description,
        icon: 'bolt',
        keywords: `${s.pattern} scenario trace`,
        run: () => {
          handleLoadScenario(s.id);
        },
      })
    );
    list.push(
      { id: 'act-refresh', group: 'Actions', label: 'Refresh metrics', icon: 'refresh', run: refreshMetrics },
      { id: 'act-docs', group: 'Actions', label: 'Open API documentation', icon: 'external', run: () => window.open('/api/docs', '_blank') },
      user
        ? { id: 'act-logout', group: 'Actions', label: 'Log out', icon: 'logout', run: handleLogout }
        : { id: 'act-login', group: 'Actions', label: 'Log in', icon: 'login', run: () => setShowLoginModal(true) }
    );
    return list;
  }, [scenarios, user, handleLoadScenario, refreshMetrics, handleLogout]);

  const loginModal = (
    <LoginModal
      demoEnabled={demoEnabled}
      open={showLoginModal}
      loading={authLoading}
      error={loginError}
      onClose={() => {
        setShowLoginModal(false);
        setLoginError(null);
      }}
      onSubmit={handleLoginSubmit}
    />
  );

  if (showLanding && !isAuthenticated) {
    return (
      <>
        <Aurora />
        <Splash />
        <Home
          onOpenDashboard={handleOpenDashboardDirectly}
          onOpenLogin={() => setShowLoginModal(true)}
          isAuthenticated={isAuthenticated}
        />
        {loginModal}
        <Toasts items={toasts} />
      </>
    );
  }

  const view = VIEWS[currentView];

  return (
    <div className="shell">
      <Aurora />

      <Sidebar
        currentView={currentView}
        onSelectView={(v) => setCurrentView(v)}
        user={user}
        currentScenario={currentScenario}
        anomalyCount={anomalyReport?.total || 0}
        onLogout={handleLogout}
        onOpenLogin={() => setShowLoginModal(true)}
        onSelectTrace={(t) => handleLoadScenario(t)}
        scenarios={scenarios}
      />

      <div className="stage">
        <Navbar
          title={view.title}
          eyebrow={view.eyebrow}
          subtitle={
            currentScenario
              ? `Active workflow: ${currentScenario.replace(/_/g, ' ')}`
              : 'Select a scenario to reconstruct causality'
          }
          user={user}
          currentScenario={currentScenario}
          onRefresh={refreshMetrics}
          onOpenLogin={() => setShowLoginModal(true)}
          onLogout={handleLogout}
          onOpenPalette={() => setPaletteOpen(true)}
          sseStatus={sseStatus}
        />

        <main className="main">
          <div className="page" key={currentView}>
            {currentView === 'overview' && (
              <DashboardPage
                metrics={metrics}
                scenarios={scenarios}
                currentScenario={currentScenario}
                events={arrivalEvents}
                liveEvents={liveEvents}
                onLoadScenario={handleLoadScenario}
                onNavigateToDag={() => setCurrentView('dag')}
                loading={loading}
                anomalyReport={anomalyReport}
              />
            )}

            {currentView === 'dag' && (
              <TracePage
                dagData={dagData}
                anomalies={anomalyReport?.anomalies || []}
                currentTrace={currentScenario}
                onRunWhatIf={() => setCurrentView('whatif')}
                onTraceRootCause={() => setCurrentView('anomaly')}
              />
            )}

            {currentView === 'timeline' && (
              <Timeline
                arrivalEvents={arrivalEvents}
                causalEvents={causalEvents}
              />
            )}

            {currentView === 'anomaly' && (
              <AnomaliesPage
                anomalyReport={anomalyReport}
                nodes={dagData?.nodes || []}
                onSelectAnomalyEvent={() => setCurrentView('dag')}
                onTraceRootCause={(eventId) => api.getRootCause(eventId)}
              />
            )}

            {currentView === 'whatif' && (
              <WhatIfPage
                dagData={dagData}
                nodes={dagData?.nodes || []}
                onRunWhatIfSimulation={(eventId) => api.runWhatIf(eventId)}
              />
            )}

            {currentView === 'experiments' && (
              <ExperimentsPage
                canRun={user?.role === 'admin' || user?.role === 'analyst'}
                onOpenExplorer={async (scenario) => {
                  setCurrentScenario(scenario);
                  await refreshAfterLoad(scenario);
                  setCurrentView('dag');
                }}
              />
            )}

            {currentView === 'benchmark' && <BenchmarkPage />}

            {currentView === 'analytics' && <AnalyticsPage />}

            {currentView === 'diff' && <GraphDiffPage />}

            {currentView === 'observe' && <ObservabilityPage metrics={metrics} />}

            {currentView === 'docs' && <DocsPage />}
          </div>
        </main>
      </div>

      {loading && (
        <div className="reconstructing" role="status" aria-live="polite">
          <div className="rc-card">
            <div className="loader-track"><i /><i /><i /><b /></div>
            <span>Reconstructing causal order…</span>
          </div>
        </div>
      )}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
      {loginModal}
      <Toasts items={toasts} />
    </div>
  );
};

export default App;
