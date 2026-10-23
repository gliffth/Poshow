"use client";

import { Loader2 } from 'lucide-react';
import { useGame } from '@/store/GameContext';

/** Shown to a logged-in player while the backend is still waking up / their roster is loading. */
export function ConnectingScreen() {
  const { serverReachable, serverChecked, actions } = useGame();
  return (
    <div className="w-full h-full flex items-center justify-center p-6 bg-retro-bg text-retro-green">
      <div className="w-full max-w-sm space-y-4 text-center">
        <Loader2 size={28} className="animate-spin mx-auto opacity-80" />
        <p className="font-pixel text-sm leading-relaxed">
          {serverReachable ? 'Loading your team…' : serverChecked ? 'Waking up the server…' : 'Connecting…'}
        </p>
        {!serverReachable && serverChecked && (
          <p className="text-xs opacity-60">
            Free hosting sleeps when idle. The first connection can take up to a minute — this retries by itself.
          </p>
        )}
        <div className="flex flex-col gap-2 pt-2">
          <button onClick={() => actions.logout()} className="text-[11px] uppercase tracking-widest opacity-50 hover:opacity-90 underline underline-offset-4">
            Log out
          </button>
          <button onClick={() => actions.playOffline()} className="text-[11px] uppercase tracking-widest opacity-50 hover:opacity-90 underline underline-offset-4">
            Play offline demo instead
          </button>
        </div>
      </div>
    </div>
  );
}
