"use client";

import { useGame } from '@/store/GameContext';
import { Volume2, VolumeX, Trash2, Check } from 'lucide-react';
import { sfx } from '@/lib/sound';
import { clearSave } from '@/lib/storage';
import { useState } from 'react';
import { ThemeName } from '@/lib/types';

const THEME_OPTIONS: { id: ThemeName; label: string; bg: string; ink: string; blurb: string }[] = [
  { id: 'weathered', label: 'Weathered', bg: '#15181a', ink: '#c9cec9', blurb: 'Worn hardware device — default' },
  { id: 'cream', label: 'Cream', bg: '#f3e9d2', ink: '#33361f', blurb: 'Warm Game Boy cartridge' },
  { id: 'paper', label: 'Paper', bg: '#ded1b0', ink: '#4a3c28', blurb: 'Aged, faded parchment' },
];

export function SettingsScreen() {
  const { state, dispatch } = useGame();
  const [confirmReset, setConfirmReset] = useState(false);

  function handleReset() {
    if (!confirmReset) {
      setConfirmReset(true);
      sfx.error();
      return;
    }
    clearSave();
    window.location.reload();
  }

  function setTheme(theme: ThemeName) {
    if (theme === state.settings.theme) return;
    sfx.menuMove();
    dispatch({ type: 'SET_THEME', theme });
  }

  return (
    <div className="w-full max-w-2xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">
      <div className="mb-8 border-b-2 border-retro-green pb-4">
        <h1 className="font-pixel text-lg sm:text-xl leading-relaxed mb-2">Settings</h1>
        <p className="text-retro-green/70">GAME PREFERENCES</p>
      </div>

      <div className="space-y-6">
        {/* Theme picker */}
        <div className="border-2 border-retro-green p-5 box-glow bg-retro-dark">
          <p className="uppercase tracking-widest mb-1">Display Theme</p>
          <p className="text-xs opacity-60 mb-4">Swap the whole look — everything updates instantly, nothing to restart</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {THEME_OPTIONS.map((opt) => {
              const active = state.settings.theme === opt.id;
              return (
                <button
                  key={opt.id}
                  onClick={() => setTheme(opt.id)}
                  className={`relative border-2 p-3 text-left transition-colors ${active ? 'border-retro-green box-glow' : 'border-retro-green/30 hover:border-retro-green/60'}`}
                >
                  {active && (
                    <span className="absolute top-2 right-2 text-retro-green">
                      <Check size={14} />
                    </span>
                  )}
                  <div
                    className="w-full h-10 border mb-2 flex items-center justify-center"
                    style={{ backgroundColor: opt.bg, borderColor: opt.ink }}
                  >
                    <span className="text-xs uppercase tracking-widest" style={{ color: opt.ink }}>Aa</span>
                  </div>
                  <p className="uppercase tracking-widest text-sm">{opt.label}</p>
                  <p className="text-[10px] opacity-60 leading-tight mt-0.5">{opt.blurb}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Sound toggle */}
        <div className="border-2 border-retro-green p-5 flex items-center justify-between box-glow bg-retro-dark">
          <div className="flex items-center gap-3">
            {state.settings.soundOn ? <Volume2 size={22} /> : <VolumeX size={22} />}
            <div>
              <p className="uppercase tracking-widest">Sound</p>
              <p className="text-xs opacity-60">Interface beeps and battle feedback tones</p>
            </div>
          </div>
          <button
            onClick={() => {
              dispatch({ type: 'TOGGLE_SOUND' });
              setTimeout(() => sfx.menuMove(), 0);
            }}
            className={`px-4 py-2 border-2 uppercase tracking-widest text-sm transition-colors ${
              state.settings.soundOn ? 'border-retro-green bg-retro-green text-retro-bg' : 'border-retro-green/40 text-retro-green/60'
            }`}
          >
            {state.settings.soundOn ? 'On' : 'Off'}
          </button>
        </div>

        {/* Reset save */}
        <div className="border-2 border-retro-alert p-5 box-glow-alert bg-retro-dark">
          <div className="flex items-center gap-3 mb-3">
            <Trash2 size={22} className="text-retro-alert" />
            <div>
              <p className="uppercase tracking-widest text-retro-alert">Reset Save Data</p>
              <p className="text-xs opacity-60">Wipes party, currency, and pokedex progress. Cannot be undone.</p>
            </div>
          </div>
          <button
            onClick={handleReset}
            className={`px-4 py-2 border-2 uppercase tracking-widest text-sm transition-colors ${
              confirmReset ? 'border-retro-alert bg-retro-alert text-retro-bg' : 'border-retro-alert/50 text-retro-alert hover:bg-retro-alert/10'
            }`}
          >
            {confirmReset ? 'Confirm Reset' : 'Reset'}
          </button>
        </div>
      </div>
    </div>
  );
}
