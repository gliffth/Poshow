import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Known-value checks for battle damage. Every expected number below is worked out by hand from the formula:
#   base = floor(((2*L/5 + 2) * power * attack / defense) / 50 + 2)
#   damage = floor(base * STAB * type * crit * burn * roll)
# The roll is fixed (1.0 or 0.85) so the results are exact. The tests call the same calc_damage the turn engine uses.
import battle_system as bs_mod
from battle_system import BattleSystem, Move

ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))


class Mon:
    """Minimal stand-in for a Pokémon: the attributes the battle engine reads."""
    def __init__(self, level=50, attack=100, defense=100, sp_attack=100, sp_defense=100, speed=100,
                 types=("normal",), ability=None, status=None):
        self.level = level
        self.attack, self.defense = attack, defense
        self.sp_attack, self.sp_defense, self.speed = sp_attack, sp_defense, speed
        self.max_hp = self.current_hp = 200
        self.types = list(types)
        self.ability = ability
        self.status = status
        self.bt = None
        self.species_name = "stub"
        self.api_data = {}


def battle(att, dfn):
    return BattleSystem(att, dfn)


def dmg(att_mon, def_mon, move, roll=1.0, crit=False, att_stages=None, def_stages=None):
    b = battle(att_mon, def_mon)
    att, dfn = b.p, b.o
    if att_stages:
        att.stages.update(att_stages)
    if def_stages:
        dfn.stages.update(def_stages)
    return b.calc_damage(att, dfn, move, roll=roll, crit=crit)


fire_pow80 = Move("ember-like", power=80, move_type="fire", category="special")
phys_fire = Move("flame-like", power=80, move_type="fire", category="physical")
normal_pow80 = Move("tackle-like", power=80, move_type="normal", category="physical")

# 1. STAB + super effective, roll 1.0.
#    base = floor(((22)*80*100/100)/50 + 2) = floor(37.2) = 37 ; x2 (super) x1.5 (STAB) = 111.
#    (The engine uses the unfloored base, so 37.2*3.0 = 111.6 -> 111.)
att = Mon(types=("fire",), sp_attack=100)
dfn = Mon(types=("grass",), sp_defense=100)
ok(dmg(att, dfn, fire_pow80) == 111, "STAB + super effective, level 50, roll 1.0 -> 111")

# 2. Same attack without STAB, neutral: base 37.2 -> 37.
ok(dmg(Mon(types=("water",)), Mon(types=("normal",)), normal_pow80) == 37, "no STAB, neutral -> 37")

# 3. Neutral with the low roll 0.85: 37.2*0.85 = 31.62 -> 31.
ok(dmg(Mon(types=("water",)), Mon(types=("normal",)), normal_pow80, roll=0.85) == 31,
   "neutral with minimum roll 0.85 -> 31")

# 4. Immunity: electric into ground does nothing.
ok(dmg(Mon(types=("electric",)), Mon(types=("ground",)),
       Move("spark-like", power=90, move_type="electric", category="special")) == 0,
   "electric into ground is immune -> 0")

# 5. Burn halves physical damage: 37.2*0.5 = 18.6 -> 18.
# (Water-type attacker so the Normal move gets no STAB; a Normal attacker would correctly give 27.)
burned = Mon(types=("water",), status="brn")
ok(dmg(burned, Mon(types=("normal",)), normal_pow80) == 18, "burned attacker, physical -> 18")

# 6. Burn does not touch special damage: same numbers as case 2 but special -> 37.
ok(dmg(burned, Mon(types=("normal",)), Move("beam-like", power=80, move_type="normal", category="special")) == 37,
   "burned attacker, special -> unaffected (37)")

# 7. Crit x1.5 and it ignores the attacker's attack drop: crit uses the unstaged 100.
#    base 37.2 * 1.5 = 55.8 -> 55.
ok(dmg(Mon(types=("water",)), Mon(types=("normal",)), normal_pow80, crit=True,
       att_stages={"atk": -2}) == 55, "crit ignores attack drop (55)")

# 8. Without the crit, the -2 attack drop applies: attack 50 -> base floor(19.6)=19.
ok(dmg(Mon(types=("water",)), Mon(types=("normal",)), normal_pow80, att_stages={"atk": -2}) == 19,
   "-2 attack drop without crit -> 19")

# 9. +2 attack stage doubles attack: attack 200 -> base 72.4 -> 72.
ok(dmg(Mon(types=("water",)), Mon(types=("normal",)), normal_pow80, att_stages={"atk": 2}) == 72,
   "+2 attack stage -> 72")

# 10. Level scales damage: level 5 -> base floor(((2*5/5+2)*80*100/100)/50+2)=floor(4*80/50+2)=floor(8.4)=8.
ok(dmg(Mon(level=5, types=("water",)), Mon(types=("normal",)), normal_pow80) == 8, "level 5 -> 8")

# 11. Huge Power doubles attack: attack 200 -> base floor(72.4) = 72.
ok(dmg(Mon(types=("water",), ability="huge-power"), Mon(types=("normal",)), normal_pow80) == 72,
   "Huge Power doubles attack -> 72")

# 12. Thick Fat halves fire damage taken. Water attacker (no STAB) uses a fire move into a grass defender:
#     base 37.2 * 2 (super effective) = 74.4 -> 74 ; with Thick Fat the defender takes half: 37.2 -> 37.
ok(dmg(Mon(types=("water",)), Mon(types=("grass",)), phys_fire) == 74, "fire into grass, no ability -> 74")
ok(dmg(Mon(types=("water",)), Mon(types=("grass",), ability="thick-fat"), phys_fire) == 37,
   "Thick Fat halves fire damage -> 37")

# 13. Random roll stays inside [0.85, 1.0] of the base damage when no roll is passed.
import random
random.seed(7)
vals = {dmg(Mon(types=("water",)), Mon(types=("normal",)), normal_pow80, roll=None) for _ in range(200)}
ok(min(vals) >= 31 and max(vals) <= 37 and len(vals) > 1, f"random roll stays in range {sorted(vals)}")

print("ALL PASS")
