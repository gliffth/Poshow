"""
🏟️ POSHOW - Battle Gym (endless gym circuit)

Climb floor after floor. Every floor is one gym trainer; every 5th floor is a Gym Leader
who hands out a badge. Opponents scale with the floor, not with you — train up to go deeper.

Rules:
  * no XP in the gym; your team is fully healed after every cleared floor
  * a fainted Pokémon stays fainted until you clear the floor (send in the next one)
  * the run ends when your whole team has fainted, or you forfeit
  * every floor pays Battle Points (BP) + credits; BP buys gear in the Gym Shop

State lives in the player's inventory JSON (no DB migration):
  _gym_floor  current floor of an active run (0 = no run)
  _gym_best   deepest floor reached, ever
  _gym_seed   per-run seed, so a floor's opponent is the same on every retry
  battle_points  the BP balance (a normal, visible inventory entry)

Used by BOTH api/index.py (web) and telegram-bot/bot.py.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

from pokemon_model import PokemonInstance

logger = logging.getLogger(__name__)

FLOOR_KEY = "_gym_floor"
BEST_KEY = "_gym_best"
SEED_KEY = "_gym_seed"
BP_KEY = "battle_points"

LEADER_EVERY = 5
BASE_LEVEL = 8
LEVELS_PER_FLOOR = 2
MAX_LEVEL = 100

# species by type theme (all verified against the PokeDex names list)
POOLS: Dict[str, List[str]] = {
    "fire": ["growlithe", "vulpix", "ponyta", "magmar", "charmeleon", "flareon"],
    "water": ["psyduck", "poliwag", "tentacool", "horsea", "staryu", "seel", "vaporeon"],
    "grass": ["bellsprout", "oddish", "exeggcute", "tangela", "ivysaur", "paras"],
    "electric": ["pikachu", "magnemite", "voltorb", "electabuzz", "jolteon", "raichu"],
    "rock": ["geodude", "onix", "rhyhorn", "kabuto", "omanyte", "graveler"],
    "psychic": ["abra", "drowzee", "kadabra", "slowpoke", "mr-mime", "hypno"],
    "ice": ["seel", "dewgong", "shellder", "cloyster", "jynx", "lapras"],
    "dragon": ["dratini", "dragonair", "dratini", "dragonair"],
    "fighting": ["mankey", "machop", "machoke", "primeape", "hitmonlee", "hitmonchan"],
    "ghost": ["gastly", "haunter", "gengar"],
    "ground": ["sandshrew", "diglett", "cubone", "marowak", "sandslash", "dugtrio"],
    "normal": ["rattata", "pidgey", "meowth", "eevee", "jigglypuff", "raticate"],
}

# signature ability per leader type (all exist in abilities_system.ABILITY_DATABASE)
LEADER_ABILITY = {
    "fire": "blaze", "water": "torrent", "grass": "overgrow", "electric": "static",
    "rock": "sturdy", "psychic": "magic_bounce", "ice": "snow_cloak",
    "dragon": "multiscale", "fighting": "guts", "ghost": "shell_armor", "ground": "shell_armor",
}

# original gym roster — loops forever, stronger each lap (levels scale with the floor)
LEADERS: List[Dict[str, str]] = [
    {"name": "Warden Cinder", "type": "fire", "gym": "Ember"},
    {"name": "Tidecaller Mira", "type": "water", "gym": "Tide"},
    {"name": "Thornwick", "type": "grass", "gym": "Thicket"},
    {"name": "Voltmaster Jun", "type": "electric", "gym": "Spark"},
    {"name": "Cairn the Steadfast", "type": "rock", "gym": "Cairn"},
    {"name": "Seer Ophel", "type": "psychic", "gym": "Mind"},
    {"name": "Frostbound Neve", "type": "ice", "gym": "Frost"},
    {"name": "Wyrmkeeper Rao", "type": "dragon", "gym": "Wyrm"},
    {"name": "Brawler Kesh", "type": "fighting", "gym": "Fist"},
    {"name": "Hollow Marrow", "type": "ghost", "gym": "Hollow"},
]

TRAINER_NAMES = [
    "Cadet Wren", "Rookie Dax", "Hiker Olm", "Angler Pell", "Scout Imri", "Ranger Tove",
    "Bug Fan Lio", "Sailor Brak", "Camper Ness", "Lass Quill", "Runner Saz", "Tamer Eko",
]

# BP shop: id -> (price in BP, label, kind) ; kind "inventory" or "pokeballs"
SHOP: Dict[str, Tuple[int, str, str]] = {
    "superpotion": (4, "Super Potion", "inventory"),
    "greatball": (4, "Great Ball", "pokeballs"),
    "ultraball": (8, "Ultra Ball", "pokeballs"),
    "exp_all": (20, "EXP All", "inventory"),
    "rare_candy": (30, "Rare Candy", "inventory"),
}


# ── state ────────────────────────────────────────────────────────────

def get_bp(player) -> int:
    return int(player.inventory.get(BP_KEY, 0))


def get_floor(player) -> int:
    return int(player.inventory.get(FLOOR_KEY, 0))


def get_best(player) -> int:
    return int(player.inventory.get(BEST_KEY, 0))


def in_run(player) -> bool:
    return get_floor(player) > 0


def is_leader_floor(floor: int) -> bool:
    return floor > 0 and floor % LEADER_EVERY == 0


def floor_level(floor: int, leader: bool = False) -> int:
    return min(MAX_LEVEL, BASE_LEVEL + LEVELS_PER_FLOOR * floor + (3 if leader else 0))


def leader_for(floor: int) -> Dict[str, str]:
    return LEADERS[(floor // LEADER_EVERY - 1) % len(LEADERS)]


def status(player) -> Dict:
    floor = get_floor(player)
    nxt = floor if floor else 1
    leader = is_leader_floor(nxt)
    info = leader_for(nxt) if leader else None
    return {
        "in_run": floor > 0,
        "floor": floor,
        "next_floor": nxt,
        "best": get_best(player),
        "bp": get_bp(player),
        "next_is_leader": leader,
        "next_level": floor_level(nxt, leader),
        "leader": ({"name": info["name"], "type": info["type"], "gym": info["gym"]} if info else None),
    }


def start_or_resume(player) -> int:
    """Begin a run at floor 1, or return the floor an active run is on."""
    if not in_run(player):
        player.inventory[FLOOR_KEY] = 1
        player.inventory[SEED_KEY] = random.randint(1, 10_000_000)
    return get_floor(player)


def build_opponent(player) -> Tuple[PokemonInstance, Dict]:
    """The current floor's opponent. Deterministic per (run seed, floor) so retrying a floor
    after a faint doesn't re-roll an easier enemy."""
    floor = get_floor(player)
    rng = random.Random(int(player.inventory.get(SEED_KEY, 1)) * 1000 + floor)
    leader = is_leader_floor(floor)

    if leader:
        info = leader_for(floor)
        theme = info["type"]
        trainer = info["name"]
        gym = info["gym"]
    else:
        theme = rng.choice(list(POOLS.keys()))
        trainer = rng.choice(TRAINER_NAMES)
        gym = None

    species = rng.choice(POOLS[theme])
    level = floor_level(floor, leader)
    mon = PokemonInstance(species, level, 0)
    mon.gym_floor = floor
    if leader:
        mon.iv = {k: 31 for k in mon.iv}
        ability = LEADER_ABILITY.get(theme)
        if ability:
            mon.ability = ability
    mon.recalculate_stats()
    mon.restore_hp()
    meta = {"floor": floor, "leader": leader, "trainer": trainer, "theme": theme, "gym": gym, "level": level}
    return mon, meta


