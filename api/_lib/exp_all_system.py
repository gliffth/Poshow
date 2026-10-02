"""
⚡ POSHOW - EXP ALL SYSTEM
Distribute battle XP across all Pokemon
"""

import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpAllItem:
    """EXP All - distributes XP to all Pokemon in collection"""
    
    ITEM_ID = "exp_all"
    ITEM_NAME = "EXP All"
    PRICE = 500  # Coins
    DESCRIPTION = "Distributes XP to all Pokemon in your team"
    
    @staticmethod
    def use(player, xp_amount: int, all_pokemon: bool = False, free: bool = False) -> Dict:
        """
        Use EXP All to distribute XP
        
        Args:
            player: PlayerInstance
            xp_amount: XP earned from battle
            all_pokemon: If True, distribute to collection; if False, active team only
        
        Returns: {
            "success": bool,
            "total_distributed": int,
            "per_pokemon": int,
            "message": str,
            "level_ups": List[str]
        }
        """
        
        if not free and not player.inventory.get("exp_all", 0):   # free = already paid for this battle
            return {
                "success": False,
                "message": "❌ You don't have EXP All!",
                "total_distributed": 0
            }
        
        pokemon_to_reward = player.active_team if not all_pokemon else player.pokemon_collection
        # fainted Pokemon don't get a share
        pokemon_to_reward = [
            p for p in pokemon_to_reward
            if not getattr(p, "is_fainted", False) and getattr(p, "current_hp", 1) > 0
        ]
        
        if not pokemon_to_reward:
            return {
                "success": False,
                "message": "❌ No Pokemon to reward!",
                "total_distributed": 0
            }
        
        # Divide XP equally among Pokemon
        xp_per_pokemon = xp_amount // len(pokemon_to_reward)
        
        level_ups = []
        for poke in pokemon_to_reward:
            old_level = poke.level
            poke.add_experience(xp_per_pokemon)
            
            if poke.level > old_level:
                level_ups.append(f"🎉 {poke.nickname} → Lv {poke.level}!")
        
        # Message
        message = f"""✨ **EXP ALL ACTIVATED**

Shared {xp_amount} XP among {len(pokemon_to_reward)} Pokemon
Each got {xp_per_pokemon} XP"""
        
        if level_ups:
            message += f"\n\n{chr(10).join(level_ups)}"
        
        return {
            "success": True,
            "total_distributed": xp_amount,
            "per_pokemon": xp_per_pokemon,
            "pokemon_count": len(pokemon_to_reward),
            "level_ups": level_ups,
            "message": message
        }
    
    @staticmethod
    def has_item(player) -> bool:
        """Check if player has EXP All"""
        return player.inventory.get("exp_all", 0) > 0
    
    @staticmethod
    def add_to_inventory(player, quantity: int = 1):
        """Add EXP All to inventory"""
        if "exp_all" not in player.inventory:
            player.inventory["exp_all"] = 0
        player.inventory["exp_all"] += quantity
        logger.info(f"Added {quantity}x EXP All to player {player.user_id}")
    
    @staticmethod
    def remove_from_inventory(player, quantity: int = 1) -> bool:
        """Remove EXP All from inventory"""
        if player.inventory.get("exp_all", 0) >= quantity:
            player.inventory["exp_all"] -= quantity
            return True
        return False


def apply_exp_all_to_battle(player, base_xp: int, use_exp_all: bool = False) -> Dict:
    """
    Award XP after battle with optional EXP All
    
    Args:
        player: PlayerInstance
        base_xp: Base XP amount from battle
        use_exp_all: Whether to use EXP All if available
    
    Returns: Reward info dict
    """
    
    result = {
        "base_xp": base_xp,
        "used_exp_all": False,
        "message": f"💰 +{base_xp} XP"
    }
    
    if use_exp_all and ExpAllItem.has_item(player):
        # Use EXP All
        exp_result = ExpAllItem.use(player, base_xp, all_pokemon=False)
        
        if exp_result["success"]:
            ExpAllItem.remove_from_inventory(player)
            result["used_exp_all"] = True
            result["message"] = exp_result["message"]
            result["level_ups"] = exp_result.get("level_ups", [])
            return result
    
    # Normal: only active Pokemon gets XP
    if player.active_team:
        old_level = player.active_team[0].level
        player.active_team[0].add_experience(base_xp)
        
        if player.active_team[0].level > old_level:
            result["message"] += f"\n🎉 {player.active_team[0].nickname} → Lv {player.active_team[0].level}!"
            result["level_ups"] = [f"{player.active_team[0].nickname}"]
    
    return result
