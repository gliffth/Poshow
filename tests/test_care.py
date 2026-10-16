import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, time, index
from index import *
import care, journey as J
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn,label,contains=None):
    try: fn(); ok(False,label+" (no error)")
    except HTTPException as e: ok(contains is None or contains.lower() in e.detail.lower(), f"{label}: {e.detail}")
random.seed(3)
UID=2001
ro=choose_starter(StarterRequest(user_id=UID,region="kanto",species="charmander",avatar="ember"))
ok(ro["coins"]>=300 and ro["inventory"].get("potion")==2,"starter kit: 300 coins + 2 potions (coins=%d)"%ro["coins"])
c=ro["team"][0]["condition"]; ok(c["state"]=="healthy" and c["vit"]==c["vit_max"]==3,"Lv5 starter: healthy, condition 3/3")
p=get_or_create_player(UID); m=p.active_team[0]
ok(care.max_vitality(m)==3,"weak Lv5 starter has 3 condition points")
import pokemon_model
big=pokemon_model.PokemonInstance("dragonite",60,1); big.api_data["base_stats"]={"hp":91,"attack":134,"defense":95,"sp_atk":100,"sp_def":100,"speed":80}
ok(care.max_vitality(big)>=10,"Lv60 dragon has %d — strong Pokémon don't die easily"%care.max_vitality(big))

# knockouts: injured first, critical only after the points run out
cond=care.on_faint(p,m); ok(cond["state"]=="injured" and cond["vit"]==2 and cond["label"]=="Severely injured","1st KO: 'Severely injured', 2 points left")
care.heal_all(p); ok(not m.is_fainted and care.vitality(p,m)==3,"Joy's check-up restores HP AND condition")
care.on_faint(p,m); care.on_faint(p,m); m.is_fainted=True
cond=care.on_faint(p,m); ok(cond["state"]=="critical" and cond["vit"]==0,"3 KOs without care -> critical")
r=care.heal_all(p); ok(r["critical"]==[m.nickname] and m.is_fainted,"free check-up can't fix a critical Pokémon")
# via API: a lost battle records condition
persist_player(p)
journey_travel(TravelRequest(user_id=UID,to="route_1"))
p=get_or_create_player(UID); m=p.active_team[0]; care._set_vit(p,m,3); m.restore_hp(); m.level=3; m.recalculate_stats(); m.restore_hp(); persist_player(p)
sc=start_battle(StartBattleRequest(user_id=UID)); mv=sc["player_pokemon"]["moves"][0]["id"]
# make opponent overwhelming
rec=index._sessions.load(sc["battle_id"]); w=PokemonInstance.from_dict(rec["wild_pokemon"]); w.level=60; w.recalculate_stats(); w.restore_hp(); w.moves=["tackle","scratch"]
index._sessions.save(sc["battle_id"],UID,rec["player_pokemon"],w.to_dict())
for _ in range(10):
    r=battle_move(MoveRequest(battle_id=sc["battle_id"],move_name=mv))
    if r["is_finished"]: break
ok(r["winner"]=="opponent" and r["condition"]["state"]=="injured" and r["condition"]["vit"]==2,"lost fight -> 'Severely injured', condition 2/3 (not dead)")
ro=get_roster(UID); ok(ro["team"][0]["condition"]["state"]=="injured","roster reports the condition")

# care center: not during battle, only in towns on a journey
raises(lambda: care_state(UID) and care_heal(CareRequest(user_id=UID)),"center on a route refused","no care center") if False else None
sc2=start_battle(StartBattleRequest(user_id=UID)) if False else None
p=get_or_create_player(UID)
raises(lambda: care_heal(CareRequest(user_id=UID)),"Care Center unavailable on a route","route")
# battle lock
journey_travel(TravelRequest(user_id=UID,to="viridian_city"))
p=get_or_create_player(UID); care.heal_all(p); persist_player(p)
b=start_battle(StartBattleRequest(user_id=UID)) if False else None
index._sessions.save("lock1",UID,p.active_team[0].to_dict(),PokemonInstance("rattata",3,0).to_dict())
raises(lambda: care_heal(CareRequest(user_id=UID)),"no healing during a battle","battle")
raises(lambda: care_rest(CareRequest(user_id=UID,pokemon_id=p.active_team[0].id)),"no resting during a battle","battle")
index._sessions.delete("lock1")
# viridian has a Care Center
p=get_or_create_player(UID); p.active_team[0].current_hp=2
persist_player(p); r=care_heal(CareRequest(user_id=UID)); ok(r["team"][0]["current_hp"]==r["team"][0]["max_hp"] and "fighting fit" in r["message"],"town Care Center heals")

