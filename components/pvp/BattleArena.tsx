"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Flag, Loader2 } from 'lucide-react';
import type { PvpAction, PvpMatch, PvpMon, PvpSide } from '@/lib/apiClient';
import { PokeSprite } from '@/components/pvp/PokeSprite';
import { sfx } from '@/lib/sound';

const btn = 'border border-retro-green/60 px-3 py-2 text-xs uppercase tracking-wide hover:bg-retro-green hover:text-retro-bg disabled:opacity-40';
const pretty = (s: string) => s.replace(/-/g, ' ');
const pct = (m: PvpMon) => Math.max(0, Math.min(100, ((m.hp ?? 0) / Math.max(1, m.max_hp ?? 1)) * 100));
const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

function HpBar({ mon }: { mon: PvpMon }) {
  const p = pct(mon);
  return (
    <div className="h-2 bg-retro-green/15" role="progressbar" aria-valuemin={0} aria-valuemax={mon.max_hp} aria-valuenow={mon.hp} aria-label="HP">
      <div className={`h-full transition-[width] duration-700 ease-out ${p > 50 ? 'bg-retro-green' : p > 20 ? 'bg-amber-500' : 'bg-retro-alert'}`} style={{ width: `${p}%` }} />
    </div>
  );
}

function Pips({ side }: { side: PvpSide }) {
  return (
    <span className="inline-flex gap-0.5" aria-label={`${side.team.filter((m) => (m.hp ?? 0) > 0).length} of ${side.team.length} left`}>
      {side.team.map((m, i) => <span key={i} className={`w-2 h-2 rounded-full border border-retro-green/60 ${(m.hp ?? 0) > 0 ? 'bg-retro-green' : ''}`} />)}
    </span>
  );
}

function Panel({ side, mon, you }: { side: PvpSide; mon: PvpMon; you?: boolean }) {
  return (
    <div className="border border-retro-green/50 bg-retro-dark/90 p-1.5 w-[58%] max-w-[15rem] text-[11px] space-y-1">
      <div className="flex items-center justify-between gap-1">
        <span className="uppercase truncate">{mon.nickname ?? mon.species}</span>
        <span className="opacity-70 shrink-0">Lv.{mon.level}</span>
      </div>
      <HpBar mon={mon} />
      <div className="flex items-center justify-between gap-1">
        <span className="opacity-70">{you ? `${mon.hp}/${mon.max_hp}` : `${Math.round(pct(mon))}%`}</span>
        {mon.status && <span className="border border-retro-alert text-retro-alert px-1 uppercase">{mon.status}</span>}
        <Pips side={side} />
      </div>
    </div>
  );
}

