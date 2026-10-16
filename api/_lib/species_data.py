"""
Offline species data (types, base stats, Pokédex id) compiled from the PokeDex by tools/build_data.py.

Before this, every Pokémon constructed anywhere — including both fighters on EVERY battle turn — called PokeAPI
over the network (slow, and a single failed lookup could make a caught Pokémon vanish on load). Now the common
case never leaves the process; PokeAPI is only a fallback for species this file doesn't know.
"""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Optional data files that failed to load (the game keeps running, degraded). Surfaced by /api/diagnose and /api/ready.
LOAD_ERRORS: List[str] = []


def _load_json(name: str, required: bool) -> Dict[str, Dict]:
    """species.json is REQUIRED: without it every stat/type/id lookup would silently fall back to the network, so a
    missing or corrupt file stops the process at startup. The extras are optional: a clear warning + LOAD_ERRORS."""
    path = os.path.join(_DATA, name)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or (required and not data):
            raise ValueError("expected a non-empty JSON object")
        return data
    except Exception as e:                       # noqa: BLE001
        msg = f"{name} could not be loaded: {e}"
        if required:
            raise RuntimeError(f"FATAL: {msg} ({path})") from e
        logger.warning(f"⚠️ {msg} — running degraded (learnsets / ability text may be missing)")
        LOAD_ERRORS.append(msg)
        return {}


SPECIES: Dict[str, Dict] = _load_json("species.json", required=True)

LEGENDARY = {"articuno", "zapdos", "moltres", "mewtwo", "mew", "raikou", "entei", "suicune", "lugia", "ho-oh", "celebi",
             "regirock", "regice", "registeel", "latias", "latios", "kyogre", "groudon", "rayquaza", "jirachi", "deoxys",
             "uxie", "mesprit", "azelf", "dialga", "palkia", "heatran", "regigigas", "giratina", "cresselia", "darkrai",
             "shaymin", "arceus", "cobalion", "terrakion", "virizion", "tornadus", "thundurus", "landorus", "reshiram",
             "zekrom", "kyurem", "xerneas", "yveltal", "zygarde", "solgaleo", "lunala", "necrozma", "zacian", "zamazenta",
             "eternatus", "koraidon", "miraidon"}

EXTRA: Dict[str, Dict] = _load_json("species_extra.json", required=False)
ABILITY_INFO: Dict[str, Dict] = _load_json("abilities_info.json", required=False)

ART = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png"


def catch_rate(species: str, bst: int) -> int:
    """Approximation of the games' capture rates (PokeDex has none): legendaries 3, strong evolved Pokémon 45,
    mid-stage 75-120, early/small Pokémon 190-255."""
    if species in LEGENDARY:
        return 3
    if bst >= 450:
        return 45
    if bst >= 400:
        return 75
    if bst >= 340:
        return 120
    if bst >= 290:
        return 190
    return 255


def get(species: str) -> Optional[Dict]:
    """Same shape pokeapi_manager.get_pokemon() returns (abilities/moves are empty: see PokemonInstance)."""
    rec = SPECIES.get((species or "").lower())
    if not rec:
        return None
    hp, atk, df, spa, spd, spe = rec["s"]
    bst = sum(rec["s"])
    ex = EXTRA.get((species or "").lower(), {})
    regular = [a[0] for a in ex.get("a", []) if not a[1]]
    hidden = [a[0] for a in ex.get("a", []) if a[1]]
    return {
        "id": rec["id"], "name": species.lower(), "height": 0, "weight": 0,
        "image": ART.format(rec["id"]), "image_shiny": "",
        "types": list(rec["t"]),
        "abilities": regular or [a for a in rec.get("a", []) if not a.startswith("~")],
        "hidden_abilities": hidden,
        "base_stats": {"hp": hp, "attack": atk, "defense": df, "sp_atk": spa, "sp_def": spd, "speed": spe},
        "base_experience": max(40, bst // 5),
        "catch_rate": int(ex["c"]) if "c" in ex else catch_rate(species.lower(), bst),
        "moves": [],
    }


def learnset(species: str):
    """[(level, move), ...] level-up moves from the most recent game that has them (real data)."""
    return [(int(l), m) for l, m in EXTRA.get((species or "").lower(), {}).get("l", [])]


_PREV: Optional[Dict[str, str]] = None


def _pre_evolution(species: str) -> Optional[str]:
    """The species this one evolves from (reverse of rules.EVOLUTIONS), or None."""
    global _PREV
    if _PREV is None:
        _PREV = {}
        try:
            import rules
            for frm, evs in rules.EVOLUTIONS.items():
                for e in evs:
                    _PREV.setdefault(e["to"], frm)
        except Exception:                      # noqa: BLE001 — without it we simply don't inherit
            pass
    return _PREV.get((species or "").lower())


def learnset_inherited(species: str):
    """The species' own level-up moves PLUS those of its earlier evolutions. The compiled data only lists what a
    final form learns itself (Meganium: 4 moves), but in the games an evolved Pokémon has the whole line's moves
    available. The evolved form's own level wins when a move appears in several stages."""
    merged, seen, cur, hops = {}, set(), (species or "").lower(), 0
    while cur and cur not in seen and hops < 4:
        seen.add(cur)
        for lv, mv in learnset(cur):
            merged.setdefault(mv, lv)
        cur = _pre_evolution(cur)
        hops += 1
    return [(lv, mv) for mv, lv in merged.items()]


def moves_at_level(species: str, level: int, limit: int = 4):
    """What a Pokémon of this level knows, the way the games do it: the latest `limit` distinct level-up moves
    (counting the moves of its earlier evolutions)."""
    seen, out = set(), []
    for lv, mv in sorted(learnset_inherited(species), key=lambda x: x[0]):
        if lv <= level and mv not in seen:
            seen.add(mv)
            out.append(mv)
    return out[-limit:]


def validate_capture_rates() -> None:
    """Verify that all supported species have verified (not estimated) capture rates.
    Raises ValueError if any species is missing a capture rate in species_extra.json,
    so the data build fails rather than silently estimating rates."""
    missing = []
    for species_name in SPECIES.keys():
        if species_name.lower() not in EXTRA or "c" not in EXTRA[species_name.lower()]:
            missing.append(species_name)
    
    if missing:
        raise ValueError(
            f"Missing capture rates for {len(missing)} species. "
            f"Add 'c' (capture_rate) to species_extra.json for: {', '.join(sorted(missing)[:10])}"
            f"{'...' if len(missing) > 10 else ''}. "
            f"Do not rely on BST-based estimates for game-critical mechanics."
        )
