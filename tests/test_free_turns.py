import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Using an item / failing to run / switching all give the opponent a turn (and can end the fight); gym re-entry resumes.
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import random, accounts, index
from battle_system import BattleSystem, Move
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
random.seed(9)
_orig_opp = BattleSystem.get_opponent_move
def strongest(on):
    BattleSystem.get_opponent_move = (lambda self: Move.from_name('psystrike')) if on else _orig_opp
def mk(name):
    u = auth_register(RegisterRequest(username=name, password="secret1"))["user_id"]
    choose_starter(StarterRequest(user_id=u, region="kanto", species="squirtle")); journey_travel(TravelRequest(user_id=u, to="route_1")); return u
def fight(u, species="pidgey", level=5):
    tok = accounts.make_encounter_token(u, species, level)
    return start_battle(StartBattleRequest(user_id=u, target_species=species, target_level=level, encounter_token=tok))
def set_player_hp(bid, u, hp):
    rec = index._sessions.load(bid); rec["player_pokemon"]["current_hp"] = hp
    index._sessions.save(bid, u, rec["player_pokemon"], rec["wild_pokemon"])

# ---- item: heals, consumes ONE item, and the opponent still acts
u = mk("Free_1"); p = get_or_create_player(u); p.inventory["potion"] = 3; persist_player(p)
bt = fight(u); bid = bt["battle_id"]; set_player_hp(bid, u, 5)
out = battle_item(ItemRequest(battle_id=bid, item_type="potion"))
ok(any("Restored" in l for l in out["log"]) and len(out["log"]) > 1, "item use: heal message AND the opponent's move are in the log: %s" % out["log"][:3])
ok(get_or_create_player(u).inventory["potion"] == 2, "exactly one potion consumed")
ok(out["player_pokemon"]["current_hp"] != 5, "HP changed (healed, then the enemy turn)")
ok(index._sessions.load(bid)["player_pokemon"]["current_hp"] == out["player_pokemon"]["current_hp"], "the session holds the post-turn HP")

# ---- item that cannot save you: the enemy's turn ends the fight (finished + session closed + HP persisted)
u = mk("Free_2"); p = get_or_create_player(u); p.inventory["potion"] = 3; persist_player(p)
bt = fight(u, "mewtwo", 100); bid = bt["battle_id"]; set_player_hp(bid, u, 1)
strongest(True)
out = battle_item(ItemRequest(battle_id=bid, item_type="potion"))
strongest(False)
ok(out["is_finished"] and out["winner"] != "player", "a potion against Lv100 Mewtwo: the fight is over (winner=%s)" % out["winner"])
ok(not any(r["user_id"] == u for r in fake.rows["battle_sessions"]), "…and the session was closed")
ok(out["remaining"] == 2, "…and the answer still reports the remaining potions")

# ---- failed escape costs the turn
u = mk("Free_3"); bt = fight(u); bid = bt["battle_id"]
real_rand = random.random; random.random = lambda: 0.99          # every escape roll fails
out = battle_flee(FleeRequest(battle_id=bid))
random.random = real_rand
ok(out["success"] is False and out["turn"]["log"][0] == "Couldn't escape!" and len(out["turn"]["log"]) > 1, "failed escape: the opponent attacked: %s" % out["turn"]["log"][:3])
ok(index._sessions.load(bid) is not None or out["turn"]["is_finished"], "the fight goes on unless that attack ended it")
u = mk("Free_4"); bt = fight(u, "mewtwo", 100); bid = bt["battle_id"]; set_player_hp(bid, u, 1)
random.random = lambda: 0.99; strongest(True)
out = battle_flee(FleeRequest(battle_id=bid))
random.random = real_rand; strongest(False)
ok(out["success"] is False and out["turn"]["is_finished"], "failing to run from Mewtwo at 1 HP loses the battle")
ok(not any(r["user_id"] == u for r in fake.rows["battle_sessions"]), "…and the session is closed")
u = mk("Free_5"); bt = fight(u); bid = bt["battle_id"]
random.random = lambda: 0.0
out = battle_flee(FleeRequest(battle_id=bid)); random.random = real_rand
ok(out == {"success": True} and not any(r["user_id"] == u for r in fake.rows["battle_sessions"]), "a successful escape is unchanged")

