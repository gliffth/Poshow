"""
Shared battle rules data: type chart, natures, move data, evolution data.

The numbers come from the scraped PokeDex (compiled by tools/build_data.py into data/*.json), so every
move has its real power / accuracy / PP / category / secondary effect, and every Pokémon its real evolutions.
"""

import json
import os
from typing import Dict, List, Optional

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(name: str, default):
    try:
        with open(os.path.join(_DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


MOVE_DATA: Dict[str, Dict] = _load("moves.json", {})
NATURES: Dict[str, Dict] = _load("natures.json", {"Neutral": {"up": None, "down": None}})
EVOLUTIONS: Dict[str, List[Dict]] = _load("evolutions.json", {})

STRUGGLE = {"t": "normal", "c": "p", "p": 50, "a": 0, "pp": 999, "pr": 0, "fx": [["recoil", 0.25]]}

# ── type chart (attacker type -> defender type -> multiplier), full 18 types incl. immunities ──
_T = {
    "normal":   {"rock": .5, "steel": .5, "ghost": 0},
    "fire":     {"fire": .5, "water": .5, "rock": .5, "dragon": .5, "grass": 2, "ice": 2, "bug": 2, "steel": 2},
    "water":    {"water": .5, "grass": .5, "dragon": .5, "fire": 2, "ground": 2, "rock": 2},
    "electric": {"electric": .5, "grass": .5, "dragon": .5, "ground": 0, "water": 2, "flying": 2},
    "grass":    {"fire": .5, "grass": .5, "poison": .5, "flying": .5, "bug": .5, "dragon": .5, "steel": .5,
                 "water": 2, "ground": 2, "rock": 2},
    "ice":      {"fire": .5, "water": .5, "ice": .5, "steel": .5, "grass": 2, "ground": 2, "flying": 2, "dragon": 2},
    "fighting": {"poison": .5, "flying": .5, "psychic": .5, "bug": .5, "fairy": .5, "ghost": 0,
                 "normal": 2, "ice": 2, "rock": 2, "dark": 2, "steel": 2},
    "poison":   {"poison": .5, "ground": .5, "rock": .5, "ghost": .5, "steel": 0, "grass": 2, "fairy": 2},
    "ground":   {"grass": .5, "bug": .5, "flying": 0, "fire": 2, "electric": 2, "poison": 2, "rock": 2, "steel": 2},
    "flying":   {"electric": .5, "rock": .5, "steel": .5, "grass": 2, "fighting": 2, "bug": 2},
    "psychic":  {"psychic": .5, "steel": .5, "dark": 0, "fighting": 2, "poison": 2},
    "bug":      {"fire": .5, "fighting": .5, "poison": .5, "flying": .5, "ghost": .5, "steel": .5, "fairy": .5,
                 "grass": 2, "psychic": 2, "dark": 2},
    "rock":     {"fighting": .5, "ground": .5, "steel": .5, "fire": 2, "ice": 2, "flying": 2, "bug": 2},
    "ghost":    {"normal": 0, "dark": .5, "ghost": 2, "psychic": 2},
    "dragon":   {"steel": .5, "fairy": 0, "dragon": 2},
    "dark":     {"fighting": .5, "dark": .5, "fairy": .5, "ghost": 2, "psychic": 2},
    "steel":    {"fire": .5, "water": .5, "electric": .5, "steel": .5, "ice": 2, "rock": 2, "fairy": 2},
    "fairy":    {"fire": .5, "poison": .5, "steel": .5, "dragon": 2, "fighting": 2, "dark": 2},
}
TYPE_CHART = _T


def type_multiplier(move_type: str, defender_types: List[str]) -> float:
    row = _T.get((move_type or "normal").lower(), {})
    mult = 1.0
    for t in defender_types or []:
        mult *= row.get(str(t).lower(), 1.0)
    return mult


# ── natures ──
_STAT_KEYS = ("atk", "def", "spa", "spd", "spe")


def nature_multiplier(nature: Optional[str], stat: str) -> float:
    """stat is one of atk/def/spa/spd/spe. +10% / -10% from the nature, 1.0 otherwise."""
    n = NATURES.get(nature or "Neutral") or NATURES["Neutral"]
    if n.get("up") == stat and n.get("down") != stat:
        return 1.1
    if n.get("down") == stat and n.get("up") != stat:
        return 0.9
    return 1.0


# ── moves ──
def move_info(name: str) -> Dict:
    """Compact move record: t(type) c(p|s|x) p(power) a(accuracy, 0=never misses) pp pr(priority) fx(effects)."""
    key = (name or "tackle").lower().replace("_", "-").replace(" ", "-")
    if key == "struggle":
        return STRUGGLE
    rec = MOVE_DATA.get(key)
    if rec:
        return rec
    try:  # moves only the older hand-written table knows
        from moves_database import get_move_data
        d = get_move_data(key) or {}
        acc = d.get("accuracy", 100)
        return {"t": str(d.get("type", "normal")).lower(),
                "c": {"physical": "p", "special": "s", "status": "x"}.get(str(d.get("category", "physical")), "p"),
                "p": int(d.get("power", 40) or 0),
                "a": int(acc) if isinstance(acc, (int, float)) else 0,
                "pp": 20, "pr": 0, "fx": []}
    except Exception:
        return {"t": "normal", "c": "p", "p": 40, "a": 100, "pp": 25, "pr": 0, "fx": []}


# ── evolutions ──
def evolutions_for(species: str) -> List[Dict]:
    return EVOLUTIONS.get((species or "").lower(), [])


# ── experience ──
# The old curve (100 * 2^(level-1) XP per level) needed 204,800 XP for Lv12 -> Lv13, so nothing got past ~Lv12.
# "Fast" growth: total XP to reach level n is 0.8 * n^3; progress toward the next level is stored in `experience`.
def xp_to_next(level: int) -> int:
    level = max(1, min(99, int(level)))
    return max(10, int(0.8 * ((level + 1) ** 3 - level ** 3)))


def battle_xp(foe_level: int, trainer: bool = False) -> int:
    """XP for beating one Pokémon of this level (trainers pay a third more, like the main games)."""
    return int((40 if trainer else 30) * max(1, foe_level))


# ── sensible default movesets ──
_BAD_FOR_DEFAULT = ("selfko", "recharge")


def default_moveset(types: List[str], level: int) -> List[str]:
    """Up to 4 usable moves for a Pokémon that has no hand-written learnset: strong-for-its-level STAB
    attacks first, then a Normal-type attack for coverage. (PokeAPI's own list starts with the first
    alphabetical moves — 'absorb', 'acid' — which made every wild Pokémon and gym leader toothless.)"""
    types = [str(t).lower() for t in (types or ["normal"])]
    cap = 45 if level < 12 else 65 if level < 25 else 90 if level < 45 else 130
    floor = 25 if level < 12 else 40 if level < 25 else 55
    stab, normal = [], []
    for name, d in MOVE_DATA.items():
        p = d["p"]
        if d["c"] == "x" or p < floor or p > cap or (d["a"] and d["a"] < 75):
            continue
        if any(fx[0] in _BAD_FOR_DEFAULT for fx in d["fx"]):
            continue
        if d["t"] in types:
            stab.append((p * (d["a"] or 100) / 100, name))
        elif d["t"] == "normal":
            normal.append((p * (d["a"] or 100) / 100, name))
    stab.sort(reverse=True)
    normal.sort(reverse=True)
    out = [n for _, n in stab[:3]] + [n for _, n in normal[:4 - min(3, len(stab))]]
    return out[:4] or ["tackle", "scratch"]
