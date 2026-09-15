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
        """Save player to Supabase"""
        try:
            data = player.to_dict()
            
            # Check if player exists
            response = requests.get(
                f"{self.url}/rest/v1/players?user_id=eq.{player.user_id}",
                headers=self.headers
            )
            
            if response.json():
                # Update
                response = requests.patch(
                    f"{self.url}/rest/v1/players?user_id=eq.{player.user_id}",
                    headers=self.headers,
                    json=data
                )
            else:
                # Insert
                response = requests.post(
                    f"{self.url}/rest/v1/players",
                    headers=self.headers,
                    json=data
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Saved player {player.user_id}")
                return True
            else:
                logger.error(f"❌ Save failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error saving player: {e}")
            return False
    
    def load_player(self, user_id: int):
        """Load player from Supabase - FIXED to load active_team and pokemon_collection"""
        try:
            from player_model import PlayerInstance
            from pokemon_model import PokemonInstance
            
            response = requests.get(
                f"{self.url}/rest/v1/players?user_id=eq.{user_id}",
                headers=self.headers
            )
            
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
                
                # ✅ FIXED: Load active_team and pokemon_collection
                try:
                    # Get all Pokemon for this player
                    pokemon_response = requests.get(
                        f"{self.url}/rest/v1/pokemon?player_id=eq.{user_id}",
                        headers=self.headers
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
            
            return response.status_code in [200, 201]
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

# Supabase credentials
SUPABASE_URL = "https://vobygrdzjhamubzcsgtw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZvYnlncmR6amhhbXViemNzZ3R3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAyMDcxMjIsImV4cCI6MjA5NTc4MzEyMn0.HhMLtg_J3h1ELlYodYrhniLRFyJspGP-82wyzCXJmuU"

# Initialize Supabase
db = SupabaseDB(SUPABASE_URL, SUPABASE_KEY)

if __name__ == "__main__":
    print("✅ Supabase connected")
    stats = db.get_stats()
    print(f"Stats: {stats}")

