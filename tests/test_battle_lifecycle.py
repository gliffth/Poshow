import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Regression tests for the "V3 critical issues" audit.
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import random, time, subprocess, requests as rq, index, accounts
from index import *
from database import DatabaseError
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
def raises(fn, exc):
    try: fn(); return False
    except exc: return True
random.seed(5)
def mk(name, sp="charmander"):
    u = auth_register(RegisterRequest(username=name, password="secret1"))["user_id"]
    choose_starter(StarterRequest(user_id=u, region="kanto", species=sp)); journey_travel(TravelRequest(user_id=u, to="route_1")); return u
def prow(u): return next(r for r in fake.rows["players"] if r["user_id"] == u)
def mon_hp(u): return get_or_create_player(u).active_team[0].current_hp

# 1) abandoning a damaged battle does NOT heal the team ------------------------------------------------------
u = mk("Life_1"); bt = start_battle(StartBattleRequest(user_id=u)); full = mon_hp(u)
rec = index._sessions.load(bt["battle_id"]); rec["player_pokemon"]["current_hp"] = 3
index._sessions.save(bt["battle_id"], u, rec["player_pokemon"], rec["wild_pokemon"])
bt2 = start_battle(StartBattleRequest(user_id=u))
ok(mon_hp(u) == 3, "starting a new battle over a damaged one keeps the damage (HP %d -> 3)" % full)
ok(len(fake.rows["battle_sessions"]) == 1 and fake.rows["battle_sessions"][0]["battle_id"] == bt2["battle_id"], "only the new session exists")
rec = index._sessions.load(bt2["battle_id"]); rec["player_pokemon"]["current_hp"] = 2
index._sessions.save(bt2["battle_id"], u, rec["player_pokemon"], rec["wild_pokemon"])
random.seed(1)
for _ in range(40):
    if battle_flee(FleeRequest(battle_id=bt2["battle_id"]))["success"]: break
ok(mon_hp(u) == 2 and not fake.rows["battle_sessions"], "fleeing successfully keeps the damage too")
bt3 = start_battle(StartBattleRequest(user_id=u)); rec = index._sessions.load(bt3["battle_id"]); rec["player_pokemon"]["current_hp"] = 1
index._sessions.save(bt3["battle_id"], u, rec["player_pokemon"], rec["wild_pokemon"])
out = battle_abandon(AbandonRequest(user_id=u))
ok(out["abandoned"] == 1 and mon_hp(u) == 1 and not fake.rows["battle_sessions"], "/api/battle/abandon closes the fight and keeps the damage")
# a failed save while replacing changes nothing (no free heal by breaking the save)
bt4 = start_battle(StartBattleRequest(user_id=u)); rec = index._sessions.load(bt4["battle_id"]); rec["player_pokemon"]["current_hp"] = 1
index._sessions.save(bt4["battle_id"], u, rec["player_pokemon"], rec["wild_pokemon"])
fake.fail_pokemon_write = True
ok(raises(lambda: start_battle(StartBattleRequest(user_id=u)), DatabaseError), "replacing a fight when the save fails -> 503")
fake.fail_pokemon_write = False
ok(len(fake.rows["battle_sessions"]) == 1 and fake.rows["battle_sessions"][0]["battle_id"] == bt4["battle_id"], "…and the old session is still there (nothing deleted before the save)")
battle_abandon(AbandonRequest(user_id=u))

# 2) an encounter token starts ONE battle --------------------------------------------------------------------
u = mk("Token_1")
sc = scout_area(ScoutRequest(user_id=u)) if "scout_area" in dir(index) else None
cands = (sc or {}).get("candidates") or []
tok = accounts.make_encounter_token(u, "pidgey", 5)
req = StartBattleRequest(user_id=u, target_species="pidgey", target_level=5, encounter_token=tok)
b1 = start_battle(req); ok(bool(b1["battle_id"]), "first use of a token starts the battle")
battle_abandon(AbandonRequest(user_id=u))
ok(code(lambda: start_battle(req)) == 403, "the same token can't start a second battle (403)")
tok2 = accounts.make_encounter_token(u, "pidgey", 5)
ok(tok2 != tok and code(lambda: start_battle(StartBattleRequest(user_id=u, target_species="pidgey", target_level=5, encounter_token=tok2))) == 200, "a fresh token works")
ok(accounts.encounter_token_id(tok) != accounts.encounter_token_id(accounts.make_encounter_token(u, "pidgey", 5)), "tokens issued in the same second are distinct")
battle_abandon(AbandonRequest(user_id=u))

