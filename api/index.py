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
from fastapi import FastAPI, Header, HTTPException, Request, Response
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
from daily_boss_system import daily_boss_system, today_key, DailyBoss  # noqa: E402
from rare_candy_system import RareCandy           # noqa: E402
from route_encounters import EncounterSystem      # noqa: E402
from abilities_system import AbilitySystem        # noqa: E402
import boss_battle                                 # noqa: E402
import gym_system                                  # noqa: E402
import accounts                                     # noqa: E402
import avatars                                      # noqa: E402
import journey                                      # noqa: E402
import onboarding                                   # noqa: E402
from database import DatabaseError                 # noqa: E402
from move_learning_system import get_moves_by_level  # noqa: E402

app = FastAPI(title="Terminal Battler Bridge")


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    logger.error(f"database error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "The database isn't answering right now — try again in a moment."},
    )


@app.exception_handler(journey.JourneyError)
async def journey_error_handler(request: Request, exc: journey.JourneyError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(accounts.AccountError)
async def account_error_handler(request: Request, exc: accounts.AccountError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


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
# Set ALLOWED_ORIGINS (comma-separated, e.g. https://poshow.vercel.app) to lock the API to your site;
# unset = open to any origin (fine while testing).
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
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

_accounts = accounts.AccountService(SUPABASE_URL, SUPABASE_KEY) if _db else accounts.AccountService()

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
    """A brand-new player starts with NO Pokemon — they pick a region and a starter first
    (POST /api/player/starter). The roster reports needs_starter until they do."""
    return PlayerInstance(user_id, username)


def persist_player(player: PlayerInstance):
    if _db:
        # saves the stats row (incl. active_team ids) AND every Pokemon row — see database.py
        if not _db.save_player(player):
            logger.error(f"persist_player: save failed for {player.user_id} (details logged above)")


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
        return _type_names(raw) or ["normal"]


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
            res = requests.post(
                f"{self.url}/rest/v1/battle_sessions?on_conflict=battle_id",
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payload,
                timeout=10,
            )
            if res.status_code not in (200, 201, 204):
                # this used to fail silently -> every /battle/move came back 404
                logger.error(f"❌ battle session save failed ({res.status_code}): {res.text}")
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
    ("rattata", 4), ("pidgey", 4), ("zubat", 3), ("psyduck", 3), ("meowth", 3),
    ("geodude", 2), ("machop", 2), ("growlithe", 2), ("gastly", 2), ("abra", 2),
    ("magikarp", 2), ("jigglypuff", 1), ("pikachu", 1),
    # rare finds — same species as the starters, low weight on purpose
    ("bulbasaur", 1), ("charmander", 1), ("squirtle", 1),
]


def roll_wild_encounter(lead_level: int):
    """Weighted species pick, level scaled to the player's lead Pokemon
    instead of a flat range — a flat range meant a level 30 player was
    still fighting level 3-8 wild Pokemon, and a level 3 player could just
    as easily run into something far too strong."""
    species = random.choices(
        [s for s, _ in WILD_SPECIES_POOL],
        weights=[w for _, w in WILD_SPECIES_POOL],
        k=1,
    )[0]
    level = max(2, lead_level + random.randint(-2, 1))
    return species, level


def _roll_encounter(route_id: Optional[str], lead_level: int, player=None):
    """Wild Pokemon for this player. On a journey the LOCATION decides (route_id from the client is
    ignored); otherwise a picked route, otherwise the original level-scaled wild roll."""
    if player is not None and journey.ensure_story(player)["mode"] == "journey":
        here = journey.current_encounter(player)
        if not here:
            raise HTTPException(400, "No wild Pokémon here — travel to a route first.")
        return EncounterSystem.spawn_in_route(here)
    if route_id:
        if not EncounterSystem.has_route(route_id):
            raise HTTPException(404, f"Unknown route: {route_id}")
        return EncounterSystem.spawn_in_route(route_id)
    return roll_wild_encounter(lead_level)


class StartBattleRequest(BaseModel):
    user_id: int
    username: str = "OPERATOR"
    target_species: Optional[str] = None
    target_level: Optional[int] = Field(default=None, ge=1, le=100)
    route_id: Optional[str] = None


class ScoutRequest(BaseModel):
    user_id: int
    route_id: Optional[str] = None


class MoveRequest(BaseModel):
    battle_id: str
    move_name: str
    use_exp_all: bool = False


class BossStartRequest(BaseModel):
    user_id: int
    username: str = "OPERATOR"


class GymEnterRequest(BaseModel):
    user_id: int
    username: str = "OPERATOR"


class GymBuyRequest(BaseModel):
    user_id: int
    item_id: str
    quantity: int = Field(default=1, ge=1, le=99)


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
    "rare_candy": 1000, "exp_all": 500,
}
BALL_TYPES = {"pokeball", "greatball", "ultraball"}
HEAL_AMOUNTS = {"potion": 20, "superpotion": 50}


