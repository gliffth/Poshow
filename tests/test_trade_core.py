import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random
import trade_system as T, care
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn,label,contains=None):
    try: fn(); ok(False,label+" (no error)")
    except T.TradeError as e: ok(contains is None or contains.lower() in str(e).lower(),f"{label}: {e}")
def tr(uid,name,mons,coins=1000):
    p=PlayerInstance(uid,name); p.coins=coins
    for sp,lv in mons: p.add_pokemon_to_team(PokemonInstance(sp,lv,uid))
    return p
A=tr(1,"Ash",[("kadabra",30),("pidgey",8)]); B=tr(2,"Gary",[("machoke",30),("rattata",5)])
A.inventory["potion"]=5
store=T.new_store(); players={"a":A,"b":B}
raises(lambda: T.invite(store,A,1,"Ash"),"not with yourself","yourself")
d=T.invite(store,A,2,"Gary"); raises(lambda: T.invite(store,A,2,"Gary"),"no double invite","already")
raises(lambda: T.respond(store,d["id"],A,True),"only the invitee answers","isn't for you")
d=T.respond(store,d["id"],B,True); ok(d["status"]=="open","accepted -> open")
tid=d["id"]
kad=A.active_team[0].id; mac=B.active_team[0].id
raises(lambda: T.set_offer(store,tid,A,pokemon_id=mac),"can't offer someone else's Pokémon","isn't yours")
T.set_offer(store,tid,A,pokemon_id=kad); T.set_offer(store,tid,B,pokemon_id=mac)
raises(lambda: T.set_offer(store,tid,A,coins=5000),"can't offer credits you lack","don't have")
raises(lambda: T.set_offer(store,tid,A,items={"potion":9}),"can't offer items you lack","don't have")
T.set_offer(store,tid,A,coins=100,items={"potion":2})
raises(lambda: T.confirm(store,tid,A,players),"confirm needs both locked","lock")
T.lock(store,tid,A); T.lock(store,tid,B)
d=store.load(tid); ok(all(d["state"]["locked"].values()),"both locked")
T.set_offer(store,tid,B,coins=50); d=store.load(tid); ok(not any(d["state"]["locked"].values()),"changing an offer un-locks everyone (no last-second swaps)")
T.lock(store,tid,A); T.lock(store,tid,B)
T.confirm(store,tid,A,players); d=store.load(tid); ok(d["status"]=="open" and d["state"]["confirmed"]["a"],"one confirmation isn't enough")
ac,bc=A.coins,B.coins
d=T.confirm(store,tid,B,players); ok(d["status"]=="done","both confirmed -> trade executes")
ok([m.species_name for m in A.active_team]==["pidgey","machamp"] or "machamp" in [m.species_name for m in A.active_team],"Ash received Gary's Machoke — and it evolved by trade into Machamp: "+str([m.species_name for m in A.active_team]))
ok("alakazam" in [m.species_name for m in B.active_team],"Gary received Kadabra and it became Alakazam: "+str([m.species_name for m in B.active_team]))
ok(A.coins==ac-100+50 and B.coins==bc+100-50,"credits swapped (A %d, B %d)"%(A.coins,B.coins))
ok(A.inventory.get("potion")==3 and B.inventory.get("potion")==2,"items moved")
ok(all(m.trainer_id==A.user_id for m in A.active_team if m.species_name=="machamp"),"ownership updated on the Pokémon")
ok(len(d["state"]["result"]["evolved"])==2,"result reports both trade evolutions")
ok(A.inventory.get("trade_cable",0)==0 and B.inventory.get("trade_cable",0)==0,"trade evolution did not leave stray Trade Cables")
# one-sided gift
C=tr(3,"Misty",[("staryu",20),("psyduck",10)]); D=tr(4,"Brock",[("onix",20)]); pl={"a":C,"b":D}
d=T.invite(store,C,4,"Brock"); T.respond(store,d["id"],D,True); tid=d["id"]
T.set_offer(store,tid,C,pokemon_id=C.active_team[1].id); T.lock(store,tid,C); T.lock(store,tid,D); T.confirm(store,tid,C,pl); T.confirm(store,tid,D,pl)
ok(len(C.active_team)==1 and len(D.active_team)==2,"gift: Misty gives Psyduck, gets nothing")
# last Pokémon
d=T.invite(store,D,3,"Misty"); T.respond(store,d["id"],C,True); tid=d["id"]; pl={"a":D,"b":C}
E=tr(5,"Solo",[("pikachu",5)]); F=tr(6,"Other",[("rattata",3)]); pl2={"a":E,"b":F}
d=T.invite(store,E,6,"Other"); T.respond(store,d["id"],F,True); t2=d["id"]
T.set_offer(store,t2,E,pokemon_id=E.active_team[0].id); T.lock(store,t2,E); T.lock(store,t2,F); T.confirm(store,t2,E,pl2)
raises(lambda: T.confirm(store,t2,F,pl2),"can't trade away your only team Pokémon","only team")
ok(len(E.active_team)==1 and E.active_team[0].species_name=="pikachu","nothing changed after the refusal")
# critical / resting can't be offered
G=tr(7,"G",[("rattata",5),("pidgey",5)]); H=tr(8,"H",[("rattata",5)])
care._set_vit(G,G.active_team[0],0); G.active_team[0].is_fainted=True; G.active_team[0].current_hp=0
d=T.invite(store,G,8,"H"); T.respond(store,d["id"],H,True)
raises(lambda: T.set_offer(store,d["id"],G,pokemon_id=G.active_team[0].id),"critical Pokémon can't be traded","critical")
care.rest(G,G.active_team[1].id)
raises(lambda: T.set_offer(store,d["id"],G,pokemon_id=care.resting(G)[0].id),"sleeping Pokémon can't be traded","sleeping")
# cancel
T.cancel(store,d["id"],7); ok(store.load(d["id"])["status"]=="cancelled","cancel")
raises(lambda: T.set_offer(store,d["id"],G,coins=1),"cancelled trade is closed","isn't open")
print("ALL TRADE CORE TESTS PASSED")
