"""
⚡ POSHOW - ADVANCED MOVES DATABASE v2
Complete move data with power, accuracy, type, category, and type effectiveness
Includes move compatibility with different Pokemon types
"""

# ════════════════════════════════════════════════════════════════
# TYPE EFFECTIVENESS CHART
# ════════════════════════════════════════════════════════════════

TYPE_EFFECTIVENESS = {
    "normal": {
        "strong_against": [],
        "weak_against": ["rock", "steel"],
        "resistant_to": [],
        "vulnerable_to": ["fighting"],
    },
    "fire": {
        "strong_against": ["grass", "ice", "bug", "steel"],
        "weak_against": ["water", "ground", "rock"],
        "resistant_to": ["grass", "ice", "bug", "steel", "fairy"],
        "vulnerable_to": ["water", "ground", "rock"],
    },
    "water": {
        "strong_against": ["fire", "ground", "rock"],
        "weak_against": ["grass", "electric"],
        "resistant_to": ["steel", "fire", "water", "ice"],
        "vulnerable_to": ["grass", "electric"],
    },
    "grass": {
        "strong_against": ["water", "ground", "rock"],
        "weak_against": ["fire", "ice", "poison", "flying", "bug"],
        "resistant_to": ["ground", "water", "grass", "electric"],
        "vulnerable_to": ["fire", "ice", "poison", "flying", "bug"],
    },
    "electric": {
        "strong_against": ["water", "flying"],
        "weak_against": ["ground"],
        "resistant_to": ["flying", "steel", "electric"],
        "vulnerable_to": ["ground"],
    },
    "ice": {
        "strong_against": ["flying", "ground", "grass", "dragon"],
        "weak_against": ["fire", "fighting", "rock", "steel"],
        "resistant_to": ["ice"],
        "vulnerable_to": ["fire", "fighting", "rock", "steel"],
    },
    "fighting": {
        "strong_against": ["normal", "ice", "rock", "dark", "steel"],
        "weak_against": ["flying", "psychic", "fairy"],
        "resistant_to": ["rock", "bug", "dark"],
        "vulnerable_to": ["flying", "psychic", "fairy"],
    },
    "poison": {
        "strong_against": ["grass", "fairy"],
        "weak_against": ["ground", "psychic"],
        "resistant_to": ["fighting", "poison", "bug", "grass"],
        "vulnerable_to": ["ground", "psychic"],
    },
    "ground": {
        "strong_against": ["fire", "electric", "poison", "rock", "steel"],
        "weak_against": ["water", "grass", "ice"],
        "resistant_to": ["poison", "rock"],
        "vulnerable_to": ["water", "grass", "ice"],
    },
    "flying": {
        "strong_against": ["fighting", "bug", "grass"],
        "weak_against": ["electric", "ice", "rock"],
        "resistant_to": ["fighting", "bug", "grass"],
        "vulnerable_to": ["electric", "ice", "rock"],
    },
    "psychic": {
        "strong_against": ["fighting", "poison"],
        "weak_against": ["bug", "ghost", "dark"],
        "resistant_to": ["fighting", "psychic"],
        "vulnerable_to": ["bug", "ghost", "dark"],
    },
    "bug": {
        "strong_against": ["grass", "psychic", "dark"],
        "weak_against": ["fire", "flying", "rock"],
        "resistant_to": ["fighting", "ground", "grass"],
        "vulnerable_to": ["fire", "flying", "rock"],
    },
    "rock": {
        "strong_against": ["flying", "bug", "fire", "ice"],
        "weak_against": ["water", "grass", "fighting", "ground", "steel"],
        "resistant_to": ["normal", "flying", "poison", "fire"],
        "vulnerable_to": ["water", "grass", "fighting", "ground", "steel"],
    },
    "ghost": {
        "strong_against": ["ghost", "psychic"],
        "weak_against": ["ghost", "dark"],
        "resistant_to": ["poison", "bug"],
        "vulnerable_to": ["ghost", "dark"],
    },
    "dragon": {
        "strong_against": ["dragon"],
        "weak_against": ["ice", "dragon", "fairy"],
        "resistant_to": ["fire", "water", "grass", "electric"],
        "vulnerable_to": ["ice", "dragon", "fairy"],
    },
    "dark": {
        "strong_against": ["ghost", "psychic"],
        "weak_against": ["fighting", "bug", "fairy"],
        "resistant_to": ["ghost", "dark"],
        "vulnerable_to": ["fighting", "bug", "fairy"],
    },
    "steel": {
        "strong_against": ["ice", "rock", "fairy"],
        "weak_against": ["fire", "water", "ground"],
        "resistant_to": ["normal", "flying", "rock", "bug", "steel", "grass", "psychic", "ice", "dragon", "fairy"],
        "vulnerable_to": ["fire", "water", "ground"],
    },
    "fairy": {
        "strong_against": ["fighting", "bug", "dark"],
        "weak_against": ["poison", "steel"],
        "resistant_to": ["fighting", "bug", "dark"],
        "vulnerable_to": ["poison", "steel"],
    },
}

