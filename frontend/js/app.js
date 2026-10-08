/**
 * ChronosMesh Frontend — app.js
 * API client, auth state, routing, toast notifications.
 * Author: Guru Sai Prasad Reddy
 */

'use strict';

// ── Config ────────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000';

// ── Global state ──────────────────────────────────────────────────────────────
const State = {
  token: localStorage.getItem('cm_token') || null,
  user:  JSON.parse(localStorage.getItem('cm_user') || 'null'),
  scenario: null,
  dagData: null,
  events: [],
  anomalies: [],
  benchmarkResults: [],
  whatIfResult: null,
  selectedNode: null,
  currentView: 'overview',
  playInterval: null,
  playStep: 0,
};

// ── API Client ────────────────────────────────────────────────────────────────
const API = {
  async request(method, path, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (State.token) opts.headers['Authorization'] = `Bearer ${State.token}`;
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(`${API_BASE}${path}`, opts);
    if (res.status === 401) {
      logout();
      throw new Error('Session expired — please log in again');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  get:    (path)        => API.request('GET',    path),
  post:   (path, body)  => API.request('POST',   path, body),
  delete: (path)        => API.request('DELETE', path),

  // Auth
  login: async (username, password) => {
    const form = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Login failed'); }
    return res.json();
  },
};

// ── Toast Notifications ───────────────────────────────────────────────────────
function toast(message, type = 'info', duration = 3500) {
  const icons = { info: '📡', success: '✅', error: '❌', warning: '⚠️' };
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || '📡'}</span><span>${message}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── Auth ──────────────────────────────────────────────────────────────────────
function logout() {
  State.token = null; State.user = null;
  localStorage.removeItem('cm_token');
  localStorage.removeItem('cm_user');
  showLanding();
}

function saveAuth(token, user) {
  State.token = token; State.user = user;
  localStorage.setItem('cm_token', token);
  localStorage.setItem('cm_user', JSON.stringify(user));
}

// ── Service colour map ────────────────────────────────────────────────────────
const SVC_COLORS = {
  'order-svc':     '#3b82f6',
  'payment-svc':   '#10b981',
  'inventory-svc': '#f59e0b',
  'shipping-svc':  '#8b5cf6',
  'notification-svc': '#ec4899',
};

function svcColor(svcId) {
  if (!svcId) return '#64748b';
  for (const [key, col] of Object.entries(SVC_COLORS)) {
    if (svcId.includes(key.split('-')[0])) return col;
  }
  return '#64748b';
}

function svcLabel(svcId) {
  if (!svcId) return 'unknown';
  return svcId.replace('-svc', '').toUpperCase();
}

// ── Page routing ──────────────────────────────────────────────────────────────
function showLanding() {
  document.getElementById('landing-page').style.display = 'block';
  document.getElementById('app-shell').style.display = 'none';
  Landing.init();
}

function showDashboard() {
  document.getElementById('landing-page').style.display = 'none';
  document.getElementById('app-shell').style.display = 'flex';
  updateUserCard();
  switchView('overview');
  loadMetrics();
}

function switchView(viewName) {
  State.currentView = viewName;
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const viewEl = document.getElementById(`${viewName}-view`);
  const navEl  = document.querySelector(`[data-view="${viewName}"]`);
  if (viewEl) viewEl.classList.add('active');
  if (navEl)  navEl.classList.add('active');

  // Page titles
  const titles = {
    overview:    ['Overview',          'Select a scenario to begin analysis'],
    dag:         ['Causal DAG',        'Reconstructed causal execution graph'],
    timeline:    ['Timeline Replay',   'Arrival order vs reconstructed causal order'],
    anomaly:     ['Anomaly Center',    'Detected causal violations and clock anomalies'],
    whatif:      ['What-If Lab',       'Blast radius simulation — remove an event and see consequences'],
    benchmark:   ['Clock Benchmark',   'Compare Lamport vs Vector vs Hybrid Logical Clocks'],
    docs:        ['Architecture Docs', 'API reference and system design documentation'],
  };
  const [title, sub] = titles[viewName] || ['ChronosMesh', ''];
  document.getElementById('page-title').textContent    = title;
  document.getElementById('page-subtitle').textContent = sub;

  // Lazy-load view content
  if (viewName === 'dag' && State.dagData) DAGViz.render(State.dagData);
  if (viewName === 'timeline' && State.events.length) Timeline.init();
  if (viewName === 'anomaly') loadAnomalies();
  if (viewName === 'whatif') loadWhatIf();
}

function updateUserCard() {
  if (!State.user) return;
  const initials = (State.user.full_name || State.user.username || 'G')
    .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  document.getElementById('user-avatar').textContent = initials;
  document.getElementById('user-name').textContent   = State.user.full_name || State.user.username;
  document.getElementById('user-role').textContent   = State.user.role || 'user';
}

// ── Metrics ───────────────────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const m = await API.get('/api/metrics');
    document.getElementById('stat-events').textContent   = m.event_count;
    document.getElementById('stat-edges').textContent    = m.dag_edges;
    document.getElementById('stat-nodes').textContent    = m.dag_nodes;
    document.getElementById('stat-services').textContent = m.services_tracked;
    if (m.current_scenario) {
      State.scenario = m.current_scenario;
      document.getElementById('current-scenario').textContent = m.current_scenario.replace(/_/g, ' ');
      document.getElementById('scenario-badge').style.display = 'flex';
    }
  } catch (e) {
    // API not reachable — demo still works with mock
  }
}

