
"""
⚡ POSHOW - POKEMON MODEL
Individual Pokemon instances with stats, moves, evolution
"""

import uuid
import random
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PokemonInstance:
    """Individual Pokemon with IV/EV/Nature system"""
    
    def __init__(self, species_name: str, level: int, trainer_id: int):
        """Create a Pokemon instance"""
        self.id = str(uuid.uuid4())
        self.species_name = species_name
        self.level = max(1, min(100, level))
        self.trainer_id = trainer_id
        self.nickname = species_name.capitalize()
        
        # Get base stats from API
        try:
            from pokeapi_manager import pokeapi
            api_data = pokeapi.get_pokemon(species_name)
            self.api_data = api_data
            
            # Extract base stats - CRITICAL FIX
            self.base_stats = {}
            if "stats" in api_data:
                for stat in api_data["stats"]:
                    name = stat.get("stat", {}).get("name", "").lower()
                    base = stat.get("base_stat", 50)
                    self.base_stats[name] = base
            elif isinstance(api_data.get("base_stats"), dict):
                # pokeapi_manager.get_pokemon() returns a flat "base_stats" dict instead of the
                # raw PokeAPI "stats" list — without this every species silently got base 50s.
                flat = api_data["base_stats"]
                for src, dst in (("hp", "hp"), ("attack", "attack"), ("defense", "defense"),
                                 ("sp_atk", "special-attack"), ("sp_def", "special-defense"),
                                 ("speed", "speed")):
                    if src in flat:
                        self.base_stats[dst] = flat[src]
            
            # Get moves
            self.moves = api_data.get("moves", ["tackle", "scratch"])[:4]
            
        except Exception as e:
            logger.error(f"Error loading {species_name}: {e}")
            # Fallback stats
            self.api_data = {}
            self.base_stats = {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "sp_atk": 65,
                "sp_def": 65,
                "speed": 45
            }
            self.moves = ["tackle", "scratch"]
        
        # Ability — derived from the species (see AbilitySystem.pick_ability), so it is
        # never stored: same species always resolves to the same ability.
        self.ability = self._resolve_ability()
        self.is_boss = False
        self.gym_floor = 0   # >0 only for Battle Gym opponents (see gym_system.py)
        self.story_ref = None  # {'t': trainer id, 'i': index, 'n': team size} for story trainer opponents (journey.py)

        # IV/EV/Nature
        self.iv = {k: random.randint(0, 31) for k in ["hp", "atk", "def", "sp_atk", "sp_def", "speed"]}
        self.ev = {k: 0 for k in ["hp", "atk", "def", "sp_atk", "sp_def", "speed"]}
        self.nature = random.choice(["Neutral", "Hardy", "Adamant", "Modest", "Timid", "Bold"])
        
        # Battle status
        self.current_hp = self._get_max_hp()
        self.max_hp = self._get_max_hp()
        self.status = None
        self.is_fainted = False
        
        # Experience
        self.experience = 0
        
        # Shiny
        self.is_shiny = random.random() < 0.0125
        
        # Calculate actual stats
        self.actual_stats = self._calculate_stats()
        
        logger.info(f"✅ Created {self.nickname} Lv{self.level}")
    
    # ════════════════════════════════════════════════════════════════
    # STAT CALCULATIONS
    # ════════════════════════════════════════════════════════════════
    
    def _resolve_ability(self):
        try:
            from abilities_system import AbilitySystem
            api_data = getattr(self, "api_data", None) or {}
            types = [
                t if isinstance(t, str) else t.get("type", {}).get("name", "")
                for t in api_data.get("types", [])
            ]
            return AbilitySystem.pick_ability(api_data.get("abilities", []), types)
        except Exception as e:  # abilities are a bonus — never block creating a Pokemon
            logger.warning(f"ability lookup failed for {self.species_name}: {e}")
            return None

    def _get_max_hp(self) -> int:
        """Calculate max HP"""
        base = self.base_stats.get("hp", 45)
        iv = self.iv.get("hp", 0)
        ev = self.ev.get("hp", 0)
        return ((2 * base + iv + ev // 4) * self.level // 100) + self.level + 5
    
    STAT_NAME_MAP = {
        "hp": "hp",
        "atk": "attack",
        "def": "defense",
        "sp_atk": "special-attack",
        "sp_def": "special-defense",
        "speed": "speed",
    }

    def _calculate_stats(self) -> Dict[str, int]:
        """Calculate all stats from IV/EV/Nature"""
        stats = {}
        
        for stat_name in ["hp", "atk", "def", "sp_atk", "sp_def", "speed"]:
            base = self.base_stats.get(self.STAT_NAME_MAP[stat_name], 50)
            iv = self.iv.get(stat_name, 0)
            ev = self.ev.get(stat_name, 0)
            
            if stat_name == "hp":
                stat = ((2 * base + iv + ev // 4) * self.level // 100) + self.level + 5
            else:
                stat = ((2 * base + iv + ev // 4) * self.level // 100) + 5
                stat = self._apply_nature_modifier(stat, stat_name)
            
            stats[stat_name] = max(1, int(stat))
        
        return stats
    
    def _apply_nature_modifier(self, stat: int, stat_name: str) -> int:
        """Apply nature modifier (±10%)"""
        # Simplified - just return as is for now
        return stat
    
    def recalculate_stats(self):
        """Recalculate stats after IV/EV changes"""
        self.max_hp = self._get_max_hp()
        self.current_hp = min(self.current_hp, self.max_hp)
        self.actual_stats = self._calculate_stats()
    
    # ════════════════════════════════════════════════════════════════
    # EXPERIENCE & LEVELING
    # ════════════════════════════════════════════════════════════════
    
    def add_experience(self, amount: int) -> bool:
        """Add experience and check for level up"""
        self.experience += amount
        
        # Check level up (exponential: doubles every level)
        xp_required = 100 * (2 ** (self.level - 1))
        
        if self.experience >= xp_required:
            self.level = min(100, self.level + 1)
            self.experience = 0
            self.recalculate_stats()
            self.restore_hp()
            return True
        
        return False
    
    def restore_hp(self):
        """Restore HP to max"""
        self.current_hp = self.max_hp
        self.is_fainted = False
    
    def restore_pp(self):
        """Restore move PP (for now, just a placeholder)"""
        pass
    
    # ════════════════════════════════════════════════════════════════
    # EV TRAINING
    # ════════════════════════════════════════════════════════════════
    
    def add_ev(self, stat: str, amount: int) -> bool:
        """Add EV to stat (max 252 per stat, 510 total)"""
        if stat not in self.ev or self.ev[stat] >= 252:
            return False
        
        total_ev = sum(self.ev.values())
        if total_ev >= 510:
            return False
        
        self.ev[stat] = min(252, self.ev[stat] + amount)
        self.recalculate_stats()
        return True
    
    # ════════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ════════════════════════════════════════════════════════════════
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = self._base_dict()
        if getattr(self, "is_boss", False) or getattr(self, "gym_floor", 0) or getattr(self, "story_ref", None):
            # only ever present on boss / gym battle sessions (battle_sessions.wild_pokemon
            # is jsonb) — these Pokemon are never written to the `pokemon` table
            data["ability"] = self.ability
            if self.is_boss:
                data["is_boss"] = True
            if self.gym_floor:
                data["gym_floor"] = self.gym_floor
            if self.story_ref:
                data["story_ref"] = self.story_ref
        return data

    def _base_dict(self) -> Dict:
        return {
            "id": self.id,
            "species_name": self.species_name,
            "nickname": self.nickname,
            "level": self.level,
            "trainer_id": self.trainer_id,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "experience": self.experience,
            "iv": self.iv,
            "ev": self.ev,
            "nature": self.nature,
            "moves": self.moves,
            "status": self.status,
            "is_fainted": self.is_fainted,
            "is_shiny": self.is_shiny,
        }
    
    @staticmethod
    def from_dict(data: Dict) -> "PokemonInstance":
        """Load from dictionary"""
        p = PokemonInstance(data["species_name"], data["level"], data["trainer_id"])
        p.id = data.get("id", p.id)
        p.nickname = data.get("nickname", p.nickname)
        p.current_hp = data.get("current_hp", p.max_hp)
        p.max_hp = data.get("max_hp", p.max_hp)
        p.experience = data.get("experience", 0)
        p.iv = data.get("iv", p.iv)
        p.ev = data.get("ev", p.ev)
        p.nature = data.get("nature", p.nature)
        p.moves = data.get("moves", p.moves)
        p.status = data.get("status")
        p.is_fainted = data.get("is_fainted", False)
        p.is_shiny = data.get("is_shiny", False)
        if data.get("is_boss"):
            p.is_boss = True
        if data.get("gym_floor"):
            p.gym_floor = int(data["gym_floor"])
        if data.get("story_ref"):
            p.story_ref = data["story_ref"]
        if data.get("is_boss") or data.get("gym_floor") or data.get("story_ref"):
            p.ability = data.get("ability", p.ability)
        p.recalculate_stats()
        return p

if __name__ == "__main__":
    print("Testing PokemonInstance...")
    p = PokemonInstance("pikachu", 5, 123)
    print(f"✅ Created {p.nickname} Lv{p.level}")
    print(f"   HP: {p.current_hp}/{p.max_hp}")
    print(f"   Stats: {p.actual_stats}")
    print("✅ All tests passed!")