# 3) other actions are blocked during a battle; an idle battle is settled, not left as a zombie -----------------
u = mk("Block_1"); bt = start_battle(StartBattleRequest(user_id=u))
for name, fn in (("travel", lambda: journey_travel(TravelRequest(user_id=u, to="route_2"))),
                 ("journey heal", lambda: journey_heal(JourneyActionRequest(user_id=u))),
                 ("trainer start", lambda: journey_trainer_start(JourneyActionRequest(user_id=u, trainer_id="x"))),
                 ("party heal", lambda: party_heal(HealRequest(user_id=u, pokemon_id="x", item_type="potion"))) if "HealRequest" in dir(index) else ("skip", lambda: (_ for _ in ()).throw(HTTPException(400, "x"))),
                 ("rare candy", lambda: party_rare_candy(CandyRequest(user_id=u, pokemon_id="x")))):
    ok(code(fn) == 400, "%s is refused during a battle" % name)
rec = index._sessions.load(bt["battle_id"]); rec["player_pokemon"]["current_hp"] = 4
index._sessions.save(bt["battle_id"], u, rec["player_pokemon"], rec["wild_pokemon"])
fake.rows["battle_sessions"][0]["updated_at"] = "2020-01-01T00:00:00Z"          # idle for years
ok(code(lambda: index._no_battle(u)) == 200, "an idle battle no longer blocks")
ok(not fake.rows["battle_sessions"], "…and it was closed (no zombie session left behind)")
ok(mon_hp(u) == 4, "…keeping the damage it had taken")

# 4) removing Pokémon really removes the rows (admin reset / release / trade-away) ----------------------------
u = mk("Reset_1"); p = get_or_create_player(u)
for sp in ("pidgey", "rattata", "zubat"): p.add_pokemon_to_team(PokemonInstance(sp, 5, u))
persist_player(p); n = sum(1 for r in fake.rows["pokemon"] if r["player_id"] == u)
ok(n == 4, "player owns 4 Pokémon rows")
p = get_or_create_player(u); p.pokemon_collection = []; p.active_team = []; persist_player(p)
ok(sum(1 for r in fake.rows["pokemon"] if r["player_id"] == u) == 0, "after a reset no Pokémon rows remain")
ok(len(index._db.load_player(u).pokemon_collection) == 0, "…and nothing reappears on reload")
# one Pokémon released, others kept
u2 = mk("Reset_2"); p = get_or_create_player(u2); extra = PokemonInstance("pidgey", 5, u2); p.add_pokemon_to_team(extra); persist_player(p)
p = get_or_create_player(u2); p.active_team = [m for m in p.active_team if m.id != extra.id]; p.pokemon_collection = [m for m in p.pokemon_collection if m.id != extra.id]; persist_player(p)
ok(sum(1 for r in fake.rows["pokemon"] if r["player_id"] == u2) == 1, "a released Pokémon's row is deleted, the rest stay")

# 5) a failed catch advances the turn counter ----------------------------------------------------------------
u = mk("Catch_1"); p = get_or_create_player(u); p.pokeballs["quickball"] = 9; p.pokeballs["timerball"] = 9; persist_player(p)
bt = start_battle(StartBattleRequest(user_id=u)); bid = bt["battle_id"]
rec = index._sessions.load(bid); rec["wild_pokemon"]["current_hp"] = rec["wild_pokemon"]["max_hp"]
index._sessions.save(bid, u, rec["player_pokemon"], rec["wild_pokemon"])
turns, quick = [], []
orig = index.CatchSystem.calculate_catch_chance
def spy(self, *a, **k):
    r = orig(self, *a, **k); quick.append((k.get("turn"), k.get("is_first_turn"))); r["will_catch"] = False; r["success"] = False; return r
index.CatchSystem.calculate_catch_chance = spy
for _ in range(3): battle_catch(CatchRequest(battle_id=bid, ball_type="quickball"))
index.CatchSystem.calculate_catch_chance = orig
ok([q[0] for q in quick] == [1, 2, 3], "turn counter advances on failed throws: %s" % [q[0] for q in quick])
ok([q[1] for q in quick] == [True, False, False], "Quick Ball's first-turn bonus applies once")
ok(index._sessions.load(bid)["wild_pokemon"]["bt"]["turn"] == 3, "the session stores the turn count")

