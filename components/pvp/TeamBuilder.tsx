"use client";

import { useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Loader2, Save, Trash2 } from 'lucide-react';
import type { PvpCandidate, PvpFormat, PvpPreset } from '@/lib/apiClient';
import { PokeSprite, TypeChips } from '@/components/pvp/PokeSprite';

const btn = 'border border-retro-green/60 px-3 py-1.5 text-xs uppercase tracking-wide hover:bg-retro-green hover:text-retro-bg disabled:opacity-40';
const pretty = (s: string) => s.replace(/-/g, ' ');

interface Props {
  format: PvpFormat;
  pokemon: PvpCandidate[];
  presets: PvpPreset[];
  confirmLabel: string;
  busy: boolean;
  error?: string;
  onConfirm: (ids: string[]) => void;
  onSave: (name: string, ids: string[]) => Promise<void>;
  onDelete: (name: string) => Promise<void>;
  onBack: () => void;
}

/** Choose the Pokémon to bring from the whole collection. The server decides what is legal; this only shows its verdict. */
export function TeamBuilder({ format, pokemon, presets, confirmLabel, busy, error, onConfirm, onSave, onDelete, onBack }: Props) {
  const [ids, setIds] = useState<string[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [note, setNote] = useState('');
  const byId = useMemo(() => new Map(pokemon.map((p) => [p.id, p])), [pokemon]);
  const exact = format.bring === format.pick;
  const valid = ids.length >= 1 && ids.length <= format.bring && (!exact || ids.length === format.pick);
  const mine = presets.filter((t) => t.format_id === format.id || format.id === 'friendly');

  function toggle(p: PvpCandidate) {
    if (!p.eligible) return;
    setNote('');
    setIds((cur) => (cur.includes(p.id) ? cur.filter((x) => x !== p.id) : cur.length < format.bring ? [...cur, p.id] : cur));
  }

  function load(t: PvpPreset) {
    const usable = t.ids.filter((i) => byId.get(i)?.eligible).slice(0, format.bring);
    setIds(usable);
    setNote(usable.length < t.ids.length ? `${t.ids.length - usable.length} Pokémon from "${t.name}" can't be used here and were left out.` : '');
  }

  const rule = exact ? `exactly ${format.pick}` : `up to ${format.bring}${format.bring > format.pick ? `, then choose ${format.pick}` : ''}`;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <button className={btn} onClick={onBack}>Back</button>
        <p className="text-xs uppercase tracking-wide opacity-70 text-right">{format.name} · bring {rule}{format.level_cap ? ` · max Lv.${format.level_cap}` : ''}</p>
      </div>

      <section aria-label="Your team" className="border border-retro-green/40 p-2 space-y-2">
        <p className="text-[11px] uppercase tracking-wide opacity-60">Your team {ids.length}/{format.bring}</p>
        {ids.length === 0 && <p className="text-xs opacity-60">Tap Pokémon below to add them.</p>}
        <ol className="flex flex-wrap gap-2">
          {ids.map((id, i) => {
            const p = byId.get(id);
            return p ? (
              <li key={id}>
                <button className="flex items-center gap-1 border border-retro-green/60 pr-2 text-xs" onClick={() => setIds((c) => c.filter((x) => x !== id))} aria-label={`Remove ${p.nickname}`}>
                  <PokeSprite dexId={p.dex_id} species={p.species} size={36} />
                  <span>{i + 1}. {p.nickname}</span>
                </button>
              </li>
            ) : null;
          })}
        </ol>
        {note && <p className="text-xs text-retro-alert">{note}</p>}
        {error && <p className="text-xs text-retro-alert" role="alert">{error}</p>}
        <button className={`${btn} w-full flex items-center justify-center gap-2`} disabled={!valid || busy} onClick={() => onConfirm(ids)}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} {confirmLabel}
        </button>
      </section>

      <section aria-label="Saved teams" className="border border-retro-green/40 p-2 space-y-2">
        <p className="text-[11px] uppercase tracking-wide opacity-60">Saved teams</p>
        {mine.length === 0 && <p className="text-xs opacity-60">None yet. Build a team and save it below.</p>}
        <ul className="space-y-1">
          {mine.map((t) => (
            <li key={t.name} className="flex items-center gap-2 text-xs">
              <button className={`${btn} flex-1 text-left`} onClick={() => load(t)}>{t.name} <span className="opacity-60">· {t.ids.length}{t.stale ? ' · some gone' : ''}</span></button>
              <button className={btn} aria-label={`Delete ${t.name}`} onClick={() => void onDelete(t.name)}><Trash2 size={12} /></button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <input value={name} maxLength={24} onChange={(e) => setName(e.target.value)} placeholder="Team name" aria-label="Team name"
            className="flex-1 min-w-0 bg-retro-bg border border-retro-green/40 px-2 py-1 text-sm" />
          <button className={`${btn} flex items-center gap-1`} disabled={!name.trim() || ids.length === 0 || busy}
            onClick={async () => { await onSave(name.trim(), ids); setName(''); }}><Save size={12} /> Save</button>
        </div>
      </section>

      <ul className="space-y-2" aria-label="Your Pokémon">
        {pokemon.map((p) => {
          const picked = ids.indexOf(p.id);
          const expanded = open === p.id;
          return (
            <li key={p.id} className={`border p-2 ${picked >= 0 ? 'border-retro-green bg-retro-green/10' : 'border-retro-green/30'} ${p.eligible ? '' : 'opacity-70'}`}>
              <div className="flex items-center gap-2">
                <button className="flex flex-1 items-center gap-2 text-left min-w-0" onClick={() => toggle(p)} disabled={!p.eligible} aria-pressed={picked >= 0}>
                  <PokeSprite dexId={p.dex_id} species={p.species} size={48} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm uppercase truncate">{p.nickname} <span className="opacity-60 text-xs">Lv.{p.level}</span></span>
                    <span className="flex items-center gap-2 text-[11px] opacity-80"><TypeChips types={p.types} /><span>{p.hp}/{p.max_hp} HP</span></span>
                  </span>
                  {picked >= 0 && <span className="text-xs border border-retro-green px-1.5">#{picked + 1}</span>}
                </button>
                <button className="p-1 opacity-70 hover:opacity-100" aria-label={expanded ? 'Hide details' : 'Show details'} aria-expanded={expanded} onClick={() => setOpen(expanded ? null : p.id)}>
                  {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
              </div>
              {!p.eligible && <p className="text-xs text-retro-alert mt-1">{p.reasons[0]}</p>}
              {expanded && (
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                  <dt className="opacity-60">Species</dt><dd className="uppercase">{pretty(p.species)}</dd>
                  <dt className="opacity-60">Ability</dt><dd className="uppercase">{p.ability ? pretty(p.ability) : '—'}</dd>
                  <dt className="opacity-60">Held item</dt><dd className="uppercase">{p.held_item ? pretty(p.held_item) : 'none'}</dd>
                  <dt className="opacity-60">Moves</dt><dd className="uppercase">{p.moves.map(pretty).join(' · ')}</dd>
                </dl>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
