import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# A duel's result and both players' rating / win / loss changes are saved in ONE transaction.
sys.path.insert(0, os.path.join(root, "tests"))
import re
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import index
from index import *
from database import DatabaseError
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def raises(fn):
    try: fn(); return False
    except DatabaseError: return True
def mk(name, sp):
    u = auth_register(RegisterRequest(username=name, password="secret1"))["user_id"]
    choose_starter(StarterRequest(user_id=u, region="kanto", species=sp)); return u
ua, ub = mk("Duel_A", "charmander"), mk("Duel_B", "squirtle")
def row(u): return next(r for r in fake.rows["players"] if r["user_id"] == u)
def match(): return fake.rows["pvp_matches"][-1]

def new_duel():
    d = pvp_challenge(PvpChallengeRequest(user_id=ua, username="Duel_B"))
    pvp_respond(PvpRespondRequest(user_id=ub, match_id=d["id"], accept=True)); return d["id"]

# ---- forfeit
mid = new_duel(); before = (row(ua)["elo"], row(ub)["elo"], row(ua)["wins"], row(ub)["losses"])
fake.fail_pokemon_write = True
ok(raises(lambda: pvp_forfeit(PvpActionRequest(user_id=ub, match_id=mid))), "a forfeit whose save fails -> 503")
fake.fail_pokemon_write = False
ok(match()["status"] == "active", "…the duel is still active (it was not recorded as finished)")
ok((row(ua)["elo"], row(ub)["elo"], row(ua)["wins"], row(ub)["losses"]) == before, "…and nobody's rating or record changed")
out = pvp_forfeit(PvpActionRequest(user_id=ub, match_id=mid))
ok(match()["status"] == "finished" and row(ua)["wins"] == before[2] + 1 and row(ub)["losses"] == before[3] + 1, "retrying then records the result AND both players' stats together")
ok(row(ua)["elo"] > before[0] and row(ub)["elo"] < before[1], "ratings moved the right way")
# a finished duel can't be forfeited again for a second rating change
elo_now = (row(ua)["elo"], row(ub)["elo"])
try: pvp_forfeit(PvpActionRequest(user_id=ub, match_id=mid))
except Exception: pass
ok((row(ua)["elo"], row(ub)["elo"]) == elo_now, "a finished duel can't pay out twice")

# ---- a normal finishing turn (both sides acted) is atomic too
mid = new_duel(); d = index._pvp.load(mid)
for m in d["state"]["sides"]["b"]["team"]: m["current_hp"] = 1          # one hit from losing
index._pvp.save(d)
mv_a, mv_b = "scratch", "tackle"            # damaging moves; the other side has 1 HP left
snap = (row(ua)["wins"], row(ub)["losses"], row(ua)["elo"], row(ub)["elo"])
pvp_action(PvpActionRequest(user_id=ua, match_id=mid, action={"type": "move", "move": mv_a}))
fake.fail_pokemon_write = True
ok(raises(lambda: pvp_action(PvpActionRequest(user_id=ub, match_id=mid, action={"type": "move", "move": mv_b}))), "the finishing turn's save fails -> 503")
fake.fail_pokemon_write = False
cur = next(r for r in fake.rows["pvp_matches"] if r["id"] == mid)
ok(cur["status"] == "active" and (row(ua)["wins"], row(ub)["losses"], row(ua)["elo"], row(ub)["elo"]) == snap, "…the duel is still active and nothing was paid out")
out = pvp_action(PvpActionRequest(user_id=ub, match_id=mid, action={"type": "move", "move": mv_b}))
cur = next(r for r in fake.rows["pvp_matches"] if r["id"] == mid)
ok(cur["status"] == "finished", "retrying finishes the duel")
ok(row(ua)["elo"] != snap[2] and row(ub)["elo"] != snap[3], "both ratings were updated together with the result")

# ---- a failed save never leaves a half-recorded duel
mid2 = new_duel(); snap = (row(ua)["wins"], row(ub)["wins"], row(ua)["elo"], row(ub)["elo"])
fake.fail_pokemon_write = True
try: pvp_forfeit(PvpActionRequest(user_id=ua, match_id=mid2))
except Exception: pass
fake.fail_pokemon_write = False
ok((row(ua)["wins"], row(ub)["wins"], row(ua)["elo"], row(ub)["elo"]) == snap and next(r for r in fake.rows["pvp_matches"] if r["id"] == mid2)["status"] == "active", "a failed save leaves the duel active and the stats untouched")

# ---- the schema never drops data
sql = open(os.path.join(REPO_ROOT, "database", "schema.sql")).read()
ok(not re.search(r"drop\s+table", sql, re.I), "schema.sql contains no DROP TABLE (re-running it can't end live battles or erase data)")
ok(re.search(r"create table if not exists battle_sessions", sql), "battle_sessions is created only if missing")
ok("p_doc_table" in sql and "'pvp_matches'" in sql, "the multi-player save function can store a duel record")
print("ALL PVP-ATOMIC TESTS PASSED")