/** Flags a sprite as hit / entering / fainted when the shown Pokémon changes between two states. */
function useCues(mon: PvpMon | undefined, key: string) {
  const prev = useRef<{ hp: number; species: string } | null>(null);
  const [cue, setCue] = useState<'' | 'pvp-hit' | 'pvp-enter' | 'pvp-faint'>('');
  useEffect(() => {
    if (!mon) return;
    const p = prev.current;
    let next: typeof cue = '';
    if (p && p.species !== mon.species) next = 'pvp-enter';
    else if (p && (mon.hp ?? 0) < p.hp) next = (mon.hp ?? 0) <= 0 ? 'pvp-faint' : 'pvp-hit';
    if (next === 'pvp-hit') sfx.hit();
    if (next === 'pvp-faint') sfx.faint();
    prev.current = { hp: mon.hp ?? 0, species: mon.species };
    if (next) {
      setCue(next);
      if (next !== 'pvp-faint') { const t = setTimeout(() => setCue(''), 700); return () => clearTimeout(t); }
    } else setCue('');
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return (mon?.hp ?? 1) <= 0 ? 'pvp-faint' : cue;
}

function useCountdown(deadline: number | null | undefined, key: string) {
  const [left, setLeft] = useState<number | null>(deadline ?? null);
  useEffect(() => {
    setLeft(deadline ?? null);
    if (deadline == null) return;
    const t = setInterval(() => setLeft((s) => (s == null ? s : Math.max(0, s - 1))), 1000);
    return () => clearInterval(t);
  }, [deadline, key]);
  return left;
}

interface Props {
  match: PvpMatch;
  busy: boolean;
  error: string;
  onAction: (action: PvpAction) => void;
  onForfeit: () => void;
  onLeave: () => void;
  onRematch?: () => void;
}

export function BattleArena({ match, busy, error, onAction, onForfeit, onLeave, onRematch }: Props) {
  const me = match.me!;
  const foe = match.foe!;
  const meMon = me.team[me.active];
  const foeMon = foe.team[foe.active];
  const key = `${match.id}:${match.seq}`;
  const meCue = useCues(meMon, key);
  const foeCue = useCues(foeMon, key);
  const left = useCountdown(match.deadline, key);
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight }); }, [key]);
  const finished = match.status !== 'active';
  const won = match.winner === match.you;
  const myElo = match.elo?.[match.you];
  const preview = match.phase === 'preview';

  if (preview) return <Preview match={match} busy={busy} error={error} left={left} onAction={onAction} onForfeit={onForfeit} />;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide opacity-70">
        <span>{match.format?.name} · turn {match.turn}</span>
        {!finished && left !== null && <span aria-label="Time left this turn">⏱ {clock(left)}</span>}
      </div>

      <div className="relative w-full aspect-[4/3] max-h-[44vh] border-2 border-retro-green/50 bg-retro-bg overflow-hidden">
        <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent 0 3px, rgba(0,255,100,.15) 3px 4px)' }} />
        <div className="absolute left-3 top-2"><Panel side={foe} mon={foeMon} /></div>
        <div className="absolute right-[8%] top-[10%]">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[110%] h-2 rounded-full bg-retro-green/15" />
          <PokeSprite dexId={foeMon.dex_id} species={foeMon.species} side="front" size={96} fainted={(foeMon.hp ?? 1) <= 0} className={foeCue} />
        </div>
        <div className="absolute left-[8%] bottom-[22%]">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[120%] h-2 rounded-full bg-retro-green/15" />
          <PokeSprite dexId={meMon.dex_id} species={meMon.species} side="back" size={112} fainted={(meMon.hp ?? 1) <= 0} className={meCue} />
        </div>
        <div className="absolute right-2 bottom-2"><Panel side={me} mon={meMon} you /></div>
        <div className="absolute left-3 bottom-2 text-[10px] uppercase opacity-60 max-w-[35%] truncate">{me.name}</div>
        <div className="absolute right-3 top-[44%] text-[10px] uppercase opacity-60 max-w-[35%] truncate text-right">{foe.name}</div>
      </div>

      <div ref={logRef} className="text-[11px] bg-retro-bg border border-retro-green/20 p-2 h-24 overflow-y-auto space-y-0.5" role="log" aria-live="polite">
        {match.log.map((l, i) => <p key={i} className={i === match.log.length - 1 ? '' : 'opacity-70'}>{l}</p>)}
      </div>
      {error && <p className="text-xs text-retro-alert" role="alert">{error}</p>}

      {finished ? (
        <div className="border border-retro-green/50 p-3 space-y-2 text-sm">
          <p className="uppercase tracking-widest">{match.status === 'abandoned' ? 'Battle abandoned' : won ? 'Victory!' : 'Defeat'}</p>
          {myElo && match.format?.rated && <p className="text-xs opacity-80">Rating {myElo.now} ({myElo.delta > 0 ? '+' : ''}{myElo.delta})</p>}
          <div className="flex gap-2 flex-wrap">
            {onRematch && <button className={btn} onClick={onRematch}>Rematch</button>}
            <button className={btn} onClick={onLeave}>Back to lobby</button>
          </div>
        </div>
      ) : match.needs_switch ? (
        <SwitchPicker side={me} prompt="Your Pokémon fainted. Send in:" busy={busy} onPick={(i) => onAction({ type: 'switch', to: i })} />
      ) : match.waiting || match.phase === 'switch' ? (
        <p className="text-xs opacity-80 flex items-center gap-2" role="status">
          <Loader2 size={12} className="animate-spin" />
          {match.phase === 'switch' ? `Waiting for ${foe.name} to send out a Pokémon…` : `Move sent. Waiting for ${foe.name}…`}
          {left !== null && <span className="opacity-60">({clock(left)} left)</span>}
        </p>
      ) : (
        <div className="space-y-2">
          {foe.chosen && <p className="text-xs opacity-80">{foe.name} has chosen. Your move.</p>}
          <div className="grid grid-cols-2 gap-2">
            {(meMon.moves ?? []).map((mv) => (
              <button key={mv.id} className={btn} disabled={busy || mv.pp === 0} onClick={() => onAction({ type: 'move', move: mv.id })}>
                {pretty(mv.id)}{mv.pp != null && <span className="opacity-60"> · {mv.pp}</span>}
              </button>
            ))}
          </div>
          <SwitchPicker side={me} prompt="Switch to:" busy={busy} exclude={me.active} onPick={(i) => onAction({ type: 'switch', to: i })} />
        </div>
      )}
      {!finished && <button className={`${btn} flex items-center gap-1`} onClick={onForfeit}><Flag size={12} /> Forfeit</button>}
    </div>
  );
}

