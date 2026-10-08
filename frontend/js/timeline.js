/**
 * ChronosMesh — timeline.js
 * Side-by-side arrival-order vs causal-order replay with scrub slider.
 * Author: Guru Sai Prasad Reddy
 */

'use strict';

const Timeline = (() => {
  let step = 0;
  let maxStep = 0;
  let playInterval = null;

  function init() {
    const arrivalData = State.events || [];
    const causalData  = State.dagData?.topological_order || [];

    if (!arrivalData.length) {
      document.getElementById('timeline-empty').style.display = 'flex';
      document.getElementById('timeline-content').style.display = 'none';
      return;
    }

    document.getElementById('timeline-empty').style.display = 'none';
    document.getElementById('timeline-content').style.display = 'flex';

    // Map causal order IDs to event objects
    const eidMap = {};
    arrivalData.forEach(e => eidMap[e.event_id] = e);
    const causalEvents = causalData
      .map(id => eidMap[id])
      .filter(Boolean);

    maxStep = Math.max(arrivalData.length, causalEvents.length);
    step = maxStep; // show all by default

    // Build arrival track
    renderTrack('arrival-track', arrivalData, 'arrival');
    renderTrack('causal-track', causalEvents, 'causal');

    const slider = document.getElementById('timeline-slider');
    slider.max = maxStep;
    slider.value = maxStep;
    updateSliderStyle(slider, maxStep, maxStep);
    updateStep(maxStep, arrivalData, causalEvents);

    slider.oninput = () => {
      const s = parseInt(slider.value);
      updateStep(s, arrivalData, causalEvents);
      updateSliderStyle(slider, s, maxStep);
    };

    document.getElementById('step-count').textContent = `Step ${maxStep} / ${maxStep}`;
  }

  function renderTrack(containerId, events, type) {
    const track = document.getElementById(containerId);
    if (!track) return;
    track.innerHTML = events.map((e, i) => `
      <div class="track-event ${type}-event" data-step="${i}" id="${type}-evt-${i}"
           style="border-left: 3px solid ${svcColor(e.service_id)}">
        <div class="te-num">${type === 'arrival' ? '📨' : '🔗'} #${i + 1}</div>
        <div class="te-type" style="color:${svcColor(e.service_id)}">${e.event_type}</div>
        <div class="te-svc">${svcLabel(e.service_id)}</div>
      </div>
    `).join('');
  }

  function updateStep(s, arrivalEvents, causalEvents) {
    step = s;
    document.getElementById('step-count').textContent = `Step ${s} / ${maxStep}`;

    // Show/hide arrival events
    arrivalEvents.forEach((_, i) => {
      const el = document.getElementById(`arrival-evt-${i}`);
      if (el) el.classList.toggle('step-hidden', i >= s);
    });

    // Show/hide causal events
    causalEvents.forEach((_, i) => {
      const el = document.getElementById(`causal-evt-${i}`);
      if (el) {
        el.classList.toggle('step-hidden', i >= s);
        if (i < s) el.classList.add('causal-active');
        else el.classList.remove('causal-active');
      }
    });
  }

  function updateSliderStyle(slider, val, max) {
    const pct = max > 0 ? (val / max * 100) : 0;
    slider.style.setProperty('--pct', `${pct}%`);
  }

  function play() {
    if (playInterval) { pause(); return; }
    if (step >= maxStep) { step = 0; }
    const btn = document.getElementById('play-btn');
    if (btn) btn.textContent = '⏸';

    const arrivalData = State.events || [];
    const causalData  = State.dagData?.topological_order || [];
    const eidMap = {};
    arrivalData.forEach(e => eidMap[e.event_id] = e);
    const causalEvents = causalData.map(id => eidMap[id]).filter(Boolean);

    playInterval = setInterval(() => {
      step++;
      const slider = document.getElementById('timeline-slider');
      if (slider) { slider.value = step; updateSliderStyle(slider, step, maxStep); }
      updateStep(step, arrivalData, causalEvents);
      if (step >= maxStep) pause();
    }, 700);
  }

  function pause() {
    clearInterval(playInterval);
    playInterval = null;
    const btn = document.getElementById('play-btn');
    if (btn) btn.textContent = '▶';
  }

  function reset() {
    pause();
    step = 0;
    const slider = document.getElementById('timeline-slider');
    if (slider) { slider.value = 0; updateSliderStyle(slider, 0, maxStep); }
    const arrivalData = State.events || [];
    const causalData  = State.dagData?.topological_order || [];
    const eidMap = {};
    arrivalData.forEach(e => eidMap[e.event_id] = e);
    const causalEvents = causalData.map(id => eidMap[id]).filter(Boolean);
    updateStep(0, arrivalData, causalEvents);
  }

  return { init, play, pause, reset };
})();

window.Timeline = Timeline;
