"""Daily boss and EXP All logic shared by the web API and the Telegram bot."""

import logging
from typing import Dict, Optional, Tuple

from daily_boss_system import DailyBoss, BossRewards, daily_boss_system, today_key
from exp_all_system import ExpAllItem
from moves_database import MOVES_DATABASE
from pokemon_model import PokemonInstance

logger = logging.getLogger(__name__)

# The players table has no column for "last boss win", so it rides along in the
# (jsonb) inventory dict. The leading underscore marks it as internal — it is
# filtered out of every player-facing inventory listing (see public_inventory).
BOSS_CLAIM_KEY = "_boss_last_win"

# Boss is scaled DOWN to the player so the fight is beatable: never above its
# own level, never more than this many levels above the player's lead.
BOSS_LEVEL_LEAD = 6
BOSS_MIN_LEVEL = 10


def public_inventory(player) -> Dict[str, int]:
    return {k: v for k, v in player.inventory.items() if not str(k).startswith("_")}


def is_claimed_today(player) -> bool:
    return player.inventory.get(BOSS_CLAIM_KEY) == today_key()


def scaled_boss(template: DailyBoss, lead_level: int) -> DailyBoss:
    """The tier's boss at a level just above your lead (never a wall: +2 at the start, +6 late game)."""
    level = max(5, min(100, lead_level + daily_boss_system.level_offset(template.tier)))
    return DailyBoss(template.species, level, template.moves, template.ability, template.nature,
                     template.iv_boost, tier=template.tier)


def template_for(lead_level: int) -> DailyBoss:
    return daily_boss_system.get_boss_for_level(lead_level)


def _usable_move_names(raw_moves) -> list:
    from rules import MOVE_DATA
    names = []
    for m in raw_moves:
        key = m.lower().replace("_", "-").replace(" ", "-")
        d = MOVE_DATA.get(key)
        if d and d["p"] > 0:
            names.append(key)
    return names


def build_boss_pokemon(lead_level: int) -> Tuple[PokemonInstance, DailyBoss]:
    """Today's boss for the player's tier as a battle-ready Pokemon, scaled to the player's lead."""
    boss = scaled_boss(template_for(lead_level), lead_level)

    mon = PokemonInstance(boss.species, boss.level, 0)
    if boss.tier >= 3:
        moves = _usable_move_names(boss.moves)
        for m in getattr(mon, "moves", []) or []:
            if len(moves) >= 4:
                break
            if m not in moves:
                moves.append(m)
        mon.moves = (moves or ["tackle"])[:4]
        mon.iv = {k: 31 for k in mon.iv}          # late bosses roll perfect IVs
        mon.nature = boss.nature
        if boss.ability:
            mon.ability = boss.ability.lower()
    elif boss.ability:
        mon.ability = boss.ability.lower()
    mon.is_boss = True
    mon.boss_tier = boss.tier
    mon.recalculate_stats()
    mon.restore_hp()
    return mon, boss


def boss_victory(player, boss: DailyBoss, hp_ratio_lost: float) -> Dict:
    """Apply coins/items and mark today as claimed. XP is returned, not applied —
    the caller decides who gets it (fighter only, or split by EXP All)."""
    ratio = min(1.0, max(0.0, hp_ratio_lost))
    rewards = BossRewards.calculate_rewards(boss.level, boss, True, ratio)
    player.add_coins(rewards["coins"])
    for name, qty in rewards["items"]:
        player.add_item(name, qty)
    player.inventory[BOSS_CLAIM_KEY] = today_key()
    return {
        "xp": rewards["xp"],
        "coins": rewards["coins"],
        "items": [[n, q] for n, q in rewards["items"]],
        "flawless": ratio < 0.5,
    }


def award_battle_xp(player, fighter, xp: int, use_exp_all: bool = False, flag: Optional[Dict] = None) -> Dict:
    """Give battle XP. With EXP All (and one in the bag) the XP is split evenly across the
    healthy active team and one EXP All is consumed; otherwise only the fighter gets it.

    `fighter` may be a copy of the team member (the API rebuilds Pokemon from dicts each
    request), so it is swapped into the team by id first."""
    for i, m in enumerate(player.active_team):
        if m.id == fighter.id:
            player.active_team[i] = fighter
            break

    # `flag` is for multi-Pokemon trainer battles: the first KO with EXP All switched on pays for ONE EXP All,
    # the rest of that trainer battle shares XP for free (flag["exp"] remembers it).
    paid = bool(flag and flag.get("exp"))
    if use_exp_all and (paid or ExpAllItem.has_item(player)):
        result = ExpAllItem.use(player, xp, free=paid)
        if result.get("success"):
            if not paid:
                ExpAllItem.remove_from_inventory(player)
                if flag is not None:
                    flag["exp"] = True
            return {
                "used": True,
                "per_pokemon": result["per_pokemon"],
                "pokemon_count": result["pokemon_count"],
                "level_ups": result["level_ups"],
            }

    leveled = fighter.add_experience(xp)
    return {
        "used": False,
        "per_pokemon": xp,
        "pokemon_count": 1,
        "level_ups": [f"{fighter.nickname} → Lv {fighter.level}!"] if leveled else [],
    }
