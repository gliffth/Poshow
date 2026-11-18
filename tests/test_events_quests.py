import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Event engine: quest progress, distinct counting, daily reset, claim-once, first-visit route rewards, and the rule
# that the engine never breaks game code. Then the real travel and quest endpoints.
import event_engine as EE
from player_model import PlayerInstance
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

def fresh():
    return PlayerInstance(501, "Quester")

# ── progress and completion ──────────────────────────────────────────────────
p = fresh()
done = []
for _ in range(9):
    done += EE.emit(p, "catch", "pidgey")
ok("catch_10" not in done and {q["id"]: q for q in EE.status(p)}["catch_10"]["progress"] == 9,
   "9 catches: catch_10 not finished yet (daily_catch_3 may already be)")
done = EE.emit(p, "catch", "pidgey")
ok("catch_10" in done, "the 10th catch completes catch_10")
ok(EE.emit(p, "catch", "pidgey") == [], "a finished quest doesn't complete again")

# ── claim: only when done, and only once ─────────────────────────────────────
coins = p.coins
ok(EE.claim(fresh(), "catch_10")["ok"] is False, "claim refused before the quest is finished")
r = EE.claim(p, "catch_10")
ok(r["ok"] and p.coins == coins + 500, "claim pays the reward (500 coins)")
ok(EE.claim(p, "catch_10")["ok"] is False and p.coins == coins + 500, "a second claim pays nothing")
ok(EE.claim(p, "no_such_quest")["ok"] is False, "unknown quest id refused")

# ── distinct counting (explore_5 counts routes, not visits) ──────────────────
p = fresh()
for _ in range(3):
    EE.emit(p, "visit", "route_1")                 # the same route three times counts once
ok(EE.status(p)[[q["id"] for q in EE.status(p)].index("explore_5")]["progress"] == 1,
   "the same route three times counts once")
for rid in ("route_2", "route_3", "route_4", "route_5"):
    EE.emit(p, "visit", rid)
st = {q["id"]: q for q in EE.status(p)}
ok(st["explore_5"]["done"], "five different routes complete explore_5")
ok(EE.emit(p, "visit", None) == [] and EE.emit(p, "visit", "route_9") == [], "no key / finished quest: nothing")

# ── daily quests reset on a new day ──────────────────────────────────────────
p = fresh()
day = {"d": "2026-10-23"}
EE.today = lambda: day["d"]
for _ in range(3):
    EE.emit(p, "catch", "rattata")
ok({q["id"]: q for q in EE.status(p)}["daily_catch_3"]["done"], "daily_catch_3 finishes on its day")
day["d"] = "2026-10-24"
s2 = {q["id"]: q for q in EE.status(p)}
ok(s2["daily_catch_3"]["progress"] == 0 and not s2["daily_catch_3"]["done"], "the daily quest starts over the next day")
ok(not {q["id"]: q for q in EE.status(p)}["catch_10"]["progress"] == 0,
   "permanent quests keep their progress across days")
EE.today = lambda: __import__("time").strftime("%Y-%m-%d", __import__("time").gmtime())

# ── first-visit route rewards ────────────────────────────────────────────────
p = fresh()
coins = p.coins
first = EE.grant_route_reward(p, "route_1")
ok(first is not None and first["coins"] == EE.route_reward_coins("route_1") and p.coins == coins + first["coins"],
   f"first visit to route_1 pays its reward ({first and first['coins']} coins)")
ok(EE.grant_route_reward(p, "route_1") is None, "the second visit pays nothing")
ok(EE.grant_route_reward(p, "vaniville_town") is None, "towns pay no route reward")
ok(EE.route_reward_coins("route_10") > EE.route_reward_coins("route_1"), "higher routes pay more")

# ── the engine never breaks game code ────────────────────────────────────────
class Broken:
    user_id = 0
    @property
    def story(self):
        raise RuntimeError("boom")
ok(EE.emit(Broken(), "catch", "pidgey") == [], "a broken player object doesn't raise out of emit()")

# ── the real endpoints ───────────────────────────────────────────────────────
import index
UID = 512
index.choose_starter(index.StarterRequest(user_id=UID, region="kanto", species="charmander"))
tr = index.journey_travel(index.TravelRequest(user_id=UID, to="route_1"))
ok(tr.get("route_reward") is not None, "travelling to route_1 reports the first-visit reward")
paid = index.get_or_create_player(UID).story.get("route_rewards", [])
ok(paid.count("route_1") == 1, "route_1 is recorded as paid once in the saved route rewards")
ok("quests" in index.quests_list(UID) and len(index.quests_list(UID)["quests"]) == len(EE.QUESTS),
   "the quest list endpoint returns every quest")

pl = index.get_or_create_player(UID)
EE.emit(pl, "catch", "pidgey")
st = pl.story["quests"]
for _ in range(10):
    EE.emit(pl, "catch", "pidgey")
index.persist_player(pl)
got = index.quests_claim(index.QuestClaimRequest(user_id=UID, quest_id="catch_10"))
ok(got["ok"] and any(q["id"] == "catch_10" and q["claimed"] for q in got["quests"]),
   "the claim endpoint pays a finished quest and marks it claimed")
try:
    index.quests_claim(index.QuestClaimRequest(user_id=UID, quest_id="catch_10"))
    again = 200
except index.HTTPException as e:
    again = e.status_code
ok(again == 400, "claiming the same quest twice is refused by the endpoint")

print("ALL PASS")