# ── outcomes ─────────────────────────────────────────────────────────

def _heal_team(player):
    for m in player.active_team:
        m.restore_hp()


def floor_won(player) -> Dict:
    floor = get_floor(player)
    leader = is_leader_floor(floor)
    bp = 1 + floor // LEADER_EVERY + (5 if leader else 0)
    coins = 12 * floor + (60 if leader else 0)

    player.inventory[BP_KEY] = get_bp(player) + bp
    player.add_coins(coins)

    badge = None
    if leader:
        badge = f"{leader_for(floor)['gym']} Badge"
        if badge not in player.badges:
            player.badges.append(badge)

    player.inventory[FLOOR_KEY] = floor + 1
    player.inventory[BEST_KEY] = max(get_best(player), floor)
    _heal_team(player)
    return {
        "floor_cleared": floor, "bp": bp, "coins": coins, "badge": badge,
        "next_floor": floor + 1, "best": get_best(player), "total_bp": get_bp(player),
    }


def floor_lost(player) -> Dict:
    """The fighter fainted. Run continues if anyone is left standing."""
    floor = get_floor(player)
    alive = [m for m in player.active_team if not m.is_fainted and m.current_hp > 0]
    if alive:
        return {"run_over": False, "floor": floor, "remaining": len(alive)}
    return end_run(player)


def end_run(player) -> Dict:
    floor = get_floor(player)
    cleared = max(0, floor - 1)
    player.inventory[BEST_KEY] = max(get_best(player), cleared)
    player.inventory[FLOOR_KEY] = 0
    player.inventory.pop(SEED_KEY, None)
    _heal_team(player)       # the gym patches you up — a finished run never leaves you stuck
    return {"run_over": True, "floors_cleared": cleared, "best": get_best(player), "total_bp": get_bp(player)}


# ── shop ─────────────────────────────────────────────────────────────

def shop_catalog() -> List[Dict]:
    return [{"id": k, "name": v[1], "price": v[0]} for k, v in SHOP.items()]


def buy(player, item_id: str, quantity: int = 1) -> Optional[str]:
    """Spend BP. Returns an error message, or None on success."""
    if item_id not in SHOP:
        return f"Unknown gym shop item: {item_id}"
    if quantity < 1 or quantity > 99:
        return "Quantity must be 1-99."
    price, _label, kind = SHOP[item_id]
    cost = price * quantity
    if get_bp(player) < cost:
        return f"Need {cost} BP (you have {get_bp(player)})."
    player.inventory[BP_KEY] = get_bp(player) - cost
    if kind == "pokeballs":
        player.pokeballs[item_id] = player.pokeballs.get(item_id, 0) + quantity
    else:
        player.add_item(item_id, quantity)
    return None
