"use client";

import { ShieldAlert, Book, Settings, ShoppingBag, UserCircle } from 'lucide-react';
import { sfx } from '@/lib/sound';

export type ViewName = 'roster' | 'pokedex' | 'shop' | 'settings' | 'profile';

interface IconDockProps {
  active: ViewName;
  onNavigate: (view: ViewName) => void;
}

const ITEMS: { view: ViewName; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }[] = [
  { view: 'roster', label: 'ROSTER', icon: ShieldAlert },
  { view: 'pokedex', label: 'DEX', icon: Book },
  { view: 'shop', label: 'SHOP', icon: ShoppingBag },
  { view: 'profile', label: 'PROFILE', icon: UserCircle },
  { view: 'settings', label: 'CONFIG', icon: Settings },
];

export function IconDock({ active, onNavigate }: IconDockProps) {
  return (
    <div className="border-t-2 border-retro-green bg-retro-dark px-1 sm:px-4 py-2 flex justify-between sm:justify-center gap-0.5 sm:gap-4 overflow-x-auto custom-scrollbar">
      {ITEMS.map(({ view, label, icon: Icon }) => {
        const isActive = active === view;
        return (
          <button
            key={view}
            onClick={() => {
              if (!isActive) sfx.menuMove();
              onNavigate(view);
            }}
            className={`flex flex-col items-center gap-1 px-2 sm:px-3 py-2 uppercase text-[9px] sm:text-xs tracking-normal sm:tracking-widest transition-colors shrink-0 ${
              isActive ? 'text-retro-bg bg-retro-green box-glow' : 'text-retro-green/70 hover:text-retro-green hover:bg-retro-green/10'
            }`}
          >
            <Icon size={16} className="sm:hidden" />
            <Icon size={18} className="hidden sm:block" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
