"""
⚡ POSHOW - ADMIN PANEL
/creative command for admin cheats and special features
"""

import logging
from typing import Dict, Optional
from pokemon_model import PokemonInstance
from player_model import PlayerInstance
from currency_system import currency
from pokeapi_manager import pokeapi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdminPanel:
    """
    Admin creative mode panel
    Allows adding Pokemon, items, coins, etc.
    """
    
    # Admin user IDs (edit in config.py)
    ADMIN_IDS = [6346043548, 7789636833, 7818848697]  # Replace with actual admin IDs
    
    def __init__(self):
        """Initialize admin panel"""
        logger.info("✅ Admin Panel initialized")
    
    # ════════════════════════════════════════════════════════════════
    # ADMIN VERIFICATION
    # ════════════════════════════════════════════════════════════════
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.ADMIN_IDS
    
    # ════════════════════════════════════════════════════════════════
    # PLAYER COMMANDS
    # ════════════════════════════════════════════════════════════════
    
    def add_coins(self, player: PlayerInstance, amount: int) -> Dict:
        """Add coins to player"""
        player.add_coins(amount)
        return {
            "success": True,
            "message": f"➕ Added {amount}₽ to {player.username}",
            "coins": player.coins
        }
    
    def set_coins(self, player: PlayerInstance, amount: int) -> Dict:
        """Set player coins to exact amount"""
        player.coins = max(0, amount)
        return {
            "success": True,
            "message": f"🎯 Set {player.username}'s coins to {player.coins}₽",
            "coins": player.coins
        }
    
    def add_level(self, player: PlayerInstance, levels: int) -> Dict:
        """Add player levels"""
        player.level += levels
        return {
            "success": True,
            "message": f"⬆️ {player.username} is now Lv{player.level}",
            "level": player.level
        }
    
    def set_level(self, player: PlayerInstance, level: int) -> Dict:
        """Set player level"""
        player.level = max(1, level)
        return {
            "success": True,
            "message": f"🎯 {player.username} is now Lv{player.level}",
            "level": player.level
        }
    
    def reset_player(self, player: PlayerInstance) -> Dict:
        """Reset player to level 1"""
        player.level = 1
        player.experience = 0
        player.coins = 0
        player.wins = 0
        player.losses = 0
        player.elo = 1000
        player.pokemon_collection = []
        player.active_team = []
        
        return {
            "success": True,
            "message": f"🔄 {player.username} has been reset to Lv1"
        }
    
    # ════════════════════════════════════════════════════════════════
    # POKEMON COMMANDS
    # ════════════════════════════════════════════════════════════════
    
    def add_pokemon(self, player: PlayerInstance, pokemon_name: str, 
                    level: int = 50, is_shiny: bool = False) -> Dict:
        """Add Pokemon to player's collection"""
        try:
            pokemon = PokemonInstance(pokemon_name, level, player.user_id)
            if is_shiny:
                pokemon.is_shiny = True
            
            player.pokemon_collection.append(pokemon)
            player.add_to_pokedex(pokemon.api_data["id"])
            
            return {
                "success": True,
                "message": f"✨ Added {pokemon.nickname} Lv{level} {'(Shiny)' if is_shiny else ''}",
                "pokemon": pokemon
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ Error: {e}"
            }
    
    def create_special_variant(self, player: PlayerInstance, base_pokemon: str,
                              variant_name: str, new_type: str, 
                              special_moves: list) -> Dict:
        """Create special Pokemon variant"""
        try:
            variant = pokeapi.create_special_variant(
                base_pokemon, variant_name, new_type, special_moves
            )
            
            if not variant:
                return {
                    "success": False,
                    "message": f"❌ Could not create variant of {base_pokemon}"
                }
            
            # Create instance from variant
            pokemon = PokemonInstance(base_pokemon, 50, player.user_id)
            pokemon.species_name = variant_name
            pokemon.api_data["types"] = [new_type]
            pokemon.moves = special_moves[:4]
            
            player.pokemon_collection.append(pokemon)
            
            return {
                "success": True,
                "message": f"🌟 Created special variant: {variant_name}",
                "pokemon": pokemon
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ Error: {e}"
            }
    
    def set_iv(self, pokemon: PokemonInstance, stat: str, value: int) -> Dict:
        """Set Pokemon IV"""
        if stat not in pokemon.iv or not 0 <= value <= 31:
            return {
                "success": False,
                "message": f"❌ Invalid IV stat or value (0-31)"
            }
        
        pokemon.iv[stat] = value
        pokemon.recalculate_stats()
        
        return {
            "success": True,
            "message": f"🎯 {pokemon.nickname}'s {stat.upper()} IV set to {value}",
            "iv": pokemon.iv[stat]
        }
    
    def max_ev(self, pokemon: PokemonInstance) -> Dict:
        """Max out all EVs"""
        max_evs = {"hp": 252, "atk": 252, "def": 252, "sp_atk": 252, "sp_def": 252, "speed": 6}
        pokemon.ev = max_evs
        pokemon.recalculate_stats()
        
        return {
            "success": True,
            "message": f"⚡ {pokemon.nickname}'s EVs maxed out",
            "ev": pokemon.ev
        }
    
    def set_level_pokemon(self, pokemon: PokemonInstance, level: int) -> Dict:
        """Set Pokemon level"""
        pokemon.level = max(1, min(100, level))
        pokemon.recalculate_stats()
        pokemon.restore_pp()
        
        return {
            "success": True,
            "message": f"📈 {pokemon.nickname} is now Lv{level}",
            "level": pokemon.level
        }
    
    # ════════════════════════════════════════════════════════════════
    # ITEM COMMANDS
    # ════════════════════════════════════════════════════════════════
    
    def add_items(self, player: PlayerInstance, item_name: str, quantity: int) -> Dict:
        """Add items to inventory"""
        player.add_item(item_name, quantity)
        
        return {
            "success": True,
            "message": f"📦 Added {quantity}x {item_name} to inventory",
            "quantity": player.inventory.get(item_name, 0)
        }
    
    def add_pokeballs(self, player: PlayerInstance, ball_type: str, quantity: int) -> Dict:
        """Add Pokéballs"""
        player.add_pokeball(ball_type, quantity)
        
        return {
            "success": True,
            "message": f"🔴 Added {quantity}x {ball_type}",
            "quantity": player.pokeballs.get(ball_type, 0)
        }
    
    def give_all_items(self, player: PlayerInstance) -> Dict:
        """Give player all shop items (1x each)"""
        from currency_system import currency
        
        for item in currency.SHOP_PRICES:
            player.add_item(item, 1)
        
        return {
            "success": True,
            "message": f"🎁 Given all shop items to {player.username}",
            "items_added": len(currency.SHOP_PRICES)
        }
    
    # ════════════════════════════════════════════════════════════════
    # ACHIEVEMENT COMMANDS
    # ════════════════════════════════════════════════════════════════
    
    def add_badge(self, player: PlayerInstance, badge_name: str) -> Dict:
        """Add badge to player"""
        if player.add_badge(badge_name):
            return {
                "success": True,
                "message": f"🏅 Added {badge_name} badge to {player.username}",
                "badges": len(player.badges)
            }
        return {
            "success": False,
            "message": f"Already has {badge_name}"
        }
    
    def add_achievement(self, player: PlayerInstance, achievement_name: str) -> Dict:
        """Add achievement to player"""
        if player.add_achievement(achievement_name):
            return {
                "success": True,
                "message": f"🎖️ Added {achievement_name} achievement",
                "achievements": len(player.achievements)
            }
        return {
            "success": False,
            "message": f"Already has {achievement_name}"
        }
    
    # ════════════════════════════════════════════════════════════════
    # REGION COMMANDS
    # ════════════════════════════════════════════════════════════════
    
    def unlock_all_regions(self, player: PlayerInstance) -> Dict:
        """Unlock all regions"""
        regions = ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "paldea"]
        for region in regions:
            player.unlock_region(region)
        
        return {
            "success": True,
            "message": f"🌍 All 9 regions unlocked for {player.username}",
            "regions": len(player.regions_unlocked)
        }
    
    # ════════════════════════════════════════════════════════════════
    # CREATIVE MENU
    # ════════════════════════════════════════════════════════════════
    
    def get_creative_menu(self) -> str:
        """Get creative mode menu"""
        menu = """
🔧 POSHOW CREATIVE MODE

👤 PLAYER COMMANDS:
  /creative coins <amount> - Add coins
  /creative level <num> - Add levels
  /creative reset - Reset player
  /creative badges - Show badge commands
  /creative unlock_all - Unlock all regions

🐾 POKEMON COMMANDS:
  /creative pokemon <name> [level] - Add Pokemon
  /creative variant <base> <name> <type> - Create special variant
  /creative iv <stat> <value> - Set IV
  /creative maxev - Max out EVs
  /creative pokemon_level <level> - Set Pokemon level

🎁 ITEM COMMANDS:
  /creative items <item> <qty> - Add items
  /creative balls <type> <qty> - Add Pokéballs
  /creative fullshop - Get all shop items

🏅 ACHIEVEMENT COMMANDS:
  /creative badge <name> - Add badge
  /creative achievement <name> - Add achievement

🔒 SESSION COMMANDS:
  /creativeend - Exit creative mode

⚠️ USE WITH CAUTION - Changes are permanent!
"""
        return menu
    
    # ════════════════════════════════════════════════════════════════
    # LOGGING
    # ════════════════════════════════════════════════════════════════
    
    def log_command(self, admin_id: int, admin_name: str, command: str, 
                    target_id: int, result: str) -> None:
        """Log admin command for audit trail"""
        import datetime
        timestamp = datetime.datetime.now().isoformat()
        log_msg = f"[{timestamp}] ADMIN {admin_name} ({admin_id}): {command} on {target_id} → {result}"
        logger.warning(log_msg)

# Singleton
admin = AdminPanel()

if __name__ == "__main__":
    print("Testing Admin Panel...")
    print("✅ Admin Panel loaded")
    print("Note: Set ADMIN_IDS in admin_panel.py")

