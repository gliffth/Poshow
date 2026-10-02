"""
POSHOW — new-player onboarding, shared by the website (api/index.py) and the Telegram bot.

Flow: avatar -> region -> starter. Both front-ends end up in create_player_with_starter(), so a
Telegram trainer and a web trainer are created by exactly the same code.
"""

from typing import Dict, List, Optional, Tuple

import avatars
from pokemon_model import PokemonInstance
from move_learning_system import get_moves_by_level

STARTERS: Dict[str, List[Tuple[str, int]]] = {
    "kanto":  [("bulbasaur", 1), ("charmander", 4), ("squirtle", 7)],
    "johto":  [("chikorita", 152), ("cyndaquil", 155), ("totodile", 158)],
    "hoenn":  [("treecko", 252), ("torchic", 255), ("mudkip", 258)],
    "sinnoh": [("turtwig", 387), ("chimchar", 390), ("piplup", 393)],
    "unova":  [("snivy", 495), ("tepig", 498), ("oshawott", 501)],
    "kalos":  [("chespin", 650), ("fennekin", 653), ("froakie", 656)],
    "alola":  [("rowlet", 722), ("litten", 725), ("popplio", 728)],
    "galar":  [("grookey", 810), ("scorbunny", 813), ("sobble", 816)],
    "paldea": [("sprigatito", 906), ("fuecoco", 909), ("quaxly", 912)],
}

REGION_NAMES = {r: r.title() for r in STARTERS}
PROFESSORS = {"kanto": "Oak", "johto": "Elm", "hoenn": "Birch", "sinnoh": "Rowan", "unova": "Juniper",
              "kalos": "Sycamore", "alola": "Kukui", "galar": "Magnolia", "paldea": "Sada"}
STARTER_EMOJI = {0: "🌿", 1: "🔥", 2: "💧"}      # every generation orders them grass / fire / water


class OnboardingError(ValueError):
    pass


def has_starter(player) -> bool:
    return bool(player.active_team or player.pokemon_collection)


def create_player_with_starter(player, region: str, species: str, avatar: Optional[str] = None) -> PokemonInstance:
    """Mutates `player` (adds the starter, sets region + avatar). The caller persists it."""
    region = (region or "").lower()
    options = dict(STARTERS.get(region, []))
    if not options:
        raise OnboardingError(f"Unknown region: {region}")
    species = (species or "").lower()
    if species not in options:
        raise OnboardingError(f"{species} isn't a starter in {region.title()}.")
    if has_starter(player):
        raise OnboardingError("You already chose a starter.")
    if avatar is not None and not avatars.is_valid(avatar):
        raise OnboardingError(f"Unknown avatar: {avatar}")

    mon = PokemonInstance(species, 5, player.user_id)
    learned = get_moves_by_level(species, 5)
    if learned:
        mon.moves = learned[:4]
    player.add_pokemon_to_team(mon)
    player.current_region = region
    player.regions_unlocked = [region]
    player.avatar = avatar or avatars.DEFAULT_AVATAR

    import journey  # local import: journey depends on the player model, not the other way round
    journey.init_story(player)
    return mon
