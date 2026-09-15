"use client";

import { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { TerminalLog } from './terminal/TerminalLog';
import { useGame } from '@/store/GameContext';
import { Backpack, Footprints, Swords, Repeat, Target, ChevronLeft } from 'lucide-react';
import { ItemType, BallType } from '@/lib/types';
import { sfx } from '@/lib/sound';

interface BattleScreenProps {
  onExit: () => void;
}

type MenuState = 'main' | 'fight' | 'bag' | 'switch';

const BALL_ITEMS: ItemType[] = ['pokeball', 'greatball', 'ultraball'];
const HEAL_ITEMS: ItemType[] = ['potion', 'superpotion'];

function BackRow({ onBack }: { onBack: () => void }) {
  // inline, in normal document flow — the old version used an absolutely
  // positioned button floating above the panel, which overlapped whatever
  // sat above it the moment the viewport got short (landscape phones)
  return (
    <button
      onClick={onBack}
      className="mb-3 flex items-center gap-1 border-2 border-retro-green/50 px-3 py-1 text-xs hover:bg-retro-green hover:text-retro-bg uppercase"
    >
      <ChevronLeft size={14} /> Back
    </button>
  );
}

export function BattleScreen({ onExit }: BattleScreenProps) {
  const { state, dispatch, actions } = useGame();
  const [menuState, setMenuState] = useState<MenuState>('main');
  const [pending, setPending] = useState(false);
  const battle = state.battle;
  const active = battle ? state.party.find((m) => m.uid === battle.playerUid) : undefined;
  const isServerBattle = !!battle?.serverBattleId;

  // local-only pacing beat, no-op for server battles (backend resolves both turns at once)
  useEffect(() => {
    if (!battle || isServerBattle) return;
    if (battle.phase === 'resolving' && battle.awaitingEnemyMove) {
      const t = setTimeout(() => dispatch({ type: 'ENEMY_MOVE' }), 1300);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [battle?.phase, battle?.awaitingEnemyMove, isServerBattle, dispatch]);

  useEffect(() => {
    if (battle?.phase === 'player_choice') setMenuState('main');
  }, [battle?.phase]);

  if (!battle || !active) {
    return (
      <div className="w-full max-w-2xl mx-auto h-full flex flex-col items-center justify-center gap-4 p-6">
        <p className="text-xl opacity-70">NO ACTIVE ENCOUNTER</p>
        <button onClick={onExit} className="border-2 border-retro-green/50 px-6 py-2 hover:bg-retro-green hover:text-retro-bg uppercase tracking-widest">
          Back to Roster
        </button>
      </div>
    );
  }

  const isLocked = pending || battle.phase === 'resolving' || battle.phase === 'victory' || battle.phase === 'defeat' || battle.phase === 'caught' || battle.phase === 'fled';
  const benchable = state.party.filter((m) => m.uid !== battle.playerUid && m.hp > 0);
  const endPhase = ['victory', 'defeat', 'caught', 'fled'].includes(battle.phase);

  async function handleMove(moveId: string) {
    if (isLocked) return;
    sfx.menuSelect();
    setMenuState('main');
    setPending(true);
    try {
      await actions.playerMove(moveId);
    } finally {
      setPending(false);
    }
  }

  async function handleCatch(ball: ItemType) {
    if (isLocked) return;
    sfx.menuSelect();
    setMenuState('main');
    setPending(true);
    try {
      await actions.catchAttempt(ball as BallType);
    } finally {
      setPending(false);
    }
  }

  async function handleHeal(item: ItemType) {
    if (isLocked) return;
    sfx.menuSelect();
    setMenuState('main');
    setPending(true);
    try {
      await actions.useItem(item as 'potion' | 'superpotion');
    } finally {
      setPending(false);
    }
  }

  async function handleSwitch(uid: string, free: boolean) {
    setMenuState('main');
    setPending(true);
    try {
      await actions.switchActive(uid, free);
    } finally {
      setPending(false);
    }
  }

  async function handleFlee() {
    if (isLocked) return;
    sfx.menuBack();
    setPending(true);
    try {
      await actions.flee();
    } finally {
      setPending(false);
    }
  }

  function handleContinue() {
    dispatch({ type: 'END_BATTLE' });
    onExit();
  }

  return (
    <div className="w-full h-full flex flex-col overflow-hidden">
      {/* scrolls independently so short/landscape viewports never clip content
          behind the sticky action menu below */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        <div className="w-full max-w-4xl mx-auto flex flex-col p-3 sm:p-6 lg:p-10 gap-3 sm:gap-4">

          <div className="flex justify-end w-full">
            <div className="w-full max-w-md">
              <StatCard monster={battle.enemy} isOpponent />
            </div>
          </div>

          <TerminalLog log={battle.log} heightClass="h-20 sm:h-28" />

          <div className="flex justify-start w-full">
            <div className="w-full max-w-md">
              <StatCard monster={active} showXp />
            </div>
          </div>

          {battle.phase === 'force_switch' && (
            <div className="border-2 border-retro-alert/60 bg-retro-dark p-3 sm:p-4 box-glow-alert">
              <p className="uppercase tracking-widest text-retro-alert mb-3 text-sm sm:text-base">Choose a replacement:</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {state.party.filter((m) => m.hp > 0).map((m) => (
                  <button
                    key={m.uid}
                    onClick={() => handleSwitch(m.uid, true)}
                    className="border-2 border-retro-green/50 px-4 py-3 hover:bg-retro-green hover:text-retro-bg uppercase tracking-wide text-left text-sm sm:text-base"
                  >
                    {m.name} <span className="opacity-70 text-xs sm:text-sm block sm:inline">Lv.{m.level} — {m.hp}/{m.maxHp} HP</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {endPhase && (
            <div className="border-2 border-retro-green/60 bg-retro-dark p-4 sm:p-6 box-glow text-center space-y-4">
              <p className="text-lg sm:text-2xl uppercase tracking-widest text-glow">
                {battle.phase === 'victory' && 'Victory'}
                {battle.phase === 'defeat' && 'Blacked Out'}
                {battle.phase === 'caught' && 'Capture Successful'}
                {battle.phase === 'fled' && 'Retreated'}
              </p>
              <button
                onClick={handleContinue}
                className="border-2 border-retro-green px-8 py-2 hover:bg-retro-green hover:text-retro-bg uppercase tracking-widest"
              >
                Continue
              </button>
            </div>
          )}
        </div>
      </div>

      {/* sticky action dock — stays reachable without scrolling past the log,
          and content-sized (no fixed h-24) so it never crowds text on narrow screens */}
      {!endPhase && battle.phase !== 'force_switch' && (
        <div className="shrink-0 border-t-2 border-retro-green/40 bg-retro-dark p-3 sm:p-4 relative box-glow">
          {menuState === 'main' && (
            <div className="grid grid-cols-4 gap-2 sm:gap-4">
              <button
                disabled={isLocked}
                onClick={() => { sfx.menuMove(); setMenuState('fight'); }}
                className="border-2 border-retro-green/50 bezel active:bezel-inverted hover:bg-retro-green hover:text-retro-bg transition-colors flex flex-col items-center justify-center gap-1 py-3 uppercase tracking-tight sm:tracking-wide text-xs sm:text-base group disabled:opacity-30 disabled:pointer-events-none"
              >
                <Swords size={18} className="group-hover:animate-bounce" />
                <span className="truncate w-full text-center">{pending ? '...' : 'Fight'}</span>
              </button>
              <button
                disabled={isLocked}
                onClick={() => { sfx.menuMove(); setMenuState('bag'); }}
                className="border-2 border-retro-green/50 bezel active:bezel-inverted hover:bg-retro-green hover:text-retro-bg transition-colors flex flex-col items-center justify-center gap-1 py-3 uppercase tracking-tight sm:tracking-wide text-xs sm:text-base group disabled:opacity-30 disabled:pointer-events-none"
              >
                <Backpack size={18} />
                <span className="truncate w-full text-center">Bag</span>
              </button>
              <button
                disabled={isLocked || benchable.length === 0}
                onClick={() => { sfx.menuMove(); setMenuState('switch'); }}
                className="border-2 border-retro-green/50 bezel active:bezel-inverted hover:bg-retro-green hover:text-retro-bg transition-colors flex flex-col items-center justify-center gap-1 py-3 uppercase tracking-tight sm:tracking-wide text-xs sm:text-base group disabled:opacity-30 disabled:pointer-events-none"
              >
                <Repeat size={18} />
                <span className="truncate w-full text-center">Switch</span>
              </button>
              <button
                disabled={isLocked}
                onClick={handleFlee}
                className="border-2 border-retro-green/50 bezel active:bezel-inverted hover:bg-retro-green hover:text-retro-bg transition-colors flex flex-col items-center justify-center gap-1 py-3 uppercase tracking-tight sm:tracking-wide text-xs sm:text-base group disabled:opacity-30 disabled:pointer-events-none"
              >
                <Footprints size={18} />
                <span className="truncate w-full text-center">Run</span>
              </button>
            </div>
          )}

          {menuState === 'fight' && (
            <div className="max-h-[40vh] overflow-y-auto custom-scrollbar">
              <BackRow onBack={() => { sfx.menuBack(); setMenuState('main'); }} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                {active.moves.map((move) => (
                  <button
                    key={move.id}
                    disabled={move.pp <= 0 || pending}
                    onClick={() => handleMove(move.id)}
                    className="border-2 border-retro-green/50 hover:bg-retro-green hover:text-retro-bg transition-colors flex justify-between items-center gap-2 px-3 sm:px-6 py-3 uppercase tracking-tight sm:tracking-wide text-sm sm:text-lg group disabled:opacity-30 disabled:pointer-events-none min-w-0"
                  >
                    <span className="truncate">{move.name}</span>
                    <span className="text-xs sm:text-sm opacity-70 group-hover:text-retro-bg group-hover:opacity-100 shrink-0">
                      {isServerBattle ? move.type.toUpperCase() : `${move.pp}/${move.maxPp}`}
                    </span>
                  </button>
                ))}
                {Array.from({ length: Math.max(0, 4 - active.moves.length) }).map((_, idx) => (
                  <button
                    key={`empty-${idx}`}
                    disabled
                    className="border-2 border-retro-green/20 text-retro-green/30 uppercase tracking-wide text-sm sm:text-lg flex items-center px-3 sm:px-6 py-3"
                  >
                    ---
                  </button>
                ))}
              </div>
            </div>
          )}

          {menuState === 'bag' && (
            <div className="max-h-[40vh] overflow-y-auto custom-scrollbar">
              <BackRow onBack={() => { sfx.menuBack(); setMenuState('main'); }} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-2">
                  <p className="text-xs uppercase opacity-60 flex items-center gap-1"><Target size={12} /> Capture</p>
                  {BALL_ITEMS.map((item) => (
                    <button
                      key={item}
                      disabled={state.inventory[item] <= 0 || pending}
                      onClick={() => handleCatch(item)}
                      className="w-full border-2 border-retro-green/50 px-3 py-2 flex justify-between items-center gap-2 hover:bg-retro-green hover:text-retro-bg uppercase text-xs sm:text-sm disabled:opacity-30 disabled:pointer-events-none min-w-0"
                    >
                      <span className="truncate">{item}</span>
                      <span className="opacity-70 shrink-0">x{state.inventory[item]}</span>
                    </button>
                  ))}
                </div>
                <div className="space-y-2">
                  <p className="text-xs uppercase opacity-60">Restore</p>
                  {HEAL_ITEMS.map((item) => (
                    <button
                      key={item}
                      disabled={state.inventory[item] <= 0 || pending}
                      onClick={() => handleHeal(item)}
                      className="w-full border-2 border-retro-green/50 px-3 py-2 flex justify-between items-center gap-2 hover:bg-retro-green hover:text-retro-bg uppercase text-xs sm:text-sm disabled:opacity-30 disabled:pointer-events-none min-w-0"
                    >
                      <span className="truncate">{item}</span>
                      <span className="opacity-70 shrink-0">x{state.inventory[item]}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {menuState === 'switch' && (
            <div className="max-h-[40vh] overflow-y-auto custom-scrollbar">
              <BackRow onBack={() => { sfx.menuBack(); setMenuState('main'); }} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {benchable.map((m) => (
                  <button
                    key={m.uid}
                    onClick={() => handleSwitch(m.uid, false)}
                    className="border-2 border-retro-green/50 px-4 py-3 hover:bg-retro-green hover:text-retro-bg uppercase tracking-wide text-left text-sm min-w-0"
                  >
                    <span className="truncate block">{m.name}</span>
                    <span className="opacity-70 text-xs">Lv.{m.level} — {m.hp}/{m.maxHp} HP</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
