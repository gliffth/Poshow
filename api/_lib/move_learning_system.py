"""
⚡ POSHOW - POKEMON MOVE LEARNING SYSTEM
Handles which moves Pokemon learn at which levels
Based on official Pokemon data with balanced progression
"""

from typing import List, Dict, Tuple

# ════════════════════════════════════════════════════════════════
# MOVE LEARNING DATABASE
# Pokemon -> [(Level, Move), ...]
# ════════════════════════════════════════════════════════════════

POKEMON_MOVE_POOLS = {
    # STARTER POKEMON - BULBASAUR LINE
    "bulbasaur": [
        (1, "tackle"),           # Start with basic attack
        (1, "growl"),            # Start with stat drop
        (7, "leech-seed"),       # Grass move - early healing
        (13, "vine-whip"),       # Grass damage move
        (19, "razor-leaf"),      # Stronger grass move
        (25, "growth"),          # Stat boost
        (31, "synthesis"),       # Healing move
        (37, "solar-beam"),      # Ultimate grass move
        (43, "worry-seed"),
        (49, "double-edge"),
    ],
    
    "ivysaur": [
        (1, "tackle"),
        (1, "growl"),
        (7, "leech-seed"),
        (13, "vine-whip"),
        (19, "razor-leaf"),
        (25, "growth"),
        (31, "synthesis"),
        (37, "solar-beam"),
        (43, "worry-seed"),
        (49, "double-edge"),
    ],
    
    "venusaur": [
        (1, "tackle"),
        (1, "growl"),
        (7, "leech-seed"),
        (13, "vine-whip"),
        (19, "razor-leaf"),
        (25, "growth"),
        (31, "synthesis"),
        (37, "solar-beam"),
        (43, "worry-seed"),
        (49, "double-edge"),
    ],
    
    # STARTER POKEMON - CHARMANDER LINE
    "charmander": [
        (1, "scratch"),          # Start: physical attack
        (1, "growl"),            # Start: defense drop
        (7, "ember"),            # Lvl 7: fire damage
        (13, "smokescreen"),     # Lvl 13: accuracy drop
        (19, "dragon-rage"),     # Lvl 19: dragon move
        (25, "scary-face"),      # Lvl 25: speed drop
        (31, "fire-fang"),       # Lvl 31: powerful fire
        (37, "flamethrower"),    # Lvl 37: ultimate fire
        (43, "slash"),           # Lvl 43: crit move
        (49, "dragon-claw"),     # Lvl 49: dragon claw
    ],
    
    "charmeleon": [
        (1, "scratch"),
        (1, "growl"),
        (7, "ember"),
        (13, "smokescreen"),
        (19, "dragon-rage"),
        (25, "scary-face"),
        (31, "fire-fang"),
        (37, "flamethrower"),
        (43, "slash"),
        (49, "dragon-claw"),
    ],
    
    "charizard": [
        (1, "scratch"),
        (1, "growl"),
        (7, "ember"),
        (13, "smokescreen"),
        (19, "dragon-rage"),
        (25, "scary-face"),
        (31, "fire-fang"),
        (37, "flamethrower"),
        (43, "slash"),
        (49, "dragon-claw"),
    ],
    
    # STARTER POKEMON - SQUIRTLE LINE
    "squirtle": [
        (1, "tackle"),           # Start: basic attack
        (1, "tail-whip"),        # Start: defense drop
        (7, "water-gun"),        # Lvl 7: water damage
        (13, "withdraw"),        # Lvl 13: defense boost
        (19, "bubble-beam"),     # Lvl 19: water attack
        (25, "bite"),            # Lvl 25: dark physical
        (31, "protect"),         # Lvl 31: defense
        (37, "hydro-pump"),      # Lvl 37: ultimate water
        (43, "iron-defense"),    # Lvl 43: defense boost
        (49, "aqua-tail"),       # Lvl 49: water physical
    ],
    
    "wartortle": [
        (1, "tackle"),
        (1, "tail-whip"),
        (7, "water-gun"),
        (13, "withdraw"),
        (19, "bubble-beam"),
        (25, "bite"),
        (31, "protect"),
        (37, "hydro-pump"),
        (43, "iron-defense"),
        (49, "aqua-tail"),
    ],
    
    "blastoise": [
        (1, "tackle"),
        (1, "tail-whip"),
        (7, "water-gun"),
        (13, "withdraw"),
        (19, "bubble-beam"),
        (25, "bite"),
        (31, "protect"),
        (37, "hydro-pump"),
        (43, "iron-defense"),
        (49, "aqua-tail"),
    ],
    
    # COMMON EARLY GAME POKEMON
    "pidgeot": [
        (1, "tackle"),
        (1, "sand-attack"),
        (5, "peck"),
        (9, "brave-bird"),
        (13, "wing-attack"),
        (17, "air-slash"),
        (25, "whirlwind"),
    ],
    
    "pikachu": [
        (1, "thunderbolt"),
        (1, "thunder-wave"),
        (7, "thundershock"),
        (13, "thunder-punch"),
        (19, "thunder-lock"),
        (25, "volt-switch"),
    ],
    
    "metang": [
        (1, "tackle"),
        (1, "metal-claw"),
        (9, "iron-defense"),
        (17, "flash-cannon"),
        (25, "meteor-mash"),
        (33, "iron-head"),
    ],
}

