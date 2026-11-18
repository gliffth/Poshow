import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Held items through the API: buy, equip, the battle lock, and that the item survives a reload.
import random, index
from index import *
from fastapi import HTTPException
random.seed(11)
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

UID = 77
index.choose_starter(index.StarterRequest(user_id=UID, region="kanto", species="charmander"))
p = get_or_create_player(UID); p.coins = 10000; persist_player(p)

r = shop_buy(BuyRequest(user_id=UID, item_id="leftovers", quantity=1))
ok(r["inventory"].get("leftovers") == 1, "shop sells Leftovers into the bag")

lead = get_or_create_player(UID).active_team[0]
r = held_equip(HeldRequest(user_id=UID, pokemon_id=lead.id, item="leftovers"))
ok(r["pokemon"]["held_item"] == "leftovers", "equip: the Pokémon reports it is holding Leftovers")
ok(r["inventory"].get("leftovers") is None, "equip: the item left the bag")

# the item survives a reload of the player from storage
fresh = get_or_create_player(UID)
mon = next(m for m in fresh.active_team if m.id == lead.id)
ok(mon.held_item == "leftovers", "held item is still on the Pokémon after a reload")
ok(serialize_pokemon(mon)["held_item"] == "leftovers", "the API response includes the held item")

# the battle lock: no changing held items during a fight
index.journey_travel(index.TravelRequest(user_id=UID, to="route_1"))
start = start_wild(UID, "route_1")
ok("battle_id" in start, "a battle started")
shop_buy(BuyRequest(user_id=UID, item_id="life-orb", quantity=1))
blocked = False
try:
    held_equip(HeldRequest(user_id=UID, pokemon_id=lead.id, item="life-orb"))
except HTTPException as e:
    blocked = e.status_code == 400
ok(blocked, "equip is refused during a battle")
blocked = False
try:
    held_unequip(HeldRequest(user_id=UID, pokemon_id=lead.id))
except HTTPException as e:
    blocked = e.status_code == 400
ok(blocked, "unequip is refused during a battle")

# after the battle is closed, the change goes through and the item comes back off
index.battle_abandon(index.AbandonRequest(user_id=UID))
r = held_unequip(HeldRequest(user_id=UID, pokemon_id=lead.id))
ok(r["pokemon"]["held_item"] is None and r["inventory"].get("leftovers") == 1,
   "unequip after the battle returns Leftovers to the bag")

# equip a Pokémon that isn't yours -> 404
try:
    held_equip(HeldRequest(user_id=UID, pokemon_id="not-a-real-id", item="life-orb"))
    ok(False, "unknown Pokémon must be rejected")
except HTTPException as e:
    ok(e.status_code == 404, "equip for a Pokémon you don't own -> 404")

# a Focus Sash used up in an unfinished battle stays used up when the battle is settled onto the team
p = get_or_create_player(UID)
sash_mon = p.active_team[0]
sash_mon.held_item = "focus-sash"
index._sync_session_into_player(p, {"player_pokemon": {"id": sash_mon.id, "current_hp": sash_mon.current_hp,
                                                        "held_item": None}})
ok(sash_mon.held_item is None, "a used-up Focus Sash is not restored when the battle is settled")
sash_mon.held_item = "leftovers"
index._sync_session_into_player(p, {"player_pokemon": {"id": sash_mon.id, "current_hp": sash_mon.current_hp}})
ok(sash_mon.held_item == "leftovers", "a session without the field leaves the item as it is")

print("ALL PASS")
