import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
from index import *
random.seed(7)
UID=42
index.choose_starter(index.StarterRequest(user_id=UID, region='kanto', species='charmander'))
index.journey_travel(index.TravelRequest(user_id=UID,to='route_1'))
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))

# routes
rs=list_routes()["routes"]
ok(len(rs)>=10 and rs[0]["min_level"]<=rs[-1]["min_level"], f"routes listed ({len(rs)}), sorted")
sc=encounter_scout(ScoutRequest(user_id=UID, route_id="route_1"))
ok(all(c["species_name"] in ("pidgey","rattata","sentret","bellsprout") and 3<=c["level"]<=8 for c in sc["candidates"]), "scout on route_1 -> route species/levels "+str([(c['species_name'],c['level']) for c in sc['candidates']]))
sc3=encounter_scout(ScoutRequest(user_id=UID, route_id="route_10")); ok(all(3<=c["level"]<=8 for c in sc3["candidates"]),"on a journey the location wins: route_id from the client is ignored")
sc2=encounter_scout(ScoutRequest(user_id=UID)); ok(len(sc2["candidates"])>=1,"scout without route still works (legacy pool)")

# shop: exp_all + rare candy
p=get_or_create_player(UID); p.coins=5000; persist_player(p)
r=shop_buy(BuyRequest(user_id=UID,item_id="exp_all",quantity=2)); ok(r["inventory"].get("exp_all")==2,"buy exp_all x2")
r=shop_buy(BuyRequest(user_id=UID,item_id="rare_candy",quantity=1)); ok(r["inventory"].get("rare_candy")==1,"buy rare_candy")
ok(get_roster(UID)["inventory"].get("exp_all")==2,"roster shows exp_all")

# add a second team mon to test exp all split
p=get_or_create_player(UID)
p.add_pokemon_to_team(PokemonInstance("squirtle",5,UID)); persist_player(p)

# wild battle on a route, with EXP ALL
b=start_battle(StartBattleRequest(user_id=UID, route_id="route_1"))
bid=b["battle_id"]; mv=b["player_pokemon"]["moves"][0]["id"]
done=None
for _ in range(60):
    r=battle_move(MoveRequest(battle_id=bid, move_name=mv, use_exp_all=True))
    if r["is_finished"]: done=r; break
ok(done is not None,"wild battle finishes")
print("   winner:",done["winner"], "| log tail:", done["log"][-3:])
if done["winner"]=="player":
    ok(done["exp_all"]["used"] is True and done["exp_all"]["pokemon_count"]>=1,"EXP ALL consumed, split across team: "+str(done["exp_all"]))
    ok(done["inventory"].get("exp_all")==1,"exp_all count decremented to 1")
    ok(len(done["team"])==2,"finished response carries whole team")
else:
    ok(get_roster(UID)["inventory"].get("exp_all")==2,"loss does not consume EXP ALL")

# heal team for boss
p=get_or_create_player(UID)
for m in p.active_team: m.current_hp=m.max_hp; m.is_fainted=False
persist_player(p)

# boss
bt=boss_today(UID); print("   boss:",bt["name"],bt["level"],bt["ability"],"claimed",bt["claimed_today"])
ok(bt["claimed_today"] is False,"boss not claimed yet")
bs=boss_start(BossStartRequest(user_id=UID)); bid=bs["battle_id"]
ok(bs["wild_pokemon"]["is_boss"] is True and "ability" in bs["wild_pokemon"],"boss flagged: "+str(bs["wild_pokemon"]["ability"]))
try: battle_catch(CatchRequest(battle_id=bid)); ok(False,"boss uncatchable")
except HTTPException as e: ok(e.status_code==400,"catching boss rejected")
# survives round-trip through session (switch/item rebuild)
_rec=index._sessions.load(bid); _rec["player_pokemon"]["level"]=100; _rec["player_pokemon"]["current_hp"]=9999   # an item costs the turn: survive the boss's reply
index._sessions.save(bid,UID,_rec["player_pokemon"],_rec["wild_pokemon"])
p=get_or_create_player(UID)
r=battle_item(ItemRequest(battle_id=bid,item_type="potion")) if p.inventory.get("potion") else None
rec=index._sessions.load(bid); ok(rec["wild_pokemon"].get("is_boss") is True,"boss marker persisted in session")
# make the player overwhelmingly strong so we win
rec_p=index.PokemonInstance.from_dict(rec["player_pokemon"]); rec_p.level=60; rec_p.recalculate_stats(); rec_p.restore_hp()
rec_p.moves=["hydro-pump","earthquake","ice-beam","crunch"]
index._sessions.save(bid, UID, rec_p.to_dict(), rec["wild_pokemon"])
# keep team member identity in player's team in sync
p=get_or_create_player(UID); p.active_team[0]=index.PokemonInstance.from_dict(rec_p.to_dict()); persist_player(p)
done=None
for _ in range(80):
    r=battle_move(MoveRequest(battle_id=bid, move_name="hydro-pump"))
    if r["is_finished"]: done=r; break
ok(done and done["winner"]=="player","boss defeated")
ok(done["boss"]["defeated"] and done["xp_gained"]>0 and done["coins_gained"]>0,f"boss rewards xp={done['xp_gained']} coins={done['coins_gained']} items={done['boss']['items']}")
ok(boss_today(UID)["claimed_today"] is True,"claimed today flag set")
try: boss_start(BossStartRequest(user_id=UID)); ok(False,"second boss attempt blocked")
except HTTPException as e: ok(e.status_code==400 and "already" in e.detail,"second attempt same day blocked")
inv=get_roster(UID)["inventory"]; ok(not any(k.startswith("_") for k in inv),"internal claim key hidden from roster")

# rare candy
p=get_or_create_player(UID); tid=p.active_team[0].id; lv=p.active_team[0].level
r=party_rare_candy(CandyRequest(user_id=UID,pokemon_id=tid)); ok(r["new_level"]==lv+1 and r["remaining"]==1,"rare candy +1 level, consumed (1 bought + 1 boss drop -> 1 left)")
party_rare_candy(CandyRequest(user_id=UID,pokemon_id=tid))
try: party_rare_candy(CandyRequest(user_id=UID,pokemon_id=tid)); ok(False,"no candy left")
except HTTPException as e: ok(e.status_code==400,"no candy -> 400")
print("ALL API TESTS PASSED")
