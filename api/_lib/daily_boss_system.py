"""
⚡ POSHOW - DAILY BOSS BATTLES
Daily challenges with powerful Pokemon
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def today_key() -> int:
    """Current UTC day as YYYYMMDD — the boss rotates and rewards reset on this."""
    return int(datetime.now(timezone.utc).strftime("%Y%m%d"))


class DailyBoss:
    """Daily boss Pokemon configuration"""
    
    def __init__(self, species: str, level: int, moves: List[str], 
                 ability: str, nature: str, iv_boost: float = 1.2):
        self.species = species
        self.level = level
        self.moves = moves
        self.ability = ability
        self.nature = nature
        self.iv_boost = iv_boost  # 1.2x stats
        self.xp_reward = 100 * level
        self.coin_reward = 50 * level
    
    def to_dict(self) -> dict:
        return {
            "species": self.species,
            "level": self.level,
            "moves": self.moves,
            "ability": self.ability,
            "nature": self.nature,
            "xp_reward": self.xp_reward,
            "coin_reward": self.coin_reward,
        }


class DailyBossSystem:
    """Manage daily boss spawning and battles"""
    
    # Boss rotation (changes daily)
    BOSS_POOL = [
        DailyBoss("gyarados", 45, ["hydro_pump", "earthquake", "ice_beam", "crunch"], 
                 "intimidate", "Adamant"),
        DailyBoss("arcanine", 42, ["fire_fang", "wild_charge", "crunch", "close_combat"],
                 "intimidate", "Adamant"),
        DailyBoss("dragonite", 48, ["dragon_dance", "earthquake", "outrage", "extreme_speed"],
                 "multiscale", "Adamant"),
        DailyBoss("alakazam", 44, ["psychic", "focus_blast", "shadow_ball", "trick_room"],
                 "magic_bounce", "Timid"),
        DailyBoss("machamp", 43, ["dynamic_punch", "stone_edge", "earthquake", "close_combat"],
                 "guts", "Adamant"),
        DailyBoss("golem", 42, ["earthquake", "stone_edge", "explosion", "heavy_slam"],
                 "sturdy", "Adamant"),
        DailyBoss("lapras", 44, ["hydro_pump", "thunderbolt", "ice_beam", "psychic"],
                 "shell_armor", "Modest"),
        DailyBoss("articuno", 46, ["blizzard", "hurricane", "earth_power", "roost"],
                 "snow_cloak", "Timid"),
    ]
    
    def __init__(self):
        self.today_boss = None
        self.last_reset = datetime.now()
        self._select_daily_boss()
    
    def _select_daily_boss(self):
        """Select boss for the day (resets daily)"""
        # Check if day changed
        if (datetime.now() - self.last_reset).days > 0:
            self.last_reset = datetime.now()
        
        # Use date as seed for deterministic selection
        day_seed = today_key()
        # private RNG: never reseed the global `random` module (shared with battles/catching)
        self.today_boss = random.Random(day_seed).choice(self.BOSS_POOL)
    
    def get_daily_boss(self) -> DailyBoss:
        """Get today's boss"""
        self._select_daily_boss()
        return self.today_boss
    
    def get_boss_info(self) -> dict:
        """Get formatted boss info"""
        boss = self.get_daily_boss()
        return {
            "name": boss.species.upper(),
            "level": boss.level,
            "moves": ", ".join([m.replace("_", " ").title() for m in boss.moves]),
            "ability": boss.ability.replace("_", " ").title(),
            "xp_reward": boss.xp_reward,
            "coin_reward": boss.coin_reward,
            "info": f"""⚔️ **DAILY BOSS**

**{boss.species.upper()}** Lv{boss.level}

💪 Ability: {boss.ability}
⭐ Nature: {boss.nature}

📚 Moves: {", ".join([m.replace("_", " ").title() for m in boss.moves])}

🎁 Rewards:
  💰 {boss.coin_reward} Pokéyen
  ✨ {boss.xp_reward} XP"""
        }


# Global boss system
daily_boss_system = DailyBossSystem()


class BossRewards:
    """Handle boss victory rewards"""
    
    @staticmethod
    def calculate_rewards(player_level: int, boss: DailyBoss, 
                         victory: bool, damage_ratio: float = 1.0) -> dict:
        """
        Calculate rewards based on battle performance
        
        Args:
            player_level: Player's level
            boss: Daily boss
            victory: Whether player won
            damage_ratio: Damage taken / max HP (0-1)
        
        Returns: Reward dict
        """
        
        if not victory:
            return {
                "victory": False,
                "xp": 0,
                "coins": 0,
                "items": [],
                "message": "❌ You were defeated by the Daily Boss!"
            }
        
        # Base rewards
        base_xp = boss.xp_reward
        base_coins = boss.coin_reward
        
        # Bonus for low damage taken (under 50% HP used)
        flawless_bonus = 1.5 if damage_ratio < 0.5 else 1.0
        
        xp = int(base_xp * flawless_bonus)
        coins = int(base_coins * flawless_bonus)
        
        # Bonus items
        items = []
        if damage_ratio < 0.3:
            items.append(("rare_candy", 1))
        if random.random() < 0.3:
            items.append(("exp_all", 1))
        
        message = f"""✅ **YOU WON!**

Defeated **{boss.species.upper()}** Lv{boss.level}!

💰 +{coins} Pokéyen
✨ +{xp} XP"""
        
        if items:
            message += "\n\n🎁 Items earned:"
            for item, qty in items:
                message += f"\n  • {item.replace('_', ' ').title()} x{qty}"
        
        return {
            "victory": True,
            "xp": xp,
            "coins": coins,
            "items": items,
            "damage_ratio": damage_ratio,
            "flawless": damage_ratio < 0.3,
            "message": message
        }
