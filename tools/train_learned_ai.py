"""
Train the learned battle policy (roadmap §7.5).

    python tools/train_learned_ai.py                 # train, evaluate on held-out matchups, ship only if it wins
    python tools/train_learned_ai.py --record d.jsonl  # also write the developer recording of baseline decisions
    python tools/train_learned_ai.py --no-ship       # train and report only

Method: evolution strategies over the policy's weights (api/_lib/learned_ai.py). Every candidate plays the same
battles (common seeds), so the comparison between candidates is fair. The rule-based battle AI is the baseline.

Shipping rule (the only way weights reach the game): on MATCHUPS THE TRAINING NEVER SAW, the learned policy must
beat the rule-based AI with a paired 95% interval whose lower bound is above zero. Anything else is reported and
not saved, so the game keeps the rule-based AI.

Battles are the engine's own. Trainer opponents use smart=True (the battle AI), as gyms and story trainers do.
"""

import argparse
import json
import logging
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.path.insert(0, os.path.join(ROOT, "api", "_lib"))
logging.disable(logging.INFO)

from battle_system import BattleSystem          # noqa: E402
from pokemon_model import PokemonInstance       # noqa: E402
import battle_ai                                # noqa: E402
import learned_ai                               # noqa: E402

MAX_TURNS = 200

# Opponent a little stronger than the player, so the baseline wins most but not all battles (room to improve).
TRAIN_MATCHUPS = [
    ("charmander", 14, "rattata", 14),
    ("pikachu", 20, "zubat", 21),
    ("gyarados", 30, "geodude", 31),
    ("bulbasaur", 18, "rattata", 18),
]
# Never used in training: the shipping decision is made on these.
HOLDOUT_MATCHUPS = [
    ("squirtle", 18, "pidgey", 18),
    ("eevee", 22, "zubat", 22),
    ("charmander", 16, "geodude", 17),
    ("pikachu", 26, "growlithe", 26),
]


def _baseline_player(bs, usable):
    """The rule-based AI playing the player's side: the same score as the opponent, from the player's own side."""
    return max(usable, key=lambda m: battle_ai._score(bs, bs.p, bs.o, m))


def play(matchup, seed: int, policy=None, record=None):
    """One battle. The player uses `policy` (or the baseline if None). Returns True if the player won."""
    ps, pl, osp, ol = matchup
    random.seed(seed)
    p = PokemonInstance(ps, pl, 0)
    o = PokemonInstance(osp, ol, 0)
    bs = BattleSystem(p, o, smart=True)
    decisions = []
    for _ in range(MAX_TURNS):
        usable = bs.get_player_moves()
        if not usable:
            break
        if policy is not None:
            pm = policy.choose(bs, usable, mover=bs.p, target=bs.o)
        else:
            pm = _baseline_player(bs, usable)
        if record is not None:
            decisions.append({"side": "player", "legal": [m.name for m in usable],
                              "features": {m.name: learned_ai.move_features(bs, bs.p, bs.o, m) for m in usable},
                              "chosen": pm.name, "policy": "learned" if policy is not None else "baseline"})
        om = bs.get_opponent_move()
        res = bs.execute_turn(pm, om)
        if res.get("is_finished"):
            won = res.get("winner") == "player"
            if record is not None:
                record.append({"matchup": list(matchup), "seed": seed, "won": won, "decisions": decisions})
            return won
    if record is not None:
        record.append({"matchup": list(matchup), "seed": seed, "won": False, "decisions": decisions, "timeout": True})
    return False


def win_rate(policy, matchups, seeds):
    wins = total = 0
    for mu in matchups:
        for s in seeds:
            total += 1
            wins += play(mu, s, policy)
    return wins / max(1, total)


def paired_diff(policy, matchups, seeds):
    """Per battle: learned win (1/0) minus baseline win on the SAME seed. Returns (mean, lo95, hi95, n)."""
    diffs = []
    for mu in matchups:
        for s in seeds:
            diffs.append((1 if play(mu, s, policy) else 0) - (1 if play(mu, s, None) else 0))
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / max(1, n - 1)
    half = 1.96 * math.sqrt(var / n)
    return mean, mean - half, mean + half, n


