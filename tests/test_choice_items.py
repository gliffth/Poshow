import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Choice items: stat boosts, the move lock, its persistence, and its end on switch-out (through the real endpoints).
import random, index
from index import *
from fastapi import HTTPException
from battle_system import BattleSystem, Move
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

class Stub:
    def __init__(self, held=None, types=("normal",), hp=200, moves=("tackle", "ember"), bt=None):
        self.level = 50
        self.attack = self.defense = self.sp_attack = self.sp_defense = self.speed = 100
        self.max_hp = self.current_hp = hp
        self.types = list(types); self.ability = None; self.status = None
        self.bt = bt; self.held_item = held; self.species_name = "stub"; self.api_data = {}
        self.moves = list(moves)

def fight(att, dfn):
    random.seed(99)
    return BattleSystem(att, dfn)

tackle = Move("tackle-like", power=80, accuracy=100, move_type="normal", category="physical")
special = Move("beam-like", power=80, accuracy=100, move_type="normal", category="special")

# Stat boosts, worked by hand. Attacker is Water-type using Normal moves, so no STAB.
# Base with attack 100 is 37.2; with attack x1.5 it is 54.8 -> 54.
b = fight(Stub(held="choice-band", types=("water",)), Stub(types=("normal",), hp=500))
ok(b.p.stat("atk") == 150, "Choice Band: attack x1.5 (100 -> 150)")
ok(b.calc_damage(b.p, b.o, tackle, roll=1.0) == 54, "Choice Band: 80-power hit deals 54 (base 54.8)")
b = fight(Stub(held="choice-specs", types=("water",)), Stub(types=("normal",), hp=500))
ok(b.p.stat("spa") == 150 and b.p.stat("atk") == 100, "Choice Specs: Sp. Atk x1.5, Attack unchanged")
ok(b.calc_damage(b.p, b.o, special, roll=1.0) == 54, "Choice Specs: special hit deals 54")
b = fight(Stub(held="choice-scarf", types=("water",)), Stub(types=("normal",), hp=500))
ok(b.p.stat("spe") == 150, "Choice Scarf: Speed x1.5 (100 -> 150)")
ok(fight(Stub(), Stub()).p.stat("spe") == 100, "no item: stats are unchanged")

# The lock: the first move used sticks; other moves are not offered.
b = fight(Stub(held="choice-band"), Stub(types=("normal",), hp=5000))
b._act("player", Move.from_name("tackle"), True)          # a move from the moveset, as in a real turn
ok(b.p.choice == "tackle", "Choice lock: the first move used is recorded")
offered = [m.name for m in b.get_player_moves()]
ok(offered == ["tackle"], f"Choice lock: only the locked move is offered (got {offered})")

# The lock survives a save and reload of the battle state.
b.p.save()
ok(b.p.real.bt.get("cl") == "tackle", "Choice lock is written with the battle state")
reloaded = BattleSystem(Stub(held="choice-band", bt=b.p.real.bt), Stub(hp=5000))
ok(reloaded.p.choice == "tackle", "Choice lock is restored when the battle state is reloaded")

# Without the item there is no lock.
b = fight(Stub(), Stub(types=("normal",), hp=5000))
b._act("player", Move.from_name("tackle"), True)
ok(b.p.choice is None and len(b.get_player_moves()) == 2, "no Choice item: no lock, every move is offered")

# The lock holds when the locked move has no PP left: it is the only move offered and turns into Struggle.
b = fight(Stub(held="choice-band", bt={"pp": {"tackle": 0}}), Stub(hp=5000))
b.p.choice = "tackle"
offered = [m.name for m in b.get_player_moves()]
ok(offered == ["tackle"], f"a locked move with no PP stays the only choice (offered {offered})")
res = b.execute_turn(b.get_player_moves()[0], b.get_opponent_move())
ok(any("STRUGGLE" in str(l).upper() for l in res["log"]), "and using it means Struggle")

# ── through the real endpoints: the lock blocks other moves, and switching out ends it ──────────
UID = 91
index.choose_starter(index.StarterRequest(user_id=UID, region="kanto", species="charmander"))
p = get_or_create_player(UID)
p.add_pokemon_to_team(PokemonInstance("squirtle", 5, UID))
for m in p.active_team:                    # strong enough that the route's wild Pokémon can't end the battle early
    m.level = 40; m.recalculate_stats(); m.current_hp = m.max_hp
p.coins = 10000; persist_player(p)
shop_buy(BuyRequest(user_id=UID, item_id="choice-band", quantity=1))
lead = get_or_create_player(UID).active_team[0]
held_equip(HeldRequest(user_id=UID, pokemon_id=lead.id, item="choice-band"))
second = next(m for m in get_or_create_player(UID).active_team if m.id != lead.id)
index.journey_travel(index.TravelRequest(user_id=UID, to="route_1"))
random.seed(5)
start = start_wild(UID, "route_1")
bid = start["battle_id"]
first, other = [m["id"] for m in start["player_pokemon"]["moves"]][:2]

battle_move(MoveRequest(battle_id=bid, move_name=first))
rec = index._sessions.load(bid)
ok(rec is not None and not rec.get("completed_at"), "the battle is still running after the first move")
ok((rec["player_pokemon"].get("bt") or {}).get("cl") == first, "the first move is recorded as the Choice lock")
try:
    battle_move(MoveRequest(battle_id=bid, move_name=other))
    refused, text = False, ""
except HTTPException as e:
    refused, text = e.status_code == 400, e.detail
ok(refused and "locked" in text.lower(), "a different move is refused while locked (endpoint)")

battle_switch(SwitchRequest(battle_id=bid, pokemon_id=second.id))
battle_switch(SwitchRequest(battle_id=bid, pokemon_id=lead.id))
rec = index._sessions.load(bid)
ok("cl" not in (rec["player_pokemon"].get("bt") or {}), "switching out and back in clears the Choice lock")
battle, _, _ = index._rebuild_battle(rec)
ok(len(battle.get_player_moves()) == len(rec["player_pokemon"]["moves"]) >= 2,
   "after switching back, every move is offered again")

print("ALL PASS")
