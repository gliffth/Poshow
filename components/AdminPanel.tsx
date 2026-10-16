"use client";

import { useState } from 'react';
import { Shield, Search, Gift, Image as ImageIcon } from 'lucide-react';
import * as api from '@/lib/apiClient';
import { ApiError, AdminPlayer } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';

const SLOTS = [
  'region_kanto', 'region_johto', 'region_hoenn', 'region_sinnoh', 'region_unova', 'region_kalos',
  'region_alola', 'region_galar', 'region_paldea', 'route', 'town', 'care_center', 'starter_lab', 'gym', 'league',
];
const BALLS = ['pokeball', 'greatball', 'ultraball', 'masterball'];
const input = 'bg-retro-bg border-2 border-retro-green/40 px-2 py-1.5 text-sm focus:border-retro-green outline-none min-w-0';
const btn = 'border-2 border-retro-green/60 px-3 py-1.5 text-xs uppercase tracking-widest hover:bg-retro-green hover:text-retro-bg disabled:opacity-40';

export function AdminPanel() {
  const { assets } = useGame();
  const [username, setUsername] = useState('');
  const [player, setPlayer] = useState<AdminPlayer | null>(null);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [coins, setCoins] = useState('');
  const [item, setItem] = useState('potion');
  const [itemQty, setItemQty] = useState('1');
  const [ball, setBall] = useState('pokeball');
  const [ballQty, setBallQty] = useState('5');
  const [species, setSpecies] = useState('');
  const [level, setLevel] = useState('5');
  const [shiny, setShiny] = useState(false);
  const [slot, setSlot] = useState(SLOTS[0]);
  const [url, setUrl] = useState('');

  async function wrap(fn: () => Promise<void>) {
    setBusy(true); setErr(''); setMsg('');
    try { await fn(); } catch (e) { setErr(e instanceof ApiError ? e.message : 'Request failed.'); } finally { setBusy(false); }
  }
  const lookup = () => wrap(async () => setPlayer(await api.adminPlayer(username.trim())));
  const give = (gift: Omit<api.AdminGift, 'username'>) => wrap(async () => {
    const r = await api.adminGive({ username: username.trim(), ...gift });
    setPlayer(r.player); setMsg('Done: ' + r.done.join(' · '));
  });

  return (
    <div className="border-2 border-retro-alert/60 p-5 bg-retro-dark space-y-4">
      <p className="flex items-center gap-2 uppercase tracking-widest text-retro-alert"><Shield size={18} /> Admin</p>

      <div className="flex gap-2">
        <input className={`${input} flex-1`} placeholder="Player username" value={username} onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') lookup(); }} autoCapitalize="none" />
        <button className={btn} disabled={busy || !username.trim()} onClick={lookup}><Search size={14} /></button>
      </div>
      {err && <p className="text-xs text-retro-alert">{err}</p>}
      {msg && <p className="text-xs">{msg}</p>}

      {player && (
        <div className="text-xs space-y-1 border border-retro-green/30 p-2">
          <p className="uppercase tracking-widest">{player.username} <span className="opacity-50">#{player.user_id}</span></p>
          <p>💰 {player.coins} · {player.region} · {player.badges.length} badges</p>
          <p>👥 {player.team.map((m) => `${m.nickname} Lv${m.level} (${m.state})`).join(', ') || '—'} {player.stored ? `· ${player.stored} stored` : ''}</p>
          <p className="opacity-70">🎒 {Object.entries(player.inventory).map(([k, v]) => `${k}×${v}`).join(', ') || '—'}</p>
        </div>
      )}

      <div className="space-y-3 border-t border-retro-green/20 pt-3">
        <p className="flex items-center gap-2 text-xs uppercase tracking-widest opacity-70"><Gift size={14} /> Give to this player</p>
        <div className="flex gap-2">
          <input className={`${input} flex-1`} type="number" placeholder="Credits (negative takes)" value={coins} onChange={(e) => setCoins(e.target.value)} />
          <button className={btn} disabled={busy || !username.trim() || !coins} onClick={() => give({ coins: parseInt(coins, 10) })}>Give</button>
        </div>
        <div className="flex gap-2">
          <input className={`${input} flex-1`} placeholder="item (potion, revive, rare_candy…)" value={item} onChange={(e) => setItem(e.target.value)} />
          <input className={`${input} w-16`} type="number" value={itemQty} onChange={(e) => setItemQty(e.target.value)} />
          <button className={btn} disabled={busy || !username.trim()} onClick={() => give({ items: { [item.trim().toLowerCase()]: parseInt(itemQty, 10) || 1 } })}>Give</button>
        </div>
        <div className="flex gap-2">
          <select className={`${input} flex-1`} value={ball} onChange={(e) => setBall(e.target.value)}>
            {BALLS.map((b) => <option key={b}>{b}</option>)}
          </select>
          <input className={`${input} w-16`} type="number" value={ballQty} onChange={(e) => setBallQty(e.target.value)} />
          <button className={btn} disabled={busy || !username.trim()} onClick={() => give({ balls: { [ball]: parseInt(ballQty, 10) || 1 } })}>Give</button>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <input className={`${input} flex-1`} placeholder="Pokémon species (e.g. eevee)" value={species} onChange={(e) => setSpecies(e.target.value)} />
          <input className={`${input} w-16`} type="number" min={1} max={100} value={level} onChange={(e) => setLevel(e.target.value)} />
          <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={shiny} onChange={(e) => setShiny(e.target.checked)} /> ✨</label>
          <button className={btn} disabled={busy || !username.trim() || !species.trim()}
            onClick={() => give({ pokemon: { species: species.trim().toLowerCase(), level: parseInt(level, 10) || 5, shiny } })}>Give</button>
        </div>
        <button className={`${btn} w-full`} disabled={busy || !username.trim()} onClick={() => give({ heal: true })}>Heal & revive their whole team</button>
      </div>

      <div className="space-y-2 border-t border-retro-green/20 pt-3">
        <p className="flex items-center gap-2 text-xs uppercase tracking-widest opacity-70"><ImageIcon size={14} /> Scene images</p>
        <p className="text-[11px] opacity-60">Pick a slot and paste an https:// image link (or a /path on this site). Leave empty and save to go back to the built-in pixel scene.</p>
        <div className="flex gap-2">
          <select className={`${input} w-40`} value={slot} onChange={(e) => { setSlot(e.target.value); setUrl(assets[e.target.value] ?? ''); }}>
            {SLOTS.map((s) => <option key={s} value={s}>{s}{assets[s] ? ' ✓' : ''}</option>)}
          </select>
          <input className={`${input} flex-1`} placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className={btn} disabled={busy} onClick={() => wrap(async () => { await api.adminSetAsset(slot, url.trim()); setMsg(`${slot} ${url.trim() ? 'updated' : 'reset'} — reload to see it.`); })}>Save</button>
        </div>
      </div>
    </div>
  );
}
