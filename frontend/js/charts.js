/**
 * ChronosMesh — charts.js
 * Chart.js visualizations for benchmark results and confidence scores.
 * Author: Guru Sai Prasad Reddy
 */

'use strict';

const Charts = (() => {
  let benchmarkChart = null;
  let confidenceChart = null;

  const CHART_DEFAULTS = {
    font: { family: 'Inter, sans-serif', size: 12 },
    color: '#94a3b8',
  };

  Chart.defaults.color = CHART_DEFAULTS.color;
  Chart.defaults.font  = CHART_DEFAULTS.font;

  // ── Benchmark bar chart ───────────────────────────────────────────────────
  function renderBenchmark(data) {
    const results = data.results;
    const winner  = data.winner;

    // Strategy cards
    const cardColors = {
      vector_clock: { color: '#00d4ff', label: 'Vector Clocks', sub: 'Full causal precision — O(N) per node' },
      lamport_clock: { color: '#8b5cf6', label: 'Lamport Clocks', sub: 'Total order only — no concurrency' },
      physical_time: { color: '#f59e0b', label: 'Physical Time',  sub: 'Clock skew prone — unreliable' },
    };

    results.forEach(r => {
      const cfg = cardColors[r.strategy] || { color: '#64748b', label: r.strategy, sub: '' };
      const cardId = `strategy-${r.strategy.replace('_', '-')}`;
      const card = document.getElementById(cardId);
      if (!card) return;

      card.classList.toggle('winner', r.strategy === winner);
      card.querySelector('.s-acc').textContent = r.accuracy_pct + '%';
      card.querySelector('.s-acc').style.color = cfg.color;

      const bar = card.querySelector('.accuracy-bar');
      if (bar) {
        bar.style.width = r.accuracy_pct + '%';
        bar.style.background = cfg.color;
      }
    });

    // Bar chart
    const ctx = document.getElementById('benchmark-chart');
    if (!ctx) return;

    if (benchmarkChart) { benchmarkChart.destroy(); benchmarkChart = null; }

    const labels = results.map(r => (cardColors[r.strategy]?.label || r.strategy));
    const accData = results.map(r => r.accuracy_pct);
    const memData = results.map(r => r.memory_kb);
    const timeData = results.map(r => r.computation_time_ms);
    const colors  = results.map(r => (cardColors[r.strategy]?.color || '#64748b'));

    benchmarkChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Accuracy (%)',
            data: accData,
            backgroundColor: colors.map(c => c + '33'),
            borderColor: colors,
            borderWidth: 2,
            borderRadius: 6,
            yAxisID: 'y',
          },
          {
            label: 'Memory (KB)',
            data: memData,
            backgroundColor: 'rgba(236,72,153,0.15)',
            borderColor: '#ec4899',
            borderWidth: 1.5,
            borderRadius: 6,
            type: 'line',
            yAxisID: 'y2',
            tension: 0.3,
            pointRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { padding: 16, usePointStyle: true } },
          tooltip: {
            backgroundColor: '#0d1526',
            borderColor: '#334155',
            borderWidth: 1,
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ${ctx.raw}${ctx.dataset.label.includes('%') ? '' : ctx.dataset.label.includes('KB') ? ' KB' : ''}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: { color: '#94a3b8' },
          },
          y: {
            type: 'linear', position: 'left',
            min: 0, max: 110,
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: { color: '#94a3b8', callback: v => v + '%' },
            title: { display: true, text: 'Accuracy (%)', color: '#64748b' },
          },
          y2: {
            type: 'linear', position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#ec4899', callback: v => v + ' KB' },
            title: { display: true, text: 'Memory (KB)', color: '#ec4899' },
          },
        },
      },
    });
  }

  // ── Confidence doughnut ───────────────────────────────────────────────────
  async function renderConfidence() {
    const ctx = document.getElementById('confidence-chart');
    if (!ctx) return;
    try {
      const data = await window.API.get('/api/analysis/confidence');
      const scores = data.edge_scores;
      if (!scores?.length) return;

      const buckets = { 'High (>0.9)': 0, 'Medium (0.7–0.9)': 0, 'Low (<0.7)': 0 };
      scores.forEach(s => {
        if (s.confidence > 0.9) buckets['High (>0.9)']++;
        else if (s.confidence >= 0.7) buckets['Medium (0.7–0.9)']++;
        else buckets['Low (<0.7)']++;
      });

      if (confidenceChart) { confidenceChart.destroy(); confidenceChart = null; }
      confidenceChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: Object.keys(buckets),
          datasets: [{
            data: Object.values(buckets),
            backgroundColor: ['rgba(16,185,129,0.7)', 'rgba(245,158,11,0.7)', 'rgba(239,68,68,0.7)'],
            borderColor:     ['#10b981', '#f59e0b', '#ef4444'],
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: '65%',
          plugins: {
            legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14 } },
            tooltip: { backgroundColor: '#0d1526', borderColor: '#334155', borderWidth: 1 },
          },
        },
      });

      // Update avg confidence display
      const avgEl = document.getElementById('avg-confidence');
      if (avgEl) avgEl.textContent = (data.average_confidence * 100).toFixed(1) + '%';
    } catch (e) {
      console.warn('Confidence chart error:', e);
    }
  }

  return { renderBenchmark, renderConfidence };
})();

window.Charts = Charts;
