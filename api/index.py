"""
FastAPI app for POSHOW: players, battles, journey, trading, PvP and accounts.

Wraps the shared game logic in api/_lib and exposes it over HTTP. Deployed as the Vercel Python entrypoint or
run with uvicorn (see README.md and docs/DEPLOY.md).
"""

import logging
import os
import random
import sys
import uuid
from typing import Dict, Optional

import re
import requests
import http_client as dbhttp
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
from route_encounters import EncounterSystem, UnknownRoute      # noqa: E402
from pokemon_model import UnknownSpecies           # noqa: E402
from abilities_system import AbilitySystem        # noqa: E402
import boss_battle                                 # noqa: E402
import gym_system                                  # noqa: E402
import rules                                        # noqa: E402
import care                                         # noqa: E402
import admin_system                                 # noqa: E402
import evolution                                    # noqa: E402
import species_data                                  # noqa: E402
import storage as storage_box                       # noqa: E402
import progression                                  # noqa: E402
import pvp_system                                   # noqa: E402
import trade_system                                 # noqa: E402
import copy as _copy                                # noqa: E402
import scenes                                       # noqa: E402
import time as _time                                # noqa: E402
import accounts                                     # noqa: E402
import feedback as feedback_mod                     # noqa: E402
import avatars                                      # noqa: E402
import journey                                      # noqa: E402
import onboarding                                   # noqa: E402
from database import DatabaseError, ConcurrentUpdateError, SchemaError   # noqa: E402
from move_learning_system import get_moves_by_level  # noqa: E402

app = FastAPI(title="Terminal Battler Bridge")


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    logger.error(f"database error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "The database isn't answering right now — try again in a moment."},
    )


_CATCH_DATA_OK = True
try:                                   # data-quality check: every species needs a verified capture rate
    species_data.validate_capture_rates()
except ValueError as _e:
    _CATCH_DATA_OK = False
    logger.critical(f"❌ capture-rate validation failed: {_e}")
    if os.environ.get("RENDER") or os.environ.get("VERCEL") or os.environ.get("PRODUCTION"):
        raise RuntimeError(f"capture-rate data is incomplete — refusing to start in production: {_e}") from _e
    logger.warning("⚠️ development: starting anyway, catching is DISABLED until the data is fixed")


@app.exception_handler(ConcurrentUpdateError)
async def concurrent_update_handler(request: Request, exc: ConcurrentUpdateError):
    logger.warning(f"concurrent update on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=409,
        content={"detail": "Your game was changed in another window (website or Telegram) while this was happening. "
                           "Nothing was lost — reload and try again."},
    )


@app.exception_handler(UnknownSpecies)
async def unknown_species_handler(request: Request, exc: UnknownSpecies):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(UnknownRoute)
async def unknown_route_handler(request: Request, exc: UnknownRoute):
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0]) if exc.args else "Unknown route."})