def _type_names(raw) -> list:
    """PokeAPI types arrive in two shapes depending on the path that produced them:
    plain strings (pokeapi_manager.get_pokemon) or raw {"type": {"name": ...}} dicts.
    Accept both — assuming only the dict shape made /roster crash with a 500."""
    names = []
    for t in raw or []:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict):
            names.append(t.get("type", {}).get("name", "normal"))
    return names


def _extract_types(p) -> list:
    direct = getattr(p, "types", None)
    if direct:
        return direct
    api_data = getattr(p, "api_data", None) or {}
    return _type_names(api_data.get("types", [])) or ["normal"]


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
        "ability": AbilitySystem.display_name(getattr(underlying, "ability", None)),
        "ability_desc": (
            AbilitySystem.get_ability(getattr(underlying, "ability", None)).description
            if getattr(underlying, "ability", None) and AbilitySystem.get_ability(underlying.ability)
            else None
        ),
        "is_boss": bool(getattr(underlying, "is_boss", False)),
        "gym_floor": int(getattr(underlying, "gym_floor", 0) or 0),
    }


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    """Render's port scanner and uptime pingers hit `/` — answer 200 instead of a noisy 404."""
    return {"ok": True, "service": "poshow-api"}


@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    """Deliberately tiny and DB-free: this is what keep-alive pingers and Render's health check
    call, and it must answer instantly."""
    return {
        "ok": True,
        "database": _db is not None,
        "player_persistence": "supabase" if _db else "memory",
        "session_persistence": "supabase" if _db else "memory",
    }


_DIAGNOSE_TABLES = {
    "players": ["user_id", "username", "created_date", "level", "experience", "coins", "wins", "losses", "elo",
                "current_streak", "current_region", "regions_unlocked", "pokemon_caught", "pokedex_seen",
                "inventory", "pokeballs", "login_streak", "badges", "achievements", "referral_code",
                "successful_referrals", "active_team", "avatar", "story"],
    "pokemon": ["id", "player_id", "species_name", "nickname", "level", "trainer_id", "current_hp", "max_hp",
                "experience", "iv", "ev", "nature", "moves", "status", "is_fainted", "is_shiny"],
    "battle_sessions": ["battle_id", "user_id", "player_pokemon", "wild_pokemon"],
    "accounts": ["username", "username_lower", "password_hash", "user_id"],
    "login_codes": ["code", "user_id", "username", "expires_at"],
}


@app.get("/api/diagnose")
def diagnose():
    """Open this URL in a browser after deploying: it checks that every Supabase table has every
    column the code writes, and says exactly what to fix. (Read-only — it only SELECTs.)"""
    if not _db:
        return {"ok": False, "database": False,
                "problems": ["SUPABASE_URL / SUPABASE_KEY are not set on this server — running in memory mode."]}
    problems = []
    for table, cols in _DIAGNOSE_TABLES.items():
        try:
            res = requests.get(
                f"{SUPABASE_URL}/rest/v1/{table}?select={','.join(cols)}&limit=1",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                timeout=15,
            )
        except requests.RequestException as e:
            problems.append(f"{table}: couldn't reach Supabase ({e})")
            continue
        if res.status_code == 200:
            continue
        try:
            msg = res.json().get("message") or res.text
        except ValueError:
            msg = res.text
        problems.append(f"{table}: {msg[:200]}")
    return {
        "ok": not problems,
        "database": True,
        "problems": problems,
        "fix": None if not problems else
               "Run database/schema.sql in the Supabase SQL editor (safe to re-run), then reload this page.",
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
        "inventory": boss_battle.public_inventory(player),
        "needs_starter": not player.active_team and not player.pokemon_collection,
        "region": player.current_region,
        "avatar": player.avatar,
    }


