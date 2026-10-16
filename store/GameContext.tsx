"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useReducer, useState } from 'react';
import { GameState, BallType, ItemType, ExtraItemId, Monster, BattleRewards, GymBattleInfo, JourneyState, StoryBattleInfo, EvolutionPending, PokedexEntry } from '@/lib/types';
import { rootReducer, Action } from './reducer';
import { spawnMonster } from '@/lib/battleEngine';
import { DEFAULT_INVENTORY, EMPTY_EXTRAS } from '@/lib/gameData';
import { loadSave, writeSave, clearSave } from '@/lib/storage';
import { setSoundEnabled, sfx } from '@/lib/sound';
import { getOrCreateGuestUserId } from '@/lib/guestId';
import { AuthSession, loadAuth, saveAuth, clearAuth } from '@/lib/auth';
import { applyPrefs, loadPrefs } from '@/lib/prefs';
import { getTelegramInitData, readyTelegramApp } from '@/lib/telegramWebApp';
import * as api from '@/lib/apiClient';
import { mapServerPokemon, mapServerInventory, mapServerExtras, serverLogToEntries, ApiError } from '@/lib/apiClient';

function defaultInitialState(): GameState {
  return {
    trainerName: 'OPERATOR',
    currency: 300,
    party: [
      spawnMonster('charmander', 12),
      spawnMonster('squirtle', 14),
    ],
    inventory: { ...DEFAULT_INVENTORY },
    extras: { ...EMPTY_EXTRAS },
    pokedex: {},
    settings: { soundOn: true, theme: 'weathered' },
    battle: null,
    // Real value (or 0 during SSR) — see lib/guestId.ts for why this exists.
    guestUserId: getOrCreateGuestUserId(),
    hasReconciledServer: false,
  };
}

/** A clean slate for a logged-in account (or logged-out): no party until the server says otherwise. */
function blankStateFor(session: AuthSession | null): GameState {
  const base = defaultInitialState();
  return {
    ...base,
    trainerName: session?.username ?? 'TRAINER',
    currency: 0,
    party: [],
    pokedex: {},
    battle: null,
    guestUserId: session?.userId ?? 0,
    hasReconciledServer: false,
  };
}

function pokedexFromServer(p: { seen: string[]; caught: string[] }): Record<string, PokedexEntry> {
  const out: Record<string, PokedexEntry> = {};
  for (const id of p.seen) out[id] = { speciesId: id, seen: true, caught: false };
  for (const id of p.caught) out[id] = { speciesId: id, seen: true, caught: true };
  return out;
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
  /** `ok:false` = no battle was started (show `message`, don't navigate to the battle screen) */
  scanArea: (target?: { species: string; level: number; token?: string }, routeId?: string) => Promise<{ ok: boolean; message?: string }>;
  startBoss: () => Promise<{ success: boolean; message?: string }>;
  startGym: () => Promise<{ success: boolean; message?: string }>;
  /** story: walk to a connected location */
  journeyTravel: (to: string) => Promise<{ success: boolean; message?: string }>;
  journeyHeal: () => Promise<{ success: boolean; message?: string }>;
  startTrainer: (trainerId: string) => Promise<{ success: boolean; message?: string }>;
  refreshJourney: () => Promise<void>;
  buyGymItem: (itemId: string) => Promise<{ success: boolean; message?: string }>;
  toggleExpAll: () => void;
  useRareCandy: (uid: string) => Promise<{ success: boolean; message?: string }>;
  playerMove: (moveId: string) => Promise<void>;
  catchAttempt: (ballType: BallType) => Promise<void>;
  flee: () => Promise<void>;
  switchActive: (uid: string, free?: boolean) => Promise<void>;
  useItem: (item: 'potion' | 'superpotion') => Promise<void>;
  buyItem: (item: ItemType | ExtraItemId) => Promise<{ success: boolean; message?: string }>;
  healMonster: (uid: string, item: 'potion' | 'superpotion') => Promise<{ success: boolean; message?: string }>;
  /** `ok:false` = the request FAILED (retry); `ok:true` with no monsters = the area really is empty */
  scoutArea: (routeId?: string) => Promise<{ ok: true; monsters: Monster[] } | { ok: false; message: string }>;
  /** store a fresh login (from the login screen) and load that player's roster */
  login: (session: AuthSession, needsStarter: boolean) => Promise<void>;
  logout: () => void;
  /** re-read the roster from the server (after choosing a starter, etc.) */
  refreshRoster: () => Promise<void>;
  /** skip accounts and play the local demo (no saving to the server) */
  playOffline: () => void;
}

