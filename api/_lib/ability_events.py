"""
Event-style abilities: the ones that DO something when something happens (a Pokémon enters battle, is hit by a
contact move, has its stats lowered, a weather starts…) instead of being a flat damage multiplier.

The battle engine calls these hooks; abilities that were previously faked as generic damage tweaks (Intimidate as
"-15% damage taken", Guts as "+20% damage", Magic Bounce as "-10% damage"…) now behave like the real thing.
Weather: sun / rain / sand / hail, five turns, started by Drought / Drizzle / Sand Stream / Snow Warning.
"""

from typing import Dict, Optional, Tuple

# name -> (display, description)
INFO: Dict[str, Tuple[str, str]] = {
    "intimidate": ("Intimidate", "Lowers the foe's Attack when it enters battle"),
    "static": ("Static", "30% chance to paralyze a Pokémon that hits it with a physical move"),
    "flame_body": ("Flame Body", "30% chance to burn a Pokémon that hits it with a physical move"),
    "poison_point": ("Poison Point", "30% chance to poison a Pokémon that hits it with a physical move"),
    "effect_spore": ("Effect Spore", "30% chance to sleep, paralyze or poison an attacker with a physical move"),
    "rough_skin": ("Rough Skin", "Hurts a Pokémon that hits it with a physical move (1/8 of its HP)"),
    "iron_barbs": ("Iron Barbs", "Hurts a Pokémon that hits it with a physical move (1/8 of its HP)"),
    "drought": ("Drought", "Turns the sunlight harsh when it enters battle"),
    "drizzle": ("Drizzle", "Makes it rain when it enters battle"),
    "sand_stream": ("Sand Stream", "Whips up a sandstorm when it enters battle"),
    "snow_warning": ("Snow Warning", "Summons hail when it enters battle"),
    "swift_swim": ("Swift Swim", "Doubles Speed in rain"),
    "chlorophyll": ("Chlorophyll", "Doubles Speed in harsh sunlight"),
    "sand_rush": ("Sand Rush", "Doubles Speed in a sandstorm"),
    "slush_rush": ("Slush Rush", "Doubles Speed in hail"),
    "guts": ("Guts", "Attack is 1.5x while it has a status condition (and burn doesn't halve it)"),
    "huge_power": ("Huge Power", "Doubles Attack"),
    "pure_power": ("Pure Power", "Doubles Attack"),
    "technician": ("Technician", "Moves with 60 power or less hit 1.5x harder"),
    "adaptability": ("Adaptability", "Same-type moves get a 2x bonus instead of 1.5x"),
    "thick_fat": ("Thick Fat", "Halves damage from Fire and Ice moves"),
    "levitate": ("Levitate", "Immune to Ground-type moves"),
    "shell_armor": ("Shell Armor", "Can't be hit by critical hits"),
    "battle_armor": ("Battle Armor", "Can't be hit by critical hits"),
    "magic_bounce": ("Magic Bounce", "Reflects status moves back at the user"),
    "competitive": ("Competitive", "Sharply raises Sp. Atk when a stat is lowered by a foe"),
    "defiant": ("Defiant", "Sharply raises Attack when a stat is lowered by a foe"),
    "rain_dish": ("Rain Dish", "Restores a little HP each turn in rain"),
    "inner_focus": ("Inner Focus", "Can't be made to flinch"),
    "snow_cloak": ("Snow Cloak", "Harder to hit in hail"),
    "speed_boost": ("Speed Boost", "Raises Speed by one stage at the end of every turn"),
    "moxie": ("Moxie", "Raises Attack by one stage after knocking out a foe"),
    "insomnia": ("Insomnia", "Can't fall asleep"),
    "vital_spirit": ("Vital Spirit", "Can't fall asleep"),
    "limber": ("Limber", "Can't be paralyzed"),
    "immunity": ("Immunity", "Can't be poisoned"),
    "water_veil": ("Water Veil", "Can't be burned"),
    "magma_armor": ("Magma Armor", "Can't be frozen"),
    "own_tempo": ("Own Tempo", "Can't become confused"),
    "clear_body": ("Clear Body", "Foes can't lower its stats"),
    "white_smoke": ("White Smoke", "Foes can't lower its stats"),
    "hyper_cutter": ("Hyper Cutter", "Foes can't lower its Attack"),
    "flash_fire": ("Flash Fire", "Immune to Fire moves; once hit by one, its own Fire moves are 1.5x"),
    "overcoat": ("Overcoat", "Immune to sandstorm and hail damage"),
    "poison_heal": ("Poison Heal", "Heals 1/8 HP each turn while poisoned instead of taking damage"),
    "magic_guard": ("Magic Guard", "Only takes damage from attacks (no status, weather, recoil or contact damage)"),
    "tinted_lens": ("Tinted Lens", "Not-very-effective moves do double damage"),
    "solid_rock": ("Solid Rock", "Super-effective moves do 0.75x damage"),
    "prism_armor": ("Prism Armor", "Super-effective moves do 0.75x damage"),
    "marvel_scale": ("Marvel Scale", "Defense is 1.5x while it has a status condition"),
    "fur_coat": ("Fur Coat", "Doubles Defense"),
    "heatproof": ("Heatproof", "Halves damage from Fire moves"),
    "rock_head": ("Rock Head", "Takes no recoil damage"),
    "reckless": ("Reckless", "Recoil moves hit 1.2x harder"),
}
EVENT_ABILITIES = set(INFO)

ENTRY_WEATHER = {"drought": "sun", "drizzle": "rain", "sand_stream": "sand", "snow_warning": "hail"}
WEATHER_NAME = {"sun": "harsh sunlight", "rain": "rain", "sand": "a sandstorm", "hail": "hail"}
WEATHER_TURNS = 5
SPEED_WEATHER = {"swift_swim": "rain", "chlorophyll": "sun", "sand_rush": "sand", "slush_rush": "hail"}
CONTACT_STATUS = {"static": "par", "flame_body": "brn", "poison_point": "psn"}
CONTACT_CHIP = {"rough_skin", "iron_barbs"}
NO_CRIT = {"shell_armor", "battle_armor"}
STATUS_BLOCK = {"insomnia": {"slp"}, "vital_spirit": {"slp"}, "limber": {"par"}, "immunity": {"psn", "tox"},
                "water_veil": {"brn"}, "magma_armor": {"frz"}}
NO_DROP_ALL = {"clear_body", "white_smoke"}
SUPER_EFFECTIVE_REDUCE = {"solid_rock", "prism_armor"}


def norm(name) -> Optional[str]:
    return str(name).strip().lower().replace("-", "_").replace(" ", "_") if name else None


def speed_mult(ability, weather) -> float:
    a = norm(ability)
    return 2.0 if a in SPEED_WEATHER and SPEED_WEATHER[a] == weather else 1.0


def weather_damage_mult(move_type: str, weather: Optional[str]) -> float:
    if weather == "sun":
        return 1.5 if move_type == "fire" else 0.5 if move_type == "water" else 1.0
    if weather == "rain":
        return 1.5 if move_type == "water" else 0.5 if move_type == "fire" else 1.0
    return 1.0


def chip_immune(types, weather) -> bool:
    types = [t.lower() for t in types]
    if weather == "sand":
        return any(t in types for t in ("rock", "ground", "steel"))
    if weather == "hail":
        return "ice" in types
    return True
