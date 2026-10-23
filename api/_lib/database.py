"""Supabase persistence for players and Pokémon, through the REST (PostgREST) API."""

import hashlib
import os
import requests
import http_client as dbhttp
import json
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """The database could not be reached / answered with an error, or its answer could not be understood.
    Distinct from "player not found" (load_player returns None — and ONLY then) so a network blip, a bad
    response or a deserialisation bug can never be mistaken for a brand-new player and overwrite real progress."""


class ConcurrentUpdateError(DatabaseError):
    """Someone else (the website, the Telegram bot, another tab) saved this player after we loaded it.
    Nothing was written. The caller should reload and redo the action."""


class SchemaError(DatabaseError):
    """The database schema is behind the code (missing column / function). Run database/schema.sql."""


def _is_missing_function(res) -> bool:
    t = (getattr(res, "text", "") or "")
    return res.status_code == 404 or "PGRST202" in t or "Could not find the function" in t


def _is_missing_column(res) -> bool:
    t = (getattr(res, "text", "") or "")
    return "PGRST204" in t or ("column" in t and ("does not exist" in t or "schema cache" in t))


class SupabaseDB:
    """Supabase database manager"""
    
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        logger.info("✅ Supabase connected")
    
    # ── Player operations ──
    
    def save_player(self, player, close_battles=None) -> bool:
        """Persist the WHOLE player — the stats row (incl. which Pokémon are on the team) and every Pokémon they
        own — in ONE database transaction (the `save_player_atomic` function in database/schema.sql).

        * All-or-nothing: if any part fails nothing is written, so a team/currency/inventory change can never be
          saved without the matching Pokémon rows (or vice-versa).
        * Optimistic versioning: the player row carries a `version`. A save only succeeds if the row is still at
          the version we loaded, so the website and the Telegram bot can't silently overwrite each other with a
          stale copy — the loser gets ConcurrentUpdateError and nothing is written.
        * Fails closed: a missing `story`/`avatar` column (or a missing function) is an error, never a quiet
          "save everything except the journey".

        Returns True on success; raises DatabaseError (or a subclass) on every failure."""
        data, rows, ids, hashes = self._player_payload(player)
        expected = getattr(player, "db_version", None)
        body = {"p_player": data, "p_pokemon": rows, "p_pokemon_ids": ids, "p_expected_version": expected}
        if close_battles:                       # battle sessions this save finishes, deleted in the same transaction
            body["p_close_battles"] = list(close_battles)
        try:
            res = dbhttp.post(
                f"{self.url}/rest/v1/rpc/save_player_atomic",
                headers=self.headers,
                json=body,
                timeout=25,
            )
        except requests.RequestException as e:
            logger.error(f"Error saving player {player.user_id}: {e}")
            raise DatabaseError(f"player save failed: {e}") from e

        if res.status_code in (200, 201, 204):
            try:
                player.db_version = int(res.json())
                player._mon_hashes = hashes
            except (ValueError, TypeError):
                raise DatabaseError(f"player save returned an unreadable version: {res.text[:200]}")
            logger.info(f"✅ Saved player {player.user_id} ({len(rows)} Pokemon, v{player.db_version})")
            return True

        text = (res.text or "")[:400]
        if "version_conflict" in text:
            logger.warning(f"⚠️ Save of player {player.user_id} rejected: stale copy ({text})")
            raise ConcurrentUpdateError(
                f"player {player.user_id} was changed elsewhere (website / Telegram) after it was loaded")
        if res.status_code == 409:
            raise ConcurrentUpdateError(f"player {player.user_id} was created or changed concurrently: {text}")
        if _is_missing_function(res):
            on_prod = bool(os.environ.get("RENDER") or os.environ.get("VERCEL") or os.environ.get("PRODUCTION"))
            if os.environ.get("ALLOW_LEGACY_SAVE") == "1" and not on_prod:
                logger.error("⚠️ save_player_atomic is missing — using the NON-atomic legacy save "
                             "(ALLOW_LEGACY_SAVE=1). Run database/schema.sql to fix this.")
                return self._save_player_legacy(player, data, self._player_payload(player, only_changed=False)[1])
            raise SchemaError("save_player_atomic() is missing — run database/schema.sql in the Supabase SQL editor "
                              "(the non-atomic ALLOW_LEGACY_SAVE fallback is local-development only and is ignored on Render/Vercel).")
        if _is_missing_column(res):
            raise SchemaError(f"players/pokemon schema is out of date ({text}) — run database/schema.sql. "
                              "Refusing to save without the story/avatar/version columns.")
        logger.error(f"❌ Save player {player.user_id} failed ({res.status_code}): {text}")
        raise DatabaseError(f"player save failed ({res.status_code}): {text}")

    @staticmethod
    def _row_hash(row: dict) -> str:
        return hashlib.md5(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()

    @classmethod
    def _player_payload(cls, player, only_changed: bool = True):
        """-> (player row, Pokémon rows to write, ids of EVERY Pokémon the player owns, {id: hash} of the saved state).
        Only rows that differ from what was loaded are sent (a big collection no longer costs a big save); the id
        list lets the database drop what the player no longer owns."""
        data = player.to_dict()
        data["active_team"] = [p.id for p in player.active_team]
        data.pop("version", None)
        mons = {}                     # team + collection, de-duplicated
        for m in list(player.pokemon_collection) + list(player.active_team):
            mons[m.id] = m
        known = getattr(player, "_mon_hashes", None) if only_changed else None
        rows, hashes = [], {}
        for mid, m in mons.items():
            row = m.to_db_dict()
            h = cls._row_hash(row)
            hashes[mid] = h
            if known is not None and known.get(mid) == h:
                continue
            row["player_id"] = player.user_id
            rows.append(row)
        return data, rows, list(mons.keys()), hashes

    def save_players(self, players, trade_row=None, doc_table: str = "trades") -> bool:
        """Save SEVERAL players in ONE transaction (trade settlement): every row version-checked, all written or
        none. Raises DatabaseError / ConcurrentUpdateError / SchemaError; there is no non-atomic fallback."""
        batch, saved_hashes = [], {}
        for pl in players:
            data, rows, ids, hashes = self._player_payload(pl)
            saved_hashes[pl.user_id] = hashes
            batch.append({"player": data, "pokemon": rows, "pokemon_ids": ids, "expected_version": getattr(pl, "db_version", None)})
        try:
            res = dbhttp.post(f"{self.url}/rest/v1/rpc/save_players_atomic", headers=self.headers,
                                json={"p_batch": batch, "p_trade": trade_row, "p_doc_table": doc_table}, timeout=30)
        except requests.RequestException as e:
            raise DatabaseError(f"multi-player save failed: {e}") from e
        text = (res.text or "")[:400]
        if res.status_code in (200, 201):
            try:
                versions = res.json()
                for pl in players:
                    pl.db_version = int(versions[str(pl.user_id)])
                    pl._mon_hashes = saved_hashes[pl.user_id]
            except (ValueError, TypeError, KeyError) as e:
                raise DatabaseError(f"multi-player save returned unreadable versions: {text}") from e
            return True
        if "version_conflict" in text or res.status_code == 409:
            raise ConcurrentUpdateError(f"a player in this save was changed elsewhere: {text}")
        if _is_missing_function(res):
            raise SchemaError("save_players_atomic() is missing — run database/schema.sql")
        if _is_missing_column(res):
            raise SchemaError(f"schema is out of date ({text}) — run database/schema.sql")
        raise DatabaseError(f"multi-player save failed ({res.status_code}): {text}")

    def _save_player_legacy(self, player, data: dict, rows: list) -> bool:
        """Transitional two-request save (NOT atomic, NOT version-checked, does NOT delete released/reset Pokémon). Only reachable with
        ALLOW_LEGACY_SAVE=1 while schema.sql hasn't been applied. Still fails closed on missing columns."""
        merge = {**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"}
        try:
            res = dbhttp.post(f"{self.url}/rest/v1/players?on_conflict=user_id", headers=merge, json=data, timeout=20)
            if res.status_code not in (200, 201, 204):
                raise DatabaseError(f"player save failed ({res.status_code}): {res.text[:300]}")
            if rows:
                res = dbhttp.post(f"{self.url}/rest/v1/pokemon?on_conflict=id", headers=merge, json=rows, timeout=20)
                if res.status_code not in (200, 201, 204):
                    raise DatabaseError(f"pokemon save failed ({res.status_code}): {res.text[:300]}")
        except requests.RequestException as e:
            raise DatabaseError(f"player save failed: {e}") from e
        return True

    def find_players_by_username(self, name: str, limit: int = 10):
        """[(user_id, username)] for players whose username matches `name` (case-insensitive, exact)."""
        res = dbhttp.get(
            f"{self.url}/rest/v1/players",
            params={"username": f"ilike.{name}", "select": "user_id,username", "limit": "50"},
            headers=self.headers, timeout=15,
        )
        if res.status_code != 200:
            raise DatabaseError(f"username lookup failed ({res.status_code}): {res.text[:200]}")
        # `_` and `%` are wildcards in LIKE patterns, so keep only true case-insensitive exact matches
        exact = [(int(r["user_id"]), r["username"]) for r in res.json()
                 if (r["username"] or "").lower() == name.lower()]
        return exact[:limit]

    def get_assets(self) -> dict:
        """Get all site assets. Returns empty dict if none exist (valid state).
        Raises DatabaseError if the read failed (network error, HTTP error, malformed response)."""
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/site_assets?select=key,url", headers=self.headers, timeout=15)
            if res.status_code != 200:
                raise DatabaseError(f"site_assets read failed ({res.status_code}): {res.text[:300]}")
            try:
                rows = res.json()
            except ValueError as e:
                raise DatabaseError("site_assets response was unreadable") from e
            return {r["key"]: r["url"] for r in rows}
        except requests.RequestException as e:
            raise DatabaseError(f"site_assets read failed: {e}") from e

    def set_asset(self, key: str, url: str) -> bool:
        """Save a site asset. Returns True if successful.
        Raises DatabaseError if the write failed."""
        try:
            res = dbhttp.post(f"{self.url}/rest/v1/site_assets?on_conflict=key",
                                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                                json={"key": key, "url": url}, timeout=15)
            if res.status_code not in (200, 201, 204):
                raise DatabaseError(f"site_assets write failed ({res.status_code}): {res.text[:300]}")
            return True
        except requests.RequestException as e:
            raise DatabaseError(f"site_assets write failed: {e}") from e

    def delete_asset(self, key: str) -> bool:
        """Delete a site asset. Returns True if successful (or already absent).
        Raises DatabaseError if the delete failed."""
        try:
            res = dbhttp.delete(f"{self.url}/rest/v1/site_assets?key=eq.{key}", headers=self.headers, timeout=15)
            if res.status_code not in (200, 204):
                raise DatabaseError(f"site_assets delete failed ({res.status_code}): {res.text[:300]}")
            return True
        except requests.RequestException as e:
            raise DatabaseError(f"site_assets delete failed: {e}") from e

    def load_player(self, user_id: int):
        """Load a player. Returns the player, or None ONLY when the database positively answered that no such
        player exists. EVERY other outcome — network error, HTTP error, malformed JSON, a row that can't be
        rebuilt — raises DatabaseError, so callers can never mistake a failed read for a new player."""
        try:
            fetched = self._fetch_player_rows(user_id)
            if fetched is None:
                return None                      # the one and only "genuinely absent" answer
            row, poke_rows = fetched
            return self._build_player(user_id, row, poke_rows)
        except DatabaseError:
            raise
        except requests.RequestException as e:
            raise DatabaseError(f"players lookup failed: {e}") from e
        except Exception as e:                   # bad JSON, missing keys, deserialisation bugs…
            logger.error(f"Error loading player {user_id}: {e}")
            raise DatabaseError(f"player {user_id} could not be loaded: {e}") from e

    _bundle_ok = None        # None = untried, False = the load_player_bundle() function isn't installed

    def _fetch_player_rows(self, user_id: int):
        """-> (player row, [pokemon rows]) or None when there is no such player. ONE round trip through the
        load_player_bundle() function; the older two-request read is the fallback when schema.sql hasn't been re-run."""
        if SupabaseDB._bundle_ok is not False:
            response = dbhttp.post(f"{self.url}/rest/v1/rpc/load_player_bundle", headers=self.headers,
                                   json={"p_user_id": int(user_id)}, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if data is None:
                    return None
                if not isinstance(data, dict) or "player" not in data or not isinstance(data.get("pokemon"), list):
                    raise DatabaseError("player bundle had an unexpected shape")
                return data["player"], data["pokemon"]
            if _is_missing_function(response):
                SupabaseDB._bundle_ok = False
                logger.warning("load_player_bundle() is missing — loading players in two requests until schema.sql is re-run")
            else:
                raise DatabaseError(f"player load failed ({response.status_code}): {response.text[:300]}")

        response = dbhttp.get(f"{self.url}/rest/v1/players?user_id=eq.{user_id}", headers=self.headers, timeout=20)
        if response.status_code != 200:
            raise DatabaseError(f"players lookup failed ({response.status_code}): {response.text[:300]}")
        data_list = response.json()
        if not isinstance(data_list, list):
            raise DatabaseError(f"players lookup returned {type(data_list).__name__}, expected a list")
        if not data_list:
            return None
        pokemon_response = dbhttp.get(f"{self.url}/rest/v1/pokemon?player_id=eq.{user_id}", headers=self.headers, timeout=20)
        if pokemon_response.status_code != 200:
            raise DatabaseError(f"pokemon lookup failed ({pokemon_response.status_code}): {pokemon_response.text[:300]}")
        poke_rows = pokemon_response.json()
        if not isinstance(poke_rows, list):
            raise DatabaseError("pokemon lookup returned an unexpected payload")
        return data_list[0], poke_rows

    def _build_player(self, user_id: int, data: dict, poke_rows: list):
        from player_model import PlayerInstance
        from pokemon_model import PokemonInstance

        p = PlayerInstance(data["user_id"], data["username"])
        p.created_date = data.get("created_date") or p.created_date
        p.level = data.get("level", 1)
        p.experience = data.get("experience", 0)
        p.coins = data.get("coins", 0)
        p.wins = data.get("wins", 0)
        p.losses = data.get("losses", 0)
        p.elo = data.get("elo", 1000)
        p.current_streak = data.get("current_streak", 0)
        p.current_region = data.get("current_region", "kanto")
        p.regions_unlocked = data.get("regions_unlocked", ["kanto"])
        p.pokemon_caught = data.get("pokemon_caught", 0)
        p.pokedex_seen = set(data.get("pokedex_seen", []))
        p.inventory = data.get("inventory", {})
        p.pokeballs = data.get("pokeballs", {})
        p.login_streak = data.get("login_streak", 1)
        p.badges = data.get("badges", [])
        p.achievements = data.get("achievements", [])
        p.successful_referrals = data.get("successful_referrals", 0)
        p.referral_code = data.get("referral_code") or p.referral_code      # was regenerated on every load
        p.avatar = data.get("avatar")
        p.story = data.get("story") or {}
        p.db_version = int(data.get("version") or 0)                         # for optimistic locking on save

        # Pokémon: ONE canonical loader (PokemonInstance.from_dict). A failure here is an ERROR — never an
        # empty roster, and never a quietly smaller one.
        all_pokemon = {}
        for poke_data in poke_rows:
            try:
                poke_data = dict(poke_data)
                poke_data["trainer_id"] = poke_data.get("trainer_id") or user_id
                poke = PokemonInstance.from_dict(poke_data)
            except Exception as e:
                raise DatabaseError(f"could not rebuild Pokemon {poke_data.get('id')} "
                                    f"({poke_data.get('species_name')}): {e}") from e
            all_pokemon[poke.id] = poke

        active_team_ids = data.get("active_team", []) or []
        p.active_team = [all_pokemon[i] for i in active_team_ids if i in all_pokemon]
        missing = [i for i in active_team_ids if i not in all_pokemon]
        if missing:
            # a team row that can't be found is a data-integrity failure, not a smaller roster
            raise DatabaseError(f"player {user_id}: team references {len(missing)} Pokemon missing from the pokemon "
                                f"table: {missing}")
        p.pokemon_collection = list(all_pokemon.values())
        # remember what was loaded so a save sends only the Pokémon that changed
        p._mon_hashes = {m.id: self._row_hash(m.to_db_dict()) for m in all_pokemon.values()}
        logger.info(f"✅ Loaded player {user_id} with {len(p.active_team)} Pokemon in team, {len(p.pokemon_collection)} total caught")
        return p

    def player_exists(self, user_id: int) -> bool:
        """True/False only when the database answered; raises DatabaseError when it could not."""
        try:
            response = dbhttp.get(f"{self.url}/rest/v1/players?user_id=eq.{user_id}&select=user_id",
                                    headers=self.headers, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"players lookup failed: {e}") from e
        if response.status_code != 200:
            raise DatabaseError(f"players lookup failed ({response.status_code}): {response.text[:200]}")
        return len(response.json()) > 0

    # ── Pokemon operations ──
    
    def get_leaderboard(self, limit: int = 100) -> List:
        """Top players by ELO. An empty list means the query succeeded and there are no players; any failure
        raises DatabaseError (an outage must never look like an empty leaderboard)."""
        try:
            response = dbhttp.get(f"{self.url}/rest/v1/players?order=elo.desc&limit={int(limit)}",
                                    headers=self.headers, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"leaderboard read failed: {e}") from e
        if response.status_code != 200:
            raise DatabaseError(f"leaderboard read failed ({response.status_code}): {response.text[:200]}")
        try:
            rows = response.json()
        except ValueError as e:
            raise DatabaseError("leaderboard response was unreadable") from e
        if not isinstance(rows, list):
            raise DatabaseError("leaderboard response was not a list")
        return rows

    def _count(self, table: str) -> int:
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/{table}?select=*&limit=1",
                               headers={**self.headers, "Prefer": "count=exact"}, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"{table} count failed: {e}") from e
        if res.status_code not in (200, 206):
            raise DatabaseError(f"{table} count failed ({res.status_code}): {res.text[:200]}")
        try:
            return int(res.headers.get("content-range", "").split("/")[-1])
        except ValueError as e:
            raise DatabaseError(f"{table} count unreadable") from e

    def get_stats(self) -> Dict:
        """Row counts. Raises DatabaseError on any failure (never an empty dict that looks like 'no data')."""
        return {"total_players": self._count("players"), "total_pokemon": self._count("pokemon")}

# Credentials come from the environment only (Render, Vercel, the bot host). Never hardcode them in the repository.
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# None when not configured: the API then runs in in-memory mode, and the bot refuses to start
db = SupabaseDB(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

if __name__ == "__main__":
    if db is None:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY first.")
    print("✅ Supabase connected")
    stats = db.get_stats()
    print(f"Stats: {stats}")

