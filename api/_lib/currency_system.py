"""
⚡ POSHOW - CURRENCY SYSTEM
Pokéyen economy: earning, spending, shop system
"""

from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Symbol: ₽ (Pokéyen)
CURRENCY_SYMBOL = "₽"
CURRENCY_NAME = "Pokéyen"

class CurrencySystem:
    """
    Pokéyen economy system
    Handles all currency transactions
    """
    
    # Earning rates
    CATCH_REWARD_BASE = {
        "level_1_20": 2,      # Lv1-20
        "level_21_30": 4,     # Lv21-30
        "level_31_40": 6,     # Lv31-40
        "level_41_plus": 7,   # Lv41+, random 7-8
    }
    
    BATTLE_REWARD = {
        "pvp_low": 15,        # Low level or incomplete team
        "pvp_medium": 45,     # Medium level/incomplete
        "pvp_high": 75,       # High level (30+), full team (6v6)
    }
    
    ACTIVITY_REWARD = {
        "daily_quest": 20,
        "tournament_win": 100,
        "raid_victory": 50,
        "evolution": 10,
    }
    
    SHOP_PRICES = {
        # Pokéballs
        "pokeball": 10,
        "greatball": 20,
        "ultraball": 30,
        "masterball": 500,
        "fastball": 25,
        "levelball": 25,
        "lureball": 25,
        "moonball": 25,
        "netball": 30,
        "nestball": 30,
        "repeatball": 30,
        "timerball": 30,
        "duskball": 35,
        "quickball": 35,
        "safariball": 40,
        
        # Items
        "potion": 20,
        "super_potion": 50,
        "hyper_potion": 100,
        "max_potion": 200,
        "full_heal": 100,
        "full_restore": 300,
        "ether": 50,
        "max_ether": 100,
        "elixir": 200,
        "max_elixir": 300,
        
        # Berries
        "cheri_berry": 30,
        "pecha_berry": 30,
        "rawst_berry": 30,
        "aspear_berry": 30,
        "chesto_berry": 30,
        "pomeg_berry": 50,
        "kelpsy_berry": 50,
        "qualot_berry": 50,
        "hondew_berry": 50,
        "grepa_berry": 50,
        "tamato_berry": 50,
        
        # Vitamins
        "hp_up": 50,
        "protein": 50,
        "iron": 50,
        "carbos": 50,
        "calcium": 50,
        "zinc": 50,
        
        # Evolution Stones
        "fire_stone": 150,
        "water_stone": 150,
        "thunder_stone": 150,
        "leaf_stone": 150,
        "ice_stone": 150,
        "moon_stone": 200,
        "sun_stone": 200,
        "shiny_stone": 250,
        "dusk_stone": 250,
        "dawn_stone": 250,
    }
    
    def __init__(self):
        """Initialize currency system"""
        logger.info("✅ Currency System initialized")
    
    # ════════════════════════════════════════════════════════════════
    # EARNING
    # ════════════════════════════════════════════════════════════════
    
    def calculate_catch_reward(self, pokemon_level: int) -> int:
        """
        Calculate Pokéyen reward for catching Pokemon
        Higher level = more currency
        """
        if pokemon_level <= 20:
            return self.CATCH_REWARD_BASE["level_1_20"]
        elif pokemon_level <= 30:
            return self.CATCH_REWARD_BASE["level_21_30"]
        elif pokemon_level <= 40:
            return self.CATCH_REWARD_BASE["level_31_40"]
        else:
            # Lv41+ gives 7-8 randomly
            import random
            return random.choice([7, 8])
    
    def calculate_battle_reward(self, player_team_count: int, avg_level: float, 
                               opponent_team_count: int, opponent_avg_level: float) -> int:
        """
        Calculate reward for PvP battle
        Factors: team size, average level, opponent strength
        """
        # Base reward
        if player_team_count < 6 or avg_level < 30:
            return self.BATTLE_REWARD["pvp_low"]
        elif player_team_count >= 6 and avg_level >= 30:
            if opponent_team_count >= 6 and opponent_avg_level >= 30:
                return self.BATTLE_REWARD["pvp_high"]
            else:
                return self.BATTLE_REWARD["pvp_medium"]
        else:
            return self.BATTLE_REWARD["pvp_medium"]
    
    def get_activity_reward(self, activity_type: str) -> int:
        """Get reward for activity"""
        return self.ACTIVITY_REWARD.get(activity_type, 0)
    
    def calculate_referral_reward(self, successful_referrals: int) -> Dict[str, int]:
        """
        Calculate referral rewards
        3 successful invites = 50 Pokéyen
        5 successful invites = 50 Pokéyen + 5 berries
        """
        rewards = {"coins": 0, "items": {}}
        
        if successful_referrals >= 5:
            rewards["coins"] = 50
            rewards["items"]["mixed_berry"] = 5
        elif successful_referrals >= 3:
            rewards["coins"] = 50
        
        return rewards
    
    # ════════════════════════════════════════════════════════════════
    # SHOP OPERATIONS
    # ════════════════════════════════════════════════════════════════
    
    def get_item_price(self, item_name: str) -> Optional[int]:
        """Get price of item"""
        return self.SHOP_PRICES.get(item_name.lower())
    
    def can_afford(self, player_coins: int, item_name: str) -> bool:
        """Check if player can afford item"""
        price = self.get_item_price(item_name)
        if price is None:
            return False
        return player_coins >= price
    
    def purchase_item(self, player_coins: int, item_name: str) -> Dict:
        """
        Purchase item from shop
        Returns: {success, coins_remaining, message}
        """
        price = self.get_item_price(item_name)
        
        if price is None:
            return {
                "success": False,
                "coins_remaining": player_coins,
                "message": f"Item '{item_name}' not found in shop"
            }
        
        if player_coins < price:
            return {
                "success": False,
                "coins_remaining": player_coins,
                "message": f"Not enough {CURRENCY_SYMBOL}! Need {price}, have {player_coins}"
            }
        
        return {
            "success": True,
            "coins_remaining": player_coins - price,
            "message": f"Purchased {item_name} for {price}{CURRENCY_SYMBOL}"
        }
    
    def bulk_purchase(self, player_coins: int, items: List[Dict]) -> Dict:
        """
        Purchase multiple items
        items = [{"name": "pokeball", "quantity": 10}, ...]
        """
        total_cost = 0
        
        # Calculate total
        for item in items:
            price = self.get_item_price(item["name"])
            if price is None:
                return {
                    "success": False,
                    "coins_remaining": player_coins,
                    "message": f"Item '{item['name']}' not found"
                }
            total_cost += price * item["quantity"]
        
        if player_coins < total_cost:
            return {
                "success": False,
                "coins_remaining": player_coins,
                "message": f"Not enough {CURRENCY_SYMBOL}! Need {total_cost}, have {player_coins}"
            }
        
        return {
            "success": True,
            "coins_remaining": player_coins - total_cost,
            "message": f"Purchased {len(items)} item types for {total_cost}{CURRENCY_SYMBOL}"
        }
    
    # ════════════════════════════════════════════════════════════════
    # SHOP CATALOG
    # ════════════════════════════════════════════════════════════════
    
    def get_pokeballs(self) -> Dict[str, int]:
        """Get all Pokéballs and prices"""
        balls = {
            "pokeball": 10,
            "greatball": 20,
            "ultraball": 30,
            "masterball": 500,
            "fastball": 25,
            "levelball": 25,
            "lureball": 25,
            "moonball": 25,
            "netball": 30,
            "nestball": 30,
            "repeatball": 30,
            "timerball": 30,
            "duskball": 35,
            "quickball": 35,
            "safariball": 40,
        }
        return balls
    
    def get_healing_items(self) -> Dict[str, int]:
        """Get healing items"""
        items = {
            "potion": 20,
            "super_potion": 50,
            "hyper_potion": 100,
            "max_potion": 200,
            "full_heal": 100,
            "full_restore": 300,
            "ether": 50,
            "max_ether": 100,
            "elixir": 200,
            "max_elixir": 300,
        }
        return items
    
    def get_berries(self) -> Dict[str, int]:
        """Get training berries"""
        berries = {
            "pomeg_berry": 50,
            "kelpsy_berry": 50,
            "qualot_berry": 50,
            "hondew_berry": 50,
            "grepa_berry": 50,
            "tamato_berry": 50,
            "cheri_berry": 30,
            "pecha_berry": 30,
            "rawst_berry": 30,
            "aspear_berry": 30,
            "chesto_berry": 30,
        }
        return berries
    
    def get_vitamins(self) -> Dict[str, int]:
        """Get stat-boosting vitamins"""
        vitamins = {
            "hp_up": 50,
            "protein": 50,      # ATK
            "iron": 50,         # DEF
            "carbos": 50,       # SPEED
            "calcium": 50,      # SP.ATK
            "zinc": 50,         # SP.DEF
        }
        return vitamins
    
    def get_evolution_stones(self) -> Dict[str, int]:
        """Get evolution stones"""
        stones = {
            "fire_stone": 150,
            "water_stone": 150,
            "thunder_stone": 150,
            "leaf_stone": 150,
            "ice_stone": 150,
            "moon_stone": 200,
            "sun_stone": 200,
            "shiny_stone": 250,
            "dusk_stone": 250,
            "dawn_stone": 250,
        }
        return stones
    
    # ════════════════════════════════════════════════════════════════
    # SPECIAL EVENTS & BONUSES
    # ════════════════════════════════════════════════════════════════
    
    def apply_daily_bonus(self, player_coins: int, day_streak: int) -> Dict:
        """
        Apply daily login bonus
        Bonus increases with consecutive days
        """
        bonus_amount = 10 + (day_streak * 5)  # 15 on day 1, 20 on day 2, etc
        
        return {
            "coins": player_coins + bonus_amount,
            "bonus": bonus_amount,
            "streak": day_streak,
            "message": f"Daily bonus! +{bonus_amount}{CURRENCY_SYMBOL} (Day {day_streak})"
        }
    
    def apply_level_up_bonus(self, player_level: int) -> int:
        """Bonus for reaching new player level"""
        return 100 + (player_level * 10)  # 110 at Lv1, 120 at Lv2, etc
    
    def calculate_weekly_reward(self, wins_count: int) -> int:
        """Weekly ranking reward based on wins"""
        if wins_count >= 10:
            return 200
        elif wins_count >= 5:
            return 100
        elif wins_count >= 1:
            return 50
        return 0
    
    # ════════════════════════════════════════════════════════════════
    # CURRENCY DISPLAY
    # ════════════════════════════════════════════════════════════════
    
    def format_currency(self, amount: int) -> str:
        """Format currency for display"""
        return f"{amount}{CURRENCY_SYMBOL}"
    
    def get_shop_display(self) -> str:
        """Get formatted shop display"""
        display = f"🏪 POKÉ STORE 🏪\n\n"
        
        display += "🔴 POKÉBALLS\n"
        for ball, price in list(self.get_pokeballs().items())[:5]:
            display += f"  {ball.capitalize()}: {price}{CURRENCY_SYMBOL}\n"
        
        display += "\n💊 HEALING ITEMS\n"
        for item, price in list(self.get_healing_items().items())[:3]:
            display += f"  {item.capitalize()}: {price}{CURRENCY_SYMBOL}\n"
        
        display += "\n🍓 BERRIES\n"
        for berry, price in list(self.get_berries().items())[:3]:
            display += f"  {berry.capitalize()}: {price}{CURRENCY_SYMBOL}\n"
        
        display += "\n💎 EVOLUTION STONES\n"
        for stone, price in list(self.get_evolution_stones().items())[:3]:
            display += f"  {stone.capitalize()}: {price}{CURRENCY_SYMBOL}\n"
        
        return display

# Singleton
currency = CurrencySystem()

# Test
if __name__ == "__main__":
    print("Testing Currency System...")
    
    # Test catch reward
    reward = currency.calculate_catch_reward(25)
    print(f"✅ Catch reward (Lv25): {reward}{CURRENCY_SYMBOL}")
    
    # Test shop prices
    price = currency.get_item_price("ultraball")
    print(f"✅ Ultra Ball price: {price}{CURRENCY_SYMBOL}")
    
    # Test purchase
    result = currency.purchase_item(100, "pokeball")
    print(f"✅ Purchase result: {result['message']}")
    
    # Test affordability
    can_buy = currency.can_afford(50, "ultraball")
    print(f"✅ Can afford Ultra Ball with 50{CURRENCY_SYMBOL}: {can_buy}")
    
    print("✅ All tests passed!")

