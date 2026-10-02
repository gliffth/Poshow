"""
⚡ POSHOW - RARE CANDY SYSTEM
Instant level up items
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RareCandy:
    """Rare Candy - instant level up"""
    
    ITEM_ID = "rare_candy"
    ITEM_NAME = "Rare Candy"
    PRICE = 1000
    DESCRIPTION = "Instantly levels up one Pokémon"
    
    MAX_LEVEL = 100
    
    @staticmethod
    def use(pokemon) -> dict:
        """
        Use Rare Candy on a Pokemon
        
        Returns: {
            "success": bool,
            "old_level": int,
            "new_level": int,
            "message": str
        }
        """
        
        if pokemon.level >= RareCandy.MAX_LEVEL:
            return {
                "success": False,
                "message": f"❌ {pokemon.nickname} is already at max level!"
            }
        
        old_level = pokemon.level
        pokemon.level = min(pokemon.level + 1, RareCandy.MAX_LEVEL)
        if hasattr(pokemon, 'experience'):
            pokemon.experience = 0
        
        # Recalculate stats
        pokemon.max_hp = pokemon._get_max_hp()
        pokemon.current_hp = pokemon.max_hp
        pokemon.actual_stats = pokemon._calculate_stats()
        
        message = f"""🍬 **RARE CANDY USED**

**{pokemon.nickname}**
Lv {old_level} → Lv {pokemon.level}

HP: {pokemon.current_hp}/{pokemon.max_hp}"""
        
        return {
            "success": True,
            "old_level": old_level,
            "new_level": pokemon.level,
            "message": message
        }
    
    @staticmethod
    def add_to_inventory(player, quantity: int = 1):
        """Add Rare Candy to inventory"""
        if "rare_candy" not in player.inventory:
            player.inventory["rare_candy"] = 0
        player.inventory["rare_candy"] += quantity
        logger.info(f"Added {quantity}x Rare Candy to player {player.user_id}")
    
    @staticmethod
    def has_item(player) -> bool:
        """Check if player has Rare Candy"""
        return player.inventory.get("rare_candy", 0) > 0
    
    @staticmethod
    def remove_from_inventory(player, quantity: int = 1) -> bool:
        """Remove Rare Candy from inventory"""
        if player.inventory.get("rare_candy", 0) >= quantity:
            player.inventory["rare_candy"] -= quantity
            return True
        return False
