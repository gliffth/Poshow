import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
# prove the hot paths never touch the network: fake dex off, species data only; and requests exploding
import pokeapi_manager, requests
def no_net(*a,**k): raise RuntimeError("network call in a hot path!")
pokeapi_manager.requests.get=no_net
from pokeapi_manager import pokeapi
pokeapi.pokemon_cache.clear()
import pokeapi_manager as PM
orig_get=PM.PokeAPIManager.get_pokemon if hasattr(PM,"PokeAPIManager") else None
# undo harness' fake so the REAL get_pokemon (local species data) is what's exercised
import importlib
cls=type(pokeapi)
pokeapi.get_pokemon=cls.get_pokemon.__get__(pokeapi)
from index import *
from battle_system import BattleSystem, Move
from pokemon_model import PokemonInstance
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn,label,status=None,contains=None):
    try: fn(); ok(False,label+" (no error)")
    except HTTPException as e: ok((status is None or e.status_code==status) and (contains is None or contains.lower() in str(e.detail).lower()),f"{label}: {e.status_code} {e.detail}")
random.seed(8)
UID=4001
choose_starter(StarterRequest(user_id=UID,region="hoenn",species="mudkip",avatar="frost"))
ok(get_roster(UID)["team"][0]["types"]==["water"],"starter built with NO network (local species data)")

# --- recoil follows damage actually dealt, not overkill (tester: 354 dmg on a 24-HP Machoke -> 88 recoil)
a=PokemonInstance("frogadier",50,1); a.moves=["take-down"]; a.restore_hp()
b=PokemonInstance("machoke",7,0); b.restore_hp()
bs=BattleSystem(a,b); mv=Move.from_name("take-down"); bs.p.stages["atk"]=6
random.seed(1)
hp_before=bs.o.hp; php=bs.p.hp
bs._act("player",mv,True)
rec=php-bs.p.hp
ok(bs.o.hp==0 and rec<=max(1,hp_before//4)+1,f"recoil capped by the target's remaining HP: target had {hp_before}, recoil {rec} (was 25% of the overkill)")
ok(any("damage" in l and str(hp_before) in l for l in bs.battle_log),"log shows the damage actually dealt ("+str(hp_before)+"), not the overkill")

# --- strict move choice
journey_travel(TravelRequest(user_id=UID,to="route_1")) if journey.state(get_or_create_player(UID))["mode"]=="journey" else None
sc=start_battle(StartBattleRequest(user_id=UID)); bid=sc["battle_id"]
raises(lambda: battle_move(MoveRequest(battle_id=bid,move_name="hyper-beam")),"unknown move is rejected, not swapped for the first move",400,"isn't one")
r=battle_move(MoveRequest(battle_id=bid,move_name=sc["player_pokemon"]["moves"][0]["id"])); ok("log" in r,"a real move still works")

# --- catch returns everything the client needs, and is saved
p=get_or_create_player(UID); p.pokeballs["pokeball"]=50; persist_player(p)
for _ in range(40):
    sc=start_battle(StartBattleRequest(user_id=UID)); rec=index._sessions.load(sc["battle_id"]); w=PokemonInstance.from_dict(rec["wild_pokemon"]); w.current_hp=1; index._sessions.save(sc["battle_id"],UID,rec["player_pokemon"],w.to_dict())
    c=battle_catch(CatchRequest(battle_id=sc["battle_id"]))
    if c["will_catch"]: break
ok(c["will_catch"] and c["caught"]["species_name"] and c["collection_count"]>=1,"catch response carries the caught Pokémon + collection count")
ok(c["caught"]["species_name"] in c["pokedex"]["caught"] and c["caught"]["species_name"] in c["pokedex"]["seen"],"…and the updated Pokédex: "+c["caught"]["species_name"]+" is now caught")
ro=get_roster(UID); ok(c["caught"]["species_name"] in ro["pokedex"]["caught"] and any(s["species_name"]==c["caught"]["species_name"] for s in ro["storage"]),"roster exposes the Pokédex and the storage box (stored Pokémon were invisible before)")
# per-species catch rate
wr=PokemonInstance("mewtwo",70,0); ok(wr.api_data["catch_rate"]==3,"catch rate is per species (Mewtwo 3, not 45)")

# --- the Pokémon you switch to takes the lead (gym floors / trainers start with it)
p=get_or_create_player(UID); p.add_pokemon_to_team(PokemonInstance("pidgey",9,UID)); p.add_pokemon_to_team(PokemonInstance("rattata",9,UID)); persist_player(p)
p=get_or_create_player(UID); ids=[m.id for m in p.active_team]
sc=start_battle(StartBattleRequest(user_id=UID))
battle_switch(SwitchRequest(battle_id=sc["battle_id"],pokemon_id=ids[2]))
p=get_or_create_player(UID); ok(p.active_team[0].id==ids[2],"switching moves the new Pokémon to the front of the team")
p.coins=0; g=gym_enter(GymEnterRequest(user_id=UID)); ok(g["player_pokemon"]["id"]==ids[2],"next gym floor starts with the Pokémon you switched to (not 'the first one alive')")
gym_system.end_run(p)

# --- a failed save fails the request instead of lying
import fake_supabase as F
print("   (persist failure covered in test_db)")
print("ALL P0 TESTS PASSED")
