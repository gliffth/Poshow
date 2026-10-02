"use client";

import { useEffect, useState } from 'react';

interface BootScreenProps {
  onComplete: () => void;
}

const BOOT_LINES = [
  'POSHOW TERMINAL v1.0',
  'checking hardware...',
  'loading species database...',
  'calibrating scanner...',
  'establishing uplink...',
  'ready.',
];

export function BootScreen({ onComplete }: BootScreenProps) {
  const [lines, setLines] = useState<string[]>([]);

  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setLines(BOOT_LINES.slice(0, i));
      if (i >= BOOT_LINES.length) {
        clearInterval(interval);
        setTimeout(onComplete, 500);
      }
    }, 220);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="w-full h-full flex items-center justify-center bg-retro-bg text-retro-green p-6">
      <div className="w-full max-w-sm space-y-1 font-mono text-sm">
        {lines.map((line, i) => (
          <p key={i} className="boot-flash-line">&gt; {line}</p>
        ))}
      </div>
    </div>
  );
}
