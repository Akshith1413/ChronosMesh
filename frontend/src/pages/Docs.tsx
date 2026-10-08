import React from 'react';
import { Icon } from '../components/Icon';
import { Tilt } from '../fx/Reveal';

const CONTRACTS = [
  { name: 'API_CONTRACT.md', desc: 'REST API endpoints, JWT auth, and error schemas', icon: 'server', color: '#4c6ef5' },
  { name: 'EVENT_SCHEMA.md', desc: 'JSON, Avro, Protobuf event models & Kafka topics', icon: 'kafka', color: '#8f4cf0' },
  { name: 'CAUSAL_DAG_SCHEMA.md', desc: 'NetworkX DiGraph & D3.js node/edge definitions', icon: 'dag', color: '#0fb98a' },
  { name: 'NEO4J_SCHEMA.md', desc: 'Cypher DDL, relationships, indexes, and queries', icon: 'db', color: '#2f9bff' },
  { name: 'STAGE1_TO_API_MAPPING.md', desc: 'Direct class-to-endpoint traceability matrix', icon: 'link', color: '#f59f00' },
  { name: 'FRONTEND_DATA_CONTRACT.md', desc: 'Component contracts, D3 layouts, and SSE specs', icon: 'layers', color: '#e64980' },
];

const OWNERS = [
  { who: 'Akshith', role: 'Core Engine', color: '#4c6ef5' },
  { who: 'Surya', role: 'Data Pipeline', color: '#0fb98a' },
  { who: 'Guru', role: 'API & Dashboard', color: '#6a4cff' },
];

export const DocsPage: React.FC = () => (
  <>
    <section className="panel docs-hero">
      <div className="docs-orbit" aria-hidden="true">
        <i className="ring r1" />
        <i className="ring r2" />
        <i className="core" />
        {OWNERS.map((o, i) => (
          <span key={o.who} className="sat" style={{ ['--c' as any]: o.color, ['--a' as any]: `${i * 120}deg` }}>
            <b>{o.who}</b>
          </span>
        ))}
      </div>
      <div className="eyebrow">Stage 2 · Interface contracts</div>
      <h2 className="docs-title">
        The verified boundary between <em className="serif gradient-text">three teams</em>.
      </h2>
      <p className="muted" style={{ maxWidth: '62ch', marginTop: 12 }}>
        Stage 2 interface and schema contracts establish the integration boundary between the Core Engine, the Data Pipeline, and the API / Dashboard.
      </p>
      <div className="row" style={{ marginTop: 18 }}>
        {OWNERS.map((o) => (
          <span key={o.who} className="svc-tag" style={{ ['--c' as any]: o.color }}>
            {o.who} · {o.role}
          </span>
        ))}
      </div>
    </section>

    <div className="grid-auto stagger" style={{ ['--min' as any]: '300px' }}>
      {CONTRACTS.map((d, i) => (
        <Tilt key={d.name} className="panel contract" style={{ ['--c' as any]: d.color, ['--i' as any]: i }}>
          <div className="contract-ico lift">
            <Icon name={d.icon} size={22} />
          </div>
          <div className="contract-name">{d.name}</div>
          <p className="muted small" style={{ marginTop: 6 }}>{d.desc}</p>
          <div className="contract-foot">
            <span className="chip chip-ok lower"><span className="dot" /> Verified</span>
            <Icon name="arrow" size={16} />
          </div>
        </Tilt>
      ))}
    </div>
  </>
);
