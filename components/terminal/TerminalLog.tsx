"use client";

import { useEffect, useRef, useState } from 'react';
import { LogEntry } from '@/lib/types';

interface TerminalLogProps {
  log: LogEntry[];
  heightClass?: string;
}

export function TerminalLog({ log, heightClass = 'h-28' }: TerminalLogProps) {
  const [typedIndex, setTypedIndex] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const firstIdRef = useRef<string | undefined>(undefined);

  // Reset the typewriter when a brand new log sequence starts (e.g. new battle)
  useEffect(() => {
    if (log[0]?.id !== firstIdRef.current) {
      firstIdRef.current = log[0]?.id;
      setTypedIndex(0);
      setCharCount(0);
    }
  }, [log]);

  // Progressive character reveal
  useEffect(() => {
    if (typedIndex >= log.length) return undefined;
    const currentText = log[typedIndex]?.text ?? '';
    if (charCount >= currentText.length) {
      const t = setTimeout(() => {
        setTypedIndex((i) => i + 1);
        setCharCount(0);
      }, 260);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setCharCount((c) => c + 1), 14);
    return () => clearTimeout(t);
  }, [log, typedIndex, charCount]);

  useEffect(() => {
    containerRef.current?.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' });
  }, [typedIndex, charCount]);

  return (
    <div
      ref={containerRef}
      className={`${heightClass} overflow-y-auto custom-scrollbar border-2 border-retro-green bg-retro-dark bezel-inverted px-3 py-2 text-base space-y-1`}
    >
      {log.map((entry, i) => {
        if (i < typedIndex) {
          return <p key={entry.id} className="opacity-80">&gt; {entry.text}</p>;
        }
        if (i === typedIndex) {
          return (
            <p key={entry.id}>
              &gt; {entry.text.slice(0, charCount)}
              <span className="animate-pulse">▊</span>
            </p>
          );
        }
        return null;
      })}
    </div>
  );
}
