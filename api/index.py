"""
FastAPI bridge exposing the real POSHOW battle/catch/player logic (from
./_lib) over HTTP. Vercel entrypoint — see README for deploy steps, the
Supabase table SQL, and a known upstream stat-exposure bug this works around.
"""

import logging
import os
import random
import sys
import uuid
from typing import Dict, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_lib"))

from pokemon_model import PokemonInstance          # noqa: E402
from player_model import PlayerInstance            # noqa: E402
from battle_system import BattleSystem             # noqa: E402
from pokeball_system import CatchSystem            # noqa: E402
from currency_system import CurrencySystem         # noqa: E402
from moves_database import get_move_data           # noqa: E402

app = FastAPI(title="Terminal Battler Bridge")


# every Pokemon construction below hits PokeAPI over the network with zero
# error handling in _lib — this catches that (or anything else unexpected)
# instead of leaking a raw 500 ⚙
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end — try again in a moment."},
    )

# same-origin in prod (Next.js + this API share one domain), mainly matters for local dev without `vercel dev`
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# persistence
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_db = None
if SUPABASE_URL and SUPABASE_KEY:
    from database import SupabaseDB
    _db = SupabaseDB(SUPABASE_URL, SUPABASE_KEY)
else:
    logger.warning(
        "SUPABASE_URL/SUPABASE_KEY not set — falling back to in-memory "
        "storage. This is fine for local dev but WILL lose data (and can "
        "behave inconsistently mid-battle) if deployed to Vercel like this."
    )

_MEMORY_PLAYERS: Dict[int, PlayerInstance] = {}


def get_or_create_player(user_id: int, username: str = "OPERATOR") -> PlayerInstance:
    if _db:
        player = _db.load_player(user_id)
        if player:
            return player
        player = _bootstrap_new_player(user_id, username)
        _db.save_player(player)
        return player

    if user_id not in _MEMORY_PLAYERS:
        _MEMORY_PLAYERS[user_id] = _bootstrap_new_player(user_id, username)
    return _MEMORY_PLAYERS[user_id]


def _bootstrap_new_player(user_id: int, username: str) -> PlayerInstance:
    """A brand-new player always starts with one Pokemon — this used to only
    happen lazily inside start_battle, which meant GET /roster on a fresh
    account returned an empty team. Centralizing it here means any endpoint
    that creates a player gets the same guarantee."""
    player = PlayerInstance(user_id, username)
    starter = PokemonInstance("charmander", 5, user_id)
    player.add_pokemon_to_team(starter)
    return player


def persist_player(player: PlayerInstance):
    if _db:
        _db.save_player(player)
    else:
        _MEMORY_PLAYERS[player.user_id] = player


# battle-stat adapter — works around a real upstream bug, see README ⚙
class BattleReadyPokemon:
    def __init__(self, pokemon: PokemonInstance):
        self._p = pokemon

    def __getattr__(self, name):
        return getattr(self._p, name)

    @property
    def attack(self):
        return self._p.actual_stats.get("atk", 10)

    @property
    def defense(self):
        return self._p.actual_stats.get("def", 10)

    @property
    def speed(self):
        return self._p.actual_stats.get("speed", 50)

    @property
    def types(self):
        raw = (self._p.api_data or {}).get("types", [])
        names = [t.get("type", {}).get("name", "normal") for t in raw]
        return names or ["normal"]


# battle sessions: persist the two Pokemon as dicts, not a live BattleSystem object.
# to_dict/from_dict round-trip IVs/nature/shiny exactly (rolled randomly at
# construction, must not re-roll). BattleSystem.__init__ sets player_hp/wild_hp
# from current_hp, so rebuilding fresh from the dicts each request just works ⚙

class SessionStore:
    def save(self, battle_id: str, user_id: int, player_dict: dict, wild_dict: dict) -> None:
        raise NotImplementedError

    def load(self, battle_id: str) -> Optional[dict]:
        raise NotImplementedError

    def delete(self, battle_id: str) -> None:
        raise NotImplementedError


class MemorySessionStore(SessionStore):
    """Local-dev-only. Does NOT survive across Vercel serverless instances."""

    def __init__(self):
        self._data: Dict[str, dict] = {}

    def save(self, battle_id, user_id, player_dict, wild_dict):
        self._data[battle_id] = {
            "user_id": user_id, "player_pokemon": player_dict, "wild_pokemon": wild_dict,
        }

    def load(self, battle_id):
        return self._data.get(battle_id)

    def delete(self, battle_id):
        self._data.pop(battle_id, None)


