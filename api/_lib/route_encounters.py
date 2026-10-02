"""
⚡ POSHOW - ROUTE-SPECIFIC ENCOUNTERS
Each route has unique Pokemon with rare spawns
"""

import random
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RouteEncounter:
    """Route encounter configuration"""
    
    def __init__(self, route_name: str, pokemon_pool: dict, rare_species: str, rare_rate: float = 0.01):
        """
        Args:
            route_name: Route identifier
            pokemon_pool: {species: weight, ...}
            rare_species: Rare spawn
            rare_rate: Spawn chance (0.0-1.0)
        """
        self.route_name = route_name
        self.pokemon_pool = pokemon_pool
        self.rare_species = rare_species
        self.rare_rate = rare_rate
        self.level_range = (3, 15)
    
    def spawn_pokemon(self) -> Tuple[str, int]:
        """Spawn a Pokemon for this route"""
        # Check rare spawn first
        if random.random() < self.rare_rate:
            level = random.randint(*self.level_range)
            return self.rare_species, level
        
        # Normal spawn
        species = random.choices(
            list(self.pokemon_pool.keys()),
            weights=list(self.pokemon_pool.values()),
            k=1
        )[0]
        
        level = random.randint(*self.level_range)
        return species, level


# KANTO ROUTES
KANTO_ROUTES = {
    "route_1": RouteEncounter(
        "Route 1",
        {
            "pidgey": 40,
            "rattata": 60,
            "sentret": 20,
        },
        "bellsprout",
        rare_rate=0.02
    ),
    "route_2": RouteEncounter(
        "Route 2",
        {
            "pidgey": 50,
            "pidgeotto": 10,
            "rattata": 40,
            "nidoran-m": 20,
        },
        "nidoran-f",
        rare_rate=0.015
    ),
    "viridian_forest": RouteEncounter(
        "Viridian Forest",
        {
            "caterpie": 50,
            "metapod": 20,
            "weedle": 40,
            "kakuna": 15,
            "pikachu": 5,
        },
        "paras",
        rare_rate=0.01
    ),
    "route_3": RouteEncounter(
        "Route 3",
        {
            "pidgeotto": 30,
            "jigglypuff": 20,
            "abra": 40,
            "mankey": 35,
        },
        "cubone",
        rare_rate=0.02
    ),
    "route_4": RouteEncounter(
        "Route 4",
        {
            "sandshrew": 50,
            "mankey": 30,
            "growlithe": 25,
            "machop": 20,
        },
        "diglett",
        rare_rate=0.015
    ),
    "route_5": RouteEncounter(
        "Route 5",
        {
            "pidgeotto": 40,
            "meowth": 45,
            "oddish": 35,
            "mankey": 20,
        },
        "bellsprout",
        rare_rate=0.01
    ),
    "route_6": RouteEncounter(
        "Route 6",
        {
            "meowth": 50,
            "oddish": 40,
            "bellsprout": 35,
            "vulpix": 20,
        },
        "growlithe",
        rare_rate=0.015
    ),
    "route_7": RouteEncounter(
        "Route 7",
        {
            "pidgeotto": 40,
            "abra": 30,
            "oddish": 35,
            "gloom": 15,
        },
        "exeggcute",
        rare_rate=0.01
    ),
    "route_8": RouteEncounter(
        "Route 8",
        {
            "abra": 50,
            "pidgeotto": 30,
            "mankey": 25,
        },
        "machop",
        rare_rate=0.02
    ),
    "route_9": RouteEncounter(
        "Route 9",
        {
            "growlithe": 40,
            "vulpix": 35,
            "mankey": 30,
            "farfetchd": 10,
        },
        "ponyta",
        rare_rate=0.01
    ),
    "route_10": RouteEncounter(
        "Route 10",
        {
            "pikachu": 30,
            "magnemite": 40,
            "voltorb": 35,
            "electabuzz": 15,
        },
        "jolteon",
        rare_rate=0.02
    ),
}

# JOHTO ROUTES (sample)
JOHTO_ROUTES = {
    "route_29": RouteEncounter(
        "Route 29",
        {
            "pidgey": 50,
            "sentret": 50,
            "hoppip": 30,
        },
        "chikorita",
        rare_rate=0.01
    ),
}

ALL_ROUTES = {
    **KANTO_ROUTES,
    **JOHTO_ROUTES,
}


