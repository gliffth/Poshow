import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Regression (audit v7 #7): production must not sign login tokens with a guessable secret.
import accounts
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
saved = {k: os.environ.get(k) for k in ("AUTH_SECRET", "RENDER", "VERCEL", "PRODUCTION", "SUPABASE_KEY")}
def env(**kw):
    for k in saved: os.environ.pop(k, None)
    for k, v in kw.items(): os.environ[k] = v
try:
    env(AUTH_SECRET="short", RENDER="1")
    try:
        accounts._secret(); refused = False
    except RuntimeError:
        refused = True
    ok(refused, "production refuses a short AUTH_SECRET")
    env(AUTH_SECRET="x" * 32, RENDER="1")
    ok(accounts._secret() == ("x" * 32).encode(), "a long AUTH_SECRET is used as given")
    env(AUTH_SECRET="short")
    ok(accounts._secret() == b"short", "outside production a short secret still works (local dev)")
    env(RENDER="1")
    try:
        accounts._secret(); refused = False
    except RuntimeError:
        refused = True
    ok(refused, "production with no secret at all refuses to start")
finally:
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None: os.environ[k] = v
print("ALL PASS")