def evolve(theta, generations, pop, sigma, lr, battles_seed, rng, seeds_per_candidate=20, make=None):
    make = make or learned_ai.LinearPolicy
    best_theta, best_fit = list(theta), -1.0
    for gen in range(generations):
        seeds = [battles_seed + gen * 1000 + i for i in range(seeds_per_candidate)]   # common random numbers
        eps = [[rng.gauss(0, 1) for _ in theta] for _ in range(pop // 2)]
        eps = eps + [[-e for e in ep] for ep in eps]                         # antithetic pairs
        fits = []
        for e in eps:
            cand = [t + sigma * x for t, x in zip(theta, e)]
            fits.append(win_rate(make(cand), TRAIN_MATCHUPS, seeds))
        mean_f = sum(fits) / len(fits)
        std_f = math.sqrt(sum((f - mean_f) ** 2 for f in fits) / len(fits)) or 1e-9
        grad = [0.0] * len(theta)
        for f, e in zip(fits, eps):
            a = (f - mean_f) / std_f
            for j, x in enumerate(e):
                grad[j] += a * x
        theta = [t + lr / (len(eps) * sigma) * g for t, g in zip(theta, grad)]
        top = max(fits)
        if top > best_fit:
            best_fit = top
        print(f"gen {gen + 1:3d}  mean win rate {mean_f * 100:5.1f}%  best {top * 100:5.1f}%", flush=True)
    return theta


def initial_weights():
    """A sensible start: prefer damaging, effective, accurate moves and finishing hits. ES then refines it."""
    w = {"power": 0.2, "effectiveness": 0.5, "stab": 0.3, "accuracy": 0.1, "is_status": -0.2, "pp_left": 0.0,
         "my_hp": 0.0, "their_hp": 0.0, "damage_share": 0.5, "kill": 0.5, "speed_edge": 0.1, "est_frac": 1.0,
         "reply_frac": 0.0, "survives": 0.0, "race": 0.0, "bias": 0.0}
    return [w[f] for f in learned_ai.FEATURES]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=30)
    ap.add_argument("--pop", type=int, default=16)
    ap.add_argument("--sigma", type=float, default=0.15)
    ap.add_argument("--lr", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--holdout-battles", type=int, default=150)
    ap.add_argument("--seeds-per-candidate", type=int, default=20,
                    help="battles per matchup that each candidate plays per generation (less noise, more time)")
    ap.add_argument("--record", help="write the developer recording (baseline decisions) to this JSONL file")
    ap.add_argument("--no-ship", action="store_true")
    ap.add_argument("--model", choices=["linear", "mlp"], default="linear")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    if args.record:
        rec = []
        for mu in TRAIN_MATCHUPS:
            for s in range(args.seed, args.seed + 25):
                play(mu, s, None, record=rec)
        with open(args.record, "w", encoding="utf-8") as f:
            for row in rec:
                f.write(json.dumps(row) + "\n")
        print(f"recorded {len(rec)} baseline battles to {args.record}")

    if args.model == "mlp":
        make = learned_ai.MLPPolicy
        start = [rng.gauss(0, 0.3) for _ in range(learned_ai.MLPPolicy.size())]
    else:
        make = learned_ai.LinearPolicy
        start = initial_weights()
    theta = evolve(start, args.generations, args.pop, args.sigma, args.lr, 10_000, rng,
                   seeds_per_candidate=args.seeds_per_candidate, make=make)
    policy = make(theta, {"trained_seed": args.seed, "generations": args.generations, "model": args.model,
                          "train_matchups": TRAIN_MATCHUPS})

    hold_seeds = [900_000 + i for i in range(args.holdout_battles // len(HOLDOUT_MATCHUPS))]
    mean, lo, hi, n = paired_diff(policy, HOLDOUT_MATCHUPS, hold_seeds)
    print(f"\nheld-out matchups ({n} paired battles): learned minus baseline = {mean * 100:+.1f} points "
          f"[{lo * 100:+.1f}, {hi * 100:+.1f}] (95%)")
    ship = lo > 0 and not args.no_ship
    policy.meta.update({"holdout_diff_mean": mean, "holdout_diff_ci": [lo, hi], "holdout_battles": n})
    if ship:
        policy.save()
        print(f"SHIPPED: weights written to {learned_ai.DEFAULT_WEIGHTS_PATH}")
    else:
        print("NOT SHIPPED: the learned policy did not beat the rule-based AI on held-out matchups "
              "with a confidence interval above zero. The game keeps the rule-based AI.")
    return 0 if ship or args.no_ship else 2


if __name__ == "__main__":
    sys.exit(main())
