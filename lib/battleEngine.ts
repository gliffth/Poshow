import { Monster, MoveInstance, MonsterStatus, BallType } from './types';
import { MOVE_DB, SPECIES_DB, getEffectivenessMultiplier, BALL_BONUS } from './gameData';

let uidCounter = 0;
function nextUid(): string {
  uidCounter += 1;
  return `m-${Date.now()}-${uidCounter}`;
}

export function buildMoveInstance(moveId: string): MoveInstance {
  const def = MOVE_DB[moveId];
  return {
    id: def.id,
    name: def.name,
    type: def.type,
    power: def.power,
    accuracy: def.accuracy,
    pp: def.maxPp,
    maxPp: def.maxPp,
    statusChance: def.statusChance,
    status: def.status,
  };
}

export function spawnMonster(speciesId: string, level: number): Monster {
  const species = SPECIES_DB[speciesId];
  const maxHp = Math.round(species.baseHp + level * 1.6);
  const learnedMoveIds = species.moveIds.slice(0, 2);
  return {
    uid: nextUid(),
    speciesId,
    name: species.name,
    types: species.types,
    level,
    xp: 0,
    xpToNext: level * 20,
    hp: maxHp,
    maxHp,
    attack: Math.round(species.baseAttack + level * 0.6),
    defense: Math.round(species.baseDefense + level * 0.5),
    status: 'none',
    hunger: 10,
    maxHunger: 10,
    portraitUrl: species.spriteUrl,
    moves: learnedMoveIds.map(buildMoveInstance),
    catchRate: species.catchRate,
    typeEffectiveness: species.typeEffectiveness,
  };
}

export interface DamageResult {
  damage: number;
  effectiveness: 'super' | 'normal' | 'weak' | 'none';
  hit: boolean;
  inflictedStatus?: MonsterStatus;
}

export function resolveMove(attacker: Monster, defender: Monster, move: MoveInstance): DamageResult {
  const hitRoll = Math.random();
  if (hitRoll > move.accuracy) {
    return { damage: 0, effectiveness: 'normal', hit: false };
  }

  // real per-species multiplier preferred, generic chart is just a fallback
  const mult = defender.typeEffectiveness?.[move.type] ?? getEffectivenessMultiplier(move.type, defender.types);

  // STAB — 1.5x when move type matches attacker's own type ⤙•
  const stab = attacker.types.includes(move.type) ? 1.5 : 1;

  const levelFactor = Math.floor((2 * attacker.level) / 5) + 2;
  const base = Math.floor((levelFactor * move.power * (attacker.attack / Math.max(1, defender.defense))) / 50) + 2;
  const randomFactor = 0.85 + Math.random() * 0.15;
  const damage = Math.max(1, Math.round(base * stab * mult * randomFactor));

  let effectiveness: DamageResult['effectiveness'] = 'normal';
  if (mult > 1) effectiveness = 'super';
  else if (mult < 1 && mult > 0) effectiveness = 'weak';
  else if (mult === 0) effectiveness = 'none';

  let inflictedStatus: MonsterStatus | undefined;
  if (defender.status === 'none' && move.status && move.statusChance && Math.random() < move.statusChance) {
    inflictedStatus = move.status;
  }

  return { damage: mult === 0 ? 0 : damage, effectiveness, hit: true, inflictedStatus };
}

export function attemptCatch(enemy: Monster, ballType: BallType): boolean {
  const hpFactor = 1 - enemy.hp / enemy.maxHp; // more damage = easier catch
  const statusBonus = enemy.status !== 'none' ? 0.15 : 0;
  const ballBonus = BALL_BONUS[ballType] ?? 0;
  const chance = enemy.catchRate * 0.5 + hpFactor * 0.4 + statusBonus + ballBonus;
  const clamped = Math.min(0.95, Math.max(0.05, chance));
  return Math.random() < clamped;
}

