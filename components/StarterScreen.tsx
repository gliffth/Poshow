"use client";

import { useState } from 'react';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import * as api from '@/lib/apiClient';
import { ApiError, avatarUrl } from '@/lib/apiClient';
import { REGIONS, RegionDef, StarterChoice, AVATAR_CHOICES, starterSprite, starterStillSprite } from '@/lib/starters';
import { sfx } from '@/lib/sound';

const TYPE_COLOR: Record<string, string> = { grass: '#7aa869', fire: '#d9824f', water: '#5f9fd1' };

function Sprite({ dex, size }: { dex: number; size: number }) {
  const [still, setStill] = useState(false);
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={still ? starterStillSprite(dex) : starterSprite(dex)}
      onError={() => setStill(true)}
      alt=""
      width={size}
      height={size}
      style={{ imageRendering: 'pixelated', width: size, height: size, objectFit: 'contain' }}
    />
  );
}

export function StarterScreen() {
  const { state, actions } = useGame();
  const [avatarId, setAvatarId] = useState<string | null>(null);
  const [region, setRegion] = useState<RegionDef | null>(null);
  const [picked, setPicked] = useState<StarterChoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function confirm() {
    if (!region || !picked || busy) return;
    setBusy(true);
    setError('');
    try {
      await api.chooseStarter(state.guestUserId, region.id, picked.species, avatarId ?? undefined);
      sfx.coin();
      await actions.refreshRoster();
    } catch (err) {
      sfx.error();
      setError(err instanceof ApiError ? err.message : 'Could not reach the server — try again in a moment.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full h-full overflow-y-auto bg-retro-bg text-retro-green">
      {/* the lab — user-supplied pixel art */}
      <div className="relative w-full h-40 sm:h-56 overflow-hidden border-b-2 border-retro-green/60">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/starter-lab.jpg"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          style={{ imageRendering: 'pixelated', objectPosition: '50% 60%' }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-retro-bg via-retro-bg/30 to-transparent" />
        <div className="absolute bottom-2 left-4 right-4">
          <p className="font-pixel text-sm sm:text-base leading-relaxed">
            {!avatarId ? `Welcome, ${state.trainerName}` : region ? `${region.name} — choose your partner` : 'Where does your journey begin?'}
          </p>
          <p className="text-[11px] uppercase tracking-widest opacity-70">
            {!avatarId ? 'First — who are you?' : region ? 'This choice is permanent' : 'Pick your home region'}
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-4 space-y-4">
        {!avatarId ? (
          <div className="grid grid-cols-3 gap-3">
            {AVATAR_CHOICES.map((a) => (
              <button
                key={a.id}
                onClick={() => { sfx.menuSelect(); setAvatarId(a.id); }}
                className="border-2 border-retro-green/40 bg-retro-dark p-2 flex flex-col items-center gap-1 hover:border-retro-green hover:box-glow transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={avatarUrl(a.id, 6)} alt={a.name} width={64} height={80} style={{ imageRendering: 'pixelated', width: 64, height: 80 }} />
                <span className="uppercase tracking-widest text-[11px]">{a.name}</span>
              </button>
            ))}
          </div>
        ) : !region ? (
          <div className="space-y-3">
          <button
            onClick={() => setAvatarId(null)}
            className="flex items-center gap-1 text-xs uppercase tracking-widest opacity-70 hover:opacity-100"
          >
            <ChevronLeft size={14} /> Change trainer
          </button>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {REGIONS.map((r) => (
              <button
                key={r.id}
                onClick={() => { sfx.menuSelect(); setRegion(r); setPicked(null); }}
                className="border-2 border-retro-green/40 bg-retro-dark p-3 text-left hover:border-retro-green hover:box-glow transition-colors"
              >
                <div className="flex gap-1 h-10 mb-2 items-end">
                  {r.starters.map((s) => <Sprite key={s.species} dex={s.pokedexId} size={32} />)}
                </div>
                <p className="uppercase tracking-widest text-sm">{r.name}</p>
                <p className="text-[10px] opacity-60 leading-tight">Gen {r.gen} · {r.blurb}</p>
              </button>
            ))}
          </div>
          </div>
        ) : (
          <>
            <button
              onClick={() => { setRegion(null); setPicked(null); setError(''); }}
              className="flex items-center gap-1 text-xs uppercase tracking-widest opacity-70 hover:opacity-100"
            >
              <ChevronLeft size={14} /> Change region
            </button>

            <div className="grid grid-cols-3 gap-3">
              {region.starters.map((s) => {
                const active = picked?.species === s.species;
                return (
                  <button
                    key={s.species}
                    onClick={() => { sfx.menuMove(); setPicked(s); }}
                    className={`border-2 p-2 flex flex-col items-center gap-1 bg-retro-dark transition-colors ${
                      active ? 'border-retro-green box-glow' : 'border-retro-green/30 hover:border-retro-green/70'
                    }`}
                  >
                    <div className="h-20 flex items-end justify-center"><Sprite dex={s.pokedexId} size={72} /></div>
                    <p className="uppercase tracking-widest text-[11px] truncate max-w-full">{s.species}</p>
                    <span className="text-[10px] uppercase" style={{ color: TYPE_COLOR[s.type] }}>{s.type}</span>
                  </button>
                );
              })}
            </div>

            {error && <p className="text-xs text-retro-alert">{error}</p>}
            <button
              onClick={confirm}
              disabled={!picked || busy}
              className="w-full border-2 border-retro-green py-3 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg disabled:opacity-30 disabled:pointer-events-none flex items-center justify-center gap-2"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              {picked ? `Choose ${picked.species}` : 'Pick a starter'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
