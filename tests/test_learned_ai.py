import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Learned policy: it sees only what a player could see, saves and loads faithfully, is off by default, and the
# engine hook really is what plays the opponent.
import random
import learned_ai as LA
from battle_system import BattleSystem, Move
from pokemon_model import PokemonInstance
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

def battle(ps="charmander", pl=14, osp="rattata", ol=14):
    random.seed(4)
    p = PokemonInstance(ps, pl, 0); o = PokemonInstance(osp, ol, 0)
    return BattleSystem(p, o, smart=True)

# ── only observable information reaches the policy ───────────────────────────
b = battle()
usable = b.get_player_moves()
before = {m.name: LA.move_features(b, b.p, b.o, m) for m in usable}

b.o.attack, b.o.defense, b.o.speed = 999, 1, 999          # hidden computed stats of the opponent
b.o.real.moves = ["hyper-beam"]                             # its moveset is hidden until used
b.o.real.ivs = {"hp": 31, "attack": 31}                     # hidden IVs
after = {m.name: LA.move_features(b, b.p, b.o, m) for m in usable}
ok(before == after, "features don't change when the opponent's hidden stats, IVs or moveset change")

b.p.hp = b.p.max_hp // 2
half = {m.name: LA.move_features(b, b.p, b.o, m) for m in usable}
ok(half != before, "features do change with visible HP (the health bar is public)")

ok(len(LA.FEATURES) == len(before[usable[0].name]), "one value per named feature")

# ── policy: deterministic, and a loss of trust in weights is refused ──────────
pol = LA.LinearPolicy([0.2, 0.5, 0.3, 0.1, -0.2, 0.0, 0.0, 0.0, 0.5, 0.5, 0.1, 0.5, 0.0, 0.0, 0.0, 0.0])
first = pol.choose(b, usable, mover=b.p, target=b.o).name
ok(first == pol.choose(b, usable, mover=b.p, target=b.o).name, "the same position gives the same move")

text = pol.to_json()
back = LA.LinearPolicy.from_json(text)
ok(back.weights == pol.weights, "weights survive a save and load")
bad = text.replace('"effectiveness"', '"renamed"')
try:
    LA.LinearPolicy.from_json(bad); refused = False
except ValueError:
    refused = True
ok(refused, "weights trained with a different feature list are refused, not silently misread")
try:
    LA.LinearPolicy([0.0, 1.0]); short = False
except ValueError:
    short = True
ok(short, "a weight vector of the wrong length is refused")

# ── the engine hook: off by default, and it plays the opponent when set ───────
ok(battle().opponent_policy is None, "the learned policy is off by default in the engine")
sentinel = Move("tackle")                      # a specific object: the engine must hand back exactly this one
b = battle()
b.opponent_policy = lambda bs, usable_: sentinel
ok(b.get_opponent_move() is sentinel, "a set opponent policy chooses the opponent's move")
seen = []
b = battle()
b.opponent_policy = lambda bs, usable_: (seen.append(bs), sentinel)[1]
b.get_opponent_move()
ok(len(seen) == 1 and seen[0] is b, "the policy is called with the battle, once per opponent move")

# ── the network variant: same interface, same guarantees ─────────────────────
import random as _r
rng2 = _r.Random(3)
mlp = LA.MLPPolicy([rng2.gauss(0, 0.3) for _ in range(LA.MLPPolicy.size())])
b = battle()
usable = b.get_player_moves()
ok(mlp.choose(b, usable, mover=b.p, target=b.o).name == mlp.choose(b, usable, mover=b.p, target=b.o).name,
   "the network plays the same move in the same position")
back_m = LA.MLPPolicy.from_json(mlp.to_json())
ok(back_m.weights == mlp.weights, "network weights survive a save and load")
try:
    LA.MLPPolicy([0.0] * 5); mlp_short = False
except ValueError:
    mlp_short = True
ok(mlp_short, "a network with the wrong number of weights is refused")
ok(isinstance(LA.load_policy(os.path.join(root, "api", "_lib", "data", "no_such.json")), type(None)),
   "load_policy returns nothing when no weights are shipped")

# ── the shipping default: no weights file means the game uses the rule-based AI ──
ok(LA.LinearPolicy.load(os.path.join(root, "api", "_lib", "data", "no_such_weights.json")) is None,
   "no weights file -> no learned policy (rule-based AI stays in charge)")

print("ALL PASS")
