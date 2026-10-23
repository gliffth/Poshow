import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Performance guards: round-trip budgets, changed-only saves, per-key locks, pooled connections, timing.
sys.path.insert(0, os.path.join(root, "tests"))
import asyncio, json, subprocess, textwrap, threading, time
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import accounts, requests as rq, index, database
import http_client as dbhttp
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

# ---- 1. database round trips per action (budgets; the numbers were 2/5/6/5/5/5/3 before) -----------------------------
calls = []
for n in ("get", "post", "patch", "delete"):
    real = getattr(rq, n)
    def mk(real, n):
        def f(url, *a, **k): calls.append((n.upper(), url.split("/rest/v1/")[-1].split("?")[0], k.get("json"))); return real(url, *a, **k)
        return f
    setattr(rq, n, mk(real, n))
def used(fn):
    calls.clear(); out = fn(); return out, len(calls)
u = auth_register(RegisterRequest(username="Perf_1", password="secret1"))["user_id"]
choose_starter(StarterRequest(user_id=u, region="kanto", species="charmander"))
p = get_or_create_player(u)
for sp in ("pidgey", "rattata", "zubat", "abra", "onix", "geodude", "meowth", "mankey"): p.pokemon_collection.append(PokemonInstance(sp, 12, u))
p.pokeballs["pokeball"] = 50; p.inventory["potion"] = 20; persist_player(p)
_, n = used(lambda: get_roster(u)); ok(n == 1, f"roster = {n} round trip (budget 1)")
_, n = used(lambda: journey_travel(TravelRequest(user_id=u, to="route_1"))); ok(n <= 3, f"travel = {n} round trips (budget 3)")
tok = accounts.make_encounter_token(u, "pidgey", 5)
bt, n = used(lambda: start_battle(StartBattleRequest(user_id=u, target_species="pidgey", target_level=5, encounter_token=tok)))
ok(n <= 4, f"start battle = {n} round trips (budget 4)")
bid = bt["battle_id"]; mv = next(m["id"] for m in bt["player_pokemon"]["moves"] if (m.get("power") or 0) > 0)
_, n = used(lambda: battle_move(MoveRequest(battle_id=bid, move_name=mv))); ok(n <= 2, f"a turn that goes on = {n} round trips (budget 2)")
_, n = used(lambda: battle_item(ItemRequest(battle_id=bid, item_type="potion"))); ok(n <= 4, f"item = {n} round trips (budget 4)")
_, n = used(lambda: shop_buy(BuyRequest(user_id=u, item_id="potion", quantity=1))); ok(n <= 2, f"shop buy = {n} round trips (budget 2)")

# ---- 2. saves send only what changed ------------------------------------------------------------------------------
def last_save():
    s = [c for c in calls if c[1] == "rpc/save_player_atomic"]; return s[-1][2]