def _lead_or_400(player, action: str = "scanning again"):
    lead = next((p for p in player.active_team if not p.is_fainted and p.current_hp > 0), None)
    if lead:
        return lead
    if not player.active_team:
        raise HTTPException(400, "Choose your starter Pokémon first.")
    raise HTTPException(400, f"Your whole team has fainted — heal up before {action}.")


@app.post("/api/encounter/scout")
def encounter_scout(req: ScoutRequest):
    player = get_or_create_player(req.user_id)
    lead = _lead_or_400(player)

    seen_species = set()
    candidates = []
    attempts = 0
    while len(candidates) < 3 and attempts < 10:
        attempts += 1
        species, level = _roll_encounter(req.route_id, lead.level, player)
        if species in seen_species:
            continue
        seen_species.add(species)
        preview = PokemonInstance(species, level, trainer_id=0)
        candidates.append(serialize_pokemon(BattleReadyPokemon(preview)))

    return {"candidates": candidates}


@app.post("/api/battle/start")
def start_battle(req: StartBattleRequest):
    player = get_or_create_player(req.user_id, req.username)

    lead = _lead_or_400(player)

    if req.target_species:
        if journey.ensure_story(player)["mode"] == "journey" and not journey.current_encounter(player):
            raise HTTPException(400, "No wild Pokémon here — travel to a route first.")
        species = req.target_species
        level = req.target_level or lead.level
    else:
        species, level = _roll_encounter(req.route_id, lead.level, player)
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
            fighter = player_mon._p
            is_boss = bool(record["wild_pokemon"].get("is_boss"))
            is_gym = bool(record["wild_pokemon"].get("gym_floor"))
            story_ref = record["wild_pokemon"].get("story_ref")

            if story_ref:
                # Story trainer (gym leader / rival / Elite Four / Champion): XP for every Pokemon beaten
                xp = 25 * wild_mon.level
                exp = boss_battle.award_battle_xp(player, fighter, xp, req.use_exp_all,
                                                  flag=player.story.get("progress"))
                nxt = journey.next_opponent(player, story_ref["t"], story_ref["i"])
                if nxt:
                    opp, meta = nxt
                    persist_player(player)
                    _sessions.save(req.battle_id, record["user_id"], fighter.to_dict(), opp.to_dict())
                    response.update({
                        "is_finished": False,
                        "winner": None,
                        "player_pokemon": serialize_pokemon(BattleReadyPokemon(fighter)),
                        "wild_pokemon": serialize_pokemon(BattleReadyPokemon(opp)),
                        "xp_gained": xp,
                        "exp_all": exp,
                        "team": [serialize_pokemon(p) for p in player.active_team],
                        "inventory": boss_battle.public_inventory(player),
                        "pokeballs": dict(player.pokeballs),
                        "story": {"advanced": True, "name": meta["name"], "idx": meta["idx"], "size": meta["size"]},
                    })
                    response["log"] = list(response["log"]) + [f"{meta['name']} sent out {opp.species_name.upper()}!"]
                    return response
                won = journey.trainer_won(player, story_ref["t"])
                response["story"] = won
                response["xp_gained"] = xp
                response["coins_gained"] = won["coins"]
                response["exp_all"] = exp
                response["team"] = [serialize_pokemon(p) for p in player.active_team]
                response["inventory"] = boss_battle.public_inventory(player)
                response["pokeballs"] = dict(player.pokeballs)
                response["player_pokemon"] = serialize_pokemon(BattleReadyPokemon(fighter))
                response["log"] = list(response["log"]) + [won["win"]]
            elif is_gym:
                # Battle Gym: no XP, but BP + credits, and the whole team is patched up
                for i, m in enumerate(player.active_team):
                    if m.id == fighter.id:
                        player.active_team[i] = fighter
                        break
                won = gym_system.floor_won(player)
                fighter.restore_hp()
                response["gym"] = {**won, "run_over": False, "leader": gym_system.is_leader_floor(won["floor_cleared"])}
                response["xp_gained"] = 0
                response["coins_gained"] = won["coins"]
                response["exp_all"] = {"used": False, "per_pokemon": 0, "pokemon_count": 0, "level_ups": []}
                response["team"] = [serialize_pokemon(p) for p in player.active_team]
                response["inventory"] = boss_battle.public_inventory(player)
                response["pokeballs"] = dict(player.pokeballs)
                response["player_pokemon"] = serialize_pokemon(BattleReadyPokemon(fighter))
            elif is_boss:
                # HP lost by the fighter, measured BEFORE xp (a level-up restores HP)
                lost = 1 - (fighter.current_hp / max(1, fighter.max_hp))
                tmpl = daily_boss_system.get_daily_boss()
                # rewards are based on the level that was actually fought (scaled), not the template's
                boss_template = DailyBoss(tmpl.species, wild_mon.level, tmpl.moves, tmpl.ability, tmpl.nature)
                won = boss_battle.boss_victory(player, boss_template, lost)
                xp, coins = won["xp"], won["coins"]   # coins already added by boss_victory
                response["boss"] = {"defeated": True, "flawless": won["flawless"], "items": won["items"]}
            else:
                xp = 20 * wild_mon.level
                coins = CurrencySystem().calculate_catch_reward(wild_mon.level)
                player.add_coins(coins)

            if not is_gym and not story_ref:
                exp = boss_battle.award_battle_xp(player, fighter, xp, req.use_exp_all)
                response["xp_gained"] = xp
                response["coins_gained"] = coins
                response["exp_all"] = exp
                response["team"] = [serialize_pokemon(p) for p in player.active_team]
                response["inventory"] = boss_battle.public_inventory(player)
                response["pokeballs"] = dict(player.pokeballs)
                response["player_pokemon"] = serialize_pokemon(BattleReadyPokemon(fighter))
        else:
            player_mon._p.is_fainted = True
            for i, p in enumerate(player.active_team):
                if p.id == player_mon._p.id:
                    player.active_team[i] = player_mon._p
                    break
            if record["wild_pokemon"].get("story_ref"):
                response["story"] = journey.trainer_lost(player)
                response["team"] = [serialize_pokemon(p) for p in player.active_team]
                response["inventory"] = boss_battle.public_inventory(player)
                response["pokeballs"] = dict(player.pokeballs)
            if record["wild_pokemon"].get("gym_floor"):
                lost = gym_system.floor_lost(player)
                response["gym"] = lost
                response["team"] = [serialize_pokemon(p) for p in player.active_team]
                response["inventory"] = boss_battle.public_inventory(player)
                response["pokeballs"] = dict(player.pokeballs)
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

    if record["wild_pokemon"].get("is_boss"):
        raise HTTPException(400, "The daily boss can't be caught — defeat it for rewards instead.")
    if record["wild_pokemon"].get("gym_floor") or record["wild_pokemon"].get("story_ref"):
        raise HTTPException(400, "A trainer's Pokémon can't be caught.")

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
    if record["wild_pokemon"].get("story_ref"):
        return {"success": False, "message": "You can't run from a trainer battle!"}
    if record["wild_pokemon"].get("gym_floor"):
        # leaving a gym fight forfeits the run (always succeeds)
        player = get_or_create_player(record["user_id"])
        result = gym_system.end_run(player)
        persist_player(player)
        _sessions.delete(req.battle_id)
        return {"success": True, "gym": result}
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