class SupabaseSessionStore(SessionStore):
    """Raw REST calls against Supabase's PostgREST API — same pattern as
    _lib/database.py's SupabaseDB, no extra client library needed."""

    def __init__(self, url: str, key: str):
        self.url = url
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def save(self, battle_id, user_id, player_dict, wild_dict):
        payload = {
            "battle_id": battle_id,
            "user_id": user_id,
            "player_pokemon": player_dict,
            "wild_pokemon": wild_dict,
        }
        try:
            requests.post(
                f"{self.url}/rest/v1/battle_sessions",
                headers={**self.headers, "Prefer": "resolution=merge-duplicates"},
                json=payload,
                timeout=10,
            )
        except requests.RequestException as e:
            logger.error(f"Failed to save battle session {battle_id}: {e}")

    def load(self, battle_id):
        try:
            res = requests.get(
                f"{self.url}/rest/v1/battle_sessions?battle_id=eq.{battle_id}",
                headers=self.headers,
                timeout=10,
            )
            rows = res.json()
            return rows[0] if rows else None
        except requests.RequestException as e:
            logger.error(f"Failed to load battle session {battle_id}: {e}")
            return None

    def delete(self, battle_id):
        try:
            requests.delete(
                f"{self.url}/rest/v1/battle_sessions?battle_id=eq.{battle_id}",
                headers=self.headers,
                timeout=10,
            )
        except requests.RequestException as e:
            logger.error(f"Failed to delete battle session {battle_id}: {e}")


_sessions: SessionStore = SupabaseSessionStore(SUPABASE_URL, SUPABASE_KEY) if _db else MemorySessionStore()


def _rebuild_battle(record: dict):
    """record is whatever SessionStore.load() returned."""
    player_mon = BattleReadyPokemon(PokemonInstance.from_dict(record["player_pokemon"]))
    wild_mon = BattleReadyPokemon(PokemonInstance.from_dict(record["wild_pokemon"]))
    battle = BattleSystem(player_mon, wild_mon)
    return battle, player_mon, wild_mon


WILD_SPECIES_POOL = [
    "pidgey", "rattata", "zubat", "geodude", "psyduck",
    "growlithe", "squirtle", "bulbasaur", "charmander",
]


class StartBattleRequest(BaseModel):
    user_id: int
    username: str = "OPERATOR"


class MoveRequest(BaseModel):
    battle_id: str
    move_name: str


class CatchRequest(BaseModel):
    battle_id: str
    ball_type: str = "pokeball"


class FleeRequest(BaseModel):
    battle_id: str


class SwitchRequest(BaseModel):
    battle_id: str
    pokemon_id: str


class ItemRequest(BaseModel):
    battle_id: str
    item_type: str  # "potion" | "superpotion"


class BuyRequest(BaseModel):
    user_id: int
    item_id: str
    quantity: int = Field(default=1, gt=0, le=99)


class HealRequest(BaseModel):
    user_id: int
    pokemon_id: str
    item_type: str  # "potion" | "superpotion"


# Prices are decided here, not trusted from the client — a request that
# only sends an item id and quantity can't smuggle in its own price.
SHOP_PRICES = {
    "pokeball": 50, "greatball": 150, "ultraball": 400,
    "potion": 80, "superpotion": 200,
}
BALL_TYPES = {"pokeball", "greatball", "ultraball"}
HEAL_AMOUNTS = {"potion": 20, "superpotion": 50}


def _extract_types(p) -> list:
    direct = getattr(p, "types", None)
    if direct:
        return direct
    api_data = getattr(p, "api_data", None) or {}
    raw = api_data.get("types", [])
    names = [t.get("type", {}).get("name", "normal") for t in raw]
    return names or ["normal"]


def serialize_move(move_name: str) -> dict:
    data = get_move_data(move_name) or {}
    return {
        "id": move_name,
        "name": move_name.upper().replace("-", " "),
        "type": data.get("type", "normal"),
        "power": data.get("power", 40),
        "accuracy": data.get("accuracy", 100),
        # The bot doesn't track per-move PP today (PokemonInstance.restore_pp
        # is a no-op) — 99/99 is an explicit "not tracked, always usable"
        # sentinel, not a real PP pool.
        "pp": 99,
        "max_pp": 99,
    }


