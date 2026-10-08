import React, { useState } from 'react';
import { Icon } from '../Icon';
import { Tilt } from '../../fx/Reveal';

const STAGES = [
  { icon: 'server', label: 'Mock Microservices', tech: 'Emit events', color: '#4c6ef5', detail: 'Order, payment, inventory, shipping and notification services emit events stamped with Lamport, vector and hybrid clocks — across simulated regions with drifting physical time.' },
  { icon: 'kafka', label: 'Kafka / MSK', tech: 'Disordered ingestion', color: '#8f4cf0', detail: 'Events arrive over partitioned topics with jitter, reordering and loss. Arrival order is deliberately not trusted.' },
  { icon: 'layers', label: 'Flink Streams', tech: 'Windowing & state', color: '#e64980', detail: 'Windowed, stateful stream processing buffers late events until their causal parents have arrived.' },
  { icon: 'clock', label: 'Clock Engines', tech: 'Lamport · Vector · HLC', color: '#f59f00', detail: 'Three clock strategies run side by side so their ordering accuracy can be benchmarked under packet loss and drift.' },
  { icon: 'dag', label: 'Causal Engine', tech: 'DAG & reduction', color: '#0fb98a', detail: 'Happens-before relations become a DAG; transitive reduction strips redundant edges; concurrency is detected, not guessed.' },
  { icon: 'db', label: 'Neo4j / Store', tech: 'Graph persistence', color: '#2f9bff', detail: 'The reconstructed graph is persisted as nodes and causal edges, ready for ancestry and blast-radius queries.' },
  { icon: 'spark', label: 'API & Dashboard', tech: 'FastAPI + React', color: '#6a4cff', detail: 'A JWT-secured FastAPI layer streams live events over SSE to this dashboard — the interface you are looking at.' },
];

/** The ingest-to-insight flow, with a pulse that travels stage to stage and tilt cards that expand on hover. */
export const Pipeline: React.FC = () => {
  const [active, setActive] = useState(4);
  const stage = STAGES[active];

  return (
    <div className="pipe">
      <div className="pipe-track" role="list">
        <div className="pipe-line">
          <i className="pipe-pulse" />
        </div>
        {STAGES.map((s, i) => (
          <Tilt
            as="button"
            max={9}
            key={s.label}
            role="listitem"
            className={`pipe-stage ${i === active ? 'on' : ''}`}
            style={{ ['--c' as any]: s.color, ['--i' as any]: i }}
            onMouseEnter={() => setActive(i)}
            onFocus={() => setActive(i)}
            onClick={() => setActive(i)}
          >
            <span className="pipe-idx num">{String(i + 1).padStart(2, '0')}</span>
            <span className="pipe-ico lift">
              <Icon name={s.icon} size={24} />
            </span>
            <b>{s.label}</b>
            <small>{s.tech}</small>
            <span className="pipe-wave" style={{ animationDelay: `${i * 0.55}s` }} />
          </Tilt>
        ))}
      </div>

      <div className="pipe-detail" key={active} style={{ ['--c' as any]: stage.color }}>
        <span className="svc-tag" style={{ ['--c' as any]: stage.color }}>
          Stage {active + 1}
        </span>
        <h4>{stage.label}</h4>
        <p>{stage.detail}</p>
      </div>
    </div>
  );
};