function SwitchPicker({ side, prompt, busy, exclude, onPick }: { side: PvpSide; prompt: string; busy: boolean; exclude?: number; onPick: (i: number) => void }) {
  const options = side.team.map((m, i) => ({ m, i })).filter(({ m, i }) => i !== exclude && (m.hp ?? 0) > 0);
  if (options.length === 0) return null;
  return (
    <div className="space-y-1">
      <p className="text-[11px] uppercase tracking-wide opacity-60">{prompt}</p>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {options.map(({ m, i }) => (
          <button key={i} className="shrink-0 w-24 border border-retro-green/50 p-1 space-y-1 hover:bg-retro-green/10 disabled:opacity-40" disabled={busy} onClick={() => onPick(i)}>
            <PokeSprite dexId={m.dex_id} species={m.species} size={40} className="mx-auto" />
            <span className="block text-[10px] uppercase truncate">{m.nickname ?? m.species}</span>
            <HpBar mon={m} />
          </button>
        ))}
      </div>
    </div>
  );
}

function Preview({ match, busy, error, left, onAction, onForfeit }: { match: PvpMatch; busy: boolean; error: string; left: number | null; onAction: (a: PvpAction) => void; onForfeit: () => void }) {
  const me = match.me!, foe = match.foe!;
  const need = Math.min(match.format?.pick ?? me.team.length, me.team.length);
  const [order, setOrder] = useState<number[]>([]);
  const ready = order.length === need;
  const waiting = !!match.waiting;
  const tap = (i: number) => setOrder((o) => (o.includes(i) ? o.filter((x) => x !== i) : o.length < need ? [...o, i] : o));
  const label = useMemo(() => `Choose ${need} of ${me.team.length}. The first one leads.`, [need, me.team.length]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide opacity-70">
        <span>{match.format?.name} · team preview</span>
        {left !== null && <span aria-label="Time left">⏱ {clock(left)}</span>}
      </div>
      <section className="border border-retro-green/40 p-2 space-y-1">
        <p className="text-[11px] uppercase tracking-wide opacity-60">{foe.name} brings</p>
        <div className="flex flex-wrap gap-2">
          {foe.team.map((m, i) => (
            <span key={i} className="flex flex-col items-center text-[10px] uppercase"><PokeSprite dexId={m.dex_id} species={m.species} size={48} /><span>Lv.{m.level}</span></span>
          ))}
        </div>
      </section>
      <section className="border border-retro-green/40 p-2 space-y-2">
        <p className="text-[11px] uppercase tracking-wide opacity-60">{label}</p>
        <div className="grid grid-cols-3 gap-2">
          {me.team.map((m, i) => {
            const n = order.indexOf(i);
            return (
              <button key={i} disabled={waiting || busy} aria-pressed={n >= 0} onClick={() => tap(i)}
                className={`border p-1 text-[10px] uppercase space-y-1 disabled:opacity-60 ${n >= 0 ? 'border-retro-green bg-retro-green/10' : 'border-retro-green/30'}`}>
                <PokeSprite dexId={m.dex_id} species={m.species} size={48} className="mx-auto" />
                <span className="block truncate">{m.nickname ?? m.species}</span>
                <span className="block opacity-60">Lv.{m.level}{n >= 0 ? ` · #${n + 1}` : ''}</span>
              </button>
            );
          })}
        </div>
        {error && <p className="text-xs text-retro-alert" role="alert">{error}</p>}
        {waiting ? (
          <p className="text-xs opacity-80 flex items-center gap-2" role="status"><Loader2 size={12} className="animate-spin" /> Team sent. Waiting for {foe.name}…</p>
        ) : (
          <button className={`${btn} w-full flex items-center justify-center gap-2`} disabled={!ready || busy} onClick={() => onAction({ type: 'pick', order })}>
            <Check size={13} /> Ready
          </button>
        )}
      </section>
      <button className={`${btn} flex items-center gap-1`} onClick={onForfeit}><Flag size={12} /> Leave</button>
    </div>
  );
}
