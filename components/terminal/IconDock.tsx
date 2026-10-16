"use client";

import { Compass, ShieldAlert, ShoppingBag } from 'lucide-react';
import { sfx } from '@/lib/sound';

/** Every screen the app can show. Only JOURNEY / POKÉMON / SHOP are dock destinations; PROFILE and CONFIG live in
 *  the top-bar menu; 'pokedex' and 'storage' are tabs inside POKÉMON (kept here so older callers still type-check). */
export type ViewName = 'roster' | 'pokemon' | 'pokedex' | 'storage' | 'shop' | 'settings' | 'profile';

interface IconDockProps {
  active: ViewName | null;
  onNavigate: (view: ViewName) => void;
}

const ITEMS: { view: ViewName; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }[] = [
  { view: 'roster', label: 'JOURNEY', icon: Compass },
  { view: 'pokemon', label: 'POKÉMON', icon: ShieldAlert },
  { view: 'shop', label: 'SHOP', icon: ShoppingBag },
];

export function IconDock({ active, onNavigate }: IconDockProps) {
  return (
    <nav aria-label="Main" className="border-t-2 border-retro-green bg-retro-dark px-2 sm:px-4 py-1.5 flex justify-around sm:justify-center gap-2 sm:gap-8">
      {ITEMS.map(({ view, label, icon: Icon }) => {
        const isActive = active === view;
        return (
          <button
            key={view}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => {
              if (!isActive) sfx.menuMove();
              onNavigate(view);
            }}
            className={`flex-1 sm:flex-none sm:min-w-28 flex flex-col items-center gap-1 px-3 py-2 uppercase text-[11px] sm:text-xs tracking-wide sm:tracking-widest transition-colors ${
              isActive ? 'text-retro-bg bg-retro-green' : 'text-retro-green/70 hover:text-retro-green hover:bg-retro-green/10'
            }`}
          >
            <Icon size={18} />
            {label}
          </button>
        );
      })}
    </nav>
  );
}
