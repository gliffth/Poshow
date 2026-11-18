"""
PvP battle formats and team rules. One shared battle engine (pvp_system.py) runs every format; a format only
changes how many Pokémon you bring and field, what is allowed, how long a turn may take and whether it is rated.

Everything here is checked on the server. The browser sends Pokémon ids; it is never trusted to say what is legal.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import species_data


class FormatError(ValueError):
    pass


@dataclass(frozen=True)
class Format:
    id: str
    name: str
    blurb: str
    bring: int                          # Pokémon you may bring to team preview
    pick: int                           # Pokémon you take into the battle (the team size)
    active: int = 1                     # Pokémon on the field per side (1 = singles)
    level_cap: Optional[int] = None     # Pokémon above this level are not allowed
    species_clause: bool = True         # one of each species
    held_items: bool = True
    turn_timer: int = 120               # seconds before a silent player loses the turn
    rated: bool = False
    queue: bool = False                 # can be joined from the matchmaking queue
    restore: bool = True                # fight at full health: your real Pokémon are never touched either way
    legacy: bool = False                # the old auto-picked first-three duel (kept for the Telegram bot)

    def public(self) -> Dict:
        d = asdict(self)
        d.pop("legacy")
        return d


FORMATS: Dict[str, Format] = {f.id: f for f in (
    Format("quick_duel", "Quick Duel", "One Pokémon each. Pick your champion and go.", bring=1, pick=1,
           turn_timer=90, rated=True, queue=True),
    Format("singles_3v3", "3v3 Singles", "Bring up to six, choose three after seeing your opponent's team.", bring=6, pick=3,
           turn_timer=120, rated=True, queue=True),
    Format("singles_6v6", "6v6 Singles", "Full teams. Bring six, use all six.", bring=6, pick=6,
           turn_timer=150, rated=True, queue=True),
    Format("friendly", "Friendly Battle", "A private challenge with rules you set. Never rated.", bring=6, pick=3,
           turn_timer=180, rated=False),
    Format("classic", "Classic Duel", "The original duel: your first three healthy Pokémon.", bring=3, pick=3,
           turn_timer=300, rated=True, restore=False, legacy=True),
)}

FRIENDLY_LIMITS = {"pick": (1, 6), "level_cap": (5, 100), "turn_timer": (30, 300)}


def get(fmt_id: str) -> Format:
    f = FORMATS.get(fmt_id)
    if f is None:
        raise FormatError("Unknown battle format.")
    return f


def listed() -> List[Dict]:
    return [f.public() for f in FORMATS.values() if not f.legacy]


def with_rules(base: Format, rules: Optional[Dict]) -> Format:
    """A friendly battle may tighten its own rules inside fixed limits; every other format ignores `rules`."""
    if base.id != "friendly" or not rules:
        return base
    kw: Dict = {}
    for key in ("pick", "level_cap", "turn_timer"):
        if rules.get(key) is None:
            continue
        v = rules[key]
        lo, hi = FRIENDLY_LIMITS[key]
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise FormatError(f"{key.replace('_', ' ').capitalize()} must be between {lo} and {hi}.")
        kw[key] = v
    for key in ("species_clause", "held_items"):
        if key in rules and rules[key] is not None:
            if not isinstance(rules[key], bool):
                raise FormatError("Rules must be yes or no.")
            kw[key] = rules[key]
    if "pick" in kw:
        kw["bring"] = max(base.bring, kw["pick"])
    return Format(**{**asdict(base), **kw})


def from_state(d: Dict) -> Format:
    """The format a stored match was created with (its custom friendly rules included)."""
    base = get(d.get("id", "classic"))
    return Format(**{**asdict(base), **{k: v for k, v in d.items() if k in asdict(base)}})


# ── eligibility ──

def _types(mon) -> List[str]:
    data = species_data.get(mon.species_name) or {}
    return list(data.get("types") or [])


def problems(fmt: Format, mon) -> List[str]:
    """Why this Pokémon can't be brought to this format (empty = eligible)."""
    out = []
    if mon.is_fainted or mon.current_hp <= 0:
        if not fmt.restore:
            out.append("It has fainted.")
    if fmt.level_cap is not None and mon.level > fmt.level_cap:
        out.append(f"Level {mon.level} is over the level {fmt.level_cap} limit.")
    if not fmt.held_items and getattr(mon, "held_item", None):
        out.append("Held items aren't allowed.")
    if not mon.moves:
        out.append("It knows no moves.")
    return out