export function grantXp(monster: Monster, amount: number): { monster: Monster; leveledUp: boolean; newMoves: MoveInstance[] } {
  let m = { ...monster };
  let xp = m.xp + amount;
  let leveledUp = false;
  const newMoves: MoveInstance[] = [];
  const species = SPECIES_DB[m.speciesId];

  while (xp >= m.xpToNext) {
    xp -= m.xpToNext;
    m.level += 1;
    m.maxHp += 4;
    m.attack += 1;
    m.defense += 1;
    m.hp = m.maxHp; // level-up heals fully
    m.xpToNext = m.level * 20;
    leveledUp = true;

    if (m.level % 5 === 0 && m.moves.length < 4) {
      const known = new Set(m.moves.map((mv) => mv.id));
      const learnable = species.moveIds.find((id) => !known.has(id));
      if (learnable) {
        const mv = buildMoveInstance(learnable);
        m.moves = [...m.moves, mv];
        newMoves.push(mv);
      }
    }
  }
  m.xp = xp;
  return { monster: m, leveledUp, newMoves };
}

export function xpRewardFor(defeated: Monster): number {
  return Math.max(6, Math.round(defeated.level * 7));
}

export function currencyRewardFor(defeated: Monster): number {
  return Math.max(10, Math.round(defeated.level * 6));
}

export interface StatusCheckResult {
  canAct: boolean;
  monster: Monster;
  log: string[];
}

/** Run before a monster attempts to use a move — handles par/slp/frz gating. */
export function preMoveStatusCheck(monster: Monster): StatusCheckResult {
  const log: string[] = [];
  let m = monster;

  if (m.status === 'par') {
    if (Math.random() < 0.25) {
      log.push(`${m.name} is paralyzed! It can't move!`);
      return { canAct: false, monster: m, log };
    }
    return { canAct: true, monster: m, log };
  }

  if (m.status === 'slp') {
    if (Math.random() < 0.33) {
      m = { ...m, status: 'none' };
      log.push(`${m.name} woke up!`);
      return { canAct: true, monster: m, log };
    }
    log.push(`${m.name} is fast asleep.`);
    return { canAct: false, monster: m, log };
  }

  if (m.status === 'frz') {
    if (Math.random() < 0.2) {
      m = { ...m, status: 'none' };
      log.push(`${m.name} thawed out!`);
      return { canAct: true, monster: m, log };
    }
    log.push(`${m.name} is frozen solid!`);
    return { canAct: false, monster: m, log };
  }

  return { canAct: true, monster: m, log };
}

export interface StatusTickResult {
  monster: Monster;
  log: string[];
}

/** Chip damage applied at the end of a round for poison/burn. */
export function applyStatusTick(monster: Monster): StatusTickResult {
  const log: string[] = [];
  if (monster.hp <= 0) return { monster, log };

  if (monster.status === 'psn') {
    const dmg = Math.max(1, Math.ceil(monster.maxHp * 0.08));
    const hp = Math.max(0, monster.hp - dmg);
    log.push(`${monster.name} is hurt by poison!`);
    return { monster: { ...monster, hp }, log };
  }
  if (monster.status === 'brn') {
    const dmg = Math.max(1, Math.ceil(monster.maxHp * 0.06));
    const hp = Math.max(0, monster.hp - dmg);
    log.push(`${monster.name} is hurt by its burn!`);
    return { monster: { ...monster, hp }, log };
  }
  return { monster, log };
}

/** Enemy AI: picks a random move with PP remaining, falls back to Struggle. */
export function pickEnemyMove(enemy: Monster): MoveInstance {
  const usable = enemy.moves.filter((mv) => mv.pp > 0);
  if (usable.length === 0) {
    return { id: 'struggle', name: 'STRUGGLE', type: 'normal', power: 30, accuracy: 1, pp: 1, maxPp: 1 };
  }
  return usable[Math.floor(Math.random() * usable.length)];
}

export function pickWildEncounter(pool: { speciesId: string; minLevel: number; maxLevel: number; weight: number }[]): { speciesId: string; level: number } {
  const totalWeight = pool.reduce((sum, e) => sum + e.weight, 0);
  let roll = Math.random() * totalWeight;
  for (const entry of pool) {
    if (roll < entry.weight) {
      const level = entry.minLevel + Math.floor(Math.random() * (entry.maxLevel - entry.minLevel + 1));
      return { speciesId: entry.speciesId, level };
    }
    roll -= entry.weight;
  }
  const fallback = pool[0];
  return { speciesId: fallback.speciesId, level: fallback.minLevel };
}
