/**
 * ChronosMesh — landing.js
 * Starfield animation, hero particle effects, scroll reveals.
 * Author: Guru Sai Prasad Reddy
 */

'use strict';

const Landing = (() => {
  // ── Starfield ──────────────────────────────────────────────────────────────
  let stars = [];
  let animFrame;

  function initStarfield() {
    const canvas = document.getElementById('star-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    function resize() {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const N = 180;
    for (let i = 0; i < N; i++) {
      stars.push({
        x:   Math.random() * canvas.width,
        y:   Math.random() * canvas.height,
        r:   Math.random() * 1.5 + 0.3,
        vx:  (Math.random() - 0.5) * 0.15,
        vy:  Math.random() * 0.08 + 0.02,
        a:   Math.random(),
        va:  (Math.random() - 0.5) * 0.005,
      });
    }

    // Floating nodes (simulates distributed events)
    const nodes = Array.from({ length: 8 }, (_, i) => ({
      x:  Math.random() * canvas.width,
      y:  Math.random() * canvas.height,
      r:  Math.random() * 4 + 2,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      color: ['#00d4ff','#8b5cf6','#10b981','#f59e0b'][i % 4],
    }));

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Stars
      stars.forEach(s => {
        s.x  += s.vx; s.y += s.vy; s.a += s.va;
        if (s.a < 0) s.a = 0, s.va *= -1;
        if (s.a > 1) s.a = 1, s.va *= -1;
        if (s.x < 0)              s.x = canvas.width;
        if (s.x > canvas.width)   s.x = 0;
        if (s.y > canvas.height)  s.y = 0;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${s.a * 0.7})`;
        ctx.fill();
      });

      // Floating nodes + connecting lines
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 50 || n.x > canvas.width  - 50) n.vx *= -1;
        if (n.y < 50 || n.y > canvas.height - 50) n.vy *= -1;

        // Lines to nearby nodes
        nodes.forEach(m => {
          if (m === n) return;
          const d = Math.hypot(n.x - m.x, n.y - m.y);
          if (d < 200) {
            ctx.beginPath();
            ctx.moveTo(n.x, n.y); ctx.lineTo(m.x, m.y);
            ctx.strokeStyle = `rgba(0,212,255,${0.15 * (1 - d / 200)})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        });

        // Node glow
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r * 3);
        grad.addColorStop(0, n.color + 'aa');
        grad.addColorStop(1, n.color + '00');
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r * 3, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // Core dot
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();
      });

      animFrame = requestAnimationFrame(draw);
    }
    draw();
  }

  // ── Scroll-reveal ──────────────────────────────────────────────────────────
  function initScrollReveal() {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.style.opacity = '1';
          e.target.style.transform = 'translateY(0)';
          observer.unobserve(e.target);
        }
      }),
      { threshold: 0.15 }
    );

    document.querySelectorAll('.feature-card, .arch-layer, .cta-section').forEach(el => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(24px)';
      el.style.transition = 'opacity .5s ease, transform .5s ease';
      observer.observe(el);
    });
  }

  // ── Hero typing effect ─────────────────────────────────────────────────────
  function initTypingEffect() {
    const target = document.getElementById('hero-subtext');
    if (!target) return;
    const texts = [
      'Reconstructs causal truth from disordered event streams.',
      'Detects clock anomalies across distributed microservices.',
      'Traces root causes backward through the causal DAG.',
      'Simulates blast radius with What-If event removal.',
    ];
    let ti = 0, ci = 0, deleting = false;
    function tick() {
      const text = texts[ti];
      if (!deleting) {
        target.textContent = text.slice(0, ++ci);
        if (ci === text.length) { deleting = true; setTimeout(tick, 2200); return; }
      } else {
        target.textContent = text.slice(0, --ci);
        if (ci === 0) { deleting = false; ti = (ti + 1) % texts.length; }
      }
      setTimeout(tick, deleting ? 28 : 52);
    }
    tick();
  }

  // ── Public ─────────────────────────────────────────────────────────────────
  function init() {
    if (animFrame) cancelAnimationFrame(animFrame);
    stars = [];
    initStarfield();
    initScrollReveal();
    initTypingEffect();
  }

  function destroy() {
    if (animFrame) cancelAnimationFrame(animFrame);
  }

  return { init, destroy };
})();

window.Landing = Landing;
