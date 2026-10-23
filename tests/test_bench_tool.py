import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# The pure helpers of tools/db_bench.py (the tool itself needs a running API and database).
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
import db_bench as B
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
v = list(range(1, 101))
ok(B.percentile(v, .5) == 51 and B.percentile(v, .95) == 96 and B.percentile(v, .99) == 100, "percentiles of 1..100")
ok(B.percentile([], .5) is None and B.summarize([])["n"] == 0, "no data is reported as no data, not zero")
s = B.summarize([10, 20, 30, 400])
ok(s["p99"] == 400 and s["mean"] == 115.0 and s["p50"] == 30, "a single slow call shows in p99 and the mean hides it: " + str(s))
ok(B.verdict(79.9) == "meets target" and B.verdict(80.0) == "meets target" and B.verdict(80.1) == "ABOVE target" and B.verdict(None) == "no data", "the 80 ms verdict")
plan = {"query": "load_player", "plan": [{"Plan": {"Node Type": "Nested Loop", "Plans": [{"Node Type": "Index Scan"}, {"Node Type": "Seq Scan"}]}, "Execution Time": 0.31, "Planning Time": 0.1}]}
ps = B.plan_summary(plan)
ok(ps["execution_ms"] == 0.31 and ps["seq_scan"] is True and "Index Scan" in ps["nodes"], "plan summary: execution time and scan types, nested plans included")
ok(B.plan_summary({"plan": []}).get("error") == "unreadable plan", "an unreadable plan is flagged")
print("ALL BENCH-TOOL TESTS PASSED")
