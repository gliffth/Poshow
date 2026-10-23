#!/usr/bin/env python3
"""
Measure database latency against a running POSHOW API (your Render service, ideally with its real Supabase project).

It plays a short game session with throwaway accounts, then reads the server's own measurements:
  * total API latency per endpoint (measured here, includes your network to the API)
  * database call latency per operation, p50 / p95 / p99 (measured by the API: GET /api/metrics)
  * database-side numbers and execution plans (GET /api/admin/db-health, /api/admin/db-explain)

Usage:
  python3 tools/db_bench.py --api https://YOUR-API.onrender.com --admin NAME:PASSWORD --users 4 --rounds 3 --yes

Use a staging database if you can: each run creates accounts named bench_<random>. `--admin` must be an account whose
id is in ADMIN_USER_IDS.
"""

import argparse
import json
import random
import statistics
import string
import sys
import threading
import time
from typing import Dict, List, Optional

import requests

TARGET_MS = 80.0


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * len(v)))], 1)


def summarize(values: List[float]) -> Dict:
    return {"n": len(values), "p50": percentile(values, .5), "p95": percentile(values, .95), "p99": percentile(values, .99),
            "mean": round(statistics.fmean(values), 1) if values else None}


def plan_summary(result: Dict) -> Dict:
    """Execution time and the scan types in an EXPLAIN (FORMAT JSON) result from /api/admin/db-explain."""
    try:
        root = result["plan"][0]
        nodes, todo = [], [root["Plan"]]
        while todo:
            n = todo.pop()
            nodes.append(n.get("Node Type", "?"))
            todo.extend(n.get("Plans", []))
        return {"execution_ms": root.get("Execution Time"), "planning_ms": root.get("Planning Time"), "nodes": nodes,
                "seq_scan": any("Seq Scan" in n for n in nodes)}
    except (KeyError, IndexError, TypeError):
        return {"error": "unreadable plan"}


def verdict(p95: Optional[float], target: float = TARGET_MS) -> str:
    if p95 is None:
        return "no data"
    return "meets target" if p95 <= target else "ABOVE target"


class Client:
    def __init__(self, base: str):
        self.base, self.token, self.user_id = base.rstrip("/"), None, None
        self.timings: Dict[str, List[float]] = {}
        self.s = requests.Session()

    def call(self, method: str, path: str, **kw):
        t0 = time.perf_counter()
        r = self.s.request(method, self.base + path, timeout=90, headers={"Authorization": f"Bearer {self.token}"} if self.token else {}, **kw)
        label = f"{method} " + "/".join("{id}" if seg.isdigit() or len(seg) > 20 else seg for seg in path.split("?")[0].split("/"))
        self.timings.setdefault(label, []).append((time.perf_counter() - t0) * 1000)
        return r

    def login(self, username: str, password: str, create: bool = False):
        r = self.call("POST", "/api/auth/register" if create else "/api/auth/login", json={"username": username, "password": password})
        r.raise_for_status()
        d = r.json()
        self.token, self.user_id = d["token"], d["user_id"]


