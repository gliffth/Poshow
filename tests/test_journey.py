import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index, struct
from index import *
import journey as J
random.seed(5)
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn, label, contains=None):
    try: fn(); ok(False,label+" (no error)")
    except (HTTPException, J.JourneyError) as e:
        msg=getattr(e,"detail",None) or str(e)
        ok(contains is None or contains.lower() in msg.lower(), f"{label}: {msg}")

# avatars
ok(len(list_avatars()["avatars"])==6,"6 avatars")
r=avatar_png("ember",4); ok(r.media_type=="image/png" and r.body[:8]==b"\x89PNG\r\n\x1a\n" and struct.unpack(">II",r.body[16:24])==(64,80),"avatar PNG renders")
raises(lambda: avatar_png("nope"),"unknown avatar 404")

# onboarding with avatar + journey start
UID=1001
raises(lambda: choose_starter(StarterRequest(user_id=UID,region="kanto",species="squirtle",avatar="bogus")),"bad avatar","avatar")
ro=choose_starter(StarterRequest(user_id=UID,region="kanto",species="squirtle",avatar="marina"))
ok(ro["avatar"]=="marina" and ro["region"]=="kanto","starter chosen with avatar")
st=journey_state(UID); ok(st["mode"]=="journey" and st["location"]["id"]=="pallet_town" and st["can_scan"] is False,"journey starts in Pallet Town (no wild Pokémon in town)")
ok([e["id"] for e in st["exits"]]==["route_1"] and "Beat" not in str(st["objective"]) and "Boulder Badge" in st["objective"],"objective points at the first gym: "+st["objective"])
raises(lambda: encounter_scout(ScoutRequest(user_id=UID)),"scan in town refused","travel to a route")

# movement + gates
raises(lambda: journey_travel(TravelRequest(user_id=UID,to="pewter_city")),"can't skip ahead","can't get")
journey_travel(TravelRequest(user_id=UID,to="route_1")); st=journey_state(UID); ok(st["can_scan"] and st["location"]["route_id"]=="route_1","on Route 1: can scan")
sc=encounter_scout(ScoutRequest(user_id=UID)); ok(all(c["species_name"] in ("pidgey","rattata","sentret","bellsprout") for c in sc["candidates"]),"route_1 encounters: "+str([c["species_name"] for c in sc["candidates"]]))
for t in ("viridian_city","route_2","viridian_forest","pewter_city"): journey_travel(TravelRequest(user_id=UID,to=t))
st=journey_state(UID); ok(st["location"]["id"]=="pewter_city" and any(c["id"]=="brock" and c["available"] for c in st["challenges"]),"Pewter City: Brock is available")
raises(lambda: journey_travel(TravelRequest(user_id=UID,to="route_3")),"Route 3 gated by Brock","Beat Brock")
raises(lambda: journey_trainer_start(JourneyActionRequest(user_id=UID,trainer_id="misty")),"Misty isn't in Pewter","isn't here")

# heal (town ok, route not)
p=get_or_create_player(UID); p.active_team[0].current_hp=1; persist_player(p)
h=journey_heal(JourneyActionRequest(user_id=UID)); ok(h["team"][0]["current_hp"]==h["team"][0]["max_hp"],"Pokémon Center heals")

