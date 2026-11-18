# Learned battle AI — report (roadmap §7.5)

## Result

**No learned policy beat the rule-based battle AI on held-out matchups, so nothing was shipped.** The game
keeps the rule-based AI. The pipeline is complete and works end to end; the shipping gate did its job by
refusing every candidate.

| Run | Model | Training | Held-out result (learned minus baseline) | Shipped |
|---|---|---|---|---|
| 1 | linear, 12 features | 40 generations, 16 candidates, 20 battles per matchup | −1.7 points, 95% interval [−4.5, +1.2] (240 battles) | no |
| 1b | linear, 12 features | 80 generations, 60 battles per matchup | −5.8 points, [−8.5, −3.0] (400 battles) | no |
| 2 | linear, 13 features (adds an observable damage estimate) | 80 generations, 60 battles per matchup | −2.8 points, [−4.6, −0.9] (400 battles) | no |
| 3 | one hidden layer (8 tanh units), 13 features | 80 generations, 60 battles per matchup | −0.8 points, [−2.6, +1.1] (400 battles) | no |
| 4 | linear, 16 features (adds the lookahead features below) | 80 generations, 60 battles per matchup | −1.8 points, [−4.0, +0.5] (400 battles) | no |
| 5 | one hidden layer, 16 features | 80 generations, 60 battles per matchup, seed 11 | −1.0 points, [−3.0, +1.0] (400 battles) | no |

Runs 3, 4 and 5 are statistically tied with the baseline, not better. Run 1b is clearly worse than the baseline: more training
without the extra feature made the linear policy worse on held-out matchups, which is a sign of overfitting the
training battery. The held-out matchups were never used in training.
The raw output of each run is in this folder.

## Why the gate matters

The shipping rule is strict: on matchups the training never saw, the learned policy must beat the baseline with
a paired 95% interval whose lower bound is above zero. Training fitness alone is noisy (74%–91% from one
generation to the next, even with common random numbers), and a policy can look good on the training battery
and still lose on new ones. Without the held-out gate, a run would have "improved" on paper.

## What the learner can and can't see

It uses only information a legitimate player could know: the move's published data, type matchups, both sides'
current HP (the health bars), base stats from the Pokédex, and the player's own actual stats. It never reads
the opponent's hidden moveset, IVs, or computed stats. A test checks that features do not change when the
opponent's hidden information changes.

## Why it probably can't beat the baseline yet

- The baseline scores moves with a one-step greedy heuristic close to the damage formula. Choosing one move from
  four, that heuristic is already near what a one-step policy can do.
- A rough estimate of the opponent's reply did not help (runs 4 and 5). What is still missing is switching
  decisions, which the policy doesn't make.
- The training battery is four matchups with single Pokémon. A richer battery (full teams, items, switching) is
  needed before any result here generalises.

## Lookahead (runs 4 and 5)

Three features estimate the opponent's likely reply from public information only: the target's types, level and
base attack stats (it is assumed to hit with an 80-power move of each of its own types) against our own defence
and HP. They are the damage that reply takes off us, whether we survive it, and who wins the exchange of hits.
The estimate does not read hidden information (the feature test still passes). It did not change the outcome:
both models are still tied with the baseline on held-out matchups.

## Switching and team battles (runs 6 and 7)

`tools/team_battle.py` plays 3-against-3 battles under the game's rules: a voluntary switch costs the turn and the
opponent gets a free hit, a fainted Pokémon is replaced for free, and the trainer AI never switches. The baseline is
the rule-based AI with no voluntary switches. `tools/train_team_ai.py` trains a policy whose move score is the
rule-based score plus a learned correction, with a learned switch scorer (7 public features). With zero weights it
plays exactly like the baseline (checked on 160 battles). Training uses four team matchups; the gate uses four
other team matchups the training never saw.

| Run | Switch start | Training | Held-out, learned minus baseline | Voluntary switches per battle | Passed |
|---|---|---|---|---|---|
| 6 | never switch | 60 generations, 30 battles per matchup | −1.6 points, [−5.6, +2.3] (800 battles) | 0.00 | no |
| 7 | mild preference to switch | 40 generations, 60 battles per matchup | −4.4 points, [−8.0, −0.8] (800 battles) | 0.00 | no |

Run 7 reached about 60% on its training teams against about 50% for the baseline, and lost on the held-out teams,
so it fitted the four training matchups rather than playing better. Both runs ended up never switching on their own,
which suggests switching does not pay against this opponent under these rules (the free hit costs more than a
better matchup gains). Hand-set switching weights gave +1.9 points over 480 battles, inside the noise.

Reproducibility: a Pokémon's ability comes from a random id that `random.seed` does not control, so the team
harness seeds the id. The earlier single-Pokémon runs (1 to 5) did not, so their numbers are valid but not
exactly reproducible.

## Next steps, if this is pursued

1. Train on many more team matchups, so a policy cannot fit a handful of them.
2. Give the opponent voluntary switching in the engine; the trainers never switch, so there is little for a
   switching policy to exploit.
3. Keep the held-out gate as it is.

## Reproduce

    python tools/train_learned_ai.py --model linear --generations 40 --pop 16 --record docs/ai/baseline_decisions.jsonl
    python tools/train_learned_ai.py --model mlp --generations 80 --pop 16 --seeds-per-candidate 60 --sigma 0.15 --lr 0.3 --seed 11 --holdout-battles 400
    python tools/train_learned_ai.py --model linear --generations 80 --pop 16 --seeds-per-candidate 60 --holdout-battles 400 --no-ship
    python tools/train_team_ai.py --generations 40 --pop 16 --seeds-per-candidate 60 --start some --seed 21 --holdout-battles 800

## What's in this folder

- `baseline_decisions.jsonl` — developer recording (step 3): every decision of the rule-based AI on the training
  battery, with the legal moves, the feature values, the choice, and the outcome. This is the data the recorder
  produces; it's the input for any imitation or lookahead work.
- The run logs above (1, 1b, 2, 3, 4, 5, 6, 7).
