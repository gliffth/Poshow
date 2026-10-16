"use client";

import Image from 'next/image';
import { useEffect, useState } from 'react';
import { getPokedexCatalogue, type PokedexCatalogueEntry } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';
import { SPECIES_DB, getTypeAccent } from '@/lib/gameData';
import { CheckCircle2, Eye, HelpCircle } from 'lucide-react';

export function PokedexScreen() {
  const { state } = useGame();
  // The server knows every species; the local SPECIES_DB is only a fallback (offline / guest) so nothing shows "???".
  const [catalogue, setCatalogue] = useState<PokedexCatalogueEntry[] | null>(null);
  const [catalogueFailed, setCatalogueFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!state.guestUserId) return;
    setCatalogueFailed(false);
    getPokedexCatalogue(state.guestUserId)
      .then((r) => setCatalogue(r.species))
      .catch(() => setCatalogueFailed(true));         // keep the local list, but SAY it is incomplete
  }, [state.guestUserId, retry]);

  const localSpecies = Object.values(SPECIES_DB);
  const allSpecies = catalogue
    ? catalogue.map((c) => ({
        id: c.name,
        name: c.name,
        types: c.types,
        spriteUrl: `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/${c.id}.gif`,
        seen: c.seen,
        caught: c.caught,
      }))
    : localSpecies.map((s) => ({
        id: s.id,
        name: s.name,
        types: s.types,
        spriteUrl: s.spriteUrl,
        seen: state.pokedex[s.id]?.seen ?? false,
        caught: state.pokedex[s.id]?.caught ?? false,
      }));
  const caughtCount = allSpecies.filter((s) => s.caught).length;

  return (
    <div className="w-full max-w-5xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">
      <div className="mb-8 border-b-2 border-retro-green pb-4">
        <h1 className="font-pixel text-lg sm:text-xl leading-relaxed mb-2">Pokédex</h1>
        <p className="text-retro-green/70">{caughtCount} / {allSpecies.length} SPECIES CAUGHT{!catalogue && state.guestUserId ? ' (LOCAL LIST)' : ''}</p>
        {catalogueFailed && (
          <p className="mt-2 text-xs text-retro-alert">
            The full Pokédex couldn&apos;t be loaded, so this is the short offline list and the totals are not your real
            progress.{' '}
            <button className="underline" onClick={() => setRetry((n) => n + 1)}>Retry</button>
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {allSpecies.map((species) => {
          const seen = species.seen || species.caught;
          const caught = species.caught;
          const accent = getTypeAccent(species.types[0]);

          return (
            <div
              key={species.id}
              className={`relative border-2 p-3 rounded-sm bg-retro-dark box-glow ${caught ? 'border-retro-green' : 'border-retro-green/30'}`}
            >
              <div className="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2" style={{ borderColor: caught ? accent : undefined }}></div>
              <div className="absolute -top-1 -right-1 w-2 h-2 border-t-2 border-r-2" style={{ borderColor: caught ? accent : undefined }}></div>
              <div className="absolute -bottom-1 -left-1 w-2 h-2 border-b-2 border-l-2" style={{ borderColor: caught ? accent : undefined }}></div>
              <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2" style={{ borderColor: caught ? accent : undefined }}></div>

              <div className="relative w-full aspect-square border-2 border-retro-green/30 bg-retro-bg mb-2 overflow-hidden">
                {seen ? (
                  <Image
                    src={species.spriteUrl}
                    alt={species.name}
                    fill
                    unoptimized
                    referrerPolicy="no-referrer"
                    className={`object-contain [image-rendering:pixelated] p-2 filter contrast-110 saturate-150 ${caught ? '' : 'grayscale brightness-[0.6]'}`}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-retro-green/30">
                    <HelpCircle size={32} />
                  </div>
                )}
              </div>

              <p className="uppercase tracking-widest text-sm truncate">{seen ? species.name : '???'}</p>
              <p className="text-xs opacity-70 uppercase mb-2" style={{ color: seen ? accent : undefined }}>
                {seen ? species.types.join(' / ') : 'unknown type'}
              </p>

              <div className="flex items-center gap-2 text-xs">
                {caught ? (
                  <span className="flex items-center gap-1 text-retro-green"><CheckCircle2 size={12} /> Caught</span>
                ) : seen ? (
                  <span className="flex items-center gap-1 text-retro-green/60"><Eye size={12} /> Seen</span>
                ) : (
                  <span className="text-retro-green/30">No data</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