# ---- gym: re-entering the same floor resumes the open fight instead of resetting the opponent
u = mk("Free_6")
g1 = gym_enter(GymEnterRequest(user_id=u))
rec = index._sessions.load(g1["battle_id"]); rec["wild_pokemon"]["current_hp"] = 1
index._sessions.save(g1["battle_id"], u, rec["player_pokemon"], rec["wild_pokemon"])
g2 = gym_enter(GymEnterRequest(user_id=u))
ok(g2.get("resumed") and g2["battle_id"] == g1["battle_id"], "re-entering resumes the same battle")
ok(g2["wild_pokemon"]["current_hp"] == 1, "the opponent keeps its damage (no free reset)")
ok(sum(1 for r in fake.rows["battle_sessions"] if r["user_id"] == u) == 1, "still exactly one session")
# ---- a failed Poké Ball throw gives the wild Pokémon its move (and can lose the fight)
u = mk("Free_7"); p = get_or_create_player(u); p.pokeballs["pokeball"] = 9; persist_player(p)
bt = fight(u); bid = bt["battle_id"]
from pokeball_system import CatchSystem
orig_calc = CatchSystem.calculate_catch_chance
def never(self, *a, **k):
    r = orig_calc(self, *a, **k); r["will_catch"] = False; return r
CatchSystem.calculate_catch_chance = never
out = battle_catch(CatchRequest(battle_id=bid, ball_type="pokeball"))
ok(out["will_catch"] is False and "turn" in out and len(out["turn"]["log"]) >= 1, "failed throw returns the wild Pokémon's turn: %s" % out["turn"]["log"][:2])
ok(get_or_create_player(u).pokeballs["pokeball"] == 8, "exactly one ball spent")
ok(index._sessions.load(bid)["wild_pokemon"]["bt"]["turn"] == 1, "the turn counter advanced with that turn")
# repeated throws against a hard hitter eventually lose the fight — no free infinite throws
u = mk("Free_8"); p = get_or_create_player(u); p.pokeballs["pokeball"] = 30; persist_player(p)
bt = fight(u, "mewtwo", 100); bid = bt["battle_id"]; strongest(True)
finished = False
for _ in range(10):
    o = battle_catch(CatchRequest(battle_id=bid, ball_type="pokeball"))
    if o["turn"]["is_finished"]: finished = True; break
strongest(False)
ok(finished and not any(r["user_id"] == u for r in fake.rows["battle_sessions"]), "spamming balls at Mewtwo ends in a loss, session closed")
# a throw whose save fails: no ball spent, no enemy move
u = mk("Free_9"); p = get_or_create_player(u); p.pokeballs["pokeball"] = 5; persist_player(p)
bt = fight(u); bid = bt["battle_id"]; before = index._sessions.load(bid)["player_pokemon"]["current_hp"]
fake.fail_pokemon_write = True
try: battle_catch(CatchRequest(battle_id=bid, ball_type="pokeball")); raised = False
except Exception: raised = True
fake.fail_pokemon_write = False
ok(raised and get_or_create_player(u).pokeballs["pokeball"] == 5 and index._sessions.load(bid)["player_pokemon"]["current_hp"] == before, "save failure: ball not spent, fight untouched")
CatchSystem.calculate_catch_chance = orig_calc

# ---- trading refuses while either side is in a battle
ua, ub = mk("TradeBat_A"), mk("TradeBat_B")
tid = trade_invite(TradeInviteRequest(user_id=ua, username="TradeBat_B"))["id"]
trade_respond(TradeRespondRequest(user_id=ub, trade_id=tid, accept=True))
give = get_or_create_player(ua).active_team[0].id; take = get_or_create_player(ub).active_team[0].id
trade_offer(TradeOfferRequest(user_id=ua, trade_id=tid, pokemon_id=give)); trade_offer(TradeOfferRequest(user_id=ub, trade_id=tid, pokemon_id=take))
trade_lock(TradeStepRequest(user_id=ua, trade_id=tid)); trade_lock(TradeStepRequest(user_id=ub, trade_id=tid))
trade_confirm(TradeStepRequest(user_id=ua, trade_id=tid))
fight(ub)                                                     # B walks into a battle after A confirmed
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
ok(code(lambda: trade_confirm(TradeStepRequest(user_id=ua, trade_id=tid))) in (400, 409), "settlement refused (the confirming side can't force it)")
ok(code(lambda: trade_confirm(TradeStepRequest(user_id=ub, trade_id=tid))) == 400, "the trainer in battle can't confirm either")
ok(code(lambda: trade_offer(TradeOfferRequest(user_id=ub, trade_id=tid, coins=1))) == 400, "offers are refused during a battle")
ok(code(lambda: trade_lock(TradeStepRequest(user_id=ub, trade_id=tid))) == 400, "locking is refused during a battle")
ok(get_or_create_player(ua).active_team[0].id == give, "nothing moved")
battle_abandon(AbandonRequest(user_id=ub))
r = trade_confirm(TradeStepRequest(user_id=ub, trade_id=tid))
ok(r["status"] == "done", "once the battle is over the trade settles")
print("ALL FREE-TURN TESTS PASSED")
