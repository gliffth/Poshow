import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Regression tests for the persistence audit: fail-closed sessions, no ghost players, atomic + versioned saves,
# schema strictness, ability stability, HP formula, level-up healing, PvP/trade store failures.
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import asyncio, random, index, requests as rq, database
from index import *
from database import DatabaseError, ConcurrentUpdateError, SchemaError
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def raises(fn, exc):
    try: fn(); return False
    except exc: return True

r = auth_register(RegisterRequest(username="Persist_A", password="secret1")); uid = r["user_id"]
choose_starter(StarterRequest(user_id=uid, region="kanto", species="squirtle"))
journey_travel(TravelRequest(user_id=uid, to="route_1"))

# ---- battle sessions fail closed
real_post = rq.post
def bad_post(url, *a, **k):
    if "battle_sessions" in url:
        return F.Resp(500, {"message": "boom"})
    return real_post(url, *a, **k)
rq.post = bad_post
ok(raises(lambda: start_battle(StartBattleRequest(user_id=uid)), DatabaseError), "battle start fails (503) when the session can't be saved")
rq.post = real_post
bt = start_battle(StartBattleRequest(user_id=uid)); bid = bt["battle_id"]
mv = bt["player_pokemon"]["moves"][0]["id"]
rq.post = bad_post
ok(raises(lambda: battle_move(MoveRequest(battle_id=bid, move_name=mv)), DatabaseError), "a turn is not reported when its session update failed")
rq.post = real_post
real_del = rq.delete
rq.delete = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
ok(raises(lambda: index._sessions.delete(bid), DatabaseError), "session delete failure raises")
ok(raises(lambda: index._sessions.purge_user(uid), DatabaseError), "session purge failure raises")
rq.delete = real_del
real_get = rq.get
rq.get = lambda url, *a, **k: F.Resp(500, {"message": "boom"}) if "battle_sessions" in url else real_get(url, *a, **k)
ok(raises(lambda: index._sessions.load(bid), DatabaseError), "session load error is not 'no active battle'")
rq.get = real_get

# ---- a failed load can never become a new player
rows_before = len(fake.rows["players"])
rq.get = lambda url, *a, **k: F.Resp(200, {"unexpected": "object"}) if "/players" in url else real_get(url, *a, **k)
ok(raises(lambda: get_roster(uid), DatabaseError), "malformed players response raises")
rq.get = real_get
orig_from = index.PokemonInstance.from_dict
index.PokemonInstance.from_dict = staticmethod(lambda d: (_ for _ in ()).throw(KeyError("boom")))
ok(raises(lambda: get_roster(uid), DatabaseError), "deserialisation bug raises instead of returning None")
index.PokemonInstance.from_dict = orig_from
ok(len(fake.rows["players"]) == rows_before and get_roster(uid)["team"], "no replacement player was created; real one intact")
ok(index._db.load_player(999999) is None, "genuinely absent player -> None")
rq.post = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
ok(raises(lambda: get_or_create_player(777001, "Ghost"), DatabaseError), "bootstrap save failure is not ignored")
rq.post = real_post

# ---- atomic save: pokemon half fails -> the player half is rolled back
p = get_or_create_player(uid); coins0 = p.coins
p.coins += 500; p.add_pokemon_to_team(PokemonInstance("pidgey", 5, uid))
fake.fail_pokemon_write = True
ok(raises(lambda: persist_player(p), DatabaseError), "failed pokemon write fails the whole save")
fake.fail_pokemon_write = False
row = next(x for x in fake.rows["players"] if x["user_id"] == uid)
ok(row["coins"] == coins0 and len(fake.rows["pokemon"]) == 1, "…and nothing was half-written (coins unchanged, no new pokemon row)")
persist_player(p)
ok(next(x for x in fake.rows["players"] if x["user_id"] == uid)["coins"] == coins0 + 500 and len(fake.rows["pokemon"]) == 2, "retry then saves everything together")

