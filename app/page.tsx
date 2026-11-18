"use client";

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { RosterScreen } from '@/components/RosterScreen';
import { ScoutScreen } from '@/components/ScoutScreen';
import { BattleScreen } from '@/components/BattleScreen';
import { PokemonHub, type HubTab } from '@/components/PokemonHub';
import { ShopScreen } from '@/components/ShopScreen';
import { QuestsScreen } from '@/components/QuestsScreen';
import { MarketScreen } from '@/components/MarketScreen';
import { SettingsScreen } from '@/components/SettingsScreen';
import { ProfileScreen } from '@/components/ProfileScreen';
import { TopBar } from '@/components/terminal/TopBar';
import { IconDock, ViewName } from '@/components/terminal/IconDock';
import { BootScreen } from '@/components/terminal/BootScreen';
import { AuthScreen } from '@/components/AuthScreen';
import { StarterScreen } from '@/components/StarterScreen';
import { ConnectingScreen } from '@/components/ConnectingScreen';
import { EvolutionScene } from '@/components/EvolutionScene';
import { useGame } from '@/store/GameContext';
import { InfoBubble } from '@/components/InfoBubble';
import { RecoveryBanner } from '@/components/RecoveryBanner';
import { resetTipVisit } from '@/lib/tips';

type View = ViewName | 'scout' | 'battle';

export default function Home() {
  const [view, setView] = useState<View>('roster');
  const [hubTab, setHubTab] = useState<HubTab>('team');
  const [booted, setBooted] = useState(false);
  const { auth, state, needsStarter, serverReachable } = useGame();

  useEffect(() => { resetTipVisit(); }, [view, hubTab]);

  /** older callers still say 'pokedex' / 'storage'; those are tabs of the POKÉMON screen now */
  function go(v: ViewName) {
    if (v === 'pokedex' || v === 'storage') {
      setHubTab(v);
      setView('pokemon');
    } else {
      setView(v);
    }
  }

  function renderScreen() {
    switch (view) {
      case 'roster':
        return <RosterScreen onScout={() => setView('scout')} onEncounter={() => setView('battle')} onNavigate={go} />;
      case 'scout':
        return <ScoutScreen onEncounter={() => setView('battle')} onCancel={() => setView('roster')} />;
      case 'battle':
        return <BattleScreen onExit={() => setView('roster')} />;
      case 'pokemon':
        return <PokemonHub tab={hubTab} onTab={setHubTab} />;
      case 'shop':
        return <ShopScreen />;
      case 'quests':
        return <QuestsScreen />;
      case 'market':
        return <MarketScreen />;
      case 'profile':
        return <ProfileScreen />;
      case 'settings':
        return <SettingsScreen />;
      default:
        return null;
    }
  }

  const dockActive: ViewName | null =
    view === 'battle' || view === 'scout' ? 'roster' : view === 'profile' || view === 'settings' ? null : view;

  if (!booted || auth.status === 'loading') {
    return <BootScreen onComplete={() => setBooted(true)} />;
  }

  // 1) not logged in → register / log in / Telegram
  if (auth.status === 'out') return <><AuthScreen /><InfoBubble aboveDock={false} /></>;

  if (auth.status === 'in') {
    // 2) logged in, but the roster hasn't come back from the server yet (server may be waking up)
    if (!state.hasReconciledServer) return <ConnectingScreen />;
    // 3) new account → pick a region, then a starter
    if (needsStarter && serverReachable) return <StarterScreen />;
  }

  return (
    <main className="w-full h-full relative z-10 flex flex-col">
      <EvolutionScene />
      <RecoveryBanner />
      <TopBar onNavigate={go} />
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
      {view !== 'battle' && view !== 'scout' && <IconDock active={dockActive} onNavigate={go} />}
      {view !== 'battle' && view !== 'scout' && <InfoBubble />}
    </main>
  );
}