# ════════════════════════════════════════════════════════════════
# POKEMON TYPE MOVE POOL (Which moves can Pokemon learn)
# ════════════════════════════════════════════════════════════════

POKEMON_TYPE_MOVES = {
    "normal": [
        "tackle", "scratch", "pound", "take-down", "double-kick", "horn-attack",
        "fury-attack", "stomp", "tail-whip", "quick-attack", "rage", "swift",
        "fury-swipes", "tackle", "false-swipe", "aqua-tail", "bounce", "facade",
    ],
    "fire": [
        "ember", "flamethrower", "fire-punch", "fire-blast", "flame-charge",
        "heat-wave", "incinerate", "scald", "will-o-wisp", "inferno",
    ],
    "water": [
        "water-gun", "hydro-pump", "aqua-jet", "surf", "waterfall", "brine",
        "bubble-beam", "hydro-cannon", "scald", "aqua-ring", "aqua-tail",
    ],
    "grass": [
        "vine-whip", "razor-leaf", "solar-beam", "leaf-blade", "synthesis",
        "growth", "leech-seed", "mega-drain", "giga-drain", "bullet-seed",
    ],
    "electric": [
        "thunderbolt", "thunder-punch", "thunder-wave", "thundershock",
        "thunder-lock", "charge-beam", "electro-ball", "power-gem", "volt-switch",
    ],
    "ice": [
        "ice-beam", "ice-punch", "blizzard", "icy-wind", "avalanche",
        "ice-shard", "aurora-beam", "frost-breath", "powder-snow",
    ],
    "fighting": [
        "punch", "kick", "strength", "submission", "seismic-toss", "dynamic-punch",
        "focus-blast", "mach-punch", "vital-throw", "superpower", "close-combat",
    ],
    "poison": [
        "poison-powder", "poison-gas", "toxic-spikes", "sludge-bomb", "toxic",
        "sludge-wave", "poison-jab", "cross-poison", "sludge-wave",
    ],
    "ground": [
        "earthquake", "dig", "sand-attack", "sandstorm", "sand-tomb",
        "earth-power", "magnitude", "mud-bomb", "mud-shot", "muddy-water",
    ],
    "flying": [
        "peck", "brave-bird", "wing-attack", "aerial-ace", "air-cutter",
        "air-slash", "fly", "tailwind", "acrobatics", "gust", "whirlwind",
    ],
    "psychic": [
        "psychic", "psybeam", "confusion", "light-screen", "reflect",
        "teleport", "zen-headbutt", "psycho-cut", "wonder-room", "trick-room",
    ],
    "bug": [
        "bug-bite", "x-scissor", "signal-beam", "infestation", "struggle-bug",
        "megahorn", "pin-missile", "fury-cutter", "leech-life", "spider-web",
    ],
    "rock": [
        "stone-edge", "rock-slide", "rock-throw", "ancient-power", "power-gem",
        "sandstorm", "stealth-rock", "rock-tomb", "head-smash", "smack-down",
    ],
    "ghost": [
        "shadow-ball", "shadow-claw", "shadow-force", "hex", "astonish",
        "night-shade", "phantom-force", "shadow-sneak", "poltergeist",
    ],
    "dragon": [
        "dragon-claw", "dragon-pulse", "dragon-breath", "outrage", "dragon-dance",
        "dragon-rush", "dragon-tail", "draco-meteor", "scale-shot", "core-enforcer",
    ],
    "dark": [
        "dark-pulse", "crunch", "night-slash", "bite", "dark-void", "sucker-punch",
        "brutal-swing", "foul-play", "dark-cleave", "knock-off",
    ],
    "steel": [
        "iron-head", "flash-cannon", "iron-tail", "bullet-punch", "autotomize",
        "metal-claw", "steel-wing", "gear-grind", "heavy-slam", "iron-defense",
    ],
    "fairy": [
        "play-rough", "moonblast", "dazzling-gleam", "fairy-wind", "disarming-voice",
        "charm", "sweet-kiss", "fairy-lock", "geomancy", "aromatic-mist",
    ],
}

