"use client";

import { useEffect, useState } from 'react';
import { Loader2, Wifi, WifiOff } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import { describeConnection, type ConnectionState } from '@/lib/connection';

const LOOK: Record<ConnectionState, string> = {
  ok: 'opacity-40 hover:opacity-80',
  slow: 'text-amber-500 animate-pulse',
  waking: 'text-sky-400',
  unreachable: 'text-retro-alert',
};

/** A small connection icon. Quiet when all is well; the popup explains the state in plain words. */
export function ConnectionIndicator() {
  const { connection, auth } = useGame();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const { snapshot } = connection;
  const text = describeConnection(snapshot);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  if (auth.status === 'offline') {
    return <WifiOff size={16} className="shrink-0 text-retro-alert" aria-label="Offline demo" role="img" />;
  }

  async function retry() {
    setBusy(true);
    try { await connection.retry(); } finally { setBusy(false); }
  }

  const Icon = snapshot.state === 'unreachable' ? WifiOff : Wifi;

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Connection: ${text.title}`}
        aria-expanded={open}
        className={`flex items-center justify-center w-6 h-6 transition-opacity ${LOOK[snapshot.state]}`}
      >
        <Icon size={16} />
      </button>
      {open && (
        <>
          <button aria-label="Close connection details" className="fixed inset-0 z-40 cursor-default" onClick={() => setOpen(false)} />
          <div
            role="dialog"
            aria-label="Connection"
            className="absolute left-0 top-full mt-2 z-50 w-72 max-w-[calc(100vw-1.5rem)] border-2 border-retro-green bg-retro-dark p-3 text-sm normal-case tracking-normal leading-snug flex flex-col gap-2"
          >
            <p className="uppercase text-xs tracking-widest opacity-70">{text.title}</p>
            <p>{text.message}</p>
            {snapshot.lastLatencyMs !== null && (
              <details className="text-xs opacity-70">
                <summary className="cursor-pointer">Details</summary>
                <p className="mt-1">Last reply took {Math.round(snapshot.lastLatencyMs)} ms. Failed requests in a row: {snapshot.failures}.</p>
              </details>
            )}
            {snapshot.state === 'unreachable' && (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={retry}
                  disabled={busy}
                  className="flex items-center gap-1 px-3 py-1 text-xs uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-50"
                >
                  {busy && <Loader2 size={12} className="animate-spin" />} Retry
                </button>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="px-3 py-1 text-xs uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg"
                >
                  Refresh
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
