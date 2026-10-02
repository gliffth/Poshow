"""
⚡ POSHOW - Complete Route Data for All 9 Regions
Use this to populate ROUTE_DATA in bot.py
"""

COMPLETE_ROUTE_DATA = {
    "kanto": {
        "route_1": {
            "name": "Pallet Town → Viridian City",
            "common": {"pidgey": 60, "rattata": 40},
            "rare": "bellsprout",
            "rare_rate": 0.02,
            "level_range": (3, 8),
            "gym": None,
        },
        "viridian_forest": {
            "name": "Viridian Forest",
            "common": {"pidgeotto": 50, "pikachu": 40, "butterfree": 10},
            "rare": "abra",
            "rare_rate": 0.02,
            "level_range": (5, 12),
            "gym": None,
        },
        "route_2": {
            "name": "Viridian City → Pewter City",
            "common": {"mankey": 60, "jigglypuff": 40},
            "rare": "cubone",
            "rare_rate": 0.02,
            "level_range": (8, 14),
            "gym": None,
        },
        "pewter_city": {
            "name": "Pewter City",
            "common": {"sandshrew": 50, "diglett": 50},
            "rare": "onix",
            "rare_rate": 0.01,
            "level_range": (10, 16),
            "gym": "brock",  # Rock gym
        },
        "route_3": {
            "name": "Pewter City → Cerulean City",
            "common": {"pidgeotto": 50, "mankey": 50},
            "rare": "growlithe",
            "rare_rate": 0.02,
            "level_range": (12, 18),
            "gym": None,
        },
        "route_4": {
            "name": "Cerulean City → Route 5",
            "common": {"sandshrew": 60, "diglett": 40},
            "rare": "charmander",
            "rare_rate": 0.01,
            "level_range": (15, 22),
            "gym": None,
        },
        "cerulean_city": {
            "name": "Cerulean City",
            "common": {"slowpoke": 50, "poliwag": 50},
            "rare": "psyduck",
            "rare_rate": 0.01,
            "level_range": (14, 20),
            "gym": "misty",  # Water gym
        },
        "route_5": {
            "name": "Route 5",
            "common": {"pidgeotto": 50, "meowth": 50},
            "rare": "bellsprout",
            "rare_rate": 0.02,
            "level_range": (20, 26),
            "gym": None,
        },
        "route_6": {
            "name": "Route 6",
            "common": {"pidgeotto": 50, "meowth": 50},
            "rare": "growlithe",
            "rare_rate": 0.02,
            "level_range": (22, 28),
            "gym": None,
        },
        "route_7": {
            "name": "Route 7",
            "common": {"pidgeotto": 40, "jigglypuff": 60},
            "rare": "oddish",
            "rare_rate": 0.02,
            "level_range": (24, 30),
            "gym": None,
        },
        "route_8": {
            "name": "Route 8",
            "common": {"sandslash": 50, "dugtrio": 50},
            "rare": "diglett",
            "rare_rate": 0.02,
            "level_range": (26, 32),
            "gym": None,
        },
        "route_9": {
            "name": "Route 9 (Rock Tunnel)",
            "common": {"zubat": 60, "geodude": 40},
            "rare": "cubone",
            "rare_rate": 0.02,
            "level_range": (28, 35),
            "gym": None,
        },
        "route_10": {
            "name": "Route 10",
            "common": {"voltorb": 50, "pikachu": 50},
            "rare": "magnemite",
            "rare_rate": 0.02,
            "level_range": (32, 38),
            "gym": None,
        },
        "vermilion_city": {
            "name": "Vermilion City",
            "common": {"pidgeotto": 50, "shellder": 50},
            "rare": "horsea",
            "rare_rate": 0.01,
            "level_range": (21, 28),
            "gym": "lt_surge",  # Electric gym
        },
        "celadon_city": {
            "name": "Celadon City",
            "common": {"oddish": 50, "bellsprout": 50},
            "rare": "gloom",
            "rare_rate": 0.01,
            "level_range": (25, 32),
            "gym": "erika",  # Grass gym
        },
        "fuchsia_city": {
            "name": "Fuchsia City",
            "common": {"koffing": 50, "weezing": 50},
            "rare": "grimer",
            "rare_rate": 0.01,
            "level_range": (35, 42),
            "gym": "janine",  # Poison gym
        },
        "cinnabar_island": {
            "name": "Cinnabar Island",
            "common": {"growlithe": 50, "ponyta": 50},
            "rare": "charizard",
            "rare_rate": 0.01,
            "level_range": (37, 45),
            "gym": "blaine",  # Fire gym
        },
        "viridian_city": {
            "name": "Viridian City (Final)",
            "common": {"pidgeotto": 50, "raticate": 50},
            "rare": "dragonite",
            "rare_rate": 0.005,
            "level_range": (40, 50),
            "gym": "giovanni",  # Final gym
        },
    },
    
    "johto": {
        "route_29": {
            "name": "New Bark Town → Cherrygrove City",
            "common": {"sentret": 60, "hoothoot": 40},
            "rare": "chikorita",
            "rare_rate": 0.01,
            "level_range": (2, 8),
            "gym": None,
        },
        "route_30": {
            "name": "Route 30",
            "common": {"pidgey": 50, "ledyba": 50},
            "rare": "chikorita",
            "rare_rate": 0.01,
            "level_range": (5, 12),
            "gym": None,
        },
        "route_31": {
            "name": "Route 31",
            "common": {"spearow": 50, "girafarig": 50},
            "rare": "meowth",
            "rare_rate": 0.02,
            "level_range": (8, 16),
            "gym": None,
        },
        "azalea_town": {
            "name": "Azalea Town",
            "common": {"oddish": 50, "bellsprout": 50},
            "rare": "bulbasaur",
            "rare_rate": 0.01,
            "level_range": (10, 18),
            "gym": "bugsy",  # Bug gym
        },
    },
    
    "hoenn": {
        "route_101": {
            "name": "Littleroot Town → Oldale Town",
            "common": {"zigzagoon": 60, "taillow": 40},
            "rare": "seedot",
            "rare_rate": 0.02,
            "level_range": (3, 10),
            "gym": None,
        },
        "route_102": {
            "name": "Route 102",
            "common": {"oddish": 50, "bellsprout": 50},
            "rare": "treecko",
            "rare_rate": 0.01,
            "level_range": (5, 14),
            "gym": None,
        },
    },
    
    "sinnoh": {
        "route_201": {
            "name": "Twinleaf Town → Route 201",
            "common": {"starly": 60, "bidoof": 40},
            "rare": "turtwig",
            "rare_rate": 0.01,
            "level_range": (2, 8),
            "gym": None,
        },
    },
    
    "unova": {
        "route_1": {
            "name": "Aspertia City → Route 2",
            "common": ["pidove", "patrat"],
            "rare": "pignite",
            "rare_rate": 0.01,
            "level_range": (2, 8),
            "gym": None,
        },
    },
    
    "kalos": {
        "route_1": {
            "name": "Vaniville Town → Aquacorde Town",
            "common": ["scatterbug", "pidgeotto"],
            "rare": "froakie",
            "rare_rate": 0.01,
            "level_range": (2, 8),
            "gym": None,
        },
    },
    
    "alola": {
        "route_1": {
            "name": "Alola Route 1",
            "common": ["caterpie", "pidgeotto"],
            "rare": "rowlet",
            "rare_rate": 0.01,
            "level_range": (1, 8),
            "gym": None,
        },
    },
    
    "galar": {
        "route_1": {
            "name": "Postwick",
            "common": ["pidove", "rookidee"],
            "rare": "grookey",
            "rare_rate": 0.01,
            "level_range": (1, 8),
            "gym": None,
        },
    },
    
    "paldea": {
        "route_1": {
            "name": "Paldea Route 1",
            "common": ["pidgeotto", "fidough"],
            "rare": "sprigatito",
            "rare_rate": 0.01,
            "level_range": (1, 8),
            "gym": None,
        },
    },
}

# GYM LEADERS - Use when implementing gym battles
GYM_LEADERS = {
    "brock": {"species": "onix", "level": 15, "type": "rock"},
    "misty": {"species": "starmie", "level": 18, "type": "water"},
    "lt_surge": {"species": "raichu", "level": 21, "type": "electric"},
    "erika": {"species": "vileplume", "level": 24, "type": "grass"},
    "janine": {"species": "weezing", "level": 35, "type": "poison"},
    "blaine": {"species": "arcanine", "level": 40, "type": "fire"},
    "giovanni": {"species": "rhydon", "level": 45, "type": "ground"},
}

# ELITE FOUR - Use when implementing Elite Four
ELITE_FOUR = [
    {"name": "Lorelei", "type": "ice", "level": 50},
    {"name": "Bruno", "type": "fighting", "level": 51},
    {"name": "Agatha", "type": "poison", "level": 52},
    {"name": "Lance", "type": "dragon", "level": 53},
]

if __name__ == "__main__":
    print(f"✅ Route data for {len(COMPLETE_ROUTE_DATA)} regions loaded")
    for region, routes in COMPLETE_ROUTE_DATA.items():
        print(f"  {region.title()}: {len(routes)} locations")
