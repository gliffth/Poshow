import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Retry safety: a battle/catch is only "done" AFTER the player was saved; a leftover session can't pay twice.
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import random, requests as rq, index, species_data, rules
from index import *
from database import DatabaseError
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def raises(fn, exc=DatabaseError):
    try: fn(); return False
    except exc: return True
random.seed(11)
A = auth_register(RegisterRequest(username="Idem_1", password="secret1")); uid = A["user_id"]
choose_starter(StarterRequest(user_id=uid, region="kanto", species="charmander"))
journey_travel(TravelRequest(user_id=uid, to="route_1"))
real_post, real_del, real_patch = rq.post, rq.delete, rq.patch
def sessions(): return fake.rows["battle_sessions"]
def start_weak():
    bt = start_battle(StartBattleRequest(user_id=uid)); rec = index._sessions.load(bt["battle_id"])
    rec["wild_pokemon"]["current_hp"] = 1; index._sessions.save(bt["battle_id"], uid, rec["player_pokemon"], rec["wild_pokemon"])
    mv = next(m["id"] for m in bt["player_pokemon"]["moves"] if (m.get("power") or 0) > 0)      # a damaging move
    return bt["battle_id"], mv
def player_row(): return next(r for r in fake.rows["players"] if r["user_id"] == uid)

# 1) player save FAILS -> nothing marked completed, session intact, retry resolves normally exactly once
bid, mv = start_weak(); wins0 = player_row()["wins"]
fake.fail_pokemon_write = True
ok(raises(lambda: battle_move(MoveRequest(battle_id=bid, move_name=mv))), "finish whose player save fails -> 503")
fake.fail_pokemon_write = False
rec = sessions()[0]
ok(not rec.get("completed_at") and not rec.get("completion_result"), "…and the session was NOT marked completed (a retry must not replay a result that was never saved)")
out = battle_move(MoveRequest(battle_id=bid, move_name=mv))
ok(out["is_finished"] and out["winner"] == "player" and player_row()["wins"] == wins0 + 1, "retry then resolves and is paid exactly once")
ok(not sessions(), "session deleted after the save")

# 2) saved fine but the session can't be deleted -> still answers 200, marks it, and a retry replays (no 2nd payout)
bid, mv = start_weak(); wins0 = player_row()["wins"]
rq.delete = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
out1 = battle_move(MoveRequest(battle_id=bid, move_name=mv))
rq.delete = real_del
ok(out1["is_finished"] and player_row()["wins"] == wins0 + 1, "saved + delete failure: client still gets the (already saved) result")
ok(sessions() and sessions()[0].get("completed_at"), "…session is marked completed")
out2 = battle_move(MoveRequest(battle_id=bid, move_name=mv))
ok(out2 == out1 and player_row()["wins"] == wins0 + 1, "retry replays the stored answer — no second payout")
ok(raises(lambda: battle_flee(FleeRequest(battle_id=bid)), HTTPException), "other actions on a completed session are refused (409)")
index._sessions.purge_user(uid)

# 3) catch: save failure leaves no half-state; delete failure replays instead of double-catching
p = get_or_create_player(uid); p.pokeballs["pokeball"] = 30; persist_player(p)
bt = start_battle(StartBattleRequest(user_id=uid)); bid = bt["battle_id"]
rec = index._sessions.load(bid); rec["wild_pokemon"]["current_hp"] = 1; index._sessions.save(bid, uid, rec["player_pokemon"], rec["wild_pokemon"])
n0 = len(fake.rows["pokemon"]); balls0 = player_row()["pokeballs"]["pokeball"]
fake.fail_pokemon_write = True
ok(raises(lambda: battle_catch(CatchRequest(battle_id=bid, ball_type="masterball" if False else "pokeball"))), "catch whose save fails -> 503")
fake.fail_pokemon_write = False
ok(len(fake.rows["pokemon"]) == n0 and player_row()["pokeballs"]["pokeball"] == balls0, "…no Pokémon stored, no ball spent")
p = get_or_create_player(uid); p.pokeballs["masterball"] = 3; persist_player(p)
rq.delete = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
c1 = battle_catch(CatchRequest(battle_id=bid, ball_type="masterball"))
rq.delete = real_del
ok(c1.get("caught") and len(fake.rows["pokemon"]) == n0 + 1, "master ball catch stored once")
c2 = battle_catch(CatchRequest(battle_id=bid, ball_type="masterball"))
ok(c2 == c1 and len(fake.rows["pokemon"]) == n0 + 1 and player_row()["pokeballs"]["masterball"] == 2, "retry replays: no duplicate Pokémon, no 2nd ball spent")

# 4) Pokédex history survives evolution / release; catalogue is complete
import evolution
p = get_or_create_player(uid)
m = PokemonInstance("rattata", 25, uid); p.catch_pokemon(m)
evolution.evolve(p, m.id, "raticate") if hasattr(evolution, "evolve") else None
dex = index._pokedex_payload(p)
ok("rattata" in dex["caught"] and "raticate" in dex["caught"], "evolved Pokémon keeps its old form in the Pokédex history")
p.pokemon_collection = [x for x in p.pokemon_collection if x.id != m.id]
ok("rattata" in index._pokedex_payload(p)["caught"], "…even after it leaves the collection")
persist_player(p); cat = get_pokedex_catalogue(uid)
ok(cat["total"] == len(species_data.SPECIES) and cat["total"] > 900, "Pokédex catalogue lists every server species (%d)" % cat["total"])
ok(next(r for r in cat["species"] if r["name"] == "rattata")["caught"], "catalogue reflects the history after a save/load round trip")

# 5) data: every species has a verified capture rate; evolution fills free move slots without overwriting
species_data.validate_capture_rates(); ok(True, "no species lacks a verified capture rate")
ok(species_data.catch_rate("mimikyu", 476) in (45, 75) and species_data.get("mimikyu")["catch_rate"] == 45, "Mimikyu uses its real rate (45)")
e = PokemonInstance("charmander", 20, 1); e.moves = ["scratch"]; p.pokemon_collection.append(e)
evolution.evolve(p, e.id, "charmeleon")
ev = next(x for x in p.pokemon_collection if x.id == e.id)
ok(ev.moves[0] == "scratch" and len(ev.moves) > 1 and len(ev.moves) <= 4, "evolution keeps old moves and fills free slots (%s)" % ev.moves)
f = PokemonInstance("charmander", 20, 1); f.moves = ["scratch", "growl", "ember", "smokescreen"]; p.pokemon_collection.append(f)
evolution.evolve(p, f.id, "charmeleon")
ok(next(x for x in p.pokemon_collection if x.id == f.id).moves == ["scratch", "growl", "ember", "smokescreen"], "a full moveset is never overwritten by evolution")
print("ALL IDEMPOTENCY / POKEDEX TESTS PASSED")
