import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import os
os.environ["ADMIN_USERNAMES"]="BossAdmin"; os.environ["ADMIN_USER_IDS"]="555000111"
import index, accounts, admin_system
from index import *
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn,status,label):
    try: fn(); ok(False,label+" (no error)")
    except HTTPException as e: ok(e.status_code==status,f"{label} -> {e.status_code}: {e.detail}")
    except admin_system.AdminError as e: ok(status==400,f"{label} -> 400 (handler): {e}")

adm=auth_register(RegisterRequest(username="BossAdmin",password="secret1")); at="Bearer "+adm["token"]
usr=auth_register(RegisterRequest(username="Plain_Joe",password="secret1")); ut="Bearer "+usr["token"]
choose_starter(StarterRequest(user_id=usr["user_id"],region="kanto",species="squirtle",avatar="frost"))
ok(admin_me(at)["is_admin"] is True and admin_me(ut)["is_admin"] is False and admin_me(None)["is_admin"] is False,"admin status: by username env, normal users no, anonymous no")
ok(admin_system.is_admin(555000111,None) and not admin_system.is_admin(1,"nobody"),"admin by user id env; others no")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe",coins=999),ut),403,"normal user can't give")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe",coins=999),None),401,"anonymous can't give")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe",coins=999),"Bearer forged.token"),401,"forged token rejected")
before=get_roster(usr["user_id"])["coins"]
r=admin_give(AdminGiveRequest(username="plain_joe",coins=500,items={"potion":3,"rare_candy":1},balls={"ultraball":5},pokemon={"species":"pikachu","level":20,"shiny":True},heal=True),at)
ok(r["ok"] and len(r["done"])==6,"gave coins+items+balls+pokemon+heal by username (case-insensitive): "+" | ".join(r["done"]))
ro=get_roster(usr["user_id"]); ok(ro["coins"]==before+500 and ro["inventory"]["potion"]==5 and ro["inventory"]["rare_candy"]==1 and ro["pokeballs"]["ultraball"]==5,"player really received them")
ok([m["species_name"] for m in ro["team"]]==["squirtle","pikachu"] and ro["team"][1]["level"]==20,"Pokémon added to the team")
r=admin_give(AdminGiveRequest(user_id=usr["user_id"],coins=-100000),at); ok(get_roster(usr["user_id"])["coins"]==0,"taking more coins than they have floors at 0")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe",items={"bad name!":1}),at),400,"bad item name rejected")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe",balls={"gigaball":1}),at),400,"unknown ball rejected")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe",pokemon={"species":"pikachu","level":500}),at),400,"level out of range rejected")
raises(lambda: admin_give(AdminGiveRequest(username="Plain_Joe"),at),400,"empty gift rejected")
raises(lambda: admin_give(AdminGiveRequest(username="Nobody_Here",coins=1),at),404,"unknown username 404")
raises(lambda: admin_give(AdminGiveRequest(),at),400,"no target")
for i in range(7): admin_give(AdminGiveRequest(user_id=usr["user_id"],pokemon={"species":"rattata","level":3}),at)
ro=get_roster(usr["user_id"]); ok(len(ro["team"])==6 and ro["collection_count"]>=3,"team caps at 6, extras go to storage")
s=admin_player(username="Plain_Joe",authorization=at); ok(s["username"]=="Plain_Joe" and len(s["team"])==6,"admin player lookup")
raises(lambda: admin_player(username="Plain_Joe",authorization=ut),403,"lookup is admin-only")
# duplicate usernames must not guess
index._MEMORY_PLAYERS[9991]=PlayerInstance(9991,"Twin"); index._MEMORY_PLAYERS[9992]=PlayerInstance(9992,"twin")
raises(lambda: admin_give(AdminGiveRequest(username="TWIN",coins=5),at),400,"two players with one name -> asks for an id")
# images
ok(get_assets()["assets"]=={} ,"no overrides yet")
raises(lambda: admin_set_asset(AssetRequest(key="region_kanto",url="https://x.com/k.png"),ut),403,"image setting is admin-only")
raises(lambda: admin_set_asset(AssetRequest(key="nope",url="https://x.com/k.png"),at),400,"unknown image slot")
raises(lambda: admin_set_asset(AssetRequest(key="route",url="javascript:alert(1)"),at),400,"unsafe url rejected")
admin_set_asset(AssetRequest(key="region_kanto",url="https://example.com/kanto.png"),at); admin_set_asset(AssetRequest(key="town",url="/scenes/town.png"),at)
ok(get_assets()["assets"]=={"region_kanto":"https://example.com/kanto.png","town":"/scenes/town.png"},"image overrides saved and public")
admin_set_asset(AssetRequest(key="town",url=""),at); ok("town" not in get_assets()["assets"],"override removed")
print("ALL ADMIN TESTS PASSED")
