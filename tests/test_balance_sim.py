import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# The balance runner: its interval maths is right, and a fixed seed reproduces the same numbers.
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
sys.path.insert(0, os.path.join(root, "tools"))
import balance_sim as B
lo, hi = B.wilson(50, 100)
ok(0.39 < lo < 0.41 and 0.59 < hi < 0.61, f"95% interval for 50/100 is about 40–60% (got {lo:.3f}–{hi:.3f})")
lo, hi = B.wilson(100, 100)
ok(hi > 0.999 and lo > 0.95, f"a perfect record gives an interval ending at 100% (got {hi:.6f})")
ok(B.wilson(0, 0) == (0.0, 0.0), "no battles gives an empty interval, not an error")
a = B.run([("x", "charmander", 12, "rattata", 10)], 6, seed=42, offsets=[0])
b = B.run([("x", "charmander", 12, "rattata", 10)], 6, seed=42, offsets=[0])
ok(a[0]["rows"][0]["win_rate"] == b[0]["rows"][0]["win_rate"], "the same seed gives the same result")
print("ALL PASS")
