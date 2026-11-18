"""
Train a battle policy that can also switch, on 3-against-3 team battles (tools/team_battle.py).

    python tools/train_team_ai.py                      # train, judge on held-out teams, report
    python tools/train_team_ai.py --out candidate.json # where to write the weights if the policy passes the gate

Method as in train_learned_ai.py: evolution strategies, common seeds, antithetic pairs. The baseline is the
rule-based AI with no voluntary switches. A policy passes only if, on held-out teams, it beats the baseline with a
paired 95% interval above zero. The game does not load these weights: the trainers in the game never switch, so
using a switching policy would need an engine change first.
"""

import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import team_battle as TB                       # noqa: E402
import learned_ai                              # noqa: E402
import train_learned_ai as T1                  # noqa: E402

DEFAULT_OUT = os.path.join(TB.ROOT, "docs", "ai", "team_policy_candidate.json")


# Zero move weights play exactly like the rule-based AI. The switch weights pick the best-damage Pokémon on a
# forced switch (as the baseline does). "never" starts far below the move scores, so voluntary switching has to be
# learned from scratch; "some" starts with a mild preference for switching to a Pokémon that is better placed.
SWITCH_STARTS = {
    "never": {"hp": 0.0, "threat": 0.0, "best_hit": 1.0, "race": 0.0, "gain": 0.0, "cur_threat": 0.0, "bias": -2.5},
    "some": {"hp": 0.0, "threat": -1.0, "best_hit": 1.0, "race": 0.5, "gain": 1.5, "cur_threat": 0.5, "bias": -2.0},
}


def initial_theta(model_rng=None, model="linear", start="never"):
    sw = SWITCH_STARTS[start]
    switch = [sw[f] for f in learned_ai.SWITCH_FEATURES]
    n = learned_ai.MLPPolicy.size() if model == "mlp" else len(learned_ai.FEATURES)
    move = [model_rng.gauss(0, 0.02) for _ in range(n)] if model == "mlp" else [0.0] * n
    return move + switch


def make_policy(theta, model, meta=None):
    return learned_ai.TeamPolicy.from_theta(theta, learned_ai.MLPPolicy if model == "mlp" else learned_ai.LinearPolicy, meta)


def win_rate(policy, teams, seeds):
    wins = total = 0
    for t in teams:
        for s in seeds:
            total += 1
            wins += TB.play_team(t, s, policy)
    return wins / max(1, total)


def paired_diff(policy, teams, seeds):
    diffs = [int(TB.play_team(t, s, policy)) - int(TB.play_team(t, s, None)) for t in teams for s in seeds]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / max(1, n - 1)
    half = 1.96 * math.sqrt(var / n)
    return mean, mean - half, mean + half, n


def evolve(theta, model, generations, pop, sigma, lr, rng, seeds_per_candidate):
    for gen in range(generations):
        seeds = [10_000 + gen * 1000 + i for i in range(seeds_per_candidate)]
        eps = [[rng.gauss(0, 1) for _ in theta] for _ in range(pop // 2)]
        eps += [[-e for e in ep] for ep in eps]
        fits = [win_rate(make_policy([t + sigma * x for t, x in zip(theta, e)], model), TB.TRAIN_TEAMS, seeds) for e in eps]
        mean_f = sum(fits) / len(fits)
        std_f = math.sqrt(sum((f - mean_f) ** 2 for f in fits) / len(fits)) or 1e-9
        grad = [0.0] * len(theta)
        for f, e in zip(fits, eps):
            a = (f - mean_f) / std_f
            for j, x in enumerate(e):
                grad[j] += a * x
        theta = [t + lr / (len(eps) * sigma) * g for t, g in zip(theta, grad)]
        print(f"gen {gen + 1:3d}  mean win rate {mean_f * 100:5.1f}%  best {max(fits) * 100:5.1f}%", flush=True)
    return theta


def switch_rate(policy, teams, seeds):
    """How often the policy switches voluntarily, per battle: a check that it uses the new action at all."""
    count = battles = 0

    class Counting:
        def choose_action(self, bs, usable, mover, target, bench):
            nonlocal count
            kind, choice = policy.choose_action(bs, usable, mover, target, bench)
            count += kind == "switch"
            return kind, choice

        def pick_forced(self, bs, bench, target):
            return policy.pick_forced(bs, bench, target)

    for t in teams:
        for s in seeds:
            battles += 1
            TB.play_team(t, s, Counting())
    return count / max(1, battles)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=40)
    ap.add_argument("--pop", type=int, default=16)
    ap.add_argument("--sigma", type=float, default=0.15)
    ap.add_argument("--lr", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--seeds-per-candidate", type=int, default=30)
    ap.add_argument("--holdout-battles", type=int, default=800)
    ap.add_argument("--model", choices=["linear", "mlp"], default="linear")
    ap.add_argument("--start", choices=sorted(SWITCH_STARTS), default="never", help="initial switch weights")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    theta = evolve(initial_theta(rng, args.model, args.start), args.model, args.generations, args.pop, args.sigma, args.lr, rng,
                   args.seeds_per_candidate)
    policy = make_policy(theta, args.model, {"trained_seed": args.seed, "generations": args.generations, "model": args.model,
                                                  "start": args.start})

    seeds = [900_000 + i for i in range(args.holdout_battles // len(TB.HOLDOUT_TEAMS))]
    mean, lo, hi, n = paired_diff(policy, TB.HOLDOUT_TEAMS, seeds)
    sw = switch_rate(policy, TB.HOLDOUT_TEAMS, seeds[:40])
    print(f"\nheld-out teams ({n} paired battles): learned minus baseline = {mean * 100:+.1f} points "
          f"[{lo * 100:+.1f}, {hi * 100:+.1f}] (95%)")
    print(f"voluntary switches per battle on held-out teams: {sw:.2f}")
    if lo > 0:
        policy.meta.update({"holdout_diff_mean": mean, "holdout_diff_ci": [lo, hi], "holdout_battles": n})
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(policy.to_json())
        print(f"PASSED the gate: weights written to {args.out} (the game does not load them yet)")
        return 0
    print("DID NOT PASS the gate: no weights written.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
