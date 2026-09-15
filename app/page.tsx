"use client";

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { RosterScreen } from '@/components/RosterScreen';
import { BattleScreen } from '@/components/BattleScreen';
import { PokedexScreen } from '@/components/PokedexScreen';
import { ShopScreen } from '@/components/ShopScreen';
import { SettingsScreen } from '@/components/SettingsScreen';
import { ProfileScreen } from '@/components/ProfileScreen';
import { TopBar } from '@/components/terminal/TopBar';
import { IconDock, ViewName } from '@/components/terminal/IconDock';

type View = ViewName | 'battle';

export default function Home() {
  const [view, setView] = useState<View>('roster');

  function renderScreen() {
    switch (view) {
      case 'roster':
        return <RosterScreen onEncounter={() => setView('battle')} onNavigate={(v) => setView(v)} />;
      case 'battle':
        return <BattleScreen onExit={() => setView('roster')} />;
      case 'pokedex':
        return <PokedexScreen />;
      case 'shop':
        return <ShopScreen />;
      case 'profile':
        return <ProfileScreen />;
      case 'settings':
        return <SettingsScreen />;
      default:
        return null;
    }
  }

  const dockActive: ViewName = view === 'battle' ? 'roster' : view;

  return (
    <main className="w-full h-full relative z-10 flex flex-col">
      <TopBar />
      <div className="flex-1 min-h-0 overflow-hidden relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={view}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="absolute inset-0 overflow-y-auto"
          >
            {renderScreen()}
          </motion.div>
        </AnimatePresence>
      </div>
      {view !== 'battle' && <IconDock active={dockActive} onNavigate={(v) => setView(v)} />}
    </main>
  );
}
