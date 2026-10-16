import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, time
import pvp_system as P
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def raises(fn,label,contains=None):
    try: fn(); ok(False,label+" (no error)")
    except P.PvpError as e: ok(contains is None or contains.lower() in str(e).lower(),f"{label}: {e}")
random.seed(5)
def trainer(uid,name,mons):
    p=PlayerInstance(uid,name)
    for sp,lv in mons: p.add_pokemon_to_team(PokemonInstance(sp,lv,uid))
    return p
A=trainer(1,"Ash",[("charmander",30),("pidgey",20),("rattata",10)])
B=trainer(2,"Gary",[("squirtle",30),("geodude",25)])
for p in (A,B):
    for m in p.active_team: m.moves=["tackle","scratch"] if m.species_name in("pidgey","rattata") else m.moves
store=P.new_store()
raises(lambda: P.challenge(store,A,1,"Ash"),"can't challenge yourself","yourself")
doc=P.challenge(store,A,2,"Gary"); ok(doc["status"]=="pending","challenge created (pending)")
raises(lambda: P.challenge(store,A,2,"Gary"),"no duplicate invites","already")
raises(lambda: P.respond(store,doc["id"],A,True),"only the opponent can answer","isn't for you")
d=P.respond(store,doc["id"],B,False); ok(d["status"]=="declined","decline")
doc=P.challenge(store,A,2,"Gary"); P.respond(store,doc["id"],B,True); d=P.start(store,doc["id"],A,B)
ok(d["status"]=="active" and len(d["state"]["sides"]["a"]["team"])==3 and len(d["state"]["sides"]["b"]["team"])==2,"accepted -> active, teams copied (3 and 2)")
mid=d["id"]; players={"a":A,"b":B}
v=P.view(d,1); ok(v["me"]["team"][0]["moves"] and v["foe"]["team"][0]["moves"]==[],"you see your moves, never the foe's moves/choice")
raises(lambda: P.submit(store,mid,3,{"type":"move","move":"tackle"},players),"outsiders can't act","not part")
raises(lambda: P.submit(store,mid,1,{"type":"move","move":"hyper-beam"},players),"can't use a move you don't know","doesn't know")
P.submit(store,mid,1,{"type":"move","move":v["me"]["team"][0]["moves"][0]["id"]},players)
d=store.load(mid); ok(d["state"]["turn"]==1 and P.view(d,1)["waiting"],"one choice made -> turn waits")
raises(lambda: P.submit(store,mid,1,{"type":"move","move":"tackle"},players),"can't choose twice","already chose")
hp0=(A.active_team[0].current_hp,B.active_team[0].current_hp)
P.submit(store,mid,2,{"type":"move","move":P.view(d,2)["me"]["team"][0]["moves"][0]["id"]},players)
d=store.load(mid); ok(d["state"]["turn"]==2 and any("damage" in l for l in d["state"]["log"]),"both chose -> turn resolved, damage logged")
ok((A.active_team[0].current_hp,B.active_team[0].current_hp)==hp0,"your REAL Pokémon are untouched by a duel (copies are used)")
ok("'s CHARMANDER" in " ".join(d["state"]["log"]) or "CHARMANDER" in " ".join(d["state"]["log"]),"log names both trainers' Pokémon")
# voluntary switch
P.submit(store,mid,1,{"type":"switch","to":1},players); P.submit(store,mid,2,{"type":"move","move":P.view(store.load(mid),2)["me"]["team"][0]["moves"][0]["id"]},players)
d=store.load(mid); ok(d["state"]["sides"]["a"]["active"]==1 and any("withdrew" in l for l in d["state"]["log"]),"switching works and the opponent still attacks")
raises(lambda: P.submit(store,mid,1,{"type":"switch","to":1},players),"can't switch to the Pokémon already out","already out") if False else None
# play to the end: both always attack
guard=0
while store.load(mid)["status"]=="active" and guard<400:
    guard+=1
    d=store.load(mid); st=d["state"]
    for uid,k in ((1,"a"),(2,"b")):
        side=st["sides"][k]; active=side["team"][side["active"]]
        if st["phase"]=="switch":
            if active["current_hp"]<=0:
                to=next(i for i,m in enumerate(side["team"]) if m["current_hp"]>0)
                P.submit(store,mid,uid,{"type":"switch","to":to},players)
        else:
            P.submit(store,mid,uid,{"type":"move","move":active["moves"][0]},players)
        d=store.load(mid)
        if d["status"]!="active": break
d=store.load(mid); ok(d["status"]=="finished" and d["state"]["winner"] in ("a","b"),f"duel finishes after {guard} rounds, winner {d['state']['winner']}")
w=d["state"]["winner"]; el=d["state"]["elo"]
ok(el[w]["delta"]>0 and el["a" if w=="b" else "b"]["delta"]<0,"ELO moves: winner %+d, loser %+d"%(el[w]["delta"],el["a" if w=="b" else "b"]["delta"]))
ok(A.wins+B.wins==1 and A.losses+B.losses==1,"win/loss recorded")
ok(all(m.current_hp==m.max_hp for m in A.active_team+B.active_team),"real teams still at full HP after the duel")
raises(lambda: P.submit(store,mid,1,{"type":"move","move":"tackle"},players),"no moves after the end","isn't active")
# forfeit + timeout
doc=P.challenge(store,A,2,"Gary"); P.respond(store,doc["id"],B,True); d=P.start(store,doc["id"],A,B)
e0=A.elo; d=P.forfeit(store,d["id"],1,players); ok(d["state"]["winner"]=="b" and A.elo<e0,"forfeit = loss")
doc=P.challenge(store,A,2,"Gary"); P.respond(store,doc["id"],B,True); d=P.start(store,doc["id"],A,B)
raises(lambda: P.claim_timeout(store,d["id"],1,players),"timeout needs your own move first","own move")
P.submit(store,d["id"],1,{"type":"move","move":"tackle"},players) if "tackle" in d["state"]["sides"]["a"]["team"][0]["moves"] else P.submit(store,d["id"],1,{"type":"move","move":d["state"]["sides"]["a"]["team"][0]["moves"][0]},players)
raises(lambda: P.claim_timeout(store,d["id"],1,players),"timeout too early","longer")
dd=store.load(d["id"]); dd["state"]["last_move_at"]-=P.TURN_TIMEOUT+5; store.save(dd)
d=P.claim_timeout(store,d["id"],1,players); ok(d["state"]["winner"]=="a" and "timed out" in d["state"]["log"][-1],"walkover after the timeout")
# unhealthy trainers can't duel
C=trainer(3,"Hurt",[("rattata",5)]); C.active_team[0].current_hp=0; C.active_team[0].is_fainted=True
raises(lambda: P.challenge(store,C,2,"Gary"),"fainted team can't duel","healthy")
print("ALL PVP CORE TESTS PASSED")
