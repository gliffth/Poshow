import { MoveDef, MonsterType, SpeciesDef, ShopItemDef, ItemType } from './types';

// legacy fallback chart — real species carry their own typeEffectiveness now, this only kicks in if one somehow doesn't (˶˃⤙˂˶)
export const TYPE_CHART: Record<MonsterType, Partial<Record<MonsterType, number>>> = {
  fire: { grass: 2, water: 0.5, fire: 0.5 },
  water: { fire: 2, grass: 0.5, water: 0.5 },
  grass: { water: 2, fire: 0.5, grass: 0.5, poison: 0.5 },
  electric: { water: 2, grass: 0.5, electric: 0.5 },
  poison: { grass: 2, poison: 0.5 },
  dark: { dark: 0.5 },
  normal: {},
};

export function getEffectivenessMultiplier(attackType: string, defendTypes: string[]): number {
  return defendTypes.reduce((mult, dType) => {
    const table = TYPE_CHART[attackType as MonsterType] || {};
    const m = table[dType as MonsterType];
    return mult * (m === undefined ? 1 : m);
  }, 1);
}

// per-type accent color, used sparingly (HP bar fill, card border glow) — covers all 18 types
const TYPE_ACCENT_MAP: Record<string, string> = {
  fire: '#ff6a3d',
  water: '#3dd6ff',
  grass: '#4af626',
  electric: '#f5e34a',
  poison: '#c86bff',
  dark: '#9a9ae0',
  normal: '#b9b08f',
  ice: '#8fe8e0',
  fighting: '#c25c3f',
  ground: '#c9a86a',
  flying: '#a8c8f0',
  psychic: '#ff6ea8',
  bug: '#a8c83a',
  rock: '#b8a05a',
  ghost: '#7a6ea8',
  dragon: '#6a5ee0',
  steel: '#a8b0c0',
  fairy: '#f0a8d8',
};

/** Safe lookup — unknown/missing types (or empty type arrays) fall back to a neutral accent. */
export function getTypeAccent(type: string | undefined): string {
  if (!type) return TYPE_ACCENT_MAP.normal;
  return TYPE_ACCENT_MAP[type] ?? TYPE_ACCENT_MAP.normal;
}

export const TYPE_ACCENT = TYPE_ACCENT_MAP;

