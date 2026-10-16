import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
from index import *
import gym_system as G
random.seed(11)
UID=77
index.choose_starter(index.StarterRequest(user_id=UID, region='kanto', species='charmander'))
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))

st=gym_status(UID); ok(st["in_run"] is False and st["best"]==0 and st["bp"]==0 and st["next_floor"]==1,"fresh status")
# fixed player: strong team so we can clear floors, plus a weak backup
p=get_or_create_player(UID)
p.active_team[0].level=40; p.active_team[0].recalculate_stats(); p.active_team[0].restore_hp()
p.active_team[0].moves=["tackle","scratch","ember","water-gun"]
p.add_pokemon_to_team(PokemonInstance("squirtle",3,UID)); persist_player(p)

def fight(bid, move="ember", cap=80):
    for _ in range(cap):
        r=battle_move(MoveRequest(battle_id=bid, move_name=move))
        if r["is_finished"]: return r
    raise SystemExit("battle never ended")

e=gym_enter(GymEnterRequest(user_id=UID)); ok(e["gym"]["floor"]==1 and not e["gym"]["leader"] and e["wild_pokemon"]["gym_floor"]==1,"enter -> floor 1 trainer: "+e["log"][0])
bid=e["battle_id"]
try: battle_catch(CatchRequest(battle_id=bid)); ok(False,"")
except HTTPException as x: ok(x.status_code==400,"gym mon can't be caught")
xp0=[m.experience for m in get_or_create_player(UID).active_team]
r=fight(bid); ok(r["winner"]=="player" and r["gym"]["floor_cleared"]==1 and r["gym"]["bp"]==1,f"floor 1 cleared, +{r['gym']['bp']} BP +{r['gym']['coins']} credits")
ok(r["xp_gained"]==0,"no XP in gym")
ok([m.experience for m in get_or_create_player(UID).active_team]==xp0,"team XP unchanged")
ok(all(not m["is_fainted"] and m["current_hp"]==m["max_hp"] for m in r["team"]),"team fully healed after floor")
st=gym_status(UID); ok(st["floor"]==2 and st["best"]==1 and st["bp"]==1,"status: floor 2, best 1, bp 1")
ok("_gym_floor" not in get_roster(UID)["inventory"] and get_roster(UID)["inventory"].get("battle_points")==1,"internal keys hidden, BP visible")

# determinism: retrying a floor gives the same opponent
e1=gym_enter(GymEnterRequest(user_id=UID)); e2=gym_enter(GymEnterRequest(user_id=UID))
ok(e1["wild_pokemon"]["species_name"]==e2["wild_pokemon"]["species_name"] and e1["wild_pokemon"]["level"]==e2["wild_pokemon"]["level"],"same floor -> same opponent on retry")

# climb to leader floor 5
for f in range(2,5):
    e=gym_enter(GymEnterRequest(user_id=UID)); r=fight(e["battle_id"])
    ok(r["winner"]=="player","floor %d cleared"%f)
e=gym_enter(GymEnterRequest(user_id=UID)); ok(e["gym"]["leader"] and e["gym"]["floor"]==5,"floor 5 is a Gym Leader: "+e["log"][0])
ok(e["wild_pokemon"]["ability"] is not None,"leader has a signature ability: "+str(e["wild_pokemon"]["ability"]))
r=fight(e["battle_id"])
if r["winner"]=="player":
    ok(r["gym"]["badge"] and r["gym"]["bp"]==7,f"leader badge '{r['gym']['badge']}' + {r['gym']['bp']} BP")
    ok(r["gym"]["badge"] in get_or_create_player(UID).badges,"badge stored on player")
else:
    print("   (leader beat us, fine) ", r["gym"])

# loss path: weak lead faints, backup continues, then everyone faints -> run over
p=get_or_create_player(UID)
for m in p.active_team: m.level=3; m.recalculate_stats(); m.restore_hp()
persist_player(p)
fl=gym_status(UID)["floor"]
e=gym_enter(GymEnterRequest(user_id=UID)); r=fight(e["battle_id"],move="tackle")
print("   DEBUG",r["winner"],r.get("gym"),[ (m["species_name"],m["current_hp"],m["is_fainted"]) for m in r.get("team",[])])
ok(r["winner"]=="opponent" and r["gym"]["run_over"] is False and r["gym"]["remaining"]==1,"first faint: run continues, 1 left")
e=gym_enter(GymEnterRequest(user_id=UID)); ok(e["player_pokemon"]["species_name"]=="squirtle","next healthy Pokemon is sent in")
r=fight(e["battle_id"],move="tackle")
ok(r["gym"]["run_over"] is True and r["gym"]["floors_cleared"]==fl-1,"all fainted -> run over, floors cleared %d"%r["gym"]["floors_cleared"])
st=gym_status(UID); ok(st["in_run"] is False and st["best"]>=fl-1,"run ended, best kept = %d"%st["best"])
ok(all(not m["is_fainted"] for m in get_roster(UID)["team"]),"team patched up after run ends")

# forfeit via flee
p=get_or_create_player(UID); p.active_team[0].level=40; p.active_team[0].recalculate_stats(); p.active_team[0].restore_hp(); persist_player(p)
e=gym_enter(GymEnterRequest(user_id=UID)); fr=battle_flee(FleeRequest(battle_id=e["battle_id"])); ok(fr["success"] and fr["gym"]["run_over"],"flee = forfeit run")
ok(gym_status(UID)["in_run"] is False,"no active run after forfeit")

# shop
p=get_or_create_player(UID); p.inventory["battle_points"]=40; persist_player(p)
try: gym_shop_buy(GymBuyRequest(user_id=UID,item_id="nope")); ok(False,"")
except HTTPException as x: ok(x.status_code==400,"unknown shop item rejected")
r=gym_shop_buy(GymBuyRequest(user_id=UID,item_id="rare_candy",quantity=1)); ok(r["bp"]==10 and r["inventory"]["rare_candy"]>=1,"buy rare candy for 30 BP")
r=gym_shop_buy(GymBuyRequest(user_id=UID,item_id="ultraball",quantity=1)); ok(r["pokeballs"].get("ultraball")==1 and r["bp"]==2,"buy ultraball (goes in pokeballs)")
try: gym_shop_buy(GymBuyRequest(user_id=UID,item_id="exp_all",quantity=1)); ok(False,"")
except HTTPException as x: ok("Need" in x.detail,"can't overspend BP")
print("ALL GYM TESTS PASSED")