# ════════════════════════════════════════════════════════════════
# COMPLETE MOVES DATABASE
# ════════════════════════════════════════════════════════════════

MOVES_DATABASE = {
    # NORMAL MOVES
    "tackle": {
        "power": 40,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Standard attack",
    },
    "scratch": {
        "power": 40,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Standard attack",
    },
    "pound": {
        "power": 40,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Standard attack",
    },
    "take-down": {
        "power": 90,
        "accuracy": 85,
        "type": "normal",
        "category": "physical",
        "effect": "User takes recoil damage",
    },
    "double-kick": {
        "power": 30,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Hits twice",
    },
    "horn-attack": {
        "power": 65,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Standard attack",
    },
    "fury-attack": {
        "power": 15,
        "accuracy": 85,
        "type": "normal",
        "category": "physical",
        "effect": "Hits 2-5 times",
    },
    "stomp": {
        "power": 65,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "May paralyze",
    },
    "tail-whip": {
        "power": 0,
        "accuracy": 100,
        "type": "normal",
        "category": "status",
        "effect": "Lowers defense",
    },
    "quick-attack": {
        "power": 40,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Always goes first",
    },
    "swift": {
        "power": 60,
        "accuracy": "inf",
        "type": "normal",
        "category": "special",
        "effect": "Never misses",
    },
    "fury-swipes": {
        "power": 18,
        "accuracy": 80,
        "type": "normal",
        "category": "physical",
        "effect": "Hits 2-5 times",
    },
    "false-swipe": {
        "power": 40,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Never KOs",
    },
    "bounce": {
        "power": 85,
        "accuracy": 85,
        "type": "normal",
        "category": "physical",
        "effect": "May paralyze",
    },
    "facade": {
        "power": 70,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Power doubles if burned/poisoned/paralyzed",
    },
    
    # FIRE MOVES
    "ember": {
        "power": 40,
        "accuracy": 100,
        "type": "fire",
        "category": "special",
        "effect": "10% burn",
    },
    "flamethrower": {
        "power": 90,
        "accuracy": 100,
        "type": "fire",
        "category": "special",
        "effect": "10% burn",
    },
    "fire-punch": {
        "power": 75,
        "accuracy": 100,
        "type": "fire",
        "category": "physical",
        "effect": "10% burn",
    },
    "fire-blast": {
        "power": 110,
        "accuracy": 85,
        "type": "fire",
        "category": "special",
        "effect": "10% burn",
    },
    "flame-charge": {
        "power": 50,
        "accuracy": 100,
        "type": "fire",
        "category": "physical",
        "effect": "Boosts speed",
    },
    "heat-wave": {
        "power": 95,
        "accuracy": 90,
        "type": "fire",
        "category": "special",
        "effect": "10% burn",
    },
    "incinerate": {
        "power": 60,
        "accuracy": 100,
        "type": "fire",
        "category": "special",
        "effect": "Destroys items",
    },
    "scald": {
        "power": 80,
        "accuracy": 100,
        "type": "water",  # Wait, scald is water-type!
        "category": "special",
        "effect": "30% burn",
    },
    
    # WATER MOVES
    "water-gun": {
        "power": 40,
        "accuracy": 100,
        "type": "water",
        "category": "special",
        "effect": "Standard attack",
    },
    "hydro-pump": {
        "power": 110,
        "accuracy": 80,
        "type": "water",
        "category": "special",
        "effect": "Standard attack",
    },
    "aqua-jet": {
        "power": 60,
        "accuracy": 100,
        "type": "water",
        "category": "physical",
        "effect": "Always goes first",
    },
    "surf": {
        "power": 90,
        "accuracy": 100,
        "type": "water",
        "category": "special",
        "effect": "Standard attack",
    },
    "waterfall": {
        "power": 80,
        "accuracy": 100,
        "type": "water",
        "category": "physical",
        "effect": "May paralyze",
    },
    "brine": {
        "power": 65,
        "accuracy": 100,
        "type": "water",
        "category": "special",
        "effect": "Double damage if low HP",
    },
    "bubble-beam": {
        "power": 65,
        "accuracy": 100,
        "type": "water",
        "category": "special",
        "effect": "May lower speed",
    },
    "hydro-cannon": {
        "power": 150,
        "accuracy": 90,
        "type": "water",
        "category": "special",
        "effect": "Must recharge",
    },
    "aqua-ring": {
        "power": 0,
        "accuracy": "inf",
        "type": "water",
        "category": "status",
        "effect": "Heals each turn",
    },
    "aqua-tail": {
        "power": 90,
        "accuracy": 90,
        "type": "water",
        "category": "physical",
        "effect": "Standard attack",
    },
    
    # GRASS MOVES
    "vine-whip": {
        "power": 45,
        "accuracy": 100,
        "type": "grass",
        "category": "physical",
        "effect": "Standard attack",
    },
    "razor-leaf": {
        "power": 55,
        "accuracy": 95,
        "type": "grass",
        "category": "physical",
        "effect": "High crit ratio",
    },
    "solar-beam": {
        "power": 120,
        "accuracy": 100,
        "type": "grass",
        "category": "special",
        "effect": "Charges first turn",
    },
    "leaf-blade": {
        "power": 90,
        "accuracy": 100,
        "type": "grass",
        "category": "physical",
        "effect": "High crit ratio",
    },
    "synthesis": {
        "power": 0,
        "accuracy": "inf",
        "type": "grass",
        "category": "status",
        "effect": "Heals user",
    },
    "growth": {
        "power": 0,
        "accuracy": "inf",
        "type": "grass",
        "category": "status",
        "effect": "Boosts special attack",
    },
    "leech-seed": {
        "power": 0,
        "accuracy": 90,
        "type": "grass",
        "category": "status",
        "effect": "Drains HP",
    },
    "mega-drain": {
        "power": 40,
        "accuracy": 100,
        "type": "grass",
        "category": "special",
        "effect": "Drains 50% damage",
    },
    "giga-drain": {
        "power": 75,
        "accuracy": 100,
        "type": "grass",
        "category": "special",
        "effect": "Drains 50% damage",
    },
    "bullet-seed": {
        "power": 25,
        "accuracy": 100,
        "type": "grass",
        "category": "physical",
        "effect": "Hits 2-5 times",
    },
    
    # ELECTRIC MOVES
    "thunderbolt": {
        "power": 90,
        "accuracy": 100,
        "type": "electric",
        "category": "special",
        "effect": "10% paralyze",
    },
    "thunder-punch": {
        "power": 75,
        "accuracy": 100,
        "type": "electric",
        "category": "physical",
        "effect": "10% paralyze",
    },
    "thunder-wave": {
        "power": 0,
        "accuracy": 90,
        "type": "electric",
        "category": "status",
        "effect": "Paralyzes",
    },
    "thundershock": {
        "power": 40,
        "accuracy": 100,
        "type": "electric",
        "category": "special",
        "effect": "10% paralyze",
    },
    "charge-beam": {
        "power": 50,
        "accuracy": 90,
        "type": "electric",
        "category": "special",
        "effect": "May boost sp.atk",
    },
    "electro-ball": {
        "power": 0,
        "accuracy": 100,
        "type": "electric",
        "category": "special",
        "effect": "Power varies by speed",
    },
    "volt-switch": {
        "power": 70,
        "accuracy": 100,
        "type": "electric",
        "category": "special",
        "effect": "User switches out",
    },
    
    # ICE MOVES
    "ice-beam": {
        "power": 90,
        "accuracy": 100,
        "type": "ice",
        "category": "special",
        "effect": "10% freeze",
    },
    "ice-punch": {
        "power": 75,
        "accuracy": 100,
        "type": "ice",
        "category": "physical",
        "effect": "10% freeze",
    },
    "blizzard": {
        "power": 110,
        "accuracy": 70,
        "type": "ice",
        "category": "special",
        "effect": "10% freeze",
    },
    "icy-wind": {
        "power": 55,
        "accuracy": 95,
        "type": "ice",
        "category": "special",
        "effect": "Lowers speed",
    },
    "avalanche": {
        "power": 60,
        "accuracy": 100,
        "type": "ice",
        "category": "physical",
        "effect": "Power doubles if hit",
    },
    "ice-shard": {
        "power": 40,
        "accuracy": 100,
        "type": "ice",
        "category": "physical",
        "effect": "Always goes first",
    },
    "aurora-beam": {
        "power": 65,
        "accuracy": 100,
        "type": "ice",
        "category": "special",
        "effect": "May lower attack",
    },
    "frost-breath": {
        "power": 60,
        "accuracy": 90,
        "type": "ice",
        "category": "special",
        "effect": "High crit ratio",
    },
    "powder-snow": {
        "power": 40,
        "accuracy": 100,
        "type": "ice",
        "category": "special",
        "effect": "10% freeze",
    },
    
    # FIGHTING MOVES
    "strength": {
        "power": 80,
        "accuracy": 100,
        "type": "normal",  # Strength is Normal-type!
        "category": "physical",
        "effect": "Standard attack",
    },
    "submission": {
        "power": 80,
        "accuracy": 80,
        "type": "fighting",
        "category": "physical",
        "effect": "User takes recoil",
    },
    "seismic-toss": {
        "power": 0,
        "accuracy": 100,
        "type": "fighting",
        "category": "physical",
        "effect": "Damage = level",
    },
    "dynamic-punch": {
        "power": 100,
        "accuracy": 50,
        "type": "fighting",
        "category": "physical",
        "effect": "Confuses",
    },
    "focus-blast": {
        "power": 120,
        "accuracy": 70,
        "type": "fighting",
        "category": "special",
        "effect": "May lower sp.def",
    },
    "mach-punch": {
        "power": 40,
        "accuracy": 100,
        "type": "fighting",
        "category": "physical",
        "effect": "Always goes first",
    },
    "vital-throw": {
        "power": 70,
        "accuracy": "inf",
        "type": "fighting",
        "category": "physical",
        "effect": "Never misses, goes last",
    },
    "superpower": {
        "power": 120,
        "accuracy": 100,
        "type": "fighting",
        "category": "physical",
        "effect": "Lowers stats after",
    },
    "close-combat": {
        "power": 120,
        "accuracy": 100,
        "type": "fighting",
        "category": "physical",
        "effect": "Lowers defenses",
    },
    
    # POISON MOVES
    "poison-powder": {
        "power": 0,
        "accuracy": 75,
        "type": "poison",
        "category": "status",
        "effect": "Poisons target",
    },
    "poison-gas": {
        "power": 0,
        "accuracy": 90,
        "type": "poison",
        "category": "status",
        "effect": "Poisons target",
    },
    "sludge-bomb": {
        "power": 90,
        "accuracy": 100,
        "type": "poison",
        "category": "special",
        "effect": "30% poison",
    },
    "toxic": {
        "power": 0,
        "accuracy": 90,
        "type": "poison",
        "category": "status",
        "effect": "Badly poisons",
    },
    "sludge-wave": {
        "power": 95,
        "accuracy": 100,
        "type": "poison",
        "category": "special",
        "effect": "10% poison",
    },
    "poison-jab": {
        "power": 80,
        "accuracy": 100,
        "type": "poison",
        "category": "physical",
        "effect": "30% poison",
    },
    "cross-poison": {
        "power": 70,
        "accuracy": 100,
        "type": "poison",
        "category": "physical",
        "effect": "10% poison, high crit",
    },
    
    # GROUND MOVES
    "earthquake": {
        "power": 100,
        "accuracy": 100,
        "type": "ground",
        "category": "physical",
        "effect": "Hits all in battle",
    },
    "dig": {
        "power": 80,
        "accuracy": 100,
        "type": "ground",
        "category": "physical",
        "effect": "Digs first turn",
    },
    "sand-attack": {
        "power": 0,
        "accuracy": 100,
        "type": "ground",
        "category": "status",
        "effect": "Lowers accuracy",
    },
    "sandstorm": {
        "power": 0,
        "accuracy": "inf",
        "type": "rock",  # Sandstorm is Rock-type!
        "category": "status",
        "effect": "Weather damage",
    },
    "sand-tomb": {
        "power": 35,
        "accuracy": 85,
        "type": "ground",
        "category": "physical",
        "effect": "Traps target",
    },
    "earth-power": {
        "power": 90,
        "accuracy": 100,
        "type": "ground",
        "category": "special",
        "effect": "May lower sp.def",
    },
    "magnitude": {
        "power": 0,
        "accuracy": 100,
        "type": "ground",
        "category": "physical",
        "effect": "Power varies",
    },
    "mud-bomb": {
        "power": 65,
        "accuracy": 85,
        "type": "ground",
        "category": "special",
        "effect": "May lower accuracy",
    },
    "mud-shot": {
        "power": 55,
        "accuracy": 95,
        "type": "ground",
        "category": "special",
        "effect": "Lowers speed",
    },
    "muddy-water": {
        "power": 90,
        "accuracy": 85,
        "type": "water",  # Muddy Water is Water-type!
        "category": "special",
        "effect": "May lower accuracy",
    },
    
    # FLYING MOVES
    "peck": {
        "power": 35,
        "accuracy": 100,
        "type": "flying",
        "category": "physical",
        "effect": "Standard attack",
    },
    "brave-bird": {
        "power": 120,
        "accuracy": 100,
        "type": "flying",
        "category": "physical",
        "effect": "User takes recoil",
    },
    "wing-attack": {
        "power": 60,
        "accuracy": 100,
        "type": "flying",
        "category": "physical",
        "effect": "Standard attack",
    },
    "aerial-ace": {
        "power": 60,
        "accuracy": "inf",
        "type": "flying",
        "category": "physical",
        "effect": "Never misses",
    },
    "air-cutter": {
        "power": 60,
        "accuracy": 95,
        "type": "flying",
        "category": "special",
        "effect": "High crit ratio",
    },
    "air-slash": {
        "power": 75,
        "accuracy": 95,
        "type": "flying",
        "category": "special",
        "effect": "May flinch",
    },
    "fly": {
        "power": 90,
        "accuracy": 95,
        "type": "flying",
        "category": "physical",
        "effect": "Flies first turn",
    },
    "tailwind": {
        "power": 0,
        "accuracy": "inf",
        "type": "flying",
        "category": "status",
        "effect": "Boosts speed",
    },
    "acrobatics": {
        "power": 55,
        "accuracy": 100,
        "type": "flying",
        "category": "physical",
        "effect": "Power doubles if no item",
    },
    "gust": {
        "power": 40,
        "accuracy": 100,
        "type": "flying",
        "category": "special",
        "effect": "Standard attack",
    },
    
    # PSYCHIC MOVES
    "psychic": {
        "power": 90,
        "accuracy": 100,
        "type": "psychic",
        "category": "special",
        "effect": "May lower sp.def",
    },
    "psybeam": {
        "power": 65,
        "accuracy": 100,
        "type": "psychic",
        "category": "special",
        "effect": "May confuse",
    },
    "confusion": {
        "power": 50,
        "accuracy": 100,
        "type": "psychic",
        "category": "special",
        "effect": "May confuse",
    },
    "light-screen": {
        "power": 0,
        "accuracy": "inf",
        "type": "psychic",
        "category": "status",
        "effect": "Boosts defense",
    },
    "reflect": {
        "power": 0,
        "accuracy": "inf",
        "type": "psychic",
        "category": "status",
        "effect": "Boosts defense",
    },
    "teleport": {
        "power": 0,
        "accuracy": "inf",
        "type": "psychic",
        "category": "status",
        "effect": "User switches out",
    },
    "zen-headbutt": {
        "power": 80,
        "accuracy": 90,
        "type": "psychic",
        "category": "physical",
        "effect": "May flinch",
    },
    "psycho-cut": {
        "power": 70,
        "accuracy": 100,
        "type": "psychic",
        "category": "physical",
        "effect": "High crit ratio",
    },
    
    # BUG MOVES
    "bug-bite": {
        "power": 60,
        "accuracy": 100,
        "type": "bug",
        "category": "physical",
        "effect": "Eats berry",
    },
    "x-scissor": {
        "power": 95,
        "accuracy": 100,
        "type": "bug",
        "category": "physical",
        "effect": "High crit ratio",
    },
    "signal-beam": {
        "power": 75,
        "accuracy": 100,
        "type": "bug",
        "category": "special",
        "effect": "May confuse",
    },
    "infestation": {
        "power": 20,
        "accuracy": 100,
        "type": "bug",
        "category": "special",
        "effect": "Traps target",
    },
    "struggle-bug": {
        "power": 50,
        "accuracy": 100,
        "type": "bug",
        "category": "special",
        "effect": "Lowers sp.atk",
    },
    "megahorn": {
        "power": 120,
        "accuracy": 85,
        "type": "bug",
        "category": "physical",
        "effect": "Standard attack",
    },
    "pin-missile": {
        "power": 25,
        "accuracy": 95,
        "type": "bug",
        "category": "physical",
        "effect": "Hits 2-5 times",
    },
    "fury-cutter": {
        "power": 20,
        "accuracy": 95,
        "type": "bug",
        "category": "physical",
        "effect": "Power increases each turn",
    },
    "leech-life": {
        "power": 80,
        "accuracy": 100,
        "type": "bug",
        "category": "physical",
        "effect": "Drains 50% damage",
    },
    
    # ROCK MOVES
    "stone-edge": {
        "power": 100,
        "accuracy": 80,
        "type": "rock",
        "category": "physical",
        "effect": "High crit ratio",
    },
    "rock-slide": {
        "power": 75,
        "accuracy": 90,
        "type": "rock",
        "category": "physical",
        "effect": "May flinch",
    },
    "rock-throw": {
        "power": 50,
        "accuracy": 90,
        "type": "rock",
        "category": "physical",
        "effect": "Standard attack",
    },
    "ancient-power": {
        "power": 60,
        "accuracy": 100,
        "type": "rock",
        "category": "special",
        "effect": "May boost stats",
    },
    "power-gem": {
        "power": 80,
        "accuracy": 100,
        "type": "rock",
        "category": "special",
        "effect": "Standard attack",
    },
    "stealth-rock": {
        "power": 0,
        "accuracy": "inf",
        "type": "rock",
        "category": "status",
        "effect": "Sets entry hazard",
    },
    "rock-tomb": {
        "power": 60,
        "accuracy": 95,
        "type": "rock",
        "category": "physical",
        "effect": "Lowers speed",
    },
    "head-smash": {
        "power": 150,
        "accuracy": 80,
        "type": "rock",
        "category": "physical",
        "effect": "User takes recoil",
    },
    
    # GHOST MOVES
    "shadow-ball": {
        "power": 80,
        "accuracy": 100,
        "type": "ghost",
        "category": "special",
        "effect": "May lower sp.def",
    },
    "shadow-claw": {
        "power": 70,
        "accuracy": 100,
        "type": "ghost",
        "category": "physical",
        "effect": "High crit ratio",
    },
    "shadow-force": {
        "power": 120,
        "accuracy": 100,
        "type": "ghost",
        "category": "physical",
        "effect": "Hides first turn",
    },
    "hex": {
        "power": 65,
        "accuracy": 100,
        "type": "ghost",
        "category": "special",
        "effect": "Power doubles if afflicted",
    },
    "astonish": {
        "power": 30,
        "accuracy": 100,
        "type": "ghost",
        "category": "physical",
        "effect": "May flinch",
    },
    "night-shade": {
        "power": 0,
        "accuracy": 100,
        "type": "ghost",
        "category": "special",
        "effect": "Damage = level",
    },
    "phantom-force": {
        "power": 90,
        "accuracy": 100,
        "type": "ghost",
        "category": "physical",
        "effect": "Hides first turn",
    },
    "shadow-sneak": {
        "power": 40,
        "accuracy": 100,
        "type": "ghost",
        "category": "physical",
        "effect": "Always goes first",
    },
    
    # DRAGON MOVES
    "dragon-claw": {
        "power": 80,
        "accuracy": 100,
        "type": "dragon",
        "category": "physical",
        "effect": "Standard attack",
    },
    "dragon-pulse": {
        "power": 85,
        "accuracy": 100,
        "type": "dragon",
        "category": "special",
        "effect": "Standard attack",
    },
    "dragon-breath": {
        "power": 60,
        "accuracy": 100,
        "type": "dragon",
        "category": "special",
        "effect": "May paralyze",
    },
    "outrage": {
        "power": 120,
        "accuracy": 100,
        "type": "dragon",
        "category": "physical",
        "effect": "Confuses after",
    },
    "dragon-dance": {
        "power": 0,
        "accuracy": "inf",
        "type": "dragon",
        "category": "status",
        "effect": "Boosts attack & speed",
    },
    "dragon-rush": {
        "power": 100,
        "accuracy": 75,
        "type": "dragon",
        "category": "physical",
        "effect": "May flinch",
    },
    "dragon-tail": {
        "power": 60,
        "accuracy": 90,
        "type": "dragon",
        "category": "physical",
        "effect": "Forces switch",
    },
    "draco-meteor": {
        "power": 130,
        "accuracy": 90,
        "type": "dragon",
        "category": "special",
        "effect": "Lowers sp.atk",
    },
    
    # DARK MOVES
    "dark-pulse": {
        "power": 80,
        "accuracy": 100,
        "type": "dark",
        "category": "special",
        "effect": "May flinch",
    },
    "crunch": {
        "power": 80,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "May lower defense",
    },
    "night-slash": {
        "power": 70,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "High crit ratio",
    },
    "bite": {
        "power": 60,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "May flinch",
    },
    "dark-void": {
        "power": 0,
        "accuracy": 50,
        "type": "dark",
        "category": "status",
        "effect": "Puts to sleep",
    },
    "sucker-punch": {
        "power": 70,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "Goes first if enemy attacks",
    },
    "brutal-swing": {
        "power": 60,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "Hits all",
    },
    "foul-play": {
        "power": 95,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "Uses enemy attack",
    },
    "knock-off": {
        "power": 65,
        "accuracy": 100,
        "type": "dark",
        "category": "physical",
        "effect": "Removes item",
    },
    
    # STEEL MOVES
    "iron-head": {
        "power": 80,
        "accuracy": 100,
        "type": "steel",
        "category": "physical",
        "effect": "May flinch",
    },
    "flash-cannon": {
        "power": 80,
        "accuracy": 100,
        "type": "steel",
        "category": "special",
        "effect": "May lower sp.def",
    },
    "iron-tail": {
        "power": 100,
        "accuracy": 75,
        "type": "steel",
        "category": "physical",
        "effect": "May lower defense",
    },
    "bullet-punch": {
        "power": 40,
        "accuracy": 100,
        "type": "steel",
        "category": "physical",
        "effect": "Always goes first",
    },
    "autotomize": {
        "power": 0,
        "accuracy": "inf",
        "type": "steel",
        "category": "status",
        "effect": "Boosts speed",
    },
    "metal-claw": {
        "power": 50,
        "accuracy": 95,
        "type": "steel",
        "category": "physical",
        "effect": "May boost attack",
    },
    "steel-wing": {
        "power": 70,
        "accuracy": 90,
        "type": "steel",
        "category": "physical",
        "effect": "May boost defense",
    },
    "gear-grind": {
        "power": 85,
        "accuracy": 100,
        "type": "steel",
        "category": "physical",
        "effect": "Hits twice",
    },
    "heavy-slam": {
        "power": 0,
        "accuracy": 100,
        "type": "steel",
        "category": "physical",
        "effect": "Power varies by weight",
    },
    
    # FAIRY MOVES
    "play-rough": {
        "power": 90,
        "accuracy": 90,
        "type": "fairy",
        "category": "physical",
        "effect": "May lower attack",
    },
    "moonblast": {
        "power": 95,
        "accuracy": 100,
        "type": "fairy",
        "category": "special",
        "effect": "May lower sp.atk",
    },
    "dazzling-gleam": {
        "power": 80,
        "accuracy": 100,
        "type": "fairy",
        "category": "special",
        "effect": "Hits all",
    },
    "fairy-wind": {
        "power": 40,
        "accuracy": 100,
        "type": "fairy",
        "category": "special",
        "effect": "Standard attack",
    },
    "disarming-voice": {
        "power": 40,
        "accuracy": "inf",
        "type": "fairy",
        "category": "special",
        "effect": "Never misses",
    },
    "charm": {
        "power": 0,
        "accuracy": 100,
        "type": "fairy",
        "category": "status",
        "effect": "Lowers attack",
    },
}

