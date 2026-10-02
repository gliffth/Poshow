"use client";

import Image from 'next/image';
import { useGame } from '@/store/GameContext';
import { SPECIES_DB, getTypeAccent } from '@/lib/gameData';
import { CheckCircle2, Eye, HelpCircle } from 'lucide-react';

export function PokedexScreen() {
  const { state } = useGame();
  const allSpecies = Object.values(SPECIES_DB);
  const caughtCount = allSpecies.filter((s) => state.pokedex[s.id]?.caught).length;

  return (
    <div className="w-full max-w-5xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">
      <div className="mb-8 border-b-2 border-retro-green pb-4">
        <h1 className="font-pixel text-lg sm:text-xl leading-relaxed mb-2">Dex Records</h1>
        <p className="text-retro-green/70">{caughtCount} / {allSpecies.length} SPECIES CATALOGUED</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {allSpecies.map((species) => {
          const entry = state.pokedex[species.id];
          const seen = entry?.seen ?? false;
          const caught = entry?.caught ?? false;
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
