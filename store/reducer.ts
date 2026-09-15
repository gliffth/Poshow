import {
  GameState, Monster, ItemType, BallType, LogEntry, BattleState, ThemeName,
} from '@/lib/types';
import {
  resolveMove, attemptCatch, grantXp, xpRewardFor, currencyRewardFor,
  pickWildEncounter, preMoveStatusCheck, applyStatusTick, pickEnemyMove,
  spawnMonster,
} from '@/lib/battleEngine';
import { WILD_POOL, SHOP_ITEMS } from '@/lib/gameData';
import { sfx } from '@/lib/sound';

export type Action =
  | { type: 'START_BATTLE' }
  | { type: 'PLAYER_MOVE'; moveId: string }
  | { type: 'ENEMY_MOVE' }
  | { type: 'CATCH_ATTEMPT'; ball: BallType }
  | { type: 'USE_ITEM_IN_BATTLE'; item: 'potion' | 'superpotion'; targetUid: string }
  | { type: 'SWITCH_ACTIVE'; uid: string; free?: boolean }
  | { type: 'FLEE' }
  | { type: 'END_BATTLE' }
  | { type: 'BUY_ITEM'; item: ItemType }
  | { type: 'TOGGLE_SOUND' }
  | { type: 'SET_THEME'; theme: ThemeName }
  | { type: 'FEED_MONSTER'; uid: string }
  | { type: 'HEAL_PARTY_MEMBER'; uid: string; item: 'potion' | 'superpotion' }
  | { type: 'HYDRATE'; state: GameState }
  | { type: 'DISMISS_BATTLE_RESULT' }
  | { type: 'SERVER_SYNC'; patch: Partial<GameState> };

let logCounter = 0;
function mkLog(text: string): LogEntry {
  logCounter += 1;
  return { id: `log-${Date.now()}-${logCounter}`, text };
}

function pushLogs(battle: BattleState, texts: string[]): BattleState {
  if (texts.length === 0) return battle;
  return { ...battle, log: [...battle.log, ...texts.map(mkLog)] };
}

function getActive(state: GameState): Monster | null {
  if (!state.battle) return null;
  return state.party.find((m) => m.uid === state.battle!.playerUid) ?? null;
}

function replaceParty(party: Monster[], updated: Monster): Monster[] {
  return party.map((m) => (m.uid === updated.uid ? updated : m));
}

function markPokedex(state: GameState, speciesId: string, patch: { seen?: boolean; caught?: boolean }): GameState['pokedex'] {
  const existing = state.pokedex[speciesId] ?? { speciesId, seen: false, caught: false };
  return {
    ...state.pokedex,
    [speciesId]: {
      ...existing,
      seen: existing.seen || !!patch.seen,
      caught: existing.caught || !!patch.caught,
    },
  };
}