class CandyRequest(BaseModel):
    user_id: int
    pokemon_id: str


@app.get("/api/routes")
def list_routes(region: Optional[str] = None):
    """Hunting routes with level ranges, easiest first. ?region=kanto narrows to one region."""
    return {"routes": EncounterSystem.list_routes(region)}


@app.get("/api/boss/today")
def boss_today(user_id: Optional[int] = None):
    """Today's boss. With ?user_id= it is scaled to that player and says whether
    today's reward has already been claimed."""
    template = daily_boss_system.get_daily_boss()
    info = daily_boss_system.get_boss_info()
    boss = template
    claimed = False
    if user_id is not None:
        player = get_or_create_player(user_id)
        lead = next((p for p in player.active_team if not p.is_fainted), None)
        lead_level = lead.level if lead else 5
        boss = boss_battle.scaled_boss(template, lead_level)
        claimed = boss_battle.is_claimed_today(player)
    return {
        "species": boss.species,
        "name": info["name"],
        "level": boss.level,
        "moves": info["moves"],
        "ability": AbilitySystem.display_name(boss.ability),
        "nature": boss.nature,
        "xp_reward": boss.xp_reward,
        "coin_reward": boss.coin_reward,
        "claimed_today": claimed,
        "day": today_key(),
    }


@app.post("/api/boss/start")
def boss_start(req: BossStartRequest):
    player = get_or_create_player(req.user_id, req.username)
    if boss_battle.is_claimed_today(player):
        raise HTTPException(400, "You already beat today's boss — a new one arrives at 00:00 UTC.")

    lead = _lead_or_400(player, "challenging the boss")

    boss_mon, boss = boss_battle.build_boss_pokemon(lead.level)
    player_mon = BattleReadyPokemon(lead)
    wild_mon = BattleReadyPokemon(boss_mon)

    battle_id = str(uuid.uuid4())
    _sessions.save(battle_id, req.user_id, lead.to_dict(), boss_mon.to_dict())

    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
        "log": [f"⚔️ DAILY BOSS: {boss_mon.species_name.upper()} Lv{boss_mon.level} blocks the way!"],
    }