# ════════════════════════════════════════════════════════════════
# MOVE DATA (Power, Accuracy, Type, Category)
# ════════════════════════════════════════════════════════════════

MOVE_DATA = {
    # LEVEL 1-7 MOVES (Starter moves - WEAK)
    "tackle": {"power": 40, "accuracy": 100, "type": "normal", "category": "physical", "desc": "Basic tackle attack"},
    "scratch": {"power": 40, "accuracy": 100, "type": "normal", "category": "physical", "desc": "Scratch with claws"},
    "growl": {"power": 0, "accuracy": 100, "type": "normal", "category": "status", "desc": "Lower opponent ATK"},
    "tail-whip": {"power": 0, "accuracy": 100, "type": "normal", "category": "status", "desc": "Lower opponent DEF"},
    "sand-attack": {"power": 0, "accuracy": 100, "type": "ground", "category": "status", "desc": "Lower opponent ACC"},
    "leech-seed": {"power": 0, "accuracy": 90, "type": "grass", "category": "status", "desc": "Drain HP each turn"},
    
    # LEVEL 7-13 MOVES (Early game - WEAK TO MEDIUM)
    "ember": {"power": 40, "accuracy": 100, "type": "fire", "category": "special", "desc": "Fire attack with burn chance"},
    "water-gun": {"power": 40, "accuracy": 100, "type": "water", "category": "special", "desc": "Water spray attack"},
    "vine-whip": {"power": 45, "accuracy": 100, "type": "grass", "category": "physical", "desc": "Whip with vines"},
    "peck": {"power": 35, "accuracy": 100, "type": "flying", "category": "physical", "desc": "Peck at opponent"},
    "smokescreen": {"power": 0, "accuracy": 100, "type": "normal", "category": "status", "desc": "Lower opponent ACC"},
    "withdraw": {"power": 0, "accuracy": 100, "type": "water", "category": "status", "desc": "Raise own DEF"},
    
    # LEVEL 13-19 MOVES (Mid game - MEDIUM)
    "razor-leaf": {"power": 55, "accuracy": 95, "type": "grass", "category": "physical", "desc": "Sharp leaves attack"},
    "dragon-rage": {"power": 40, "accuracy": 100, "type": "dragon", "category": "special", "desc": "Dragon breath attack"},
    "bubble-beam": {"power": 65, "accuracy": 100, "type": "water", "category": "special", "desc": "Bubble stream attack"},
    "wing-attack": {"power": 60, "accuracy": 100, "type": "flying", "category": "physical", "desc": "Wing strike"},
    "thundershock": {"power": 40, "accuracy": 100, "type": "electric", "category": "special", "desc": "Electric shock"},
    
    # LEVEL 19-25 MOVES (Late mid game - MEDIUM TO STRONG)
    "growth": {"power": 0, "accuracy": 100, "type": "grass", "category": "status", "desc": "Raise own SP.ATK"},
    "bite": {"power": 60, "accuracy": 100, "type": "dark", "category": "physical", "desc": "Bite attack with flinch"},
    "scary-face": {"power": 0, "accuracy": 100, "type": "normal", "category": "status", "desc": "Sharply lower SPEED"},
    "protect": {"power": 0, "accuracy": 100, "type": "normal", "category": "status", "desc": "Prevent damage this turn"},
    "metal-claw": {"power": 50, "accuracy": 95, "type": "steel", "category": "physical", "desc": "Metal claw strike"},
    
    # LEVEL 25-31 MOVES (Strong - MEDIUM TO STRONG)
    "synthesis": {"power": 0, "accuracy": 100, "type": "grass", "category": "status", "desc": "Heal 50% max HP"},
    "fire-fang": {"power": 65, "accuracy": 95, "type": "fire", "category": "physical", "desc": "Bite with burn chance"},
    "thunder-punch": {"power": 75, "accuracy": 100, "type": "electric", "category": "physical", "desc": "Electric punch"},
    "slash": {"power": 70, "accuracy": 100, "type": "normal", "category": "physical", "desc": "Slash attack, high crit"},
    "air-slash": {"power": 75, "accuracy": 95, "type": "flying", "category": "special", "desc": "Air blade, may flinch"},
    "iron-defense": {"power": 0, "accuracy": 100, "type": "steel", "category": "status", "desc": "Sharply raise DEF"},
    
    # LEVEL 31-37 MOVES (STRONG)
    "solar-beam": {"power": 120, "accuracy": 100, "type": "grass", "category": "special", "desc": "Ultimate grass attack"},
    "flamethrower": {"power": 90, "accuracy": 100, "type": "fire", "category": "special", "desc": "Flame attack"},
    "hydro-pump": {"power": 110, "accuracy": 80, "type": "water", "category": "special", "desc": "Ultimate water attack"},
    "brave-bird": {"power": 120, "accuracy": 100, "type": "flying", "category": "physical", "desc": "Reckless flying attack"},
    "whirlwind": {"power": 0, "accuracy": 100, "type": "flying", "category": "status", "desc": "Force opponent out"},
    "flash-cannon": {"power": 80, "accuracy": 100, "type": "steel", "category": "special", "desc": "Steel beam attack"},
    "thunder-wave": {"power": 0, "accuracy": 90, "type": "electric", "category": "status", "desc": "Paralyze opponent"},
    
    # LEVEL 37-43 MOVES (VERY STRONG)
    "worry-seed": {"power": 0, "accuracy": 100, "type": "grass", "category": "status", "desc": "Change ability"},
    "iron-head": {"power": 80, "accuracy": 100, "type": "steel", "category": "physical", "desc": "Steel head strike"},
    "volt-switch": {"power": 70, "accuracy": 100, "type": "electric", "category": "special", "desc": "Electric hit, switch out"},
    "meteor-mash": {"power": 90, "accuracy": 90, "type": "steel", "category": "physical", "desc": "Meteor strike"},
    
    # LEVEL 43-49 MOVES (ULTIMATE)
    "double-edge": {"power": 120, "accuracy": 100, "type": "normal", "category": "physical", "desc": "Risky powerful move"},
    "dragon-claw": {"power": 80, "accuracy": 100, "type": "dragon", "category": "physical", "desc": "Dragon claw strike"},
    "aqua-tail": {"power": 90, "accuracy": 90, "type": "water", "category": "physical", "desc": "Tail water attack"},
    "thunderbolt": {"power": 90, "accuracy": 100, "type": "electric", "category": "special", "desc": "Powerful electric attack"},
    "thunder-lock": {"power": 0, "accuracy": 100, "type": "electric", "category": "status", "desc": "Lock in move"},
}

# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════

def get_moves_by_level(pokemon_name: str, current_level: int) -> List[str]:
    """
    Get all moves a Pokemon can learn up to current level
    
    Args:
        pokemon_name: Pokemon species name
        current_level: Current Pokemon level
    
    Returns:
        List of move names the Pokemon knows
    """
    pokemon_name = pokemon_name.lower()
    
    if pokemon_name not in POKEMON_MOVE_POOLS:
        return ["tackle"]  # Fallback
    
    moves = []
    move_pool = POKEMON_MOVE_POOLS[pokemon_name]
    
    for level, move in move_pool:
        if level <= current_level:
            if move not in moves:  # Avoid duplicates
                moves.append(move)
    
    # Return max 4 moves (latest 4)
    return moves[-4:] if len(moves) > 4 else moves

def get_new_moves_at_level(pokemon_name: str, new_level: int, old_level: int) -> List[str]:
    """
    Get moves a Pokemon learns when leveling up
    
    Args:
        pokemon_name: Pokemon species name
        new_level: New level after level up
        old_level: Previous level
    
    Returns:
        List of new moves learned
    """
    pokemon_name = pokemon_name.lower()
    
    if pokemon_name not in POKEMON_MOVE_POOLS:
        return []
    
    new_moves = []
    move_pool = POKEMON_MOVE_POOLS[pokemon_name]
    
    for level, move in move_pool:
        if old_level < level <= new_level:
            if move not in new_moves:
                new_moves.append(move)
    
    return new_moves