def session(base: str, rounds: int, out: List[Client]):
    c = Client(base)
    name = "bench_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    c.login(name, "bench-" + name, create=True)
    c.call("POST", "/api/player/starter", json={"user_id": c.user_id, "region": "kanto", "species": "charmander"}).raise_for_status()
    for _ in range(rounds):
        c.call("GET", f"/api/player/{c.user_id}/roster")
        c.call("GET", f"/api/journey/state?user_id={c.user_id}")
        c.call("POST", "/api/journey/travel", json={"user_id": c.user_id, "to": "route_1"})
        b = c.call("POST", "/api/battle/start", json={"user_id": c.user_id, "username": name})
        if b.status_code == 200:
            bid, moves = b.json()["battle_id"], b.json()["player_pokemon"]["moves"]
            mv = next((m["id"] for m in moves if (m.get("power") or 0) > 0), moves[0]["id"])
            for _ in range(12):
                r = c.call("POST", "/api/battle/move", json={"battle_id": bid, "move_name": mv})
                if r.status_code != 200 or r.json().get("is_finished"):
                    break
            else:
                c.call("POST", "/api/battle/abandon", json={"user_id": c.user_id})
        c.call("POST", "/api/journey/travel", json={"user_id": c.user_id, "to": "pallet_town"})
        c.call("GET", "/api/leaderboard")
    out.append(c)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", required=True)
    ap.add_argument("--admin", help="NAME:PASSWORD of an admin account (needed for server-side numbers)")
    ap.add_argument("--users", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--yes", action="store_true", help="confirm that creating bench_* accounts on this API is fine")
    a = ap.parse_args()
    if not a.yes:
        print("This creates throwaway accounts on", a.api, "- re-run with --yes to continue.")
        return 2
    # wake a sleeping instance first, so a cold start isn't counted as latency
    t0 = time.perf_counter(); requests.get(a.api.rstrip("/") + "/api/health", timeout=120)
    print(f"warm-up: /api/health answered in {(time.perf_counter() - t0) * 1000:.0f} ms")

    admin = None
    if a.admin:
        admin = Client(a.api); u, p = a.admin.split(":", 1); admin.login(u, p)
        admin.call("GET", "/api/metrics")                     # baseline; the numbers below cover this run plus what came before

    clients: List[Client] = []
    threads = [threading.Thread(target=session, args=(a.api, a.rounds, clients)) for _ in range(a.users)]
    t0 = time.time(); [t.start() for t in threads]; [t.join() for t in threads]
    print(f"\n{a.users} users x {a.rounds} rounds in {time.time() - t0:.1f}s\n")

    merged: Dict[str, List[float]] = {}
    for c in clients:
        for k, v in c.timings.items():
            merged.setdefault(k, []).extend(v)
    print("TOTAL API LATENCY (client side, ms)")
    for k, v in sorted(merged.items(), key=lambda kv: -(percentile(kv[1], .95) or 0)):
        s = summarize(v); print(f"  {k:48s} n={s['n']:3d} p50={s['p50']:7} p95={s['p95']:7} p99={s['p99']:7}")

    if admin:
        m = admin.call("GET", "/api/metrics").json()
        d = m["db_call_ms"]
        print(f"\nDATABASE CALLS (server side, ms; includes the network round trip to the database)")
        print(f"  overall  n={d['n']} p50={d['p50']} p95={d['p95']} p99={d['p99']}  ->  {verdict(d['p95'])} ({TARGET_MS:.0f} ms)")
        for op, s in m["db_operations"].items():
            print(f"  {op:36s} calls={s['calls']:4d} p50={s['p50']:7} p95={s['p95']:7} p99={s['p99']:7} "
                  f"rows r/w={s['rows_read']}/{s['rows_written']} errors={s['errors'] or '-'}")
        print(f"  pool: {m['pool']}   throughput: {m['throughput']}   lock wait: {m['lock_wait_ms']}")
        h = admin.call("GET", "/api/admin/db-health")
        if h.status_code == 200:
            print("\nDATABASE SIDE (Postgres)")
            print(json.dumps(h.json()["database"], indent=2)); print(json.dumps(h.json()["connections"], indent=2))
            for t in h.json()["tables"]:
                print(f"  table {t['table']:18s} rows={t['rows']:7} seq_scans={t['seq_scans']:7} idx_scans={t['index_scans']:7} size_kb={t['size_kb']}")
            print("  slowest statements:", json.dumps(h.json()["slowest_statements"], indent=2)[:1500])
        else:
            print("\n(db-health unavailable:", h.status_code, h.text[:120], ")")
        uid = clients[0].user_id if clients else 0
        print("\nEXECUTION PLANS (Postgres time only, no network)")
        for name in ("load_player", "load_pokemon", "player_sessions", "trades_for_user", "duels_for_user", "leaderboard", "account_by_user"):
            r = admin.call("GET", f"/api/admin/db-explain?name={name}&user_id={uid}")
            if r.status_code == 200:
                ps = plan_summary(r.json()); print(f"  {name:18s} execution={ps.get('execution_ms')} ms  nodes={ps.get('nodes')}  seq_scan={ps.get('seq_scan')}")
            else:
                print(f"  {name:18s} unavailable ({r.status_code})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
