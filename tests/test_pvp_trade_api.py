import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random, index
from index import *
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
def st(fn):
    try: return fn(),200
    except HTTPException as e: return None,e.status_code
    except Exception as e: return None,type(e).__name__
random.seed(2)
pings=[]; index.notify_telegram=lambda uid,text,buttons=None: pings.append((uid,text))
A=auth_register(RegisterRequest(username="Ash_K",password="secret1")); B=auth_register(RegisterRequest(username="Gary_K",password="secret1"))
ua,ub=A["user_id"],B["user_id"]
choose_starter(StarterRequest(user_id=ua,region="kanto",species="charmander",avatar="ember"))
choose_starter(StarterRequest(user_id=ub,region="kanto",species="squirtle",avatar="frost"))
for uid,mons in ((ua,[("pidgey",12),("rattata",8)]),(ub,[("geodude",14)])):
    p=get_or_create_player(uid)
    for sp,lv in mons: p.add_pokemon_to_team(PokemonInstance(sp,lv,uid))
    persist_player(p)
# ---------- PvP over the API ----------
v=pvp_challenge(PvpChallengeRequest(user_id=ua,username="gary_k"))
ok(v["status"]=="pending" and any(u==ub for u,_ in pings),"challenge by username; opponent pinged")
s=pvp_state(ub); ok(len(s["incoming"])==1 and s["incoming"][0]["from"]=="Ash_K","opponent sees the incoming challenge")
mid=s["incoming"][0]["id"]
v=pvp_respond(PvpRespondRequest(user_id=ub,match_id=mid,accept=True)); ok(v["status"]=="active" and len(v["me"]["team"])==2,"accepted -> duel starts (Gary has 2 Pokémon)")
sa=pvp_state(ua); ok(sa["active"]["status"]=="active" and len(sa["active"]["me"]["team"])==3,"challenger sees the active duel (Ash has 3)")
guard=0
while guard<300:
    guard+=1
    for uid in (ua,ub):
        cur=pvp_state(uid)["active"]
        if not cur or cur["status"]!="active": continue
        me=cur["me"]; act=me["team"][me["active"]]
        if cur["phase"]=="switch":
            if cur["needs_switch"]:
                to=next(i for i,m in enumerate(me["team"]) if m["hp"]>0); pvp_action(PvpActionRequest(user_id=uid,match_id=mid,action={"type":"switch","to":to}))
        elif not cur["waiting"]:
            pvp_action(PvpActionRequest(user_id=uid,match_id=mid,action={"type":"move","move":act["moves"][0]["id"]}))
    if pvp_state(ua)["active"]["status"]=="finished": break
fin=pvp_state(ua)["active"]; ok(fin["status"]=="finished" and fin["winner"] in ("a","b"),f"duel played to the end in {guard} rounds")
ea=get_or_create_player(ua); eb=get_or_create_player(ub)
ok(ea.elo+eb.elo==2000 and ea.elo!=eb.elo and ea.wins+eb.wins==1,f"ELO persisted: Ash {ea.elo}, Gary {eb.elo}")
ok(all(m.current_hp==m.max_hp for m in ea.active_team+eb.active_team),"real Pokémon untouched")
lb=leaderboard(); ok(lb["leaderboard"][0]["elo"]>=lb["leaderboard"][-1]["elo"] and lb["leaderboard"][0]["rank"]==1,"leaderboard ranks by ELO: "+str([(r["username"],r["elo"]) for r in lb["leaderboard"][:2]]))
v,code=st(lambda: pvp_challenge(PvpChallengeRequest(user_id=ua,username="nobody_here"))); ok(code==404,"unknown opponent 404")
# ---------- trading over the API ----------
r=trade_invite(TradeInviteRequest(user_id=ua,username="Gary_K")); tid=r["id"]
s=trade_state(ub); ok(len(s["incoming"])==1,"trade invite visible to the other trainer")
v=trade_respond(TradeRespondRequest(user_id=ub,trade_id=tid,accept=True)); ok(v["status"]=="open","trade opened")
pa=get_or_create_player(ua); pb=get_or_create_player(ub)
give=pa.active_team[1].id; take=pb.active_team[1].id
trade_offer(TradeOfferRequest(user_id=ua,trade_id=tid,pokemon_id=give,coins=25))
v=trade_offer(TradeOfferRequest(user_id=ub,trade_id=tid,pokemon_id=take))
ok(v["pokemon"]["a"]["species"]=="pidgey" and v["pokemon"]["b"]["species"]=="geodude","each side sees the other's offered Pokémon (species/level)")
trade_lock(TradeStepRequest(user_id=ua,trade_id=tid)); trade_lock(TradeStepRequest(user_id=ub,trade_id=tid))
c,code=st(lambda: trade_confirm(TradeStepRequest(user_id=ua,trade_id=tid))); ok(code==200 and c["status"]=="open","first confirm waits")
c=trade_confirm(TradeStepRequest(user_id=ub,trade_id=tid)); ok(c["status"]=="done","second confirm completes the trade")
pa=get_or_create_player(ua); pb=get_or_create_player(ub)
ok("geodude" in [m.species_name for m in pa.active_team+pa.pokemon_collection] and "pidgey" in [m.species_name for m in pb.active_team+pb.pokemon_collection],"Pokémon really changed hands (persisted)")
ok(pa.coins+pb.coins>0,"credits moved")
# trade-evolution via trade
p1=get_or_create_player(ua); p1.add_pokemon_to_team(PokemonInstance("kadabra",30,ua)); persist_player(p1)
p2=get_or_create_player(ub); p2.add_pokemon_to_team(PokemonInstance("rattata",4,ub)); persist_player(p2)
r=trade_invite(TradeInviteRequest(user_id=ua,username="Gary_K")); tid=r["id"]; trade_respond(TradeRespondRequest(user_id=ub,trade_id=tid,accept=True))
kid=[m for m in get_or_create_player(ua).active_team if m.species_name=="kadabra"][0].id
trade_offer(TradeOfferRequest(user_id=ua,trade_id=tid,pokemon_id=kid)); trade_lock(TradeStepRequest(user_id=ua,trade_id=tid)); trade_lock(TradeStepRequest(user_id=ub,trade_id=tid))
trade_confirm(TradeStepRequest(user_id=ua,trade_id=tid)); c=trade_confirm(TradeStepRequest(user_id=ub,trade_id=tid))
ok("alakazam" in [m.species_name for m in get_or_create_player(ub).active_team+get_or_create_player(ub).pokemon_collection] and c["result"]["evolved"],"Kadabra traded away -> Alakazam on arrival: "+str(c["result"]["evolved"]))
print("ALL PVP/TRADE API TESTS PASSED")
