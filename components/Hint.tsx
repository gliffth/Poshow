"use client";

import { GLOSSARY, type GlossaryId } from '@/lib/glossary';
import { HelpPopup } from '@/components/HelpPopup';

/** A "?" beside an unfamiliar term, with its short definition. */
export function Hint({ term, className }: { term: GlossaryId; className?: string }) {
  const entry = GLOSSARY[term];
  return (
    <HelpPopup id={`hint-${term}`} label={`What is ${entry.label}?`} className={className}>
      <p className="uppercase text-xs tracking-widest mb-1 opacity-70">{entry.label}</p>
      <p>{entry.text}</p>
    </HelpPopup>
  );
}