// real Pokémon data, 16 species — curated to level-up-only moves so nothing's wildly out of place (Magikarp = just Tackle, not TM Hydro Pump) ◝(ᵔᗜᵔ)◜
export const MOVE_DB: Record<string, MoveDef> = {
  tackle: { id: "tackle", name: "TACKLE", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  vine_whip: { id: "vine_whip", name: "VINE WHIP", type: "grass", power: 45, accuracy: 1.0, maxPp: 20 },
  razor_leaf: { id: "razor_leaf", name: "RAZOR LEAF", type: "grass", power: 55, accuracy: 0.95, maxPp: 20 },
  seed_bomb: { id: "seed_bomb", name: "SEED BOMB", type: "grass", power: 80, accuracy: 1.0, maxPp: 20 },
  scratch: { id: "scratch", name: "SCRATCH", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  ember: { id: "ember", name: "EMBER", type: "fire", power: 40, accuracy: 1.0, maxPp: 20 },
  dragon_breath: { id: "dragon_breath", name: "DRAGON BREATH", type: "dragon", power: 60, accuracy: 1.0, maxPp: 20 },
  fire_fang: { id: "fire_fang", name: "FIRE FANG", type: "fire", power: 65, accuracy: 0.95, maxPp: 20 },
  water_gun: { id: "water_gun", name: "WATER GUN", type: "water", power: 40, accuracy: 1.0, maxPp: 20 },
  bubble: { id: "bubble", name: "BUBBLE", type: "water", power: 40, accuracy: 1.0, maxPp: 20 },
  rapid_spin: { id: "rapid_spin", name: "RAPID SPIN", type: "normal", power: 50, accuracy: 1.0, maxPp: 20 },
  thunder_shock: { id: "thunder_shock", name: "THUNDER SHOCK", type: "electric", power: 40, accuracy: 1.0, maxPp: 20 },
  double_kick: { id: "double_kick", name: "DOUBLE KICK", type: "fighting", power: 30, accuracy: 1.0, maxPp: 20 },
  spark: { id: "spark", name: "SPARK", type: "electric", power: 65, accuracy: 1.0, maxPp: 20 },
  slam: { id: "slam", name: "SLAM", type: "normal", power: 80, accuracy: 0.75, maxPp: 20 },
  gust: { id: "gust", name: "GUST", type: "flying", power: 40, accuracy: 1.0, maxPp: 20 },
  quick_attack: { id: "quick_attack", name: "QUICK ATTACK", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  twister: { id: "twister", name: "TWISTER", type: "dragon", power: 40, accuracy: 1.0, maxPp: 20 },
  bite: { id: "bite", name: "BITE", type: "dark", power: 60, accuracy: 1.0, maxPp: 20 },
  pursuit: { id: "pursuit", name: "PURSUIT", type: "dark", power: 40, accuracy: 1.0, maxPp: 20 },
  absorb: { id: "absorb", name: "ABSORB", type: "grass", power: 20, accuracy: 1.0, maxPp: 20 },
  astonish: { id: "astonish", name: "ASTONISH", type: "ghost", power: 30, accuracy: 1.0, maxPp: 20 },
  rollout: { id: "rollout", name: "ROLLOUT", type: "rock", power: 30, accuracy: 0.9, maxPp: 20 },
  bulldoze: { id: "bulldoze", name: "BULLDOZE", type: "ground", power: 60, accuracy: 1.0, maxPp: 20 },
  rock_throw: { id: "rock_throw", name: "ROCK THROW", type: "rock", power: 50, accuracy: 0.9, maxPp: 20 },
  confusion: { id: "confusion", name: "CONFUSION", type: "psychic", power: 50, accuracy: 1.0, maxPp: 20 },
  flame_wheel: { id: "flame_wheel", name: "FLAME WHEEL", type: "fire", power: 60, accuracy: 1.0, maxPp: 20 },
  lick: { id: "lick", name: "LICK", type: "ghost", power: 30, accuracy: 1.0, maxPp: 20 },
  payback: { id: "payback", name: "PAYBACK", type: "dark", power: 50, accuracy: 1.0, maxPp: 20 },
  hex: { id: "hex", name: "HEX", type: "ghost", power: 65, accuracy: 1.0, maxPp: 20 },
  sucker_punch: { id: "sucker_punch", name: "SUCKER PUNCH", type: "dark", power: 70, accuracy: 1.0, maxPp: 20 },
  rock_smash: { id: "rock_smash", name: "ROCK SMASH", type: "fighting", power: 40, accuracy: 1.0, maxPp: 20 },
  revenge: { id: "revenge", name: "REVENGE", type: "fighting", power: 60, accuracy: 1.0, maxPp: 20 },
  bullet_punch: { id: "bullet_punch", name: "BULLET PUNCH", type: "steel", power: 40, accuracy: 1.0, maxPp: 20 },
  mega_punch: { id: "mega_punch", name: "MEGA PUNCH", type: "normal", power: 80, accuracy: 0.85, maxPp: 20 },
  fake_out: { id: "fake_out", name: "FAKE OUT", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  feint: { id: "feint", name: "FEINT", type: "normal", power: 30, accuracy: 1.0, maxPp: 20 },
  pay_day: { id: "pay_day", name: "PAY DAY", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  pound: { id: "pound", name: "POUND", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  disarming_voice: { id: "disarming_voice", name: "DISARMING VOICE", type: "fairy", power: 40, accuracy: 1.0, maxPp: 20 },
  echoed_voice: { id: "echoed_voice", name: "ECHOED VOICE", type: "normal", power: 40, accuracy: 1.0, maxPp: 20 },
  covet: { id: "covet", name: "COVET", type: "normal", power: 60, accuracy: 1.0, maxPp: 20 },
};

export const SPECIES_DB: Record<string, SpeciesDef> = {
  "bulbasaur": {
    id: "bulbasaur", name: "BULBASAUR", types: ["grass", "poison"],
    baseHp: 45, baseAttack: 49, baseDefense: 49, catchRate: 0.176,
    moveIds: ["tackle", "vine_whip", "razor_leaf", "seed_bomb"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/1.gif",
    typeEffectiveness: { "flying": 2, "fire": 2, "ice": 2, "water": 0.5, "grass": 0.25, "electric": 0.5, "psychic": 2, "fighting": 0.5, "fairy": 0.5 },
  },
  "charmander": {
    id: "charmander", name: "CHARMANDER", types: ["fire"],
    baseHp: 39, baseAttack: 52, baseDefense: 43, catchRate: 0.176,
    moveIds: ["scratch", "ember", "dragon_breath", "fire_fang"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/4.gif",
    typeEffectiveness: { "ground": 2, "rock": 2, "water": 2, "bug": 0.5, "steel": 0.5, "fire": 0.5, "grass": 0.5, "ice": 0.5, "fairy": 0.5 },
  },
  "squirtle": {
    id: "squirtle", name: "SQUIRTLE", types: ["water"],
    baseHp: 44, baseAttack: 48, baseDefense: 65, catchRate: 0.176,
    moveIds: ["tackle", "water_gun", "bubble", "rapid_spin"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/7.gif",
    typeEffectiveness: { "grass": 2, "electric": 2, "steel": 0.5, "fire": 0.5, "water": 0.5, "ice": 0.5 },
  },
  "pikachu": {
    id: "pikachu", name: "PIKACHU", types: ["electric"],
    baseHp: 35, baseAttack: 55, baseDefense: 40, catchRate: 0.745,
    moveIds: ["thunder_shock", "double_kick", "spark", "slam"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/25.gif",
    typeEffectiveness: { "ground": 2, "flying": 0.5, "steel": 0.5, "electric": 0.5 },
  },
  "pidgey": {
    id: "pidgey", name: "PIDGEY", types: ["normal", "flying"],
    baseHp: 40, baseAttack: 45, baseDefense: 40, catchRate: 1.0,
    moveIds: ["tackle", "gust", "quick_attack", "twister"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/16.gif",
    typeEffectiveness: { "ghost": 0, "rock": 2, "electric": 2, "ice": 2, "bug": 0.5, "grass": 0.5, "ground": 0 },
  },
  "rattata": {
    id: "rattata", name: "RATTATA", types: ["normal"],
    baseHp: 30, baseAttack: 56, baseDefense: 35, catchRate: 1.0,
    moveIds: ["tackle", "quick_attack", "bite", "pursuit"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/19.gif",
    typeEffectiveness: { "fighting": 2, "ghost": 0 },
  },
  "zubat": {
    id: "zubat", name: "ZUBAT", types: ["poison", "flying"],
    baseHp: 40, baseAttack: 45, baseDefense: 35, catchRate: 1.0,
    moveIds: ["gust", "absorb", "astonish", "bite"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/41.gif",
    typeEffectiveness: { "ground": 0, "psychic": 2, "fighting": 0.25, "poison": 0.5, "bug": 0.25, "grass": 0.25, "fairy": 0.5, "rock": 2, "electric": 2, "ice": 2 },
  },
  "geodude": {
    id: "geodude", name: "GEODUDE", types: ["rock", "ground"],
    baseHp: 40, baseAttack: 80, baseDefense: 100, catchRate: 1.0,
    moveIds: ["tackle", "rollout", "bulldoze", "rock_throw"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/74.gif",
    typeEffectiveness: { "fighting": 2, "ground": 2, "steel": 2, "water": 4, "grass": 4, "normal": 0.5, "flying": 0.5, "poison": 0.25, "fire": 0.5, "ice": 2, "rock": 0.5, "electric": 0 },
  },
  "psyduck": {
    id: "psyduck", name: "PSYDUCK", types: ["water"],
    baseHp: 50, baseAttack: 52, baseDefense: 48, catchRate: 0.745,
    moveIds: ["scratch", "bubble", "water_gun", "confusion"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/54.gif",
    typeEffectiveness: { "grass": 2, "electric": 2, "steel": 0.5, "fire": 0.5, "water": 0.5, "ice": 0.5 },
  },
  "growlithe": {
    id: "growlithe", name: "GROWLITHE", types: ["fire"],
    baseHp: 55, baseAttack: 70, baseDefense: 45, catchRate: 0.745,
    moveIds: ["ember", "bite", "flame_wheel", "fire_fang"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/58.gif",
    typeEffectiveness: { "ground": 2, "rock": 2, "water": 2, "bug": 0.5, "steel": 0.5, "fire": 0.5, "grass": 0.5, "ice": 0.5, "fairy": 0.5 },
  },
  "gastly": {
    id: "gastly", name: "GASTLY", types: ["ghost", "poison"],
    baseHp: 30, baseAttack: 35, baseDefense: 30, catchRate: 0.745,
    moveIds: ["lick", "payback", "hex", "sucker_punch"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/92.gif",
    typeEffectiveness: { "ghost": 2, "dark": 2, "poison": 0.25, "bug": 0.25, "normal": 0, "fighting": 0.0, "ground": 2, "psychic": 2, "grass": 0.5, "fairy": 0.5 },
  },
  "machop": {
    id: "machop", name: "MACHOP", types: ["fighting"],
    baseHp: 70, baseAttack: 80, baseDefense: 50, catchRate: 0.706,
    moveIds: ["tackle", "rock_smash", "revenge", "bullet_punch"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/66.gif",
    typeEffectiveness: { "flying": 2, "psychic": 2, "fairy": 2, "rock": 0.5, "bug": 0.5, "dark": 0.5 },
  },
  "abra": {
    id: "abra", name: "ABRA", types: ["psychic"],
    baseHp: 25, baseAttack: 20, baseDefense: 15, catchRate: 0.784,
    moveIds: ["mega_punch"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/63.gif",
    typeEffectiveness: { "bug": 2, "ghost": 2, "dark": 2, "fighting": 0.5, "psychic": 0.5 },
  },
  "magikarp": {
    id: "magikarp", name: "MAGIKARP", types: ["water"],
    baseHp: 20, baseAttack: 10, baseDefense: 55, catchRate: 1.0,
    moveIds: ["tackle"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/129.gif",
    typeEffectiveness: { "grass": 2, "electric": 2, "steel": 0.5, "fire": 0.5, "water": 0.5, "ice": 0.5 },
  },
  "meowth": {
    id: "meowth", name: "MEOWTH", types: ["normal"],
    baseHp: 40, baseAttack: 45, baseDefense: 35, catchRate: 1.0,
    moveIds: ["fake_out", "feint", "scratch", "pay_day"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/52.gif",
    typeEffectiveness: { "fighting": 2, "ghost": 0 },
  },
  "jigglypuff": {
    id: "jigglypuff", name: "JIGGLYPUFF", types: ["normal", "fairy"],
    baseHp: 115, baseAttack: 45, baseDefense: 20, catchRate: 0.667,
    moveIds: ["pound", "disarming_voice", "echoed_voice", "covet"], spriteUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/39.gif",
    typeEffectiveness: { "ghost": 0, "poison": 2, "steel": 2, "bug": 0.5, "dark": 0.5, "dragon": 0 },
  },
};

// Wild encounter table used by "Scan Area"
export const WILD_POOL: { speciesId: string; minLevel: number; maxLevel: number; weight: number }[] = [
  { speciesId: 'rattata', minLevel: 3, maxLevel: 8, weight: 4 },
  { speciesId: 'pidgey', minLevel: 3, maxLevel: 9, weight: 4 },
  { speciesId: 'zubat', minLevel: 4, maxLevel: 10, weight: 3 },
  { speciesId: 'psyduck', minLevel: 5, maxLevel: 11, weight: 3 },
  { speciesId: 'meowth', minLevel: 4, maxLevel: 10, weight: 3 },
  { speciesId: 'geodude', minLevel: 6, maxLevel: 12, weight: 2 },
  { speciesId: 'machop', minLevel: 6, maxLevel: 12, weight: 2 },
  { speciesId: 'growlithe', minLevel: 7, maxLevel: 13, weight: 2 },
  { speciesId: 'gastly', minLevel: 7, maxLevel: 13, weight: 2 },
  { speciesId: 'abra', minLevel: 5, maxLevel: 10, weight: 2 },
  { speciesId: 'magikarp', minLevel: 3, maxLevel: 15, weight: 2 },
  { speciesId: 'jigglypuff', minLevel: 5, maxLevel: 11, weight: 1 },
  { speciesId: 'pikachu', minLevel: 8, maxLevel: 14, weight: 1 },
];

// shop ⟆
export const SHOP_ITEMS: ShopItemDef[] = [
  { id: 'pokeball', name: 'BASIC BALL', price: 50, description: 'Standard capture unit. Low field bonus.' },
  { id: 'greatball', name: 'GREAT BALL', price: 150, description: 'Improved capture unit. Moderate field bonus.' },
  { id: 'ultraball', name: 'ULTRA BALL', price: 400, description: 'High-grade capture unit. Strong field bonus.' },
  { id: 'potion', name: 'POTION', price: 80, description: 'Restores 20 HP to one unit.' },
  { id: 'superpotion', name: 'SUPER POTION', price: 200, description: 'Restores 50 HP to one unit.' },
];

export const BALL_BONUS: Record<ItemType, number> = {
  pokeball: 0.1,
  greatball: 0.25,
  ultraball: 0.4,
  potion: 0,
  superpotion: 0,
};

export const DEFAULT_INVENTORY: Record<ItemType, number> = {
  pokeball: 5,
  greatball: 0,
  ultraball: 0,
  potion: 2,
  superpotion: 0,
};
