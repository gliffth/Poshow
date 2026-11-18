import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

# The app is started as `uvicorn api.index:app` from the repository root, with nothing else on the import path.
env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": os.path.join(ROOT, "tests", "stubs")}
r = subprocess.run([sys.executable, "-c", "import api.index"], cwd=ROOT, env=env, capture_output=True, text=True)
ok(r.returncode == 0, "api.index imports with a clean path (as uvicorn loads it)" + ("" if r.returncode == 0 else "\n" + r.stderr[-400:]))
