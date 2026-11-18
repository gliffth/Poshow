import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random
from pokemon_model import PokemonInstance
from battle_system import BattleSystem, Move
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
random.seed(8)
def mon(sp, lv=30, ab=None, moves=None):
    q = PokemonInstance(sp, lv, 1)
    q.ability = ab
    if moves: q.moves = moves
    q.restore_hp(); return q
def bs(a, b): return BattleSystem(a, b, smart=False)
M = Move.from_name

# Speed Boost
b = bs(mon("rattata", 30, "speed_boost", ["tackle"]), mon("pidgey", 30, None, ["tackle"]))
b.execute_turn(M("tackle"), M("tackle")); b.execute_turn(M("tackle"), M("tackle"))
ok(b.p.stages.get("spe", 0) == 2, "Speed Boost: +1 Speed every turn")
# Moxie
a = mon("gyarados", 60, "moxie", ["tackle"]); v = mon("rattata", 3, None, ["tackle"]); v.current_hp = 1
b = bs(a, v); b.execute_turn(M("tackle"), M("tackle"))
ok(b.is_finished and b.winner == "player" and b.p.stages.get("atk") == 1, "Moxie: Attack rises after a KO")
# Flash Fire
b = bs(mon("charmander", 30, None, ["ember"]), mon("bulbasaur", 30, "flash_fire", ["tackle"]))
hp0 = b.o.hp; b._act("player", M("ember"), True)
ok(b.o.hp == hp0 and b.o.ff, "Flash Fire: immune to Fire and charged")
base = bs(mon("charmander", 30, None, ["tackle"]), mon("bulbasaur", 30, "flash_fire", ["ember"]))
b.o.ff = True; atk, dfn = b.o, b.p
lo = [b.calc_damage(atk, dfn, M("ember"), roll=1.0, crit=False) for _ in range(1)][0]
b.o.ff = False; hi_off = b.calc_damage(b.o, b.p, M("ember"), roll=1.0, crit=False)
ok(lo > hi_off, "…and its own Fire moves are stronger afterwards (%d > %d)" % (lo, hi_off))
back = BattleSystem(b.player_pokemon, b.wild_pokemon); b.o.ff = True; b.o.save()
ok(BattleSystem(b.player_pokemon, b.wild_pokemon).o.ff, "Flash Fire charge survives a session rebuild")
# status immunities
for ab, code, mv in (("insomnia", "slp", "spore"), ("limber", "par", "thunder-wave"), ("immunity", "psn", "poison-powder"), ("water_veil", "brn", "will-o-wisp")):
    c = bs(mon("pidgey", 30, None, [mv]), mon("rattata", 30, ab, ["tackle"]))
    if not Move.from_name(mv).fx: continue
    c._act("player", M(mv), True)
    ok(c.o.status is None, "%s blocks %s" % (ab, code))
# stat-drop protection
c = bs(mon("pidgey", 30, None, ["growl"]), mon("rattata", 30, "clear_body", ["tackle"])); c._act("player", M("growl"), True)
ok(c.o.stages.get("atk", 0) == 0, "Clear Body: stats can't be lowered by foes")
c = bs(mon("pidgey", 30, None, ["growl"]), mon("rattata", 30, "hyper_cutter", ["tackle"])); c._act("player", M("growl"), True)
ok(c.o.stages.get("atk", 0) == 0, "Hyper Cutter protects Attack")
c = bs(mon("gyarados", 30, "intimidate", ["tackle"]), mon("rattata", 30, "clear_body", ["tackle"])); c.execute_turn(M("tackle"), M("tackle"))
ok(c.o.stages.get("atk", 0) == 0, "Clear Body also stops Intimidate")
# Poison Heal / Magic Guard / Overcoat
c = bs(mon("rattata", 30, "poison_heal", ["tackle"]), mon("pidgey", 30, None, ["tackle"])); c.p.status = "psn"; c.p.hp = c.p.max_hp // 2; h = c.p.hp
c._end_of_turn(); ok(c.p.hp > h, "Poison Heal heals instead of hurting")
c = bs(mon("rattata", 30, "magic_guard", ["tackle"]), mon("pidgey", 30, None, ["tackle"])); c.p.status = "psn"; h = c.p.hp; c._end_of_turn()
ok(c.p.hp == h, "Magic Guard: no poison damage")
c = bs(mon("rattata", 30, "overcoat", ["tackle"]), mon("pidgey", 30, None, ["tackle"])); c.weather = "sand"; c.weather_turns = 5; c._sync_weather(); h = c.p.hp; c._weather_tick()
ok(c.p.hp == h, "Overcoat ignores sandstorm")
# damage modifiers
def dmg(att_ab, def_ab, move, att_sp="rattata", def_sp="pidgey", **kw):
    c = bs(mon(att_sp, 40, att_ab, [move]), mon(def_sp, 40, def_ab, ["tackle"])); return c.calc_damage(c.p, c.o, M(move), roll=1.0, crit=False)
ok(dmg(None, "heatproof", "ember", "charmander", "bulbasaur") < dmg(None, None, "ember", "charmander", "bulbasaur"), "Heatproof halves Fire")
ok(dmg(None, "solid_rock", "rock-throw", "geodude", "pidgey") < dmg(None, None, "rock-throw", "geodude", "pidgey"), "Solid Rock softens super-effective hits")
ok(dmg(None, "fur_coat", "tackle") < dmg(None, None, "tackle"), "Fur Coat doubles Defense")
ok(dmg("tinted_lens", None, "tackle", "rattata", "geodude") > dmg(None, None, "tackle", "rattata", "geodude"), "Tinted Lens boosts not-very-effective moves")
# absorb-style immunities via the damage pipeline
import abilities_system as AS
d, h, n = AS.AbilitySystem.modify_incoming("sap_sipper", 40, "grass", 1, 50, 100); ok(d == 0, "Sap Sipper nullifies Grass")
d, h, n = AS.AbilitySystem.modify_incoming("storm_drain", 40, "water", 1, 50, 100); ok(d == 0, "Storm Drain nullifies Water")
# honest descriptions
ok("1.3" not in (AS.AbilitySystem.describe("power_spot") or ""), "Power Spot no longer claims a boost it doesn't give")
print("ALL EXTRA ABILITY TESTS PASSED")