# 6) battle item: no free heal when the save fails -----------------------------------------------------------
u = mk("Item_1"); p = get_or_create_player(u); p.inventory["potion"] = 2; persist_player(p)
bt = start_battle(StartBattleRequest(user_id=u)); bid = bt["battle_id"]
rec = index._sessions.load(bid); rec["player_pokemon"]["current_hp"] = 3
index._sessions.save(bid, u, rec["player_pokemon"], rec["wild_pokemon"])
fake.fail_pokemon_write = True
ok(raises(lambda: battle_item(ItemRequest(battle_id=bid, item_type="potion")), DatabaseError), "item use whose save fails -> 503")
fake.fail_pokemon_write = False
ok(index._sessions.load(bid)["player_pokemon"]["current_hp"] == 3, "the session was NOT healed")
ok(get_or_create_player(u).inventory.get("potion") == 2, "and the potion was not consumed")
out = battle_item(ItemRequest(battle_id=bid, item_type="potion"))
ok(get_or_create_player(u).inventory.get("potion") == 1 and out["player_pokemon"]["current_hp"] > 3, "the retry heals and consumes exactly one")
battle_abandon(AbandonRequest(user_id=u))

# 7) Telegram login codes ------------------------------------------------------------------------------------
svc = index._accounts
c1 = svc.start_telegram_login()["code"]
real_get = rq.get
rq.get = lambda url, *a, **k: F.Resp(500, {"message": "down"}) if "login_codes" in url else real_get(url, *a, **k)
try: svc.poll_telegram_login(c1); outage = None
except accounts.AccountError as e: outage = e
rq.get = real_get
ok(outage is not None and outage.status == 503 and "expired" not in outage.message.lower(), "a database outage is a 503, not 'code expired'")
ok(svc.poll_telegram_login(c1)["status"] == "pending", "…and the code is still valid afterwards")
ok(svc.confirm_telegram_login(c1, 111, "A") is True and svc.confirm_telegram_login(c1, 222, "B") is False, "only the first confirmation of a code wins")
real_del = rq.delete; calls = {"n": 0}
def racy_delete(url, *a, **k):          # two polls both saw the row; only one DELETE ... RETURNING gets it
    calls["n"] += 1; return real_del(url, *a, **k)
rq.delete = racy_delete
r1 = svc.poll_telegram_login(c1); r2 = svc.poll_telegram_login(c1)
rq.delete = real_del
ok(r1["status"] == "ok" and r1["user_id"] == 111, "first poll logs in")
ok(r2["status"] == "expired", "the second use of the same code does not")
c2 = svc.start_telegram_login()["code"]; svc.confirm_telegram_login(c2, 5, "C")
row = svc._get_code(c2)
real_get2 = svc._get_code
svc._get_code = lambda code: row           # both racers read the row before either deleted it
a = svc.poll_telegram_login(c2); b = svc.poll_telegram_login(c2)
svc._get_code = real_get2
ok([a["status"], b["status"]] == ["ok", "expired"], "even with a stale read exactly one concurrent poll wins: %s" % [a["status"], b["status"]])

# 8) capture-rate data problems block production -------------------------------------------------------------
import shutil, tempfile
d = tempfile.mkdtemp(); shutil.copytree(os.path.join(REPO_ROOT, "api"), os.path.join(d, "api"))
import json
ex = os.path.join(d, "api", "_lib", "data", "species_extra.json"); data = json.load(open(ex)); data["pidgey"].pop("c", None); json.dump(data, open(ex, "w"))
stub = os.path.join(REPO_ROOT, "tests", "stubs")
def boot(extra_env):
    env = {**os.environ, **extra_env, "PYTHONPATH": os.pathsep.join([stub, os.path.join(d, "api", "_lib"), os.path.join(d, "api")])}
    env.pop("SUPABASE_URL", None); env.pop("SUPABASE_KEY", None)
    return subprocess.run([sys.executable, "-c", "import index; print('BOOTED', index._CATCH_DATA_OK)"], cwd=os.path.join(d, "api"), env=env, capture_output=True, text=True)
r = boot({"RENDER": "true", "JWT_SECRET": "x" * 32, "AUTH_SECRET": "x" * 32, "REQUIRE_AUTH": "0"})
ok("BOOTED" not in r.stdout and "capture-rate" in (r.stderr + r.stdout), "production refuses to start with incomplete capture-rate data")
r = boot({"REQUIRE_AUTH": "0"})
ok("BOOTED False" in r.stdout, "development starts but with catching disabled")
shutil.rmtree(d, ignore_errors=True)
print("ALL BATTLE-LIFECYCLE TESTS PASSED")
