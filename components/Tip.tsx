"use client";

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { claimTipVisit, releaseTipVisit, useSeen } from '@/lib/tips';
import { HelpPopup } from '@/components/HelpPopup';

/** A first-visit tip: a small icon that pulses until it is opened once. Never a modal, one pulse per screen visit. */
export function Tip({ id, title, children, className }: { id: string; title: string; children: ReactNode; className?: string }) {
  const [seen, markSeen] = useSeen(id);
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    if (seen) return;
    setPulse(claimTipVisit(id));
    return () => releaseTipVisit(id);
  }, [id, seen]);

  return (
    <HelpPopup id={`tip-${id}`} label={title} pulse={pulse && !seen} onOpen={markSeen} className={className}>
      <p className="uppercase text-xs tracking-widest mb-1 opacity-70">{title}</p>
      <div className="space-y-1">{children}</div>
    </HelpPopup>
  );
}
