"""
🛡️ POSHOW — admin tools (shared by the website's Admin panel and the Telegram bot)

Who is an admin?  Anyone whose user id is in ADMIN_USER_IDS (comma-separated, env var) or whose web
username is in ADMIN_USERNAMES, plus the ids already hardcoded in admin_panel.py for the bot.
Admin status is checked from the signed login token on the server — the website only hides the panel.

Admins can find a player by username (or id) and give them credits, items, Poké Balls or a Pokémon,
fully heal them, or change the images the scenes use (see scenes / site_assets).
"""

import logging
import os
import re
from typing import Dict, List, Optional

from pokemon_model import PokemonInstance

logger = logging.getLogger(__name__)

try:
    from admin_panel import AdminPanel
    _LEGACY_IDS = set(AdminPanel.ADMIN_IDS)
except Exception:          # pragma: no cover
    _LEGACY_IDS = set()

NAME_RE = re.compile(r"^[a-z0-9_]{1,40}$")
BALLS = ("pokeball", "greatball", "ultraball", "masterball")
MAX_QTY = 9999


def _env_ids() -> set:
    out = set()
    for part in os.environ.get("ADMIN_USER_IDS", "").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _env_names() -> set:
    return {n.strip().lower() for n in os.environ.get("ADMIN_USERNAMES", "").split(",") if n.strip()}


def is_admin(user_id: Optional[int], username: Optional[str] = None) -> bool:
    if user_id is not None and (user_id in _env_ids() or user_id in _LEGACY_IDS):
        return True
    return bool(username) and username.strip().lower() in _env_names()


class AdminError(ValueError):
    pass


def _clean_name(name: str) -> str:
    name = (name or "").strip().lower().replace("-", "_")
    if not NAME_RE.match(name):
        raise AdminError(f"'{name}' isn't a valid item name.")
    return name


def give(player, coins: int = 0, items: Optional[Dict[str, int]] = None, balls: Optional[Dict[str, int]] = None,
         pokemon: Optional[Dict] = None, heal: bool = False) -> List[str]:
    """Apply a gift to an (already loaded) player. Returns human-readable lines. Caller persists."""
    done: List[str] = []
    if coins:
        coins = int(coins)
        player.coins = max(0, player.coins + coins)
        done.append(f"{'+' if coins > 0 else ''}{coins} credits (now {player.coins})")
    for name, qty in (items or {}).items():
        qty = int(qty)
        if not qty:
            continue
        name = _clean_name(name)
        if abs(qty) > MAX_QTY:
            raise AdminError(f"Quantity must be within ±{MAX_QTY}.")
        if qty > 0:
            player.add_item(name, qty)
        else:
            player.remove_item(name, -qty)
        done.append(f"{qty:+d} {name.replace('_', ' ')}")
    for name, qty in (balls or {}).items():
        qty = int(qty)
        if not qty:
            continue
        name = _clean_name(name)
        if name not in BALLS:
            raise AdminError(f"Unknown ball: {name}.")
        player.pokeballs[name] = max(0, player.pokeballs.get(name, 0) + qty)
        done.append(f"{qty:+d} {name}")
    if pokemon:
        species = _clean_name(str(pokemon.get("species", "")).replace(" ", "-")) if False else str(pokemon.get("species", "")).strip().lower().replace(" ", "-")
        level = int(pokemon.get("level", 5))
        if not species or not 1 <= level <= 100:
            raise AdminError("Pokémon needs a species and a level from 1 to 100.")
        try:
            mon = PokemonInstance(species, level, player.user_id)
        except Exception as e:
            raise AdminError(f"Couldn't create {species}: {e}")
        if pokemon.get("shiny"):
            mon.is_shiny = True
        if len(player.active_team) < 6:
            player.add_pokemon_to_team(mon)
            where = "team"
        else:
            player.pokemon_collection.append(mon)
            where = "storage (team is full)"
        done.append(f"{mon.nickname} Lv{level}{' ✨' if mon.is_shiny else ''} → {where}")
    if heal:
        import care
        for mon in list(player.active_team):
            mon.restore_hp()
            care._set_vit(player, mon, care.max_vitality(mon))
        done.append("whole team fully healed (critical ones revived)")
    if not done:
        raise AdminError("Nothing to give.")
    return done


def player_summary(player) -> Dict:
    import care
    return {
        "user_id": player.user_id,
        "username": player.username,
        "coins": player.coins,
        "region": player.current_region,
        "badges": list(player.badges),
        "inventory": {k: v for k, v in player.inventory.items() if not str(k).startswith("_")},
        "pokeballs": dict(player.pokeballs),
        "team": [{"nickname": m.nickname, "species": m.species_name, "level": m.level,
                  "state": care.condition(player, m)["state"]} for m in player.active_team],
        "stored": len(player.pokemon_collection),
    }


# ── images ──────────────────────────────────────────────────────────
ASSET_KEYS = (
    ["region_" + r for r in ("kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "paldea")]
    + ["route", "town", "care_center", "starter_lab", "gym", "league"]
)
_URL_RE = re.compile(r"^(https://[^\s]+|/[A-Za-z0-9_./-]+)$")


def valid_asset_key(key: str) -> bool:
    return key in ASSET_KEYS


def valid_asset_url(url: str) -> bool:
    return bool(_URL_RE.match(url or "")) and len(url) < 500


def admin_ids() -> set:
    """Every user id that is an admin (for notifications)."""
    return set(_env_ids()) | set(_LEGACY_IDS)
