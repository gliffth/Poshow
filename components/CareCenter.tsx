"use client";

import { useCallback, useEffect, useState } from 'react';
import { HeartPulse, Moon, ArrowUpFromLine, Siren, Pill, Loader2 } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import * as api from '@/lib/apiClient';
import { ApiError } from '@/lib/apiClient';
import { CareState, CareRow } from '@/lib/types';
import { SceneImage } from '@/components/SceneImage';
import { sfx } from '@/lib/sound';

const STATE_STYLE: Record<string, string> = {
  healthy: 'text-retro-green',
  hurt: 'text-retro-green opacity-80',
  injured: 'text-retro-alert',
  critical: 'text-retro-alert',
  resting: 'opacity-60',
};

function ConditionBar({ row }: { row: CareRow }) {
  const c = row.condition;
  return (
    <span className="flex gap-[2px]" title={`${c.ko_left} knockouts before it is in critical danger`}>
      {Array.from({ length: c.vit_max }).map((_, i) => (
        <span key={i} className={`inline-block w-1.5 h-3 ${i < c.vit ? (c.vit <= 1 ? 'bg-retro-alert' : 'bg-retro-green') : 'bg-retro-green/15'}`} />
      ))}
    </span>
  );
}

/** Nurse Joy's Care Center — heal, intensive care for critical Pokémon, resting in the ball. Never during a battle. */
export function CareCenter() {
  const { state, actions, avatar, journey } = useGame();
  const [care, setCare] = useState<CareState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [line, setLine] = useState('Welcome! We\'ll take good care of your Pokémon.');
  const [error, setError] = useState('');
  const region = journey?.region ?? 'kanto';

  const load = useCallback(async () => {
    try {
      setCare(await api.careState(state.guestUserId));
    } catch {
      setCare(null);
    }
  }, [state.guestUserId]);

  useEffect(() => { load(); }, [load, state.party.length]);

  async function run(key: string, action: 'heal' | 'intensive' | 'rest' | 'withdraw', pokemonId?: string, revive = false) {
    if (busy) return;
    setBusy(key);
    setError('');
    try {
      const res = await api.careAction(action, state.guestUserId, pokemonId, revive);
      setCare(res);
      if (res.message) setLine(res.message.replace(/^Joy: /, '').replace(/^"|"$/g, ''));
      sfx.coin();
      await actions.refreshRoster();
    } catch (err) {
      sfx.error();
      setError(err instanceof ApiError ? err.message : 'Nurse Joy is busy — try again.');
    } finally {
      setBusy(null);
    }
  }

  if (!care) return null;
  const hurtAny = care.team.some((r) => r.condition.state !== 'healthy');

  return (
    <div className="border border-retro-green/60 bg-retro-dark box-glow overflow-hidden">
      <div className="relative aspect-[16/7] overflow-hidden border-b border-retro-green/40">
        <SceneImage kind="care" region={region} alt="Pokémon Care Center" />
        <div className="absolute bottom-0 left-0 right-0 bg-retro-bg/85 border-t-2 border-retro-green/50 px-3 py-2">
          <p className="text-[10px] uppercase tracking-wide opacity-60">Nurse Joy</p>
          <p className="text-xs sm:text-sm leading-snug">“{line}”</p>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <p className="flex items-center gap-2 uppercase tracking-wide text-sm"><HeartPulse size={16} /> Pokémon Care Center</p>

        {!care.center_here && (
          <p className="text-xs text-retro-alert">There's no Care Center on a route — head to a town to heal. You can still let a Pokémon sleep in its ball.</p>
        )}
        {error && <p className="text-xs text-retro-alert">{error}</p>}

        {care.team.map((r) => (
          <div key={r.id} className="border border-retro-green/30 p-2 space-y-1">
            <div className="flex justify-between items-center gap-2 text-sm">
              <span className="truncate uppercase">{r.nickname} <span className="opacity-60 text-xs">Lv.{r.level}</span></span>
              <span className="text-xs opacity-70 shrink-0">{r.current_hp}/{r.max_hp} HP</span>
            </div>
            <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-wide">
              <span className="flex items-center gap-2"><ConditionBar row={r} /><span className={STATE_STYLE[r.condition.state]}>{r.condition.label}</span></span>
              <span className="opacity-50 shrink-0">{r.condition.ko_left} KO left</span>
            </div>
            <div className="flex gap-2 flex-wrap pt-1">
              {r.condition.state === 'critical' ? (
                <>
                  <button disabled={!!busy || !care.center_here} onClick={() => run('i' + r.id, 'intensive', r.id)}
                    className="border border-retro-alert text-retro-alert px-2 py-1 text-[11px] uppercase tracking-wide flex items-center gap-1 hover:bg-retro-alert hover:text-retro-bg disabled:opacity-40">
                    <Siren size={12} /> Intensive care · {r.condition.care_cost}₽ · {Math.round(r.condition.revive_chance * 100)}%
                  </button>
                  {care.revives > 0 && (
                    <button disabled={!!busy || !care.center_here} onClick={() => run('v' + r.id, 'intensive', r.id, true)}
                      className="border border-retro-green px-2 py-1 text-[11px] uppercase tracking-wide flex items-center gap-1 hover:bg-retro-green hover:text-retro-bg disabled:opacity-40">
                      <Pill size={12} /> Revive ×{care.revives}
                    </button>
                  )}
                </>
              ) : (
                <button disabled={!!busy} onClick={() => run('r' + r.id, 'rest', r.id)}
                  className="border border-retro-green/50 px-2 py-1 text-[11px] uppercase tracking-wide flex items-center gap-1 hover:bg-retro-green hover:text-retro-bg disabled:opacity-40">
                  <Moon size={12} /> Sleep in ball
                </button>
              )}
            </div>
          </div>
        ))}

        {care.resting.length > 0 && (
          <div className="space-y-1">
            <p className="text-[10px] uppercase tracking-wide opacity-60">Sleeping in their Poké Balls — slowly recovering</p>
            {care.resting.map((r) => (
              <div key={r.id} className="border border-retro-green/20 p-2 flex items-center justify-between gap-2 opacity-90">
                <span className="text-sm uppercase truncate">💤 {r.nickname} <span className="opacity-60 text-xs">{r.current_hp}/{r.max_hp}</span></span>
                <span className="flex items-center gap-2 shrink-0"><ConditionBar row={r} />
                  <button disabled={!!busy} onClick={() => run('w' + r.id, 'withdraw', r.id)}
                    className="border border-retro-green/50 px-2 py-1 text-[11px] uppercase tracking-wide flex items-center gap-1 hover:bg-retro-green hover:text-retro-bg disabled:opacity-40">
                    <ArrowUpFromLine size={12} /> Take out
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}

        <button disabled={!!busy || !care.center_here || !care.team.length} onClick={() => run('heal', 'heal')}
          className="w-full border-2 border-retro-green py-2 flex items-center justify-center gap-2 text-sm uppercase tracking-wide hover:bg-retro-green hover:text-retro-bg disabled:opacity-40 disabled:pointer-events-none">
          {busy === 'heal' ? <Loader2 size={14} className="animate-spin" /> : <HeartPulse size={14} />}
          {hurtAny ? 'Heal everyone — free' : 'Everyone is healthy'}
        </button>
        <p className="text-[10px] opacity-50">Not available during a battle. Sleeping Pokémon recover ~2% HP a minute and a condition point every 15 minutes.</p>
      </div>
    </div>
  );
}