@app.exception_handler(journey.JourneyError)
async def journey_error_handler(request: Request, exc: journey.JourneyError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(admin_system.AdminError)
async def admin_error_handler(request: Request, exc: admin_system.AdminError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(pvp_system.PvpError)
async def pvp_error_handler(request: Request, exc: pvp_system.PvpError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(trade_system.TradeError)
async def trade_error_handler(request: Request, exc: trade_system.TradeError):
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

# JSON responses (roster, Pokédex, journey…) are large and repetitive: compress them (free on a phone connection)
try:
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=800)
except ImportError:                      # the offline test stubs have no starlette
    pass


_ROUTE_ID = re.compile(r"/(\d+|[0-9a-f]{8}-[0-9a-f-]{27}|[A-Za-z0-9]{24,})(?=/|$)")
SLOW_REQUEST_MS = float(os.environ.get("SLOW_REQUEST_MS", "1500"))


class TimingMiddleware:
    """Pure ASGI: times every request, splits the time into database / lock-wait / the rest, adds a Server-Timing
    header (visible in the browser's network panel) and logs slow ones. Tokens and bodies are never logged."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        rec = dbhttp.start_request()
        route = _ROUTE_ID.sub("/:id", scope.get("path", ""))
        status = {"code": 500}

        async def send_with_timing(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                total = (_time.perf_counter() - rec["t0"]) * 1000
                value = (f'total;dur={total:.0f}, db;dur={rec["db_ms"]:.0f};desc="{rec["db_calls"]} calls", '
                         f'lock;dur={rec["lock_ms"]:.0f}')
                if rec.get("db_max_op"):
                    value += f', dbmax;dur={rec["db_max_ms"]:.0f};desc="{rec["db_max_op"]}"'
                message = {**message, "headers": list(message.get("headers", [])) + [(b"server-timing", value.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            total = (_time.perf_counter() - rec["t0"]) * 1000
            dbhttp.STATS.record_request(f'{scope.get("method", "GET")} {route}', total, status["code"])
            if total >= SLOW_REQUEST_MS:
                logger.warning(f'slow request {scope.get("method")} {route}: {total:.0f} ms '
                               f'(db {rec["db_ms"]:.0f} ms in {rec["db_calls"]} calls, lock wait {rec["lock_ms"]:.0f} ms) '
                               f'status {status["code"]}')


app.add_middleware(TimingMiddleware)

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

# On a real host the game must never quietly run in "memory mode" (everything vanishes whenever the server
# restarts or a serverless instance is recycled). Fail the deploy loudly instead.
if _db is None and (os.environ.get("RENDER") or os.environ.get("VERCEL")) and os.environ.get("ALLOW_MEMORY_MODE") != "1":
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY are not set on this host. Set them (see docs/DEPLOY.md), "
                       "or set ALLOW_MEMORY_MODE=1 to deliberately run without a database.")
if int(os.environ.get("WEB_CONCURRENCY", "1") or 1) > 1:
    logging.getLogger(__name__).warning("WEB_CONCURRENCY > 1: request locks are per process, so only the database version check protects across workers. Use 1 worker.")

_accounts = accounts.AccountService(SUPABASE_URL, SUPABASE_KEY) if _db else accounts.AccountService()

_MEMORY_PLAYERS: Dict[int, PlayerInstance] = {}


def get_or_create_player(user_id: int, username: str = "OPERATOR") -> PlayerInstance:
    if _db:
        player = _db.load_player(user_id)
        if player:
            care.tick(player)         # resting Pokémon earned some healing since last time
            return player
        # load_player() returned None => the database positively said "no such player" (every failure raises).
        player = _bootstrap_new_player(user_id, username)
        persist_player(player)        # a new player that could not be stored is an error, not a silent ghost
        return player

    if user_id not in _MEMORY_PLAYERS:
        _MEMORY_PLAYERS[user_id] = _bootstrap_new_player(user_id, username)
    care.tick(_MEMORY_PLAYERS[user_id])
    return _MEMORY_PLAYERS[user_id]


def _bootstrap_new_player(user_id: int, username: str) -> PlayerInstance:
    """A brand-new player starts with NO Pokemon — they pick a region and a starter first
    (POST /api/player/starter). The roster reports needs_starter until they do."""
    return PlayerInstance(user_id, username)


def persist_player(player: PlayerInstance, close_battles=None):
    """Save the player. `close_battles` = ids of battle sessions this save ends: with the Supabase store they are
    deleted inside the same transaction (one round trip, and a finished fight can never outlive its result);
    with any other store they are deleted right after the save."""
    ids = [b for b in (close_battles or []) if b]
    atomic = bool(ids) and _db is not None and isinstance(_sessions, SupabaseSessionStore)
    if _db:
        # saves the stats row (incl. active_team ids) AND the Pokémon rows that changed — see database.py
        saved = _db.save_player(player, close_battles=ids) if atomic else _db.save_player(player)
        if not saved:
            logger.error(f"persist_player: save failed for {player.user_id} (details logged above)")
            raise DatabaseError("player save failed")
    if ids and not atomic:
        for b in ids:
            _sessions.delete(b)


def _persist_and_close(player: PlayerInstance, battle_id: str, response: dict) -> None:
    """Save the player and end the battle session: one transaction with Supabase, save-then-close otherwise."""
    if isinstance(_sessions, SupabaseSessionStore):
        persist_player(player, close_battles=[battle_id])
    else:
        persist_player(player)
        _close_session(battle_id, response)


def persist_players(players, trade_doc: Optional[dict] = None, trade_store=None):
    """Save several players (and optionally a trade record) in ONE transaction: all or nothing, every row
    version-checked. Used wherever two accounts change together (trade settlement, PvP results)."""
    players = list(players)
    if _db:
        row = trade_store.atomic_row(trade_doc) if (trade_doc is not None and trade_store is not None and trade_store.remote) else None
        _db.save_players(players, trade_row=row, doc_table=getattr(trade_store, "table", "trades"))
        if trade_doc is not None and trade_store is not None and not trade_store.remote:
            trade_store.save(trade_doc)
    elif trade_doc is not None and trade_store is not None:
        trade_store.save(trade_doc)


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

    def mark_completed(self, battle_id: str, result: dict) -> None:
        """Record that this session's outcome is already in the player's saved data (used ONLY after a successful
        player save when the session could not be deleted), so a client retry gets the same answer back instead of
        the battle being resolved — and paid out — a second time."""
        raise NotImplementedError

    def in_battle(self, user_id: int, within_s: int = 600) -> bool:
        """True if this player has a battle that was touched in the last `within_s` seconds
        (older ones are abandoned tabs and must not lock the Care Center forever)."""
        raise NotImplementedError

    def purge_user(self, user_id: int) -> None:
        """One active battle per player: starting a new one discards any older session of theirs."""
        raise NotImplementedError

    def list_user(self, user_id: int) -> list:
        """Every session row of this player (finished-but-undeleted ones included), each with `_age_s` = seconds
        since it was last touched. Raises DatabaseError when it cannot be read."""
        raise NotImplementedError


class MemorySessionStore(SessionStore):
    """Local-dev-only. Does NOT survive across Vercel serverless instances."""

    def __init__(self):
        self._data: Dict[str, dict] = {}

    def save(self, battle_id, user_id, player_dict, wild_dict):
        _remember_battle_owner(battle_id, user_id)
        self._data[battle_id] = {
            "user_id": user_id, "player_pokemon": player_dict, "wild_pokemon": wild_dict, "_ts": _time.time(),
        }

    def mark_completed(self, battle_id, result):
        if battle_id in self._data:
            self._data[battle_id]["completed_at"] = _time.time()
            self._data[battle_id]["completion_result"] = result

    def in_battle(self, user_id, within_s=600):
        now = _time.time()
        return any(r["user_id"] == user_id and not r.get("completed_at") and now - r.get("_ts", 0) < within_s
                   for r in self._data.values())

    def list_user(self, user_id):
        now = _time.time()
        return [{**r, "battle_id": k, "_age_s": now - r.get("_ts", 0)} for k, r in self._data.items()
                if r["user_id"] == user_id]

    def load(self, battle_id):
        return self._data.get(battle_id)

    def purge_user(self, user_id):
        for k in [k for k, r in self._data.items() if r["user_id"] == user_id]:
            self._data.pop(k, None)

    def delete(self, battle_id):
        self._data.pop(battle_id, None)


class SupabaseSessionStore(SessionStore):
    """Raw REST calls against Supabase's PostgREST API — same pattern as _lib/database.py's SupabaseDB.

    Fails closed: save / delete / purge / load raise DatabaseError when the write or read did not demonstrably
    succeed, so a turn is never answered "ok" when its state wasn't stored (the next request would find the old
    state, or no battle at all)."""

    def __init__(self, url: str, key: str):
        self.url = url
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _ok(res) -> bool:
        return res.status_code in (200, 201, 204)

    def save(self, battle_id, user_id, player_dict, wild_dict):
        _remember_battle_owner(battle_id, user_id)
        payload = {
            "battle_id": battle_id,
            "user_id": user_id,
            "player_pokemon": player_dict,
            "wild_pokemon": wild_dict,
            "updated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        try:
            res = dbhttp.post(
                f"{self.url}/rest/v1/battle_sessions?on_conflict=battle_id",
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payload,
                timeout=10,
            )
        except requests.RequestException as e:
            logger.error(f"Failed to save battle session {battle_id}: {e}")
            raise DatabaseError(f"battle session save failed: {e}") from e
        if not self._ok(res):
            logger.error(f"❌ battle session save failed ({res.status_code}): {res.text}")
            raise DatabaseError(f"battle session save failed ({res.status_code}): {res.text[:300]}")

    def load(self, battle_id):
        """None only when the database answered and there is no such battle; any failure raises."""
        try:
            res = dbhttp.get(
                f"{self.url}/rest/v1/battle_sessions?battle_id=eq.{battle_id}",
                headers=self.headers,
                timeout=10,
            )
        except requests.RequestException as e:
            logger.error(f"Failed to load battle session {battle_id}: {e}")
            raise DatabaseError(f"battle session load failed: {e}") from e
        if res.status_code != 200:
            raise DatabaseError(f"battle session load failed ({res.status_code}): {res.text[:300]}")
        try:
            rows = res.json()
        except ValueError as e:
            raise DatabaseError("battle session load returned unreadable data") from e
        return rows[0] if rows else None

    def in_battle(self, user_id, within_s=600):
        """True/False only when the database answered; raises DatabaseError when it could not, so the caller
        fails safely instead of guessing."""
        since = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_time.time() - within_s))
        try:
            res = dbhttp.get(
                f"{self.url}/rest/v1/battle_sessions",
                params={"user_id": f"eq.{user_id}", "updated_at": f"gt.{since}", "completed_at": "is.null",
                        "select": "battle_id", "limit": "1"},
                headers=self.headers,
                timeout=10,
            )
        except requests.RequestException as e:
            raise DatabaseError(f"in_battle check failed: {e}") from e
        if res.status_code != 200:
            raise DatabaseError(f"in_battle check failed ({res.status_code}): {res.text[:300]}")
        try:
            return bool(res.json())
        except ValueError as e:
            raise DatabaseError("in_battle response was unreadable") from e

    def list_user(self, user_id):
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/battle_sessions", params={"user_id": f"eq.{user_id}"},
                               headers=self.headers, timeout=10)
        except requests.RequestException as e:
            raise DatabaseError(f"battle session list failed: {e}") from e
        if res.status_code != 200:
            raise DatabaseError(f"battle session list failed ({res.status_code}): {res.text[:300]}")
        rows, now = res.json(), _time.time()
        for r in rows:
            try:
                ts = _time.mktime(_time.strptime(str(r.get("updated_at", ""))[:19], "%Y-%m-%dT%H:%M:%S")) - _time.timezone
            except ValueError:
                ts = 0                                   # unreadable timestamp = treat as old
            r["_age_s"] = now - ts
        return rows

    def mark_completed(self, battle_id, result):
        try:
            res = dbhttp.patch(
                f"{self.url}/rest/v1/battle_sessions?battle_id=eq.{battle_id}",
                headers={**self.headers, "Prefer": "return=minimal"},
                json={"completed_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
                      "completion_result": result},
                timeout=10,
            )
        except requests.RequestException as e:
            raise DatabaseError(f"mark_completed failed: {e}") from e
        if not self._ok(res):
            raise DatabaseError(f"mark_completed failed ({res.status_code}): {res.text[:300]}")

    def _delete(self, query: str, what: str):
        last = None
        for _attempt in range(3):            # a delete is idempotent, so retrying is safe
            try:
                res = dbhttp.delete(f"{self.url}/rest/v1/battle_sessions?{query}", headers=self.headers, timeout=10)
                if self._ok(res):
                    return
                last = f"{res.status_code}: {res.text[:200]}"
            except requests.RequestException as e:
                last = str(e)
        logger.error(f"Failed to {what}: {last}")
        raise DatabaseError(f"could not {what}: {last}")

    def purge_user(self, user_id):
        self._delete(f"user_id=eq.{user_id}", f"purge battle sessions for {user_id}")

    def delete(self, battle_id):
        self._delete(f"battle_id=eq.{battle_id}", f"delete battle session {battle_id}")


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
    encounter_token: Optional[str] = None       # proves target_species/level came from this player's own scan
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
    **evolution.SHOP_PRICES,
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


def serialize_move(move_name: str, pp_used: Optional[dict] = None) -> dict:
    d = rules.move_info(move_name)
    key = move_name.lower().replace("_", "-")
    left = (pp_used or {}).get(key, d["pp"])
    return {
        "id": move_name,
        "name": move_name.upper().replace("-", " "),
        "type": d["t"],
        "power": d["p"],
        "accuracy": d["a"] or 100,
        "category": {"p": "physical", "s": "special", "x": "status"}[d["c"]],
        "pp": left,
        "max_pp": d["pp"],
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
        "xp_to_next": rules.xp_to_next(underlying.level),
        "types": _extract_types(p),
        "moves": [serialize_move(m, (getattr(underlying, "bt", None) or {}).get("pp")) for m in underlying.moves],
        "status": getattr(underlying, "status", None),
        "stages": {k: v for k, v in ((getattr(underlying, "bt", None) or {}).get("stages") or {}).items() if v},
        "is_shiny": getattr(underlying, "is_shiny", False),
        "is_fainted": getattr(underlying, "is_fainted", underlying.current_hp <= 0),
        # National dex number from PokeAPI — lets the frontend build a real
        # sprite URL instead of a placeholder. None if api_data wasn't fetched.
        "pokedex_id": api_data.get("id"),
        "ability": AbilitySystem.display_name(getattr(underlying, "ability", None)),
        "ability_desc": AbilitySystem.describe(getattr(underlying, "ability", None)),
        "is_boss": bool(getattr(underlying, "is_boss", False)),
        "gym_floor": int(getattr(underlying, "gym_floor", 0) or 0),
        "pending_moves": list(getattr(underlying, "pending_moves", []) or []),
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


if hasattr(app, "on_event"):
    @app.on_event("startup")
    def _warm_up():
        """Open the pooled connection to the database before the first player arrives (TLS handshake + a cheap query)."""
        if not _db:
            return
        try:
            dbhttp.get(f"{SUPABASE_URL}/rest/v1/players?select=user_id&limit=1",
                       headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=8)
        except Exception as e:                 # noqa: BLE001 — warming is best effort
            logger.info(f"warm-up skipped: {e}")


@app.get("/api/metrics")
def metrics(authorization: Optional[str] = Header(default=None)):
    """Request timing since this process started (p50/p95/p99 per route, database and lock-wait time). Admin only."""
    _require_admin(authorization)
    return {**dbhttp.STATS.summary(), "caches": {c.name: c.stats() for c in (_assets_cache, _leaderboard_cache)}}


def _rpc_admin(name: str, body: dict):
    """Call an admin-only database function. A missing function or a database error is reported, never guessed."""
    if not _db:
        raise HTTPException(503, "No database configured.")
    res = dbhttp.post(f"{SUPABASE_URL}/rest/v1/rpc/{name}",
                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
                      json=body, timeout=15)
    if res.status_code == 404 or "PGRST202" in (res.text or ""):
        raise HTTPException(503, f"{name}() is not installed — re-run database/schema.sql.")
    if res.status_code != 200:
        raise HTTPException(503, f"{name}() failed ({res.status_code}): {(res.text or '')[:200]}")
    return res.json()


@app.get("/api/admin/db-health")
def admin_db_health(authorization: Optional[str] = Header(default=None)):
    """Database-side numbers: connections, lock waits, cache hit ratio, scan statistics, slowest statements."""
    _require_admin(authorization)
    return _rpc_admin("db_health", {})


@app.get("/api/admin/db-explain")
def admin_db_explain(name: str, user_id: int = 0, authorization: Optional[str] = Header(default=None)):
    """Execution plan (EXPLAIN ANALYZE) of one named hot query, for a real player id."""
    _require_admin(authorization)
    return _rpc_admin("db_explain", {"p_name": name, "p_user_id": int(user_id)})


@app.get("/api/ready")
def ready():
    """READINESS (unlike /health, which is liveness only): a bounded, read-only database query plus a data check.
    200 = persistence is reachable; 503 = degraded. Use this for deploy verification, not for keep-alive pings."""
    import species_data
    problems = []
    if _db is None:
        problems.append("no database configured: running in memory mode (progress is lost on restart)")
    else:
        try:
            res = dbhttp.get(f"{SUPABASE_URL}/rest/v1/players?select=user_id&limit=1",
                               headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=5)
            if res.status_code != 200:
                problems.append(f"database answered {res.status_code}: {res.text[:120]}")
        except requests.RequestException as e:
            problems.append(f"database unreachable: {e}")
    problems += species_data.LOAD_ERRORS
    body = {"ok": not problems, "problems": problems}
    return body if not problems else JSONResponse(status_code=503, content=body)


_DIAGNOSE_TABLES = {
    "identity_links": ["alias_id", "user_id", "kind"],
    "feedback": ["id", "user_id", "username", "category", "message", "context", "status", "created_at"],
    "players": ["user_id", "username", "created_date", "level", "experience", "coins", "wins", "losses", "elo",
                "current_streak", "current_region", "regions_unlocked", "pokemon_caught", "pokedex_seen",
                "inventory", "pokeballs", "login_streak", "badges", "achievements", "referral_code",
                "successful_referrals", "active_team", "avatar", "story", "version"],
    "pokemon": ["id", "player_id", "species_name", "nickname", "level", "trainer_id", "current_hp", "max_hp",
                "experience", "iv", "ev", "nature", "moves", "status", "is_fainted", "is_shiny", "pending_moves"],
    "battle_sessions": ["battle_id", "user_id", "player_pokemon", "wild_pokemon", "completed_at", "completion_result"],
    "login_codes": ["code", "user_id", "username", "expires_at", "link_user_id"],
    "site_assets": ["key", "url"],
    "pvp_matches": ["id", "user_a", "user_b", "status", "state", "ts"],
    "trades": ["id", "user_a", "user_b", "status", "state", "ts"],
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
            res = dbhttp.get(
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
    # the atomic save function must exist (an empty call is rejected by the function itself and writes nothing)
    try:
        res = dbhttp.post(
            f"{SUPABASE_URL}/rest/v1/rpc/save_player_atomic",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"p_player": {}, "p_pokemon": [], "p_expected_version": None}, timeout=15)
        if res.status_code == 404 or "PGRST202" in (res.text or ""):
            problems.append("function save_player_atomic() is missing — player saves are not atomic until schema.sql is run")
        res2 = dbhttp.post(
            f"{SUPABASE_URL}/rest/v1/rpc/save_players_atomic",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"p_batch": [], "p_trade": None}, timeout=15)
        if res2.status_code == 404 or "PGRST202" in (res2.text or ""):
            problems.append("function save_players_atomic() is missing — trades can't settle atomically until schema.sql is run")
        res4 = dbhttp.post(
            f"{SUPABASE_URL}/rest/v1/rpc/load_player_bundle",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"p_user_id": 0}, timeout=15)
        if res4.status_code == 404 or "PGRST202" in (res4.text or ""):
            problems.append("function load_player_bundle() is missing — players load in two requests (slower) until schema.sql is re-run")
        res3 = dbhttp.post(
            f"{SUPABASE_URL}/rest/v1/rpc/link_identity",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"p_code": "", "p_telegram_id": 0, "p_tg_name": "", "p_keep": None}, timeout=15)
        if res3.status_code == 404 or "PGRST202" in (res3.text or ""):
            problems.append("function link_identity() is missing — web/Telegram account linking is off until schema.sql is run")
    except requests.RequestException as e:
        problems.append(f"save_player_atomic: couldn't reach Supabase ({e})")
    import species_data as _sd
    problems += list(_sd.LOAD_ERRORS)
    return {
        "ok": not problems,
        "database": True,
        "problems": problems,
        "fix": None if not problems else
               "Run database/schema.sql in the Supabase SQL editor (safe to re-run), then reload this page.",
    }


@app.get("/api/player/{user_id}/roster")
def get_roster(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    player = get_or_create_player(user_id)
    return {
        "user_id": player.user_id,
        "username": player.username,
        "coins": player.coins,
        "level": player.level,
        "team": [{**serialize_pokemon(p), "condition": care.condition(player, p),
                  "evolutions": evolution.options(player, p)} for p in player.active_team],
        "collection_count": len(player.pokemon_collection),
        "pokeballs": player.pokeballs,
        "inventory": boss_battle.public_inventory(player),
        "needs_starter": not player.active_team and not player.pokemon_collection,
        "region": player.current_region,
        "avatar": player.avatar,
        "resting_count": len(care.resting(player)),
        "pokedex": _pokedex_payload(player),
        "storage": [{**serialize_pokemon(p), "condition": care.condition(player, p)}
                    for p in player.pokemon_collection if not care.is_resting(player, p)][:60],
    }


# ON by default. Set REQUIRE_AUTH=0 only for local development without logging in.
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "1") != "0"

# State-changing requests are read-modify-write on a player. Two at once (a double-tap, a second tab, a script)
# could both read "100 credits" and both spend them, or both finish the same battle. The API therefore handles
# one state-changing request at a time per process (run a single worker — Render's default). Reads aren't locked.
import threading as _threading
import functools as _functools
import contextlib as _contextlib
from collections import OrderedDict as _OrderedDict


class _KeyedLocks:
    """One re-entrant lock per key (a player, a battle, a trade, a duel) instead of one lock for everybody.
    Several keys are always taken in sorted order, so two requests can never wait on each other in a cycle.
    This only serialises requests inside THIS process; the database version check (save_player_atomic) is what
    protects against the website, the Telegram bot and other processes."""

    def __init__(self):
        self._mutex = _threading.Lock()
        self._locks = {}                      # key -> [RLock, users]

    @_contextlib.contextmanager
    def hold(self, *keys):
        keys = sorted({k for k in keys if k})
        entries = []
        t0 = _time.perf_counter()
        with self._mutex:
            for k in keys:
                e = self._locks.setdefault(k, [_threading.RLock(), 0])
                e[1] += 1
                entries.append((k, e))
        acquired = []
        try:
            for _k, e in entries:
                e[0].acquire()
                acquired.append(e)
            waited = (_time.perf_counter() - t0) * 1000
            rec = dbhttp.CURRENT.get()
            if rec is not None:
                rec["lock_ms"] += waited
            dbhttp.STATS.record_lock(waited)
            yield
        finally:
            for e in reversed(acquired):
                e[0].release()
            with self._mutex:
                for k, e in entries:
                    e[1] -= 1
                    if e[1] <= 0:
                        self._locks.pop(k, None)


_locks = _KeyedLocks()

# battle_id -> owner, so a battle request also takes its player's lock (start_battle / abandon take that lock too)
_BATTLE_OWNER: "_OrderedDict[str, int]" = _OrderedDict()


def _remember_battle_owner(battle_id: str, user_id: int) -> None:
    _BATTLE_OWNER[battle_id] = int(user_id)
    _BATTLE_OWNER.move_to_end(battle_id)
    while len(_BATTLE_OWNER) > 5000:
        _BATTLE_OWNER.popitem(last=False)


def _lock_keys(args, kwargs):
    req = kwargs.get("req") if "req" in kwargs else (args[0] if args else None)
    keys = []
    uid = getattr(req, "user_id", None)
    if uid is not None:
        keys.append(f"u:{int(uid)}")
    bid = getattr(req, "battle_id", None)
    if bid:
        keys.append(f"b:{bid}")
        owner = _BATTLE_OWNER.get(bid)
        if owner is not None:
            keys.append(f"u:{owner}")
    for attr, tag in (("trade_id", "t"), ("match_id", "m")):
        v = getattr(req, attr, None)
        if v:
            keys.append(f"{tag}:{v}")
    return keys


def _serialized(fn):
    """Serialise state-changing endpoints per player / battle / trade / duel (never globally)."""
    @_functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _locks.hold(*_lock_keys(args, kwargs)):
            return fn(*args, **kwargs)
    return wrapper


def _check_user(authorization: Optional[str], user_id: int):
    """With REQUIRE_AUTH=1 every endpoint that touches a player verifies the signed login token and that it
    belongs to that player — the user_id in a request body is never trusted on its own."""
    if not REQUIRE_AUTH:
        return
    claims = accounts.verify_token(authorization if isinstance(authorization, str) else None)
    if not claims:
        raise HTTPException(401, "Log in first.")
    if claims["uid"] != int(user_id):
        raise HTTPException(403, "That isn't your account.")
    if _accounts.is_alias(claims["uid"]):
        # this id was merged into another player: the old session must not create a ghost player
        raise HTTPException(401, "Your account was linked — please log in again.")


def _lead_or_400(player, action: str = "scanning again"):
    lead = next((p for p in player.active_team if not p.is_fainted and p.current_hp > 0), None)
    if lead:
        return lead
    if not player.active_team:
        if player.pokemon_collection:
            raise HTTPException(400, "No Pokémon on your team — take one out of its Poké Ball in the Care Center.")
        raise HTTPException(400, "Choose your starter Pokémon first.")
    raise HTTPException(400, f"Your whole team has fainted — heal up before {action}.")


@app.post("/api/encounter/scout")
@_serialized
def encounter_scout(req: ScoutRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
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
        entry = serialize_pokemon(BattleReadyPokemon(preview))
        entry["token"] = accounts.make_encounter_token(req.user_id, species, level)
        candidates.append(entry)

    return {"candidates": candidates}


@app.post("/api/battle/start")
@_serialized
def start_battle(req: StartBattleRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    player = get_or_create_player(req.user_id, req.username)

    # (an unfinished older battle's damage is applied to the team first, so the new fight starts from real HP)
    old = _sessions.list_user(req.user_id)          # read once: used now (carry damage) and again below (delete)
    for _r in old:
        if not _r.get("completed_at"):
            _sync_session_into_player(player, _r)
    lead = _lead_or_400(player)

    if req.target_species:
        if journey.ensure_story(player)["mode"] == "journey" and not journey.current_encounter(player):
            raise HTTPException(400, "No wild Pokémon here — travel to a route first.")
        # the client may only fight a Pokémon the SERVER offered it (signed scan result) — never one it names itself
        verified = accounts.verify_encounter_token(req.encounter_token, req.user_id)
        if not verified or verified[0] != (req.target_species or "").lower() or verified[1] != (req.target_level or verified[1]):
            raise HTTPException(403, "That encounter wasn't offered to you — scan the area again.")
        species, level = verified
        token_id = accounts.encounter_token_id(req.encounter_token)
        used = player.story.setdefault("enc_used", []) if isinstance(player.story, dict) else []
        if token_id and token_id in used:
            raise HTTPException(403, "That encounter was already used — scan the area again.")
    else:
        species, level = _roll_encounter(req.route_id, lead.level, player)
        token_id = None
    wild = PokemonInstance(species, level, trainer_id=0)
    try:                       # where this fight happens (Dive Ball / Dusk Ball rules); session-only state
        _route_here = journey.current_encounter(player) or req.route_id
        import route_data as _rd
        wild.bt = {"loc": _rd.terrain_flags(_route_here), "turn": 0}
    except Exception as e:     # noqa: BLE001 — terrain is a bonus, never block a battle
        logger.warning(f"terrain lookup failed: {e}")

    player_mon = BattleReadyPokemon(lead)
    wild_mon = BattleReadyPokemon(wild)

    battle_id = str(uuid.uuid4())
    # Leaving an older fight (reload, new scan) keeps the damage it dealt, and a scan result can start only ONE battle:
    # both are saved together BEFORE anything is deleted, so a failed save changes nothing.
    if token_id and isinstance(player.story, dict):
        used = player.story.setdefault("enc_used", [])
        used.append(token_id)
        del used[:-40]                         # tokens expire in minutes; remember the recent ones
    if old or token_id:
        persist_player(player, close_battles=[r["battle_id"] for r in old])
    _sessions.save(battle_id, req.user_id, lead.to_dict(), wild.to_dict())

    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
        "log": [f"A wild {wild.species_name.upper()} appeared!"],
    }


def _free_enemy_turn(record: dict, player_dict: dict):
    """The opponent acts while the player does something that isn't an attack (use an item, fail to run, switch).
    Uses the engine's one-sided turn (`execute_turn(None, move)`). Returns (record_for_state, player_mon, wild_mon, result)."""
    rec = {**record, "player_pokemon": player_dict}
    battle, player_mon, wild_mon = _rebuild_battle(rec)
    result = battle.execute_turn(None, battle.get_opponent_move())
    player_mon._p.current_hp = max(0, battle.player_hp)
    wild_mon._p.current_hp = max(0, battle.wild_hp)
    _old_bt = record["wild_pokemon"].get("bt") or {}
    wild_mon._p.bt = {**(wild_mon._p.bt or {}), "loc": _old_bt.get("loc") or {}, "turn": int(_old_bt.get("turn", 0) or 0) + 1}
    return rec, player_mon, wild_mon, result


def _turn_log(result: dict) -> list:
    return [l for l in result["log"] if not str(l).startswith("\nTurn")]


def _close_session(battle_id: str, response: dict) -> None:
    """Called ONLY after the player was saved successfully. The outcome is already durable, so nothing here may
    turn the answer into an error: if the session can't be deleted we mark it completed (a retry then replays
    `response` instead of paying out again); if even that fails we log loudly and still answer."""
    try:
        _sessions.delete(battle_id)
        return
    except DatabaseError as e:
        logger.error(f"battle {battle_id}: finished and saved, but the session could not be deleted: {e}")
    try:
        _sessions.mark_completed(battle_id, response)
    except DatabaseError as e:
        logger.critical(f"battle {battle_id}: could not delete OR mark the finished session — a retry could be "
                        f"resolved twice until it expires: {e}")


def _already_completed(record: dict):
    """The cached answer if this session already finished (client retry), else None."""
    if record.get("completed_at") and record.get("completion_result") is not None:
        return record["completion_result"]
    return None


def _after_turn(battle_id: str, use_exp_all: bool, record: dict, player_mon, wild_mon, result: dict, response: dict) -> dict:
    """Everything that follows a resolved turn: finish the battle (rewards / loss, ONE save, then drop the session)
    or store the new state. Shared by /battle/move and /battle/switch (a voluntary switch costs the turn)."""
    if result["is_finished"]:
        player = get_or_create_player(record["user_id"])
        player_mon._p.bt = None           # PP / stat stages only live for one battle (status stays)
        wild_mon._p.bt = None
        if result["winner"] == "player":
            player.wins += 1
            player.current_streak += 1
            player.add_experience(5 + wild_mon.level // 2)      # trainer level / profile progression (ELO is PvP-only)
        else:
            player.losses += 1
            player.current_streak = 0
        if result["winner"] == "player":
            fighter = player_mon._p
            is_boss = bool(record["wild_pokemon"].get("is_boss"))
            is_gym = bool(record["wild_pokemon"].get("gym_floor"))
            story_ref = record["wild_pokemon"].get("story_ref")

            if story_ref:
                # Story trainer (gym leader / rival / Elite Four / Champion): XP for every Pokemon beaten
                xp = rules.battle_xp(wild_mon.level, trainer=True)
                exp = boss_battle.award_battle_xp(player, fighter, xp, use_exp_all,
                                                  flag=player.story.get("progress"))
                nxt = journey.next_opponent(player, story_ref["t"], story_ref["i"])
                if nxt:
                    opp, meta = nxt
                    persist_player(player)
                    _sessions.save(battle_id, record["user_id"], fighter.to_dict(), opp.to_dict())
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
                    response["evolution_pending"] = progression.pending(player)
                    response["moves_learned"] = progression.move_events(player)
                    response["move_learning"] = progression.pending_moves(player)
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
                # HP lost by the fighter, measured BEFORE xp (a level-up also raises current HP by the max-HP gain)
                lost = 1 - (fighter.current_hp / max(1, fighter.max_hp))
                tmpl = daily_boss_system.get_boss_for_tier(int(record["wild_pokemon"].get("boss_tier", 3)))
                # rewards are based on the level that was actually fought (scaled), not the template's
                boss_template = DailyBoss(tmpl.species, wild_mon.level, tmpl.moves, tmpl.ability, tmpl.nature)
                won = boss_battle.boss_victory(player, boss_template, lost)
                xp, coins = won["xp"], won["coins"]   # coins already added by boss_victory
                response["boss"] = {"defeated": True, "flawless": won["flawless"], "items": won["items"]}
            else:
                xp = rules.battle_xp(wild_mon.level)
                coins = CurrencySystem().calculate_catch_reward(wild_mon.level)
                player.add_coins(coins)

            if not is_gym and not story_ref:
                exp = boss_battle.award_battle_xp(player, fighter, xp, use_exp_all)
                response["xp_gained"] = xp
                response["coins_gained"] = coins
                response["exp_all"] = exp
                response["team"] = [serialize_pokemon(p) for p in player.active_team]
                response["inventory"] = boss_battle.public_inventory(player)
                response["pokeballs"] = dict(player.pokeballs)
                response["player_pokemon"] = serialize_pokemon(BattleReadyPokemon(fighter))
        else:
            for i, p in enumerate(player.active_team):
                if p.id == player_mon._p.id:
                    player.active_team[i] = player_mon._p
                    break
            response["condition"] = care.on_faint(player, player_mon._p)
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
        response["evolution_pending"] = progression.pending(player)
        response["moves_learned"] = progression.move_events(player)
        response["move_learning"] = progression.pending_moves(player)
        _persist_and_close(player, battle_id, response)    # raises (503) when it could not be saved
    else:
        _sessions.save(battle_id, record["user_id"], player_mon._p.to_dict(), wild_mon._p.to_dict())

    return response


@app.post("/api/battle/move")
@_serialized
def battle_move(req: MoveRequest, authorization: Optional[str] = Header(default=None)):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    _check_user(authorization, record["user_id"])
    if (cached := _already_completed(record)) is not None:
        return cached

    battle, player_mon, wild_mon = _rebuild_battle(record)

    available = battle.get_player_moves()
    if not available:
        raise HTTPException(500, "This Pokemon has no usable moves — can't resolve a turn.")
    wanted = req.move_name.lower().replace("_", "-")
    move = next((m for m in available if m.name.lower().replace("_", "-") == wanted), None)
    if move is None:
        # never guess: silently playing a different move than the one pressed is how "my Pokémon did nothing" happens
        raise HTTPException(400, f"{req.move_name} isn't one of this Pokémon's moves.")
    opponent_move = battle.get_opponent_move()
    result = battle.execute_turn(move, opponent_move)

    player_mon._p.current_hp = max(0, battle.player_hp)
    wild_mon._p.current_hp = max(0, battle.wild_hp)
    # remember how many turns have been fought (Quick / Timer Ball need it); lives in the session only
    _old_bt = record["wild_pokemon"].get("bt") or {}
    wild_mon._p.bt = {**(wild_mon._p.bt or {}), "loc": _old_bt.get("loc") or {},
                      "turn": int(_old_bt.get("turn", 0) or 0) + 1}

    response = {
        "log": result["log"],
        "is_finished": result["is_finished"],
        "winner": result["winner"],
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
    }

    return _after_turn(req.battle_id, req.use_exp_all, record, player_mon, wild_mon, result, response)


@app.post("/api/battle/catch")
@_serialized
def battle_catch(req: CatchRequest, authorization: Optional[str] = Header(default=None)):
    if not _CATCH_DATA_OK:
        raise HTTPException(503, "Catching is disabled until the species capture-rate data is fixed.")
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    _check_user(authorization, record["user_id"])
    if (cached := _already_completed(record)) is not None:
        return cached

    if record["wild_pokemon"].get("is_boss"):
        raise HTTPException(400, "The daily boss can't be caught — defeat it for rewards instead.")
    if record["wild_pokemon"].get("gym_floor") or record["wild_pokemon"].get("story_ref"):
        raise HTTPException(400, "A trainer's Pokémon can't be caught.")

    player = get_or_create_player(record["user_id"])
    if not player.use_pokeball(req.ball_type):
        raise HTTPException(400, f"No {req.ball_type} left.")

    wild = PokemonInstance.from_dict(record["wild_pokemon"])
    hp_percent = wild.current_hp / max(1, wild.max_hp)
    catch_rate = int((wild.api_data or {}).get("catch_rate", 45))     # per-species (see species_data.catch_rate)
    elapsed = int(((record["wild_pokemon"].get("bt") or {}).get("turn", 0)) or 0)      # turns fought so far
    lead = next((m for m in player.active_team if not m.is_fainted), None)
    result = CatchSystem().calculate_catch_chance(
        pokemon_hp_percent=hp_percent,
        pokemon_level=wild.level,
        pokemon_catch_rate=catch_rate,
        ball_type=req.ball_type,
        turn=elapsed + 1,
        is_first_turn=(elapsed == 0),
        is_water_location=bool(((record["wild_pokemon"].get("bt") or {}).get("loc") or {}).get("water")),
        is_cave_location=bool(((record["wild_pokemon"].get("bt") or {}).get("loc") or {}).get("cave")),
        status=getattr(wild, "status", None),
        is_status=bool(getattr(wild, "status", None)),
        player_level=lead.level if lead else 1,
        already_caught=any(m.species_name == wild.species_name for m in player.pokemon_collection),
        species_name=wild.species_name,
        base_speed=int(((wild.api_data or {}).get("base_stats") or {}).get("speed", 0) or 0),
        types=_type_names((wild.api_data or {}).get("types", [])),
    )

    caught = None
    if result["will_catch"]:
        wild.bt = None
        player.catch_pokemon(wild)
        caught = wild

    out = {**result, "battle_id": req.battle_id, "remaining_balls": player.pokeballs.get(req.ball_type, 0)}
    if caught is not None:
        out.update({
            "caught": serialize_pokemon(caught),
            "collection_count": len(player.pokemon_collection),
            "pokedex": _pokedex_payload(player),
        })
    if caught is not None:
        _persist_and_close(player, req.battle_id, out)       # raises (503) if it could not be saved
        return out
    persist_player(player)          # raises (503) if it could not be saved — a throw is never reported unsaved
    # A failed throw is a full turn: the ball is spent (saved above), then the wild Pokémon acts — it can hit,
    # and it can win. The turn counter advances inside that same step (Quick Ball's bonus is first-turn only).
    # If anything after the save fails the player loses a ball but never gets a free throw.
    rec, player_mon, wild_mon, tr = _free_enemy_turn(record, record["player_pokemon"])
    turn = {
        "log": _turn_log(tr),
        "is_finished": tr["is_finished"],
        "winner": tr["winner"],
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
    }
    out["turn"] = _after_turn(req.battle_id, False, rec, player_mon, wild_mon, tr, turn)
    return out


@app.post("/api/battle/flee")
@_serialized
def battle_flee(req: FleeRequest, authorization: Optional[str] = Header(default=None)):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    _check_user(authorization, record["user_id"])
    if _already_completed(record) is not None:
        raise HTTPException(409, "That battle is already over.")
    if record["wild_pokemon"].get("story_ref"):
        return {"success": False, "message": "You can't run from a trainer battle!"}
    if record["wild_pokemon"].get("gym_floor"):
        # leaving a gym fight forfeits the run (always succeeds)
        player = get_or_create_player(record["user_id"])
        result = gym_system.end_run(player)
        out = {"success": True, "gym": result}
        _persist_and_close(player, req.battle_id, out)
        return out
    success = random.random() < 0.75
    if success:
        player = get_or_create_player(record["user_id"])
        _sync_session_into_player(player, record)      # running away doesn't heal the team
        persist_player(player, close_battles=[req.battle_id])
        return {"success": True}
    # A failed escape costs the turn: the opponent attacks (and can win the fight).
    rec, player_mon, wild_mon, result = _free_enemy_turn(record, record["player_pokemon"])
    turn = {
        "log": ["Couldn't escape!"] + _turn_log(result),
        "is_finished": result["is_finished"],
        "winner": result["winner"],
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
    }
    turn = _after_turn(req.battle_id, False, rec, player_mon, wild_mon, result, turn)
    return {"success": False, "message": "Couldn't escape!", "turn": turn}


class AbandonRequest(BaseModel):
    user_id: int


@app.post("/api/battle/abandon")
@_serialized
def battle_abandon(req: AbandonRequest, authorization: Optional[str] = Header(default=None)):
    """Leave whatever battle this player has open (e.g. after reloading the page). The damage taken stays."""
    _check_user(authorization, req.user_id)
    rows = [r for r in _sessions.list_user(req.user_id)]
    player = get_or_create_player(req.user_id)
    for r in rows:
        if not r.get("completed_at"):
            if (r.get("wild_pokemon") or {}).get("gym_floor"):
                gym_system.end_run(player)             # leaving a gym fight forfeits the run, same as Run
            _sync_session_into_player(player, r)
    persist_player(player, close_battles=[r["battle_id"] for r in rows])
    return {"success": True, "abandoned": len(rows)}


@app.post("/api/battle/switch")
@_serialized
def battle_switch(req: SwitchRequest, authorization: Optional[str] = Header(default=None)):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    _check_user(authorization, record["user_id"])
    if _already_completed(record) is not None:
        raise HTTPException(409, "That battle is already over.")

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

    # the Pokémon you send out takes the lead slot, so the next fight (next gym floor, next trainer) starts with it
    player.active_team = [target] + [p for p in player.active_team if p.id != target.id]
    persist_player(player)

    # A voluntary switch costs the turn, like the games: the new Pokémon comes in and the opponent gets a free hit.
    # (Engine turns accept `None` for the side that didn't act.)
    switched_record = {**record, "player_pokemon": target.to_dict(),
                       "wild_pokemon": PokemonInstance.from_dict(record["wild_pokemon"]).to_dict()}
    switched_record, player_mon, wild_mon, result = _free_enemy_turn(switched_record, target.to_dict())
    response = {
        "log": [f"Go, {target.species_name.upper()}!"] + _turn_log(result),
        "is_finished": result["is_finished"],
        "winner": result["winner"],
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
    }
    for i, p in enumerate(player.active_team):          # the free hit is real damage on the team member
        if p.id == target.id:
            player.active_team[i] = player_mon._p
            break
    return _after_turn(req.battle_id, False, switched_record, player_mon, wild_mon, result, response)


@app.post("/api/battle/item")
@_serialized
def battle_item(req: ItemRequest, authorization: Optional[str] = Header(default=None)):
    record = _sessions.load(req.battle_id)
    if not record:
        raise HTTPException(404, "No active battle with that id.")
    _check_user(authorization, record["user_id"])
    if _already_completed(record) is not None:
        raise HTTPException(409, "That battle is already over.")
    if req.item_type not in HEAL_AMOUNTS:
        raise HTTPException(400, f"Unknown item: {req.item_type}")

    player = get_or_create_player(record["user_id"])
    if not player.remove_item(req.item_type, 1):
        raise HTTPException(400, f"No {req.item_type} left.")

    active = PokemonInstance.from_dict(record["player_pokemon"])
    heal = HEAL_AMOUNTS[req.item_type]
    active.current_hp = min(active.max_hp, active.current_hp + heal)

    # Item first, effect second: if the save fails nothing was consumed AND nothing healed; if only the session
    # write fails afterwards the player loses the item without the heal (never the other way round = a free heal).
    persist_player(player)

    # Using an item costs the turn: the healed Pokémon then takes the opponent's move.
    rec, player_mon, wild_mon, result = _free_enemy_turn(record, active.to_dict())
    response = {
        "log": [f"Used {req.item_type.upper()}. Restored {heal} HP."] + _turn_log(result),
        "is_finished": result["is_finished"],
        "winner": result["winner"],
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
        "remaining": player.inventory.get(req.item_type, 0),
    }
    return _after_turn(req.battle_id, False, rec, player_mon, wild_mon, result, response)


@app.post("/api/shop/buy")
@_serialized
def shop_buy(req: BuyRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
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
@_serialized
def party_heal(req: HealRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
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
def boss_today(user_id: Optional[int] = None, authorization: Optional[str] = Header(default=None)):
    if user_id is not None:
        _check_user(authorization, user_id)
    """Today's boss. With ?user_id= it is scaled to that player and says whether
    today's reward has already been claimed."""
    claimed = False
    lead_level = 5
    if user_id is not None:
        player = get_or_create_player(user_id)
        lead = next((p for p in player.active_team if not p.is_fainted and p.current_hp > 0), None)
        lead_level = lead.level if lead else 5
        claimed = boss_battle.is_claimed_today(player)
    template = boss_battle.template_for(lead_level)
    boss = boss_battle.scaled_boss(template, lead_level)
    info = {"name": boss.species.upper(), "moves": "", "ability": boss.ability}
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
@_serialized
def boss_start(req: BossStartRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id, req.username)
    if boss_battle.is_claimed_today(player):
        raise HTTPException(400, "You already beat today's boss — a new one arrives at 00:00 UTC.")

    lead = _lead_or_400(player, "challenging the boss")

    boss_mon, boss = boss_battle.build_boss_pokemon(lead.level)
    player_mon = BattleReadyPokemon(lead)
    wild_mon = BattleReadyPokemon(boss_mon)

    battle_id = str(uuid.uuid4())
    _sessions.purge_user(req.user_id)
    _sessions.save(battle_id, req.user_id, lead.to_dict(), boss_mon.to_dict())

    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(player_mon),
        "wild_pokemon": serialize_pokemon(wild_mon),
        "log": [f"⚔️ DAILY BOSS: {boss_mon.species_name.upper()} Lv{boss_mon.level} blocks the way!"],
    }


@app.post("/api/party/rare-candy")
@_serialized
def party_rare_candy(req: CandyRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
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
        "evolution_pending": progression.pending(player),
        "moves_learned": progression.move_events(player),
        "move_learning": progression.pending_moves(player),
    }


class LearnMoveRequest(BaseModel):
    user_id: int
    pokemon_id: str
    move: str
    replace: Optional[str] = None      # the known move to forget; omit to decline learning `move`


@app.post("/api/party/learn-move")
@_serialized
def party_learn_move(req: LearnMoveRequest, authorization: Optional[str] = Header(default=None)):
    """Answer a pending level-up move (offered when the moveset was full): teach it over `replace`, or decline."""
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    mon = next((p for p in list(player.active_team) + list(player.pokemon_collection) if p.id == req.pokemon_id), None)
    if not mon:
        raise HTTPException(404, "That Pokemon isn't yours.")
    result = mon.resolve_pending_move(req.move, req.replace)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    return {**result, "pokemon": serialize_pokemon(mon), "move_learning": progression.pending_moves(player)}


def _gym_status_payload(player) -> dict:
    return {**gym_system.status(player), "shop": gym_system.shop_catalog()}


@app.get("/api/gym/status")
def gym_status(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    return _gym_status_payload(get_or_create_player(user_id))


@app.post("/api/gym/enter")
@_serialized
def gym_enter(req: GymEnterRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    """Start a run (floor 1) or fight the floor an active run is on. Also used for 'next floor'
    and for sending in your next Pokemon after one faints."""
    player = get_or_create_player(req.user_id, req.username)
    sessions = _sessions.list_user(req.user_id)
    # RESUME: re-entering (page reload, double tap) while a fight on THIS floor is still open must not hand the
    # opponent a fresh set of HP — return the fight as it stands.
    gym_system.start_or_resume(player)
    _opp0, meta0 = gym_system.build_opponent(player)
    for r in sessions:
        wp = r.get("wild_pokemon") or {}
        if (not r.get("completed_at") and wp.get("gym_floor") and int(wp["gym_floor"]) == int(meta0["floor"])
                and r.get("_age_s", 1e9) < BATTLE_LOCK_S):
            mine = PokemonInstance.from_dict(r["player_pokemon"])
            theirs = PokemonInstance.from_dict(wp)
            return {
                "battle_id": r["battle_id"],
                "player_pokemon": serialize_pokemon(BattleReadyPokemon(mine)),
                "wild_pokemon": serialize_pokemon(BattleReadyPokemon(theirs)),
                "log": ["Back in the fight!"],
                "gym": meta0,
                "resumed": True,
            }
    # Otherwise gym_enter is how the next floor / next Pokémon is sent in, so an open fight is replaced, not
    # refused — but its damage is kept (saved below, before the old session is dropped)
    for _r in sessions:
        if not _r.get("completed_at"):
            _sync_session_into_player(player, _r)
    lead = _lead_or_400(player, "entering the gym")

    opp, meta = gym_system.build_opponent(player)
    persist_player(player)

    player_mon = BattleReadyPokemon(lead)
    wild_mon = BattleReadyPokemon(opp)
    battle_id = str(uuid.uuid4())
    _sessions.purge_user(req.user_id)
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
@_serialized
def gym_forfeit(req: GymEnterRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    player = get_or_create_player(req.user_id, req.username)
    if not gym_system.in_run(player):
        raise HTTPException(400, "You're not in a gym run.")
    result = gym_system.end_run(player)
    persist_player(player)
    return {"gym": result, "team": [serialize_pokemon(p) for p in player.active_team]}


@app.post("/api/gym/shop/buy")
@_serialized
def gym_shop_buy(req: GymBuyRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
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


# ── ACCOUNTS (username/password + Telegram link) and STARTER SELECTION ──

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


class WebAppAuthRequest(BaseModel):
    init_data: str


@app.post("/api/auth/telegram/webapp")
def auth_telegram_webapp(req: WebAppAuthRequest):
    """Telegram Mini App sign-in: the identity comes from Telegram's SIGNED initData (checked against the bot token),
    never from anything the client merely claims."""
    who = _accounts.webapp_login(req.init_data, TELEGRAM_BOT_TOKEN)
    return _auth_payload({"user_id": who["user_id"], "username": who["username"]})


@app.post("/api/auth/link/start")
def auth_link_start(authorization: Optional[str] = Header(default=None)):
    """A logged-in WEB player asks to join their Telegram account to this one. They send the code to the bot."""
    claims = accounts.verify_token(authorization if isinstance(authorization, str) else None)
    if not claims:
        raise HTTPException(401, "Log in first.")
    if claims["uid"] < accounts.WEB_ID_BASE:
        raise HTTPException(400, "You're already signed in with Telegram — there's nothing to link.")
    if _accounts.is_alias(claims["uid"]):
        raise HTTPException(401, "Your account was linked — please log in again.")
    started = _accounts.start_link(claims["uid"])
    bot_username = (os.environ.get("BOT_USERNAME") or "").lstrip("@")
    return {
        "code": started["code"],
        "expires_in": started["expires_in"],
        "bot_url": f"https://t.me/{bot_username}?start=link_{started['code']}" if bot_username else None,
        "command": f"/link {started['code']}",
    }


@app.get("/api/starters")
def list_starters():
    return {
        "regions": {
            region: [{"species": sp, "pokedex_id": dex} for sp, dex in mons]
            for region, mons in STARTERS.items()
        }
    }


@app.post("/api/player/starter")
@_serialized
def choose_starter(req: StarterRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    player = get_or_create_player(req.user_id)
    try:
        onboarding.create_player_with_starter(player, req.region, req.species, req.avatar)
    except onboarding.OnboardingError as e:
        raise HTTPException(400, str(e))
    persist_player(player)
    return get_roster(req.user_id, authorization)


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


# ── JOURNEY (towns, routes, story trainers) ──

@app.get("/api/journey/state")
def journey_state(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    return journey.state(get_or_create_player(user_id))


class RegionRequest(BaseModel):
    user_id: int
    region: str


@app.post("/api/journey/region")
@_serialized
def journey_region(req: RegionRequest, authorization: Optional[str] = Header(default=None)):
    """Move to another region the player has unlocked. Each region keeps its own progress."""
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    result = journey.begin_region(player, (req.region or "").lower())
    persist_player(player)
    return result


@app.post("/api/journey/travel")
@_serialized
def journey_travel(req: TravelRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    result = journey.travel(player, req.to)
    persist_player(player)
    return result


@app.post("/api/journey/heal")
@_serialized
def journey_heal(req: JourneyActionRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    result = journey.heal(player)
    persist_player(player)
    return {**result, "team": [serialize_pokemon(p) for p in player.active_team]}


@app.post("/api/journey/trainer/start")
@_serialized
def journey_trainer_start(req: JourneyActionRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id, req.username)
    if not req.trainer_id:
        raise HTTPException(400, "Which trainer?")
    lead = _lead_or_400(player, "challenging a trainer")
    opp, meta = journey.start_trainer(player, req.trainer_id)
    persist_player(player)

    battle_id = str(uuid.uuid4())
    _sessions.purge_user(req.user_id)
    _sessions.save(battle_id, req.user_id, lead.to_dict(), opp.to_dict())
    return {
        "battle_id": battle_id,
        "player_pokemon": serialize_pokemon(BattleReadyPokemon(lead)),
        "wild_pokemon": serialize_pokemon(BattleReadyPokemon(opp)),
        "log": [f"{meta['name']}: \"{meta['intro']}\"", f"{meta['name']} sent out {opp.species_name.upper()}!"],
        "story": meta,
    }


# ── CARE CENTER (Nurse Joy) — never during a battle ──

class CareRequest(BaseModel):
    user_id: int
    pokemon_id: Optional[str] = None
    use_revive: bool = False


def _species_by_id() -> Dict[int, str]:
    import species_data
    return {v["id"]: k for k, v in species_data.SPECIES.items()}


def _pokedex_payload(player) -> dict:
    """seen / caught as species names (what the website's Pokédex is keyed by). Caught = owned now or ever caught."""
    by_id = _species_by_id()
    seen = {by_id[i] for i in player.pokedex_seen if i in by_id}
    owned = {m.species_name for m in list(player.active_team) + list(player.pokemon_collection)}
    history = {str(n).lower() for n in (player.story.get("caught", []) if isinstance(player.story, dict) else [])}
    caught = {str(n).lower() for n in owned} | history          # owned now OR ever caught (survives evolve / trade)
    return {"seen": sorted(seen | owned | caught), "caught": sorted(caught)}


_POKEDEX_STATIC = None


@app.get("/api/player/{user_id}/pokedex")
def get_pokedex_catalogue(user_id: int, authorization: Optional[str] = Header(default=None)):
    """The COMPLETE species catalogue (every species the server knows, not the website's small local list) with this
    player's seen / caught / owned-now status. Caught is history: it survives evolving, trading and releasing."""
    import species_data
    _check_user(authorization, user_id)
    player = get_or_create_player(user_id)
    dex = _pokedex_payload(player)
    seen, caught = set(dex["seen"]), set(dex["caught"])
    owned: Dict[str, int] = {}
    for m in list(player.active_team) + [m for m in player.pokemon_collection if m.id not in {t.id for t in player.active_team}]:
        owned[m.species_name.lower()] = owned.get(m.species_name.lower(), 0) + 1
    global _POKEDEX_STATIC
    if _POKEDEX_STATIC is None:              # the species list never changes while the process runs: build it once
        _POKEDEX_STATIC = [(k, v["id"], list(v["t"]))
                           for k, v in sorted(species_data.SPECIES.items(), key=lambda kv: kv[1]["id"])]
    rows = [{"id": sid, "name": k, "types": types, "seen": k in seen, "caught": k in caught, "owned": owned.get(k, 0)}
            for k, sid, types in _POKEDEX_STATIC]
    return {"species": rows, "total": len(rows), "seen": len(seen), "caught": len(caught)}


def _sync_session_into_player(player, record: dict) -> None:
    """Carry the damage / status a Pokémon took in an UNFINISHED battle back onto the real Pokémon. Battle HP lives
    only in the session, so without this, abandoning (or fleeing) would silently heal the team."""
    snap = record.get("player_pokemon") or {}
    pid = snap.get("id")
    if not pid:
        return
    for mon in list(player.active_team) + list(player.pokemon_collection):
        if mon.id == pid:
            mon.current_hp = max(0, min(mon.max_hp, int(snap.get("current_hp", mon.current_hp))))
            mon.status = snap.get("status", mon.status)
            mon.is_fainted = mon.current_hp <= 0
            mon.bt = None


def _settle_sessions(user_id: int, player=None, stale_only: bool = False, rows: Optional[list] = None) -> None:
    """Close this player's unfinished battle sessions WITHOUT losing the damage taken: sync HP/status onto the
    team, save the player, THEN delete the sessions (a failed save leaves them in place, nothing is lost).
    stale_only=True closes only sessions idle longer than the battle lock (AFK tabs)."""
    rows = [r for r in (rows if rows is not None else _sessions.list_user(user_id))
            if not stale_only or r.get("_age_s", 0) >= BATTLE_LOCK_S or r.get("completed_at")]
    if not rows:
        return
    own = player is None
    if own:
        player = get_or_create_player(user_id)
    changed = False
    for r in rows:
        if not r.get("completed_at"):
            _sync_session_into_player(player, r)
            changed = True
    ids = [r["battle_id"] for r in rows]
    if own and changed:
        persist_player(player, close_battles=ids)
    else:
        for b in ids:
            _sessions.delete(b)


BATTLE_LOCK_S = 600     # a battle touched within this window blocks other actions; an idle one is settled, not left as a zombie


def _no_battle(user_id: int):
    rows = _sessions.list_user(user_id)             # ONE read answers both questions below
    if any(not r.get("completed_at") and r.get("_age_s", 1e9) < BATTLE_LOCK_S for r in rows):
        raise HTTPException(400, "Finish your battle first — that can't be done during a fight "
                                 "(or leave it with Run / /api/battle/abandon).")
    if rows:                                        # an abandoned tab's old battle (or a finished one that couldn't be
        _settle_sessions(user_id, stale_only=True, rows=rows)    # deleted) is closed properly, keeping its damage


def _center_here(player) -> bool:
    """Journey: the Care Center is in towns. Free-roam regions can visit any time."""
    st = journey.ensure_story(player)
    if st["mode"] != "journey":
        return True
    return bool(journey.state(player)["location"]["heal"])


def _care_payload(player, message: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    data = care.summary(player)
    return {
        **data,
        "coins": player.coins,
        "revives": player.inventory.get("revive", 0),
        "center_here": _center_here(player),
        "message": message,
        **(extra or {}),
    }


@app.get("/api/care/state")
def care_state(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    player = get_or_create_player(user_id)
    return _care_payload(player)


@app.post("/api/care/heal")
@_serialized
def care_heal(req: CareRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    if not _center_here(player):
        raise HTTPException(400, "There's no Care Center on a route — head to a town.")
    result = care.heal_all(player)
    persist_player(player)
    msg = "Joy: \"Your Pokémon are all fighting fit!\"" if not result["critical"] else (
        f"Joy: \"I've treated everyone I could — but {', '.join(result['critical'])} needs intensive care.\"")
    return _care_payload(player, msg, {"team_full": [serialize_pokemon(p) for p in player.active_team]})


@app.post("/api/care/intensive")
@_serialized
def care_intensive(req: CareRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    if not _center_here(player):
        raise HTTPException(400, "There's no Care Center on a route — head to a town.")
    if not req.pokemon_id:
        raise HTTPException(400, "Which Pokémon?")
    result = care.intensive_care(player, req.pokemon_id, req.use_revive)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    return _care_payload(player, result["message"], {"success": result["success"], "cost": result["cost"]})


class StorageRequest(BaseModel):
    user_id: int
    pokemon_id: str


def _storage_payload(player, message: str = "") -> dict:
    return {"message": message,
            "team": [{**serialize_pokemon(p), "condition": care.condition(player, p)} for p in player.active_team],
            "box": [{**serialize_pokemon(p), "condition": care.condition(player, p)} for p in storage_box.box(player)],
            "team_limit": storage_box.TEAM_LIMIT}


@app.get("/api/player/{user_id}/storage")
def get_storage(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    return _storage_payload(get_or_create_player(user_id))


@app.post("/api/storage/deposit")
@_serialized
def storage_deposit(req: StorageRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    result = storage_box.deposit(player, req.pokemon_id)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    return _storage_payload(player, result["message"])


@app.post("/api/storage/withdraw")
@_serialized
def storage_withdraw(req: StorageRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    result = storage_box.withdraw(player, req.pokemon_id)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    return _storage_payload(player, result["message"])


@app.post("/api/care/rest")
@_serialized
def care_rest(req: CareRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    if not req.pokemon_id:
        raise HTTPException(400, "Which Pokémon?")
    result = care.rest(player, req.pokemon_id)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    return _care_payload(player, result["message"])


@app.post("/api/care/withdraw")
@_serialized
def care_withdraw(req: CareRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    if not req.pokemon_id:
        raise HTTPException(400, "Which Pokémon?")
    result = care.withdraw(player, req.pokemon_id)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    return _care_payload(player, result["message"])


# ── FEEDBACK — bug reports / ideas from Settings ──

_feedback = feedback_mod.FeedbackStore(SUPABASE_URL, SUPABASE_KEY) if _db else feedback_mod.FeedbackStore()


class FeedbackRequest(BaseModel):
    category: str = "bug"
    message: str
    context: Optional[Dict] = None


@app.post("/api/feedback")
def post_feedback(req: FeedbackRequest, request: Request, authorization: Optional[str] = Header(default=None)):
    """Anyone may report (a broken login is when it matters most). A valid token attaches the player's id."""
    claims = accounts.verify_token(authorization if isinstance(authorization, str) else None)
    uid = claims["uid"] if claims else None
    sender = f"u{uid}" if uid else "ip:" + ((request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
                                           or (request.client.host if request.client else "anon"))
    try:
        row = _feedback.submit(sender, uid, claims["name"] if claims else None, req.category, req.message, req.context)
    except feedback_mod.FeedbackError as e:
        raise HTTPException(e.status, e.message)
    who = f"{row.get('username') or 'guest'}" + (f" ({uid})" if uid else "")
    for admin_id in admin_system.admin_ids():
        notify_telegram(admin_id, f"🪲 {row['category']} from {who}:\n{row['message'][:300]}")
    return {"ok": True, "id": row.get("id")}


@app.get("/api/admin/feedback")
def admin_feedback(limit: int = 50, authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    return {"feedback": _feedback.recent(max(1, min(200, limit)))}


# ── ADMIN — requires a valid login token of an admin account (checked server-side) ──

_MEMORY_ASSETS: Dict[str, str] = {}


def _require_admin(authorization: Optional[str]) -> dict:
    claims = accounts.verify_token(authorization)
    if not claims:
        raise HTTPException(401, "Log in first.")
    if not admin_system.is_admin(claims["uid"], claims["name"]):
        raise HTTPException(403, "Admins only.")
    return claims


def _find_target(user_id: Optional[int], username: Optional[str]) -> PlayerInstance:
    if user_id is None and not (username or "").strip():
        raise HTTPException(400, "Give a username or a user id.")
    if user_id is None:
        name = username.strip()
        if _db:
            matches = _db.find_players_by_username(name)
        else:
            matches = [(p.user_id, p.username) for p in _MEMORY_PLAYERS.values()
                       if (p.username or "").lower() == name.lower()]
        if not matches:
            raise HTTPException(404, f"No player called '{name}'.")
        if len(matches) > 1:
            ids = ", ".join(f"{u} ({n})" for u, n in matches)
            raise HTTPException(400, f"Several players are called '{name}' — use a user id: {ids}")
        user_id = matches[0][0]
    if _db:
        player = _db.load_player(user_id)
    else:
        player = _MEMORY_PLAYERS.get(user_id)
    if not player:
        raise HTTPException(404, f"No player with id {user_id}.")
    return player


class AdminGiveRequest(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    coins: int = 0
    items: Dict[str, int] = {}
    balls: Dict[str, int] = {}
    pokemon: Optional[Dict] = None
    heal: bool = False


class AssetRequest(BaseModel):
    key: str
    url: Optional[str] = None


@app.get("/api/admin/me")
def admin_me(authorization: Optional[str] = Header(default=None)):
    claims = accounts.verify_token(authorization)
    if not claims:
        return {"is_admin": False}
    return {"is_admin": admin_system.is_admin(claims["uid"], claims["name"])}


@app.get("/api/admin/player")
def admin_player(username: Optional[str] = None, user_id: Optional[int] = None,
                 authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    return admin_system.player_summary(_find_target(user_id, username))


@app.post("/api/admin/give")
@_serialized
def admin_give(req: AdminGiveRequest, authorization: Optional[str] = Header(default=None)):
    claims = _require_admin(authorization)
    player = _find_target(req.user_id, req.username)
    done = admin_system.give(player, req.coins, req.items, req.balls, req.pokemon, req.heal)
    persist_player(player)
    logger.info(f"ADMIN {claims['uid']} ({claims['name']}) -> {player.user_id} ({player.username}): {done}")
    return {"ok": True, "done": done, "player": admin_system.player_summary(player)}


import ttl_cache                                    # noqa: E402
ASSETS_TTL_S = float(os.environ.get("ASSETS_CACHE_S", "60"))
LEADERBOARD_TTL_S = float(os.environ.get("LEADERBOARD_CACHE_S", "15"))
_assets_cache = ttl_cache.TTLCache("assets")
_leaderboard_cache = ttl_cache.TTLCache("leaderboard")


@app.get("/api/assets")
def get_assets():
    """Public: image overrides the admin has set (scene backgrounds etc.). Cached: read on every page load, rarely edited."""
    if _db:
        return {"assets": _assets_cache.get_or_load("all", ASSETS_TTL_S, _db.get_assets), "keys": admin_system.ASSET_KEYS}
    return {"assets": dict(_MEMORY_ASSETS), "keys": admin_system.ASSET_KEYS}


@app.post("/api/admin/assets")
@_serialized
def admin_set_asset(req: AssetRequest, authorization: Optional[str] = Header(default=None)):
    claims = _require_admin(authorization)
    if not admin_system.valid_asset_key(req.key):
        raise HTTPException(400, "Unknown image slot.")
    if req.url is None or req.url == "":
        if _db:
            _db.delete_asset(req.key)
        _MEMORY_ASSETS.pop(req.key, None)
        _assets_cache.invalidate()
        return {"ok": True, "removed": req.key}
    if not admin_system.valid_asset_url(req.url):
        raise HTTPException(400, "Use an https:// image link, or a path on the site like /scenes/kanto.png.")
    if _db:
        if not _db.set_asset(req.key, req.url):
            raise HTTPException(503, "Couldn't save — run database/schema.sql (the site_assets table).")
    else:
        _MEMORY_ASSETS[req.key] = req.url
    _assets_cache.invalidate()                   # the admin sees their change immediately (other instances within the TTL)
    logger.info(f"ADMIN {claims['uid']} set image {req.key} -> {req.url}")
    return {"ok": True, "key": req.key, "url": req.url}


# ── SCENES — procedural pixel scenery & cutscene GIFs (original art, drawn from code) ──

_IMG_HEADERS = {"Cache-Control": "public, max-age=86400"}


@app.get("/api/scenes/slide/{region}.png")
def scene_slide(region: str, scale: int = 4):
    return Response(content=scenes.region_slide(region, scale), media_type="image/png", headers=_IMG_HEADERS)


@app.get("/api/scenes/{kind}.png")
def scene_png(kind: str, region: str = "kanto", avatar: str = "ember", scale: int = 4):
    if kind not in scenes.KINDS:
        raise HTTPException(404, "No such scene.")
    return Response(content=scenes.render_png(kind, region, avatar, scale), media_type="image/png", headers=_IMG_HEADERS)


@app.get("/api/scenes/{kind}.gif")
def scene_gif(kind: str, region: str = "kanto", avatar: str = "ember", scale: int = 3):
    if kind not in scenes.KINDS:
        raise HTTPException(404, "No such scene.")
    return Response(content=scenes.render_gif(kind, region, avatar, scale), media_type="image/gif", headers=_IMG_HEADERS)


# ── EVOLUTION — by level, evolution stone, or Trade Cable (never during a battle) ──

class EvolveRequest(BaseModel):
    user_id: int
    pokemon_id: str
    to: str


@app.get("/api/evolution/state")
def evolution_state(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    player = get_or_create_player(user_id)
    return {
        "team": [{"id": p.id, "species_name": p.species_name, "level": p.level, "options": evolution.options(player, p)}
                 for p in player.active_team],
        "trade_cables": player.inventory.get(evolution.TRADE_ITEM, 0),
    }


@app.post("/api/evolution/evolve")
@_serialized
def evolution_evolve(req: EvolveRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    player = get_or_create_player(req.user_id)
    result = evolution.evolve(player, req.pokemon_id, req.to.lower())
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    persist_player(player)
    roster = get_roster(req.user_id, authorization)
    return {**result, "roster": roster}


# ── PvP DUELS and PLAYER-TO-PLAYER TRADING (web and Telegram players can face / trade with each other) ──

_pvp = pvp_system.new_store(SUPABASE_URL, SUPABASE_KEY) if _db else pvp_system.new_store()
_trades = trade_system.new_store(SUPABASE_URL, SUPABASE_KEY) if _db else trade_system.new_store()
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_ID_LIMIT = 10 ** 11            # web accounts are far above this (accounts.WEB_ID_BASE); Telegram ids are below


from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
_NOTIFY_POOL = _ThreadPoolExecutor(max_workers=4, thread_name_prefix="notify")


def notify_telegram(user_id: int, text: str, buttons: Optional[list] = None):
    """Best-effort ping to a Telegram player (needs BOT_TOKEN on the API too). Web players poll instead."""
    if not TELEGRAM_BOT_TOKEN:
        return
    if user_id >= TELEGRAM_ID_LIMIT:               # a web player: ping their linked Telegram account, if any
        try:
            user_id = _accounts.telegram_for(user_id) or 0
        except Exception:
            return
        if not user_id:
            return
    payload = {"chat_id": user_id, "text": text}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}

    def _send():
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json=payload, timeout=5)
        except Exception as e:
            logger.info(f"telegram notify skipped: {e}")

    # a ping must never hold up the request that caused it (Telegram can take seconds): send it off-thread
    if os.environ.get("POSHOW_SYNC_NOTIFY"):
        _send()
    else:
        _NOTIFY_POOL.submit(_send)


class PvpChallengeRequest(BaseModel):
    user_id: int
    username: str


class PvpRespondRequest(BaseModel):
    user_id: int
    match_id: str
    accept: bool = True


class PvpActionRequest(BaseModel):
    user_id: int
    match_id: str
    action: Optional[Dict] = None


def _players_of(doc: dict) -> dict:
    return {"a": get_or_create_player(doc["a"]), "b": get_or_create_player(doc["b"])}


def _persist_pair(players: dict):
    persist_players([players["a"], players["b"]])


@app.post("/api/pvp/challenge")
@_serialized
def pvp_challenge(req: PvpChallengeRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    me = get_or_create_player(req.user_id)
    target = _find_target(None, req.username)
    doc = pvp_system.challenge(_pvp, me, target.user_id, target.username)
    notify_telegram(target.user_id, f"⚔ {me.username} challenges you to a duel! Open /pvp to answer.",
                    [[{"text": "Accept", "callback_data": f"pvp_yes_{doc['id']}"},
                      {"text": "Decline", "callback_data": f"pvp_no_{doc['id']}"}]])
    return pvp_system.view(doc, req.user_id)


@app.get("/api/pvp/state")
def pvp_state(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    now = _time.time()
    incoming, outgoing, active = [], [], None
    for d in _pvp.for_user(user_id, ["pending", "active", "finished"], 3600):
        if d["status"] == "pending" and now - d["ts"] < pvp_system.INVITE_TTL:
            row = {"id": d["id"], "from": d["state"]["names"]["a"], "to": d["state"]["names"]["b"]}
            (incoming if d["b"] == user_id else outgoing).append(row)
        elif d["status"] == "active":
            active = pvp_system.view(d, user_id)
        elif d["status"] == "finished" and active is None and now - d["ts"] < 600:
            active = pvp_system.view(d, user_id)         # show the result for ten minutes
    me = get_or_create_player(user_id)
    return {"incoming": incoming, "outgoing": outgoing, "active": active,
            "elo": me.elo, "wins": me.wins, "losses": me.losses}


@app.post("/api/pvp/respond")
@_serialized
def pvp_respond(req: PvpRespondRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    me = get_or_create_player(req.user_id)
    doc = pvp_system.respond(_pvp, req.match_id, me, req.accept)
    if doc["status"] == "declined":
        notify_telegram(doc["a"], f"{me.username} declined your duel.")
        return {"declined": True}
    players = _players_of(doc)
    doc = pvp_system.start(_pvp, doc["id"], players["a"], players["b"])
    notify_telegram(doc["a"], f"⚔ {me.username} accepted! Your duel has begun — open /pvp.")
    return pvp_system.view(doc, req.user_id)


@app.post("/api/pvp/action")
@_serialized
def pvp_action(req: PvpActionRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    doc = _pvp.load(req.match_id)
    if not doc:
        raise HTTPException(404, "No such duel.")
    players = _players_of(doc)
    before = doc["status"]
    # A finishing turn is not stored by pvp_system: the result and both players' ELO / wins / losses are written
    # together, so a failed save can never leave a finished duel whose rating changes were lost.
    doc = pvp_system.submit(_pvp, req.match_id, req.user_id, req.action or {}, players, save_finished=False)
    if doc["status"] == "finished" and before == "active":
        persist_players([players["a"], players["b"]], trade_doc=doc, trade_store=_pvp)
    other = doc["b"] if req.user_id == doc["a"] else doc["a"]
    if doc["status"] == "active":
        notify_telegram(other, "⚔ Your opponent made their move — your turn in /pvp.")
    return pvp_system.view(doc, req.user_id)


@app.post("/api/pvp/forfeit")
@_serialized
def pvp_forfeit(req: PvpActionRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    doc = _pvp.load(req.match_id)
    if not doc:
        raise HTTPException(404, "No such duel.")
    players = _players_of(doc)
    doc = pvp_system.forfeit(_pvp, req.match_id, req.user_id, players, save_finished=False)
    persist_players([players["a"], players["b"]], trade_doc=doc, trade_store=_pvp)
    return pvp_system.view(doc, req.user_id)


@app.post("/api/pvp/timeout")
@_serialized
def pvp_timeout(req: PvpActionRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    doc = _pvp.load(req.match_id)
    if not doc:
        raise HTTPException(404, "No such duel.")
    players = _players_of(doc)
    doc = pvp_system.claim_timeout(_pvp, req.match_id, req.user_id, players, save_finished=False)
    persist_players([players["a"], players["b"]], trade_doc=doc, trade_store=_pvp)
    return pvp_system.view(doc, req.user_id)


@app.get("/api/leaderboard")
def leaderboard(limit: int = 20):
    """Top trainers by ELO (public: usernames and ranking only). Cached for a few seconds: read by everyone, changes slowly."""
    limit = max(1, min(50, limit))

    def load():
        if _db:
            try:
                res = dbhttp.get(f"{SUPABASE_URL}/rest/v1/players",
                                 params={"select": "username,elo,wins,losses", "order": "elo.desc", "limit": str(limit)},
                                 headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=15)
                if res.status_code != 200:
                    raise DatabaseError(f"leaderboard read failed ({res.status_code}): {res.text[:200]}")
                return res.json()
            except requests.RequestException as e:
                raise DatabaseError(f"leaderboard read failed: {e}") from e     # an outage is a 503, not an empty ranking
        return sorted(({"username": p.username, "elo": p.elo, "wins": p.wins, "losses": p.losses}
                       for p in _MEMORY_PLAYERS.values()), key=lambda r: -r["elo"])[:limit]

    rows = _leaderboard_cache.get_or_load(limit, LEADERBOARD_TTL_S, load) if _db else load()
    return {"leaderboard": [{"rank": i + 1, **r} for i, r in enumerate(rows)]}


# ── trading ──

class TradeInviteRequest(BaseModel):
    user_id: int
    username: str


class TradeRespondRequest(BaseModel):
    user_id: int
    trade_id: str
    accept: bool = True


class TradeOfferRequest(BaseModel):
    user_id: int
    trade_id: str
    pokemon_id: Optional[str] = None
    clear_pokemon: bool = False
    coins: Optional[int] = None
    items: Optional[Dict[str, int]] = None


class TradeStepRequest(BaseModel):
    user_id: int
    trade_id: str
    locked: bool = True


def _trade_view(doc: dict, uid: int) -> dict:
    return trade_system.view(doc, uid, _players_of(doc))


@app.post("/api/trade/invite")
@_serialized
def trade_invite(req: TradeInviteRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    me = get_or_create_player(req.user_id)
    target = _find_target(None, req.username)
    doc = trade_system.invite(_trades, me, target.user_id, target.username)
    notify_telegram(target.user_id, f"🔁 {me.username} wants to trade with you. Open /trade to answer.",
                    [[{"text": "Accept", "callback_data": f"trd_yes_{doc['id']}"},
                      {"text": "Decline", "callback_data": f"trd_no_{doc['id']}"}]])
    return {"id": doc["id"], "status": doc["status"]}


@app.get("/api/trade/state")
def trade_state(user_id: int, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, user_id)
    now = _time.time()
    incoming, outgoing, open_trade = [], [], None
    for d in _trades.for_user(user_id, ["pending", "open", "done"], trade_system.IDLE_TTL):
        if d["status"] == "pending" and now - d["ts"] < trade_system.INVITE_TTL:
            row = {"id": d["id"], "from": d["state"]["names"]["a"], "to": d["state"]["names"]["b"]}
            (incoming if d["b"] == user_id else outgoing).append(row)
        elif d["status"] == "open":
            open_trade = _trade_view(d, user_id)
        elif d["status"] == "done" and open_trade is None and now - d["ts"] < 600:
            open_trade = _trade_view(d, user_id)
    return {"incoming": incoming, "outgoing": outgoing, "trade": open_trade}


@app.post("/api/trade/respond")
@_serialized
def trade_respond(req: TradeRespondRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    me = get_or_create_player(req.user_id)
    doc = trade_system.respond(_trades, req.trade_id, me, req.accept)
    if doc["status"] == "declined":
        notify_telegram(doc["a"], f"{me.username} declined your trade.")
        return {"declined": True}
    notify_telegram(doc["a"], f"🔁 {me.username} accepted — the trade is open in /trade.")
    return _trade_view(doc, req.user_id)


@app.post("/api/trade/offer")
@_serialized
def trade_offer(req: TradeOfferRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    me = get_or_create_player(req.user_id)
    doc = trade_system.set_offer(_trades, req.trade_id, me, req.pokemon_id, req.clear_pokemon, req.coins, req.items)
    return _trade_view(doc, req.user_id)


@app.post("/api/trade/lock")
@_serialized
def trade_lock(req: TradeStepRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    me = get_or_create_player(req.user_id)
    doc = trade_system.lock(_trades, req.trade_id, me, req.locked)
    return _trade_view(doc, req.user_id)


@app.post("/api/trade/confirm")
@_serialized
def trade_confirm(req: TradeStepRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    _no_battle(req.user_id)
    doc = _trades.load(req.trade_id)
    if not doc or doc["status"] != "open":
        raise HTTPException(400, "This trade isn't open.")
    # BOTH trainers must be out of battle: a Pokémon that is fighting (or whose team a live battle session refers to)
    # can't be handed over. A battle that starts after this check changes the player row, so the settlement below
    # is rejected by its version check instead of corrupting that fight.
    other_id = doc["b"] if req.user_id == doc["a"] else doc["a"]
    if _sessions.in_battle(other_id, BATTLE_LOCK_S):
        raise HTTPException(409, "The other trainer is in a battle — try again when it's over.")
    players = _players_of(doc)
    # Nothing is written until the swap is final; then both players AND the trade record go in ONE transaction.
    # If it fails (outage, a version conflict), nothing changed — no rollback writes are needed or attempted.
    doc = trade_system.confirm(_trades, req.trade_id, get_or_create_player(req.user_id), players, save_done=False)
    if doc["status"] == "done":
        persist_players([players["a"], players["b"]], trade_doc=doc, trade_store=_trades)
    if doc["status"] == "done":
        other = doc["b"] if req.user_id == doc["a"] else doc["a"]
        notify_telegram(other, "🔁 Trade complete! Check your team.")
    return _trade_view(doc, req.user_id)


@app.post("/api/trade/cancel")
@_serialized
def trade_cancel(req: TradeStepRequest, authorization: Optional[str] = Header(default=None)):
    _check_user(authorization, req.user_id)
    doc = trade_system.cancel(_trades, req.trade_id, req.user_id)
    other = doc["b"] if req.user_id == doc["a"] else doc["a"]
    notify_telegram(other, "The trade was cancelled.")
    return {"cancelled": True}