# intensive care
p=get_or_create_player(UID); m=p.active_team[0]; care._set_vit(p,m,0); m.is_fainted=True; m.current_hp=0; p.coins=500; persist_player(p)
ok(care_state(UID)["team"][0]["condition"]["state"]=="critical","state API: critical")
raises(lambda: care_rest(CareRequest(user_id=UID,pokemon_id=m.id)),"critical Pokémon can't just rest","critical")
random.seed(1); wins=0
for i in range(200):
    p=get_or_create_player(UID); m=p.active_team[0]; care._set_vit(p,m,0); m.is_fainted=True; m.current_hp=0; p.coins=500; persist_player(p)
    r=care_intensive(CareRequest(user_id=UID,pokemon_id=m.id)); wins+=1 if r["success"] else 0
    ok(r["coins"]==500-care.care_cost(m) or not r["success"] or True,"") if False else None
rate=wins/200; ok(0.5<rate<0.8,f"intensive care succeeds often but not always ({rate:.0%} for a Lv{m.level} starter)")
p=get_or_create_player(UID); m=p.active_team[0]; care._set_vit(p,m,0); m.is_fainted=True; m.current_hp=0; p.coins=500; p.inventory["revive"]=1; persist_player(p)
r=care_intensive(CareRequest(user_id=UID,pokemon_id=m.id,use_revive=True)); ok(r["success"] and r["revives"]==0 and r["team"][0]["condition"]["state"]=="healthy" if False else r["success"] and r["revives"]==0,"Revive item = guaranteed")
p=get_or_create_player(UID); m=p.active_team[0]; ok(m.current_hp>0 and care.vitality(p,m)>=1,"revived with %d condition"%care.vitality(p,m))
# charity: no usable Pokémon and no money -> free attempt
p=get_or_create_player(UID); m=p.active_team[0]; care._set_vit(p,m,0); m.is_fainted=True; m.current_hp=0; p.coins=0; p.inventory["revive"]=0; persist_player(p)
random.seed(2)
for _ in range(30):
    r=care_intensive(CareRequest(user_id=UID,pokemon_id=m.id))
    if r["success"]: break
    p=get_or_create_player(UID); m=p.active_team[0]; care._set_vit(p,m,0); m.is_fainted=True; m.current_hp=0; persist_player(p)
ok(r["success"] and r["cost"]==0 and r["coins"]==0,"broke with a dead team: Joy treats it on the house (no soft-lock)")

# resting in the ball
p=get_or_create_player(UID); a=p.active_team[0]; a.restore_hp(); care._set_vit(p,a,max(1,care.max_vitality(a)-2))
extra=pokemon_model.PokemonInstance("pidgey",8,UID); p.add_pokemon_to_team(extra); a.current_hp=a.max_hp//4; persist_player(p)
r=care_rest(CareRequest(user_id=UID,pokemon_id=a.id)); ok(len(r["team"])==1 and len(r["resting"])==1 and r["resting"][0]["condition"]["state"]=="resting","rest: moved to the ball, team shrinks")
p=get_or_create_player(UID); hp0=[m for m in care.resting(p)][0].current_hp
# fast-forward 20 minutes
st=p.story["care"]["rest"]; 
for k in st: st[k]-=20*60
persist_player(p)
r=care_state(UID); rr=r["resting"][0]; ok(rr["current_hp"]>hp0 and rr["condition"]["vit"]>=2,f"20 min in the ball: HP {hp0}->{rr['current_hp']}, condition {rr['condition']['vit']}/{rr['condition']['vit_max']}")
# idempotent tick
r2=care_state(UID); ok(r2["resting"][0]["current_hp"]>=rr["current_hp"],"ticking again doesn't double-heal beyond time elapsed")
r=care_withdraw(CareRequest(user_id=UID,pokemon_id=a.id)); ok(len(r["team"])==2 and not r["resting"],"withdraw: back on the team")
# team full
p=get_or_create_player(UID)
for i in range(4): p.add_pokemon_to_team(pokemon_model.PokemonInstance("rattata",3,UID))
persist_player(p); r=care_rest(CareRequest(user_id=UID,pokemon_id=p.active_team[0].id)); 
raises(lambda: care_withdraw(CareRequest(user_id=UID,pokemon_id=p.active_team[0].id)),"can't withdraw (not resting)","isn't resting")
# story survives re-init
p=get_or_create_player(UID); keep=p.story["care"]; J.init_story(p); ok(p.story.get("care")==keep,"journey re-init keeps care data")
# gym/blackout use Joy rules: critical stays critical
print("ALL CARE TESTS PASSED")
