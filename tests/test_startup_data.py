import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Required data stops the process; optional data degrades loudly. Run in subprocesses with a copied data dir.
import json, shutil, subprocess, tempfile, textwrap
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
LIB = os.path.join(REPO_ROOT, "api", "_lib")
def run(mutate):
    d = tempfile.mkdtemp()
    shutil.copytree(os.path.join(LIB, "data"), os.path.join(d, "data"))
    shutil.copy(os.path.join(LIB, "species_data.py"), d)
    mutate(os.path.join(d, "data"))
    code = textwrap.dedent("""
        import sys; sys.path.insert(0, %r)
        import species_data as s
        print("OK", len(s.SPECIES), len(s.EXTRA), len(s.ABILITY_INFO), s.LOAD_ERRORS)
    """ % d)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    shutil.rmtree(d, ignore_errors=True); return r
r = run(lambda d: None); ok(r.returncode == 0 and f"OK {len(json.load(open(os.path.join(LIB, 'data', 'species.json'))))}" in r.stdout and "[]" in r.stdout, "intact data loads with no errors")
r = run(lambda d: os.remove(os.path.join(d, "species.json"))); ok(r.returncode != 0 and "FATAL" in r.stderr, "missing species.json is a startup error")
r = run(lambda d: open(os.path.join(d, "species.json"), "w").write("{not json")); ok(r.returncode != 0 and "FATAL" in r.stderr, "corrupt species.json is a startup error")
r = run(lambda d: open(os.path.join(d, "species.json"), "w").write("{}")); ok(r.returncode != 0, "empty species.json is a startup error")
r = run(lambda d: os.remove(os.path.join(d, "species_extra.json"))); ok(r.returncode == 0 and "species_extra.json" in r.stdout, "missing species_extra.json degrades with a recorded error")
r = run(lambda d: open(os.path.join(d, "abilities_info.json"), "w").write("[1,2")); ok(r.returncode == 0 and "abilities_info.json" in r.stdout, "corrupt abilities_info.json degrades with a recorded error")

# readiness / health
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import requests as rq, index
rd = index.ready(); ok(rd["ok"] is True, "readiness ok when the database answers")
real = rq.get; rq.get = lambda *a, **k: F.Resp(500, {"message": "down"})
resp = index.ready(); body = getattr(resp, "content", resp)
ok(isinstance(body, dict) and body["ok"] is False and body["problems"], "readiness reports DEGRADED when the database errors")
def boom(*a, **k): raise rq.RequestException("net down")
rq.get = boom; resp = index.ready(); body = getattr(resp, "content", resp)
ok(body["ok"] is False and "unreachable" in body["problems"][0], "…and when it is unreachable")
rq.get = real
h = index.health(); ok(h["ok"] is True, "/health stays a cheap liveness check (no database call)")
d = index.diagnose() if hasattr(index, "diagnose") else None
print("ALL STARTUP-DATA TESTS PASSED")