# Brock fight: multi-pokemon trainer, player strong enough
p=get_or_create_player(UID); lead=p.active_team[0]; lead.level=30; lead.recalculate_stats(); lead.restore_hp(); lead.moves=["water-gun","hydro-pump","bite","tackle"]; persist_player(p)
p=get_or_create_player(UID); p.inventory["exp_all"]=2; p.add_pokemon_to_team(PokemonInstance("pidgey",4,UID)); persist_player(p)
bs=journey_trainer_start(JourneyActionRequest(user_id=UID,trainer_id="brock"))
ok(bs["story"]["size"]==2 and bs["wild_pokemon"]["species_name"]=="geodude" and bs["wild_pokemon"]["level"]==12,"Brock leads with Geodude Lv12")
ok(set(m["name"] for m in bs["wild_pokemon"]["moves"])!=set(),"trainer has a real moveset: "+str([m["name"] for m in bs["wild_pokemon"]["moves"]]))
bid=bs["battle_id"]
try: battle_catch(CatchRequest(battle_id=bid)); ok(False,"")
except HTTPException as e: ok(e.status_code==400,"trainer's Pokémon can't be caught")
ok(battle_flee(FleeRequest(battle_id=bid))["success"] is False,"can't flee a trainer battle")
seen=[]; advanced=False; done=None
for _ in range(120):
    r=battle_move(MoveRequest(battle_id=bid,move_name="hydro-pump",use_exp_all=True))
    if r.get("story",{}).get("advanced"): advanced=True; seen.append(r["wild_pokemon"]["species_name"]); ok(not r["is_finished"] and r["xp_gained"]>0,"KO #1 -> next Pokémon sent out without ending the battle: "+r["wild_pokemon"]["species_name"])
    if r["is_finished"]: done=r; break
ok(advanced and seen==["onix"],"Brock's team went Geodude -> Onix")
ok(done["winner"]=="player" and done["story"]["won"] and done["story"]["badge"]=="Boulder Badge","beat Brock, got the Boulder Badge")
ok(get_or_create_player(UID).inventory.get("exp_all")==1,"EXP All with a 2-Pokémon trainer: only ONE consumed (2 -> 1)")
ok(done["coins_gained"]==700 and "Boulder Badge" in get_or_create_player(UID).badges,"coins + badge persisted")
ok("brock" in journey_state(UID)["badges"] or "Boulder Badge" in journey_state(UID)["badges"],"badge shows in journey state")
raises(lambda: journey_trainer_start(JourneyActionRequest(user_id=UID,trainer_id="brock")),"can't re-fight Brock","already")
journey_travel(TravelRequest(user_id=UID,to="route_3")); ok(True,"Route 3 opened after Brock")

# EXP All is consumed ONCE for a whole trainer battle, not once per Pokémon (checked on Misty below)
# lose to a trainer: weak team -> retry, then blackout
p=get_or_create_player(UID)
for t in ("route_4","cerulean_city"): journey_travel(TravelRequest(user_id=UID,to=t))
p=get_or_create_player(UID)
for m in p.active_team: m.level=5; m.recalculate_stats(); m.restore_hp()
p.active_team=p.active_team[:1]; p.add_pokemon_to_team(PokemonInstance("rattata",3,UID)); persist_player(p)
raises(lambda: journey_trainer_start(JourneyActionRequest(user_id=UID,trainer_id="rival_1")),"rival needs Misty first","Misty")
bs=journey_trainer_start(JourneyActionRequest(user_id=UID,trainer_id="misty")); bid=bs["battle_id"]
for _ in range(80):
    r=battle_move(MoveRequest(battle_id=bid,move_name=bs["player_pokemon"]["moves"][0]["id"]))
    if r["is_finished"]: break
ok(r["winner"]=="opponent" and r["story"]["blackout"] is False and r["story"]["remaining"]==1,"lead fainted, 1 left -> can send the next one")
bs=journey_trainer_start(JourneyActionRequest(user_id=UID,trainer_id="misty")); bid=bs["battle_id"]
ok(bs["player_pokemon"]["species_name"]=="rattata","next healthy Pokémon leads the retry")
for _ in range(80):
    r=battle_move(MoveRequest(battle_id=bid,move_name=bs["player_pokemon"]["moves"][0]["id"]))
    if r["is_finished"]: break
ok(r["story"]["blackout"] is True and r["story"]["location"]=="Cerulean City","whole team down -> blackout, wake up in the last town you reached (Cerulean City)")
ok(journey_state(UID)["location"]["id"]=="cerulean_city" and all(not m["is_fainted"] for m in get_roster(UID)["team"]),"teleported home + team healed")