def serialize_pokemon(p) -> dict:
    underlying = getattr(p, "_p", p)  # unwrap BattleReadyPokemon if needed
    api_data = getattr(underlying, "api_data", None) or {}
    return {
        "id": getattr(underlying, "id", underlying.species_name),
        "species_name": underlying.species_name,
        "nickname": getattr(underlying, "nickname", underlying.species_name),
        "level": underlying.level,
        "current_hp": underlying.current_hp,
        "max_hp": underlying.max_hp,
        "experience": getattr(underlying, "experience", 0),
        "xp_to_next": 100 * (2 ** (underlying.level - 1)),
        "types": _extract_types(p),
        "moves": [serialize_move(m) for m in underlying.moves],
        "is_shiny": getattr(underlying, "is_shiny", False),
        "is_fainted": getattr(underlying, "is_fainted", underlying.current_hp <= 0),
        # National dex number from PokeAPI — lets the frontend build a real
        # sprite URL instead of a placeholder. None if api_data wasn't fetched.
        "pokedex_id": api_data.get("id"),
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "player_persistence": "supabase" if _db else "memory",
        "session_persistence": "supabase" if _db else "memory",
    }


@app.get("/api/player/{user_id}/roster")
def get_roster(user_id: int):
    player = get_or_create_player(user_id)
    return {
        "user_id": player.user_id,
        "username": player.username,
        "coins": player.coins,
        "level": player.level,
        "team": [serialize_pokemon(p) for p in player.active_team],
        "collection_count": len(player.pokemon_collection),
        "pokeballs": player.pokeballs,
        "inventory": player.inventory,
    }


@app.post("/api/battle/start")
def start_battle(req: StartBattleRequest):
    player = get_or_create_player(req.user_id, req.username)

    lead = next((p for p in player.active_team if not p.is_fainted), None)
    if not lead:
        raise HTTPException(400, "Your whole team has fainted — heal up before scanning again.")

    species = random.choice(WILD_SPECIES_POOL)
    level = random.randint(3, 8)
    wild = PokemonInstance(species, level, trainer_id=0)

    player_mon = BattleReadyPokemon(lead)
    wild_mon = BattleReadyPokemon(wild)

    battle_id = str(uuid.uuid4())
    _sessions.save(battle_id, req.user_id, lead.to_dict(), wild.to_dict())

    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
        "log": [f"A wild {wild.species_name.upper()} appeared!"],
    }


@app.post("/api/battle/move")
def battle_move(req: MoveRequest):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")

    battle, player_mon, wild_mon = _rebuild_battle(record)

    available = battle.get_player_moves()
    if not available:
        raise HTTPException(500, "This Pokemon has no usable moves — can't resolve a turn.")
    move = next((m for m in available if m.name == req.move_name), available[0])
    opponent_move = battle.get_opponent_move()
    result = battle.execute_turn(move, opponent_move)

    player_mon._p.current_hp = max(0, battle.player_hp)
    wild_mon._p.current_hp = max(0, battle.wild_hp)

    response = {
        "log": result["log"],
        "is_finished": result["is_finished"],
        "winner": result["winner"],
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
    }

    if result["is_finished"]:
        player = get_or_create_player(record["user_id"])
        if result["winner"] == "player":
            xp = 20 * wild_mon.level
            coins = CurrencySystem().calculate_catch_reward(wild_mon.level)
            player_mon._p.add_experience(xp)
            response["xp_gained"] = xp
            response["coins_gained"] = coins
            for i, p in enumerate(player.active_team):
                if p.id == player_mon._p.id:
                    player.active_team[i] = player_mon._p
                    break
            player.add_coins(coins)
        else:
            player_mon._p.is_fainted = True
            for i, p in enumerate(player.active_team):
                if p.id == player_mon._p.id:
                    player.active_team[i] = player_mon._p
                    break
        persist_player(player)
        _sessions.delete(req.battle_id)
    else:
        _sessions.save(req.battle_id, record["user_id"], player_mon._p.to_dict(), wild_mon._p.to_dict())

    return response


@app.post("/api/battle/catch")
def battle_catch(req: CatchRequest):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")

    player = get_or_create_player(record["user_id"])
    if not player.use_pokeball(req.ball_type):
        raise HTTPException(400, f"No {req.ball_type} left.")

    wild = PokemonInstance.from_dict(record["wild_pokemon"])
    hp_percent = wild.current_hp / max(1, wild.max_hp)
    catch_rate = 45  # TODO: pull real per-species catch rate once pokeapi_manager exposes it

    result = CatchSystem().calculate_catch_chance(
        pokemon_hp_percent=hp_percent,
        pokemon_level=wild.level,
        pokemon_catch_rate=catch_rate,
        ball_type=req.ball_type,
    )

    if result["will_catch"]:
        player.catch_pokemon(wild)
        _sessions.delete(req.battle_id)

    persist_player(player)
    return {**result, "battle_id": req.battle_id, "remaining_balls": player.pokeballs.get(req.ball_type, 0)}


