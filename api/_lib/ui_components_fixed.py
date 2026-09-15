"""
⚡ POSHOW BOT - UI & BATTLE INTEGRATION FIXES
Proper starter selection and battle system integration
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from typing import List, Tuple

# ════════════════════════════════════════════════════════════════
# STARTER SELECTION UI - FIXED
# ════════════════════════════════════════════════════════════════

def get_starter_buttons():
    """
    Get starter selection buttons
    Format: 🔥 Charmander | 💧 Squirtle | 🌿 Bulbasaur (side by side)
    """
    buttons = [[
        InlineKeyboardButton("🔥", callback_data="starter_charmander"),
        InlineKeyboardButton("💧", callback_data="starter_squirtle"),
        InlineKeyboardButton("🌿 ", callback_data="starter_bulbasaur"),
    ]]
    return buttons

def get_starter_message() -> str:
    """Get starter selection message"""
    return """🎮 CHOOSE YOUR STARTER POKEMON

🔥 CHARMANDER - Fire Type
Fire-breathing dragon. Loves warmth.
Evolution: Charmeleon → Charizard

💧 SQUIRTLE - Water Type
Water turtle. Hides in its shell.
Evolution: Wartortle → Blastoise

🌿 BULBASAUR - Grass Type
Plant bulb on back. Gentle nature.
Evolution: Ivysaur → Venusaur

Choose one to begin your journey!"""

# ════════════════════════════════════════════════════════════════
# BATTLE UI - FIXED
# ════════════════════════════════════════════════════════════════

def format_battle_panel(player_pokemon, wild_pokemon, moves: List[str]) -> str:
    """
    Format battle display panel
    
    Shows:
    - Wild Pokemon stats
    - Player Pokemon stats
    - Available moves with data
    """
    try:
        # Get types safely
        wild_types = getattr(wild_pokemon, 'types', ['normal'])
        if isinstance(wild_types, str):
            wild_types = [wild_types]
        wild_types_str = " / ".join(wild_types)
        
        player_types = getattr(player_pokemon, 'types', ['normal'])
        if isinstance(player_types, str):
            player_types = [player_types]
        player_types_str = " / ".join(player_types)
        
        # HP bars (20 chars)
        def get_hp_bar(current, max_hp, width=20):
            if max_hp <= 0:
                return "░" * width
            filled = int((current / max_hp) * width)
            return "█" * filled + "░" * (width - filled)
        
        wild_bar = get_hp_bar(wild_pokemon.current_hp, wild_pokemon.max_hp)
        player_bar = get_hp_bar(player_pokemon.current_hp, player_pokemon.max_hp)
        
        # Build message
        text = f"""
⚔️ WILD {wild_pokemon.species_name.upper()} [{wild_types_str}]
Lv. {wild_pokemon.level} • HP {wild_pokemon.current_hp}/{wild_pokemon.max_hp}
{wild_bar}

═════════════════════════════════

Your {player_pokemon.nickname.upper()} [{player_types_str}]
Lv. {player_pokemon.level} • HP {player_pokemon.current_hp}/{player_pokemon.max_hp}
{player_bar}

═════════════════════════════════

