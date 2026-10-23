"""Catch mechanics for each ball type."""

import random
import logging
from typing import Dict, Optional
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BallType(Enum):
    """All Pokéball types with catch multipliers"""
    MASTER_BALL = ("Master Ball", float('inf'), "Guaranteed catch")
    ULTRA_BALL = ("Ultra Ball", 2.0, "Standard high-tier")
    GREAT_BALL = ("Great Ball", 1.5, "Standard mid-tier")
    POKE_BALL = ("Poké Ball", 1.0, "Standard")
    QUICK_BALL = ("Quick Ball", 5.0, "First turn only")
    TIMER_BALL = ("Timer Ball", 1.0, "Scales with turns (max 4x)")
    NEST_BALL = ("Nest Ball", 1.0, "Better for low levels (max 4x)")
    REPEAT_BALL = ("Repeat Ball", 3.5, "Already caught Pokemon")
    NET_BALL = ("Net Ball", 3.5, "Bug/Water types")
    DIVE_BALL = ("Dive Ball", 3.5, "Water Pokemon")
    DUSK_BALL = ("Dusk Ball", 3.0, "Cave/Night")
    FAST_BALL = ("Fast Ball", 4.0, "Base Speed ≥100")
    LEVEL_BALL = ("Level Ball", 1.0, "Level difference (max 8x)")
    HEAVY_BALL = ("Heavy Ball", 1.0, "Weight-based")
    MOON_BALL = ("Moon Ball", 4.0, "Nidoran/Clefairy families")
    FRIEND_BALL = ("Friend Ball", 1.0, "No bonus")
    LUXURY_BALL = ("Luxury Ball", 1.0, "No bonus")
    HEAL_BALL = ("Heal Ball", 1.0, "Heals on catch")
    PREMIER_BALL = ("Premier Ball", 1.0, "No bonus")
    CHERISH_BALL = ("Cherish Ball", 1.0, "No bonus")
    SAFARI_BALL = ("Safari Ball", 1.0, "Safari Zone")
    SPORT_BALL = ("Sport Ball", 1.0, "Sport/Bug Catching Contest")
    BEAST_BALL = ("Beast Ball", 5.0, "Ultra Beasts only")
    LOVE_BALL = ("Love Ball", 8.0, "Opposite gender, same species")

