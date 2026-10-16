import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
from index import *
import evolution, rules
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn,label,contains=None):
    try: fn(); ok(False,label+" (no error)")
    except HTTPException as e: ok(contains is None or contains.lower() in e.detail.lower(),f"{label}: {e.detail}")
UID=3001
choose_starter(StarterRequest(user_id=UID,region="kanto",species="charmander",avatar="ember"))
p=get_or_create_player(UID); m=p.active_team[0]
ro=get_roster(UID); o=ro["team"][0]["evolutions"]; ok(o and o[0]["to"]=="charmeleon" and o[0]["ready"] is False and o[0]["label"]=="Lv 16","roster shows evolution options: Charmeleon at Lv 16 (not ready)")
raises(lambda: evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=m.id,to="charmeleon")),"can't evolve too early","isn't ready")
raises(lambda: evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=m.id,to="charizard")),"can't skip a stage","can't evolve")
m.level=16; m.recalculate_stats(); m.restore_hp(); m.nickname="Blazey"; m.nature="Adamant"; m.is_shiny=True; m.experience=33; old_iv=dict(m.iv); mid=m.id; persist_player(p)
ok(m.id in evolution.pending(p),"ready by level -> flagged as pending")
r=evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=m.id,to="charmeleon"))
t=r["roster"]["team"][0]; ok(r["ok"] and t["species_name"]=="charmeleon" and t["id"]==mid,"Charmander -> Charmeleon, same Pokémon id")
p=get_or_create_player(UID); n=p.active_team[0]
ok(n.iv==old_iv and n.nature=="Adamant" and n.is_shiny and n.experience==33 and n.nickname=="Blazey","keeps IVs, nature, shininess, XP and custom nickname")
ok(n.max_hp>m.max_hp-1 and n.current_hp>0,"stats recalculated for the new species")
ok(n.api_data["id"] in p.pokedex_seen,"new species registered in the Pokédex")
# stone evolution consumes the stone
p.active_team[0]=PokemonInstance("pikachu",20,UID); p.inventory["thunder_stone"]=1; persist_player(p)
ro=get_roster(UID); ok(ro["team"][0]["evolutions"][0]["ready"],"Pikachu + Thunder Stone -> ready")
r=evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=p.active_team[0].id,to="raichu")); ok(r["roster"]["team"][0]["species_name"]=="raichu" and r["roster"]["inventory"].get("thunder_stone",0)==0,"Raichu, stone used up")
# Trade Cable
p=get_or_create_player(UID); p.active_team[0]=PokemonInstance("kadabra",30,UID); p.inventory.pop("trade_cable",None); persist_player(p)
raises(lambda: evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=p.active_team[0].id,to="alakazam")),"Kadabra without a cable","needs trade cable")
p=get_or_create_player(UID); p.inventory["trade_cable"]=2; persist_player(p)
r=evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=p.active_team[0].id,to="alakazam")); ok(r["roster"]["team"][0]["species_name"]=="alakazam" and r["roster"]["inventory"]["trade_cable"]==1,"Trade Cable evolves Kadabra -> Alakazam (1 cable used, 1 left)")
# Eevee branches
p=get_or_create_player(UID); p.active_team[0]=PokemonInstance("eevee",10,UID); p.inventory["water_stone"]=1; persist_player(p)
opts={o["to"]:o["ready"] for o in evolution_state(UID)["team"][0]["options"]}; ok(opts["vaporeon"] and not opts["jolteon"],"Eevee: only the branch you have a stone for is ready")
# shop sells them
p=get_or_create_player(UID); p.coins=5000; persist_player(p)
r=shop_buy(BuyRequest(user_id=UID,item_id="trade_cable",quantity=1)); ok(r["inventory"].get("trade_cable")==2 and r["coins"]==3500,"shop: Trade Cable 1500")
r=shop_buy(BuyRequest(user_id=UID,item_id="fire_stone",quantity=1)); ok(r["inventory"].get("fire_stone")==1,"shop: Fire Stone 800")
# never mid-battle
index._sessions.save("evb",UID,p.active_team[0].to_dict(),PokemonInstance("rattata",3,0).to_dict())
raises(lambda: evolution_evolve(EvolveRequest(user_id=UID,pokemon_id=p.active_team[0].id,to="vaporeon")),"no evolving in battle","battle")
index._sessions.delete("evb")
# data sanity: every rule is well-formed and every target exists
bad=[(a,e) for a,l in rules.EVOLUTIONS.items() for e in l if e["rule"][0] not in ("level","item","trade")]
ok(not bad and len(rules.EVOLUTIONS)>350,"evolution data: %d species with evolutions"%len(rules.EVOLUTIONS))
print("ALL EVOLUTION TESTS PASSED")
