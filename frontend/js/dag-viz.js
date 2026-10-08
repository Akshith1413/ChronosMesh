/**
 * ChronosMesh — dag-viz.js
 * D3.js v7 interactive causal DAG visualizer.
 * Hierarchical swimlane layout: each service = column, depth = row.
 * Author: Guru Sai Prasad Reddy
 */

'use strict';

const DAGViz = (() => {
  let svg, g, simulation, tooltip;
  const NODE_R  = 26;
  const COL_W   = 200;
  const ROW_H   = 110;
  const PADDING = 60;

  // ── Compute layout positions ──────────────────────────────────────────────
  function computePositions(nodes, edges) {
    // 1. Topological order via Kahn's algorithm
    const inDegree = {};
    const adj = {};
    nodes.forEach(n => { inDegree[n.id] = 0; adj[n.id] = []; });
    edges.forEach(e => {
      inDegree[e.target] = (inDegree[e.target] || 0) + 1;
      adj[e.source].push(e.target);
    });

    const queue = nodes.filter(n => inDegree[n.id] === 0).map(n => n.id);
    const depth = {};
    queue.forEach(id => depth[id] = 0);
    const topo = [];

    while (queue.length) {
      const cur = queue.shift();
      topo.push(cur);
      (adj[cur] || []).forEach(nxt => {
        depth[nxt] = Math.max(depth[nxt] || 0, (depth[cur] || 0) + 1);
        if (--inDegree[nxt] === 0) queue.push(nxt);
      });
    }

    // 2. Assign columns by service
    const services = [...new Set(nodes.map(n => n.service_id))];
    const svcCol   = {};
    services.forEach((s, i) => svcCol[s] = i);

    // 3. Assign row within each (service, depth) bucket
    const slotCount = {};
    nodes.forEach(n => {
      const key = `${n.service_id}_${depth[n.id] || 0}`;
      slotCount[key] = (slotCount[key] || 0);
      n._slot = slotCount[key]++;
    });

    const positions = {};
    nodes.forEach(n => {
      const col  = svcCol[n.service_id] || 0;
      const row  = depth[n.id] || 0;
      positions[n.id] = {
        x: PADDING + col * COL_W + n._slot * 40,
        y: PADDING + row * ROW_H,
      };
    });

    return { positions, services, svcCol, maxDepth: Math.max(...Object.values(depth), 0) };
  }

  // ── Main render ───────────────────────────────────────────────────────────
  function render(dagData) {
    const container = document.getElementById('dag-svg-container');
    if (!container) return;
    container.innerHTML = '';

    const { nodes, edges } = dagData;
    if (!nodes || nodes.length === 0) {
      document.getElementById('dag-empty').style.display = 'flex';
      return;
    }
    document.getElementById('dag-empty').style.display = 'none';

    const W = container.clientWidth  || 900;
    const H = container.clientHeight || 600;

    // Tooltip
    tooltip = d3.select(container)
      .append('div').attr('class', 'dag-tooltip').attr('id', 'dag-tooltip');

    svg = d3.select(container).append('svg')
      .attr('id', 'dag-svg')
      .attr('width', W).attr('height', H);

    // Defs: arrowhead marker
    const defs = svg.append('defs');
    ['normal', 'explicit', 'highlighted', 'invalidated'].forEach(type => {
      const colors = {
        normal:      '#475569',
        explicit:    '#00d4ff',
        highlighted: '#f59e0b',
        invalidated: '#ef4444',
      };
      defs.append('marker')
        .attr('id',          `arrow-${type}`)
        .attr('viewBox',     '0 -5 10 10')
        .attr('refX',        NODE_R + 8)
        .attr('refY',        0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient',      'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', colors[type]);
    });

    // Zoom + pan
    const zoom = d3.zoom().scaleExtent([0.3, 3]).on('zoom', e => g.attr('transform', e.transform));
    svg.call(zoom);

    g = svg.append('g');

    const { positions, services, maxDepth } = computePositions(nodes, edges);

    // Compute canvas extents and center the layout
    const xs = Object.values(positions).map(p => p.x);
    const ys = Object.values(positions).map(p => p.y);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const tx = W / 2 - cx;
    const ty = H / 2 - cy;
    g.attr('transform', `translate(${tx},${ty})`);

    // ── Swimlane backgrounds ──
    const laneG = g.append('g').attr('class', 'lanes');
    services.forEach((svc, i) => {
      const lx = PADDING + i * COL_W - COL_W / 2;
      const ly = PADDING - 40;
      const lh = PADDING + maxDepth * ROW_H + 60;

      laneG.append('rect')
        .attr('x', lx).attr('y', ly)
        .attr('width', COL_W).attr('height', lh - ly)
        .attr('rx', 12)
        .attr('fill', `${svcColor(svc)}08`)
        .attr('stroke', `${svcColor(svc)}18`)
        .attr('stroke-width', 1);

      laneG.append('text')
        .attr('x', lx + COL_W / 2)
        .attr('y', ly + 22)
        .attr('text-anchor', 'middle')
        .attr('font-size', '11')
        .attr('font-weight', '700')
        .attr('font-family', 'Inter, sans-serif')
        .attr('fill', svcColor(svc))
        .attr('letter-spacing', '1')
        .text(svcLabel(svc));
    });

    // ── Edges ──
    const edgeG = g.append('g').attr('class', 'edges');
    edges.forEach(e => {
      const src = positions[e.source];
      const tgt = positions[e.target];
      if (!src || !tgt) return;

      // Curved path
      const mx = (src.x + tgt.x) / 2;
      const my = (src.y + tgt.y) / 2 - 20;

      edgeG.append('path')
        .attr('class', `edge ${e.explicit ? 'explicit' : 'inferred'}`)
        .attr('d', `M${src.x},${src.y} Q${mx},${my} ${tgt.x},${tgt.y}`)
        .attr('fill', 'none')
        .attr('stroke', e.explicit ? '#00d4ff' : '#334155')
        .attr('stroke-width', e.explicit ? 2 : 1.5)
        .attr('stroke-dasharray', e.explicit ? 'none' : '4,3')
        .attr('marker-end', `url(#arrow-${e.explicit ? 'explicit' : 'normal'})`)
        .attr('opacity', 0.7)
        .attr('data-source', e.source)
        .attr('data-target', e.target);
    });

    // ── Nodes ──
    const nodeG = g.append('g').attr('class', 'nodes');
    const nodeEls = nodeG.selectAll('.node-group')
      .data(nodes, d => d.id)
      .join('g')
      .attr('class', 'node-group')
      .attr('transform', d => `translate(${positions[d.id].x},${positions[d.id].y})`)
      .attr('cursor', 'pointer')
      .on('click', (e, d) => selectNode(d, edges, positions))
      .on('mouseenter', (e, d) => showTooltip(e, d))
      .on('mouseleave', hideTooltip);

    // Outer glow ring
    nodeEls.append('circle')
      .attr('r', NODE_R + 6)
      .attr('fill', d => `${svcColor(d.service_id)}18`)
      .attr('stroke', d => `${svcColor(d.service_id)}40`)
      .attr('stroke-width', 1);

    // Main circle
    nodeEls.append('circle')
      .attr('class', 'node-circle')
      .attr('r', NODE_R)
      .attr('fill', d => {
        const col = svcColor(d.service_id);
        return `url(#grad-${d.id})`;
      })
      .attr('stroke', d => svcColor(d.service_id))
      .attr('stroke-width', 2);

    // Gradient for each node
    nodes.forEach(n => {
      const col = svcColor(n.service_id);
      const grad = defs.append('radialGradient')
        .attr('id', `grad-${n.id}`)
        .attr('cx', '35%').attr('cy', '35%');
      grad.append('stop').attr('offset', '0%').attr('stop-color', col).attr('stop-opacity', 0.5);
      grad.append('stop').attr('offset', '100%').attr('stop-color', col).attr('stop-opacity', 0.15);
    });

    // Event type label (abbreviated)
    nodeEls.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', '8.5')
      .attr('font-weight', '700')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', '#e2e8f0')
      .text(d => abbreviate(d.event_type));

    // Lamport clock badge
    nodeEls.append('rect')
      .attr('x', NODE_R - 10).attr('y', NODE_R - 10)
      .attr('width', 20).attr('height', 16).attr('rx', 8)
      .attr('fill', '#0d1526').attr('stroke', '#475569').attr('stroke-width', 1);

    nodeEls.append('text')
      .attr('x', NODE_R - 0).attr('y', NODE_R - 1)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
      .attr('font-size', '9').attr('font-weight', '700')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', '#94a3b8')
      .text(d => `L${d.lamport_ts}`);

    // Entry animation
    nodeEls.attr('opacity', 0)
      .transition().duration(400).delay((d, i) => i * 60)
      .attr('opacity', 1);

    // Build legend
    buildLegend(services);
  }

  function abbreviate(type) {
    if (!type) return '?';
    const words = type.split('_');
    if (words.length === 1) return type.slice(0, 6);
    return words.map(w => w[0]).join('').slice(0, 5);
  }

  // ── Tooltip ───────────────────────────────────────────────────────────────
  function showTooltip(event, d) {
    const vc = d.vector_clock || {};
    const vcStr = Object.entries(vc).map(([k, v]) => `${k.split('-')[0]}:${v}`).join(' ');
    tooltip
      .classed('visible', true)
      .style('left', (event.offsetX + 16) + 'px')
      .style('top',  (event.offsetY - 10) + 'px')
      .html(`
        <div class="tt-event-type">${d.event_type}</div>
        <div class="tt-row"><span class="tt-label">Service</span><span class="tt-val">${d.service_id}</span></div>
        <div class="tt-row"><span class="tt-label">Region</span><span class="tt-val">${d.region || '—'}</span></div>
        <div class="tt-row"><span class="tt-label">Lamport</span><span class="tt-val">${d.lamport_ts}</span></div>
        <div class="tt-row"><span class="tt-label">VC</span><span class="tt-val">{${vcStr}}</span></div>
        <div style="margin-top:6px;font-size:10px;color:var(--text-muted)">Click to select for analysis</div>
      `);
  }

  function hideTooltip() {
    tooltip?.classed('visible', false);
  }

  // ── Node selection ────────────────────────────────────────────────────────
  function selectNode(d, edges, positions) {
    window.State.selectedNode = d;

    // Highlight selected node + neighbours
    d3.selectAll('.node-circle').attr('stroke-width', 2).attr('filter', null);
    d3.select(event?.currentTarget || `.node-group`)
      .select('.node-circle')
      .attr('stroke-width', 3)
      .attr('filter', 'brightness(1.4)');

    // Highlight connected edges
    d3.selectAll('.edge')
      .attr('stroke', e => '#334155')
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.4);

    d3.selectAll('.edge')
      .filter(e => e.source === d.id || e.target === d.id)
      .attr('stroke', '#f59e0b')
      .attr('stroke-width', 2.5)
      .attr('opacity', 1)
      .raise();

    renderDetailPanel(d, edges);
  }

  function renderDetailPanel(d, edges) {
    const panel = document.getElementById('dag-detail-content');
    if (!panel) return;

    const vc = d.vector_clock || {};
    const maxVC = Math.max(...Object.values(vc), 1);
    const parents  = edges.filter(e => e.target === d.id).map(e => e.source);
    const children = edges.filter(e => e.source === d.id).map(e => e.target);

    panel.innerHTML = `
      <div class="detail-event-type">${d.event_type}</div>
      <div style="margin-top:4px">
        <span class="tag" style="border-color:${svcColor(d.service_id)};color:${svcColor(d.service_id)}">${d.service_id}</span>
        ${d.region ? `<span class="tag" style="margin-left:6px">${d.region}</span>` : ''}
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Clock Info</div>
        <div class="detail-kv">
          <div class="detail-row"><span class="detail-key">Lamport</span><span class="detail-val">${d.lamport_ts}</span></div>
          <div class="detail-row"><span class="detail-key">Phys. time</span><span class="detail-val">${new Date(d.timestamp_ms).toISOString().replace('T',' ').slice(0,19)}</span></div>
          <div class="detail-row"><span class="detail-key">Uncertainty</span><span class="detail-val">${d.clock_uncertainty_ms ?? 5} ms</span></div>
        </div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Vector Clock</div>
        <div class="vc-list">
          ${Object.entries(vc).map(([svc, cnt]) => `
            <div class="vc-row">
              <span class="vc-svc">${svc.replace('-svc','')}</span>
              <div class="vc-bar-wrap"><div class="vc-bar" style="width:${Math.round(cnt/maxVC*100)}%;background:${svcColor(svc)}"></div></div>
              <span class="vc-count">${cnt}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Causal Links</div>
        <div class="detail-kv">
          <div class="detail-row"><span class="detail-key">Parents</span><span class="detail-val">${parents.length ? parents.map(id => id.slice(0,8)+'…').join(', ') : 'None (root)'}</span></div>
          <div class="detail-row"><span class="detail-key">Children</span><span class="detail-val">${children.length ? children.length + ' event(s)' : 'None (leaf)'}</span></div>
        </div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">Event ID</div>
        <div class="mono" style="font-size:10px;color:var(--text-muted);word-break:break-all">${d.id}</div>
      </div>

      <div style="margin-top:20px;display:flex;flex-direction:column;gap:8px">
        <button class="btn btn-outline btn-sm" onclick="runWhatIfForNode('${d.id}')">🎯 Run What-If Analysis</button>
        <button class="btn btn-ghost btn-sm" onclick="runRootCause('${d.id}')">🔭 Trace Root Causes</button>
      </div>
    `;
  }

  // ── Legend ────────────────────────────────────────────────────────────────
  function buildLegend(services) {
    const legend = document.getElementById('dag-legend');
    if (!legend) return;
    legend.innerHTML = services.map(svc => `
      <div class="legend-item">
        <div class="legend-dot" style="background:${svcColor(svc)}"></div>
        <span>${svcLabel(svc)}</span>
      </div>
    `).join('') + `
      <div class="legend-item">
        <svg width="24" height="10"><line x1="0" y1="5" x2="24" y2="5" stroke="#00d4ff" stroke-width="2"/></svg>
        <span>Explicit</span>
      </div>
      <div class="legend-item">
        <svg width="24" height="10"><line x1="0" y1="5" x2="24" y2="5" stroke="#334155" stroke-width="1.5" stroke-dasharray="4,3"/></svg>
        <span>Inferred</span>
      </div>
    `;
  }

  // ── Highlight for what-if ─────────────────────────────────────────────────
  function highlightWhatIf(invalidatedIds, removedId) {
    d3.selectAll('.node-group').each(function(d) {
      const circle = d3.select(this).select('.node-circle');
      if (d.id === removedId) {
        circle.attr('fill', '#ef4444').attr('fill-opacity', 0.6);
      } else if (invalidatedIds.includes(d.id)) {
        circle.attr('fill', '#f97316').attr('fill-opacity', 0.4);
      } else {
        circle.attr('fill', `url(#grad-${d.id})`).attr('fill-opacity', 1);
      }
    });
  }

  function clearHighlight() {
    d3.selectAll('.node-group .node-circle').each(function(d) {
      d3.select(this).attr('fill', `url(#grad-${d.id})`).attr('fill-opacity', 1);
    });
  }

  return { render, highlightWhatIf, clearHighlight };
})();

// Helpers used by detail panel buttons
async function runWhatIfForNode(nodeId) {
  switchView('whatif');
  setTimeout(() => {
    const sel = document.getElementById('whatif-event-select');
    if (sel) sel.value = nodeId;
    runWhatIf();
  }, 200);
}

async function runRootCause(nodeId) {
  try {
    const data = await API.get(`/api/analysis/rootcause/${nodeId}`);
    const paths = data.trace_paths.map(p => p.join(' → ')).join('\n');
    toast(`Root causes: ${data.root_cause_count} | Critical path: ${data.critical_path.length} steps`, 'info', 5000);
  } catch (e) { toast(e.message, 'error'); }
}

window.DAGViz = DAGViz;
window.runWhatIfForNode = runWhatIfForNode;
window.runRootCause     = runRootCause;