@app.post("/api/battle/flee")
def battle_flee(req: FleeRequest):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    success = random.random() < 0.75
    if success:
        _sessions.delete(req.battle_id)
    return {"success": success}


@app.post("/api/battle/switch")
def battle_switch(req: SwitchRequest):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")

    player = get_or_create_player(record["user_id"])
    target = next((p for p in player.active_team if p.id == req.pokemon_id and not p.is_fainted), None)
    if not target:
        raise HTTPException(400, "That Pokemon can't battle right now.")

    # Save the outgoing Pokemon's current HP back onto the player's team
    # before switching away from it.
    outgoing = PokemonInstance.from_dict(record["player_pokemon"])
    for i, p in enumerate(player.active_team):
        if p.id == outgoing.id:
            player.active_team[i] = outgoing
            break
    persist_player(player)

    # simplification: real games punish a voluntary switch with a free enemy hit.
    # battle_system.py's execute_turn() always resolves both sides together with
    # no "skip this side" option, reproducing it means duplicating its damage
    # logic. switching is free here for now, not silently passed off as real rules (˶˃⤙˂˶)
    new_active = BattleReadyPokemon(target)
    wild = PokemonInstance.from_dict(record["wild_pokemon"])
    _sessions.save(req.battle_id, record["user_id"], target.to_dict(), wild.to_dict())

    return {
        "log": [f"Go, {target.species_name.upper()}!"],
        "player_pokemon": serialize_pokemon(new_active),
        "wild_pokemon": serialize_pokemon(BattleReadyPokemon(wild)),
    }


@app.post("/api/battle/item")
def battle_item(req: ItemRequest):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    if req.item_type not in HEAL_AMOUNTS:
        raise HTTPException(400, f"Unknown item: {req.item_type}")

    player = get_or_create_player(record["user_id"])
    if not player.remove_item(req.item_type, 1):
        raise HTTPException(400, f"No {req.item_type} left.")

    active = PokemonInstance.from_dict(record["player_pokemon"])
    heal = HEAL_AMOUNTS[req.item_type]
    active.current_hp = min(active.max_hp, active.current_hp + heal)

    wild = PokemonInstance.from_dict(record["wild_pokemon"])
    _sessions.save(req.battle_id, record["user_id"], active.to_dict(), wild.to_dict())
    persist_player(player)

    return {
        "log": [f"Used {req.item_type.upper()}. Restored {heal} HP."],
        "player_pokemon": serialize_pokemon(BattleReadyPokemon(active)),
        "wild_pokemon": serialize_pokemon(BattleReadyPokemon(wild)),
        "remaining": player.inventory.get(req.item_type, 0),
    }


@app.post("/api/shop/buy")
def shop_buy(req: BuyRequest):
    if req.item_id not in SHOP_PRICES:
        raise HTTPException(400, f"Unknown item: {req.item_id}")

    player = get_or_create_player(req.user_id)
    total_price = SHOP_PRICES[req.item_id] * req.quantity
    if not player.spend_coins(total_price):
        raise HTTPException(400, "Not enough coins.")

    if req.item_id in BALL_TYPES:
        player.add_pokeball(req.item_id, req.quantity)
    else:
        player.add_item(req.item_id, req.quantity)

    persist_player(player)
    return {
        "coins": player.coins,
        "pokeballs": player.pokeballs,
        "inventory": player.inventory,
    }


@app.post("/api/party/heal")
def party_heal(req: HealRequest):
    if req.item_type not in HEAL_AMOUNTS:
        raise HTTPException(400, f"Unknown item: {req.item_type}")

    player = get_or_create_player(req.user_id)
    target = next((p for p in player.active_team if p.id == req.pokemon_id), None)
    if not target:
        raise HTTPException(404, "That Pokemon isn't on your team.")
    if target.current_hp >= target.max_hp:
        raise HTTPException(400, f"{target.species_name} is already at full HP.")

    if not player.remove_item(req.item_type, 1):
        raise HTTPException(400, f"No {req.item_type} left.")

    heal = HEAL_AMOUNTS[req.item_type]
    target.current_hp = min(target.max_hp, target.current_hp + heal)
    # a Potion reviving a fainted Pokemon is a simplification — real games
    # need a separate Revive item for that. Kept simple on purpose rather
    # than adding a whole new item type just for this.
    target.is_fainted = target.current_hp <= 0

    persist_player(player)
    return {
        "player_pokemon": serialize_pokemon(target),
        "remaining": player.inventory.get(req.item_type, 0),
    }
