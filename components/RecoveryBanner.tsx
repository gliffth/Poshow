"use client";

import { AlertCircle, Loader2, X } from 'lucide-react';
import { useGame } from '@/store/GameContext';

/** Shows an action whose answer never arrived, with a safe Retry (same request id), and one-line results. */
export function RecoveryBanner() {
  const { recovery } = useGame();
  const { pending, busy, notice } = recovery;
  if (!pending && !notice) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed left-2 right-2 sm:left-auto sm:right-4 sm:w-96 z-40 top-[calc(env(safe-area-inset-top,0px)+3.25rem)] border-2 border-retro-alert bg-retro-dark p-3 text-sm flex flex-col gap-2"
    >
      <div className="flex items-start gap-2">
        <AlertCircle size={16} className="shrink-0 mt-0.5 text-retro-alert" />
        <div className="min-w-0 flex-1">
          {pending && <p>Couldn&apos;t confirm that. Your {pending.label} may or may not have gone through.</p>}
          {notice && <p className={pending ? 'mt-1 opacity-80' : ''}>{notice}</p>}
        </div>
        <button type="button" onClick={pending ? recovery.dismiss : recovery.dismissNotice} aria-label="Dismiss" className="opacity-70 hover:opacity-100">
          <X size={16} />
        </button>
      </div>
      {pending && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={recovery.retry}
            disabled={busy}
            className="flex items-center gap-1 px-3 py-1 text-xs uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-50"
          >
            {busy && <Loader2 size={12} className="animate-spin" />} Retry
          </button>
          <button
            type="button"
            onClick={recovery.refresh}
            disabled={busy}
            className="px-3 py-1 text-xs uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      )}
    </div>
  );
}
