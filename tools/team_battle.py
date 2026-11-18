"""
Headless team battles (3 against 3) under the game's own rules, for training and judging the battle AI.

  * every turn the engine is rebuilt from the Pokémon, as the API does, so HP, PP, status and stat stages carry over
  * a voluntary switch costs the turn: the new Pokémon comes in and the opponent gets a free hit
  * a fainted Pokémon is replaced for free, with no free hit
  * the opponent is the trainer AI (smart=True) and never switches on its own, as in the game; it sends out its
    next Pokémon when one faints
"""

import logging
import os
import random
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.path.insert(0, os.path.join(ROOT, "api", "_lib"))
logging.disable(logging.INFO)

from battle_system import BattleSystem, Combatant   # noqa: E402
from pokemon_model import PokemonInstance           # noqa: E402
import battle_ai                                    # noqa: E402
import learned_ai                                   # noqa: E402

MAX_TURNS = 300

# (our team, their team). Opponent levels are set so the baseline wins roughly 30-75% of each matchup.
TRAIN_TEAMS = [
    ([("charmander", 18), ("squirtle", 18), ("bulbasaur", 18)], [("geodude", 18), ("zubat", 18), ("growlithe", 18)]),
    ([("pikachu", 22), ("pidgey", 22), ("rattata", 22)], [("gastly", 20), ("machop", 20), ("geodude", 20)]),
    ([("eevee", 25), ("growlithe", 25), ("zubat", 25)], [("squirtle", 26), ("bulbasaur", 26), ("pikachu", 26)]),
    ([("machop", 20), ("abra", 20), ("geodude", 20)], [("pidgey", 21), ("rattata", 21), ("charmander", 21)]),
]
# Never used in training: the shipping decision is made on these.
HOLDOUT_TEAMS = [
    ([("squirtle", 22), ("pikachu", 22), ("zubat", 22)], [("geodude", 25), ("growlithe", 25), ("rattata", 25)]),
    ([("bulbasaur", 24), ("machop", 24), ("pidgey", 24)], [("gastly", 23), ("zubat", 24), ("charmander", 24)]),
    ([("charmander", 20), ("geodude", 20), ("eevee", 20)], [("squirtle", 22), ("abra", 22), ("pidgey", 22)]),
    ([("growlithe", 28), ("gastly", 28), ("rattata", 28)], [("bulbasaur", 31), ("machop", 31), ("pikachu", 31)]),
]


def _mon(species: str, level: int) -> PokemonInstance:
    """A Pokémon whose id (and so its ability) comes from the seeded RNG; uuid4 alone would make seeds irreproducible."""
    real = uuid.uuid4
    uuid.uuid4 = lambda: uuid.UUID(int=random.getrandbits(128), version=4)
    try:
        return PokemonInstance(species, level, 0)
    finally:
        uuid.uuid4 = real


def _usable(bs):
    moves = bs.get_player_moves()
    return [m for m in moves if bs.pp_left(bs.p, m) > 0] or moves


def _alive(team, exclude=None):
    return [m for m in team if m.current_hp > 0 and m is not exclude]


class Baseline:
    """The rule-based AI: the trainer move scorer from the player's side, no voluntary switches, and the
    best-damage Pokémon sent in when one faints."""

    def choose_action(self, bs, usable, mover, target, bench):
        return "move", max(usable, key=lambda m: battle_ai._score(bs, bs.p, bs.o, m))

    def pick_forced(self, bs, bench, target):
        return max(bench, key=lambda m: min(2.0, learned_ai._best_hit(bs, Combatant(m, m.current_hp), target)))   # 2.0 = the feature's cap


def _forced(policy, bs, bench, target):
    if hasattr(policy, "pick_forced"):
        return policy.pick_forced(bs, bench, target)
    return policy.pick_switch(bs, bench, target, None)[0]


def play_team(matchup, seed: int, policy=None) -> bool:
    """One team battle. `policy` plays our side (the baseline when None). True if we win."""
    policy = policy or Baseline()
    random.seed(seed)
    mine = [_mon(s, l) for s, l in matchup[0]]
    theirs = [_mon(s, l) for s, l in matchup[1]]
    p, o = mine[0], theirs[0]
    for _ in range(MAX_TURNS):
        bs = BattleSystem(p, o, smart=True)
        usable = _usable(bs)
        if not usable:
            return False
        kind, choice = policy.choose_action(bs, usable, bs.p, bs.o, _alive(mine, p))
        if kind == "switch":
            p = choice
            bs = BattleSystem(p, o, smart=True)
            bs.execute_turn(None, bs.get_opponent_move())
        else:
            bs.execute_turn(choice, bs.get_opponent_move())
        if o.current_hp <= 0:
            left = _alive(theirs)
            if not left:
                return True
            o = left[0]
        if p.current_hp <= 0:
            bench = _alive(mine)
            if not bench:
                return False
            p = _forced(policy, BattleSystem(bench[0], o, smart=True), bench, Combatant(o, o.current_hp))
    return False
