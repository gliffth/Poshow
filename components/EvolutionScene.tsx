"use client";

import { useEffect, useRef, useState } from 'react';
import { useGame } from '@/store/GameContext';
import * as api from '@/lib/apiClient';
import { ApiError } from '@/lib/apiClient';
import { usePrefs } from '@/lib/prefs';
import { sfx } from '@/lib/sound';

const sprite = (name: string) =>
  `https://play.pokemonshowdown.com/sprites/ani/${name.toLowerCase().replace(/[^a-z0-9]/g, '')}.gif`;

type Phase = 'ask' | 'charge' | 'cycle' | 'flash' | 'reveal' | 'error';

/**
 * Evolution as a moment, not a database update. Modelled on the games' own evolution scene:
 * message -> the Pokémon reacts -> sparkles gather -> the sprite cycles between old and new forms faster and
 * faster -> white flash -> the new form appears. The species only changes on the SERVER once the player agrees
 * (one atomic call), and "Not now" leaves it pending — the Roster keeps its Evolve button.
 */
export function EvolutionScene() {
  const { evolutionQueue, dismissEvolution, actions, state } = useGame();
  const [prefs] = usePrefs();
  const [phase, setPhase] = useState<Phase>('ask');
  const [showNew, setShowNew] = useState(false);
  const [msg, setMsg] = useState('');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const cur = evolutionQueue[0];

  useEffect(() => {
    setPhase('ask'); setShowNew(false); setMsg('');
    return () => { timers.current.forEach(clearTimeout); timers.current = []; };
  }, [cur?.id]);

  if (!cur || state.battle) return null;           // never in the middle of a battle
  const strobe = prefs.flicker && prefs.cutscenes;

  const later = (ms: number, fn: () => void) => { timers.current.push(setTimeout(fn, ms)); };

  async function start() {
    if (!cur) return;
    sfx.menuSelect();
    setPhase('charge');
    const call = api.evolve(state.guestUserId, cur.id, cur.to).then(() => null, (e) => (e instanceof ApiError ? e.message : 'It could not evolve.'));
    later(strobe ? 1500 : 600, async () => {
      const err = await call;
      if (err) { setMsg(err); setPhase('error'); return; }
      setPhase('cycle');
      // old <-> new, accelerating (slow cross-fade only, if flicker is off)
      let delay = strobe ? 420 : 900, n = 0, newShown = false;
      const tick = () => {
        newShown = !newShown; setShowNew(newShown); n += 1; delay = Math.max(70, delay * 0.82);
        if (n < (strobe ? 16 : 4)) later(delay, tick);
        else later(200, () => { setPhase('flash'); sfx.coin(); later(strobe ? 700 : 300, () => { setShowNew(true); setPhase('reveal'); actions.refreshRoster(); }); });
      };
      later(delay, tick);
    });
  }

  const name = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const silhouette = phase === 'cycle' || phase === 'flash';

  return (
    <div className="fixed inset-0 z-[60] bg-black/90 flex flex-col items-center justify-center p-4 text-retro-green">
      {phase === 'flash' && <div className="absolute inset-0 bg-white evo-flash pointer-events-none" />}

      <div className="relative w-56 h-56 flex items-center justify-center">
        {(phase === 'charge' || phase === 'cycle') && strobe &&
          Array.from({ length: 10 }).map((_, i) => (
            <span key={i} className="evo-spark absolute text-retro-green" style={{ left: `${10 + (i * 37) % 80}%`, top: `${15 + (i * 53) % 70}%`, animationDelay: `${(i % 5) * 0.2}s` }}>✦</span>
          ))}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={sprite(showNew || phase === 'reveal' ? cur.to : cur.from)}
          alt=""
          className={phase === 'charge' ? 'evo-glow' : ''}
          style={{
            imageRendering: 'pixelated', maxWidth: '100%', maxHeight: '100%', transition: 'filter 0.15s',
            filter: silhouette ? 'brightness(0) invert(1) drop-shadow(0 0 10px #fff)' : phase === 'reveal' ? 'drop-shadow(0 0 12px #c9cec9)' : 'none',
          }}
        />
      </div>

      <div className="mt-6 text-center max-w-sm min-h-[5rem] space-y-3">
        {phase === 'ask' && (
          <>
            <p className="font-pixel text-sm leading-relaxed">What? {cur.nickname} is ready to evolve!</p>
            <p className="text-xs opacity-60">{name(cur.from)} → {name(cur.to)}</p>
            <div className="flex gap-3 justify-center">
              <button onClick={start} className="border-2 border-retro-green px-5 py-2 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg">Evolve</button>
              <button onClick={() => dismissEvolution(cur.id)} className="border-2 border-retro-green/40 px-5 py-2 uppercase tracking-widest text-sm opacity-70 hover:opacity-100">Not now</button>
            </div>
          </>
        )}
        {(phase === 'charge' || phase === 'cycle' || phase === 'flash') && <p className="font-pixel text-sm leading-relaxed">{cur.nickname} is evolving…</p>}
        {phase === 'reveal' && (
          <>
            <p className="font-pixel text-sm leading-relaxed">Congratulations! {cur.nickname} evolved into {name(cur.to)}!</p>
            <button onClick={() => dismissEvolution(cur.id)} className="border-2 border-retro-green px-6 py-2 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg">Continue</button>
          </>
        )}
        {phase === 'error' && (
          <>
            <p className="text-sm text-retro-alert">{msg}</p>
            <button onClick={() => dismissEvolution(cur.id)} className="border-2 border-retro-green/50 px-6 py-2 uppercase tracking-widest text-sm">Close</button>
          </>
        )}
      </div>
    </div>
  );
}
