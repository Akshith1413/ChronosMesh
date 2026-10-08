import React from 'react';
import { useInView, useTilt } from './hooks';

interface RevealProps extends React.HTMLAttributes<HTMLElement> {
  as?: any;
  delay?: number;
  threshold?: number;
}

/** Fades, lifts and un-blurs its children when scrolled into view. */
export const Reveal: React.FC<RevealProps> = ({
  as: Tag = 'div',
  delay = 0,
  threshold = 0.18,
  className = '',
  style,
  children,
  ...rest
}) => {
  const [ref, seen] = useInView<HTMLElement>(threshold);
  return (
    <Tag
      ref={ref}
      className={`reveal ${seen ? 'in' : ''} ${className}`}
      style={{ ...style, ['--d' as any]: `${delay}ms` }}
      {...rest}
    >
      {children}
    </Tag>
  );
};

interface TiltProps extends React.HTMLAttributes<HTMLElement> {
  as?: any;
  max?: number;
  spot?: boolean;
  [attr: string]: any; // forwarded to the element (disabled, type, …)
}

/** A surface that leans toward the pointer, with glare and a spotlight edge. */
export const Tilt: React.FC<TiltProps> = ({
  as: Tag = 'div',
  max = 7,
  spot = true,
  className = '',
  children,
  ...rest
}) => {
  const ref = useTilt<HTMLElement>(max);
  return (
    <Tag ref={ref} className={`tilt ${spot ? 'spot' : ''} ${className}`} {...rest}>
      {children}
    </Tag>
  );
};
