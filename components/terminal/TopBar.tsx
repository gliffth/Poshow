"use client";

import { useState } from 'react';
import { Menu, Settings, UserCircle, Volume2, VolumeX, Wallet } from 'lucide-react';
import type { ViewName } from '@/components/terminal/IconDock';
import { useGame } from '@/store/GameContext';
import { avatarUrl } from '@/lib/apiClient';
import { sfx } from '@/lib/sound';

export function TopBar({ onNavigate }: { onNavigate?: (view: ViewName) => void }) {
  const { state, dispatch, serverReachable, auth, avatar } = useGame();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="border-b-2 border-retro-green bg-retro-dark px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-2 uppercase tracking-widest opacity-80 min-w-0 truncate">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            auth.status === 'offline' ? 'bg-retro-alert' : serverReachable ? 'bg-retro-green animate-pulse box-glow' : 'bg-retro-alert animate-pulse'
          }`}
          title={auth.status === 'offline' ? 'Offline demo' : serverReachable ? 'Connected' : 'Reconnecting…'}
        />
        {avatar && auth.status === 'in' && serverReachable && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl(avatar, 3)} alt="" width={24} height={30} className="shrink-0" style={{ imageRendering: 'pixelated', width: 24, height: 30 }} />
        )}
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
        {onNavigate && (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Account and settings"
              aria-expanded={menuOpen}
              className="hover:text-retro-green/70 transition-colors"
            >
              <Menu size={20} />
            </button>
            {menuOpen && (
              <>
                {/* click-away layer */}
                <button aria-label="Close menu" className="fixed inset-0 z-40 cursor-default" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-2 z-50 min-w-40 border-2 border-retro-green bg-retro-dark flex flex-col">
                  <button
                    onClick={() => { setMenuOpen(false); onNavigate('profile'); }}
                    className="flex items-center gap-2 px-3 py-2 text-left uppercase text-xs tracking-widest hover:bg-retro-green hover:text-retro-bg"
                  >
                    <UserCircle size={16} /> Profile
                  </button>
                  <button
                    onClick={() => { setMenuOpen(false); onNavigate('settings'); }}
                    className="flex items-center gap-2 px-3 py-2 text-left uppercase text-xs tracking-widest hover:bg-retro-green hover:text-retro-bg"
                  >
                    <Settings size={16} /> Settings
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
