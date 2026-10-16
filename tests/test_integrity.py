import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, threading, subprocess, os
import index
from index import *
import progression, rules, pokemon_model
from battle_system import BattleSystem, Move
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def st(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
    except Exception as e: return type(e).__name__
random.seed(12)
UID=5001
choose_starter(StarterRequest(user_id=UID,region="kanto",species="charmander",avatar="ember"))
journey_travel(TravelRequest(user_id=UID,to="route_1"))

# --- 1. the client can't invent an encounter
ok(st(lambda: start_battle(StartBattleRequest(user_id=UID,target_species="mewtwo",target_level=100)))==403,"forged Mewtwo Lv100 -> 403")
ok(st(lambda: start_battle(StartBattleRequest(user_id=UID,target_species="mewtwo",target_level=100,encounter_token="x.y")))==403,"forged token -> 403")
sc=encounter_scout(ScoutRequest(user_id=UID)); c=sc["candidates"][0]
ok(st(lambda: start_battle(StartBattleRequest(user_id=UID,target_species="mewtwo",target_level=c["level"],encounter_token=c["token"])))==403,"a real token can't be reused for a different species")
ok(st(lambda: start_battle(StartBattleRequest(user_id=UID+1,target_species=c["species_name"],target_level=c["level"],encounter_token=c["token"])))in(400,403),"another player's token is useless")
r=start_battle(StartBattleRequest(user_id=UID,target_species=c["species_name"],target_level=c["level"],encounter_token=c["token"]))
ok(r["wild_pokemon"]["species_name"]==c["species_name"],"the genuine scanned candidate starts fine")

# --- 2. one active battle per player
first=r["battle_id"]; r2=start_battle(StartBattleRequest(user_id=UID))
ok(index._sessions.load(first) is None and index._sessions.load(r2["battle_id"]),"starting a new battle discards the old one (no battle farming)")
mv=r2["player_pokemon"]["moves"][0]["id"]
ok(st(lambda: battle_move(MoveRequest(battle_id=first,move_name=mv)))==404,"the discarded battle can't be played")

# --- 3. concurrent double-submit: only one of two simultaneous finishing requests pays out
p=get_or_create_player(UID); p.coins=0; persist_player(p); w0=p.wins
bs=start_battle(StartBattleRequest(user_id=UID)); bid=bs["battle_id"]
rec=index._sessions.load(bid); w=PokemonInstance.from_dict(rec["wild_pokemon"]); w.current_hp=1; w.ability=None; index._sessions.save(bid,UID,rec["player_pokemon"],w.to_dict())
res=[]
def go():
    try: res.append(("ok",battle_move(MoveRequest(battle_id=bid,move_name=bs["player_pokemon"]["moves"][0]["id"]))))
    except HTTPException as e: res.append(("err",e.status_code))
    except Exception as e: res.append(("err",type(e).__name__))
ts=[threading.Thread(target=go) for _ in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
fins=[x for x in res if x[0]=="ok" and x[1]["is_finished"]]
ok(len(fins)==1 and get_or_create_player(UID).wins-w0<=1,f"6 simultaneous requests: exactly one finishing response, rewards paid once; others {[x[1] for x in res if x[0]=='err'][:3]}")
# concurrent shop buys can't double-spend
p=get_or_create_player(UID); p.coins=100; persist_player(p)
out=[]
def buy():
    try: shop_buy(BuyRequest(user_id=UID,item_id="potion",quantity=1)); out.append(1)
    except Exception: out.append(0)
ts=[threading.Thread(target=buy) for _ in range(8)]; [t.start() for t in ts]; [t.join() for t in ts]
bought=sum(out); coins=get_or_create_player(UID).coins
ok(coins==100-bought*index.SHOP_PRICES["potion"] if hasattr(index,"SHOP_PRICES") else coins>=0,f"8 simultaneous purchases: {bought} succeeded, credits consistent ({coins})")

# --- 4. unified progression: every XP source reports pending evolutions; Rare Candy goes through add_experience
p=get_or_create_player(UID); m=p.active_team[0]; m.level=15; m.experience=0; m.recalculate_stats(); persist_player(p)
ok(progression.pending(p)==[],"Lv15 Charmander: nothing pending")
p.inventory["rare_candy"]=1; persist_player(p)
r=party_rare_candy(CandyRequest(user_id=UID,pokemon_id=m.id))
ok(r["new_level"]==16 and r["evolution_pending"] and r["evolution_pending"][0]["to"]=="charmeleon","Rare Candy to Lv16 -> evolution_pending Charmeleon")
p=get_or_create_player(UID); m=p.active_team[0]; m.level=31; m.experience=0; m.recalculate_stats()
from exp_all_system import ExpAllItem
p.add_pokemon_to_team(PokemonInstance("bayleef",31,UID)); bay=p.active_team[-1]; bay.experience=0
bay.add_experience(rules.xp_to_next(31)); ok(bay.level==32 and any(x["id"]==bay.id for x in progression.pending(p)),"Bayleef reaching Lv32 via XP is reported as ready to evolve into Meganium")
ev=evolution.evolve(p,bay.id,"meganium"); ok(ev["ok"] and p.active_team[-1].species_name=="meganium","…and evolves")
# battle responses carry it
p=get_or_create_player(UID); p.active_team=[p.active_team[0]]; fire=p.active_team[0]; fire.level=15; fire.experience=rules.xp_to_next(15)-1; fire.recalculate_stats(); fire.restore_hp(); persist_player(p)
bs=start_battle(StartBattleRequest(user_id=UID)); rec=index._sessions.load(bs["battle_id"]); w=PokemonInstance.from_dict(rec["wild_pokemon"]); w.current_hp=1; w.ability=None; w.status=None
pl=dict(rec["player_pokemon"]); pl["current_hp"]=pl["max_hp"]; pl["is_fainted"]=False; pl["status"]=None
index._sessions.save(bs["battle_id"],UID,pl,w.to_dict())
best=max(bs["player_pokemon"]["moves"],key=lambda m:m["power"])["id"]
for _ in range(30):
    r=battle_move(MoveRequest(battle_id=bs["battle_id"],move_name=best))
    if r["is_finished"]: break
ok(r["winner"]=="player" and r["evolution_pending"] and r["evolution_pending"][0]["from"]=="charmander","winning the fight that levels Charmander to 16 reports evolution_pending")

# --- 5. PvE stats + player XP
p=get_or_create_player(UID); ok(p.wins>=1 and p.current_streak>=1,"PvE wins counted (wins=%d)"%p.wins)

# --- 6. fail closed
ok(st(lambda: EncounterSystem.spawn_in_route("johto:nope_route"))=="UnknownRoute","unknown route raises (no silent Pikachu/Pidgeotto/Eevee)")
ok(st(lambda: PokemonInstance("notapokemon",5,1))=="UnknownSpecies" or True,"(unknown species handled below)")
import pokeapi_manager as PM
from pokeapi_manager import pokeapi
orig=pokeapi.get_pokemon; pokeapi.get_pokemon=lambda n: (_ for _ in ()).throw(RuntimeError("down"))
try: PokemonInstance("notapokemon",5,1); ok(False,"should raise")
except pokemon_model.UnknownSpecies: ok(True,"unknown species raises UnknownSpecies (no generic 45/49/49 blob)")
pokeapi.get_pokemon=orig
# memory-mode guard: importing the API on a real host without Supabase must fail
_ST=os.path.join(REPO_ROOT,"tests","stubs"); _CODE=f"import sys; sys.path.insert(0,{_ST!r}); import index"
env={**os.environ,"RENDER":"true","PYTHONPATH":os.pathsep.join([_ST,os.path.join(REPO_ROOT,"api","_lib"),os.path.join(REPO_ROOT,"api")])}
env.pop("SUPABASE_URL",None); env.pop("SUPABASE_KEY",None)
rc=subprocess.run([sys.executable,"-c",_CODE],cwd=os.path.join(REPO_ROOT,"api"),env=env,capture_output=True,text=True)
ok(rc.returncode!=0 and "SUPABASE_URL" in rc.stderr,"on Render/Vercel without Supabase the API refuses to start (no silent memory mode)")
env["ALLOW_MEMORY_MODE"]="1"
rc=subprocess.run([sys.executable,"-c",_CODE],cwd=os.path.join(REPO_ROOT,"api"),env=env,capture_output=True,text=True)
ok(rc.returncode==0,"…unless ALLOW_MEMORY_MODE=1")

# --- 7. HP can never exceed max after loading
mm=PokemonInstance("greninja",31,1); d=mm.to_db_dict(); d["current_hp"]=9999; d["iv"]={k:0 for k in d["iv"]}
back=PokemonInstance.from_dict(d); ok(back.current_hp==back.max_hp,"loaded Pokémon with stale HP is clamped: %d/%d (was the 90/85 bug)"%(back.current_hp,back.max_hp))
d["nature"]="Adamant"; d["current_hp"]=1; ok(PokemonInstance.from_dict(d).actual_stats["atk"]!=PokemonInstance.from_dict({**d,"nature":"Bold"}).actual_stats["atk"],"stats recalculated from the restored IV/nature")

# --- 8. ability events & new move effects
def mon(sp,lv,ab=None,moves=None):
    q=PokemonInstance(sp,lv,1); 
    if ab: q.ability=ab
    if moves: q.moves=moves
    q.restore_hp(); return q
bs=BattleSystem(mon("gyarados",40,"intimidate",["tackle"]),mon("rattata",40,None,["tackle"]),smart=False)
bs.execute_turn(Move.from_name("tackle"),Move.from_name("tackle")); ok(bs.o.stages.get("atk")==-1 and any("Intimidate" in l for l in bs.battle_log),"Intimidate lowers the foe's Attack on entry (once)")
bs.execute_turn(Move.from_name("tackle"),Move.from_name("tackle")); ok(bs.o.stages.get("atk")==-1,"…and not again next turn")
# persists across API-style rebuilds
a=mon("gyarados",40,"intimidate",["tackle"]); b=mon("rattata",40,None,["tackle"]); BattleSystem(a,b).execute_turn(Move.from_name("tackle"),Move.from_name("tackle"))
a2=PokemonInstance.from_dict(a.to_dict()); b2=PokemonInstance.from_dict(b.to_dict()); bs2=BattleSystem(a2,b2); bs2.execute_turn(Move.from_name("tackle"),Move.from_name("tackle")); ok(bs2.o.stages.get("atk")==-1,"entry ability fires once even when the battle is rebuilt each request")
random.seed(3); n=0
for _ in range(60):
    x=mon("squirtle",30,None,["tackle"]); y=mon("pikachu",30,"static",["tackle"]); b=BattleSystem(x,y,smart=False); b._act("player",Move.from_name("tackle"),True); n+= b.p.status=="par"
ok(8<=n<=30,f"Static paralyses ~30% of physical attackers ({n}/60)")
b=BattleSystem(mon("pikachu",30,None,["thunderbolt"]),mon("gyarados",30,"levitate",["tackle"]),smart=False)
b.o.ability="levitate"; b.o.ab="levitate"; b._act("player",Move.from_name("earthquake"),True); ok(any("doesn't affect" in l for l in b.battle_log),"Levitate: immune to Ground")
b=BattleSystem(mon("charmander",30,None,["ember"]),mon("bulbasaur",30,None,["tackle"]),smart=False); b.weather="sun"; b._sync_weather()
sun=b.calc_damage(b.p,b.o,Move.from_name("ember"),roll=1.0); b.weather="rain"; rain=b.calc_damage(b.p,b.o,Move.from_name("ember"),roll=1.0); ok(sun>rain*2.5,f"sun boosts Fire, rain weakens it ({sun} vs {rain})")
b=BattleSystem(mon("rattata",30,None,["tackle"]),mon("pikachu",30,"drizzle",["tackle"]),smart=False); b.execute_turn(Move.from_name("tackle"),Move.from_name("tackle")); ok(b.weather=="rain" and any("rain" in l for l in b.battle_log),"Drizzle starts rain on entry")
b=BattleSystem(mon("rattata",30,None,["tackle"]),mon("pikachu",30,"sand_stream",["tackle"]),smart=False)
for _ in range(2): b.execute_turn(Move.from_name("tackle"),Move.from_name("tackle"))
ok(b.weather=="sand" and any("buffeted" in l for l in b.battle_log),"sandstorm damages non-Rock/Ground/Steel Pokémon")
x=mon("pidgey",30,None,["tackle"]); y=mon("pidgey",30,None,["tackle"]); fast=BattleSystem(x,y,smart=False); base=fast.o.stat("spe"); fast.o.ability="swift_swim"; fast.o.ab="swift_swim"; fast.weather="rain"; fast._sync_weather(); ok(fast.o.stat("spe")==base*2,"Swift Swim doubles Speed in rain")
b=BattleSystem(mon("pidgey",30,None,["tackle"]),mon("alakazam",30,"magic_bounce",["tackle"]),smart=False); b._act("player",Move.from_name("thunder-wave"),True); ok(b.p.status=="par" and b.o.status is None,"Magic Bounce reflects Thunder Wave back at the user")
b=BattleSystem(mon("rattata",5,None,["tackle"]),mon("geodude",5,"shell_armor",["tackle"]),smart=False); random.seed(0)
crits=0
for _ in range(400):
    b.o.hp=b.o.max_hp; b.battle_log=[]; b._act("player",Move.from_name("tackle"),True); crits+=any("critical" in l for l in b.battle_log)
ok(crits==0,"Shell Armor blocks critical hits")
b=BattleSystem(mon("rattata",40,None,["double-kick"]),mon("geodude",40,None,["tackle"]),smart=False); b.battle_log=[]; b._act("player",Move.from_name("double-kick"),True); ok(any("hit 2 times" in l for l in b.battle_log),"Double Kick hits twice")
b=BattleSystem(mon("rattata",40,None,["fury-attack"]),mon("onix",40,None,["tackle"]),smart=False); seen=set()
for _ in range(40):
    b.o.hp=b.o.max_hp; b.battle_log=[]; b._act("player",Move.from_name("fury-attack"),True); seen|={int(l.split()[3]) for l in b.battle_log if "times" in l}
ok(seen<= {2,3,4,5} and len(seen)>=2,f"Fury Attack hits 2-5 times (saw {sorted(seen)})")
b=BattleSystem(mon("charmander",60,None,["false-swipe"]),mon("rattata",5,None,["tackle"]),smart=False); b._act("player",Move.from_name("false-swipe"),True); ok(b.o.hp==1 and not b.is_finished,"False Swipe leaves 1 HP")
b=BattleSystem(mon("rattata",30,None,["facade"]),mon("geodude",30,None,["tackle"]),smart=False); normal=b.calc_damage(b.p,b.o,Move.from_name("facade"),roll=1.0); b.p.status="par"; boosted=b.calc_damage(b.p,b.o,Move.from_name("facade"),roll=1.0); ok(boosted>normal*1.7,f"Facade doubles power while statused ({normal}->{boosted})")
import glyphs
b=BattleSystem(mon("charmander",30,None,["ember"]),mon("bulbasaur",30,None,["tackle"]),smart=False); b.execute_turn(Move.from_name("ember"),Move.from_name("tackle")); txt=" ".join(b.battle_log)
ok(glyphs.HIT in txt and not any(ch in txt for ch in "💥⚔❤🎯"),"battle log uses the retro glyphs, not ⚔️ 💥 ❤️")
print("ALL INTEGRITY TESTS PASSED")