// ── Scenario loading ──────────────────────────────────────────────────────────
async function loadScenario(name) {
  const card = document.querySelector(`[data-scenario="${name}"]`);
  if (card) card.classList.add('loading');
  showLoading('Loading scenario…');
  try {
    const data = await API.post(`/api/scenarios/${name}/load`);
    State.dagData  = data.dag;
    State.events   = data.arrival_order || [];
    State.scenario = name;
    State.anomalies = [];
    State.whatIfResult = null;
    State.selectedNode = null;
    hideLoading();

    // Update badge
    document.getElementById('current-scenario').textContent = name.replace(/_/g, ' ');
    document.getElementById('scenario-badge').style.display = 'flex';

    // Update stats
    document.getElementById('stat-events').textContent   = data.event_count;
    document.getElementById('stat-nodes').textContent    = data.dag.nodes.length;
    document.getElementById('stat-edges').textContent    = data.dag.edges.length;
    document.getElementById('stat-services').textContent =
      new Set(data.dag.nodes.map(n => n.service_id)).size;

    updateEventFeed(data.dag.nodes);
    toast(`Scenario "${name.replace(/_/g, ' ')}" loaded — ${data.event_count} events reconstructed`, 'success');
    switchView('dag');
    setTimeout(() => DAGViz.render(State.dagData), 100);
  } catch (e) {
    hideLoading();
    toast(e.message, 'error');
  } finally {
    if (card) card.classList.remove('loading');
  }
}

function updateEventFeed(nodes) {
  const feed = document.getElementById('event-feed');
  if (!feed) return;
  const svcSet = new Set(nodes.map(n => n.service_id));
  document.getElementById('stat-services').textContent = svcSet.size;

  feed.innerHTML = nodes.map(n => `
    <div class="event-row">
      <span class="event-svc-dot" style="background:${svcColor(n.service_id)}"></span>
      <span class="event-type">${n.event_type}</span>
      <span class="event-svc">${svcLabel(n.service_id)}</span>
      <span class="event-lamport">L${n.lamport_ts}</span>
    </div>
  `).join('');
}

