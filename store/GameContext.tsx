"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useReducer, useState } from 'react';
import { GameState, BallType, ItemType } from '@/lib/types';
import { rootReducer, Action } from './reducer';
import { spawnMonster } from '@/lib/battleEngine';
import { DEFAULT_INVENTORY } from '@/lib/gameData';
import { loadSave, writeSave } from '@/lib/storage';
import { setSoundEnabled, sfx } from '@/lib/sound';
import { getOrCreateGuestUserId } from '@/lib/guestId';
import * as api from '@/lib/apiClient';
import { mapServerPokemon, mapServerInventory, serverLogToEntries, ApiError } from '@/lib/apiClient';

function defaultInitialState(): GameState {
  return {
    trainerName: 'OPERATOR',
    currency: 300,
    party: [
      spawnMonster('charmander', 12),
      spawnMonster('squirtle', 14),
    ],
    inventory: { ...DEFAULT_INVENTORY },
    pokedex: {},
    settings: { soundOn: true, theme: 'weathered' },
    battle: null,
    // Real value (or 0 during SSR) — see lib/guestId.ts for why this exists.
    guestUserId: getOrCreateGuestUserId(),
    hasReconciledServer: false,
  };
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ApiError has a status only when the server actually responded (and
// rejected the request for a real reason — insufficient coins, no balls
// left, etc). No status means the request never reached the server at all.
// Only the second case should ever fall back to local behavior — falling
// back after a genuine rejection would silently let the player bypass
// whatever check just correctly said no.
function isNetworkFailure(err: unknown): boolean {
  return !(err instanceof ApiError) || err.status === undefined;
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export interface GameActions {
  scanArea: () => Promise<void>;
  playerMove: (moveId: string) => Promise<void>;
  catchAttempt: (ballType: BallType) => Promise<void>;
  flee: () => Promise<void>;
  switchActive: (uid: string, free?: boolean) => Promise<void>;
  useItem: (item: 'potion' | 'superpotion') => Promise<void>;
  buyItem: (item: ItemType) => Promise<{ success: boolean; message?: string }>;
  healMonster: (uid: string, item: 'potion' | 'superpotion') => Promise<{ success: boolean; message?: string }>;
}

interface GameContextValue {
  state: GameState;
  dispatch: React.Dispatch<Action>;
  actions: GameActions;
  /** true once api/index.py answers a health check — false means local mock engine */
  serverAvailable: boolean;
}

const GameContext = createContext<GameContextValue | null>(null);

export function GameProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(rootReducer, undefined, defaultInitialState);
  const hydrated = useRef(false);
  const [serverAvailable, setServerAvailable] = useState(false);

  // ref mirrors state so async actions don't close over stale values
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const saved = loadSave<GameState>();
    if (saved) dispatch({ type: 'HYDRATE', state: saved });
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    writeSave(state);
  }, [state]);

  useEffect(() => {
    setSoundEnabled(state.settings.soundOn);
  }, [state.settings.soundOn]);

  async function reconcileWithServer() {
    if (stateRef.current.hasReconciledServer) return;
    try {
      const roster = await api.getRoster(stateRef.current.guestUserId);
      const party = roster.team.map(mapServerPokemon);
      if (party.length === 0) return; // nothing to reconcile onto yet
      dispatch({
        type: 'SERVER_SYNC',
        patch: {
          party,
          currency: roster.coins,
          inventory: mapServerInventory(roster.pokeballs, roster.inventory),
          hasReconciledServer: true,
        },
      });
    } catch (err) {
      console.warn('[api] initial roster reconciliation failed:', err);
    }
  }

  // polls instead of checking once — a backend that comes up a few seconds
  // after the app loads would otherwise leave the session stuck on the
  // local engine forever. reconciliation fires once, the first time this
  // flips from unavailable to available ᓚ₍⑅^..^₎♡
  useEffect(() => {
    let cancelled = false;

    async function check() {
      const ok = await api.checkHealth();
      if (cancelled) return;
      setServerAvailable((was) => {
        if (ok && !was) reconcileWithServer();
        return ok;
      });
    }

    check();
    const interval = setInterval(check, 20000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  function appendBattleLog(text: string) {
    const battle = stateRef.current.battle;
    if (!battle) return;
    dispatch({
      type: 'SERVER_SYNC',
      patch: { battle: { ...battle, log: [...battle.log, ...serverLogToEntries([text])] } },
    });
  }

  const scanArea = useCallback(async () => {
    const s = stateRef.current;

    if (serverAvailable) {
      try {
        const res = await api.startBattle(s.guestUserId, s.trainerName);
        const playerMon = mapServerPokemon(res.player_pokemon);
        const enemyMon = mapServerPokemon(res.wild_pokemon);
        const fresh = stateRef.current;
        const alreadyInParty = fresh.party.some((m) => m.uid === playerMon.uid);
        const party = alreadyInParty
          ? fresh.party.map((m) => (m.uid === playerMon.uid ? playerMon : m))
          : [playerMon, ...fresh.party];

        sfx.menuSelect();
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            party,
            battle: {
              playerUid: playerMon.uid,
              enemy: enemyMon,
              phase: 'player_choice',
              log: serverLogToEntries(res.log),
              awaitingEnemyMove: false,
              serverBattleId: res.battle_id,
            },
          },
        });
        return;
      } catch (err) {
        console.warn('[api] startBattle failed:', err);
        if (!isNetworkFailure(err)) {
          // server responded and said no (e.g. whole team fainted) — that's
          // still true locally too, showing a local battle would be wrong
          return;
        }
      }
    }

    // Local fallback — only reached when the server was unreachable, never
    // after a real rejection from it.
    const alive = s.party.some((m) => m.hp > 0);
    if (!alive) return;
    sfx.menuSelect();
    dispatch({ type: 'START_BATTLE' });
  }, [serverAvailable]);

  const playerMove = useCallback(async (moveId: string) => {
    const s = stateRef.current;
    const battleId = s.battle?.serverBattleId;

    if (battleId) {
      try {
        const res = await api.sendMove(battleId, moveId);
        await sleep(450); // server resolves both turns in one call — keep a beat of pacing
        const playerMon = mapServerPokemon(res.player_pokemon);
        const enemyMon = mapServerPokemon(res.wild_pokemon);
        const fresh = stateRef.current;
        const party = fresh.party.map((m) => (m.uid === playerMon.uid ? playerMon : m));
        const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries(res.log)];
        const phase = res.is_finished ? (res.winner === 'player' ? 'victory' : 'defeat') : 'player_choice';

        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            party,
            currency: fresh.currency + (res.coins_gained ?? 0),
            battle: fresh.battle ? { ...fresh.battle, enemy: enemyMon, phase, log: newLog, awaitingEnemyMove: false } : null,
          },
        });
      } catch (err) {
        console.warn('[api] sendMove failed:', err);
        appendBattleLog(errorMessage(err, "Connection hiccup — that move didn't go through."));
      }
      return; // this battle is server-authoritative — never fall back mid-fight
    }

    dispatch({ type: 'PLAYER_MOVE', moveId });
  }, []);

  const catchAttempt = useCallback(async (ballType: BallType) => {
    const s = stateRef.current;
    const battleId = s.battle?.serverBattleId;

    if (battleId) {
      try {
        const res = await api.attemptCatch(battleId, ballType);
        const fresh = stateRef.current;
        const enemyName = fresh.battle?.enemy.name ?? 'It';
        const text = res.will_catch ? `Gotcha! ${enemyName} was caught!` : `${enemyName} broke free!`;
        const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries([text])];
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            inventory: { ...fresh.inventory, [ballType]: res.remaining_balls },
            battle: fresh.battle
              ? { ...fresh.battle, phase: res.will_catch ? 'caught' : 'player_choice', log: newLog }
              : null,
          },
        });
      } catch (err) {
        console.warn('[api] attemptCatch failed:', err);
        appendBattleLog(errorMessage(err, "Couldn't attempt that catch — try again."));
      }
      return;
    }

    dispatch({ type: 'CATCH_ATTEMPT', ball: ballType });
  }, []);

  const flee = useCallback(async () => {
    const s = stateRef.current;
    const battleId = s.battle?.serverBattleId;

    if (battleId) {
      try {
        const res = await api.flee(battleId);
        const fresh = stateRef.current;
        const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries([res.success ? 'Got away safely!' : "Couldn't escape!"])];
        dispatch({
          type: 'SERVER_SYNC',
          patch: { battle: fresh.battle ? { ...fresh.battle, phase: res.success ? 'fled' : 'player_choice', log: newLog } : null },
        });
      } catch (err) {
        console.warn('[api] flee failed:', err);
        appendBattleLog(errorMessage(err, 'Connection hiccup — try again.'));
      }
      return;
    }

    dispatch({ type: 'FLEE' });
  }, []);

  const switchActive = useCallback(async (uid: string, free = false) => {
    const s = stateRef.current;
    const battleId = s.battle?.serverBattleId;

    if (battleId) {
      try {
        const res = await api.switchPokemon(battleId, uid);
        const playerMon = mapServerPokemon(res.player_pokemon);
        const enemyMon = mapServerPokemon(res.wild_pokemon);
        const fresh = stateRef.current;
        const party = fresh.party.map((m) => (m.uid === playerMon.uid ? playerMon : m));
        const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries(res.log)];
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            party,
            battle: fresh.battle ? { ...fresh.battle, playerUid: playerMon.uid, enemy: enemyMon, log: newLog } : null,
          },
        });
      } catch (err) {
        console.warn('[api] switch failed:', err);
        appendBattleLog(errorMessage(err, "Couldn't switch right now."));
      }
      return;
    }

    sfx.menuSelect();
    dispatch({ type: 'SWITCH_ACTIVE', uid, free });
  }, []);

  const useItem = useCallback(async (item: 'potion' | 'superpotion') => {
    const s = stateRef.current;
    const battleId = s.battle?.serverBattleId;
    const active = s.party.find((m) => m.uid === s.battle?.playerUid);

    if (battleId) {
      try {
        const res = await api.useItem(battleId, item);
        const playerMon = mapServerPokemon(res.player_pokemon);
        const fresh = stateRef.current;
        const party = fresh.party.map((m) => (m.uid === playerMon.uid ? playerMon : m));
        const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries(res.log)];
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            party,
            inventory: { ...fresh.inventory, [item]: res.remaining },
            battle: fresh.battle ? { ...fresh.battle, log: newLog } : null,
          },
        });
      } catch (err) {
        console.warn('[api] useItem failed:', err);
        appendBattleLog(errorMessage(err, `Couldn't use that ${item} right now.`));
      }
      return;
    }

    if (!active) return;
    dispatch({ type: 'USE_ITEM_IN_BATTLE', item, targetUid: active.uid });
  }, []);

  const buyItem = useCallback(async (item: ItemType) => {
    const s = stateRef.current;

    if (serverAvailable) {
      try {
        const res = await api.buyItem(s.guestUserId, item, 1);
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            currency: res.coins,
            inventory: mapServerInventory(res.pokeballs, res.inventory),
          },
        });
        sfx.coin();
        return { success: true };
      } catch (err) {
        console.warn('[api] buyItem failed:', err);
        if (!isNetworkFailure(err)) {
          // server responded and said no (not enough coins, unknown item) —
          // a local purchase would silently bypass that rejection
          sfx.error();
          return { success: false, message: errorMessage(err, "That purchase didn't go through.") };
        }
      }
    }

    dispatch({ type: 'BUY_ITEM', item });
    return { success: true };
  }, [serverAvailable]);

  const healMonster = useCallback(async (uid: string, item: 'potion' | 'superpotion') => {
    const s = stateRef.current;

    if (serverAvailable) {
      try {
        const res = await api.healParty(s.guestUserId, uid, item);
        const healed = mapServerPokemon(res.player_pokemon);
        const fresh = stateRef.current;
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            party: fresh.party.map((m) => (m.uid === healed.uid ? healed : m)),
            inventory: { ...fresh.inventory, [item]: res.remaining },
          },
        });
        return { success: true };
      } catch (err) {
        console.warn('[api] healParty failed:', err);
        if (!isNetworkFailure(err)) {
          // server responded and said no (already full HP, no items left) —
          // a local heal would silently bypass that rejection
          sfx.error();
          return { success: false, message: errorMessage(err, "Couldn't heal that Pokemon.") };
        }
      }
    }

    dispatch({ type: 'HEAL_PARTY_MEMBER', uid, item });
    return { success: true };
  }, [serverAvailable]);

  const actions: GameActions = { scanArea, playerMove, catchAttempt, flee, switchActive, useItem, buyItem, healMonster };

  return (
    <GameContext.Provider value={{ state, dispatch, actions, serverAvailable }}>
      {children}
    </GameContext.Provider>
  );
}

export function useGame(): GameContextValue {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within a GameProvider');
  return ctx;
}
