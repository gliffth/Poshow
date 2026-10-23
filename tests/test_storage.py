import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
A = auth_register(RegisterRequest(username="Boxer_1", password="secret1")); uid = A["user_id"]
choose_starter(StarterRequest(user_id=uid, region="kanto", species="squirtle"))
p = get_or_create_player(uid)
for sp in ("pidgey", "rattata", "zubat"): p.add_pokemon_to_team(PokemonInstance(sp, 8, uid)); 
persist_player(p)
team = get_roster(uid)["team"]; ids = [m["id"] for m in team]
out = storage_deposit(StorageRequest(user_id=uid, pokemon_id=ids[1]))
ok(len(out["team"]) == 3 and any(m["id"] == ids[1] for m in out["box"]), "deposit moves a Pokémon from team to box")
ok(len(get_or_create_player(uid).active_team) == 3 and len(get_storage(uid)["box"]) == 1, "…and it persists")
ok(code(lambda: storage_deposit(StorageRequest(user_id=uid, pokemon_id=ids[1]))) == 400, "can't deposit a Pokémon that isn't on the team")
out = storage_withdraw(StorageRequest(user_id=uid, pokemon_id=ids[1]))
ok(len(out["team"]) == 4 and not out["box"], "withdraw brings it back")
# last Pokémon can't be stored
for i in ids[1:]: storage_deposit(StorageRequest(user_id=uid, pokemon_id=i))
ok(code(lambda: storage_deposit(StorageRequest(user_id=uid, pokemon_id=ids[0]))) == 400, "can't store the last team member")
# full team can't withdraw
p = get_or_create_player(uid)
for sp in ("pidgey", "rattata", "zubat", "abra", "onix"): p.add_pokemon_to_team(PokemonInstance(sp, 8, uid))
persist_player(p)
ok(len(get_or_create_player(uid).active_team) == 6, "team of six")
ok(code(lambda: storage_withdraw(StorageRequest(user_id=uid, pokemon_id=ids[1]))) == 400, "full team: withdraw refused")
# nobody else's Pokémon
B = auth_register(RegisterRequest(username="Boxer_2", password="secret1")); ub = B["user_id"]
choose_starter(StarterRequest(user_id=ub, region="kanto", species="charmander"))
ok(code(lambda: storage_withdraw(StorageRequest(user_id=ub, pokemon_id=ids[1]))) == 400, "can't withdraw another player's Pokémon")
# resting Pokémon come out through the care logic
p = get_or_create_player(uid); import care
care.rest(p, p.active_team[2].id); rid = None
rid = next(iter(care._care(p)["rest"])); persist_player(p)
ok(code(lambda: storage_withdraw(StorageRequest(user_id=uid, pokemon_id=rid))) == 200, "resting Pokémon withdrawn via care")
print("ALL STORAGE TESTS PASSED")