# Difficulty ramps with route number; the flat (3, 15) default made Route 1 and Route 10 identical.
ROUTE_LEVELS = {
    "route_1": (3, 8), "route_2": (4, 10), "viridian_forest": (5, 12),
    "route_3": (8, 14), "route_4": (10, 16), "route_5": (12, 18),
    "route_6": (14, 20), "route_7": (16, 22), "route_8": (18, 24),
    "route_9": (20, 26), "route_10": (22, 28), "route_29": (2, 8),
}
for _rid, _range in ROUTE_LEVELS.items():
    if _rid in ALL_ROUTES:
        ALL_ROUTES[_rid].level_range = _range


# ── regions ──────────────────────────────────────────────────────────
# Every route belongs to a region. Kanto/Johto come from the hand-tuned tables above; everything
# else is loaded from route_data.py. Routes that would collide on id (several regions have a
# "route_1") are namespaced as "<region>:<id>".
ROUTE_REGION = {rid: "kanto" for rid in ALL_ROUTES}
if "route_29" in ALL_ROUTES:
    ROUTE_REGION["route_29"] = "johto"

try:
    from route_data import COMPLETE_ROUTE_DATA
    _seen_in = {}
    for _region, _routes in COMPLETE_ROUTE_DATA.items():
        for _rid in _routes:
            _seen_in.setdefault(_rid, []).append(_region)

    for _region, _routes in COMPLETE_ROUTE_DATA.items():
        for _rid, _r in _routes.items():
            if _rid in ALL_ROUTES and ROUTE_REGION.get(_rid) == _region:
                continue  # the hand-tuned version already covers this route
            _key = _rid if (len(_seen_in[_rid]) == 1 and _rid not in ALL_ROUTES) else f"{_region}:{_rid}"
            if _key in ALL_ROUTES:
                continue
            _common = _r["common"]
            if not isinstance(_common, dict):             # a few entries are plain lists
                _common = {sp: 1 for sp in _common}
            _enc = RouteEncounter(_r["name"], dict(_common), _r["rare"], _r.get("rare_rate", 0.02))
            _enc.level_range = tuple(_r.get("level_range", (3, 15)))
            ALL_ROUTES[_key] = _enc
            ROUTE_REGION[_key] = _region
except Exception as _e:  # region data is optional — the core Kanto routes keep working without it
    logger.warning(f"route_data not loaded: {_e}")


class EncounterSystem:
    """Route encounter management"""
    
    @staticmethod
    def get_route(route_id: str) -> RouteEncounter:
        """Get route configuration"""
        if route_id not in ALL_ROUTES:
            # Fallback to generic encounter
            return RouteEncounter(
                "Unknown Route",
                {"pikachu": 50, "pidgeotto": 50},
                "eevee",
                rare_rate=0.01
            )
        return ALL_ROUTES[route_id]
    
    @staticmethod
    def spawn_in_route(route_id: str) -> Tuple[str, int]:
        """Spawn Pokemon in a specific route"""
        route = EncounterSystem.get_route(route_id)
        species, level = route.spawn_pokemon()
        logger.info(f"🌍 Spawned {species} Lv{level} on {route.route_name}")
        return species, level
    
    @staticmethod
    def has_route(route_id) -> bool:
        return route_id in ALL_ROUTES

    @staticmethod
    def list_routes(region=None) -> list:
        """Routes (optionally only one region's), easiest first (sorted by min level), for menus."""
        rows = []
        for rid, r in ALL_ROUTES.items():
            if region and ROUTE_REGION.get(rid) != region:
                continue
            rows.append({
                "region": ROUTE_REGION.get(rid),
                "id": rid,
                "name": r.route_name,
                "min_level": r.level_range[0],
                "max_level": r.level_range[1],
                "pokemon": list(r.pokemon_pool.keys()),
                "rare_rate": r.rare_rate,
            })
        rows.sort(key=lambda x: (x["min_level"], x["max_level"], x["id"]))
        return rows

    @staticmethod
    def get_route_info(route_id: str) -> dict:
        """Get route information"""
        route = EncounterSystem.get_route(route_id)
        return {
            "name": route.route_name,
            "pokemon": list(route.pokemon_pool.keys()),
            "rare": route.rare_species,
            "rare_rate": f"{route.rare_rate * 100:.1f}%",
            "levels": f"Lv{route.level_range[0]}-{route.level_range[1]}"
        }


# Global encounter system instance
encounter_system = EncounterSystem()
