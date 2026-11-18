import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Regression (audit v7 #5): a wild battle can only start from a scouted, signed encounter. A bare request must not
# roll an encounter, otherwise a client can reroll rare spawns without limit.
import index
from index import *
from fastapi import HTTPException
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

UID = 303
index.choose_starter(index.StarterRequest(user_id=UID, region="kanto", species="charmander"))
index.journey_travel(index.TravelRequest(user_id=UID, to="route_1"))

refused = 0
for _ in range(5):
    try:
        start_battle(StartBattleRequest(user_id=UID, route_id="route_1"))
    except HTTPException as e:
        refused += e.status_code == 400
ok(refused == 5, "a bare battle start is refused every time (no reroll)")
ok(not index._sessions.in_battle(UID), "refused starts create no battle")

b = start_wild(UID, "route_1")                       # the real flow still works
ok("battle_id" in b, "a scouted encounter still starts a battle")
print("ALL PASS")

# Regression (audit v3 #2): a scouted token is single-use. Once it has started a battle, replaying it is refused,
# even after that battle is over and the same Pokémon is on offer again.
UID2 = 304
index.choose_starter(index.StarterRequest(user_id=UID2, region="kanto", species="charmander"))
index.journey_travel(index.TravelRequest(user_id=UID2, to="route_1"))
sc = encounter_scout(ScoutRequest(user_id=UID2, route_id="route_1"))
cand = sc["candidates"][0]
first = start_battle(StartBattleRequest(user_id=UID2, target_species=cand["species_name"],
                                        target_level=cand["level"], encounter_token=cand["token"]))
ok("battle_id" in first, "a scouted token starts its battle once")
index.battle_abandon(index.AbandonRequest(user_id=UID2))
try:
    start_battle(StartBattleRequest(user_id=UID2, target_species=cand["species_name"],
                                    target_level=cand["level"], encounter_token=cand["token"]))
    replay = 200
except HTTPException as e:
    replay = e.status_code
ok(replay == 403, f"replaying a used token is refused (got {replay})")
print("ALL PASS (token replay)")
