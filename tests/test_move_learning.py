import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index, species_data, rules, progression
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
random.seed(4)
ls = [(lv, mv) for lv, mv in species_data.learnset("charmander") if mv in rules.MOVE_DATA]
ok(len(ls) >= 6, "charmander has a real learnset (%d moves)" % len(ls))

def gain(mon, to_level):
    while mon.level < to_level:
        mon.add_experience(rules.xp_to_next(mon.level) - mon.experience)

# free slot -> learned automatically
m = PokemonInstance("charmander", 1, 1); m.moves = ["scratch"]; m.pending_moves = []
first = next((lv, mv) for lv, mv in sorted(ls) if lv > 1 and mv != "scratch")
gain(m, first[0])
ok(first[1] in m.moves and not m.pending_moves, "a move learned on level-up with a free slot is added (%s at Lv%d)" % (first[1], first[0]))
ok(any(e["move"] == first[1] for e in m.move_events), "…and reported as an event")

# full moveset -> parked as pending, nothing overwritten
m2 = PokemonInstance("charmander", 1, 1); m2.moves = ["scratch", "growl", "ember", "smokescreen"]; m2.pending_moves = []; m2.move_events = []
target = next((lv, mv) for lv, mv in sorted(ls) if lv > 1 and mv not in m2.moves)
before = list(m2.moves); gain(m2, target[0])
ok(m2.moves == before and target[1] in m2.pending_moves, "full moveset: move is offered, known moves untouched")
back = PokemonInstance.from_dict(m2.to_db_dict())
ok(back.pending_moves == m2.pending_moves, "pending moves survive save -> load")

# resolve: replace / decline / invalid
r = m2.resolve_pending_move(target[1], "growl")
ok(r["ok"] and target[1] in m2.moves and "growl" not in m2.moves and not m2.pending_moves, "teach over a chosen move")
m2.pending_moves = ["flamethrower"]
ok(not m2.resolve_pending_move("flamethrower", "not-a-known-move")["ok"], "can't forget a move it doesn't know")
ok(m2.resolve_pending_move("flamethrower", None)["ok"] and not m2.pending_moves, "declining drops the offer")

# API endpoint
A = auth_register(RegisterRequest(username="Learner_1", password="secret1")); uid = A["user_id"]
choose_starter(StarterRequest(user_id=uid, region="kanto", species="charmander"))
p = get_or_create_player(uid); mon = p.active_team[0]
mon.moves = ["scratch", "growl", "ember", "smokescreen"]; mon.pending_moves = ["flamethrower"]; persist_player(p)
ok(progression.pending_moves(get_or_create_player(uid))[0]["moves"] == ["flamethrower"], "pending list is exposed")
out = party_learn_move(LearnMoveRequest(user_id=uid, pokemon_id=mon.id, move="flamethrower", replace="growl"))
ok(out["learned"] and "flamethrower" in get_or_create_player(uid).active_team[0].moves, "endpoint teaches and persists")
try: party_learn_move(LearnMoveRequest(user_id=uid, pokemon_id=mon.id, move="surf")); ok(False, "should 400")
except HTTPException as e: ok(e.status_code == 400, "unknown offer -> 400")
# a high-level Pokémon saved with a single move (older versions never taught level-up moves) is repaired on load
m = PokemonInstance("meganium", 44, 1); m.moves = ["tackle"]
back = PokemonInstance.from_dict(m.to_db_dict())
ok(len(back.moves) == 4 and back.moves[0] == "tackle", "Lv44 Meganium that only knew Tackle is topped up on load: %s" % back.moves)
full = PokemonInstance("meganium", 44, 1); full.moves = ["tackle", "growl", "razor-leaf", "synthesis"]
ok(PokemonInstance.from_dict(full.to_db_dict()).moves == ["tackle", "growl", "razor-leaf", "synthesis"], "a full moveset is never changed")
ok(len(PokemonInstance("meganium", 44, 1).moves) == 4, "a fresh evolved-form Pokémon also draws on its pre-evolutions' moves")
ok(species_data.learnset_inherited("meganium") and len(species_data.learnset_inherited("meganium")) > len(species_data.learnset("meganium")), "inherited learnset is larger than the final form's own list")
print("ALL MOVE-LEARNING TESTS PASSED")