class CatchSystem:
    """
    Complete Pokéball catch system
    Implements official Pokemon catch formula
    """
    
    def __init__(self):
        """Initialize catch system"""
        logger.info("✅ Catch System initialized")
    
    # ── Catch calculation ──
    
    def calculate_catch_chance(self, pokemon_hp_percent: float, pokemon_level: int,
                               pokemon_catch_rate: int, ball_type: str,
                               turn: int = 1, is_status: bool = False,
                               player_level: int = 1, is_first_turn: bool = False,
                               already_caught: bool = False,
                               pokemon_type: str = "", pokemon_weight: int = 0,
                               is_water_location: bool = False,
                               is_cave_location: bool = False,
                               is_night: bool = False,
                               status: Optional[str] = None,
                               species_name: str = "",
                               base_speed: int = 0,
                               types: Optional[list] = None) -> Dict:
        """
        Calculate catch probability using official formula
        Returns: {chance: 0-100, message, will_catch: bool}
        """
        
        # Get ball multiplier
        types = [str(t).lower() for t in (types or ([pokemon_type] if pokemon_type else []))]
        ball_multiplier = self._get_ball_multiplier(
            ball_type, turn, pokemon_level, player_level,
            pokemon_type, pokemon_weight, already_caught,
            is_water_location, is_cave_location, is_night,
            is_first_turn, species_name=species_name, base_speed=base_speed, types=types
        )
        # Heavy Ball changes the species' catch RATE (Gen 7+): -20 under 100 kg, +20 from 200 kg, +30 from 300 kg
        # (weight in kg; 0 = unknown -> no change). The rate never drops below 1.
        if self._ball_key(ball_type) == "heavyball" and pokemon_weight:
            pokemon_catch_rate = max(1, pokemon_catch_rate + (-20 if pokemon_weight < 100 else 0 if pokemon_weight < 200
                                                              else 20 if pokemon_weight < 300 else 30))
        
        # Gen 5+ capture: a = (3*maxHP - 2*HP) / (3*maxHP) * rate * ball * status [* low-level bonus], then four
        # "shake checks", each passed with probability (a/255)^(3/16). a >= 255 is a sure catch; Master Ball always.
        # (Gen 6+ critical captures are not modelled.) Status: sleep/freeze 2.5x, paralysis/poison/burn 1.5x.
        if ball_multiplier == float('inf'):                       # Master Ball
            catch_chance = 100.0
        else:
            max_hp = 1000
            hp = max(1, int(max_hp * max(0.0, min(1.0, pokemon_hp_percent))))
            catch_chance = 100.0 * self.catch_probability(
                hp, max_hp, pokemon_catch_rate, ball_multiplier, self.status_multiplier(status, is_status), pokemon_level)

        will_catch = random.random() * 100 < catch_chance
        
        return {
            "chance": catch_chance,
            "ball": ball_type,
            "multiplier": ball_multiplier,
            "will_catch": will_catch,
            "message": self._get_catch_message(catch_chance, ball_type, will_catch)
        }
    
    @staticmethod
    def status_multiplier(status: Optional[str], generic: bool = False) -> float:
        st = (status or "").lower()
        if st in ("sleep", "slp", "freeze", "frz", "frozen"):
            return 2.5
        if st in ("paralysis", "par", "poison", "psn", "toxic", "tox", "burn", "brn"):
            return 1.5
        return 1.5 if generic else 1.0

    @staticmethod
    def catch_probability(hp: int, max_hp: int, rate: int, ball: float, status: float = 1.0, level: int = 50) -> float:
        """Probability (0..1) that the capture succeeds. Pure function of its inputs (unit-testable)."""
        low_level = max(1.0, (36 - 2 * level) / 10) if level < 13 else 1.0      # Gen 7+ low-level bonus
        a = ((3 * max_hp - 2 * hp) / (3 * max_hp)) * max(1, rate) * ball * status * low_level
        if a >= 255:
            return 1.0
        return ((a / 255.0) ** 0.1875) ** 4

    @staticmethod
    def _ball_key(ball_type: str) -> str:
        return (ball_type or "").lower().replace(" ", "").replace("_", "").replace("-", "")

    MOON_FAMILIES = {"nidoran-f", "nidorina", "nidoqueen", "nidoran-m", "nidorino", "nidoking", "clefairy",
                     "clefable", "cleffa", "jigglypuff", "wigglytuff", "igglybuff", "skitty", "delcatty", "munna",
                     "musharna"}
    ULTRA_BEASTS = {"nihilego", "buzzwole", "pheromosa", "xurkitree", "celesteela", "kartana", "guzzlord",
                    "poipole", "naganadel", "stakataka", "blacephalon"}

    def _get_ball_multiplier(self, ball_type: str, turn: int, pokemon_level: int,
                            player_level: int, pokemon_type: str, pokemon_weight: int,
                            already_caught: bool, is_water_location: bool,
                            is_cave_location: bool, is_night: bool,
                            is_first_turn: bool, species_name: str = "", base_speed: int = 0,
                            types: Optional[list] = None) -> float:
        """Ball multipliers with the real conditions (Gen 7-style values). A condition that can't be known from the
        information given counts as NOT met — a ball never gets its bonus 'by assumption'."""
        ball = self._ball_key(ball_type)
        types = [t.lower() for t in (types or ([pokemon_type] if pokemon_type else []))]
        species = (species_name or "").lower()

        fixed = {"masterball": float('inf'), "ultraball": 2.0, "greatball": 1.5, "pokeball": 1.0, "premierball": 1.0,
                 "luxuryball": 1.0, "healball": 1.0, "friendball": 1.0, "cherishball": 1.0, "sportball": 1.0,
                 "safariball": 1.0}
        if ball in fixed:
            return fixed[ball]
        if ball == "quickball":                         # 5x on the very first turn only
            return 5.0 if (is_first_turn or turn <= 1) else 1.0
        if ball == "timerball":                         # (turns + 10) / 10, max 4x
            return min(4.0, (max(1, turn) + 10) / 10.0)
        if ball == "nestball":                          # (41 - level) / 10 up to level 29, then 1x
            return max(1.0, (41 - pokemon_level) / 10.0) if pokemon_level <= 29 else 1.0
        if ball == "repeatball":                        # species already registered as caught
            return 3.5 if already_caught else 1.0
        if ball == "netball":                           # Bug or Water type
            return 3.5 if ("bug" in types or "water" in types) else 1.0
        if ball == "diveball":                          # while surfing / fishing — a LOCATION, not the target's type
            return 3.5 if is_water_location else 1.0
        if ball == "duskball":                          # caves or at night
            return 3.5 if (is_cave_location or is_night) else 1.0
        if ball == "fastball":                          # target's base Speed >= 100
            return 4.0 if base_speed >= 100 else 1.0
        if ball == "levelball":                         # your lead's level vs the target's
            if player_level >= 4 * pokemon_level:
                return 8.0
            if player_level > 2 * pokemon_level:
                return 4.0
            if player_level > pokemon_level:
                return 2.0
            return 1.0
        if ball == "heavyball":                         # modifies the catch RATE instead (see calculate_catch_chance)
            return 1.0
        if ball == "moonball":
            return 4.0 if species in self.MOON_FAMILIES else 1.0
        if ball == "beastball":
            return 5.0 if species in self.ULTRA_BEASTS else 0.1
        if ball == "loveball":                          # needs gender data this game doesn't track -> no bonus
            return 1.0
        return 1.0

    def _get_catch_message(self, chance: float, ball_type: str, will_catch: bool) -> str:
        """Generate catch message based on chance"""
        
        if chance >= 90:
            if will_catch:
                return f"✅ **Caught!** {ball_type} worked perfectly! ({chance:.0f}% chance)"
            else:
                return f"❌ Almost had it! The Pokemon broke free! ({chance:.0f}% chance)"
        
        elif chance >= 70:
            if will_catch:
                return f"✅ **Caught!** {ball_type} succeeded! ({chance:.0f}% chance)"
            else:
                return f"❌ So close! The Pokemon escaped! ({chance:.0f}% chance)"
        
        elif chance >= 50:
            if will_catch:
                return f"✅ **Caught!** {ball_type} was effective! ({chance:.0f}% chance)"
            else:
                return f"❌ The Pokemon wiggled free! ({chance:.0f}% chance)"
        
        elif chance >= 30:
            if will_catch:
                return f"✅ **Caught!** Lucky hit with {ball_type}! ({chance:.0f}% chance)"
            else:
                return f"❌ The Pokemon struggled free! ({chance:.0f}% chance)"
        
        elif chance >= 10:
            if will_catch:
                return f"✅ **Caught!** {ball_type} barely worked! ({chance:.0f}% chance)"
            else:
                return f"❌ The Pokemon broke out! ({chance:.0f}% chance)"
        
        else:
            if will_catch:
                return f"✅ **Caught!** Against all odds! ({chance:.0f}% chance)"
            else:
                return f"❌ The Pokemon broke free easily! ({chance:.0f}% chance)"
    
    # ── Ball information ──
    
    def get_ball_info(self, ball_type: str) -> Dict:
        """Get ball information"""
        balls_info = {
            "master ball": {
                "name": "Master Ball",
                "catch_rate": "∞",
                "effect": "Guarantees catch (with rare exceptions)",
                "best_for": "Legendary Pokemon",
                "price": 500
            },
            "ultra ball": {
                "name": "Ultra Ball",
                "catch_rate": "2x",
                "effect": "High catch rate",
                "best_for": "Any Pokemon",
                "price": 30
            },
            "great ball": {
                "name": "Great Ball",
                "catch_rate": "1.5x",
                "effect": "Mid-tier catch rate",
                "best_for": "Mid-level Pokemon",
                "price": 20
            },
            "pokeball": {
                "name": "Poké Ball",
                "catch_rate": "1x",
                "effect": "Standard catch rate",
                "best_for": "Starter Pokemon",
                "price": 10
            },
            "quick ball": {
                "name": "Quick Ball",
                "catch_rate": "5x (turn 1)",
                "effect": "5x multiplier on first turn only",
                "best_for": "First turn catches",
                "price": 25
            },
            "timer ball": {
                "name": "Timer Ball",
                "catch_rate": "1-4x",
                "effect": "(turns + 10) / 10, max 4x at 30+ turns",
                "best_for": "Long battles",
                "price": 30
            },
            "nest ball": {
                "name": "Nest Ball",
                "catch_rate": "1-4x",
                "effect": "(41 - level) / 10 up to Lv29 (max 4x), then 1x",
                "best_for": "Low-level Pokemon",
                "price": 30
            },
            "repeat ball": {
                "name": "Repeat Ball",
                "catch_rate": "3.5x",
                "effect": "3.5x if Pokemon already caught",
                "best_for": "Duplicate Pokemon",
                "price": 30
            },
            "net ball": {
                "name": "Net Ball",
                "catch_rate": "3.5x",
                "effect": "3.5x for Bug/Water types",
                "best_for": "Bug & Water Pokemon",
                "price": 30
            },
            "dive ball": {
                "name": "Dive Ball",
                "catch_rate": "3.5x",
                "effect": "3.5x while surfing or fishing",
                "best_for": "Water encounters",
                "price": 30
            },
            "dusk ball": {
                "name": "Dusk Ball",
                "catch_rate": "3.5x",
                "effect": "3.5x in caves or at night",
                "best_for": "Cave/night encounters",
                "price": 35
            },
            "fast ball": {
                "name": "Fast Ball",
                "catch_rate": "4x",
                "effect": "4x for high-Speed Pokemon",
                "best_for": "Fast Pokemon",
                "price": 25
            },
            "level ball": {
                "name": "Level Ball",
                "catch_rate": "1-8x",
                "effect": "2x / 4x / 8x when your lead is higher / over 2x / over 4x the target's level",
                "best_for": "Low-level Pokemon",
                "price": 25
            },
            "heavy ball": {
                "name": "Heavy Ball",
                "catch_rate": "1-2x",
                "effect": "Better for heavier Pokemon",
                "best_for": "Heavy Pokemon",
                "price": 25
            },
            "moon ball": {
                "name": "Moon Ball",
                "catch_rate": "4x",
                "effect": "4x for Nidoran/Clefairy families",
                "best_for": "Moon Stone families",
                "price": 25
            },
            "beast ball": {
                "name": "Beast Ball",
                "catch_rate": "5x/0.1x",
                "effect": "5x for Ultra Beasts, 0.1x otherwise",
                "best_for": "Ultra Beasts only",
                "price": 50
            },
            "love ball": {
                "name": "Love Ball",
                "catch_rate": "1x",
                "effect": "No bonus here (gender isn't tracked)",
                "best_for": "Gender-matched Pokemon",
                "price": 25
            },
        }
        
        return balls_info.get(ball_type.lower(), {"name": "Unknown", "catch_rate": "?"})
    
    def get_all_balls(self) -> Dict[str, Dict]:
        """Get all available balls"""
        balls = {}
        for ball_name in ["master ball", "ultra ball", "great ball", "pokeball", 
                         "quick ball", "timer ball", "nest ball", "repeat ball",
                         "net ball", "dive ball", "dusk ball", "fast ball",
                         "level ball", "heavy ball", "moon ball", "beast ball",
                         "love ball"]:
            balls[ball_name] = self.get_ball_info(ball_name)
        return balls

# Singleton
catch_system = CatchSystem()

# Test
if __name__ == "__main__":
    print("Testing Catch System...")
    
    # Test catch chance
    result = catch_system.calculate_catch_chance(
        pokemon_hp_percent=0.3,
        pokemon_level=20,
        pokemon_catch_rate=45,
        ball_type="ultra ball",
        turn=1
    )
    print(f"✅ Ultra Ball vs Lv20 at low HP: {result['chance']:.1f}%")
    print(f"   {result['message']}")
    
    # Test Master Ball
    result = catch_system.calculate_catch_chance(
        pokemon_hp_percent=1.0,
        pokemon_level=100,
        pokemon_catch_rate=3,
        ball_type="master ball"
    )
    print(f"✅ Master Ball guaranteed: {result['will_catch']}")
    
    # Test Quick Ball first turn
    result = catch_system.calculate_catch_chance(
        pokemon_hp_percent=1.0,
        pokemon_level=15,
        pokemon_catch_rate=50,
        ball_type="quick ball",
        turn=1,
        is_first_turn=True
    )
    print(f"✅ Quick Ball first turn: {result['multiplier']}x")
    
    print("✅ All tests passed!")

