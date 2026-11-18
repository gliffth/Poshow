"""
Headless battle runner and difficulty report.

    python tools/balance_sim.py                     # the default matchups, 200 battles each
    python tools/balance_sim.py --n 500 --seed 7

For each matchup it plays many battles with the real battle engine (execute_turn) and reports the player's win
rate at each level offset, so difficulty can be judged from measured numbers. It never changes game data.

The opponent is a trainer (smart=True), so it picks with the game's battle AI. Wild Pokémon pick at random in the
engine, which is why this runner models trainers and gyms only. The player's side uses the same heuristic, scored
from the player's own perspective (battle_ai._score with the player as attacker), as a stand-in for a reasonable
player. Results depend on the seed and sample size; the report prints both so a difference can be checked against
the noise.

This is also step 1 of the learning battle AI (roadmap §7.5): a battle that can be run without a server or a
browser, and one that can be replayed with a fixed seed.
"""

import argparse
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.path.insert(0, os.path.join(ROOT, "api", "_lib"))

from battle_system import BattleSystem   # noqa: E402
from pokemon_model import PokemonInstance  # noqa: E402
import battle_ai  # noqa: E402
import logging  # noqa: E402

logging.disable(logging.INFO)     # the engine logs every created Pokémon; the runner only needs results

MAX_TURNS = 200

# (label, player species, player level, opponent species, opponent level)
MATCHUPS = [
    ("starter vs route trainer", "charmander", 12, "rattata", 10),
    ("starter vs route trainer (2 levels up)", "charmander", 14, "rattata", 10),
    ("mid-game vs gym-style", "gyarados", 30, "geodude", 30),
    ("mid-game vs gym-style (+5)", "gyarados", 35, "geodude", 30),
]
OFFSETS = [-4, -2, 0, 2, 4]


def player_move(bs, usable):
    """The player's stand-in: the battle AI's score, from the PLAYER's side (bs.p attacking bs.o).
    battle_ai.choose_move scores from bs.o, so it can't be used for the player without swapping sides."""
    return max(usable, key=lambda m: battle_ai._score(bs, bs.p, bs.o, m))


def battle_once(player_species, player_level, opp_species, opp_level, rng: random.Random):
    random.seed(rng.randrange(2 ** 31))
    p = PokemonInstance(player_species, player_level, 0)
    o = PokemonInstance(opp_species, opp_level, 0)
    bs = BattleSystem(p, o, smart=True)     # trainer-style opponent: the battle AI picks its moves
    for _ in range(MAX_TURNS):
        usable = bs.get_player_moves()
        if not usable:
            return "loss", bs.turn if hasattr(bs, "turn") else 0
        pm = player_move(bs, usable)
        om = bs.get_opponent_move()
        res = bs.execute_turn(pm, om)
        if res.get("is_finished"):
            return ("win" if res.get("winner") == "player" else "loss"), bs.turn if hasattr(bs, "turn") else 0
    return "draw", MAX_TURNS


def wilson(wins: int, n: int, z: float = 1.96):
    """95% confidence interval for a win rate."""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def run(matchups, n: int, seed: int, offsets=OFFSETS):
    rng = random.Random(seed)
    report = []
    for label, ps, pl, osp, ol in matchups:
        rows = []
        for off in offsets:
            wins = losses = draws = 0
            for _ in range(n):
                result, _turns = battle_once(ps, max(1, pl + off), osp, ol, rng)
                if result == "win":
                    wins += 1
                elif result == "loss":
                    losses += 1
                else:
                    draws += 1
            lo, hi = wilson(wins, n)
            rows.append({"offset": off, "win_rate": wins / n, "ci": (lo, hi), "draws": draws})
        report.append({"label": label, "rows": rows})
    return report


def print_report(report, n: int, seed: int):
    print(f"Win rate of the player's team by level offset ({n} battles per cell, seed {seed}, 95% interval)\n")
    for m in report:
        print(m["label"])
        for r in m["rows"]:
            lo, hi = r["ci"]
            print(f"  level {r['offset']:+d}: {r['win_rate'] * 100:5.1f}%  [{lo * 100:4.1f}–{hi * 100:4.1f}]"
                  + (f"  draws {r['draws']}" if r["draws"] else ""))
        print()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)
    report = run(MATCHUPS, args.n, args.seed)
    print_report(report, args.n, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
