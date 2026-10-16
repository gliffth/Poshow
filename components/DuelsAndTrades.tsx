"use client";

import { useCallback, useEffect, useState } from 'react';
import { Swords, Repeat, Trophy, Loader2 } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import { apiGet, apiPost, ApiError } from '@/lib/apiClient';
import { sfx } from '@/lib/sound';

interface DuelMon { species: string; nickname: string; level: number; hp: number; max_hp: number; status?: string | null; moves: { id: string; pp: number | null }[] }
interface DuelSide { name: string; active: number; chosen: boolean; team: DuelMon[] }
interface Duel { id: string; status: string; you: 'a' | 'b'; phase: string; winner: string | null; log: string[]; me: DuelSide; foe: DuelSide; waiting: boolean; needs_switch: boolean; elo?: Record<string, { name: string; now: number; delta: number }> }
interface PvpState { incoming: { id: string; from: string }[]; outgoing: { id: string; to: string }[]; active: Duel | null; elo: number; wins: number; losses: number }
interface TradeView { id: string; status: string; you: 'a' | 'b'; names: { a: string; b: string }; locked: Record<string, boolean>; confirmed: Record<string, boolean>; offers: Record<string, { pokemon_id: string | null; coins: number }>; pokemon?: Record<string, { species: string; nickname: string; level: number; shiny: boolean } | null>; result?: { evolved: { for: string; from: string; to: string }[] } }
interface TradeState { incoming: { id: string; from: string }[]; outgoing: { id: string; to: string }[]; trade: TradeView | null }

const btn = 'border border-retro-green/60 px-3 py-1.5 text-xs uppercase tracking-wide hover:bg-retro-green hover:text-retro-bg disabled:opacity-40';
const input = 'bg-retro-bg border border-retro-green/40 px-2 py-1.5 text-sm focus:border-retro-green outline-none min-w-0';
const hpBar = (hp: number, max: number) => (
  <span className="inline-block w-24 h-2 bg-retro-green/15 align-middle"><span className="block h-full bg-retro-green" style={{ width: `${Math.max(0, Math.min(100, (hp / Math.max(1, max)) * 100))}%` }} /></span>
);