export type AuthState =
  | { status: 'loading'; session: null }
  | { status: 'out'; session: null }
  | { status: 'in'; session: AuthSession }
  | { status: 'offline'; session: null };

interface GameContextValue {
  state: GameState;
  dispatch: React.Dispatch<Action>;
  actions: GameActions;
  /** true when logged in AND the backend answers — false means the local demo engine */
  serverAvailable: boolean;
  /** the backend answers health checks (regardless of login) */
  serverReachable: boolean;
  /** at least one health check has finished (so the UI can tell "waking up" from "never tried") */
  serverChecked: boolean;
  auth: AuthState;
  /** logged in, but this account has no Pokémon yet — show avatar + region + starter selection */
  needsStarter: boolean;
  /** where the player is on their journey (null until loaded / when offline) */
  journey: JourneyState | null;
  /** trainer avatar id (pixel sprite) */
  avatar: string | null;
  /** admin-set image overrides for scenes (slot -> url) */
  assets: Record<string, string>;
  /** Pokémon that can evolve right now (from battle XP, Rare Candy…) — the evolution cutscene works through this */
  evolutionQueue: EvolutionPending[];
  dismissEvolution: (id?: string) => void;
  /** the logged-in account is an admin (checked server-side; this only decides whether to show the panel) */
  isAdmin: boolean;
  /** true only if the backend is ALSO backed by Supabase, not volatile in-memory storage */
  serverPersistent: boolean;
}

const GameContext = createContext<GameContextValue | null>(null);

