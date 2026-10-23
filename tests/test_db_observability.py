import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Database observability and the consolidations built on it.
sys.path.insert(0, os.path.join(root, "tests"))
import asyncio, logging, threading, time
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import accounts, requests as rq, index
import http_client as dbhttp
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
random_names = lambda: None
S = dbhttp.STATS

# ---- 1. operation labels --------------------------------------------------------------------------------------------
L = dbhttp.label
ok(L("post", "https://x.supabase.co/rest/v1/rpc/save_player_atomic") == "rpc:save_player_atomic", "RPC calls are labelled by function")
ok(L("get", "https://x/rest/v1/battle_sessions?user_id=eq.5&select=*") == "GET battle_sessions", "table reads are labelled METHOD table")
ok(L("delete", "https://x/rest/v1/login_codes?code=eq.A") == "DELETE login_codes" and L("patch", "http://fake/rest/v1/trades?id=eq.1") == "PATCH trades", "writes too")
ok("user_id" not in L("get", "https://x/rest/v1/players?user_id=eq.123456"), "the label never contains query values (no ids, tokens or filters)")

# ---- 2. real actions populate per-operation statistics ---------------------------------------------------------------
u = auth_register(RegisterRequest(username="Obs_1", password="secret1"))["user_id"]
choose_starter(StarterRequest(user_id=u, region="kanto", species="charmander"))
p = get_or_create_player(u)
for sp in ("pidgey", "rattata", "zubat", "abra"): p.pokemon_collection.append(PokemonInstance(sp, 10, u))
persist_player(p)
S.__init__()                                                   # start from a clean slate
get_roster(u)
ops = S.summary()["db_operations"]
b = ops["rpc:load_player_bundle"]
ok(b["calls"] == 1 and b["rows_read"] == 1 + 5 and b["kb"] > 0, f"loading a player: 1 call, {b['rows_read']} rows read (player + 5 Pokémon), {b['kb']} KB")
p = get_or_create_player(u); p.pokemon_collection[1].current_hp -= 1; p.coins += 5
S.__init__(); persist_player(p)
w = S.summary()["db_operations"]["rpc:save_player_atomic"]
ok(w["calls"] == 1 and w["rows_written"] == 2, f"a save of one changed Pokémon writes {w['rows_written']} rows (player + 1), not the whole collection")
ok(all(k in b for k in ("p50", "p95", "p99", "n", "over_target_pct", "errors")), "every operation reports p50 / p95 / p99, sample count, % over target and errors")
ok(S.summary()["db_call_ms"]["target_ms"] == 80.0, "the 80 ms target is part of the report")
# the row-count parse is cached on the response: callers don't parse twice
res = dbhttp.get("http://fake/rest/v1/players?user_id=eq.%d" % u)
ok(res.json() is res.json() and isinstance(res.json(), list), "the parsed body is cached on the response (no double JSON parse)")

# ---- 3. errors by kind --------------------------------------------------------------------------------------------------
S.__init__()
real_get = rq.get; real_post = rq.post; real_patch = rq.patch; real_delete = rq.delete
rq.get = lambda url, *a, **k: F.Resp(503, {"message": "down"})
dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
class ReadTimeoutX(rq.RequestException): pass
class ConnectionErrorX(rq.RequestException): pass
for exc in (ReadTimeoutX, ConnectionErrorX):
    def boom(*a, _e=exc, **k): raise _e("x")
    rq.get = boom
    try: dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
    except rq.RequestException: pass
rq.get = real_get
errs = S.summary()["db_operations"]["GET players"]["errors"]
ok(errs == {"http_5xx": 1, "timeout": 1, "connection": 1}, f"errors are counted by kind: {errs}")
ok(S.summary()["db_operations"]["GET players"]["calls"] == 3, "a failed call still counts as a call, with its latency")

