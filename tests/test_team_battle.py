import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Team battles: the harness follows the game's rules (a switch costs the turn, a faint is replaced for free), is
# reproducible, and the team policy starts out playing exactly like the rule-based AI.
sys.path.insert(0, os.path.join(root, "tools"))
import json, random
import team_battle as TB
import train_team_ai as TT
import learned_ai as LA
from battle_system import BattleSystem, Combatant
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

TEAMS = TB.TRAIN_TEAMS + TB.HOLDOUT_TEAMS

# ── reproducible ──
a = [TB.play_team(t, s) for t in TEAMS for s in range(12)]
b = [TB.play_team(t, s) for t in TEAMS for s in range(12)]
ok(a == b, "the same seeds give the same battles")
ok(True in a and False in a, "the baseline wins some team battles and loses others")

# ── the engine rules ──
class Probe:
    """Switches once on the first turn, then fights; records what the engine did to each Pokémon."""
    def __init__(self, switch_first=True):
        self.log, self.switch_first, self.n = [], switch_first, 0
    def choose_action(self, bs, usable, mover, target, bench):
        assert all(m.current_hp > 0 for m in bench) and all(m is not mover.mon for m in bench), "the bench holds only other, standing Pokémon"
        self.n += 1
        self.log.append(("act", mover.mon.species_name, mover.hp, mover.max_hp, target.hp, target.max_hp))
        if self.n == 1 and self.switch_first and bench:
            return "switch", bench[0]
        return "move", max(usable, key=lambda m: m.power)
    def pick_forced(self, bs, bench, target):
        self.log.append(("forced", bench[0].species_name, bench[0].current_hp, bench[0].max_hp))
        return bench[0]

free_hit = full_opp = 0
for t in TB.TRAIN_TEAMS:
    for s in range(15):
        p = Probe()
        TB.play_team(t, s, p)
        first, second = p.log[0], p.log[1]
        if second[0] != "act":
            continue
        ok(second[1] != first[1], "after a voluntary switch the new Pokémon is on the field")
        full_opp += second[4] == second[5] and second[4] == first[4]       # the switch used the turn: we dealt no damage
        free_hit += second[2] < second[3]                                  # and the opponent's free hit landed
ok(full_opp > 0 and free_hit > 0, "a switch costs the turn: the opponent hits the newcomer and takes no damage")

forced_checked = 0
for t in TEAMS:
    for s in range(20):
        p = Probe(switch_first=False)
        TB.play_team(t, s, p)
        for i, e in enumerate(p.log[:-1]):
            if e[0] == "forced" and p.log[i + 1][0] == "act":
                ok(p.log[i + 1][2] == e[2], "a replacement after a faint arrives untouched (no free hit)")
                forced_checked += 1
ok(forced_checked > 0, "forced replacements were exercised")

# ── information the switch scorer may use ──
random.seed(3)
mine = [TB._mon(s, l) for s, l in TB.TRAIN_TEAMS[0][0]]
theirs = [TB._mon(s, l) for s, l in TB.TRAIN_TEAMS[0][1]]
bs = BattleSystem(mine[0], theirs[0], smart=True)
cand = Combatant(mine[1], mine[1].current_hp)
before = LA.switch_features(bs, cand, bs.o, bs.p)
bs.o.attack, bs.o.defense, bs.o.speed = 999, 1, 999
bs.o.real.moves = ["hyper-beam"]
bs.o.real.iv = {k: 31 for k in bs.o.real.iv}
ok(LA.switch_features(bs, cand, bs.o, bs.p) == before, "switch features ignore the opponent's hidden stats, IVs and moveset")
ok(len(before) == len(LA.SWITCH_FEATURES), "one value per named switch feature")
forced = LA.switch_features(bs, cand, bs.o, None)
ok(forced[4] == 0.0 and forced[5] == 0.0, "a forced switch has no current Pokémon to compare against")

# ── the team policy ──
zero = TT.make_policy(TT.initial_theta(), "linear")
ok(all(w == 0.0 for w in zero.move_policy.weights), "the starting move correction is zero")
same = [TB.play_team(t, s, zero) for t in TEAMS for s in range(12)]
ok(same == a, "zero weights play exactly like the rule-based AI")
ok(TT.switch_rate(zero, TB.TRAIN_TEAMS, range(10)) == 0.0, "and never switch voluntarily at the start")

eager = LA.TeamPolicy(LA.LinearPolicy([0.0] * len(LA.FEATURES)), [0, 0, 0, 0, 0, 0, 5.0])
ok(TT.switch_rate(eager, TB.TRAIN_TEAMS, range(5)) > 0, "a policy that scores switching highly does switch")

text = eager.to_json()
back = LA.TeamPolicy.from_json(text)
ok(back.switch_weights == eager.switch_weights and back.move_policy.weights == eager.move_policy.weights, "a team policy survives a save and load")
bad = json.loads(text); bad["switch_features"] = bad["switch_features"][:-1]
try:
    LA.TeamPolicy.from_json(json.dumps(bad)); refused = False
except ValueError:
    refused = True
ok(refused, "weights trained on a different switch feature list are refused")
bad = json.loads(text); bad["residual_scale"] = 1.0
try:
    LA.TeamPolicy.from_json(json.dumps(bad)); refused = False
except ValueError:
    refused = True
ok(refused, "weights trained with a different score scale are refused")
try:
    LA.TeamPolicy(LA.LinearPolicy([0.0] * len(LA.FEATURES)), [0.0]); refused = False
except ValueError:
    refused = True
ok(refused, "a wrong number of switch weights is refused")

# ── the gate's statistics ──
mean, lo, hi, n = TT.paired_diff(zero, TB.HOLDOUT_TEAMS, range(10))
ok(mean == 0.0 and lo == 0.0 and hi == 0.0 and n == 40, "an identical policy has a zero difference, so it cannot pass the gate")
print("ALL TEAM BATTLE TESTS PASSED")
