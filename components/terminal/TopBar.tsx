"use client";

import { Volume2, VolumeX, Wallet } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import { sfx } from '@/lib/sound';

export function TopBar() {
  const { state, dispatch } = useGame();

  return (
    <div className="border-b-2 border-retro-green bg-retro-dark px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-2 uppercase tracking-widest opacity-80 min-w-0 truncate">
        <span className="w-2 h-2 rounded-full bg-retro-green animate-pulse box-glow shrink-0" />
        <span className="truncate">{state.trainerName}</span>
      </div>
      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        <div className="flex items-center gap-1" title="Currency">
          <Wallet size={16} />
          <span>{state.currency}</span>
        </div>
        <button
          onClick={() => {
            dispatch({ type: 'TOGGLE_SOUND' });
            // fire after the toggle so muting doesn't play a sound and unmuting confirms audibly
            setTimeout(() => sfx.menuMove(), 0);
          }}
          aria-label={state.settings.soundOn ? 'Mute sound' : 'Unmute sound'}
          className="hover:text-retro-green/70 transition-colors"
        >
          {state.settings.soundOn ? <Volume2 size={18} /> : <VolumeX size={18} />}
        </button>
      </div>
    </div>
  );
}