p = get_or_create_player(u); total = len({m.id for m in p.pokemon_collection} | {m.id for m in p.active_team})
used(lambda: persist_player(p)); body = last_save()
ok(body["p_pokemon"] == [] and len(body["p_pokemon_ids"]) == total, f"nothing changed: 0 Pokémon rows sent (of {total}), full id list kept")
p = get_or_create_player(u); p.pokemon_collection[3].current_hp = max(1, p.pokemon_collection[3].current_hp - 3); changed = p.pokemon_collection[3].id
used(lambda: persist_player(p)); body = last_save()
ok([r["id"] for r in body["p_pokemon"]] == [changed], "one Pokémon changed: exactly that row is sent")
row = next(r for r in fake.rows["pokemon"] if r["id"] == changed); ok(row["current_hp"] == p.pokemon_collection[3].current_hp, "…and it is stored")
p = get_or_create_player(u); newbie = PokemonInstance("eevee", 9, u); p.pokemon_collection.append(newbie)
used(lambda: persist_player(p)); body = last_save()
ok([r["id"] for r in body["p_pokemon"]] == [newbie.id], "a new Pokémon: one row sent")
p = get_or_create_player(u); gone = p.pokemon_collection[2].id; p.pokemon_collection = [m for m in p.pokemon_collection if m.id != gone]
p.active_team = [m for m in p.active_team if m.id != gone]
used(lambda: persist_player(p)); body = last_save()
ok(body["p_pokemon"] == [] and gone not in body["p_pokemon_ids"] and not any(r["id"] == gone for r in fake.rows["pokemon"]), "a removed Pokémon: nothing sent, row deleted by the id list")
p2 = get_or_create_player(u); ok(len(p2.pokemon_collection) == len({m.id for m in p2.pokemon_collection}) and all(m.id != gone for m in p2.pokemon_collection), "reload agrees with what was saved")
# two saves in a row from the same object (hashes refresh after every save)
p = get_or_create_player(u); p.pokemon_collection[0].current_hp -= 1; used(lambda: persist_player(p)); used(lambda: persist_player(p))
ok(last_save()["p_pokemon"] == [], "the second identical save sends nothing")
# a Pokémon can't be lost when a concurrent client changed it: the version check still rejects the stale writer
a, b = get_or_create_player(u), get_or_create_player(u)
a.pokemon_collection[0].current_hp = 1; persist_player(a); b.pokemon_collection[1].current_hp = 1
try: persist_player(b); stale_ok = False
except Exception as e: stale_ok = type(e).__name__ == "ConcurrentUpdateError"
ok(stale_ok, "a stale writer is still rejected (changed-only saves keep the version check)")

# ---- 3. the one-call load falls back cleanly when the function isn't installed -----------------------------------------
fake.has_bundle = False; database.SupabaseDB._bundle_ok = None
_, n = used(lambda: get_roster(u)); ok(n == 3 and database.SupabaseDB._bundle_ok is False, f"without load_player_bundle(): falls back to the two-request read (one probe + two reads = {n})")
_, n = used(lambda: get_roster(u)); ok(n == 2, "…and then stops probing (2 calls)")
fake.has_bundle = True; database.SupabaseDB._bundle_ok = None
_, n = used(lambda: get_roster(u)); ok(n == 1, "once the function exists, it is used again")

# ---- 4. locks are per player, not global ---------------------------------------------------------------------------
class R:                                           # a request object with a user id
    def __init__(self, uid=None, bid=None, tid=None): self.user_id, self.battle_id, self.trade_id = uid, bid, tid
@index._serialized
def slow(req): time.sleep(0.3); return req.user_id
def run_threads(reqs):
    t0 = time.time(); ts = [threading.Thread(target=slow, args=(r,)) for r in reqs]
    [t.start() for t in ts]; [t.join() for t in ts]; return time.time() - t0
d = run_threads([R(1), R(2), R(3), R(4)])
ok(d < 0.6, f"four different players' slow actions overlap ({d:.2f}s, a global lock would take 1.2s)")
d = run_threads([R(7), R(7), R(7)])
ok(d >= 0.85, f"the same player's actions are serialised ({d:.2f}s)")
index._remember_battle_owner("bat1", 5)
d = run_threads([R(5), R(None, "bat1")])
ok(d >= 0.55, f"a battle request waits for its owner's other actions ({d:.2f}s)")
d = run_threads([R(5), R(None, "bat1"), R(6)])
ok(d < 0.9, f"…while another player isn't held up ({d:.2f}s)")
# no deadlock when many threads take overlapping key sets in different orders
@index._serialized
def quick(req): time.sleep(0.001)
errs = []
def hammer(i):
    try:
        for j in range(60): quick(R(j % 3, f"b{(i + j) % 3}") if i % 2 else R(None, f"b{(i + j) % 3}", f"t{j % 2}"))
    except Exception as e: errs.append(e)