export function GameProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(rootReducer, undefined, defaultInitialState);
  const hydrated = useRef(false);
  const [serverReachable, setServerReachable] = useState(false);
  const [serverChecked, setServerChecked] = useState(false);
  const [serverPersistent, setServerPersistent] = useState(false);
  const [auth, setAuth] = useState<AuthState>({ status: 'loading', session: null });
  const [needsStarter, setNeedsStarter] = useState(false);
  const [journey, setJourney] = useState<JourneyState | null>(null);
  const [avatar, setAvatar] = useState<string | null>(null);
  const [assets, setAssets] = useState<Record<string, string>>({});
  const [isAdmin, setIsAdmin] = useState(false);
  const [evolutionQueue, setEvolutionQueue] = useState<EvolutionPending[]>([]);
  // every action below talks to the server only when there's a logged-in player AND a reachable backend
  const serverAvailable = serverReachable && auth.status === 'in';
  const authRef = useRef<AuthState>(auth);
  authRef.current = auth;

  // ref mirrors state so async actions don't close over stale values
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    applyPrefs(loadPrefs());
    const saved = loadSave<GameState>();
    const session = loadAuth();
    if (saved) dispatch({ type: 'HYDRATE', state: saved });
    if (session) {
      // a different account than the one this browser last played → don't show their party/coins
      if (!saved || saved.guestUserId !== session.userId) {
        dispatch({ type: 'HYDRATE', state: blankStateFor(session) });
      } else {
        dispatch({ type: 'SERVER_SYNC', patch: { trainerName: session.username } });
      }
      setAuth({ status: 'in', session });
    } else {
      setAuth({ status: 'out', session: null });
    }
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    writeSave(state);
  }, [state]);

  useEffect(() => {
    setSoundEnabled(state.settings.soundOn);
  }, [state.settings.soundOn]);

  // Pull this account's roster from the server. An EMPTY roster is real information now
  // (a new account that hasn't picked a starter yet), not "nothing to do".
  async function syncRoster() {
    const session = authRef.current.session;
    if (!session) return;
    try {
      const roster = await api.getRoster(session.userId);
      const party = roster.team.map(mapServerPokemon);
      setNeedsStarter(!!roster.needs_starter);
      setAvatar(roster.avatar ?? null);
      api.adminMe().then((r) => setIsAdmin(!!r.is_admin)).catch(() => setIsAdmin(false));
      api.getAssets().then((r) => setAssets(r.assets ?? {})).catch(() => { /* optional */ });
      if (!roster.needs_starter) {
        api.journeyState(session.userId).then(setJourney).catch(() => { /* optional garnish */ });
      } else {
        setJourney(null);
      }
      dispatch({
        type: 'SERVER_SYNC',
        patch: {
          party,
          trainerName: roster.username || session.username,
          currency: roster.coins,
          inventory: mapServerInventory(roster.pokeballs, roster.inventory),
          extras: mapServerExtras(roster.inventory),
          ...(roster.pokedex ? { pokedex: pokedexFromServer(roster.pokedex) } : {}),
          hasReconciledServer: true,
        },
      });
    } catch (err) {
      console.warn('[api] roster sync failed:', err);
    }
  }

  // The health check polls (instead of checking once) so a backend that wakes up after the app
  // loaded is picked up. Free hosts sleep when idle: the first check after that can take ~50s, so
  // it's patient, and a single failed poll doesn't flip a working connection to "offline".
  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    let failures = 0;
    let wasReachable = false;

    async function check() {
      if (inFlight) return;
      inFlight = true;
      const status = await api.checkHealth();
      inFlight = false;
      if (cancelled) return;
      setServerPersistent(status.persistent);
      setServerChecked(true);

      if (status.reachable) {
        failures = 0;
        setServerReachable(true);
        if (!wasReachable) {
          wasReachable = true;
          // first contact (or back after a drop): validate the saved login and load the roster
          if (authRef.current.session) {
            api.authMe()
              .then((me) => {
                if (cancelled) return;
                setNeedsStarter(me.needs_starter);
                return syncRoster();
              })
              .catch((err) => {
                if (err instanceof ApiError && err.status === 401) {
                  clearAuth();
                  setAuth({ status: 'out', session: null });
                } else {
                  return syncRoster();
                }
              });
          }
        }
      } else {
        failures += 1;
        if (failures >= 2 || !wasReachable) {
          wasReachable = false;
          setServerReachable(false);
        }
      }
    }

    check();
    const interval = setInterval(check, 20000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function appendBattleLog(text: string) {
    const battle = stateRef.current.battle;
    if (!battle) return;
    dispatch({
      type: 'SERVER_SYNC',
      patch: { battle: { ...battle, log: [...battle.log, ...serverLogToEntries([text])] } },
    });
  }

  const scanArea = useCallback(async (target?: { species: string; level: number; token?: string }, routeId?: string) => {
    const s = stateRef.current;

    if (serverAvailable) {
      try {
        const res = await api.startBattle(s.guestUserId, s.trainerName, target, routeId);
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
        return { ok: true };
      } catch (err) {
        console.warn('[api] startBattle failed:', err);
        if (!isNetworkFailure(err)) {
          // server responded and said no (e.g. whole team fainted, encounter already used) — that's
          // still true locally too, showing a local battle would be wrong
          return { ok: false, message: err instanceof Error ? err.message : 'The server refused that battle.' };
        }
      }
    }

    // A logged-in player never silently drops into the offline engine (two different rulesets = two different games).
    if (authRef.current.status === 'in') {
      sfx.error();
      return { ok: false, message: "Couldn't reach the server — try again." };
    }
    // Local fallback — only the explicit offline demo gets here.
    const alive = s.party.some((m) => m.hp > 0);
    if (!alive) return { ok: false, message: 'Your whole team has fainted.' };
    sfx.menuSelect();
    dispatch({ type: 'START_BATTLE' });
    return { ok: true };
  }, [serverAvailable]);

  /** Everything that follows a resolved turn from the server (a move, or any action that gave the opponent a turn:
   *  switching, using an item, failing to run). One handler so a fainted Pokémon / finished fight looks the same. */
  const applyTurnResult = useCallback(async (res: api.BattleMoveResponse) => {
    await sleep(450); // server resolves both turns in one call — keep a beat of pacing
    const playerMon = mapServerPokemon(res.player_pokemon);
    const enemyMon = mapServerPokemon(res.wild_pokemon);
    const fresh = stateRef.current;
    // on a win the server sends the whole (XP-updated) team; otherwise only the fighter changed
    const party = res.team
      ? res.team.map(mapServerPokemon)
      : fresh.party.map((m) => (m.uid === playerMon.uid ? playerMon : m));
    const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries(res.log)];
    const won = res.is_finished && res.winner === 'player';
    if (res.evolution_pending?.length) {
      setEvolutionQueue((q) => [...q, ...res.evolution_pending!.filter((e) => !q.some((x) => x.id === e.id))]);
    }
    const phase = res.is_finished ? (won ? 'victory' : 'defeat') : 'player_choice';

    // Battle Gym outcome rides on the same battle object
    let gymInfo: GymBattleInfo | undefined = fresh.battle?.gym;
    if (res.is_finished && gymInfo && res.gym) {
      const g = res.gym;
      gymInfo = {
        ...gymInfo,
        outcome: {
          won,
          bp: g.bp ?? 0,
          coins: g.coins ?? 0,
          badge: g.badge ?? null,
          runOver: !!g.run_over,
          floorsCleared: g.floors_cleared ?? g.floor_cleared ?? 0,
          best: g.best ?? 0,
          remaining: g.remaining ?? 0,
        },
      };
      newLog.push(...serverLogToEntries(
        won
          ? [`Floor ${g.floor_cleared} cleared! +${g.bp} BP`, ...(g.badge ? [`🏅 ${g.badge} earned!`] : [])]
          : g.run_over
            ? [`Run over — you cleared ${g.floors_cleared ?? 0} floors.`]
            : [`Your Pokémon fainted. ${g.remaining ?? 0} left — send in the next one!`]
      ));
    }

    // Story trainer: a mid-battle advance just swaps the opponent; a finish carries the outcome
    let storyInfo: StoryBattleInfo | undefined = fresh.battle?.story;
    if (storyInfo && res.story) {
      const st = res.story;
      if (st.advanced) {
        storyInfo = { ...storyInfo, idx: st.idx ?? storyInfo.idx, size: st.size ?? storyInfo.size };
        newLog.push(...serverLogToEntries([`+${res.xp_gained ?? 0} XP`]));
      } else if (res.is_finished) {
        storyInfo = {
          ...storyInfo,
          outcome: {
            won: !!st.won,
            coins: st.coins ?? 0,
            badge: st.badge ?? null,
            win: st.win,
            complete: !!st.complete,
            unlockedRegion: st.unlocked_region ?? null,
            blackout: !!st.blackout,
            remaining: st.remaining ?? 0,
            location: st.location,
            items: st.items,
          },
        };
        newLog.push(...serverLogToEntries(
          st.won
            ? [`+${res.xp_gained ?? 0} XP`, ...(st.badge ? [`🏅 ${st.badge} earned!`] : [])]
            : st.blackout
              ? [`You blacked out and woke up in ${st.location}.`]
              : [`Your Pokémon fainted. ${st.remaining ?? 0} left — send in the next one!`]
        ));
      }
    }

    let rewards: BattleRewards | undefined;
    if (won && !gymInfo && !storyInfo) {
      rewards = {
        xp: res.xp_gained ?? 0,
        coins: res.coins_gained ?? 0,
        items: res.boss?.items ?? [],
        expAll: {
          used: !!res.exp_all?.used,
          perPokemon: res.exp_all?.per_pokemon ?? res.xp_gained ?? 0,
          count: res.exp_all?.pokemon_count ?? 1,
          levelUps: res.exp_all?.level_ups ?? [],
        },
        boss: !!res.boss?.defeated,
        flawless: !!res.boss?.flawless,
      };
      newLog.push(...serverLogToEntries([
        `+${rewards.xp} XP${rewards.expAll.used ? ` (split ${rewards.expAll.count} ways by EXP ALL)` : ''}`,
        ...rewards.expAll.levelUps,
      ]));
    }

    dispatch({
      type: 'SERVER_SYNC',
      patch: {
        party,
        currency: fresh.currency + (res.coins_gained ?? 0),
        ...(res.inventory && res.pokeballs
          ? { inventory: mapServerInventory(res.pokeballs, res.inventory), extras: mapServerExtras(res.inventory) }
          : {}),
        battle: fresh.battle
          ? { ...fresh.battle, enemy: enemyMon, phase, log: newLog, awaitingEnemyMove: false, ...(rewards ? { rewards } : {}), ...(gymInfo ? { gym: gymInfo } : {}), ...(storyInfo ? { story: storyInfo } : {}) }
          : null,
      },
    });
  }, []);

  const playerMove = useCallback(async (moveId: string) => {
    const s = stateRef.current;
    const battleId = s.battle?.serverBattleId;

    if (battleId) {
      try {
        const res = await api.sendMove(battleId, moveId, !!s.battle?.useExpAll);
        await applyTurnResult(res);
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
            ...(res.pokedex ? { pokedex: pokedexFromServer(res.pokedex) } : {}),
            battle: fresh.battle
              ? { ...fresh.battle, phase: res.will_catch ? 'caught' : 'player_choice', log: newLog }
              : null,
          },
        });
        if (res.will_catch) await syncRoster();      // the caught Pokémon, storage box and Pokédex come from the server
        else if (res.turn) await applyTurnResult(res.turn);   // it broke free — and the wild Pokémon got its move
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
        if (!res.success && res.turn) { await applyTurnResult(res.turn); return; }   // failing to run costs the turn
        const fresh = stateRef.current;
        const gymForfeit = !!fresh.battle?.gym && res.success;
        const newLog = [...(fresh.battle?.log ?? []), ...serverLogToEntries([
          gymForfeit ? `You left the gym. Floors cleared: ${res.gym?.floors_cleared ?? 0}.` : res.success ? 'Got away safely!' : (res.message ?? "Couldn't escape!"),
        ])];
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            battle: fresh.battle
              ? {
                  ...fresh.battle,
                  phase: res.success ? 'fled' : 'player_choice',
                  log: newLog,
                  ...(gymForfeit && fresh.battle.gym
                    ? { gym: { ...fresh.battle.gym, outcome: { won: false, bp: 0, coins: 0, runOver: true, floorsCleared: res.gym?.floors_cleared ?? 0, best: res.gym?.best ?? 0, remaining: 0 } } }
                    : {}),
                }
              : null,
          },
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
        if (res.is_finished) { await applyTurnResult(res); return; }     // the free hit ended the fight
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
        if (res.is_finished) {                                           // the opponent's turn ended the fight
          await applyTurnResult(res);
          dispatch({ type: 'SERVER_SYNC', patch: { inventory: { ...stateRef.current.inventory, [item]: res.remaining } } });
          return;
        }
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

  const buyItem = useCallback(async (item: ItemType | ExtraItemId) => {
    const s = stateRef.current;
    const isExtra = item === 'exp_all' || item === 'rare_candy';

    if (serverAvailable) {
      try {
        const res = await api.buyItem(s.guestUserId, item, 1);
        dispatch({
          type: 'SERVER_SYNC',
          patch: {
            currency: res.coins,
            inventory: mapServerInventory(res.pokeballs, res.inventory),
            extras: mapServerExtras(res.inventory),
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

    if (authRef.current.status === 'in') {
      sfx.error();
      return { success: false, message: "Can't reach the server — try again in a moment." };
    }
    if (isExtra) {
      // EXP All / Rare Candy only exist server-side — never grant them from the offline engine
      sfx.error();
      return { success: false, message: 'This item needs a server connection.' };
    }
    dispatch({ type: 'BUY_ITEM', item: item as ItemType });
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

    if (authRef.current.status === 'in') {
      sfx.error();
      return { success: false, message: "Can't reach the server — try again in a moment." };
    }
    dispatch({ type: 'HEAL_PARTY_MEMBER', uid, item });
    return { success: true };
  }, [serverAvailable]);

  const scoutArea = useCallback(async (routeId?: string) => {
    const s = stateRef.current;
    if (!serverAvailable) return { ok: true as const, monsters: [] as Monster[] };
    try {
      const res = await api.scoutArea(s.guestUserId, routeId);
      return { ok: true as const, monsters: res.candidates.map(mapServerPokemon) };
    } catch (err) {
      console.warn('[api] scoutArea failed:', err);
      return { ok: false as const, message: err instanceof Error ? err.message : "Couldn't reach the server." };
    }
  }, [serverAvailable]);

  const startBoss = useCallback(async () => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'The daily boss needs a server connection.' };
    try {
      const res = await api.startBoss(s.guestUserId, s.trainerName);
      const playerMon = mapServerPokemon(res.player_pokemon);
      const bossMon = mapServerPokemon(res.wild_pokemon);
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
            enemy: bossMon,
            phase: 'player_choice',
            log: serverLogToEntries(res.log),
            awaitingEnemyMove: false,
            serverBattleId: res.battle_id,
            isBoss: true,
          },
        },
      });
      return { success: true };
    } catch (err) {
      console.warn('[api] startBoss failed:', err);
      sfx.error();
      return { success: false, message: errorMessage(err, "Couldn't reach the boss right now.") };
    }
  }, [serverAvailable]);

  const refreshJourney = useCallback(async () => {
    const session = authRef.current.session;
    if (!session) return;
    try {
      setJourney(await api.journeyState(session.userId));
    } catch {
      /* keep whatever we had */
    }
  }, []);

  const journeyTravel = useCallback(async (to: string) => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'Travelling needs a server connection.' };
    try {
      setJourney(await api.journeyTravel(s.guestUserId, to));
      sfx.menuSelect();
      return { success: true };
    } catch (err) {
      sfx.error();
      return { success: false, message: errorMessage(err, "You can't go there yet.") };
    }
  }, [serverAvailable]);

  const journeyHeal = useCallback(async () => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'Healing needs a server connection.' };
    try {
      const res = await api.journeyHeal(s.guestUserId);
      const team = res.team.map(mapServerPokemon);
      const fresh = stateRef.current;
      dispatch({ type: 'SERVER_SYNC', patch: { party: fresh.party.map((m) => team.find((t) => t.uid === m.uid) ?? m) } });
      setJourney(res);
      sfx.coin();
      return { success: true };
    } catch (err) {
      sfx.error();
      return { success: false, message: errorMessage(err, "Couldn't heal here.") };
    }
  }, [serverAvailable]);

  const startTrainer = useCallback(async (trainerId: string) => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'Trainer battles need a server connection.' };
    try {
      const res = await api.journeyTrainerStart(s.guestUserId, s.trainerName, trainerId);
      const playerMon = mapServerPokemon(res.player_pokemon);
      const oppMon = mapServerPokemon(res.wild_pokemon);
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
            enemy: oppMon,
            phase: 'player_choice',
            log: serverLogToEntries(res.log),
            awaitingEnemyMove: false,
            serverBattleId: res.battle_id,
            story: { ...res.story, badge: res.story.badge },
          },
        },
      });
      return { success: true };
    } catch (err) {
      console.warn('[api] startTrainer failed:', err);
      sfx.error();
      return { success: false, message: errorMessage(err, "Couldn't start that battle.") };
    }
  }, [serverAvailable]);

  const startGym = useCallback(async () => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'The Battle Gym needs a server connection.' };
    try {
      const res = await api.gymEnter(s.guestUserId, s.trainerName);
      const playerMon = mapServerPokemon(res.player_pokemon);
      const oppMon = mapServerPokemon(res.wild_pokemon);
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
            enemy: oppMon,
            phase: 'player_choice',
            log: serverLogToEntries(res.log),
            awaitingEnemyMove: false,
            serverBattleId: res.battle_id,
            gym: { floor: res.gym.floor, leader: res.gym.leader, trainer: res.gym.trainer, gym: res.gym.gym },
          },
        },
      });
      return { success: true };
    } catch (err) {
      console.warn('[api] startGym failed:', err);
      sfx.error();
      return { success: false, message: errorMessage(err, "Couldn't enter the gym right now.") };
    }
  }, [serverAvailable]);

  const buyGymItem = useCallback(async (itemId: string) => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'The Gym Shop needs a server connection.' };
    try {
      const res = await api.gymShopBuy(s.guestUserId, itemId, 1);
      dispatch({
        type: 'SERVER_SYNC',
        patch: {
          inventory: mapServerInventory(res.pokeballs, res.inventory),
          extras: mapServerExtras({ ...res.inventory, battle_points: res.bp }),
        },
      });
      sfx.coin();
      return { success: true };
    } catch (err) {
      console.warn('[api] gymShopBuy failed:', err);
      sfx.error();
      return { success: false, message: errorMessage(err, "That purchase didn't go through.") };
    }
  }, [serverAvailable]);

  const toggleExpAll = useCallback(() => {
    const b = stateRef.current.battle;
    if (!b || !b.serverBattleId) return;
    sfx.menuSelect();
    dispatch({ type: 'SERVER_SYNC', patch: { battle: { ...b, useExpAll: !b.useExpAll } } });
  }, []);

  const useRareCandy = useCallback(async (uid: string) => {
    const s = stateRef.current;
    if (!serverAvailable) return { success: false, message: 'Rare Candy needs a server connection.' };
    try {
      const res = await api.useRareCandy(s.guestUserId, uid);
      const grown = mapServerPokemon(res.player_pokemon);
      const pend = res.evolution_pending ?? [];
      if (pend.length) setEvolutionQueue((q) => [...q, ...pend.filter((e) => !q.some((x) => x.id === e.id))]);
      const fresh = stateRef.current;
      dispatch({
        type: 'SERVER_SYNC',
        patch: {
          party: fresh.party.map((m) => (m.uid === grown.uid ? grown : m)),
          extras: { ...fresh.extras, rare_candy: res.remaining },
        },
      });
      sfx.coin();
      return { success: true };
    } catch (err) {
      console.warn('[api] rareCandy failed:', err);
      sfx.error();
      return { success: false, message: errorMessage(err, "Couldn't use that Rare Candy.") };
    }
  }, [serverAvailable]);

  const login = useCallback(async (session: AuthSession, starterNeeded: boolean) => {
    saveAuth(session);
    const same = stateRef.current.guestUserId === session.userId;
    if (!same) dispatch({ type: 'HYDRATE', state: blankStateFor(session) });
    authRef.current = { status: 'in', session };
    setAuth({ status: 'in', session });
    setNeedsStarter(starterNeeded);
    await syncRoster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Inside a Telegram Mini App the identity is Telegram's SIGNED initData (verified by the server), so the same
  // player shows up as in the bot — no password, no random local id.
  useEffect(() => {
    const initData = getTelegramInitData();
    if (!initData) return;
    readyTelegramApp();
    let cancelled = false;
    (async () => {
      try {
        const r = await api.telegramWebApp(initData);
        if (cancelled) return;
        await login({ token: r.token, userId: r.user_id, username: r.username }, r.needs_starter);
      } catch (err) {
        console.warn('[auth] Telegram sign-in failed:', err);     // keep any existing session; the login screen stays available
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    clearSave();
    dispatch({ type: 'HYDRATE', state: blankStateFor(null) });
    setNeedsStarter(false);
    setJourney(null);
    setAvatar(null);
    setIsAdmin(false);
    setAuth({ status: 'out', session: null });
  }, []);

  const dismissEvolution = useCallback((id?: string) => {
    setEvolutionQueue((q) => (id ? q.filter((e) => e.id !== id) : []));
  }, []);

  const refreshRoster = useCallback(async () => {
    await syncRoster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const playOffline = useCallback(() => {
    dispatch({ type: 'HYDRATE', state: defaultInitialState() });
    setNeedsStarter(false);
    setAuth({ status: 'offline', session: null });
  }, []);

  const actions: GameActions = {
    login, logout, refreshRoster, playOffline,
    scanArea, startBoss, startGym, buyGymItem, toggleExpAll,
    journeyTravel, journeyHeal, startTrainer, refreshJourney, useRareCandy, playerMove, catchAttempt, flee,
    switchActive, useItem, buyItem, healMonster, scoutArea,
  };

  return (
    <GameContext.Provider value={{ state, dispatch, actions, serverAvailable, serverReachable, serverChecked, serverPersistent, auth, needsStarter, journey, avatar, assets, isAdmin, evolutionQueue, dismissEvolution }}>
      {children}
    </GameContext.Provider>
  );
}

export function useGame(): GameContextValue {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within a GameProvider');
  return ctx;
}
