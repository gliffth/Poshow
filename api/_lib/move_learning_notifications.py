"""
⚡ POSHOW - POKEMON MOVE LEARNING NOTIFICATIONS
Handles level up events and move learning prompts
"""

from typing import List, Dict, Tuple
from move_learning_system import get_new_moves_at_level, get_move_info

# ════════════════════════════════════════════════════════════════
# MOVE LEARNING HANDLER
# ════════════════════════════════════════════════════════════════

class MoveUnlocker:
    """Handles Pokemon learning new moves"""
    
    @staticmethod
    def handle_level_up(pokemon, old_level: int, new_level: int) -> Dict:
        """
        Handle Pokemon leveling up and learning new moves
        
        Args:
            pokemon: Pokemon instance
            old_level: Previous level
            new_level: New level after leveling
        
        Returns:
            {
                "level_up": True/False,
                "new_moves": ["move1", "move2"],
                "message": "Notification message"
            }
        """
        try:
            # Get new moves learned
            new_moves = get_new_moves_at_level(pokemon.species_name, new_level, old_level)
            
            if not new_moves:
                # No new moves at this level
                message = f"🎉 {pokemon.nickname} grew to Lv{new_level}!\n\nNo new moves learned this level."
                return {
                    "level_up": True,
                    "new_moves": [],
                    "message": message,
                    "has_choice": False
                }
            
            elif len(new_moves) == 1:
                # Single move - auto-learn if space
                move = new_moves[0]
                move_info = get_move_info(move)
                
                if len(pokemon.moves) < 4:
                    # Has space - auto-learn
                    pokemon.moves.append(move)
                    message = f"""🎉 {pokemon.nickname} grew to Lv{new_level}!

✨ Learned new move: {move.upper()}
Power: {move_info['power']} | Accuracy: {move_info['accuracy']}%
Type: {move_info['type'].upper()}
{move_info['desc']}"""
                    
                    return {
                        "level_up": True,
                        "new_moves": [move],
                        "message": message,
                        "has_choice": False,
                        "auto_learned": True
                    }
                else:
                    # Team is full - need to replace
                    message = f"""🎉 {pokemon.nickname} grew to Lv{new_level}!

✨ Wants to learn: {move.upper()}
Power: {move_info['power']} | Accuracy: {move_info['accuracy']}%
Type: {move_info['type'].upper()}
{move_info['desc']}

Your team is full! Which move do you want to replace?"""
                    
                    return {
                        "level_up": True,
                        "new_moves": [move],
                        "message": message,
                        "has_choice": True,
                        "current_moves": pokemon.moves,
                        "move_to_learn": move
                    }
            
            else:
                # Multiple moves - player chooses which one to learn
                message = f"""🎉 {pokemon.nickname} grew to Lv{new_level}!

✨ Can learn multiple moves! Choose one:
"""
                for i, move in enumerate(new_moves, 1):
                    move_info = get_move_info(move)
                    message += f"\n{i}. {move.upper()}\n"
                    message += f"   Power: {move_info['power']} | Acc: {move_info['accuracy']}%\n"
                    message += f"   Type: {move_info['type'].upper()}"
                
                return {
                    "level_up": True,
                    "new_moves": new_moves,
                    "message": message,
                    "has_choice": True,
                    "multiple_choice": True
                }
        
        except Exception as e:
            return {
                "level_up": True,
                "new_moves": [],
                "message": f"🎉 {pokemon.nickname} grew to Lv{new_level}!",
                "error": str(e)
            }
    
    @staticmethod
    def learn_move(pokemon, move_name: str) -> Dict:
        """
        Teach Pokemon a new move
        
        Args:
            pokemon: Pokemon instance
            move_name: Move to learn
        
        Returns:
            {
                "success": True/False,
                "message": "Result message",
                "replaced_move": "move_name" or None
            }
        """
        try:
            move_name = move_name.lower()
            move_info = get_move_info(move_name)
            
            if len(pokemon.moves) < 4:
                # Has space
                pokemon.moves.append(move_name)
                message = f"""✅ {pokemon.nickname} learned {move_name.upper()}!

Power: {move_info['power']} | Accuracy: {move_info['accuracy']}%
Type: {move_info['type'].upper()}
{move_info['desc']}

Current Moves: {', '.join(m.upper() for m in pokemon.moves)}"""
                
                return {
                    "success": True,
                    "message": message,
                    "replaced_move": None
                }
            
            else:
                message = f"""🎉 {pokemon.nickname} wants to learn {move_name.upper()}!

Power: {move_info['power']} | Accuracy: {move_info['accuracy']}%
Type: {move_info['type'].upper()}
{move_info['desc']}

Current Moves:
"""
                for i, m in enumerate(pokemon.moves, 1):
                    message += f"{i}. {m.upper()}\n"
                
                message += f"\nWhich move do you want to replace?"
                
                return {
                    "success": False,
                    "message": message,
                    "needs_replacement": True,
                    "move_to_learn": move_name,
                    "current_moves": pokemon.moves
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ Error learning move: {str(e)}",
                "error": str(e)
            }
    
    @staticmethod
    def replace_move(pokemon, old_move_index: int, new_move_name: str) -> Dict:
        """
        Replace one move with another
        
        Args:
            pokemon: Pokemon instance
            old_move_index: Index of move to replace (0-3)
            new_move_name: New move name
        
        Returns:
            {
                "success": True/False,
                "message": "Result message"
            }
        """
        try:
            if not 0 <= old_move_index < len(pokemon.moves):
                return {
                    "success": False,
                    "message": "❌ Invalid move selection!"
                }
            
            old_move = pokemon.moves[old_move_index]
            new_move_name = new_move_name.lower()
            
            pokemon.moves[old_move_index] = new_move_name
            
            message = f"""✅ Move Updated!

Forgot: {old_move.upper()}
Learned: {new_move_name.upper()}

Current Moves:
"""
            for i, m in enumerate(pokemon.moves, 1):
                message += f"{i}. {m.upper()}\n"
            
            return {
                "success": True,
                "message": message
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ Error replacing move: {str(e)}"
            }

# ════════════════════════════════════════════════════════════════
# EXAMPLE NOTIFICATION FORMATS
# ════════════════════════════════════════════════════════════════

def format_level_up_notification(pokemon, old_level: int, new_level: int) -> Tuple[str, List]:
    """
    Format level up notification with buttons
    
    Returns:
        (message, button_rows)
    """
    result = MoveUnlocker.handle_level_up(pokemon, old_level, new_level)
    
    message = result["message"]
    buttons = []
    
    if result.get("has_choice"):
        if result.get("multiple_choice"):
            # Multiple moves to choose from
            for i, move in enumerate(result["new_moves"], 1):
                buttons.append([f"{i}️⃣ {move.upper()}"])
        else:
            # Replace existing move
            buttons.append(["✅ Learn Move"])
            buttons.append(["❌ Forget", "⬅️ Skip"])
    else:
        buttons.append(["✅ Continue"])
    
    return message, buttons

# ════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Move Learning Notification System Loaded ✅")
    print("\nExample: Charmander learning moves as it levels\n")
    
    # Mock Pokemon object
    class MockPokemon:
        def __init__(self):
            self.species_name = "charmander"
            self.nickname = "Charmy"
            self.level = 5
            self.moves = ["scratch", "growl"]
    
    poke = MockPokemon()
    
    # Level 5 → 7 (should learn ember)
    print("Leveling Charmander from Lv5 to Lv7:")
    result = MoveUnlocker.handle_level_up(poke, 5, 7)
    print(result["message"])
    print(f"\nNew Moves: {result['new_moves']}")
    print()