index._remember_battle_owner("b0", 0); index._remember_battle_owner("b1", 1); index._remember_battle_owner("b2", 2)
ts = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]; t0 = time.time(); [t.start() for t in ts]; [t.join(20) for t in ts]
ok(not errs and not any(t.is_alive() for t in ts) and time.time() - t0 < 15, "8 threads over overlapping lock sets finish (no deadlock)")
ok(index._locks._locks == {}, "lock table is empty afterwards (no leak)")
# a failure inside doesn't leave a lock held
@index._serialized
def boom(req): raise ValueError("x")
try: boom(R(9))
except ValueError: pass
ok(index._locks._locks == {}, "an exception releases its locks")

# ---- 5. pooled HTTP connections (real requests against a local server) ---------------------------------------------
script = textwrap.dedent(f"""
    import sys, threading, http.server, socketserver, json
    sys.path.insert(0, {os.path.join(REPO_ROOT, 'api', '_lib')!r})
    import http_client as h
    conns = []
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def setup(self): super().setup(); conns.append(1)
        def do_GET(self):
            b = b'[]'; self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
    class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
    srv = S(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{{srv.server_address[1]}}/x"
    for _ in range(20): assert h.get(url, timeout=5).status_code == 200
    print("CONNECTIONS", len(conns))
    # a dead port: connection errors are retried (never read errors), then raised
    import requests, time
    t0 = time.time()
    try: h.get("http://127.0.0.1:9/x", timeout=1); print("NORAISE")
    except requests.RequestException: print("RAISED", round(time.time() - t0, 1) < 4)
""")
r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
ok("CONNECTIONS 1" in r.stdout, f"20 requests reuse ONE connection ({r.stdout.strip().splitlines()[:1]})")
ok("RAISED True" in r.stdout, "a dead host raises RequestException promptly (connection retries are bounded)")

# ---- 6. request timing ---------------------------------------------------------------------------------------------
sent = []
async def inner_app(scope, receive, send):
    dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
    await send({"type": "http.response.start", "status": 200, "headers": []}); await send({"type": "http.response.body", "body": b"{}"})
async def collect(msg): sent.append(msg)
mw = index.TimingMiddleware(inner_app)
asyncio.run(mw({"type": "http", "method": "GET", "path": "/api/player/123456789/roster"}, None, collect))
hdr = dict(sent[0]["headers"]).get(b"server-timing", b"").decode()
ok("total;dur=" in hdr and "db;dur=" in hdr and '1 calls' in hdr and "lock;dur=" in hdr, f"Server-Timing header: {hdr}")
summary = dbhttp.STATS.summary()
ok("GET /api/player/:id/roster" in summary["slowest_routes_by_p95_ms"], "route ids are normalised for the statistics")
ok(summary["db_call_ms"]["n"] >= 1 and summary["status"].get("2xx", 0) >= 1, "database call time and status counts are recorded")
os.environ["ADMIN_USER_IDS"] = str(u)
am = index.metrics("Bearer " + accounts.make_token(u, "Perf_1"))
ok("slowest_routes_by_p95_ms" in am, "/api/metrics answers an admin")
os.environ["ADMIN_USER_IDS"] = ""
try: index.metrics("Bearer " + accounts.make_token(u, "Perf_1")); denied = False
except HTTPException as e: denied = e.status_code == 403
ok(denied, "…and refuses everyone else")
# slow requests are logged without secrets
import logging
class Cap(logging.Handler):
    def __init__(self): super().__init__(); self.msgs = []
    def emit(self, r): self.msgs.append(r.getMessage())
cap = Cap(); index.logger.addHandler(cap); index.SLOW_REQUEST_MS = 0; logging.disable(logging.NOTSET)   # the harness silences logging
asyncio.run(mw({"type": "http", "method": "POST", "path": "/api/battle/move", "headers": [(b"authorization", b"Bearer SECRET-TOKEN")]}, None, collect))
index.SLOW_REQUEST_MS = 1500; logging.disable(logging.CRITICAL)
ok(any("slow request POST /api/battle/move" in m for m in cap.msgs) and not any("SECRET" in m for m in cap.msgs), "slow requests are logged with a db/lock breakdown and no tokens")
print("ALL PERFORMANCE TESTS PASSED")