📚 AVAILABLE MOVES:
"""
        
        # Get move data
        try:
            from moves_database import get_move_data
            
            for i, move_name in enumerate(moves[:4], 1):
                move_data = get_move_data(move_name)
                type_emoji = get_type_emoji(move_data["type"])
                text += f"\n{i}. {type_emoji} {move_name.upper()}"
                text += f" | Power: {move_data['power']} | Acc: {move_data['accuracy']}%"
        except:
            # Fallback without move data
            for i, move_name in enumerate(moves[:4], 1):
                text += f"\n{i}. {move_name.upper()}"
        
        return text
    
    except Exception as e:
        return f"⚔️ BATTLE IN PROGRESS\n\nError: {str(e)[:50]}"

def get_type_emoji(ptype: str) -> str:
    """Get emoji for Pokemon type"""
    emojis = {
        "normal": "⚪", "fire": "🔥", "water": "💧", "grass": "🌿",
        "electric": "⚡", "ice": "❄️", "fighting": "👊", "poison": "☠️",
        "ground": "🌍", "flying": "🦅", "psychic": "🧠", "bug": "🐛",
        "rock": "🪨", "ghost": "👻", "dragon": "🐉", "dark": "🌑",
        "steel": "⚙️", "fairy": "✨"
    }
    return emojis.get(ptype.lower(), "⚪")

def get_battle_move_buttons(moves: List[str]) -> List[List]:
    """
    Get battle move buttons
    Shows up to 4 moves + special buttons
    """
    buttons = []
    
    # Move buttons (2 per row)
    for i in range(0, min(4, len(moves)), 2):
        row = []
        
        # First move
        move1 = moves[i]
        row.append(InlineKeyboardButton(f"{i+1}️⃣ {move1.upper()}", 
                                       callback_data=f"use_move_{i}"))
        
        # Second move (if exists)
        if i + 1 < len(moves):
            move2 = moves[i + 1]
            row.append(InlineKeyboardButton(f"{i+2}️⃣ {move2.upper()}", 
                                           callback_data=f"use_move_{i+1}"))
        
        buttons.append(row)
    
    # Action buttons
    buttons.append([
        InlineKeyboardButton("🔴 Pokéballs", callback_data="catch_pokeball"),
        InlineKeyboardButton("🏃 Flee", callback_data="battle_run")
    ])
    
    return buttons

def get_catch_buttons() -> List[List]:
    """Get pokéball selection buttons after winning battle"""
    buttons = [[
        InlineKeyboardButton("🔴 Pokéball", callback_data="catch_pokeball"),
        InlineKeyboardButton("🔵 Great Ball", callback_data="catch_greatball"),
    ], [
        InlineKeyboardButton("🟣 Ultra Ball", callback_data="catch_ultraball"),
        InlineKeyboardButton("❌ Skip", callback_data="show_menu")
    ]]
    return buttons

def format_catch_result(success: bool, pokemon, ball_type: str, 
                       reward_coins: int) -> str:
    """Format catch result message"""
    if success:
        return f"""✅ CAUGHT!

🎉 {pokemon.species_name} Lv{pokemon.level} caught!
💰 +{reward_coins}₽ earned!

Added to your collection!"""
    else:
        return f"""❌ FAILED!

{pokemon.species_name} broke free from the {ball_type}!
Try a different pokéball or weaken it more."""

# ════════════════════════════════════════════════════════════════
# MOVE LEARNING NOTIFICATION UI
# ════════════════════════════════════════════════════════════════

def format_level_up_message(pokemon, old_level: int, new_level: int, 
                           new_moves: List[str]) -> str:
    """Format level up notification"""
    try:
        from moves_database import get_move_data
        
        message = f"""🎉 LEVEL UP!

{pokemon.nickname} grew to Lv{new_level}!
⭐ +{(new_level - old_level) * 10} XP
"""
        
        if new_moves:
            message += f"\n✨ Learned new move"
            if len(new_moves) == 1:
                move_data = get_move_data(new_moves[0])
                message += f":\n\n{new_moves[0].upper()}"
                message += f"\nPower: {move_data['power']}"
                message += f" | Accuracy: {move_data['accuracy']}%"
                message += f"\nType: {move_data['type'].upper()}"
            else:
                message += "s:\n"
                for move in new_moves[:3]:
                    message += f"\n• {move.upper()}"
        else:
            message += "\nNo new moves at this level."
        
        return message
    
    except Exception as e:
        return f"🎉 {pokemon.nickname} grew to Lv{new_level}!"

def get_move_choice_buttons(moves: List[str]) -> List[List]:
    """Get buttons for choosing which move to learn"""
    buttons = []
    
    for i, move in enumerate(moves, 1):
        buttons.append([InlineKeyboardButton(
            f"{i}️⃣ {move.upper()}",
            callback_data=f"learn_move_{move.lower()}"
        )])
    
    buttons.append([InlineKeyboardButton("⬅️ Cancel", callback_data="show_menu")])
    
    return buttons

# ════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("UI Components Loaded ✅\n")
    
    # Test 1: Starter buttons
    print("Starter Buttons:")
    print(get_starter_buttons())
    print()
    
    # Test 2: Starter message
    print("Starter Message:")
    print(get_starter_message())

