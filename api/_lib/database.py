"""
⚡ POSHOW - SUPABASE DATABASE - FIXED
Cloud-based persistence using Supabase
Properly loads active_team and pokemon_collection
"""

import requests
import json
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """The database could not be reached / answered with an error.
    Distinct from "player not found" (load_player returns None) so a network blip can never
    be mistaken for a brand-new player and overwrite real progress."""


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
    
    # ════════════════════════════════════════════════════════════════
    # PLAYER OPERATIONS
    # ════════════════════════════════════════════════════════════════
    
    def save_player(self, player) -> bool:
        """Persist the WHOLE player: stats row (incl. which Pokemon are on the team) and every
        Pokemon they own. Two HTTP calls total (upserts), and every failure is logged with
        Supabase's actual error text — before, Pokemon rows failed silently when the table
        schema didn't match, which is how teams vanished on the next load."""
        try:
            data = player.to_dict()
            data["active_team"] = [p.id for p in player.active_team]

            res = requests.post(
                f"{self.url}/rest/v1/players?on_conflict=user_id",
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=data,
                timeout=20,
            )
            if res.status_code not in (200, 201, 204) and ("'story'" in res.text or "'avatar'" in res.text):
                # database.schema.sql hasn't been re-run since avatars/journey were added: keep the player
                # saving (without those two fields) instead of breaking the whole game, and say so loudly
                logger.error("⚠️ players.avatar / players.story columns are missing — run database/schema.sql. "
                             "Saving WITHOUT them; journey progress won't persist until you do.")
                data.pop("avatar", None)
                data.pop("story", None)
                res = requests.post(
                    f"{self.url}/rest/v1/players?on_conflict=user_id",
                    headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                    json=data,
                    timeout=20,
                )
            if res.status_code not in (200, 201, 204):
                logger.error(f"❌ Save player {player.user_id} failed ({res.status_code}): {res.text}")
                return False

            # team + collection, de-duplicated (a starter lives in the team only until caught again)
            mons = {}
            for m in list(player.pokemon_collection) + list(player.active_team):
                mons[m.id] = m
            if mons:
                rows = []
                for m in mons.values():
                    row = m.to_dict()
                    row["player_id"] = player.user_id
                    rows.append(row)
                res = requests.post(
                    f"{self.url}/rest/v1/pokemon?on_conflict=id",
                    headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                    json=rows,
                    timeout=20,
                )
                if res.status_code not in (200, 201, 204):
                    logger.error(f"❌ Save pokemon for {player.user_id} failed ({res.status_code}): {res.text}")
                    return False

            logger.info(f"✅ Saved player {player.user_id} ({len(mons)} Pokemon)")
            return True
        except requests.RequestException as e:
            logger.error(f"Error saving player {player.user_id}: {e}")
            return False

    def load_player(self, user_id: int):
        """Load player from Supabase - FIXED to load active_team and pokemon_collection"""
        try:
            from player_model import PlayerInstance
            from pokemon_model import PokemonInstance
            
            response = requests.get(
                f"{self.url}/rest/v1/players?user_id=eq.{user_id}",
                headers=self.headers,
                timeout=20,
            )
            if response.status_code != 200:
                raise DatabaseError(f"players lookup failed ({response.status_code}): {response.text[:300]}")

            data_list = response.json()
            if data_list and len(data_list) > 0:
                data = data_list[0]
                p = PlayerInstance(data["user_id"], data["username"])
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
                p.avatar = data.get("avatar")
                p.story = data.get("story") or {}
                
                # ✅ FIXED: Load active_team and pokemon_collection
                try:
                    # Get all Pokemon for this player
                    pokemon_response = requests.get(
                        f"{self.url}/rest/v1/pokemon?player_id=eq.{user_id}",
                        headers=self.headers,
                        timeout=20,
                    )
                    
                    if pokemon_response.status_code == 200:
                        all_pokemon = {}
                        pokemon_data_list = pokemon_response.json()
                        
                        # Build Pokemon objects
                        for poke_data in pokemon_data_list:
                            try:
                                poke = PokemonInstance(
                                    poke_data["species_name"], 
                                    poke_data["level"], 
                                    user_id
                                )
                                poke.id = poke_data["id"]
                                poke.nickname = poke_data.get("nickname", poke_data["species_name"])
                                poke.current_hp = poke_data.get("current_hp", poke.max_hp)
                                poke.moves = poke_data.get("moves", [])
                                poke.iv = poke_data.get("iv", {})
                                poke.ev = poke_data.get("ev", {})
                                poke.nature = poke_data.get("nature", "Neutral")
                                poke.is_shiny = poke_data.get("is_shiny", False)
                                poke.happiness = poke_data.get("happiness", 0)
                                poke.status = poke_data.get("status")
                                poke.experience = poke_data.get("experience", 0)
                                poke.is_fainted = bool(poke_data.get("is_fainted", False))
                                
                                all_pokemon[poke.id] = poke
                            except Exception as e:
                                logger.warning(f"Could not load individual Pokemon: {e}")
                        
                        # Rebuild active team with actual Pokemon objects
                        active_team_ids = data.get("active_team", [])
                        p.active_team = []
                        
                        if active_team_ids:
                            for poke_id in active_team_ids:
                                if poke_id in all_pokemon:
                                    p.active_team.append(all_pokemon[poke_id])
                        
                        # Set pokemon_collection to all caught Pokemon
                        p.pokemon_collection = list(all_pokemon.values())
                        
                        logger.info(f"✅ Loaded player {user_id} with {len(p.active_team)} Pokemon in team, {len(p.pokemon_collection)} total caught")
                    else:
                        p.active_team = []
                        p.pokemon_collection = []
                        logger.warning(f"Could not load Pokemon for player {user_id}: {pokemon_response.status_code}")
                
                except Exception as e:
                    logger.warning(f"Error loading Pokemon for player {user_id}: {e}")
                    p.active_team = []
                    p.pokemon_collection = []
                
                return p
            return None
        except DatabaseError:
            raise
        except requests.RequestException as e:
            raise DatabaseError(f"players lookup failed: {e}") from e
        except Exception as e:
            logger.error(f"Error loading player: {e}")
            return None
    
    def player_exists(self, user_id: int) -> bool:
        """Check if player exists"""
        try:
            response = requests.get(
                f"{self.url}/rest/v1/players?user_id=eq.{user_id}",
                headers=self.headers
            )
            return len(response.json()) > 0
        except:
            return False
    
    # ════════════════════════════════════════════════════════════════
    # POKEMON OPERATIONS
    # ════════════════════════════════════════════════════════════════
    
    def save_pokemon(self, pokemon, player_id: int) -> bool:
        """Save Pokemon to Supabase"""
        try:
            data = pokemon.to_dict()
            data["player_id"] = player_id
            
            # Check if exists
            response = requests.get(
                f"{self.url}/rest/v1/pokemon?id=eq.{pokemon.id}",
                headers=self.headers
            )
            
            if response.json():
                # Update
                response = requests.patch(
                    f"{self.url}/rest/v1/pokemon?id=eq.{pokemon.id}",
                    headers=self.headers,
                    json=data
                )
            else:
                # Insert
                response = requests.post(
                    f"{self.url}/rest/v1/pokemon",
                    headers=self.headers,
                    json=data
                )
            
            if response.status_code not in [200, 201, 204]:
                logger.error(f"❌ Save pokemon {pokemon.id} failed ({response.status_code}): {response.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error saving Pokemon: {e}")
            return False
    
    def get_player_pokemon(self, player_id: int) -> List:
        """Get all Pokemon for player"""
        try:
            from pokemon_model import PokemonInstance
            
            response = requests.get(
                f"{self.url}/rest/v1/pokemon?player_id=eq.{player_id}",
                headers=self.headers
            )
            
            pokemon_list = []
            for data in response.json():
                # Create Pokemon instance from data
                p = PokemonInstance(data["species_name"], data["level"], player_id)
                p.id = data["id"]
                p.nickname = data["nickname"]
                p.iv = data.get("iv", {})
                p.ev = data.get("ev", {})
                p.nature = data.get("nature", "Neutral")
                p.current_hp = data.get("current_hp", p.max_hp)
                p.status = data.get("status")
                p.moves = data.get("moves", [])
                pokemon_list.append(p)
            
            return pokemon_list
        except Exception as e:
            logger.error(f"Error getting Pokemon: {e}")
            return []
    
    # ════════════════════════════════════════════════════════════════
    # LEADERBOARD
    # ════════════════════════════════════════════════════════════════
    
    def get_leaderboard(self, limit: int = 100) -> List:
        """Get top players"""
        try:
            response = requests.get(
                f"{self.url}/rest/v1/players?order=elo.desc&limit={limit}",
                headers=self.headers
            )
            
            return response.json()
        except:
            return []
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            players = requests.get(
                f"{self.url}/rest/v1/players?select=count",
                headers=self.headers
            )
            
            pokemon = requests.get(
                f"{self.url}/rest/v1/pokemon?select=count",
                headers=self.headers
            )
            
            return {
                "total_players": len(players.json()),
                "total_pokemon": len(pokemon.json()),
            }
        except:
            return {}

# Credentials come from the environment ONLY (Render / Vercel / the bot host).
# They used to be hardcoded here, which publishes them to anyone who can read the repo.
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

