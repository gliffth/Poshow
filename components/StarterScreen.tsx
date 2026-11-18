"use client";

import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import * as api from '@/lib/apiClient';
import { ApiError, avatarUrl } from '@/lib/apiClient';
import { REGIONS, RegionDef, StarterChoice, AVATAR_CHOICES, starterSprite, starterStillSprite } from '@/lib/starters';
import { SceneImage } from '@/components/SceneImage';
import { usePrefs } from '@/lib/prefs';
import { sfx } from '@/lib/sound';

const TYPE_COLOR: Record<string, string> = { grass: '#7aa869', fire: '#d9824f', water: '#5f9fd1' };
const PROFESSORS: Record<string, string> = {
  kanto: 'Oak', johto: 'Elm', hoenn: 'Birch', sinnoh: 'Rowan', unova: 'Juniper',
  kalos: 'Sycamore', alola: 'Kukui', galar: 'Magnolia', paldea: 'Sada',
};

function Sprite({ dex, size, bob = false }: { dex: number; size: number; bob?: boolean }) {
  const [still, setStill] = useState(false);
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={still ? starterStillSprite(dex) : starterSprite(dex)}
      onError={() => setStill(true)}
      alt=""
      width={size}
      height={size}
      className={bob ? 'animate-bounce' : ''}
      style={{ imageRendering: 'pixelated', width: size, height: size, objectFit: 'contain', animationDuration: '1.6s' }}
    />
  );
}

type Step = 'avatar' | 'region' | 'arrive' | 'starter';

