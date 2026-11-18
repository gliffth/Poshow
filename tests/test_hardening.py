import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
sys.path.insert(0, os.path.join(root, "tests"))
import subprocess
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import requests as rq, index
from database import DatabaseError
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def raises(fn):
    try: fn(); return False
    except DatabaseError: return True
# leaderboard: outage != empty ranking
ok(index.leaderboard()["leaderboard"] == [], "an empty database gives an empty leaderboard")
real = rq.get
index._leaderboard_cache.invalidate()                      # the cache would otherwise (correctly) answer from memory
rq.get = lambda url, *a, **k: F.Resp(500, {"message": "down"}) if "/players" in url else real(url, *a, **k)
ok(raises(lambda: index.leaderboard()), "leaderboard database error -> 503, not an empty ranking")
def boom(*a, **k): raise rq.RequestException("net")
rq.get = boom
ok(raises(lambda: index.leaderboard()), "leaderboard network error -> 503")
rq.get = real
# signing secret: never the public development default in production
code = "import sys; sys.path.insert(0, %r); import accounts; accounts._secret(); print('OK')" % os.path.join(REPO_ROOT, "api", "_lib")
def run(env):
    e = {k: v for k, v in os.environ.items() if k not in ("AUTH_SECRET", "SUPABASE_KEY", "SUPABASE_URL", "RENDER", "VERCEL", "PRODUCTION")}
    e.update(env); return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=e)
r = run({"RENDER": "true"}); ok("OK" not in r.stdout and "AUTH_SECRET" in r.stderr, "production with neither AUTH_SECRET nor SUPABASE_KEY refuses to sign tokens")
ok("OK" in run({"RENDER": "true", "AUTH_SECRET": "x" * 32}).stdout, "production with AUTH_SECRET works")
ok("OK" in run({"RENDER": "true", "SUPABASE_KEY": "service-key"}).stdout, "production with only SUPABASE_KEY keeps working (derived secret)")
ok("OK" in run({}).stdout, "local development still works with the dev default")
# EV rules
from pokemon_model import PokemonInstance
m = PokemonInstance("pikachu", 30, 1); m.ev = {k: 0 for k in m.ev}
ok(m.add_ev("atk", -50) is False and m.ev["atk"] == 0, "negative EV amounts are rejected")
ok(m.add_ev("atk", 0) is False and m.add_ev("atk", True) is False and m.add_ev("atk", 2.5) is False, "zero / bool / float amounts are rejected")
ok(m.add_ev("atk", 300) is True and m.ev["atk"] == 252, "a stat is capped at 252 (amount trimmed)")
ok(m.add_ev("atk", 5) is False, "a full stat takes no more")
m.add_ev("speed", 252); ok(sum(m.ev.values()) == 504, "two stats at 252 = 504")
ok(m.add_ev("hp", 100) is True and sum(m.ev.values()) == 510 and m.ev["hp"] == 6, "the 510 total is a hard cap (trimmed to 6)")
ok(m.add_ev("def", 1) is False and sum(m.ev.values()) == 510, "nothing fits past 510")
ok(m.add_ev("nonsense", 4) is False, "unknown stat rejected")
print("ALL HARDENING TESTS PASSED")