def get_move_info(move_name: str) -> Dict:
    """
    Get move data
    
    Args:
        move_name: Move name
    
    Returns:
        Move data dict
    """
    move_name = move_name.lower().replace(" ", "-")
    
    if move_name in MOVE_DATA:
        return MOVE_DATA[move_name]
    
    # Fallback
    return {
        "power": 40,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "desc": "Unknown move"
    }

def get_move_difficulty(move_name: str) -> str:
    """
    Get difficulty tier of a move
    
    Args:
        move_name: Move name
    
    Returns:
        Tier: "starter", "early", "mid", "strong", "ultimate"
    """
    move_name = move_name.lower().replace(" ", "-")
    
    # Find level where move is first learned
    for pokemon, moves in POKEMON_MOVE_POOLS.items():
        for level, move in moves:
            if move == move_name:
                if level <= 7:
                    return "starter"
                elif level <= 13:
                    return "early"
                elif level <= 25:
                    return "mid"
                elif level <= 37:
                    return "strong"
                else:
                    return "ultimate"
    
    return "unknown"

def format_move_pool(pokemon_name: str, current_level: int) -> str:
    """
    Format move pool for display
    
    Args:
        pokemon_name: Pokemon species name
        current_level: Current level
    
    Returns:
        Formatted string
    """
    moves = get_moves_by_level(pokemon_name, current_level)
    
    text = "📚 MOVES:\n\n"
    for i, move in enumerate(moves, 1):
        move_info = get_move_info(move)
        text += f"{i}. {move.upper()}\n"
        text += f"   Power: {move_info['power']} | Acc: {move_info['accuracy']}%\n"
        text += f"   Type: {move_info['type'].upper()}\n"
        text += f"   {move_info['desc']}\n\n"
    
    return text

# ════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing Move Learning System...\n")
    
    # Test 1: Charmander at level 5
    print("🔥 Charmander Lv5:")
    moves = get_moves_by_level("charmander", 5)
    print(f"Moves: {moves}\n")
    
    # Test 2: Charmander leveling up from 5 to 7
    print("🔥 Charmander Lv5 → Lv7:")
    new_moves = get_new_moves_at_level("charmander", 7, 5)
    print(f"New Moves Learned: {new_moves}\n")
    
    # Test 3: Charmander at level 25
    print("🔥 Charmander Lv25:")
    moves = get_moves_by_level("charmander", 25)
    print(f"Moves: {moves}\n")
    
    # Test 4: Move info
    print("🔥 Ember Move Info:")
    info = get_move_info("ember")
    print(f"{info}\n")
    
    # Test 5: Format move pool
    print("🔥 Charmander Lv13 Move Pool:")
    print(format_move_pool("charmander", 13))

