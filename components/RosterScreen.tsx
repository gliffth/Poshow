"use client";

import { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { RosterStrip } from './terminal/RosterStrip';
import { ShieldAlert, Book, Settings, Radar, ShoppingBag, Wifi, WifiOff } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import { ViewName } from './terminal/IconDock';

interface RosterScreenProps {
  onEncounter: () => void;
  onNavigate: (view: ViewName) => void;
}

export function RosterScreen({ onEncounter, onNavigate }: RosterScreenProps) {
  const { state, dispatch, actions, serverAvailable } = useGame();
  const [scanning, setScanning] = useState(false);
  const [selectedUid, setSelectedUid] = useState<string | undefined>(state.party[0]?.uid);
  const caughtCount = Object.values(state.pokedex).filter((e) => e.caught).length;

  // keep viewport pointed at a real party member as the roster changes underneath it
  useEffect(() => {
    if (!state.party.some((m) => m.uid === selectedUid)) {
      setSelectedUid(state.party[0]?.uid);
    }
  }, [state.party, selectedUid]);

  const selected = state.party.find((m) => m.uid === selectedUid) ?? state.party[0];

  async function handleScan() {
    const alive = state.party.some((m) => m.hp > 0);
    if (!alive || scanning) return;
    setScanning(true);
    try {
      await actions.scanArea();
      onEncounter();
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="w-full max-w-5xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">

      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 mb-6 sm:mb-8 border-b-2 border-retro-green pb-4">
        <div className="min-w-0">
          <h1 className="font-pixel text-base sm:text-lg lg:text-xl leading-relaxed mb-2 truncate">Your Team</h1>
          <p className="text-retro-green/70 flex items-center gap-2 text-sm">
            {state.party.length} MONSTERS READY
            <span title={serverAvailable ? 'Connected to server' : 'Offline — using local rules'} className="opacity-60 shrink-0">
              {serverAvailable ? <Wifi size={12} /> : <WifiOff size={12} />}
            </span>
          </p>
        </div>
        <div className="flex gap-4">
           <button
             onClick={handleScan}
             disabled={!state.party.some((m) => m.hp > 0) || scanning}
             className="border-2 border-retro-green bg-retro-green/10 hover:bg-retro-green hover:text-retro-bg px-4 sm:px-6 py-2 uppercase tracking-wide sm:tracking-widest text-sm sm:text-base flex items-center gap-2 box-glow group disabled:opacity-30 disabled:pointer-events-none shrink-0"
           >
             <Radar size={18} className={scanning ? 'animate-spin' : 'group-hover:animate-spin'} />
             {scanning ? 'Scanning...' : 'Scan Area'}
           </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 flex-1">
        <div className="space-y-4">
           <h2 className="text-xl uppercase border-b-2 border-retro-green/30 pb-2 flex items-center gap-2">
             <ShieldAlert size={18} /> Active Team
           </h2>

           {/* Party lineup strip — tap one to view it in the frame below */}
           {state.party.length > 1 && (
             <RosterStrip party={state.party} selectedUid={selected?.uid} onSelect={setSelectedUid} />
           )}

           {/* Main viewport — the currently selected monster, in detail */}
           {selected && (
             <StatCard
               monster={selected}
               showXp
               onFeed={() => dispatch({ type: 'FEED_MONSTER', uid: selected.uid })}
               onHeal={(item) => actions.healMonster(selected.uid, item)}
               potionCount={state.inventory.potion}
               superpotionCount={state.inventory.superpotion}
             />
           )}
        </div>

        <div className="space-y-6">
           <h2 className="text-xl uppercase border-b-2 border-retro-green/30 pb-2 flex items-center gap-2">
             <Book size={18} /> Menu
           </h2>

           <div className="grid grid-cols-2 gap-3 sm:gap-4">
             <button
               onClick={() => onNavigate('pokedex')}
               className="border-2 border-retro-green/40 p-4 sm:p-6 flex flex-col items-center justify-center gap-2 sm:gap-3 hover:bg-retro-green/10 hover:border-retro-green box-glow"
             >
               <Book size={24} className="sm:hidden" /><Book size={32} className="hidden sm:block" />
               <span className="uppercase tracking-wide sm:tracking-widest text-sm sm:text-lg">Pokedex</span>
             </button>
             <button
               onClick={() => onNavigate('shop')}
               className="border-2 border-retro-green/40 p-4 sm:p-6 flex flex-col items-center justify-center gap-2 sm:gap-3 hover:bg-retro-green/10 hover:border-retro-green box-glow"
             >
               <ShoppingBag size={24} className="sm:hidden" /><ShoppingBag size={32} className="hidden sm:block" />
               <span className="uppercase tracking-wide sm:tracking-widest text-sm sm:text-lg">Shop</span>
             </button>
             <button
               onClick={() => onNavigate('settings')}
               className="col-span-2 border-2 border-retro-green/40 p-4 sm:p-6 flex flex-col items-center justify-center gap-2 sm:gap-3 hover:bg-retro-green/10 hover:border-retro-green box-glow"
             >
               <Settings size={24} className="sm:hidden" /><Settings size={32} className="hidden sm:block" />
               <span className="uppercase tracking-wide sm:tracking-widest text-sm sm:text-lg">Settings</span>
             </button>
           </div>

           {/* Quick stats */}
           <div className="mt-8 border-2 border-retro-green/30 p-4 bg-retro-green/5 text-sm space-y-1">
             <p className="flex justify-between"><span className="opacity-70">Party size</span> <span>{state.party.length} / 6</span></p>
             <p className="flex justify-between"><span className="opacity-70">Species caught</span> <span>{caughtCount}</span></p>
             <p className="flex justify-between"><span className="opacity-70">Credits</span> <span>{state.currency}</span></p>
           </div>
        </div>
      </div>
    </div>
  );
}
