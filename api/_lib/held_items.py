"""
Held items (roadmap §3F): an item a Pokémon carries. Its effect applies in battle, and only one can be held at a time.

Rules implemented here (Gen 5+ behaviour, to be checked against the games):
  Leftovers   restores 1/16 of max HP at the end of every turn, while the holder is alive and hurt.
  Life Orb    damaging moves deal 30% more. The holder loses 1/10 of max HP once after each turn in which it
              landed a damaging hit (this can knock out the holder).
  Focus Sash  at full HP, a single hit that would knock the holder out leaves it on 1 HP instead. Used up.

Everything here is pure: the battle engine calls these functions and stores the result, so the rules can be tested
without a battle. The item is consumed by the battle that uses it, and the change is saved with the Pokémon.
"""

from typing import Optional

HELD_ITEMS = {
    "leftovers":   {"name": "Leftovers",   "effect": "Restores 1/16 of max HP at the end of each turn."},
    "life-orb":    {"name": "Life Orb",    "effect": "Damaging moves deal 30% more. The holder loses 1/10 max HP after it hits."},
    "focus-sash":  {"name": "Focus Sash",  "effect": "At full HP, survives one knock-out hit with 1 HP. Used up when it does."},
    "choice-band":  {"name": "Choice Band",  "effect": "Attack x1.5, but the holder can only use the first move it picks."},
    "choice-specs": {"name": "Choice Specs", "effect": "Sp. Atk x1.5, but the holder can only use the first move it picks."},
    "choice-scarf": {"name": "Choice Scarf", "effect": "Speed x1.5, but the holder can only use the first move it picks."},
}

# Choice items: the stat each one boosts. The holder is locked into its first move until it switches out.
CHOICE_STAT = {"choice-band": "atk", "choice-specs": "spa", "choice-scarf": "spe"}

LIFE_ORB_BOOST = 1.3


def is_held_item(item: Optional[str]) -> bool:
    return bool(item) and item in HELD_ITEMS


def damage_multiplier(item: Optional[str], category: str) -> float:
    """Life Orb boosts damaging moves only (status moves deal no damage)."""
    if item == "life-orb" and category != "status":
        return LIFE_ORB_BOOST
    return 1.0


def recoil_after_turn(item: Optional[str], max_hp: int, landed_damage: bool) -> int:
    """Life Orb recoil, applied once per turn in which the holder dealt damage."""
    if item == "life-orb" and landed_damage:
        return max(1, max_hp // 10)
    return 0


def end_of_turn_heal(item: Optional[str], max_hp: int, hp: int) -> int:
    """HP Leftovers restores this turn (0 if not applicable or already full)."""
    if item != "leftovers" or hp <= 0 or hp >= max_hp:
        return 0
    return min(max_hp - hp, max(1, max_hp // 16))


def locks_move(item: Optional[str]) -> bool:
    return item in CHOICE_STAT


def stat_multiplier(item: Optional[str], stat: str) -> float:
    """A Choice item boosts its one stat by 1.5. Other items don't change stats."""
    return 1.5 if CHOICE_STAT.get(item) == stat else 1.0


def sash_saves(item: Optional[str], hp: int, max_hp: int, damage: int) -> bool:
    """True when a Focus Sash must turn this hit into a 1 HP survival."""
    return item == "focus-sash" and hp == max_hp and damage >= hp


def equip(player, pokemon, item: str) -> dict:
    """Put a held item on a Pokémon. Swaps out whatever it held (which returns to the bag). Returns {ok, message}."""
    if not is_held_item(item):
        return {"ok": False, "message": f"{item} can't be held."}
    if player.inventory.get(item, 0) < 1:
        return {"ok": False, "message": f"You don't have a {HELD_ITEMS[item]['name']}."}
    if pokemon.held_item == item:
        return {"ok": False, "message": f"{pokemon.nickname} is already holding a {HELD_ITEMS[item]['name']}."}
    previous = pokemon.held_item
    player.remove_item(item, 1)
    if previous:
        player.add_item(previous, 1)
    pokemon.held_item = item
    msg = f"{pokemon.nickname} is now holding a {HELD_ITEMS[item]['name']}."
    if previous:
        msg += f" The {HELD_ITEMS[previous]['name']} went back to your bag."
    return {"ok": True, "message": msg}


def unequip(player, pokemon) -> dict:
    """Take a held item back into the bag."""
    if not pokemon.held_item:
        return {"ok": False, "message": f"{pokemon.nickname} isn't holding anything."}
    item = pokemon.held_item
    pokemon.held_item = None
    player.add_item(item, 1)
    return {"ok": True, "message": f"{pokemon.nickname} gave back its {HELD_ITEMS[item]['name']}."}