export function rootReducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case 'HYDRATE':
      return action.state;

    case 'SERVER_SYNC':
      return { ...state, ...action.patch };

    case 'TOGGLE_SOUND': {
      const soundOn = !state.settings.soundOn;
      return { ...state, settings: { ...state.settings, soundOn } };
    }

    case 'SET_THEME':
      return { ...state, settings: { ...state.settings, theme: action.theme } };

    case 'FEED_MONSTER': {
      const target = state.party.find((m) => m.uid === action.uid);
      if (!target || target.hunger >= target.maxHunger) return state;
      const fed = { ...target, hunger: Math.min(target.maxHunger, target.hunger + 4) };
      return { ...state, party: replaceParty(state.party, fed) };
    }

    case 'HEAL_PARTY_MEMBER': {
      const count = state.inventory[action.item];
      if (!count || count <= 0) return state;
      const target = state.party.find((m) => m.uid === action.uid);
      if (!target || target.hp >= target.maxHp) return state;
      const heal = action.item === 'potion' ? 20 : 50;
      const healed = { ...target, hp: Math.min(target.maxHp, target.hp + heal) };
      sfx.coin();
      return {
        ...state,
        party: replaceParty(state.party, healed),
        inventory: { ...state.inventory, [action.item]: count - 1 },
      };
    }

    case 'BUY_ITEM': {
      const item = SHOP_ITEMS.find((i) => i.id === action.item);
      if (!item || state.currency < item.price) return state;
      return {
        ...state,
        currency: state.currency - item.price,
        inventory: { ...state.inventory, [action.item]: state.inventory[action.item] + 1 },
      };
    }

    case 'START_BATTLE': {
      const firstAlive = state.party.find((m) => m.hp > 0);
      if (!firstAlive) return state;
      const { speciesId, level } = pickWildEncounter(WILD_POOL);
      const enemy = spawnMonster(speciesId, level);
      const battle: BattleState = {
        playerUid: firstAlive.uid,
        enemy,
        phase: 'player_choice',
        log: [mkLog(`WILD ${enemy.name} APPEARED!`)],
        awaitingEnemyMove: false,
      };
      return {
        ...state,
        battle,
        pokedex: markPokedex(state, speciesId, { seen: true }),
      };
    }

    case 'PLAYER_MOVE': {
      if (!state.battle || state.battle.phase !== 'player_choice') return state;
      let active = getActive(state);
      if (!active) return state;
      let enemy = state.battle.enemy;
      let logs: string[] = [];

      const statusCheck = preMoveStatusCheck(active);
      active = statusCheck.monster;
      logs.push(...statusCheck.log);

      if (statusCheck.canAct) {
        const move = active.moves.find((mv) => mv.id === action.moveId);
        if (move && move.pp > 0) {
          const updatedMoves = active.moves.map((mv) => (mv.id === move.id ? { ...mv, pp: mv.pp - 1 } : mv));
          active = { ...active, moves: updatedMoves };

          const result = resolveMove(active, enemy, move);
          if (!result.hit) {
            logs.push(`${active.name}'s ${move.name} missed!`);
          } else {
            logs.push(`${active.name} used ${move.name}!`);
            const newHp = Math.max(0, enemy.hp - result.damage);
            enemy = { ...enemy, hp: newHp };
            sfx.moveUsed();
            if (result.effectiveness === 'super') { logs.push('It was super effective!'); sfx.superEffective(); }
            else if (result.effectiveness === 'weak') logs.push("It wasn't very effective...");
            else if (result.effectiveness === 'none') logs.push(`It had no effect on ${enemy.name}...`);
            if (result.damage > 0) sfx.hit();
            if (result.inflictedStatus && enemy.status === 'none') {
              enemy = { ...enemy, status: result.inflictedStatus };
              logs.push(`${enemy.name} was afflicted with a status condition!`);
            }
          }
        }
      }

      let party = replaceParty(state.party, active);
      let battle: BattleState = { ...state.battle, enemy, log: [...state.battle.log, ...logs.map(mkLog)] };

      if (enemy.hp <= 0) {
        sfx.faint();
        battle = pushLogs(battle, [`WILD ${enemy.name} fainted!`]);
        const xpGain = xpRewardFor(enemy);
        const coinGain = currencyRewardFor(enemy);
        const xpResult = grantXp(active, xpGain);
        party = replaceParty(party, xpResult.monster);
        battle = pushLogs(battle, [`${active.name} gained ${xpGain} XP!`]);
        if (xpResult.leveledUp) {
          sfx.levelUp();
          battle = pushLogs(battle, [`${xpResult.monster.name} grew to Lv.${xpResult.monster.level}!`]);
          xpResult.newMoves.forEach((mv) => {
            battle = pushLogs(battle, [`${xpResult.monster.name} learned ${mv.name}!`]);
          });
        }
        battle = { ...battle, phase: 'victory', awaitingEnemyMove: false };
        return {
          ...state,
          party,
          currency: state.currency + coinGain,
          pokedex: markPokedex(state, enemy.speciesId, { seen: true }),
          battle,
        };
      }

      battle = { ...battle, phase: 'resolving', awaitingEnemyMove: true };
      return { ...state, party, battle };
    }

    case 'ENEMY_MOVE': {
      if (!state.battle) return state;
      let active = getActive(state);
      if (!active) return state;
      let enemy = state.battle.enemy;
      let logs: string[] = [];

      const statusCheck = preMoveStatusCheck(enemy);
      enemy = statusCheck.monster;
      logs.push(...statusCheck.log);

      if (statusCheck.canAct && enemy.hp > 0) {
        const move = pickEnemyMove(enemy);
        const updatedMoves = enemy.moves.map((mv) => (mv.id === move.id ? { ...mv, pp: Math.max(0, mv.pp - 1) } : mv));
        enemy = { ...enemy, moves: updatedMoves };

        const result = resolveMove(enemy, active, move);
        if (!result.hit) {
          logs.push(`${enemy.name}'s ${move.name} missed!`);
        } else {
          logs.push(`${enemy.name} used ${move.name}!`);
          const newHp = Math.max(0, active.hp - result.damage);
          active = { ...active, hp: newHp };
          sfx.hit();
          if (result.effectiveness === 'super') { logs.push('It was super effective!'); sfx.superEffective(); }
          else if (result.effectiveness === 'weak') logs.push("It wasn't very effective...");
          if (result.inflictedStatus && active.status === 'none') {
            active = { ...active, status: result.inflictedStatus };
            logs.push(`${active.name} was afflicted with a status condition!`);
          }
        }
      }

      // End-of-round status chip damage for both combatants
      const enemyTick = applyStatusTick(enemy);
      enemy = enemyTick.monster;
      logs.push(...enemyTick.log);
      const activeTick = applyStatusTick(active);
      active = activeTick.monster;
      logs.push(...activeTick.log);

      let party = replaceParty(state.party, active);
      let battle: BattleState = { ...state.battle, enemy, log: [...state.battle.log, ...logs.map(mkLog)], awaitingEnemyMove: false };

      if (enemy.hp <= 0) {
        sfx.faint();
        battle = pushLogs(battle, [`WILD ${enemy.name} fainted!`]);
        const xpGain = xpRewardFor(enemy);
        const coinGain = currencyRewardFor(enemy);
        const xpResult = grantXp(active, xpGain);
        party = replaceParty(party, xpResult.monster);
        battle = pushLogs(battle, [`${active.name} gained ${xpGain} XP!`]);
        if (xpResult.leveledUp) {
          sfx.levelUp();
          battle = pushLogs(battle, [`${xpResult.monster.name} grew to Lv.${xpResult.monster.level}!`]);
        }
        battle = { ...battle, phase: 'victory' };
        return {
          ...state, party, currency: state.currency + coinGain,
          pokedex: markPokedex(state, enemy.speciesId, { seen: true }), battle,
        };
      }

      if (active.hp <= 0) {
        sfx.faint();
        battle = pushLogs(battle, [`${active.name} fainted!`]);
        const anyAlive = party.some((m) => m.hp > 0);
        battle = { ...battle, phase: anyAlive ? 'force_switch' : 'defeat' };
        if (!anyAlive) battle = pushLogs(battle, ['Your team has no unfainted units left. Retreating...']);
        return { ...state, party, battle };
      }

      battle = { ...battle, phase: 'player_choice' };
      return { ...state, party, battle };
    }

    case 'SWITCH_ACTIVE': {
      if (!state.battle) return state;
      const target = state.party.find((m) => m.uid === action.uid);
      if (!target || target.hp <= 0) return state;
      sfx.menuSelect();
      let battle: BattleState = {
        ...state.battle,
        playerUid: target.uid,
        phase: action.free ? 'player_choice' : 'resolving',
        awaitingEnemyMove: !action.free,
        log: [...state.battle.log, mkLog(`Go, ${target.name}!`)],
      };
      return { ...state, battle };
    }

    case 'USE_ITEM_IN_BATTLE': {
      if (!state.battle) return state;
      const count = state.inventory[action.item];
      if (!count || count <= 0) return state;
      const target = state.party.find((m) => m.uid === action.targetUid);
      if (!target) return state;
      const heal = action.item === 'potion' ? 20 : 50;
      const healed = { ...target, hp: Math.min(target.maxHp, target.hp + heal) };
      const party = replaceParty(state.party, healed);
      sfx.coin();
      const battle: BattleState = {
        ...state.battle,
        phase: 'resolving',
        awaitingEnemyMove: true,
        log: [...state.battle.log, mkLog(`Used ${action.item.toUpperCase()} on ${healed.name}. Restored ${heal} HP.`)],
      };
      return {
        ...state,
        party,
        inventory: { ...state.inventory, [action.item]: count - 1 },
        battle,
      };
    }

    case 'CATCH_ATTEMPT': {
      if (!state.battle) return state;
      const count = state.inventory[action.ball];
      if (!count || count <= 0) return state;
      const enemy = state.battle.enemy;
      const inventory = { ...state.inventory, [action.ball]: count - 1 };
      const success = attemptCatch(enemy, action.ball);

      if (success) {
        sfx.catchSuccess();
        const canAddToParty = state.party.length < 6;
        const party = canAddToParty ? [...state.party, { ...enemy, hp: enemy.maxHp }] : state.party;
        const battle: BattleState = {
          ...state.battle,
          phase: 'caught',
          log: [...state.battle.log, mkLog(`Gotcha! ${enemy.name} was caught!`),
            ...(canAddToParty ? [] : [mkLog('Party is full — sent to storage.')])],
        };
        return {
          ...state, party, inventory,
          pokedex: markPokedex(state, enemy.speciesId, { seen: true, caught: true }),
          battle,
        };
      }

      sfx.catchFail();
      const battle: BattleState = {
        ...state.battle,
        phase: 'resolving',
        awaitingEnemyMove: true,
        log: [...state.battle.log, mkLog(`${enemy.name} broke free!`)],
      };
      return { ...state, inventory, battle };
    }

    case 'FLEE': {
      if (!state.battle) return state;
      const success = Math.random() < 0.75;
      if (success) {
        sfx.menuBack();
        const battle: BattleState = { ...state.battle, phase: 'fled', log: [...state.battle.log, mkLog('Got away safely!')] };
        return { ...state, battle };
      }
      sfx.error();
      const battle: BattleState = {
        ...state.battle,
        phase: 'resolving',
        awaitingEnemyMove: true,
        log: [...state.battle.log, mkLog("Couldn't escape!")],
      };
      return { ...state, battle };
    }

    case 'DISMISS_BATTLE_RESULT':
    case 'END_BATTLE':
      return { ...state, battle: null };

    default:
      return state;
  }
}
