"""
⚡ POSHOW - PLAYER MODEL (FIXED)
Player instance with stats, teams, achievements, and progression
"""

import random
from typing import Dict, List, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlayerInstance:
    """Individual player with stats, teams, progress, and achievements"""
    
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.created_date = datetime.now().isoformat()
        
        # Player Stats
        self.level = 1
        self.experience = 0
        self.coins = 100  # Start with 100 coins
        
        # Teams
        self.active_team = []  # List of 6 Pokemon (or less)
        self.pokemon_collection = []  # All caught Pokemon
        
        # Battle Stats
        self.wins = 0
        self.losses = 0
        self.elo = 1000
        self.current_streak = 0
        
        # Region Progress
        self.current_region = "kanto"
        self.regions_unlocked = ["kanto"]
        self.pokemon_caught = 0
        self.pokedex_seen = set()
        
        # Items & Inventory
        self.inventory = {}
        self.pokeballs = {"pokeball": 5, "greatball": 0, "ultraball": 0}
        
        # Daily Tracking
        self.last_login = datetime.now().isoformat()
        self.login_streak = 1
        self.daily_reward_claimed = False
        
        # Achievements
        self.badges = []
        self.achievements = []
        
        # Referral System
        self.referral_code = f"P{user_id}{random.randint(1000, 9999)}"
        self.referrals = []
        self.successful_referrals = 0
        
        # Settings
        self.language = "en"
        self.notifications_enabled = True
    
    # ════════════════════════════════════════════════════════════════
    # TEAM MANAGEMENT
    # ════════════════════════════════════════════════════════════════
    
    def add_pokemon_to_team(self, pokemon) -> bool:
        """Add Pokemon to active team (max 6)"""
        if len(self.active_team) < 6:
            self.active_team.append(pokemon)
            return True
        return False
    
    def remove_from_team(self, pokemon_id: str) -> bool:
        """Remove Pokemon from active team"""
        self.active_team = [p for p in self.active_team if p.id != pokemon_id]
        return True
    
    # ════════════════════════════════════════════════════════════════
    # PROFILE & DISPLAY
    # ════════════════════════════════════════════════════════════════
    
    def get_profile(self) -> str:
        """Get formatted profile display"""
        return f"""👤 PROFILE - {self.username}

📊 STATS
Level: {self.level}
XP: {self.experience}
💰 {self.coins}₽

⚔️ PVP RECORD
Wins: {self.wins}
Losses: {self.losses}
ELO: {self.elo}
Rank: {self.get_rank()}

🎮 COLLECTION
Caught: {self.pokemon_caught}/151
Pokedex: {len(self.pokedex_seen)}/151
"""
    
    def get_team_summary(self) -> str:
        """Get formatted team display"""
        if not self.active_team:
            return "🎮 TEAM\n\nNo Pokemon in team!"
        
        summary = "🎮 TEAM\n\n"
        for i, poke in enumerate(self.active_team, 1):
            emoji = "✨" if hasattr(poke, 'is_shiny') and poke.is_shiny else "⭐"
            summary += f"{i}. {poke.nickname} Lv{poke.level} {emoji}\n"
            summary += f"   HP: {poke.current_hp}/{poke.max_hp}\n"
        
        return summary
    
    def get_rank(self) -> str:
        """Get rank based on ELO"""
        if self.elo >= 2400:
            return "👑 Champion"
        elif self.elo >= 2000:
            return "🏆 Master"
        elif self.elo >= 1600:
            return "💎 Expert"
        elif self.elo >= 1400:
            return "🥇 Advanced"
        elif self.elo >= 1200:
            return "🥈 Intermediate"
        elif self.elo >= 1000:
            return "🥉 Standard"
        else:
            return "🎯 Beginner"
    
    # ════════════════════════════════════════════════════════════════
    # BATTLE STATS
    # ════════════════════════════════════════════════════════════════
    
    def record_battle_win(self, opponent_elo: int = 1000) -> int:
        """Record win and update ELO"""
        self.wins += 1
        self.current_streak += 1
        
        # ELO calculation
        expected = 1 / (1 + 10 ** ((opponent_elo - self.elo) / 400))
        elo_gain = int(32 * (1 - expected))
        self.elo += elo_gain
        
        return elo_gain
    
    def record_battle_loss(self, opponent_elo: int = 1000) -> int:
        """Record loss and update ELO"""
        self.losses += 1
        self.current_streak = 0
        
        # ELO calculation
        expected = 1 / (1 + 10 ** ((opponent_elo - self.elo) / 400))
        elo_loss = int(32 * expected)
        self.elo = max(0, self.elo - elo_loss)
        
        return -elo_loss
    
    def get_win_rate(self) -> float:
        """Get win rate percentage"""
        total = self.wins + self.losses
        if total == 0:
            return 0.0
        return (self.wins / total) * 100
    
    # ════════════════════════════════════════════════════════════════
    # CURRENCY
    # ════════════════════════════════════════════════════════════════
    
    def add_coins(self, amount: int) -> int:
        """Add coins, return new total"""
        self.coins += amount
        return self.coins
    
    def spend_coins(self, amount: int) -> bool:
        """Spend coins if sufficient"""
        if self.coins >= amount:
            self.coins -= amount
            return True
        return False
    
    # ════════════════════════════════════════════════════════════════
    # INVENTORY MANAGEMENT
    # ════════════════════════════════════════════════════════════════
    
    def add_pokeball(self, ball_type: str, quantity: int = 1) -> None:
        """Add Pokéballs"""
        if ball_type not in self.pokeballs:
            self.pokeballs[ball_type] = 0
        self.pokeballs[ball_type] += quantity
    
    def use_pokeball(self, ball_type: str) -> bool:
        """Use a Pokéball"""
        if self.pokeballs.get(ball_type, 0) > 0:
            self.pokeballs[ball_type] -= 1
            return True
        return False
    
    def add_item(self, item_name: str, quantity: int = 1) -> bool:
        """Add item to inventory"""
        if item_name not in self.inventory:
            self.inventory[item_name] = 0
        self.inventory[item_name] += quantity
        return True
    
    def remove_item(self, item_name: str, quantity: int = 1) -> bool:
        """Remove item from inventory"""
        if item_name not in self.inventory or self.inventory[item_name] < quantity:
            return False
        self.inventory[item_name] -= quantity
        if self.inventory[item_name] == 0:
            del self.inventory[item_name]
        return True
    
    def get_inventory_display(self) -> str:
        """Get inventory display text"""
        display = "📦 INVENTORY\n"
        
        if not self.pokeballs and not self.inventory:
            return display + "\nEmpty"
        
        if self.pokeballs:
            display += "\n🔴 POKÉBALLS\n"
            for ball, count in self.pokeballs.items():
                if count > 0:
                    display += f"  {ball.capitalize()}: {count}x\n"
        
        if self.inventory:
            display += "\n💊 ITEMS\n"
            for item, count in list(self.inventory.items())[:10]:
                display += f"  {item.capitalize()}: {count}x\n"
        
        return display
    
    # ════════════════════════════════════════════════════════════════
    # PROGRESSION
    # ════════════════════════════════════════════════════════════════
    
    def add_experience(self, amount: int) -> bool:
        """Add player XP"""
        self.experience += amount
        
        # Simple leveling: 100 XP per level
        if self.experience >= 100 * self.level:
            self.level += 1
            self.experience = 0
            return True
        
        return False
    
    def catch_pokemon(self, pokemon) -> None:
        """Record caught Pokemon"""
        self.pokemon_caught += 1
        self.pokemon_collection.append(pokemon)
        if hasattr(pokemon, 'api_data') and pokemon.api_data:
            self.pokedex_seen.add(pokemon.api_data.get("id", 0))
    
    def unlock_region(self, region: str) -> bool:
        """Unlock new region"""
        if region not in self.regions_unlocked:
            self.regions_unlocked.append(region)
            return True
        return False
    
    def set_current_region(self, region: str) -> bool:
        """Travel to region"""
        if region in self.regions_unlocked:
            self.current_region = region
            return True
        return False
    
    # ════════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ════════════════════════════════════════════════════════════════
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "created_date": self.created_date,
            "level": self.level,
            "experience": self.experience,
            "coins": self.coins,
            "wins": self.wins,
            "losses": self.losses,
            "elo": self.elo,
            "current_streak": self.current_streak,
            "current_region": self.current_region,
            "regions_unlocked": self.regions_unlocked,
            "pokemon_caught": self.pokemon_caught,
            "pokedex_seen": list(self.pokedex_seen),
            "inventory": self.inventory,
            "pokeballs": self.pokeballs,
            "login_streak": self.login_streak,
            "badges": self.badges,
            "achievements": self.achievements,
            "referral_code": self.referral_code,
            "successful_referrals": self.successful_referrals,
        }
    
    @staticmethod
    def from_dict(data: Dict) -> "PlayerInstance":
        """Load from dictionary"""
        player = PlayerInstance(data.get("user_id"), data.get("username", "Player"))
        
        # Restore all state
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.coins = data.get("coins", 100)
        player.wins = data.get("wins", 0)
        player.losses = data.get("losses", 0)
        player.elo = data.get("elo", 1000)
        player.current_streak = data.get("current_streak", 0)
        player.current_region = data.get("current_region", "kanto")
        player.regions_unlocked = data.get("regions_unlocked", ["kanto"])
        player.pokemon_caught = data.get("pokemon_caught", 0)
        player.pokedex_seen = set(data.get("pokedex_seen", []))
        player.inventory = data.get("inventory", {})
        player.pokeballs = data.get("pokeballs", {"pokeball": 0, "greatball": 0, "ultraball": 0})
        player.login_streak = data.get("login_streak", 1)
        player.badges = data.get("badges", [])
        player.achievements = data.get("achievements", [])
        player.successful_referrals = data.get("successful_referrals", 0)
        player.created_date = data.get("created_date", player.created_date)
        
        return player


if __name__ == "__main__":
    print("Testing Player Model...")
    p = PlayerInstance(123, "Trainer")
    print(f"✅ Created {p.username}")
    print(f"✅ Profile:\n{p.get_profile()}")