@app.post("/api/party/rare-candy")
def party_rare_candy(req: CandyRequest):
    player = get_or_create_player(req.user_id)
    target = next((p for p in player.active_team if p.id == req.pokemon_id), None)
    if not target:
        raise HTTPException(404, "That Pokemon isn't on your team.")
    if target.level >= RareCandy.MAX_LEVEL:
        raise HTTPException(400, f"{target.species_name} is already at max level.")
    if not player.remove_item("rare_candy", 1):
        raise HTTPException(400, "No rare_candy left.")

    result = RareCandy.use(target)
    persist_player(player)
    return {
        "player_pokemon": serialize_pokemon(target),
        "remaining": player.inventory.get("rare_candy", 0),
        "old_level": result.get("old_level"),
        "new_level": result.get("new_level"),
    }


def _gym_status_payload(player) -> dict:
    return {**gym_system.status(player), "shop": gym_system.shop_catalog()}


@app.get("/api/gym/status")
def gym_status(user_id: int):
    return _gym_status_payload(get_or_create_player(user_id))


@app.post("/api/gym/enter")
def gym_enter(req: GymEnterRequest):
    """Start a run (floor 1) or fight the floor an active run is on. Also used for 'next floor'
    and for sending in your next Pokemon after one faints."""
    player = get_or_create_player(req.user_id, req.username)
    lead = _lead_or_400(player, "entering the gym")

    gym_system.start_or_resume(player)
    opp, meta = gym_system.build_opponent(player)
    persist_player(player)

    player_mon = BattleReadyPokemon(lead)
    wild_mon = BattleReadyPokemon(opp)
    battle_id = str(uuid.uuid4())
    _sessions.save(battle_id, req.user_id, lead.to_dict(), opp.to_dict())

    if meta["leader"]:
        intro = f"🏟️ {meta['gym'].upper()} GYM — Leader {meta['trainer']} sends out {opp.species_name.upper()} Lv{opp.level}!"
    else:
        intro = f"🏟️ Floor {meta['floor']}: {meta['trainer']} sends out {opp.species_name.upper()} Lv{opp.level}!"
    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
        "log": [intro],
        "gym": meta,
    }


@app.post("/api/gym/forfeit")
def gym_forfeit(req: GymEnterRequest):
    player = get_or_create_player(req.user_id, req.username)
    if not gym_system.in_run(player):
        raise HTTPException(400, "You're not in a gym run.")
    result = gym_system.end_run(player)
    persist_player(player)
    return {"gym": result, "team": [serialize_pokemon(p) for p in player.active_team]}


@app.post("/api/gym/shop/buy")
def gym_shop_buy(req: GymBuyRequest):
    player = get_or_create_player(req.user_id)
    err = gym_system.buy(player, req.item_id, req.quantity)
    if err:
        raise HTTPException(400, err)
    persist_player(player)
    return {
        "bp": gym_system.get_bp(player),
        "inventory": boss_battle.public_inventory(player),
        "pokeballs": dict(player.pokeballs),
    }


# ════════════════════════════════════════════════════════════════
# ACCOUNTS (username/password + Telegram link) and STARTER SELECTION
# ════════════════════════════════════════════════════════════════

STARTERS = onboarding.STARTERS


class RegisterRequest(BaseModel):
    username: str
    password: str


class TelegramPollRequest(BaseModel):
    code: str


class StarterRequest(BaseModel):
    user_id: int
    region: str
    species: str
    avatar: Optional[str] = None


class TravelRequest(BaseModel):
    user_id: int
    to: str


class JourneyActionRequest(BaseModel):
    user_id: int
    username: str = "OPERATOR"
    trainer_id: Optional[str] = None


