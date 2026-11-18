"use client";

import { useEffect } from 'react';
import { SceneImage } from '@/components/SceneImage';
import { SceneKind } from '@/lib/apiClient';

/** A short walking cutscene shown over the game. Tap to skip; it closes by itself. */
export function Cutscene({
  kind, region, title, line, onDone, ms = 3200,
}: { kind: SceneKind; region: string; title: string; line?: string; onDone: () => void; ms?: number }) {
  useEffect(() => {
    const t = setTimeout(onDone, ms);
    return () => clearTimeout(t);
  }, [onDone, ms]);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-3" onClick={onDone} role="dialog" aria-label={title}>
      <div className="w-full max-w-xl border-2 border-retro-green bg-retro-bg box-glow">
        <div className="aspect-video w-full overflow-hidden">
          <SceneImage kind={kind} region={region} alt={title} />
        </div>
        <div className="p-3 border-t-2 border-retro-green/60">
          <p className="font-pixel text-xs sm:text-sm leading-relaxed">{title}</p>
          {line && <p className="text-xs opacity-70 mt-1">{line}</p>}
          <p className="text-[10px] uppercase tracking-widest opacity-40 mt-2">Tap to skip</p>
        </div>
      </div>
    </div>
  );
}
