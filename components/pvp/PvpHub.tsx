"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Swords, Users } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import {
  ApiError, pvpChallenge, pvpCollection, pvpDeleteTeam, pvpForfeit, pvpFormats, pvpProfile, pvpQueueJoin, pvpQueueLeave,
  pvpRespond, pvpSaveTeam, type PvpAction, type PvpCandidate, type PvpFormat, type PvpInvite, type PvpMatch, type PvpProfile,
} from '@/lib/apiClient';
import { usePvp } from '@/hooks/usePvp';
import { sfx } from '@/lib/sound';
import { BattleArena } from '@/components/pvp/BattleArena';
import { TeamBuilder } from '@/components/pvp/TeamBuilder';

const btn = 'border border-retro-green/60 px-3 py-1.5 text-xs uppercase tracking-wide hover:bg-retro-green hover:text-retro-bg disabled:opacity-40';
const field = 'bg-retro-bg border border-retro-green/40 px-2 py-1.5 text-sm focus:border-retro-green outline-none min-w-0';
const msg = (e: unknown, fallback = 'That did not work.') => (e instanceof ApiError || e instanceof Error ? e.message : fallback);

type Step =
  | { kind: 'home' }
  | { kind: 'ranked'; format: PvpFormat; ids?: string[] }
  | { kind: 'friendly' }
  | { kind: 'respond'; invite: PvpInvite };

interface Rules { pick: number; level_cap: number | null; turn_timer: number; species_clause: boolean; held_items: boolean }
const DEFAULT_RULES: Rules = { pick: 3, level_cap: null, turn_timer: 120, species_clause: true, held_items: true };

let formatCache: PvpFormat[] | null = null;