# ---- optimistic versioning: website vs Telegram
a = index._db.load_player(uid); b = index._db.load_player(uid)
a.coins += 10; index._db.save_player(a)
b.coins -= 10
ok(raises(lambda: index._db.save_player(b), ConcurrentUpdateError), "stale copy (other client saved first) is rejected")
ok(next(x for x in fake.rows["players"] if x["user_id"] == uid)["coins"] == a.coins, "the first writer's change survived")
b2 = index._db.load_player(uid); b2.coins -= 10; index._db.save_player(b2)
ok(True, "after reloading, the second client can save")
import types
resp = asyncio.run(index.concurrent_update_handler(types.SimpleNamespace(url=types.SimpleNamespace(path="/x")), ConcurrentUpdateError("x")))
ok(resp is not None, "API has a 409 handler for version conflicts")

# ---- missing columns / function: fail closed, no silent stripping
saved = list(F.GOOD["players"]); fake.schema["players"] = [c for c in saved if c not in ("story", "avatar")]
q = index._db.load_player(uid); q.coins += 1
ok(raises(lambda: index._db.save_player(q), DatabaseError), "missing story/avatar columns -> save fails (not silently trimmed)")
fake.schema["players"] = saved
fake.has_rpc = False
ok(raises(lambda: index._db.save_player(index._db.load_player(uid)), SchemaError), "missing save_player_atomic -> SchemaError")
fake.has_rpc = True

# ---- ability stays the same across reloads
random.seed(3)
same = 0
for sp in ("charmander", "pidgey", "gyarados", "pikachu", "bulbasaur", "zubat"):
    for _ in range(10):
        m = PokemonInstance(sp, 20, 1)
        back = PokemonInstance.from_dict(m.to_db_dict())
        same += (back.ability == m.ability)
ok(same == 60, "ability identical after to_db_dict -> from_dict (60/60)")

# ---- HP formula + level-up behaviour
m = PokemonInstance("pikachu", 50, 1); m.iv = {k: 31 for k in m.iv}; m.ev = {k: 0 for k in m.ev}; m.recalculate_stats()
ok(m.max_hp == ((2 * 35 + 31) * 50 // 100) + 50 + 10, "max HP uses + level + 10 (%d)" % m.max_hp)
ok(m.actual_stats["hp"] == m.max_hp, "_calculate_stats and _get_max_hp agree")
sh = PokemonInstance("shedinja", 30, 1) if False else None
lv = PokemonInstance("charmander", 10, 1); lv.current_hp = 5; lv.status = "burn"
old_max = lv.max_hp; lv.add_experience(10 ** 9 if False else __import__("rules").xp_to_next(10))
ok(lv.level == 11 and lv.max_hp > old_max, "level-up raised max HP")
ok(lv.current_hp == 5 + (lv.max_hp - old_max) and lv.current_hp < lv.max_hp, "level-up is not a full heal (HP rose only by the gain)")
ok(lv.status == "burn", "level-up does not cure status")
fz = PokemonInstance("charmander", 10, 1); fz.current_hp = 0; fz.is_fainted = True
fz.add_experience(__import__("rules").xp_to_next(10))
ok(fz.current_hp == 0 and fz.is_fainted, "level-up never revives a fainted Pokémon")

# ---- PvP / trade doc store fails closed
import doc_store
ds = doc_store.DocStore("pvp_matches", "http://fake", "k")
doc = {"id": "m1", "a": 1, "b": 2, "status": "pending", "state": {}}
ok(ds.save(doc) is True, "doc save ok")
rq.post = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
ok(raises(lambda: ds.save(doc), DatabaseError), "doc save failure raises (invite can't look accepted)")
rq.post = real_post
rq.get = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
ok(raises(lambda: ds.load("m1"), DatabaseError), "doc load error is not 'no such match'")
ok(raises(lambda: ds.for_user(1), DatabaseError), "doc list error is not 'no active matches'")
rq.get = real_get
rq.delete = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
ok(raises(lambda: ds.delete("m1"), DatabaseError), "doc delete failure raises")
rq.delete = real_del
ok(ds.load("nope") is None, "genuinely missing doc -> None")
print("ALL PERSISTENCE TESTS PASSED")
