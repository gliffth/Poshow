import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Held items: the pure rules, equip/unequip, and their effects in a real battle turn (BattleSystem._act).
import random
import held_items as HI
from battle_system import BattleSystem, Move

ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

# ── pure rules ───────────────────────────────────────────────────────────────
ok(HI.damage_multiplier("life-orb", "physical") == 1.3 and HI.damage_multiplier("life-orb", "special") == 1.3,
   "Life Orb: +30% on physical and special damage")
ok(HI.damage_multiplier("life-orb", "status") == 1.0, "Life Orb: no boost on status moves")
ok(HI.damage_multiplier(None, "physical") == 1.0 and HI.damage_multiplier("leftovers", "physical") == 1.0,
   "other items: no damage change")

ok(HI.recoil_after_turn("life-orb", 200, True) == 20, "Life Orb recoil: 1/10 of 200 max HP = 20")
ok(HI.recoil_after_turn("life-orb", 200, False) == 0, "Life Orb: no recoil when no damage landed")
ok(HI.recoil_after_turn("life-orb", 5, True) == 1, "Life Orb recoil never below 1")
ok(HI.recoil_after_turn("leftovers", 200, True) == 0, "no recoil for other items")

ok(HI.end_of_turn_heal("leftovers", 200, 100) == 12, "Leftovers: 1/16 of 200 = 12 HP per turn")
ok(HI.end_of_turn_heal("leftovers", 200, 195) == 5, "Leftovers: capped at max HP (heals only 5)")
ok(HI.end_of_turn_heal("leftovers", 200, 200) == 0, "Leftovers: nothing at full HP")
ok(HI.end_of_turn_heal("leftovers", 200, 0) == 0, "Leftovers: fainted Pokémon don't heal")
ok(HI.end_of_turn_heal("life-orb", 200, 100) == 0, "Leftovers rule ignores other items")

ok(HI.sash_saves("focus-sash", 200, 200, 250), "Focus Sash: saves from a knock-out at full HP")
ok(HI.sash_saves("focus-sash", 200, 200, 200), "Focus Sash: exactly lethal damage at full HP is saved")
ok(not HI.sash_saves("focus-sash", 199, 200, 250), "Focus Sash: no save when not at full HP")
ok(not HI.sash_saves("focus-sash", 200, 200, 150), "Focus Sash: no save when the hit isn't lethal")
ok(not HI.sash_saves("leftovers", 200, 200, 250), "Focus Sash rule ignores other items")

# ── equip / unequip (player bag and a Pokémon) ─────────────────────────────
class Bag:
    def __init__(self, inv):
        self.inventory = dict(inv)
    def add_item(self, item, n):
        self.inventory[item] = self.inventory.get(item, 0) + n
    def remove_item(self, item, n):
        if self.inventory.get(item, 0) < n:
            return False
        self.inventory[item] -= n
        if self.inventory[item] == 0:
            del self.inventory[item]
        return True

class Mon:
    def __init__(self, held=None):
        self.nickname = "Pika"
        self.held_item = held

bag = Bag({"leftovers": 1, "life-orb": 1})
mon = Mon()
r = HI.equip(bag, mon, "leftovers")
ok(r["ok"] and mon.held_item == "leftovers" and bag.inventory.get("leftovers") is None,
   "equip: moves the item from the bag onto the Pokémon")
r = HI.equip(bag, mon, "life-orb")
ok(r["ok"] and mon.held_item == "life-orb" and bag.inventory.get("leftovers") == 1,
   "equip over another item: the old one goes back to the bag")
ok(not HI.equip(bag, mon, "focus-sash")["ok"], "equip: refused when the item isn't in the bag")
ok(not HI.equip(bag, mon, "potion")["ok"], "equip: refused for an item that can't be held")
ok(HI.unequip(bag, mon)["ok"] and mon.held_item is None and bag.inventory.get("life-orb") == 1,
   "unequip: returns the item to the bag")
ok(not HI.unequip(bag, mon)["ok"], "unequip: nothing to return when nothing is held")

# ── battle: the rules act through BattleSystem ───────────────────────────────
class Stub:
    """A Pokémon as the battle engine reads it (attributes only, no network)."""
    def __init__(self, held=None, types=("normal",), hp=200, species="stub"):
        self.level = 50
        self.attack = self.defense = self.sp_attack = self.sp_defense = self.speed = 100
        self.max_hp = self.current_hp = hp
        self.types = list(types)
        self.ability = None
        self.status = None
        self.bt = None
        self.held_item = held
        self.species_name = species
        self.api_data = {}

