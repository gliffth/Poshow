"use client";

import { useEffect, useState } from 'react';

const BASE = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon';

function sources(dexId: number, side: 'front' | 'back'): string[] {
  return side === 'back'
    ? [`${BASE}/other/showdown/back/${dexId}.gif`, `${BASE}/back/${dexId}.png`, `${BASE}/${dexId}.png`]
    : [`${BASE}/other/showdown/${dexId}.gif`, `${BASE}/${dexId}.png`];
}

interface Props {
  dexId?: number | null;
  species: string;
  side?: 'front' | 'back';
  size?: number;
  fainted?: boolean;
  className?: string;
}

/** A Pokémon sprite in a fixed square, scaled without distortion. Falls back to the next artwork, then to a letter. */
export function PokeSprite({ dexId, species, side = 'front', size = 96, fainted = false, className = '' }: Props) {
  const [stage, setStage] = useState(0);
  useEffect(() => { setStage(0); }, [dexId, side]);
  const list = dexId ? sources(dexId, side) : [];
  const box = { width: size, height: size };
  if (!dexId || stage >= list.length) {
    return (
      <span style={box} className={`inline-flex items-center justify-center border border-retro-green/40 text-retro-green/70 uppercase ${className}`} role="img" aria-label={species}>
        {species.slice(0, 1)}
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={list[stage]}
      alt={species}
      style={{ ...box, imageRendering: 'pixelated', objectFit: 'contain' }}
      className={`${fainted ? 'grayscale opacity-60' : ''} ${className}`}
      onError={() => setStage((s) => s + 1)}
      draggable={false}
    />
  );
}

export const TYPE_COLOR: Record<string, string> = {
  normal: 'border-zinc-400/60', fire: 'border-orange-500/70', water: 'border-sky-500/70', electric: 'border-yellow-400/70',
  grass: 'border-green-500/70', ice: 'border-cyan-300/70', fighting: 'border-red-600/70', poison: 'border-purple-500/70',
  ground: 'border-amber-600/70', flying: 'border-indigo-300/70', psychic: 'border-pink-500/70', bug: 'border-lime-500/70',
  rock: 'border-stone-500/70', ghost: 'border-violet-600/70', dragon: 'border-indigo-500/70', dark: 'border-neutral-500/70',
  steel: 'border-slate-400/70', fairy: 'border-fuchsia-300/70',
};

export function TypeChips({ types }: { types: string[] }) {
  return (
    <span className="inline-flex gap-1 flex-wrap">
      {types.map((t) => (
        <span key={t} className={`border px-1 text-[10px] uppercase tracking-wide ${TYPE_COLOR[t] ?? 'border-retro-green/40'}`}>{t}</span>
      ))}
    </span>
  );
}
