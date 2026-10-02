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
  /** display name of the ability (server monsters only) */
  ability?: string;
  abilityDesc?: string;
  /** true for the daily boss */
  isBoss?: boolean;
}

/** Items that live outside the classic ball/potion inventory: server-only, tracked separately */
export type ExtraItemId = 'exp_all' | 'rare_candy';
export type ExtrasInventory = Record<ExtraItemId, number> & { battle_points: number };

export interface ExtraShopItemDef {
  id: ExtraItemId;
  name: string;
  price: number;
  description: string;
}

/** Battle Gym fight context + outcome (server-driven) */
export interface GymBattleInfo {
  floor: number;
  leader: boolean;
  trainer: string;
  gym?: string | null;
  /** set once the fight ends */
  outcome?: {
    won: boolean;
    bp: number;
    coins: number;
    badge?: string | null;
    runOver: boolean;
    floorsCleared: number;
    best: number;
    remaining: number;
  };
}

export interface GymStatus {
  in_run: boolean;
  floor: number;
  next_floor: number;
  best: number;
  bp: number;
  next_is_leader: boolean;
  next_level: number;
  leader: { name: string; type: string; gym: string } | null;
  shop: { id: string; name: string; price: number }[];
}

/** Journey (towns, routes, story trainers) — mirrors api/_lib/journey.py state() */
export interface JourneyChallenge {
  id: string;
  name: string;
  title: string;
  kind: 'gym' | 'rival' | 'e4' | 'champion';
  cleared: boolean;
  available: boolean;
  reason: string | null;
  team_size: number;
  top_level: number;
  badge: string | null;
}

export interface JourneyExit {
  id: string;
  name: string;
  kind: 'town' | 'route';
  locked: boolean;
  reason: string | null;
}

export interface JourneyState {
  mode: 'journey' | 'free_roam';
  region: string;
  location: { id: string; name: string; kind: 'town' | 'route'; desc: string; heal: string | null; route_id: string | null } | null;
  exits: JourneyExit[];
  challenges: JourneyChallenge[];
  badges: string[];
  badge_count?: number;
  objective: string;
  complete: boolean;
  can_scan: boolean;
  pending: { trainer: string; idx: number } | null;
}

/** A story trainer battle (gym leader / rival / Elite Four / Champion) */
export interface StoryBattleInfo {
  trainer: string;
  name: string;
  title: string;
  kind: string;
  /** 0-based index of the opponent's current Pokémon, and team size */
  idx: number;
  size: number;
  badge?: string | null;
  outcome?: {
    won: boolean;
    coins: number;
    badge?: string | null;
    win?: string;
    complete?: boolean;
    unlockedRegion?: string | null;
    blackout?: boolean;
    remaining?: number;
    location?: string;
    items?: Record<string, number>;
  };
}

export interface BattleRewards {
  xp: number;
  coins: number;
  items: [string, number][];
  expAll: { used: boolean; perPokemon: number; count: number; levelUps: string[] };
  boss: boolean;
  flawless: boolean;
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
  /** daily boss fight — can't be caught, pays out once per day */
  isBoss?: boolean;
  /** Battle Gym floor fight */
  gym?: GymBattleInfo;
  /** story trainer fight (journey) */
  story?: StoryBattleInfo;
  /** split this battle's XP across the team (consumes one EXP All on a win) */
  useExpAll?: boolean;
  /** filled in when the server reports a win */
  rewards?: BattleRewards;
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
  /** EXP All / Rare Candy — server-only items (older saves won't have this; see HYDRATE) */
  extras: ExtrasInventory;
  pokedex: Record<string, PokedexEntry>;
  settings: GameSettings;
  battle: BattleState | null;
  /** placeholder id until real Telegram initData auth exists, see lib/guestId.ts ᓚ₍⑅^..^₎♡ */
  guestUserId: number;
  /** true once local state has been replaced by the real backend roster, one time only */
  hasReconciledServer: boolean;
}
