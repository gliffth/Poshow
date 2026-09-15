"use client";

import { useGame } from '@/store/GameContext';
import { SPECIES_DB } from '@/lib/gameData';
import { UserCircle, Wallet, Book, ShieldAlert, Package } from 'lucide-react';

export function ProfileScreen() {
  const { state } = useGame();
  const totalSpecies = Object.keys(SPECIES_DB).length;
  const caughtCount = Object.values(state.pokedex).filter((e) => e.caught).length;
  const highestLevel = state.party.reduce((max, m) => Math.max(max, m.level), 0);
  const inventoryTotal = Object.values(state.inventory).reduce((a, b) => a + b, 0);

  return (
    <div className="w-full max-w-2xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">
      <div className="mb-8 border-b-2 border-retro-green pb-4">
        <h1 className="font-pixel text-lg sm:text-xl leading-relaxed mb-2">Trainer Card</h1>
        <p className="text-retro-green/70">YOUR PROGRESS</p>
      </div>

      <div className="relative border-2 border-retro-green p-6 bg-retro-dark box-glow mb-6">
        <div className="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2 border-retro-green"></div>
        <div className="absolute -top-1 -right-1 w-2 h-2 border-t-2 border-r-2 border-retro-green"></div>
        <div className="absolute -bottom-1 -left-1 w-2 h-2 border-b-2 border-l-2 border-retro-green"></div>
        <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2 border-retro-green"></div>

        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 border-2 border-retro-green/50 flex items-center justify-center bg-retro-bg">
            <UserCircle size={40} />
          </div>
          <div>
            <p className="font-pixel text-sm leading-relaxed">{state.trainerName}</p>
            <p className="text-xs opacity-60 mt-1">TRAINER</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <StatRow icon={<Wallet size={16} />} label="Credits" value={state.currency} />
          <StatRow icon={<ShieldAlert size={16} />} label="Party Size" value={`${state.party.length} / 6`} />
          <StatRow icon={<Book size={16} />} label="Dex Progress" value={`${caughtCount} / ${totalSpecies}`} />
          <StatRow icon={<Package size={16} />} label="Items Held" value={inventoryTotal} />
        </div>
      </div>

      <div className="border-2 border-retro-green/30 p-4 bg-retro-green/5 text-sm space-y-1">
        <p className="flex justify-between"><span className="opacity-70">Highest level</span> <span>Lv.{highestLevel}</span></p>
        <p className="flex justify-between"><span className="opacity-70">Species catalogued</span> <span>{caughtCount}</span></p>
      </div>
    </div>
  );
}

function StatRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="border-2 border-retro-green/20 p-3 flex items-center gap-3">
      <div className="text-retro-green/70">{icon}</div>
      <div>
        <p className="text-xs opacity-60 uppercase">{label}</p>
        <p className="text-lg">{value}</p>
      </div>
    </div>
  );
}
