import { Monster, MoveInstance, LogEntry, ItemType } from './types';

// empty = same-origin relative paths, correct once deployed. set NEXT_PUBLIC_API_URL for local dev only if not using `vercel dev`
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Request timed out — the server took too long to respond.');
    }
    throw new ApiError(err instanceof Error ? err.message : 'Network request failed.');
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

// server response shapes (mirrors api/index.py) ⚙
export interface ServerMove {
  id: string;
  name: string;
  type: string;
  power: number;
  accuracy: number;
  pp: number;
  max_pp: number;
}

export interface ServerPokemon {
  id: string;
  species_name: string;
  nickname: string;
  level: number;
  current_hp: number;
  max_hp: number;
  experience: number;
  xp_to_next: number;
  types: string[];
  moves: ServerMove[];
  is_shiny: boolean;
  is_fainted: boolean;
  pokedex_id: number | null;
}

export interface StartBattleResponse {
  battle_id: string;
  player_pokemon: ServerPokemon;
  wild_pokemon: ServerPokemon;
  log: string[];
}

export interface BattleMoveResponse {
  log: string[];
  is_finished: boolean;
  winner: 'player' | 'wild' | null;
  player_pokemon: ServerPokemon;
  wild_pokemon: ServerPokemon;
  xp_gained?: number;
  coins_gained?: number;
}

export interface CatchResponse {
  battle_id: string;
  will_catch: boolean;
  message?: string;
  remaining_balls: number;
  [key: string]: unknown;
}

export interface FleeResponse {
  success: boolean;
}

export interface RosterResponse {
  user_id: number;
  username: string;
  coins: number;
  level: number;
  team: ServerPokemon[];
  collection_count: number;
  pokeballs: Record<string, number>;
  inventory: Record<string, number>;
}

export interface SwitchResponse {
  log: string[];
  player_pokemon: ServerPokemon;
  wild_pokemon: ServerPokemon;
}

export interface ItemResponse {
  log: string[];
  player_pokemon: ServerPokemon;
  wild_pokemon: ServerPokemon;
  remaining: number;
}

export interface BuyResponse {
  coins: number;
  pokeballs: Record<string, number>;
  inventory: Record<string, number>;
}

export interface HealResponse {
  player_pokemon: ServerPokemon;
  remaining: number;
}

// endpoints ⤙
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await request<{ ok: boolean }>('/api/health');
    return !!res.ok;
  } catch {
    return false;
  }
}

export function getRoster(userId: number) {
  return request<RosterResponse>(`/api/player/${userId}/roster`);
}

export function startBattle(userId: number, username: string) {
  return request<StartBattleResponse>('/api/battle/start', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, username }),
  });
}

export function sendMove(battleId: string, moveName: string) {
  return request<BattleMoveResponse>('/api/battle/move', {
    method: 'POST',
    body: JSON.stringify({ battle_id: battleId, move_name: moveName }),
  });
}

export function attemptCatch(battleId: string, ballType: string) {
  return request<CatchResponse>('/api/battle/catch', {
    method: 'POST',
    body: JSON.stringify({ battle_id: battleId, ball_type: ballType }),
  });
}

export function switchPokemon(battleId: string, pokemonId: string) {
  return request<SwitchResponse>('/api/battle/switch', {
    method: 'POST',
    body: JSON.stringify({ battle_id: battleId, pokemon_id: pokemonId }),
  });
}

export function useItem(battleId: string, itemType: string) {
  return request<ItemResponse>('/api/battle/item', {
    method: 'POST',
    body: JSON.stringify({ battle_id: battleId, item_type: itemType }),
  });
}

export function buyItem(userId: number, itemId: string, quantity = 1) {
  return request<BuyResponse>('/api/shop/buy', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, item_id: itemId, quantity }),
  });
}

export function healParty(userId: number, pokemonId: string, itemType: string) {
  return request<HealResponse>('/api/party/heal', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, pokemon_id: pokemonId, item_type: itemType }),
  });
}

export function flee(battleId: string) {
  return request<FleeResponse>('/api/battle/flee', {
    method: 'POST',
    body: JSON.stringify({ battle_id: battleId }),
  });
}

// mapping: server pokemon → frontend Monster ദ്ദി(ᵔᗜᵔ)
// hunger/PP/status aren't tracked by the bot yet — honest placeholders, not fabricated data
function spriteUrlFor(pokedexId: number | null): string {
  if (!pokedexId) {
    // No PokeAPI data came back (offline/rate-limited) — a neutral pokeball
    // icon reads better than a broken image, and doesn't imply real data.
    return 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png';
  }
  return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/${pokedexId}.gif`;
}

export function mapServerPokemon(sp: ServerPokemon): Monster {
  const moves: MoveInstance[] = sp.moves.map((m) => ({
    id: m.id,
    name: m.name,
    type: m.type,
    power: m.power,
    accuracy: (m.accuracy ?? 100) / 100, // backend sends 0-100, frontend math expects 0-1
    pp: m.pp,
    maxPp: m.max_pp,
  }));

  return {
    uid: sp.id,
    speciesId: sp.species_name,
    name: sp.nickname?.toUpperCase() || sp.species_name.toUpperCase(),
    types: sp.types,
    level: sp.level,
    xp: sp.experience,
    xpToNext: sp.xp_to_next,
    hp: sp.current_hp,
    maxHp: sp.max_hp,
    attack: 0, // not surfaced by the API today — battle math runs server-side
    defense: 0,
    status: 'none', // battle_system.py doesn't apply status effects yet
    hunger: 10,
    maxHunger: 10, // the bot has no hunger system — server monsters always read "full"
    portraitUrl: spriteUrlFor(sp.pokedex_id),
    moves,
    catchRate: 0, // unused for server monsters — /api/battle/catch decides server-side
  };
}

let logIdCounter = 0;
export function serverLogToEntries(lines: string[]): LogEntry[] {
  return lines.map((text) => {
    logIdCounter += 1;
    return { id: `srv-${Date.now()}-${logIdCounter}`, text };
  });
}

// server splits pokeballs/items into two dicts, frontend wants one flat record ฅ^>⩊<^ ฅ
export function mapServerInventory(
  pokeballs: Record<string, number>,
  inventory: Record<string, number>
): Record<ItemType, number> {
  return {
    pokeball: pokeballs.pokeball ?? 0,
    greatball: pokeballs.greatball ?? 0,
    ultraball: pokeballs.ultraball ?? 0,
    potion: inventory.potion ?? 0,
    superpotion: inventory.superpotion ?? 0,
  };
}
