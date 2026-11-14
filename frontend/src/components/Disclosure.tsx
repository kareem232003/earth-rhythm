import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

/**
 * Collapsible "show more" section used for progressive disclosure (D-014).
 * Content is only folded away, never removed: the summary line always says what is inside.
 */
export const Disclosure: React.FC<{
  title: React.ReactNode;
  hint?: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  children: React.ReactNode;
}> = ({ title, hint, defaultOpen = false, className = '', children }) => {
  const [open, setOpen] = useState<boolean>(defaultOpen);
  return (
    <div className={`disclosure ${open ? 'disclosure-open' : ''} ${className}`}>
      <button type="button" className="disclosure-bar" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="disclosure-title">{title}</span>
        {hint && <span className="disclosure-hint">{hint}</span>}
        <span className="disclosure-action">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && <div className="disclosure-body">{children}</div>}
    </div>
  );
};
