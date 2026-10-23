import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
random.seed(21)
A = auth_register(RegisterRequest(username="Switcher_1", password="secret1")); uid = A["user_id"]
choose_starter(StarterRequest(user_id=uid, region="kanto", species="squirtle"))
p = get_or_create_player(uid); p.add_pokemon_to_team(PokemonInstance("pidgey", 12, uid)); persist_player(p)
journey_travel(TravelRequest(user_id=uid, to="route_1"))
bt = start_battle(StartBattleRequest(user_id=uid)); bid = bt["battle_id"]
other = next(m for m in get_or_create_player(uid).active_team if m.id != bt["player_pokemon"]["id"])
hp_before = other.current_hp
hits = 0
out = battle_switch(SwitchRequest(battle_id=bid, pokemon_id=other.id))
ok(out["player_pokemon"]["id"] == other.id, "switch brings the chosen Pokémon in")
ok(any("damage" in str(l).lower() or "used" in str(l).lower() for l in out["log"]), "the opponent acted during the switch: %s" % [l for l in out["log"][:3]])
ok(out["player_pokemon"]["current_hp"] <= hp_before, "the free enemy turn can hurt the incoming Pokémon (HP %d -> %d)" % (hp_before, out["player_pokemon"]["current_hp"]))
print("ALL SWITCH TESTS PASSED")