// ── Anomaly loading ───────────────────────────────────────────────────────────
async function loadAnomalies() {
  const tbody = document.getElementById('anomaly-tbody');
  if (!State.dagData) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="icon">🔍</div><h3>No scenario loaded</h3><p>Load a scenario from Overview first</p></div></td></tr>`;
    return;
  }
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px"><span class="spinner"></span></td></tr>`;
  try {
    const data = await API.get('/api/analysis/anomalies');
    State.anomalies = data.anomalies;

    document.getElementById('total-anomalies').textContent    = data.total;
    document.getElementById('critical-anomalies').textContent = data.severity_summary.CRITICAL;
    document.getElementById('warning-anomalies').textContent  = data.severity_summary.WARNING;

    // Badge on nav
    const badge = document.querySelector('[data-view="anomaly"] .nav-badge');
    if (badge && data.total > 0) { badge.textContent = data.total; badge.classList.add('show'); }

    if (data.anomalies.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:32px"><div class="icon">✅</div><h3>No anomalies detected</h3><p>The causal graph is consistent</p></div></td></tr>`;
      return;
    }

    tbody.innerHTML = data.anomalies.map(a => `
      <tr>
        <td><span class="severity-badge ${a.severity}">${a.severity}</span></td>
        <td><span class="mono">${a.anomaly_type}</span></td>
        <td>${a.description}</td>
        <td class="event-id-mono">${(a.source_event_id || '—').slice(0, 8)}…</td>
        <td class="event-id-mono">${a.target_event_id ? a.target_event_id.slice(0, 8) + '…' : '—'}</td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--c-red);padding:20px">${e.message}</td></tr>`;
  }
}

// ── What-if loading ───────────────────────────────────────────────────────────
function loadWhatIf() {
  const sel = document.getElementById('whatif-event-select');
  if (!State.dagData) { sel.innerHTML = '<option>Load a scenario first</option>'; return; }
  sel.innerHTML = State.dagData.nodes.map(n =>
    `<option value="${n.id}">${n.event_type} (${svcLabel(n.service_id)})</option>`
  ).join('');
}

async function runWhatIf() {
  const sel = document.getElementById('whatif-event-select');
  if (!sel.value || !State.dagData) return;
  try {
    const data = await API.post(`/api/analysis/whatif/${sel.value}`);
    State.whatIfResult = data;
    renderWhatIfResult(data);
  } catch (e) { toast(e.message, 'error'); }
}

function renderWhatIfResult(data) {
  const deg = Math.round((data.blast_radius_pct / 100) * 360);
  const gauge = document.getElementById('blast-gauge-circle');
  if (gauge) {
    gauge.style.setProperty('--pct-deg', `${deg}deg`);
    document.getElementById('blast-pct').textContent = data.blast_radius_pct + '%';
  }
  document.getElementById('cascade-depth').textContent = data.cascade_depth;
  document.getElementById('affected-services').textContent = data.affected_services.join(', ') || '—';

  const list = document.getElementById('invalidated-list');
  const invalid = data.invalidated_events || [];
  const surviving = data.surviving_events || [];

  list.innerHTML = [
    ...invalid.map(id => `<div class="invalidated-item removed">❌ <span class="mono">${id.slice(0,8)}…</span> <span style="color:var(--c-red);margin-left:auto">invalidated</span></div>`),
    ...surviving.map(id => `<div class="invalidated-item surviving">✅ <span class="mono">${id.slice(0,8)}…</span> <span style="color:var(--c-emerald);margin-left:auto">surviving</span></div>`),
  ].join('');
}

// ── Benchmark ─────────────────────────────────────────────────────────────────
async function runBenchmark() {
  if (!State.dagData) { toast('Load a scenario first', 'warning'); return; }
  const pl  = parseFloat(document.getElementById('packet-loss-input').value)  || 0;
  const cd  = parseFloat(document.getElementById('clock-drift-input').value)  || 0;
  try {
    const data = await API.get(`/api/analysis/benchmark?packet_loss_pct=${pl}&clock_drift_ms=${cd}`);
    State.benchmarkResults = data.results;
    Charts.renderBenchmark(data);
  } catch (e) { toast(e.message, 'error'); }
}

// ── Loading overlay ───────────────────────────────────────────────────────────
function showLoading(msg = 'Loading…') {
  let ov = document.getElementById('global-loading');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'global-loading';
    ov.className = 'loading-overlay';
    ov.innerHTML = `<div class="spinner"></div><p id="loading-msg">${msg}</p>`;
    document.body.appendChild(ov);
  } else {
    document.getElementById('loading-msg').textContent = msg;
    ov.style.display = 'flex';
  }
}

function hideLoading() {
  const ov = document.getElementById('global-loading');
  if (ov) ov.style.display = 'none';
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Decide landing vs dashboard
  if (State.token && State.user) {
    showDashboard();
  } else {
    showLanding();
  }

  // Login form
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const user = document.getElementById('login-username').value.trim();
      const pass = document.getElementById('login-password').value;
      const errEl = document.getElementById('login-error');
      const btn   = document.getElementById('login-btn');
      errEl.classList.remove('show');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Signing in…';
      try {
        const res = await API.login(user, pass);
        saveAuth(res.access_token, res.user);
        closeModal('login-modal');
        showDashboard();
        toast(`Welcome back, ${res.user.full_name}! 🚀`, 'success');
      } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '🔐 Sign In';
      }
    });
  }

  // Nav items
  document.querySelectorAll('.nav-item[data-view]').forEach(el => {
    el.addEventListener('click', () => switchView(el.dataset.view));
  });

  // Logout
  document.getElementById('logout-btn')?.addEventListener('click', logout);
});

// ── Modal helpers ─────────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id)?.classList.add('active'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('active'); }

// Expose globals
window.State       = State;
window.API         = API;
window.SVC_COLORS  = SVC_COLORS;
window.svcColor    = svcColor;
window.svcLabel    = svcLabel;
window.toast       = toast;
window.openModal   = openModal;
window.closeModal  = closeModal;
window.loadScenario = loadScenario;
window.switchView  = switchView;
window.runWhatIf   = runWhatIf;
window.runBenchmark = runBenchmark;
window.showDashboard = showDashboard;
window.showLanding   = showLanding;