# ════════════════════════════════════════════════════════════════
# MOVE DATA GETTER
# ════════════════════════════════════════════════════════════════

def get_move_data(move_name: str, pokemon_types: list = None) -> dict:
    """
    Get move data with fallback to defaults
    
    Args:
        move_name: Name of the move
        pokemon_types: List of Pokemon types (for checking compatibility)
    
    Returns:
        Dict with move data
    """
    move_name = move_name.lower().replace(" ", "-")
    
    if move_name in MOVES_DATABASE:
        return MOVES_DATABASE[move_name]
    
    # Default move if not found
    return {
        "power": 60,
        "accuracy": 100,
        "type": "normal",
        "category": "physical",
        "effect": "Standard attack",
    }

def get_type_effectiveness(attacking_type: str, defending_types: list) -> float:
    """
    Calculate type effectiveness multiplier
    
    Args:
        attacking_type: Type of attacking move
        defending_types: List of types defending Pokemon has
    
    Returns:
        Float multiplier (0.25, 0.5, 1.0, 2.0, 4.0)
    """
    attacking_type = attacking_type.lower()
    
    if attacking_type not in TYPE_EFFECTIVENESS:
        return 1.0
    
    effectiveness_data = TYPE_EFFECTIVENESS[attacking_type]
    multiplier = 1.0
    
    for def_type in defending_types:
        def_type = def_type.lower()
        
        # Check if super effective
        if def_type in effectiveness_data["strong_against"]:
            multiplier *= 2.0
        
        # Check if not very effective
        elif def_type in effectiveness_data["weak_against"]:
            multiplier *= 0.5
    
    return multiplier

def can_pokemon_learn_move(pokemon_type: str, move_name: str) -> bool:
    """
    Check if Pokemon can learn a move based on type
    
    Args:
        pokemon_type: Pokemon's type
        move_name: Name of move
    
    Returns:
        Boolean
    """
    pokemon_type = pokemon_type.lower()
    move_name = move_name.lower().replace(" ", "-")
    
    # All Pokemon can learn normal moves
    if pokemon_type in POKEMON_TYPE_MOVES:
        return move_name in POKEMON_TYPE_MOVES[pokemon_type]
    
    # If not in database, allow it
    return True
