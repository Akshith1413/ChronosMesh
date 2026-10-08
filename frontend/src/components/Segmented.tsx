import React, { useLayoutEffect, useRef, useState } from 'react';
import { Icon } from './Icon';

interface Option<T extends string> {
  value: T;
  label: string;
  icon?: string;
}

interface Props<T extends string> {
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
  ariaLabel?: string;
}

/** Pill tabs with a thumb that springs to the selected option (measured, so any label width works). */
export function Segmented<T extends string>({ options, value, onChange, className = '', ariaLabel }: Props<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [geo, setGeo] = useState({ x: 4, w: 0 });

  useLayoutEffect(() => {
    const measure = () => {
      const el = refs.current[value];
      if (el) setGeo({ x: el.offsetLeft, w: el.offsetWidth });
    };
    measure();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    const el = refs.current[value];
    if (el && ro) ro.observe(el.parentElement as Element);
    document.fonts?.ready.then(measure).catch(() => {});
    return () => ro?.disconnect();
  }, [value, options.length]);

  return (
    <div className={`seg ${className}`} role="tablist" aria-label={ariaLabel} style={{ ['--tx' as any]: `${geo.x}px`, ['--tw' as any]: `${geo.w}px` }}>
      <i className="thumb" />
      {options.map((o) => (
        <button
          key={o.value}
          ref={(el) => (refs.current[o.value] = el)}
          role="tab"
          aria-selected={o.value === value}
          className={o.value === value ? 'is-on' : ''}
          onClick={() => onChange(o.value)}
        >
          {o.icon && <Icon name={o.icon} size={15} />}
          {o.label}
        </button>
      ))}
    </div>
  );
}