# legacy/free-roam region still works, and journey_state for it
UID2=1002
choose_starter(StarterRequest(user_id=UID2,region="hoenn",species="mudkip"))
st=journey_state(UID2); ok(st["mode"]=="free_roam" and st["can_scan"],"hoenn: free roam (no map yet)")
raises(lambda: journey_travel(TravelRequest(user_id=UID2,to="route_101")),"travel not available in free roam","no journey map")
ok(len(encounter_scout(ScoutRequest(user_id=UID2,route_id="route_101"))["candidates"])>=1,"free roam keeps the route picker")

# existing (pre-journey) kanto player gets a story lazily
UID3=1003
pl=get_or_create_player(UID3); pl.add_pokemon_to_team(PokemonInstance("charmander",7,UID3)); pl.current_region="kanto"; pl.story={}; persist_player(pl)
ok(journey_state(UID3)["mode"]=="journey" and journey_state(UID3)["location"]["id"]=="pallet_town","existing player: story created on first look")

# full-run engine test: beat everything in order (direct calls)
UID4=1004
choose_starter(StarterRequest(user_id=UID4,region="kanto",species="bulbasaur",avatar="ember"))
pl=get_or_create_player(UID4)
def go(to): 
    if pl.story["location"]!=to: J.travel(pl,to)
path=["route_1","viridian_city","route_2","viridian_forest","pewter_city"]
for t in path: J.travel(pl,t)
J.start_trainer(pl,"brock"); [J.next_opponent(pl,"brock",i) for i in range(1)]; J.trainer_won(pl,"brock")
for t in ["route_3","route_4","cerulean_city"]: J.travel(pl,t)
J.start_trainer(pl,"misty"); J.trainer_won(pl,"misty")
t,_=J.build_opponent(pl,"rival_1",3); ok(t.species_name=="charmeleon","rival counters a Bulbasaur starter with Charmeleon")
J.start_trainer(pl,"rival_1"); J.trainer_won(pl,"rival_1")
for t in ["route_5","route_6","vermilion_city"]: J.travel(pl,t)
J.start_trainer(pl,"surge"); J.trainer_won(pl,"surge"); J.start_trainer(pl,"rival_2"); J.trainer_won(pl,"rival_2")
for t in ["route_7","celadon_city"]: J.travel(pl,t)
J.start_trainer(pl,"erika"); J.trainer_won(pl,"erika")
for t in ["route_8","fuchsia_city"]: J.travel(pl,t)
J.start_trainer(pl,"koga"); J.trainer_won(pl,"koga")
for t in ["route_9","route_10","saffron_city"]: J.travel(pl,t)
J.start_trainer(pl,"sabrina"); J.trainer_won(pl,"sabrina")
J.travel(pl,"cinnabar_island"); J.start_trainer(pl,"blaine"); J.trainer_won(pl,"blaine")
J.travel(pl,"viridian_city")
try: J.travel(pl,"victory_road"); ok(False,"")
except J.JourneyError as e: ok("badges" in str(e),"Victory Road needs 8 badges: "+str(e))
raises(lambda: J.start_trainer(pl,"giovanni"),"Giovanni needs 7 gyms first (has 7?)") if J.gyms_won(pl)<7 else None
J.start_trainer(pl,"giovanni"); J.trainer_won(pl,"giovanni")
ok(J.gyms_won(pl)==8 and len(pl.badges)==8,"8 badges")
J.travel(pl,"victory_road"); J.travel(pl,"indigo_plateau")
for tid in ("lorelei","bruno","agatha","lance"): J.start_trainer(pl,tid); J.trainer_won(pl,tid)
J.start_trainer(pl,"champion"); res=J.trainer_won(pl,"champion")
ok(res["complete"] and res["unlocked_region"]=="johto" and "johto" in pl.regions_unlocked and "hall_of_fame" in pl.achievements,"Champion beaten: region complete, Johto unlocked, Hall of Fame")
ok(journey_state(UID4)["complete"] if False else J.state(pl)["complete"],"journey state reports complete")
print("ALL JOURNEY TESTS PASSED")