/** PvP duels (3v3, ranked) and player-to-player trading — web and Telegram trainers can face / trade with each other. */
export function DuelsAndTrades() {
  const { state, actions, avatar } = useGame();
  const uid = state.guestUserId;
  const [tab, setTab] = useState<'duel' | 'trade' | 'rank'>('duel');
  const [pvp, setPvp] = useState<PvpState | null>(null);
  const [trade, setTrade] = useState<TradeState | null>(null);
  const [board, setBoard] = useState<{ rank: number; username: string; elo: number; wins: number; losses: number }[]>([]);
  const [name, setName] = useState('');
  const [coins, setCoins] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPvp(await apiGet<PvpState>(`/api/pvp/state?user_id=${uid}`));
      setTrade(await apiGet<TradeState>(`/api/trade/state?user_id=${uid}`));
    } catch { /* keep the last state */ }
  }, [uid]);

  useEffect(() => { load(); const t = setInterval(load, 3000); return () => clearInterval(t); }, [load]);
  useEffect(() => { if (tab === 'rank') apiGet<{ leaderboard: typeof board }>('/api/leaderboard').then((r) => setBoard(r.leaderboard)).catch(() => {}); }, [tab]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setErr('');
    try { await fn(); sfx.menuSelect(); await load(); await actions.refreshRoster(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : 'That did not work.'); sfx.error(); }
    finally { setBusy(false); }
  }

  const d = pvp?.active;
  const t = trade?.trade;

  return (
    <div className="border border-retro-green/50 bg-retro-dark p-4 space-y-3">
      <div className="flex gap-2">
        {([['duel', Swords, 'Duel'], ['trade', Repeat, 'Trade'], ['rank', Trophy, 'Ranking']] as const).map(([k, Icon, label]) => (
          <button key={k} onClick={() => setTab(k)} className={`flex-1 py-2 text-xs uppercase tracking-wide border-2 flex items-center justify-center gap-1 ${tab === k ? 'bg-retro-green text-retro-bg border-retro-green' : 'border-retro-green/40'}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>
      {err && <p className="text-xs text-retro-alert">{err}</p>}

      {tab === 'duel' && (
        <div className="space-y-3">
          {pvp && <p className="text-[11px] uppercase tracking-wide opacity-60">ELO {pvp.elo} · {pvp.wins}W {pvp.losses}L · 3v3, your real Pokémon aren't hurt</p>}
          {!d && (
            <>
              <div className="flex gap-2">
                <input className={`${input} flex-1`} placeholder="Opponent's username" value={name} onChange={(e) => setName(e.target.value)} autoCapitalize="none" />
                <button className={btn} disabled={busy || !name.trim()} onClick={() => run(() => apiPost('/api/pvp/challenge', { user_id: uid, username: name.trim() }))}>Challenge</button>
              </div>
              {pvp?.incoming.map((i) => (
                <div key={i.id} className="flex items-center justify-between gap-2 border border-retro-green/30 p-2 text-sm">
                  <span>{i.from} challenges you</span>
                  <span className="flex gap-2">
                    <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/respond', { user_id: uid, match_id: i.id, accept: true }))}>Accept</button>
                    <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/respond', { user_id: uid, match_id: i.id, accept: false }))}>No</button>
                  </span>
                </div>
              ))}
              {pvp?.outgoing.map((o) => <p key={o.id} className="text-xs opacity-60 flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Waiting for {o.to} to answer…</p>)}
            </>
          )}
          {d && (
            <div className="space-y-2">
              {[d.foe, d.me].map((side, idx) => {
                const m = side.team[side.active];
                return (
                  <div key={idx} className="border border-retro-green/30 p-2 text-sm">
                    <div className="flex justify-between"><span className="uppercase">{idx === 0 ? side.name : 'You'} · {m.nickname} <span className="opacity-60 text-xs">Lv.{m.level}{m.status ? ` · ${m.status}` : ''}</span></span><span className="text-xs opacity-70">{m.hp}/{m.max_hp}</span></div>
                    {hpBar(m.hp, m.max_hp)} <span className="text-[10px] opacity-50 ml-2">{side.team.filter((x) => x.hp > 0).length}/{side.team.length} left</span>
                  </div>
                );
              })}
              <div className="text-[11px] bg-retro-bg border border-retro-green/20 p-2 max-h-28 overflow-y-auto space-y-0.5">{d.log.map((l, i) => <p key={i}>{l}</p>)}</div>
              {d.status === 'finished' ? (
                <div className="text-sm space-y-1">
                  <p className="uppercase tracking-wide">{d.winner === d.you ? 'You won!' : 'You lost.'}</p>
                  {d.elo && (Object.values(d.elo) as { name: string; now: number; delta: number }[]).map((e) => <p key={e.name} className="text-xs opacity-70">{e.name}: ELO {e.now} ({e.delta > 0 ? '+' : ''}{e.delta})</p>)}
                </div>
              ) : d.needs_switch ? (
                <div className="space-y-1"><p className="text-xs">Your Pokémon fainted — send in:</p>
                  <div className="flex flex-wrap gap-2">{d.me.team.map((m, i) => m.hp > 0 && <button key={i} className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/action', { user_id: uid, match_id: d.id, action: { type: 'switch', to: i } }))}>{m.nickname}</button>)}</div></div>
              ) : d.waiting || d.phase === 'switch' ? (
                <p className="text-xs opacity-70 flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Waiting for your opponent…</p>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">{d.me.team[d.me.active].moves.map((mv) => <button key={mv.id} className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/action', { user_id: uid, match_id: d.id, action: { type: 'move', move: mv.id } }))}>{mv.id.replace(/-/g, ' ')}</button>)}</div>
                  <div className="flex flex-wrap gap-2">{d.me.team.map((m, i) => i !== d.me.active && m.hp > 0 && <button key={i} className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/action', { user_id: uid, match_id: d.id, action: { type: 'switch', to: i } }))}>Switch → {m.nickname}</button>)}</div>
                </div>
              )}
              <div className="flex gap-2">
                {d.status === 'active' && <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/forfeit', { user_id: uid, match_id: d.id }))}>Forfeit</button>}
                {d.status === 'active' && d.waiting === false && <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/pvp/timeout', { user_id: uid, match_id: d.id }))}>Claim timeout</button>}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'trade' && (
        <div className="space-y-3">
          {!t && (
            <>
              <div className="flex gap-2">
                <input className={`${input} flex-1`} placeholder="Trade with (username)" value={name} onChange={(e) => setName(e.target.value)} autoCapitalize="none" />
                <button className={btn} disabled={busy || !name.trim()} onClick={() => run(() => apiPost('/api/trade/invite', { user_id: uid, username: name.trim() }))}>Invite</button>
              </div>
              {trade?.incoming.map((i) => (
                <div key={i.id} className="flex items-center justify-between gap-2 border border-retro-green/30 p-2 text-sm">
                  <span>{i.from} wants to trade</span>
                  <span className="flex gap-2">
                    <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/trade/respond', { user_id: uid, trade_id: i.id, accept: true }))}>Accept</button>
                    <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/trade/respond', { user_id: uid, trade_id: i.id, accept: false }))}>No</button>
                  </span>
                </div>
              ))}
              {trade?.outgoing.map((o) => <p key={o.id} className="text-xs opacity-60 flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Waiting for {o.to}…</p>)}
            </>
          )}
          {t && (() => {
            const me = t.you, other = me === 'a' ? 'b' : 'a';
            const done = t.status === 'done';
            return (
              <div className="space-y-2">
                {(['a', 'b'] as const).map((k) => (
                  <div key={k} className="border border-retro-green/30 p-2 text-sm">
                    <p className="text-[11px] uppercase tracking-wide opacity-60">{k === me ? 'You offer' : `${t.names[k]} offers`} {t.locked[k] ? '· 🔒 locked' : ''}{t.confirmed[k] ? ' · ✔ confirmed' : ''}</p>
                    <p>{t.pokemon?.[k] ? `${t.pokemon[k]!.nickname} Lv.${t.pokemon[k]!.level}${t.pokemon[k]!.shiny ? ' ✦' : ''}` : 'no Pokémon'} · {t.offers[k].coins}₽</p>
                  </div>
                ))}
                {done ? (
                  <p className="text-sm">Trade complete!{t.result?.evolved?.map((e) => ` ${e.for}'s ${e.from} evolved into ${e.to}!`)}</p>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2">
                      {state.party.map((m) => <button key={m.uid} className={`${btn} ${t.offers[me].pokemon_id === m.uid ? 'bg-retro-green text-retro-bg' : ''}`} disabled={busy}
                        onClick={() => run(() => apiPost('/api/trade/offer', { user_id: uid, trade_id: t.id, pokemon_id: m.uid }))}>{m.name}</button>)}
                      <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/trade/offer', { user_id: uid, trade_id: t.id, clear_pokemon: true }))}>No Pokémon</button>
                    </div>
                    <div className="flex gap-2">
                      <input className={`${input} w-28`} type="number" placeholder="Credits" value={coins} onChange={(e) => setCoins(e.target.value)} />
                      <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/trade/offer', { user_id: uid, trade_id: t.id, coins: parseInt(coins || '0', 10) }))}>Set</button>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/trade/lock', { user_id: uid, trade_id: t.id, locked: !t.locked[me] }))}>{t.locked[me] ? 'Unlock' : 'Lock offer'}</button>
                      <button className={btn} disabled={busy || !(t.locked.a && t.locked.b)} onClick={() => run(() => apiPost('/api/trade/confirm', { user_id: uid, trade_id: t.id }))}>Confirm trade</button>
                      <button className={btn} disabled={busy} onClick={() => run(() => apiPost('/api/trade/cancel', { user_id: uid, trade_id: t.id }))}>Cancel</button>
                    </div>
                    <p className="text-[10px] opacity-50">Changing an offer unlocks both sides. Trade-evolution Pokémon (Kadabra, Machoke, Graveler, Haunter…) evolve when they arrive.</p>
                  </>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {tab === 'rank' && (
        <div className="text-sm space-y-1">
          {board.length === 0 && <p className="text-xs opacity-60">No ranked duels yet.</p>}
          {board.map((r) => <p key={r.rank} className="flex justify-between"><span>{r.rank}. {r.username}</span><span className="opacity-70">ELO {r.elo} · {r.wins}W {r.losses}L</span></p>)}
        </div>
      )}
    </div>
  );
}