/** The PvP lobby: pick a mode, build a team, queue or challenge, then fight in the arena. */
export function PvpHub() {
  const { state, actions } = useGame();
  const uid = state.guestUserId;
  const { summary, active, link, refresh, dismiss, act, setSummary } = usePvp(uid, true);
  const [formats, setFormats] = useState<PvpFormat[]>(formatCache ?? []);
  const [profile, setProfile] = useState<PvpProfile | null>(null);
  const [step, setStep] = useState<Step>({ kind: 'home' });
  const [builder, setBuilder] = useState<{ format: PvpFormat; pokemon: PvpCandidate[] } | null>(null);
  const [name, setName] = useState('');
  const [rules, setRules] = useState<Rules>(DEFAULT_RULES);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [actErr, setActErr] = useState('');
  const queuedSince = useRef<number | null>(null);
  const [, tick] = useState(0);

  const loadProfile = useCallback(async () => { if (uid) try { setProfile(await pvpProfile(uid)); } catch { /* shown on next try */ } }, [uid]);

  useEffect(() => {
    if (formatCache) return;
    pvpFormats().then((r) => { formatCache = r.formats; setFormats(r.formats); }).catch(() => {});
  }, []);
  useEffect(() => { void loadProfile(); }, [loadProfile]);
  useEffect(() => { if (active?.status === 'finished') void loadProfile(); }, [active?.status, loadProfile]);

  const queue = summary?.queue ?? null;
  useEffect(() => {
    if (!queue) { queuedSince.current = null; return; }
    if (queuedSince.current === null) queuedSince.current = Date.now();
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [queue]);

  async function run(fn: () => Promise<void>) {
    setBusy(true); setErr('');
    try { await fn(); sfx.menuSelect(); } catch (e) { setErr(msg(e)); sfx.error(); } finally { setBusy(false); }
  }

  async function openBuilder(next: Step, formatId: string, ruleSet?: { level_cap?: number | null; pick?: number; held_items?: boolean }) {
    await run(async () => {
      const r = await pvpCollection(uid, formatId, ruleSet);
      setBuilder({ format: r.format, pokemon: r.pokemon });
      setStep(next);
    });
  }

  const back = () => { setStep({ kind: 'home' }); setBuilder(null); setErr(''); };
  const savePreset = async (n: string, ids: string[]) => {
    try { const r = await pvpSaveTeam(uid, n, builder!.format.id === 'friendly' ? 'friendly' : builder!.format.id, ids); setProfile((p) => (p ? { ...p, teams: r.teams } : p)); setErr(''); }
    catch (e) { setErr(msg(e)); }
  };
  const deletePreset = async (n: string) => {
    try { const r = await pvpDeleteTeam(uid, n); setProfile((p) => (p ? { ...p, teams: r.teams } : p)); } catch (e) { setErr(msg(e)); }
  };

  async function joinQueue(format: PvpFormat, ids: string[]) {
    await run(async () => {
      const r = await pvpQueueJoin(uid, format.id, ids);
      if (r.matched && r.match) setSummary((s) => ({ incoming: s?.incoming ?? [], outgoing: s?.outgoing ?? [], queue: null, active: r.match! }));
      else await refresh();
      back();
    });
  }

  async function sendAction(match: PvpMatch, action: PvpAction) {
    setBusy(true); setActErr('');
    const problem = await act(match, action);
    if (problem) setActErr(problem);
    setBusy(false);
  }

  // ── in a battle ──
  if (active && active.me && active.foe) {
    const rematch = active.status !== 'active' && active.format
      ? () => {
          const foeName = active.foe!.name;
          dismiss(active.id);
          if (active.format!.id === 'friendly') { setName(foeName); void openBuilder({ kind: 'friendly' }, 'friendly', { level_cap: active.format!.level_cap, pick: active.format!.pick }); }
          else { const f = formats.find((x) => x.id === active.format!.id); if (f) void openBuilder({ kind: 'ranked', format: f }, f.id); }
        }
      : undefined;
    return (
      <div className="space-y-2">
        {link === 'polling' && <p className="text-[10px] opacity-60">Live updates are unavailable; checking every few seconds.</p>}
        <BattleArena
          match={active}
          busy={busy}
          error={actErr}
          onAction={(a) => void sendAction(active, a)}
          onForfeit={async () => {
            if (typeof window !== 'undefined' && !window.confirm(active.phase === 'preview' ? 'Leave this battle?' : 'Forfeit this battle?')) return;
            try { await pvpForfeit(uid, active.id); await refresh(); } catch (e) { setActErr(msg(e)); }
          }}
          onLeave={() => { dismiss(active.id); void actions.refreshRoster(); void loadProfile(); }}
          onRematch={rematch}
        />
      </div>
    );
  }

  // ── building a team ──
  if (builder && step.kind !== 'home') {
    const f = builder.format;
    const label = step.kind === 'ranked' ? 'Find a match' : step.kind === 'friendly' ? 'Send challenge' : 'Accept';
    const onConfirm = (ids: string[]) => {
      if (step.kind === 'ranked') void joinQueue(f, ids);
      else if (step.kind === 'respond') {
        void run(async () => {
          await pvpRespond(uid, step.invite.id, true, ids);
          await refresh();
          back();
        });
      } else {
        void run(async () => {
          await pvpChallenge(uid, name.trim(), ids, { ...rules });
          await refresh();
          back();
        });
      }
    };
    return (
      <TeamBuilder format={f} pokemon={builder.pokemon} presets={profile?.teams ?? []} confirmLabel={label} busy={busy} error={err}
        onConfirm={onConfirm} onSave={savePreset} onDelete={deletePreset} onBack={back} />
    );
  }

  // ── friendly challenge: opponent and rules ──
  if (step.kind === 'friendly') {
    const set = <K extends keyof Rules>(k: K, v: Rules[K]) => setRules((r) => ({ ...r, [k]: v }));
    return (
      <div className="space-y-3">
        <button className={btn} onClick={back}>Back</button>
        <p className="text-xs uppercase tracking-wide opacity-70">Friendly battle · not rated, no rewards</p>
        <input className={`${field} w-full`} placeholder="Opponent's username" value={name} onChange={(e) => setName(e.target.value)} autoCapitalize="none" aria-label="Opponent" />
        <div className="grid grid-cols-2 gap-2 text-xs">
          <label className="space-y-1">Team size
            <select className={`${field} w-full`} value={rules.pick} onChange={(e) => set('pick', Number(e.target.value))}>{[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}</select>
          </label>
          <label className="space-y-1">Level limit
            <input className={`${field} w-full`} type="number" min={5} max={100} placeholder="none" value={rules.level_cap ?? ''} onChange={(e) => set('level_cap', e.target.value ? Number(e.target.value) : null)} />
          </label>
          <label className="space-y-1">Turn timer (s)
            <input className={`${field} w-full`} type="number" min={30} max={300} value={rules.turn_timer} onChange={(e) => set('turn_timer', Number(e.target.value) || 120)} />
          </label>
          <div className="space-y-1">
            <label className="flex items-center gap-2"><input type="checkbox" checked={rules.species_clause} onChange={(e) => set('species_clause', e.target.checked)} /> One of each species</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={rules.held_items} onChange={(e) => set('held_items', e.target.checked)} /> Held items allowed</label>
          </div>
        </div>
        {err && <p className="text-xs text-retro-alert" role="alert">{err}</p>}
        <button className={btn} disabled={busy || !name.trim()} onClick={() => void openBuilder({ kind: 'friendly' }, 'friendly', { level_cap: rules.level_cap, pick: rules.pick, held_items: rules.held_items })}>
          Choose team
        </button>
      </div>
    );
  }

  // ── lobby ──
  const waited = queuedSince.current ? Math.floor((Date.now() - queuedSince.current) / 1000) : 0;
  return (
    <div className="space-y-3">
      {err && <p className="text-xs text-retro-alert" role="alert">{err}</p>}
      {link === 'polling' && <p className="text-[10px] opacity-60">Live updates are unavailable; checking every few seconds.</p>}

      {queue && (
        <div className="border border-retro-green p-3 space-y-2" role="status">
          <p className="text-sm uppercase flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Looking for an opponent · {queue.format?.name}</p>
          <p className="text-xs opacity-70">Waiting {Math.floor(waited / 60)}:{String(waited % 60).padStart(2, '0')}. The search widens the longer you wait. You can leave this screen; you&apos;ll be told when a match is found.</p>
          <button className={btn} disabled={busy} onClick={() => run(async () => { await pvpQueueLeave(uid); await refresh(); })}>Cancel search</button>
        </div>
      )}

      {summary?.incoming.map((i) => (
        <div key={i.id} className="border border-retro-green/40 p-2 text-sm space-y-1">
          <p>{i.from} challenges you{i.format ? ` · ${i.format.name}, bring ${i.format.bring}, use ${i.format.pick}${i.format.level_cap ? `, max Lv.${i.format.level_cap}` : ''}` : ''}</p>
          <div className="flex gap-2">
            {i.format
              ? <button className={btn} disabled={busy} onClick={() => void openBuilder({ kind: 'respond', invite: i }, 'friendly', { level_cap: i.format!.level_cap, pick: i.format!.pick })}>Choose team</button>
              : <button className={btn} disabled={busy} onClick={() => run(async () => { await pvpRespond(uid, i.id, true); await refresh(); })}>Accept</button>}
            <button className={btn} disabled={busy} onClick={() => run(async () => { await pvpRespond(uid, i.id, false); await refresh(); })}>Decline</button>
          </div>
        </div>
      ))}
      {summary?.outgoing.map((o) => <p key={o.id} className="text-xs opacity-60 flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Waiting for {o.to} to answer…</p>)}

      {!queue && (
        <ul className="space-y-2" aria-label="Battle modes">
          {formats.map((f) => {
            const r = profile?.ratings[f.id];
            return (
              <li key={f.id} className="border border-retro-green/40 p-3 space-y-1">
                <p className="text-sm uppercase flex items-center gap-2 justify-between">
                  <span className="flex items-center gap-2">{f.id === 'friendly' ? <Users size={14} /> : <Swords size={14} />} {f.name}</span>
                  {f.rated && <span className="text-xs opacity-70">{r ? `${r.elo} · ${r.w}W ${r.l}L` : '1000 · new'}</span>}
                </p>
                <p className="text-xs opacity-70">{f.blurb}</p>
                <p className="text-[11px] opacity-50">{f.rated ? 'Rated' : 'Not rated'} · {f.turn_timer}s turns</p>
                <button className={btn} disabled={busy} onClick={() => (f.queue ? void openBuilder({ kind: 'ranked', format: f }, f.id) : setStep({ kind: 'friendly' }))}>
                  {f.queue ? 'Find a match' : 'Challenge a friend'}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {profile && (
        <section className="border border-retro-green/30 p-2 space-y-1 text-xs" aria-label="Your record">
          <p className="uppercase tracking-wide opacity-60">Overall {profile.elo} · {profile.wins}W {profile.losses}L</p>
          {profile.history.length === 0 && <p className="opacity-60">No battles yet.</p>}
          <ul className="space-y-0.5">
            {profile.history.slice(0, 8).map((h, i) => (
              <li key={i} className="flex justify-between gap-2"><span>{h.won ? 'W' : 'L'} · {h.opp} · {h.format.replace(/_/g, ' ')}</span><span className="opacity-60">{h.rated ? `${h.delta > 0 ? '+' : ''}${h.delta}` : 'friendly'}</span></li>
            ))}
          </ul>
        </section>
      )}
      {!summary && <p className="text-xs opacity-60 flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Loading…</p>}
    </div>
  );
}
