import React from 'react';

/**
 * Lightweight fade & slide entry transition wrapper.
 * Honors prefers-reduced-motion in CSS.
 */
export default function PageTransition({ children, className = '' }) {
  return (
    <div className={`page-transition ${className}`}>
      {children}
    </div>
  );
}
