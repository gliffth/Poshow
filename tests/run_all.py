#!/usr/bin/env python3
"""Run the whole offline suite from a clean checkout:  python3 tests/run_all.py
Every test file runs in its own process (they stub different modules). test_db runs against both the
correct schema (`good`) and the old one (`bad`). Exit code is non-zero if anything fails."""
import glob, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
jobs = []
for f in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
    name = os.path.basename(f)
    if name == "test_db.py":
        jobs += [(name + " good", [sys.executable, f, "good"]), (name + " bad", [sys.executable, f, "bad"])]
    else:
        jobs.append((name, [sys.executable, f]))
if shutil.which("node"):
    for f in sorted(glob.glob(os.path.join(HERE, "ts", "*.test.mts"))):
        jobs.append(("ts/" + os.path.basename(f), ["node", "--experimental-strip-types", "--no-warnings", f]))

failed = []
for label, args in jobs:
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600)
    lines = (r.stdout + r.stderr).strip().splitlines()
    npass = sum(1 for l in lines if l.startswith("PASS"))
    nfail = sum(1 for l in lines if l.startswith("FAIL"))
    status = "ok  " if r.returncode == 0 else "FAIL"
    print(f"{status} {label:34s} pass={npass} fail={nfail}")
    if r.returncode != 0:
        failed.append(label)
        print("\n".join("      " + l for l in lines[-15:]))
print()
print("ALL GREEN" if not failed else f"FAILED: {', '.join(failed)}")
sys.exit(1 if failed else 0)
