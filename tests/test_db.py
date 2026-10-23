import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_supabase as F
which=sys.argv[1] if len(sys.argv)>1 else "good"     # `good` (schema.sql applied) or `bad` (old schema)
fake=F.install(F.GOOD if which=="good" else F.BAD, rpc=(which=="good"))
os.environ["SUPABASE_URL"]="http://fake"; os.environ["SUPABASE_KEY"]="k"
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import index
from index import *
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
ok(index._db is not None,"db layer active")
d=diagnose()
if which=="bad":
    print("   diagnose problems:"); [print("    -",p) for p in d["problems"]]
    ok(not d["ok"] and any("created_date" in p or "players" in p for p in d["problems"]) and any("battle_sessions" in p for p in d["problems"]) and any("trainer_id" in p for p in d["problems"]),"diagnose pinpoints the wrong-schema columns/tables")
    # reproduce the user's symptoms
    ok(any("save_player_atomic" in p for p in d["problems"]),"diagnose reports the missing atomic-save function")
    try: auth_register(RegisterRequest(username="x_user",password="secret1")); ok(False,"should refuse")
    except Exception as e: ok(type(e).__name__=="SchemaError","old schema: saving fails closed (SchemaError) instead of dropping columns")
    print("   (accounts table exists in both)")
    sys.exit(0)
ok(d["ok"],"diagnose: schema OK")
r=auth_register(RegisterRequest(username="Brown_DB",password="secret1")); uid=r["user_id"]
ok(r["needs_starter"],"register creates player row")
ro=choose_starter(StarterRequest(user_id=uid,region="kanto",species="squirtle")); pid=ro["team"][0]["id"]
ok(len(fake.rows["pokemon"])==1 and fake.rows["players"][0]["active_team"]==[pid],"pokemon row + active_team saved")
# 'restart': a fresh load from the database returns the SAME starter, no new one is created
a=get_roster(uid); b=get_roster(uid); c=get_roster(uid)
ok(a["team"][0]["id"]==b["team"][0]["id"]==c["team"][0]["id"]==pid and len(fake.rows["pokemon"])==1,"repeated loads return the same Pokemon (no regeneration)")
# battle session survives (this was the 404)
journey_travel(TravelRequest(user_id=uid,to="route_1")); bt=start_battle(StartBattleRequest(user_id=uid)); ok(len(fake.rows["battle_sessions"])==1,"battle session stored")
mv=bt["player_pokemon"]["moves"][0]["id"]
for _ in range(60):
    r2=battle_move(MoveRequest(battle_id=bt["battle_id"],move_name=mv))
    if r2["is_finished"]: break
ok(r2["is_finished"],"battle/move works (no 404)")
ok(len(fake.rows["battle_sessions"])==0,"finished session cleaned up")
# progress persisted
after=get_roster(uid); ok(after["coins"]>=r["needs_starter"]*0 and after["team"][0]["id"]==pid,"progress persisted across loads")
# transient DB failure must NOT create a fresh player over the real one
import requests as rq
orig=rq.get; origp=rq.post
def boom(*a,**k): raise rq.RequestException("network blip")
rq.get=boom; rq.post=boom
try: get_roster(uid); ok(False,"should raise")
except Exception as e: ok(type(e).__name__=="DatabaseError","DB outage raises DatabaseError (not a silent new player)")
rq.get=orig; rq.post=origp
ok(get_roster(uid)["team"][0]["id"]==pid and len(fake.rows["players"])==1,"after the outage the real player is intact")
# a failed save must fail the request (a catch is never reported "saved" when it wasn't)
real=index._db.save_player
index._db.save_player=lambda p: False
try:
    care_rest(CareRequest(user_id=uid,pokemon_id=get_roster(uid)["team"][0]["id"])); ok(False,"should raise")
except Exception as e: ok(type(e).__name__=="DatabaseError","failed save raises DatabaseError (503) instead of reporting success")
index._db.save_player=real
print("ALL DB TESTS PASSED")