def _auth_payload(info: dict) -> dict:
    player = get_or_create_player(info["user_id"], info["username"])
    return {
        "token": accounts.make_token(info["user_id"], info["username"]),
        "user_id": info["user_id"],
        "username": player.username or info["username"],
        "needs_starter": not player.active_team and not player.pokemon_collection,
    }


@app.post("/api/auth/register")
def auth_register(req: RegisterRequest):
    info = _accounts.create_account(req.username, req.password)
    return _auth_payload(info)


@app.post("/api/auth/login")
def auth_login(req: RegisterRequest):
    info = _accounts.authenticate(req.username, req.password)
    return _auth_payload(info)


@app.get("/api/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    claims = accounts.verify_token(authorization)
    if not claims:
        raise HTTPException(401, "Session expired — please log in again.")
    player = get_or_create_player(claims["uid"], claims["name"] or "TRAINER")
    return {
        "user_id": claims["uid"],
        "username": player.username or claims["name"],
        "needs_starter": not player.active_team and not player.pokemon_collection,
    }


@app.post("/api/auth/telegram/start")
def auth_telegram_start():
    started = _accounts.start_telegram_login()
    bot_username = (os.environ.get("BOT_USERNAME") or "").lstrip("@")
    return {
        "code": started["code"],
        "expires_in": started["expires_in"],
        "bot_url": f"https://t.me/{bot_username}?start=web_{started['code']}" if bot_username else None,
        "bot_username": bot_username or None,
    }


@app.post("/api/auth/telegram/poll")
def auth_telegram_poll(req: TelegramPollRequest):
    result = _accounts.poll_telegram_login(req.code)
    if result["status"] != "ok":
        return result
    return {"status": "ok", **_auth_payload({"user_id": result["user_id"], "username": result["username"]})}


@app.get("/api/starters")
def list_starters():
    return {
        "regions": {
            region: [{"species": sp, "pokedex_id": dex} for sp, dex in mons]
            for region, mons in STARTERS.items()
        }
    }


@app.post("/api/player/starter")
def choose_starter(req: StarterRequest):
    player = get_or_create_player(req.user_id)
    try:
        onboarding.create_player_with_starter(player, req.region, req.species, req.avatar)
    except onboarding.OnboardingError as e:
        raise HTTPException(400, str(e))
    persist_player(player)
    return get_roster(req.user_id)


@app.get("/api/avatars")
def list_avatars():
    return {"avatars": avatars.list_avatars()}


@app.get("/api/avatars/{avatar_id}.png")
def avatar_png(avatar_id: str, scale: int = 8):
    if not avatars.is_valid(avatar_id):
        raise HTTPException(404, "No such avatar.")
    return Response(
        content=avatars.render_png(avatar_id, scale),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ════════════════════════════════════════════════════════════════
# JOURNEY (towns, routes, story trainers)
# ════════════════════════════════════════════════════════════════

@app.get("/api/journey/state")
def journey_state(user_id: int):
    return journey.state(get_or_create_player(user_id))


@app.post("/api/journey/travel")
def journey_travel(req: TravelRequest):
    player = get_or_create_player(req.user_id)
    result = journey.travel(player, req.to)
    persist_player(player)
    return result


@app.post("/api/journey/heal")
def journey_heal(req: JourneyActionRequest):
    player = get_or_create_player(req.user_id)
    result = journey.heal(player)
    persist_player(player)
    return {**result, "team": [serialize_pokemon(p) for p in player.active_team]}


@app.post("/api/journey/trainer/start")
def journey_trainer_start(req: JourneyActionRequest):
    player = get_or_create_player(req.user_id, req.username)
    if not req.trainer_id:
        raise HTTPException(400, "Which trainer?")
    lead = _lead_or_400(player, "challenging a trainer")
    opp, meta = journey.start_trainer(player, req.trainer_id)
    persist_player(player)

    battle_id = str(uuid.uuid4())
    _sessions.save(battle_id, req.user_id, lead.to_dict(), opp.to_dict())
    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(BattleReadyPokemon(lead)),
        "wild_pokemon": serialize_pokemon(BattleReadyPokemon(opp)),
        "log": [f"{meta['name']}: \"{meta['intro']}\"", f"{meta['name']} sent out {opp.species_name.upper()}!"],
        "story": meta,
    }
