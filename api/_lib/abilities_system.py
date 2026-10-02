"""
⚡ POSHOW - ABILITIES SYSTEM
Pokemon abilities with battle effects
"""

import logging
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Ability:
    """Pokemon ability with battle effects"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def apply_damage_modifier(self, base_damage: int, attacker, defender, move) -> int:
        """Modify damage based on ability"""
        return base_damage
    
    def apply_stat_modifier(self, stats: Dict, pokemon_type: str) -> Dict:
        """Modify stats"""
        return stats


class OffensiveAbility(Ability):
    """Abilities that increase damage output"""
    
    def __init__(self, name: str, description: str, damage_boost: float = 1.3):
        super().__init__(name, description)
        self.damage_boost = damage_boost


class DefensiveAbility(Ability):
    """Abilities that reduce damage intake"""
    
    def __init__(self, name: str, description: str, damage_reduction: float = 0.8):
        super().__init__(name, description)
        self.damage_reduction = damage_reduction


class TypeAbility(Ability):
    """Abilities that boost specific type moves"""
    
    def __init__(self, name: str, description: str, boosted_type: str, boost: float = 1.5):
        super().__init__(name, description)
        self.boosted_type = boosted_type
        self.boost = boost


# OFFENSIVE ABILITIES
ABILITY_DATABASE = {
    "intimidate": OffensiveAbility(
        "Intimidate",
        "Lowers foe's Attack on entry",
        damage_boost=1.0
    ),
    "blaze": TypeAbility(
        "Blaze",
        "Fire moves are 1.5x stronger when HP is low",
        "fire",
        boost=1.5
    ),
    "torrent": TypeAbility(
        "Torrent",
        "Water moves are 1.5x stronger when HP is low",
        "water",
        boost=1.5
    ),
    "overgrow": TypeAbility(
        "Overgrow",
        "Grass moves are 1.5x stronger when HP is low",
        "grass",
        boost=1.5
    ),
    "static": OffensiveAbility(
        "Static",
        "May paralyze attacker on contact",
        damage_boost=1.0
    ),
    "volt_absorb": DefensiveAbility(
        "Volt Absorb",
        "Heals 1/4 HP when hit by Electric move",
        damage_reduction=0.75
    ),
    "water_absorb": DefensiveAbility(
        "Water Absorb",
        "Heals 1/4 HP when hit by Water move",
        damage_reduction=0.75
    ),
    "flash_fire": DefensiveAbility(
        "Flash Fire",
        "Absorbs Fire move, boosts Fire moves 1.5x",
        damage_reduction=0.5
    ),
    "drought": OffensiveAbility(
        "Drought",
        "Summons harsh sunlight",
        damage_boost=1.2
    ),
    "sand_stream": OffensiveAbility(
        "Sand Stream",
        "Summons sandstorm",
        damage_boost=1.15
    ),
    "rain_dish": DefensiveAbility(
        "Rain Dish",
        "Heals 1/8 HP in rain",
        damage_reduction=0.95
    ),
    "swift_swim": OffensiveAbility(
        "Swift Swim",
        "Speed is doubled in rain",
        damage_boost=1.0
    ),
    "chlorophyll": OffensiveAbility(
        "Chlorophyll",
        "Speed is doubled in sunlight",
        damage_boost=1.0
    ),
    "aqua_absorb": DefensiveAbility(
        "Aqua Absorb",
        "Heals 1/4 HP when hit by Water move",
        damage_reduction=0.75
    ),
    "filter": DefensiveAbility(
        "Filter",
        "Reduces super-effective damage to 0.75x",
        damage_reduction=0.75
    ),
    "competitive": OffensiveAbility(
        "Competitive",
        "Raises Sp.Atk when stats are lowered",
        damage_boost=1.2
    ),
    "power_spot": OffensiveAbility(
        "Power Spot",
        "Boosts allies' moves 1.3x",
        damage_boost=1.3
    ),
    "multiscale": DefensiveAbility(
        "Multiscale",
        "Halves damage taken while at full HP",
        damage_reduction=0.5
    ),
    "guts": OffensiveAbility(
        "Guts",
        "Hits 1.2x harder",
        damage_boost=1.2
    ),
    "magic_bounce": DefensiveAbility(
        "Magic Bounce",
        "Takes 10% less damage",
        damage_reduction=0.9
    ),
    "shell_armor": DefensiveAbility(
        "Shell Armor",
        "Takes 10% less damage",
        damage_reduction=0.9
    ),
    "snow_cloak": DefensiveAbility(
        "Snow Cloak",
        "Takes 10% less damage",
        damage_reduction=0.9
    ),
    "sturdy": DefensiveAbility(
        "Sturdy",
        "Survives a knockout hit from full HP with 1 HP left",
        damage_reduction=1.0
    ),
}

# Fallback so the starters (and most fire/water/grass/electric species) always
# have something when PokeAPI's ability list has no match in the database above.
TYPE_DEFAULT_ABILITY = {
    "fire": "blaze",
    "water": "torrent",
    "grass": "overgrow",
    "electric": "static",
}

# flat "takes X of normal damage" defenders
GENERIC_REDUCTION = {"magic_bounce": 0.9, "shell_armor": 0.9, "snow_cloak": 0.9}

# "low HP" threshold for Blaze / Torrent / Overgrow
LOW_HP_FRACTION = 1 / 3

# absorb-style abilities: (type absorbed, heals 1/4 max HP)
ABSORB_ABILITIES = {
    "volt_absorb": ("electric", True),
    "water_absorb": ("water", True),
    "aqua_absorb": ("water", True),
    "flash_fire": ("fire", False),  # absorbs the hit but doesn't heal
}


class AbilitySystem:
    """Manage Pokemon abilities"""
    
    @staticmethod
    def get_ability(ability_name: str) -> Optional[Ability]:
        """Get ability from database"""
        ability_key = ability_name.lower().replace(" ", "_").replace("_", "_")
        return ABILITY_DATABASE.get(ability_key)
    
    @staticmethod
    def apply_ability_damage_modifier(pokemon_ability: str, base_damage: int,
                                     attacker, defender, move) -> int:
        """Apply ability-based damage modification"""
        ability = AbilitySystem.get_ability(pokemon_ability)
        
        if not ability:
            return base_damage
        
        # Offensive ability: boost damage
        if isinstance(ability, OffensiveAbility):
            return int(base_damage * ability.damage_boost)
        
        # Type ability: boost if move matches
        if isinstance(ability, TypeAbility):
            if hasattr(move, 'move_type') and move.move_type.lower() == ability.boosted_type.lower():
                return int(base_damage * ability.boost)
        
        return base_damage
    
    @staticmethod
    def get_ability_info(ability_name: str) -> Dict:
        """Get formatted ability info"""
        ability = AbilitySystem.get_ability(ability_name)
        
        if not ability:
            return {
                "name": ability_name,
                "description": "Unknown ability",
                "effect": "N/A"
            }
        
        return {
            "name": ability.name,
            "description": ability.description,
            "effect": f"{ability.__class__.__name__}"
        }

    # ── battle hooks (used by battle_system.BattleSystem) ────────────────

    @staticmethod
    def normalize(name) -> Optional[str]:
        if not name:
            return None
        return str(name).strip().lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def pick_ability(api_ability_names, types) -> Optional[str]:
        """Deterministic ability for a species: first PokeAPI ability we have a
        definition for, else a type default, else None. Deterministic on purpose —
        it is derived from the species every time, so nothing extra has to be
        stored in the database."""
        for raw in api_ability_names or []:
            key = AbilitySystem.normalize(raw)
            if key in ABILITY_DATABASE:
                return key
        for t in types or []:
            key = TYPE_DEFAULT_ABILITY.get(str(t).lower())
            if key:
                return key
        return None

    @staticmethod
    def display_name(ability_name) -> Optional[str]:
        ability = AbilitySystem.get_ability(ability_name) if ability_name else None
        if ability:
            return ability.name
        return str(ability_name).replace("_", " ").title() if ability_name else None

    @staticmethod
    def modify_outgoing(ability_name, damage: int, move_type: str, hp: int, max_hp: int):
        """Attacker's ability. Returns (damage, note_or_None)."""
        key = AbilitySystem.normalize(ability_name)
        ability = ABILITY_DATABASE.get(key) if key else None
        if not ability:
            return damage, None

        if isinstance(ability, TypeAbility):
            low = max_hp > 0 and hp <= max_hp * LOW_HP_FRACTION
            if low and (move_type or "").lower() == ability.boosted_type.lower():
                return int(damage * ability.boost), f"🔥 {ability.name} boosted the attack!"
            return damage, None

        if isinstance(ability, OffensiveAbility) and ability.damage_boost != 1.0:
            return int(damage * ability.damage_boost), f"✨ {ability.name} powers the attack!"

        return damage, None

    @staticmethod
    def modify_incoming(ability_name, damage: int, move_type: str, effectiveness: float,
                        hp: int, max_hp: int):
        """Defender's ability. Returns (damage, heal, note_or_None)."""
        key = AbilitySystem.normalize(ability_name)
        ability = ABILITY_DATABASE.get(key) if key else None
        if not ability:
            return damage, 0, None
        mtype = (move_type or "").lower()

        if key in ABSORB_ABILITIES:
            absorbed, heals = ABSORB_ABILITIES[key]
            if mtype == absorbed:
                heal = max(1, max_hp // 4) if heals else 0
                return 0, heal, f"🛡️ {ability.name} absorbed the {mtype} move!"
            return damage, 0, None

        if key == "filter":
            if effectiveness > 1.0:
                return int(damage * 0.75), 0, f"🛡️ {ability.name} softened the blow!"
            return damage, 0, None

        if key == "multiscale":
            if hp >= max_hp:
                return max(1, int(damage * 0.5)), 0, f"🛡️ {ability.name} halved the damage!"
            return damage, 0, None

        if key == "sturdy":
            if hp >= max_hp and damage >= hp and hp > 1:
                return hp - 1, 0, f"🛡️ {ability.name} held on with 1 HP!"
            return damage, 0, None

        if key == "intimidate":
            return max(1, int(damage * 0.85)), 0, None

        if key in GENERIC_REDUCTION:
            return max(1, int(damage * GENERIC_REDUCTION[key])), 0, None

        return damage, 0, None


# Global ability system
ability_system = AbilitySystem()
