import React from 'react';

/** Fixed, drifting pastel backdrop with a cursor-following glow. Purely decorative. */
export const Aurora: React.FC = React.memo(() => (
  <div className="aurora" aria-hidden="true">
    <i className="blob b1" />
    <i className="blob b2" />
    <i className="blob b3" />
    <i className="blob b4" />
    <div className="ruler" />
    <div className="spot" />
    <div className="grain" />
  </div>
));
