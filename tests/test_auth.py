import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import index
from index import *
import accounts
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn, status, label):
    try: fn(); ok(False,label+" (no error)")
    except (HTTPException, accounts.AccountError) as e:
        code=getattr(e,"status_code",None) or getattr(e,"status",None); ok(code==status,f"{label} -> {code}")

# health / root / diagnose (memory mode)
ok(health()["ok"] is True and root()["ok"] is True,"health + root answer instantly")
d=diagnose(); ok(d["ok"] is False and "memory mode" in d["problems"][0],"diagnose reports memory mode")

# register -> needs starter, no auto-Charmander
r=auth_register(RegisterRequest(username="Brown_X",password="hunter22"))
uid=r["user_id"]; ok(r["needs_starter"] is True and r["username"]=="Brown_X" and uid>=10**12,"register: needs_starter, web-range id")
me=auth_me("Bearer "+r["token"]); ok(me["user_id"]==uid and me["username"]=="Brown_X" and me["needs_starter"],"/me with token")
raises(lambda: auth_me("Bearer nonsense"),401,"/me with bad token")
raises(lambda: auth_me(None),401,"/me with no token")
raises(lambda: auth_register(RegisterRequest(username="Brown_X",password="hunter22")),409,"duplicate username")
raises(lambda: auth_login(RegisterRequest(username="Brown_X",password="nope!!")),401,"wrong password")
l=auth_login(RegisterRequest(username="brown_x",password="hunter22")); ok(l["user_id"]==uid,"login (case-insensitive) returns same id")

# roster of a fresh player is EMPTY and says so; nothing is spawned for them
ro=get_roster(uid); ok(ro["team"]==[] and ro["needs_starter"] is True,"fresh roster empty, needs_starter")
raises(lambda: encounter_scout(ScoutRequest(user_id=uid)),400,"scout before starter")
raises(lambda: boss_start(BossStartRequest(user_id=uid)),400,"boss before starter")
raises(lambda: gym_enter(GymEnterRequest(user_id=uid)),400,"gym before starter")
try: encounter_scout(ScoutRequest(user_id=uid))
except HTTPException as e: ok("starter" in e.detail,"message says to choose a starter: "+e.detail)

# starters list + selection rules
st=list_starters()["regions"]; ok(len(st)==9 and [m["species"] for m in st["hoenn"]]==["treecko","torchic","mudkip"],"9 regions, 3 starters each")
raises(lambda: choose_starter(StarterRequest(user_id=uid,region="atlantis",species="x")),400,"unknown region")
raises(lambda: choose_starter(StarterRequest(user_id=uid,region="hoenn",species="charmander")),400,"starter from the wrong region")
ro=choose_starter(StarterRequest(user_id=uid,region="hoenn",species="mudkip"))
ok(len(ro["team"])==1 and ro["team"][0]["species_name"]=="mudkip" and ro["team"][0]["level"]==5 and ro["needs_starter"] is False and ro["region"]=="hoenn","chose mudkip in Hoenn")
ok(len(ro["team"][0]["moves"])>=1,"starter has moves: "+str([m["name"] for m in ro["team"][0]["moves"]]))
raises(lambda: choose_starter(StarterRequest(user_id=uid,region="hoenn",species="torchic")),400,"can't pick twice")
ok(get_roster(uid)["team"][0]["species_name"]=="mudkip","roster keeps the starter (does not change on reload)")
ok(auth_login(RegisterRequest(username="Brown_X",password="hunter22"))["needs_starter"] is False,"login after starter: no longer needs one")
raises(lambda: encounter_scout(ScoutRequest(user_id=uid)),200,"x") if False else None
b=encounter_scout(ScoutRequest(user_id=uid)); ok(len(b["candidates"])>=1,"hoenn (no journey map yet) = free roam: can scout anywhere")

# regional routes
ok([r["id"] for r in list_routes("hoenn")["routes"]]==["route_101","route_102"],"hoenn routes")
ok(len(list_routes()["routes"])>=30 and all(r["region"] for r in list_routes()["routes"]),"all routes carry a region")
sc=encounter_scout(ScoutRequest(user_id=uid,route_id="route_101")); ok(all(c["species_name"] in ("zigzagoon","taillow","seedot") for c in sc["candidates"]),"scout on route_101 uses Hoenn pool")
sc=encounter_scout(ScoutRequest(user_id=uid,route_id="paldea:route_1")); ok(len(sc["candidates"])>=1,"namespaced route id works")

# telegram link login
s=auth_telegram_start(); code=s["code"]; ok(len(code)==8,"telegram code issued, bot_url=%s"%s["bot_url"])
ok(auth_telegram_poll(TelegramPollRequest(code=code))["status"]=="pending","pending until the bot confirms")
index._accounts.confirm_telegram_login(code, 555123, "TgTrainer")
p=auth_telegram_poll(TelegramPollRequest(code=code)); ok(p["status"]=="ok" and p["user_id"]==555123 and accounts.verify_token(p["token"])["uid"]==555123 and p["needs_starter"],"confirmed -> token for the Telegram user id")
ok(auth_telegram_poll(TelegramPollRequest(code=code))["status"]=="expired","code is single-use")
print("ALL AUTH TESTS PASSED")
