"use client";

import { PokedexScreen } from '@/components/PokedexScreen';
import { StorageScreen } from '@/components/StorageScreen';

export type HubTab = 'team' | 'storage' | 'pokedex';

const TABS: { id: HubTab; label: string }[] = [
  { id: 'team', label: 'Team' },
  { id: 'storage', label: 'Storage' },
  { id: 'pokedex', label: 'Pokédex' },
];

/** One home for everything about your Pokémon: Team (who fights), Storage (who you own), Pokédex (which species you
 *  have seen / caught). */
export function PokemonHub({ tab, onTab }: { tab: HubTab; onTab: (t: HubTab) => void }) {
  return (
    <div className="h-full flex flex-col">
      <div role="tablist" aria-label="Pokémon" className="flex border-b-2 border-retro-green/40 shrink-0">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => onTab(t.id)}
            className={`flex-1 py-2.5 uppercase text-xs sm:text-sm tracking-widest transition-colors ${
              tab === t.id ? 'bg-retro-green text-retro-bg' : 'text-retro-green/70 hover:bg-retro-green/10'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        {tab === 'team' && <StorageScreen mode="team" />}
        {tab === 'storage' && <StorageScreen mode="storage" />}
        {tab === 'pokedex' && <PokedexScreen />}
      </div>
    </div>
  );
}