def fight(att, dfn):
    random.seed(1234)
    return BattleSystem(att, dfn)

tackle = Move("tackle-like", power=40, accuracy=100, move_type="normal", category="physical")
bigmove = Move("crush-like", power=900, accuracy=100, move_type="normal", category="physical")

# Life Orb, worked out by hand: base = ((2*50/5+2)*40*100/100)/50 + 2 = 19.6 (no STAB: water user, normal move).
# Without the item: 19.6 -> 19. With it: 19.6 * 1.3 = 25.48 -> 25. Roll fixed at 1.0.
b = fight(Stub(held="life-orb", types=("water",)), Stub(types=("normal",), hp=500))
dmg_with = b.calc_damage(b.p, b.o, tackle, roll=1.0)
plain = fight(Stub(types=("water",)), Stub(types=("normal",), hp=500))
dmg_without = plain.calc_damage(plain.p, plain.o, tackle, roll=1.0)
ok(dmg_without == 19, f"no item: 19 damage (got {dmg_without})")
ok(dmg_with == 25, f"Life Orb: 25 damage (got {dmg_with})")
ok(dmg_with > dmg_without, "Life Orb damage is higher than without it")

# Life Orb recoil, through a real turn: the holder takes 1/10 of max HP after it lands a hit.
b = fight(Stub(held="life-orb", types=("water",), hp=200), Stub(types=("normal",), hp=500))
b._act("player", tackle, True)
ok(b.p.hp == 200 - 20, f"Life Orb: holder loses 1/10 max HP after a hit (hp {b.p.hp})")
ok(any("Life Orb" in line for line in b.battle_log), "Life Orb recoil is in the battle log")

# No recoil when the move did no damage (immune target).
b = fight(Stub(held="life-orb", types=("electric",), hp=200), Stub(types=("ground",), hp=500))
b._act("player", Move("spark-like", power=90, accuracy=100, move_type="electric", category="special"), True)
ok(b.p.hp == 200, "Life Orb: no recoil when the move hits nothing")

# Focus Sash (power 900 is lethal to 200 HP: base 398 before the roll): a knock-out hit from full HP leaves the defender on 1 HP and uses the item up.
b = fight(Stub(types=("water",), hp=200), Stub(held="focus-sash", types=("normal",), hp=200))
b._act("player", bigmove, True)
ok(b.o.hp == 1, f"Focus Sash: defender survives on 1 HP (hp {b.o.hp})")
ok(b.o.held is None, "Focus Sash: the item is used up")
ok(any("Focus Sash" in line for line in b.battle_log), "Focus Sash is in the battle log")
b.o.save()
ok(b.o.real.held_item is None, "Focus Sash: the used-up state is written back to the Pokémon")
b._act("player", bigmove, True)
ok(b.o.hp == 0, "Focus Sash: a second knock-out hit does finish the defender")

# Focus Sash does nothing when not at full HP.
b = fight(Stub(types=("water",), hp=200), Stub(held="focus-sash", types=("normal",), hp=200))
b.o.hp = 150
b._act("player", bigmove, True)
ok(b.o.hp == 0 and b.o.held == "focus-sash", "Focus Sash: not triggered below full HP")

# Leftovers at the end of a turn.
b = fight(Stub(held="leftovers", types=("water",), hp=200), Stub(types=("normal",), hp=200))
b.p.hp = 100
b._end_of_turn()
ok(b.p.hp == 112, f"Leftovers: +12 HP at the end of the turn (hp {b.p.hp})")
ok(any("Leftovers" in line for line in b.battle_log), "Leftovers is in the battle log")

# ── persistence: the held item survives save/load of the Pokémon ─────────────
from pokemon_model import PokemonInstance
p = PokemonInstance("pikachu", 20, 1)
p.held_item = "life-orb"
restored = PokemonInstance.from_dict(p.to_db_dict())
ok(restored.held_item == "life-orb", "held item survives a database round trip")
ok(PokemonInstance.from_dict({"species_name": "pikachu", "level": 20, "trainer_id": 1}).held_item is None,
   "older rows without the column load with no held item")

print("ALL PASS")
