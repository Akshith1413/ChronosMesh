import React from 'react';
import { getServiceColor } from '../utils/colors';

interface Props {
  pattern: string;
  services?: string[];
  nodes?: number;
}

type P = { x: number; y: number };

/** A tiny animated drawing of a scenario's causal shape. */
export const PatternGlyph: React.FC<Props> = ({ pattern, services = [], nodes = 4 }) => {
  let pts: P[] = [];
  let edges: [number, number][] = [];

  if (pattern === 'chain') {
    const n = Math.min(6, Math.max(3, nodes));
    pts = Array.from({ length: n }, (_, i) => ({ x: 14 + (i * 132) / (n - 1), y: 29 }));
    edges = pts.slice(1).map((_, i) => [i, i + 1]);
  } else if (pattern === 'fork') {
    pts = [{ x: 18, y: 29 }, { x: 80, y: 12 }, { x: 80, y: 46 }];
    edges = [[0, 1], [0, 2]];
  } else if (pattern === 'diamond') {
    pts = [{ x: 16, y: 29 }, { x: 62, y: 11 }, { x: 62, y: 47 }, { x: 108, y: 29 }];
    edges = [[0, 1], [0, 2], [1, 3], [2, 3]];
  } else {
    pts = [{ x: 12, y: 29 }, { x: 44, y: 12 }, { x: 44, y: 46 }, { x: 80, y: 12 }, { x: 80, y: 46 }, { x: 116, y: 29 }, { x: 148, y: 29 }];
    edges = [[0, 1], [0, 2], [1, 3], [2, 4], [3, 5], [4, 5], [5, 6]];
  }

  const colorAt = (i: number) => getServiceColor(services[i % Math.max(1, services.length)]);

  return (
    <svg className="glyph" viewBox="0 0 160 58" aria-hidden="true">
      {edges.map(([a, b], i) => {
        const pa = pts[a], pb = pts[b];
        const mx = (pa.x + pb.x) / 2;
        return (
          <path
            key={i}
            className="glyph-edge"
            d={`M${pa.x} ${pa.y} C ${mx} ${pa.y}, ${mx} ${pb.y}, ${pb.x} ${pb.y}`}
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        );
      })}
      {pts.map((p, i) => (
        <g key={i} className="glyph-node" style={{ transform: `translate(${p.x}px, ${p.y}px)`, animationDelay: `${i * 0.12}s`, ['--c' as any]: colorAt(i) }}>
          <circle r="9" className="halo" />
          <circle r="5.6" className="dot" />
          <circle cx="-1.6" cy="-2" r="1.5" fill="#fff" opacity="0.8" />
        </g>
      ))}
    </svg>
  );
};
