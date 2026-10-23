import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import os
os.environ["REQUIRE_AUTH"]="1"
import index
from index import *
index.REQUIRE_AUTH=True
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def st(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
A=auth_register(RegisterRequest(username="Alice_Z",password="secret1")); B=auth_register(RegisterRequest(username="Bobby_Z",password="secret1"))
ta,tb="Bearer "+A["token"],"Bearer "+B["token"]; ua,ub=A["user_id"],B["user_id"]
ok(st(lambda: choose_starter(StarterRequest(user_id=ua,region="kanto",species="squirtle"),ta))==200,"Alice picks a starter with her token")
ok(st(lambda: choose_starter(StarterRequest(user_id=ub,region="kanto",species="squirtle"),ta))==403,"…but can't create/modify Bob's player with her token (403)")
ok(st(lambda: choose_starter(StarterRequest(user_id=ub,region="kanto",species="squirtle"),None))==401,"no token -> 401")
ok(st(lambda: choose_starter(StarterRequest(user_id=ub,region="kanto",species="squirtle"),"Bearer forged.x"))==401,"forged token -> 401")
choose_starter(StarterRequest(user_id=ub,region="kanto",species="charmander"),tb)
ok(st(lambda: get_roster(ua,ta))==200 and st(lambda: get_roster(ub,ta))==403 and st(lambda: get_roster(ua,None))==401,"roster: own 200, someone else's 403, anonymous 401")
a_coins=get_roster(ua,ta)["coins"]
ok(st(lambda: shop_buy(BuyRequest(user_id=ua,item_id="potion",quantity=1),tb))==403,"Bob can't spend Alice's credits")
ok(get_roster(ua,ta)["coins"]==a_coins,"Alice's credits untouched")
ok(st(lambda: gym_status(ua,tb))==403 and st(lambda: journey_state(ua,tb))==403 and st(lambda: care_state(ua,tb))==403,"gym / journey / care state are private too")
ok(st(lambda: boss_today(ua,tb))==403 and st(lambda: boss_today(None,None))==200,"boss info: own data protected, anonymous generic info fine")
# battles belong to their owner
journey_travel(TravelRequest(user_id=ua,to="route_1"),ta)
sc=start_battle(StartBattleRequest(user_id=ua),ta); bid=sc["battle_id"]
mv=sc["player_pokemon"]["moves"][0]["id"]
ok(st(lambda: battle_move(MoveRequest(battle_id=bid,move_name=mv),tb))==403,"Bob can't play Alice's battle")
ok(st(lambda: battle_flee(FleeRequest(battle_id=bid),tb))==403 and st(lambda: battle_catch(CatchRequest(battle_id=bid),tb))==403,"…or flee/catch in it")
ok(st(lambda: battle_move(MoveRequest(battle_id=bid,move_name=mv),ta))==200,"Alice can")
# admin endpoints still use their own token check
ok(st(lambda: admin_give(AdminGiveRequest(username="Alice_Z",coins=5),tb))==403,"admin endpoints still admin-only")
# public ones stay public
ok(st(lambda: list_starters())==200 and st(lambda: list_routes())==200 and st(lambda: health())==200,"public endpoints unaffected")
# every endpoint that takes a user is guarded: scan the source
import re,inspect
src=open('./api/index.py').read()
unguarded=[]
for m in re.finditer(r'@app\.(?:get|post)\("([^"]+)"\)\ndef (\w+)\(([^)]*)\):\n((?:    .*\n)+)',src):
    path,name,args,body=m.groups()
    if path.startswith(("/api/auth","/api/admin","/api/scenes","/api/avatars","/api/assets","/api/starters","/api/routes","/api/health","/api/diagnose","/health")) or path=="/": continue
    if "user_id" in args or "req:" in args:
        if "_check_user(" not in body: unguarded.append(path)
ok(not unguarded,"no player endpoint is missing the ownership check: %s"%unguarded)
print("ALL AUTHZ TESTS PASSED")
