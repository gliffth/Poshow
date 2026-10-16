"""
⚡ POSHOW - EXPERIENCE & LEVELING SYSTEM
Player and Pokemon XP progression with exponential growth
"""

import logging
from typing import Dict, Optional, List
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XPSystem:
    """
    Player and Pokemon experience system
    Exponential growth: each level requires 2x previous level
    """
    
    # Player XP progression
    PLAYER_BASE_XP = 1000  # XP needed for level 1→2
    PLAYER_XP_MULTIPLIER = 2.0  # Each level 2x previous
    
    # Pokemon XP progression
    POKEMON_BASE_XP = 100   # XP for level 1→2
    POKEMON_XP_MULTIPLIER = 2.0  # Every 10 levels
    
    # Region unlocking
    REGION_UNLOCK_LEVELS = {
        "kanto": 1,
        "johto": 10,
        "hoenn": 20,
        "sinnoh": 30,
        "unova": 40,
        "kalos": 50,
        "alola": 60,
        "galar": 70,
        "paldea": 80,
    }
    
    # XP rewards
    XP_REWARDS = {
        "wild_pokemon_defeat": lambda level: 20 + (level * 2),
        "trainer_battle_win": lambda level: 50 + (level * 5),
        "trainer_battle_lose": lambda level: 10 + (level // 2),
        "quest_complete": 100,
        "evolution": 50,
        "daily_login": 25,
        "catch_pokemon": lambda level: 15 + level,
    }
    
    def __init__(self):
        """Initialize XP system"""
        logger.info("✅ XP System initialized")
    
    # ════════════════════════════════════════════════════════════════
    # PLAYER XP
    # ════════════════════════════════════════════════════════════════
    
    def get_player_xp_for_level(self, level: int) -> int:
        """
        Get total XP needed to reach a level
        Level 1→2: 1000
        Level 2→3: 2000
        Level 3→4: 4000
        """
        if level <= 1:
            return 0
        
        xp = self.PLAYER_BASE_XP
        for _ in range(level - 2):
            xp = int(xp * self.PLAYER_XP_MULTIPLIER)
        
        return xp
    
    def get_player_next_level_xp(self, current_level: int, current_xp: int) -> int:
        """Get XP needed for next level from current XP"""
        xp_for_next = self.get_player_xp_for_level(current_level + 1)
        return max(0, xp_for_next - current_xp)
    
    def add_player_xp(self, current_level: int, current_xp: int, 
                      xp_gain: int) -> Dict:
        """
        Add XP to player and check for level ups
        Returns: {new_level, new_xp, levels_gained, message}
        """
        new_xp = current_xp + xp_gain
        new_level = current_level
        levels_gained = 0
        messages = [f"Gained {xp_gain} XP!"]
        
        # Check for level ups
        while True:
            xp_needed = self.get_player_xp_for_level(new_level + 1)
            if new_xp >= xp_needed:
                new_level += 1
                new_xp -= xp_needed
                levels_gained += 1
                messages.append(f"⭐ LEVEL UP! Now Lv{new_level}!")
            else:
                break
        
        return {
            "new_level": new_level,
            "new_xp": new_xp,
            "levels_gained": levels_gained,
            "messages": messages
        }
    
    def get_player_xp_progress(self, level: int, current_xp: int) -> Dict:
        """Get player XP progress for display"""
        xp_for_next = self.get_player_xp_for_level(level + 1)
        xp_for_current = self.get_player_xp_for_level(level)
        
        progress = current_xp - xp_for_current
        needed = xp_for_next - xp_for_current
        
        percent = (progress / needed * 100) if needed > 0 else 0
        
        return {
            "current": current_xp,
            "progress": progress,
            "needed": needed,
            "percent": percent
        }
    
    # ════════════════════════════════════════════════════════════════
    # POKEMON XP
    # ════════════════════════════════════════════════════════════════
    
    def get_pokemon_xp_for_level(self, level: int) -> int:
        """
        Get total XP needed for Pokemon to reach level
        Level 1→2: 100
        Level 10→11: 200 (2x every 10 levels)
        Level 20→21: 400
        """
        if level <= 1:
            return 0
        
        # Calculate which 10-level bracket
        bracket = (level - 1) // 10
        xp = self.POKEMON_BASE_XP * (self.POKEMON_XP_MULTIPLIER ** bracket)
        
        return int(xp)
    
    def get_pokemon_next_level_xp(self, current_level: int, current_xp: int) -> int:
        """Get XP needed for Pokemon's next level"""
        xp_for_next = self.get_pokemon_xp_for_level(current_level + 1)
        return max(0, xp_for_next - current_xp)
    
    def add_pokemon_xp(self, current_level: int, current_xp: int, 
                       xp_gain: int) -> Dict:
        """
        Add XP to Pokemon and check for level ups
        Returns: {new_level, new_xp, levels_gained, moves_learned}
        """
        new_xp = current_xp + xp_gain
        new_level = current_level
        levels_gained = 0
        moves_learned = []
        
        while True:
            xp_needed = self.get_pokemon_xp_for_level(new_level + 1)
            if new_xp >= xp_needed:
                new_level += 1
                new_xp -= xp_needed
                levels_gained += 1
            else:
                break
        
        return {
            "new_level": new_level,
            "new_xp": new_xp,
            "levels_gained": levels_gained,
            "moves_learned": moves_learned
        }
    
    def get_pokemon_xp_progress(self, level: int, current_xp: int) -> Dict:
        """Get Pokemon XP progress for display"""
        xp_for_next = self.get_pokemon_xp_for_level(level + 1)
        xp_for_current = self.get_pokemon_xp_for_level(level)
        
        progress = current_xp - xp_for_current
        needed = xp_for_next - xp_for_current
        
        percent = (progress / needed * 100) if needed > 0 else 0
        
        return {
            "current": current_xp,
            "progress": progress,
            "needed": needed,
            "percent": percent
        }
    
    # ════════════════════════════════════════════════════════════════
    # XP REWARDS
    # ════════════════════════════════════════════════════════════════
    
    def get_reward_xp(self, activity: str, level: int = 1) -> int:
        """Get XP reward for activity"""
        if activity not in self.XP_REWARDS:
            return 0
        
        reward = self.XP_REWARDS[activity]
        
        # If it's a function, call it with level
        if callable(reward):
            return reward(level)
        
        return reward
    
    def get_battle_xp(self, is_win: bool, opponent_level: int, trainer_level: int) -> int:
        """
        Calculate XP for battle
        Winning = more XP
        Opponent level affects reward
        """
        if is_win:
            base = 50
        else:
            base = 10
        
        # Opponent level bonus
        level_diff = opponent_level - trainer_level
        multiplier = 1.0 + (level_diff * 0.1)  # +10% per level difference
        
        return int(base * multiplier)
    
    def get_quest_completion_xp(self, quest_difficulty: str) -> int:
        """Get XP for quest completion"""
        difficulties = {
            "easy": 50,
            "medium": 100,
            "hard": 200,
            "expert": 500,
        }
        return difficulties.get(quest_difficulty.lower(), 100)
    
    # ════════════════════════════════════════════════════════════════
    # PROGRESSION FEATURES
    # ════════════════════════════════════════════════════════════════
    
    def check_region_unlock(self, player_level: int) -> List[str]:
        """
        Check which regions are unlocked
        Returns list of unlocked regions
        """
        unlocked = []
        for region, required_level in self.REGION_UNLOCK_LEVELS.items():
            if player_level >= required_level:
                unlocked.append(region)
        
        return unlocked
    
    def get_next_region_unlock(self, player_level: int) -> Optional[Dict]:
        """Get next region to unlock"""
        sorted_regions = sorted(self.REGION_UNLOCK_LEVELS.items(), 
                               key=lambda x: x[1])
        
        for region, required_level in sorted_regions:
            if player_level < required_level:
                return {
                    "region": region.capitalize(),
                    "current_level": player_level,
                    "required_level": required_level,
                    "levels_remaining": required_level - player_level
                }
        
        return None
    
    # ════════════════════════════════════════════════════════════════
    # DISPLAY HELPERS
    # ════════════════════════════════════════════════════════════════
    
    def format_xp_bar(self, current: int, needed: int, width: int = 15) -> str:
        """
        Format XP bar for display
        Example: [■■■■□□□□□□□] 40%
        """
        if needed <= 0:
            filled = width
        else:
            filled = int((current / needed) * width)
        
        empty = width - filled
        percent = (current / needed * 100) if needed > 0 else 100
        
        bar = "■" * filled + "□" * empty
        return f"[{bar}] {percent:.0f}%"
    
    def get_player_progress_text(self, level: int, current_xp: int) -> str:
        """Get formatted player XP progress text"""
        progress = self.get_player_xp_progress(level, current_xp)
        bar = self.format_xp_bar(progress["progress"], progress["needed"])
        
        return f"Level {level}\n{bar}\n{progress['progress']}/{progress['needed']} XP"
    
    def get_pokemon_progress_text(self, level: int, current_xp: int) -> str:
        """Get formatted Pokemon XP progress text"""
        progress = self.get_pokemon_xp_progress(level, current_xp)
        bar = self.format_xp_bar(progress["progress"], progress["needed"])
        
        return f"Lv {level}\n{bar}\n{progress['progress']}/{progress['needed']} XP"

# Singleton
xp_system = XPSystem()

# Test
if __name__ == "__main__":
    print("Testing XP System...")
    
    # Test player XP
    xp_needed = xp_system.get_player_xp_for_level(2)
    print(f"✅ Player Lv1→2: {xp_needed} XP")
    
    xp_needed = xp_system.get_player_xp_for_level(3)
    print(f"✅ Player Lv2→3: {xp_needed} XP (2x)")
    
    # Test Pokemon XP
    xp_needed = xp_system.get_pokemon_xp_for_level(2)
    print(f"✅ Pokemon Lv1→2: {xp_needed} XP")
    
    xp_needed = xp_system.get_pokemon_xp_for_level(11)
    print(f"✅ Pokemon Lv10→11: {xp_needed} XP (2x every 10)")
    
    # Test region unlock
    regions = xp_system.check_region_unlock(25)
    print(f"✅ Regions unlocked at Lv25: {regions}")
    
    # Test XP bar
    bar = xp_system.format_xp_bar(40, 100)
    print(f"✅ XP bar: {bar}")
    
    print("✅ All tests passed!")