def owned(player) -> Dict[str, object]:
    """Every Pokémon the player owns, by id (team first, then the rest of the collection)."""
    mons: Dict[str, object] = {}
    for m in list(player.active_team) + list(player.pokemon_collection):
        mons.setdefault(m.id, m)
    return mons


def check_selection(player, fmt: Format, ids: List[str], bringing: bool = True) -> List[object]:
    """The chosen Pokémon as real objects, in order, or a FormatError saying exactly what is wrong.
    `bringing` is team preview (up to `bring`); the final pick (exactly `pick`) is checked by check_pick()."""
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise FormatError("Choose your Pokémon from the list.")
    if len(set(ids)) != len(ids):
        raise FormatError("You can't bring the same Pokémon twice.")
    pool = owned(player)
    chosen = []
    for i in ids:
        mon = pool.get(i)
        if mon is None:
            raise FormatError("One of those Pokémon isn't yours.")
        chosen.append(mon)
    if not chosen:
        raise FormatError("Choose at least one Pokémon.")
    if len(chosen) > fmt.bring:
        raise FormatError(f"{fmt.name} allows at most {fmt.bring} Pokémon.")
    if bringing and fmt.bring == fmt.pick and len(chosen) != fmt.pick:
        raise FormatError(f"{fmt.name} needs exactly {fmt.pick} Pokémon.")
    for mon in chosen:
        bad = problems(fmt, mon)
        if bad:
            raise FormatError(f"{mon.nickname}: {bad[0]}")
    if fmt.species_clause:
        seen = set()
        for mon in chosen:
            if mon.species_name in seen:
                raise FormatError(f"Only one {mon.species_name.replace('-', ' ').title()} is allowed.")
            seen.add(mon.species_name)
    return chosen


def check_pick(fmt: Format, brought: List[str], picked: List[int]) -> List[int]:
    """Team preview: the indexes (into the brought list) of the Pokémon actually used, in lead order."""
    if not isinstance(picked, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in picked):
        raise FormatError("Choose which Pokémon to use.")
    if len(set(picked)) != len(picked) or any(not 0 <= i < len(brought) for i in picked):
        raise FormatError("Choose from the Pokémon you brought.")
    need = min(fmt.pick, len(brought))
    if len(picked) != need:
        raise FormatError(f"Choose {need} Pokémon for this battle.")
    return picked


def battle_copy(fmt: Format, mon) -> Dict:
    """What the engine fights with: a copy, at full health when the format restores, with no leftover battle state."""
    d = mon.to_dict()
    d["bt"] = None
    if fmt.restore:
        d["current_hp"] = d["max_hp"]
        d["is_fainted"] = False
        d["status"] = None
    return d


def describe(player, fmt: Format) -> List[Dict]:
    """The player's whole collection with a verdict for this format, for the team builder."""
    out = []
    for mon in owned(player).values():
        data = species_data.get(mon.species_name) or {}
        why = problems(fmt, mon)
        out.append({
            "id": mon.id, "species": mon.species_name, "nickname": mon.nickname, "level": mon.level,
            "types": _types(mon), "ability": getattr(mon, "ability", None), "moves": list(mon.moves),
            "hp": mon.current_hp, "max_hp": mon.max_hp, "held_item": getattr(mon, "held_item", None),
            "dex_id": (data.get("id") or (mon.api_data or {}).get("id")),
            "eligible": not why, "reasons": why,
        })
    out.sort(key=lambda r: (not r["eligible"], -r["level"], r["nickname"]))
    return out
