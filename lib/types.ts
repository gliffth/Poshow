export type MonsterStatus = 'none' | 'psn' | 'brn' | 'slp' | 'par' | 'frz';
export type MonsterType = 'normal' | 'fire' | 'water' | 'grass' | 'electric' | 'poison' | 'dark';
export type BallType = 'pokeball' | 'greatball' | 'ultraball';
export type ItemType = BallType | 'potion' | 'superpotion';

export interface MoveDef {
  id: string;
  name: string;
  type: string;
  power: number;
  accuracy: number;
  maxPp: number;
  /** chance (0-1) this move inflicts its status on hit, if any */
  statusChance?: number;
  status?: MonsterStatus;
}

export interface MoveInstance {
  id: string;
  name: string;
  type: string;
  power: number;
  accuracy: number;
  pp: number;
  maxPp: number;
  statusChance?: number;
  status?: MonsterStatus;
}

export interface SpeciesDef {
  id: string;
  name: string;
  types: string[]; // widened — real species span all 18 types, not just this app's original 7
  baseHp: number;
  baseAttack: number;
  baseDefense: number;
  catchRate: number; // 0-1, higher = easier
  moveIds: string[]; // full learnable pool, first entries learned first
  spriteUrl: string;
  /** real dual-type multiplier per attacking type, preferred over the global chart ⤙• */
  typeEffectiveness?: Record<string, number>;
}

export interface Monster {
  uid: string; // unique instance id
  speciesId: string;
  name: string;
  types: string[]; // widened from MonsterType — server data spans all 18 real types
  level: number;
  xp: number;
  xpToNext: number;
  hp: number;
  maxHp: number;
  attack: number;
  defense: number;
  status: MonsterStatus;
  hunger: number;
  maxHunger: number;
  portraitUrl: string;
  moves: MoveInstance[];
  catchRate: number;
  typeEffectiveness?: Record<string, number>;
}

export interface ShopItemDef {
  id: ItemType;
  name: string;
  price: number;
  description: string;
}

export interface PokedexEntry {
  speciesId: string;
  seen: boolean;
  caught: boolean;
}

export interface LogEntry {
  id: string;
  text: string;
}

export type BattlePhase =
  | 'intro'
  | 'player_choice'
  | 'resolving'
  | 'force_switch'
  | 'victory'
  | 'defeat'
  | 'caught'
  | 'fled'
  | 'exit';

export interface BattleState {
  playerUid: string;
  enemy: Monster;
  phase: BattlePhase;
  log: LogEntry[];
  awaitingEnemyMove: boolean;
  /** set when this battle is server-authoritative, not the local mock engine */
  serverBattleId?: string;
}

export type ThemeName = 'weathered' | 'cream' | 'paper';

export interface GameSettings {
  soundOn: boolean;
  theme: ThemeName;
}

export interface GameState {
  trainerName: string;
  currency: number;
  party: Monster[];
  inventory: Record<ItemType, number>;
  pokedex: Record<string, PokedexEntry>;
  settings: GameSettings;
  battle: BattleState | null;
  /** placeholder id until real Telegram initData auth exists, see lib/guestId.ts ᓚ₍⑅^..^₎♡ */
  guestUserId: number;
  /** true once local state has been replaced by the real backend roster, one time only */
  hasReconciledServer: boolean;
}