# ---- 4. connection pool utilisation ---------------------------------------------------------------------------------------
S.__init__(); fake.latency = 0.15
ts = [threading.Thread(target=lambda: dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")) for _ in range(8)]
[t.start() for t in ts]; time.sleep(0.05); mid = S.summary()["pool"]["in_flight"]; [t.join() for t in ts]
fake.latency = 0
pool = S.summary()["pool"]
ok(mid >= 6 and pool["peak_in_flight"] >= 6 and pool["in_flight"] == 0, f"in-flight calls are tracked (peak {pool['peak_in_flight']}, now {pool['in_flight']})")
ok(pool["size"] == dbhttp.POOL_SIZE and 0 < pool["saturation_pct"] <= 100, f"saturation = peak / pool size = {pool['saturation_pct']}%")
logging.disable(logging.NOTSET); logging.getLogger("urllib3.connectionpool").warning("Connection pool is full, discarding connection: x"); logging.disable(logging.CRITICAL)
ok(S.summary()["pool"]["pool_full_warnings"] == 1, "urllib3's 'pool is full' warning is counted")

# ---- 5. throughput -------------------------------------------------------------------------------------------------------------
S.__init__()
for _ in range(30): dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
tp = S.summary()["throughput"]
ok(tp["db_calls_per_s"] > 0, f"database calls per second over the last minute: {tp['db_calls_per_s']}")

# ---- 6. the 80 ms target is evaluated from measurements --------------------------------------------------------------------
S.__init__()
for _ in range(20): dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
fast = S.summary()["db_call_ms"]
ok(fast["meets_target_p95"] is True and fast["over_target_pct"] == 0.0, "fast calls: target met, 0% over")
S.__init__(); fake.latency = 0.1
for _ in range(10): dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
fake.latency = 0
slow = S.summary()
ok(slow["db_call_ms"]["meets_target_p95"] is False and slow["db_call_ms"]["over_target_pct"] == 100.0, "100 ms calls: target missed, 100% over")
ok(slow["slowest_operation"]["op"] == "GET players" and slow["slowest_operation"]["p95"] >= 100, "the slowest operation is named")
ok("round trip" in slow["db_call_ms"]["note"], "the report says these include the network round trip (they are not server-side execution times)")

# ---- 7. slow calls are logged by operation, without secrets ---------------------------------------------------------------------
class Cap(logging.Handler):
    def __init__(self): super().__init__(); self.msgs = []
    def emit(self, r): self.msgs.append(r.getMessage())
cap = Cap(); dbhttp.logger.addHandler(cap); old_thr = dbhttp.SLOW_DB_MS; dbhttp.SLOW_DB_MS = 0; logging.disable(logging.NOTSET)
dbhttp.post("http://fake/rest/v1/rpc/load_player_bundle", json={"p_user_id": u, "token": "SECRET-TOKEN"}, headers={"Authorization": "Bearer SECRET-TOKEN"})
dbhttp.SLOW_DB_MS = old_thr; logging.disable(logging.CRITICAL)
ok(any("slow db op rpc:load_player_bundle" in m for m in cap.msgs) and not any("SECRET" in m for m in cap.msgs), "slow calls are logged with their operation, rows and size — never bodies or tokens")

# ---- 8. Server-Timing names the slowest operation --------------------------------------------------------------------------------
sent = []
async def inner(scope, receive, send):
    dbhttp.get("http://fake/rest/v1/players?user_id=eq.1"); dbhttp.post("http://fake/rest/v1/rpc/load_player_bundle", json={"p_user_id": u})
    await send({"type": "http.response.start", "status": 200, "headers": []}); await send({"type": "http.response.body", "body": b"{}"})
async def collect(m): sent.append(m)
asyncio.run(index.TimingMiddleware(inner)({"type": "http", "method": "GET", "path": "/api/x"}, None, collect))
hdr = dict(sent[0]["headers"])[b"server-timing"].decode()
ok('dbmax;dur=' in hdr and ('desc="rpc:load_player_bundle"' in hdr or 'desc="GET players"' in hdr), f"Server-Timing: {hdr}")

# ---- 9. /api/metrics and the admin database endpoints ---------------------------------------------------------------------------------
os.environ["ADMIN_USER_IDS"] = str(u); tok = "Bearer " + accounts.make_token(u, "Obs_1")
m = index.metrics(tok)
ok(all(k in m for k in ("db_operations", "pool", "throughput", "db_call_ms", "caches", "lock_wait_ms")), "/api/metrics: operations, pool, throughput, latency, caches, lock wait")
h = index.admin_db_health(tok)
ok(h["database"]["cache_hit_pct"] > 90 and "connections" in h, "/api/admin/db-health returns the database-side numbers")
for name in ("load_player", "player_sessions", "leaderboard"):
    ok(index.admin_db_explain(name, u, tok)["query"] == name, f"/api/admin/db-explain runs the named query '{name}'")
ok(code(lambda: index.admin_db_explain("drop table players", u, tok)) == 503, "an unknown / arbitrary query name is refused")
fake.has_health = False
ok(code(lambda: index.admin_db_health(tok)) == 503, "a missing function is reported (503: re-run schema.sql), not guessed")
fake.has_health = True
os.environ["ADMIN_USER_IDS"] = ""
ok(code(lambda: index.admin_db_health(tok)) == 403 and code(lambda: index.admin_db_explain("load_player", u, tok)) == 403, "both are admin only")

# ---- 10. instrumentation is cheap ---------------------------------------------------------------------------------------------------
S.__init__(); n = 3000; t0 = time.perf_counter()
for _ in range(n): dbhttp.get("http://fake/rest/v1/players?user_id=eq.1")
per_call_ms = (time.perf_counter() - t0) * 1000 / n
ok(per_call_ms < 0.5, f"instrumentation + fake round trip costs {per_call_ms:.3f} ms per call (well under the 80 ms target)")

# ---- 11. caching of rarely changing, often read data ---------------------------------------------------------------------------------
calls = []
for n_ in ("get", "post"):
    real = getattr(rq, n_)
    setattr(rq, n_, (lambda real, n_: lambda url, *a, **k: calls.append(url) or real(url, *a, **k))(real, n_))
index._assets_cache.invalidate(); index._leaderboard_cache.invalidate()
calls.clear(); index.get_assets(); index.get_assets(); index.get_assets()
ok(sum("site_assets" in c for c in calls) == 1, "site assets: 3 page loads -> 1 database read")
adm = "Bearer " + accounts.make_token(u, "Obs_1"); os.environ["ADMIN_USER_IDS"] = str(u)
index.admin_set_asset(AssetRequest(key=admin_system.ASSET_KEYS[0], url="/scenes/x.png"), adm) if hasattr(admin_system, "ASSET_KEYS") else None
calls.clear(); out = index.get_assets()
ok(out["assets"].get(admin_system.ASSET_KEYS[0]) == "/scenes/x.png" and sum("site_assets" in c for c in calls) == 1, "an admin edit clears the cache: the new image shows immediately")
os.environ["ADMIN_USER_IDS"] = ""
calls.clear(); index.leaderboard(10); index.leaderboard(10); index.leaderboard(20)
ok(sum("/players" in c for c in calls) == 2, "leaderboard: same limit cached, a different limit is its own entry")
old_ttl = index.LEADERBOARD_TTL_S; index.LEADERBOARD_TTL_S = 0.05; time.sleep(0.08); calls.clear(); index.leaderboard(10)
index.LEADERBOARD_TTL_S = old_ttl
ok(sum("/players" in c for c in calls) == 1, "entries expire after their TTL")
rq.get = real_get; rq.post = real_post
c = index.ttl_cache.TTLCache("t"); boom = {"on": True}
def loader():
    if boom["on"]: raise RuntimeError("down")
    return [1]
try: c.get_or_load("k", 60, loader); raised = False
except RuntimeError: raised = True
boom["on"] = False
ok(raised and c.get_or_load("k", 60, loader) == [1], "a failing loader is never cached")
st = index._leaderboard_cache.stats()
ok(st["hits"] >= 1 and st["misses"] >= 1 and st["hit_pct"] is not None, f"cache hit rate is reported ({st['hit_pct']}%)")

# ---- 12. consolidation: a fight ends in ONE write ------------------------------------------------------------------------------------
def start(sp="pidgey", lvl=5):
    tk = accounts.make_encounter_token(u, sp, lvl)
    return start_battle(StartBattleRequest(user_id=u, target_species=sp, target_level=lvl, encounter_token=tk))
journey_travel(TravelRequest(user_id=u, to="route_1"))
bt = start(); bid = bt["battle_id"]
rec = index._sessions.load(bid); rec["wild_pokemon"]["current_hp"] = 1; index._sessions.save(bid, u, rec["player_pokemon"], rec["wild_pokemon"])
mv = next(m["id"] for m in bt["player_pokemon"]["moves"] if (m.get("power") or 0) > 0)
for n_ in ("get", "post", "patch", "delete"):
    real = getattr(rq, n_)
    setattr(rq, n_, (lambda real, n_: lambda url, *a, **k: calls.append((n_.upper(), url.split("/rest/v1/")[-1].split("?")[0], (k.get("json") or {}).get("p_close_battles"))) or real(url, *a, **k))(real, n_))
calls.clear(); out = battle_move(MoveRequest(battle_id=bid, move_name=mv))
ok(out["is_finished"] and len(calls) == 3, f"winning a fight = {len(calls)} database calls (was 4): {[c[1] for c in calls]}")
ok(not any(c[0] == "DELETE" for c in calls) and any(c[2] == [bid] for c in calls), "…the session is deleted inside the save (p_close_battles), not by a separate call")
ok(not any(r["user_id"] == u for r in fake.rows["battle_sessions"]), "…and it is gone")
# a failing save leaves the session in place (it ends only if the result was stored)
bt = start(); bid = bt["battle_id"]
rec = index._sessions.load(bid); rec["wild_pokemon"]["current_hp"] = 1; index._sessions.save(bid, u, rec["player_pokemon"], rec["wild_pokemon"])
fake.fail_pokemon_write = True
try: battle_move(MoveRequest(battle_id=bid, move_name=mv)); raised = False
except Exception: raised = True
fake.fail_pokemon_write = False
ok(raised and any(r["battle_id"] == bid for r in fake.rows["battle_sessions"]), "if the save fails the session is still there (nothing half-ended)")
# the RPC only ever deletes the caller's own sessions
other = auth_register(RegisterRequest(username="Obs_2", password="secret1"))["user_id"]
fake.rows["battle_sessions"].append({"battle_id": "foreign", "user_id": other, "player_pokemon": {}, "wild_pokemon": {}, "updated_at": "2099-01-01T00:00:00Z"})
pl = get_or_create_player(u); index._db.save_player(pl, close_battles=["foreign"])
ok(any(r["battle_id"] == "foreign" for r in fake.rows["battle_sessions"]), "a save can't close someone else's battle")
# starting a new fight over an old one: the old session leaves with the token / damage save
bt = start(); old_id = bt["battle_id"]; calls.clear(); bt2 = start()
ok(not any(c[0] == "DELETE" for c in calls) and not any(r["battle_id"] == old_id for r in fake.rows["battle_sessions"]), f"replacing a fight: no separate DELETE ({[c[:2] for c in calls]})")
print("ALL DB-OBSERVABILITY TESTS PASSED")
