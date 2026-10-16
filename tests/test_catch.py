import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random
from pokeball_system import CatchSystem as C
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
P = C.catch_probability
c = C()
# reference values of the Gen 5+ formula
ok(abs(P(1000, 1000, 120, 1.0, 1.0, 30) - 0.2488) < 0.002, "full-HP Pidgeotto (rate 120), Poké Ball ≈ 24.9%%")
ok(P(1, 1000, 120, 1.0, 1.0, 30) > P(1000, 1000, 120, 1.0, 1.0, 30) * 2, "low HP at least doubles the odds")
ok(P(1000, 1000, 3, 1.0, 1.0, 70) < 0.03, "full-HP legendary (rate 3) is very hard in a Poké Ball")
ok(P(1, 1000, 255, 2.0, 1.0, 30) == 1.0, "a >= 255 is a sure catch")
ok(P(500, 1000, 45, 2.0, 1.0, 30) > P(500, 1000, 45, 1.5, 1.0, 30) > P(500, 1000, 45, 1.0, 1.0, 30), "Ultra > Great > Poké")
ok(C.status_multiplier("sleep") == 2.5 and C.status_multiplier("burn") == 1.5 and C.status_multiplier(None) == 1.0, "status multipliers")
def mult(ball, **k):
    d = dict(turn=1, pokemon_level=20, player_level=30, pokemon_type="", pokemon_weight=0, already_caught=False,
             is_water_location=False, is_cave_location=False, is_night=False, is_first_turn=False)
    d.update(k); return c._get_ball_multiplier(ball, **d)
ok(mult("quickball", is_first_turn=True) == 5.0 and mult("quickball", turn=2) == 1.0, "Quick Ball: first turn only")
ok(mult("timerball", turn=1) == 1.1 and mult("timerball", turn=40) == 4.0, "Timer Ball: (turn+10)/10, max 4")
ok(mult("nestball", pokemon_level=10) == 3.1 and mult("nestball", pokemon_level=40) == 1.0, "Nest Ball: (41-level)/10, 1x from Lv30")
ok(mult("repeatball", already_caught=True) == 3.5 and mult("repeatball") == 1.0, "Repeat Ball needs a registered species")
ok(mult("netball", types=["bug"]) == 3.5 and mult("netball", types=["fire"]) == 1.0, "Net Ball: Bug/Water only")
ok(mult("diveball", types=["water"]) == 1.0 and mult("diveball", is_water_location=True) == 3.5, "Dive Ball depends on location, not type")
ok(mult("duskball") == 1.0 and mult("duskball", is_cave_location=True) == 3.5, "Dusk Ball: caves/night only")
ok(mult("fastball", base_speed=120) == 4.0 and mult("fastball", base_speed=60) == 1.0, "Fast Ball: base Speed >= 100 only (no assumption)")
ok(mult("levelball", player_level=90, pokemon_level=20) == 8.0 and mult("levelball", player_level=50, pokemon_level=20) == 4.0
   and mult("levelball", player_level=25, pokemon_level=20) == 2.0 and mult("levelball", player_level=20, pokemon_level=20) == 1.0, "Level Ball tiers")
ok(mult("moonball", species_name="clefairy") == 4.0 and mult("moonball", species_name="pidgey") == 1.0, "Moon Ball: moon-stone families only")
ok(mult("beastball", species_name="pidgey") == 0.1 and mult("loveball") == 1.0, "Beast Ball penalises non-UBs; Love Ball needs gender data (no bonus)")
r_light = c.calculate_catch_chance(1.0, 30, 45, "heavyball", pokemon_weight=10)["chance"]
r_heavy = c.calculate_catch_chance(1.0, 30, 45, "heavyball", pokemon_weight=400)["chance"]
ok(r_heavy > r_light, "Heavy Ball changes the catch rate by weight")
ok(c.calculate_catch_chance(1.0, 100, 3, "masterball")["will_catch"], "Master Ball always catches")
n = sum(c.calculate_catch_chance(1.0, 30, 120, "pokeball")["will_catch"] for _ in range(4000))
ok(0.20 < n / 4000 < 0.30, "simulated catch rate matches the formula (%.1f%%)" % (n / 40))
print("ALL CATCH TESTS PASSED")