export function StarterScreen() {
  const { state, actions } = useGame();
  const [prefs] = usePrefs();
  const [step, setStep] = useState<Step>('avatar');
  const [avatarId, setAvatarId] = useState<string | null>(null);
  const [slide, setSlide] = useState(0);
  const [region, setRegion] = useState<RegionDef | null>(null);
  const [picked, setPicked] = useState<StarterChoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // the region slideshow drifts on by itself (unless the player turned cutscenes off)
  useEffect(() => {
    if (step !== 'region' || !prefs.cutscenes) return;
    const t = setInterval(() => setSlide((s) => (s + 1) % REGIONS.length), 4200);
    return () => clearInterval(t);
  }, [step, prefs.cutscenes]);

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

  const current = REGIONS[slide];
  const prof = region ? PROFESSORS[region.id] ?? 'the Professor' : '';

  return (
    <div className="w-full h-full overflow-y-auto bg-retro-bg text-retro-green">
      {/* scene banner: the lab for the first steps, the chosen region afterwards */}
      <div className="relative w-full h-40 sm:h-56 overflow-hidden border-b border-retro-green/60">
        {step === 'avatar' ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src="/starter-lab.jpg" alt="" className="absolute inset-0 w-full h-full object-cover"
            style={{ imageRendering: 'pixelated', objectPosition: '50% 60%' }} />
        ) : step === 'region' ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img key={current.id} src={api.regionSlideUrl(current.id)} alt={current.name}
            className="absolute inset-0 w-full h-full object-cover" style={{ imageRendering: 'pixelated' }} />
        ) : region ? (
          <SceneImage kind="region" region={region.id} className="absolute inset-0" />
        ) : null}
        <div className="absolute inset-0 bg-gradient-to-t from-retro-bg via-retro-bg/20 to-transparent" />
        <div className="absolute bottom-2 left-4 right-4">
          <p className="font-pixel text-sm sm:text-base leading-relaxed">
            {step === 'avatar' && `Welcome, ${state.trainerName}`}
            {step === 'region' && `${current.name} · Gen ${current.gen}`}
            {step === 'arrive' && region && `Welcome to ${region.name}`}
            {step === 'starter' && region && `${region.name} — choose your partner`}
          </p>
          <p className="text-[11px] uppercase tracking-widest opacity-70">
            {step === 'avatar' && 'First — who are you?'}
            {step === 'region' && current.blurb}
            {step === 'arrive' && `Professor ${prof} is waiting`}
            {step === 'starter' && 'This choice is permanent'}
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-4 space-y-4">
        {step === 'avatar' && (
          <div className="grid grid-cols-3 gap-3">
            {AVATAR_CHOICES.map((a) => (
              <button
                key={a.id}
                onClick={() => { sfx.menuSelect(); setAvatarId(a.id); setStep('region'); }}
                className="border border-retro-green/40 bg-retro-dark p-2 flex flex-col items-center gap-1 hover:border-retro-green hover:box-glow transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={avatarUrl(a.id, 6)} alt={a.name} width={64} height={80} style={{ imageRendering: 'pixelated', width: 64, height: 80 }} />
                <span className="uppercase tracking-widest text-[11px]">{a.name}</span>
              </button>
            ))}
          </div>
        )}

        {step === 'region' && (
          <div className="space-y-4">
            <button onClick={() => setStep('avatar')} className="flex items-center gap-1 text-xs uppercase tracking-widest opacity-70 hover:opacity-100">
              <ChevronLeft size={14} /> Change trainer
            </button>

            <div className="flex items-center justify-between gap-2">
              <button aria-label="Previous region" onClick={() => setSlide((s) => (s + REGIONS.length - 1) % REGIONS.length)}
                className="border border-retro-green/50 p-2 hover:bg-retro-green hover:text-retro-bg"><ChevronLeft size={16} /></button>
              <div className="flex items-end gap-2 min-h-[56px]">
                {current.starters.map((s) => <Sprite key={s.species} dex={s.pokedexId} size={48} bob={prefs.cutscenes} />)}
              </div>
              <button aria-label="Next region" onClick={() => setSlide((s) => (s + 1) % REGIONS.length)}
                className="border border-retro-green/50 p-2 hover:bg-retro-green hover:text-retro-bg"><ChevronRight size={16} /></button>
            </div>

            <div className="flex justify-center gap-1">
              {REGIONS.map((r, i) => (
                <button key={r.id} aria-label={r.name} onClick={() => setSlide(i)}
                  className={`h-1.5 w-5 ${i === slide ? 'bg-retro-green' : 'bg-retro-green/20'}`} />
              ))}
            </div>

            <button
              onClick={() => { sfx.menuSelect(); setRegion(current); setPicked(null); setStep('arrive'); }}
              className="w-full border-2 border-retro-green py-3 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg"
            >
              Begin in {current.name}
            </button>
            {current.id !== 'kanto' && (
              <p className="text-[11px] opacity-60 text-center">Kanto has the full journey (gyms, rival, Elite Four). {current.name} is open for exploring while its map is being drawn.</p>
            )}
          </div>
        )}

        {step === 'arrive' && region && (
          <div className="space-y-4">
            <div className="border border-retro-green/40 bg-retro-dark p-4">
              <p className="text-[10px] uppercase tracking-widest opacity-60 mb-1">Professor {prof}</p>
              <p className="text-sm leading-relaxed">
                “Welcome to {region.name}, {state.trainerName}! Your journey is about to begin. Come — choose the Pokémon that will travel with you.”
              </p>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep('region')} className="border border-retro-green/50 px-4 py-3 uppercase tracking-widest text-xs hover:bg-retro-green hover:text-retro-bg">Back</button>
              <button onClick={() => { sfx.menuSelect(); setStep('starter'); }}
                className="flex-1 border-2 border-retro-green py-3 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg">Choose my partner</button>
            </div>
          </div>
        )}

        {step === 'starter' && region && (
          <>
            <button onClick={() => { setStep('arrive'); setPicked(null); setError(''); }} className="flex items-center gap-1 text-xs uppercase tracking-widest opacity-70 hover:opacity-100">
              <ChevronLeft size={14} /> Back
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
                    <div className="h-20 flex items-end justify-center"><Sprite dex={s.pokedexId} size={72} bob={active} /></div>
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
