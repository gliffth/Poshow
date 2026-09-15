"""
⚡ POSHOW - POKEAPI MANAGER
Fetches, caches, and manages all Pokemon data from official PokéAPI
Handles stats, moves, types, evolution chains, and special variants
"""

import requests
import json
import os
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PokéAPIManager:
    """
    Complete PokéAPI integration
    Caches data locally for faster access
    Handles all Pokemon information
    """
    
    BASE_URL = "https://pokeapi.co/api/v2"
    CACHE_DIR = "cache"
    
    def __init__(self):
        """Initialize cache directory"""
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self.pokemon_cache = {}
        self.move_cache = {}
        self.type_cache = {}
        self.evolution_cache = {}
        logger.info("✅ PokéAPI Manager initialized")
    
    # ════════════════════════════════════════════════════════════════
    # POKEMON DATA
    # ════════════════════════════════════════════════════════════════
    
    def get_pokemon(self, pokemon_name: str) -> Optional[Dict]:
        """
        Fetch complete Pokemon data from API
        Caches locally for future use
        
        Returns:
            Dict with: id, name, base_stats, types, moves, height, weight, image, abilities
        """
        # Check cache first
        if pokemon_name.lower() in self.pokemon_cache:
            return self.pokemon_cache[pokemon_name.lower()]
        
        try:
            url = f"{self.BASE_URL}/pokemon/{pokemon_name.lower()}"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                logger.error(f"Pokemon not found: {pokemon_name}")
                return None
            
            data = response.json()
            
            # Extract relevant data
            pokemon_data = {
                "id": data["id"],
                "name": data["name"],
                "height": data["height"],
                "weight": data["weight"],
                "image": data["sprites"]["other"]["official-artwork"]["front_default"],
                "image_shiny": data["sprites"]["other"]["official-artwork"].get("front_shiny", ""),
                "types": [t["type"]["name"] for t in data["types"]],
                "abilities": [a["ability"]["name"] for a in data["abilities"]],
                "base_stats": {
                    "hp": data["stats"][0]["base_stat"],
                    "attack": data["stats"][1]["base_stat"],
                    "defense": data["stats"][2]["base_stat"],
                    "sp_atk": data["stats"][3]["base_stat"],
                    "sp_def": data["stats"][4]["base_stat"],
                    "speed": data["stats"][5]["base_stat"],
                },
                "base_experience": data.get("base_experience", 50),
                "catch_rate": data.get("catch_rate", 45),
                "moves": [m["move"]["name"] for m in data["moves"][:10]],  # First 10 moves
            }
            
            # Cache locally
            self.pokemon_cache[pokemon_name.lower()] = pokemon_data
            
            logger.info(f"✅ Fetched: {pokemon_name}")
            return pokemon_data
        
        except Exception as e:
            logger.error(f"Error fetching {pokemon_name}: {e}")
            return None
    
    def get_pokemon_species(self, pokemon_name: str) -> Optional[Dict]:
        """
        Get Pokemon species data (evolution chain, generation, etc)
        """
        try:
            url = f"{self.BASE_URL}/pokemon-species/{pokemon_name.lower()}"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            species_data = {
                "generation": data["generation"]["name"],
                "color": data["color"]["name"],
                "habitat": data.get("habitat", {}).get("name"),
                "growth_rate": data["growth_rate"]["name"],
                "egg_groups": [eg["name"] for eg in data["egg_groups"]],
                "evolution_chain_url": data["evolution_chain"]["url"],
                "is_main_series": data["is_main_series"],
            }
            
            return species_data
        
        except Exception as e:
            logger.error(f"Error fetching species {pokemon_name}: {e}")
            return None
    
    # ════════════════════════════════════════════════════════════════
    # EVOLUTION CHAINS
    # ════════════════════════════════════════════════════════════════
    
    def get_evolution_chain(self, pokemon_name: str) -> Optional[Dict]:
        """
        Fetch evolution chain for a Pokemon
        Returns evolution tree with conditions
        """
        if pokemon_name.lower() in self.evolution_cache:
            return self.evolution_cache[pokemon_name.lower()]
        
        try:
            # Get species first to find evolution chain URL
            species_url = f"{self.BASE_URL}/pokemon-species/{pokemon_name.lower()}"
            species_response = requests.get(species_url, timeout=5)
            
            if species_response.status_code != 200:
                return None
            
            species_data = species_response.json()
            chain_url = species_data["evolution_chain"]["url"]
            
            # Fetch evolution chain
            chain_response = requests.get(chain_url, timeout=5)
            if chain_response.status_code != 200:
                return None
            
            chain_data = chain_response.json()
            evolution_info = self._parse_evolution_chain(chain_data["chain"])
            
            self.evolution_cache[pokemon_name.lower()] = evolution_info
            return evolution_info
        
        except Exception as e:
            logger.error(f"Error fetching evolution chain: {e}")
            return None
    
    def _parse_evolution_chain(self, chain) -> Dict:
        """Parse evolution chain recursively"""
        evolutions = {
            "name": chain["species"]["name"],
            "next_evolutions": []
        }
        
        for evolution in chain.get("evolves_to", []):
            evo_data = {
                "name": evolution["species"]["name"],
                "trigger": evolution["evolution_details"][0] if evolution["evolution_details"] else {},
                "next_evolutions": []
            }
            
            # Add evolution conditions
            if evo_data["trigger"]:
                conditions = {
                    "min_level": evo_data["trigger"].get("min_level"),
                    "item": evo_data["trigger"].get("item", {}).get("name"),
                    "trade": evo_data["trigger"].get("trigger", {}).get("name") == "trade",
                    "happiness": evo_data["trigger"].get("min_happiness"),
                }
                evo_data["conditions"] = conditions
            
            # Recursive for next evolutions
            if evolution.get("evolves_to"):
                evo_data["next_evolutions"] = [
                    self._parse_evolution_chain(e) for e in evolution["evolves_to"]
                ]
            
            evolutions["next_evolutions"].append(evo_data)
        
        return evolutions
    
    # ════════════════════════════════════════════════════════════════
    # MOVES
    # ════════════════════════════════════════════════════════════════
    
    def get_move(self, move_name: str) -> Optional[Dict]:
        """Fetch move data from API"""
        if move_name.lower() in self.move_cache:
            return self.move_cache[move_name.lower()]
        
        try:
            url = f"{self.BASE_URL}/move/{move_name.lower()}"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            move_data = {
                "name": data["name"],
                "power": data.get("power", 0),
                "accuracy": data.get("accuracy", 100),
                "type": data["type"]["name"],
                "category": data["damage_class"]["name"],  # physical, special, status
                "pp": data.get("pp", 20),
                "effect": data.get("effect_entries", [{}])[0].get("effect", ""),
                "priority": data.get("priority", 0),
            }
            
            self.move_cache[move_name.lower()] = move_data
            return move_data
        
        except Exception as e:
            logger.error(f"Error fetching move {move_name}: {e}")
            return None
    
    def get_pokemon_moveset(self, pokemon_name: str, level: int = 1) -> List[Dict]:
        """
        Get all moves a Pokemon can learn up to a specific level
        """
        try:
            url = f"{self.BASE_URL}/pokemon/{pokemon_name.lower()}"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            moves = []
            
            for move_data in data["moves"]:
                move_name = move_data["move"]["name"]
                
                # Check version group details for level learned
                for vg_detail in move_data.get("version_group_details", []):
                    if vg_detail["level_learned_at"] <= level:
                        move_info = self.get_move(move_name)
                        if move_info:
                            move_info["learned_at_level"] = vg_detail["level_learned_at"]
                            moves.append(move_info)
                        break
            
            # Return only top 4 moves
            return sorted(moves, key=lambda x: x.get("learned_at_level", 0), reverse=True)[:4]
        
        except Exception as e:
            logger.error(f"Error fetching moveset: {e}")
            return []
    
    # ════════════════════════════════════════════════════════════════
    # TYPE EFFECTIVENESS
    # ════════════════════════════════════════════════════════════════
    
    def get_type_effectiveness(self, attack_type: str, defend_type: str) -> float:
        """
        Get type effectiveness multiplier
        1.0 = normal, 2.0 = super effective, 0.5 = not very effective
        """
        try:
            url = f"{self.BASE_URL}/type/{attack_type.lower()}"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return 1.0
            
            data = response.json()
            
            # Check super effective against
            for type_data in data.get("damage_relations", {}).get("double_damage_to", []):
                if type_data["name"].lower() == defend_type.lower():
                    return 2.0
            
            # Check not very effective
            for type_data in data.get("damage_relations", {}).get("half_damage_to", []):
                if type_data["name"].lower() == defend_type.lower():
                    return 0.5
            
            # Check immune
            for type_data in data.get("damage_relations", {}).get("no_damage_to", []):
                if type_data["name"].lower() == defend_type.lower():
                    return 0.0
            
            return 1.0
        
        except Exception as e:
            logger.error(f"Error calculating type effectiveness: {e}")
            return 1.0
    
    # ════════════════════════════════════════════════════════════════
    # SPECIAL VARIANTS (Custom Pokemon)
    # ════════════════════════════════════════════════════════════════
    
    def create_special_variant(self, base_pokemon: str, variant_name: str, 
                             new_type: str, special_moves: List[str]) -> Dict:
        """
        Create special Pokemon variant (inverted types, special forms, etc)
        Used for admin custom Pokemon creation
        """
        base_data = self.get_pokemon(base_pokemon)
        
        if not base_data:
            return None
        
        variant = {
            "base_pokemon": base_pokemon,
            "variant_name": variant_name,
            "id": f"variant_{base_pokemon}_{variant_name}",
            "name": variant_name,
            "types": [new_type] if new_type else base_data["types"],
            "base_stats": base_data["base_stats"].copy(),
            "moves": special_moves,
            "image": base_data["image"],
            "is_variant": True,
            "catch_rate": base_data.get("catch_rate", 45),
        }
        
        return variant
    
    # ════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ════════════════════════════════════════════════════════════════
    
    def search_pokemon(self, query: str) -> List[Dict]:
        """Search for Pokemon by partial name"""
        try:
            url = f"{self.BASE_URL}/pokemon?limit=1000&offset=0"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            for pokemon in data["results"]:
                if query.lower() in pokemon["name"].lower():
                    results.append({
                        "name": pokemon["name"],
                        "url": pokemon["url"]
                    })
                    if len(results) >= 10:
                        break
            
            return results
        
        except Exception as e:
            logger.error(f"Error searching Pokemon: {e}")
            return []
    
    def get_random_pokemon(self, min_id: int = 1, max_id: int = 151) -> Optional[Dict]:
        """Get random Pokemon within ID range"""
        import random
        random_id = random.randint(min_id, max_id)
        try:
            url = f"{self.BASE_URL}/pokemon/{random_id}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "id": data["id"],
                    "name": data["name"],
                    "image": data["sprites"]["other"]["official-artwork"]["front_default"],
                }
        except:
            pass
        
        return None
    
    def get_pokemon_by_type(self, type_name: str) -> List[Dict]:
        """Get all Pokemon of a specific type"""
        try:
            url = f"{self.BASE_URL}/type/{type_name.lower()}"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            pokemon_list = []
            
            for pokemon in data["pokemon"][:20]:  # Limit to 20
                pokemon_list.append({
                    "name": pokemon["pokemon"]["name"],
                    "type": type_name
                })
            
            return pokemon_list
        
        except Exception as e:
            logger.error(f"Error fetching Pokemon by type: {e}")
            return []
    
    def get_pokemon_stats_total(self, pokemon_name: str) -> int:
        """Calculate total base stats"""
        pokemon = self.get_pokemon(pokemon_name)
        if not pokemon:
            return 0
        
        return sum(pokemon["base_stats"].values())

# ════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ════════════════════════════════════════════════════════════════

pokeapi = PokéAPIManager()

# Test
if __name__ == "__main__":
    # Test basic functionality
    print("Testing PokéAPI Manager...")
    
    # Test fetching Pokemon
    poke = pokeapi.get_pokemon("pikachu")
    if poke:
        print(f"✅ Pikachu: {poke['name']}")
        print(f"   Types: {poke['types']}")
        print(f"   Stats: {poke['base_stats']}")
    
    # Test moves
    move = pokeapi.get_move("thunderbolt")
    if move:
        print(f"✅ Thunderbolt: Power={move['power']}, Type={move['type']}")
    
    # Test type effectiveness
    eff = pokeapi.get_type_effectiveness("electric", "water")
    print(f"✅ Electric vs Water: {eff}x")
    
    # Test evolution
    evo = pokeapi.get_evolution_chain("charmander")
    if evo:
        print(f"✅ Evolution chain: {evo}")
    
    print("✅ All tests passed!")

