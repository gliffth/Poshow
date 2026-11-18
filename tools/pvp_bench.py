"""
PvP round-trip and latency benchmark against the in-memory Supabase stand-in with a fixed delay per request.

    python tools/pvp_bench.py [latency_ms=40] [matches=8]

It reports database requests per call and the time a move takes with many matches running at once. The delay is
simulated, so absolute times are only meaningful relative to each other; the request counts are exact.
Works on any version of the repository that has the classic duel endpoints.
"""
import os, statistics, sys, threading, time
HERE = os.path.dirname(os.path.abspath(__file__))
_script = __file__
__file__ = os.path.join(os.path.dirname(HERE), "tests", "harness.py")      # the harness finds the repository from its own path
exec(open(__file__).read())
__file__ = _script
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import index
from index import *

LAT = float(sys.argv[1]) / 1000 if len(sys.argv) > 1 else 0.04
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
index.notify_telegram = lambda *a, **k: None


def mk(name, sp):
    u = auth_register(RegisterRequest(username=name, password="secret1"))["user_id"]
    choose_starter(StarterRequest(user_id=u, region="kanto", species=sp))
    return u


def counted(fn):
    n0 = len(fake.reqs)
    t0 = time.perf_counter()
    out = fn()
    return out, len(fake.reqs) - n0, (time.perf_counter() - t0) * 1000


def duel(a, b):
    d = pvp_challenge(PvpChallengeRequest(user_id=a, username=index.get_or_create_player(b).username))
    pvp_respond(PvpRespondRequest(user_id=b, match_id=d["id"], accept=True))
    return d["id"]


def move_of(uid):
    cur = pvp_state(uid)["active"]
    me = cur["me"]
    return cur, me["team"][me["active"]]["moves"][0]["id"]


a, b = mk("Bench_A", "charmander"), mk("Bench_B", "squirtle")
fake.latency = 0
mid = duel(a, b)
fake.latency = LAT
_, n_poll, ms_poll = counted(lambda: pvp_state(a))
fake.latency = 0
idle = mk("Bench_Idle", "charmander")
fake.latency = LAT
_, n_poll_idle, _ = counted(lambda: pvp_state(idle))
cur, mv = move_of(a)
_, n_first, ms_first = counted(lambda: pvp_action(PvpActionRequest(user_id=a, match_id=mid, action={"type": "move", "move": mv})))
cur, mv = move_of(b)
_, n_second, ms_second = counted(lambda: pvp_action(PvpActionRequest(user_id=b, match_id=mid, action={"type": "move", "move": mv})))
print(f"simulated delay per database request: {LAT * 1000:.0f} ms")
print(f"state poll (one player, one active match): {n_poll} requests, {ms_poll:.0f} ms")
print(f"state poll (no match):                     {n_poll_idle} requests")
print(f"first move of a turn (waiting for foe):    {n_first} requests, {ms_first:.0f} ms")
print(f"second move (turn resolves):               {n_second} requests, {ms_second:.0f} ms")

# many matches at once
fake.latency = 0
pairs = [(mk(f"C{i}a", "charmander"), mk(f"C{i}b", "squirtle")) for i in range(N)]
mids = [duel(x, y) for x, y in pairs]
fake.latency = LAT
times, errors = [], []


def play(x, y, match):
    for _ in range(4):
        for uid in (x, y):
            try:
                cur = pvp_state(uid)["active"]
                if cur["status"] != "active" or cur["waiting"] or cur["phase"] == "switch":
                    continue
                me = cur["me"]
                mv = me["team"][me["active"]]["moves"][0]["id"]
                t0 = time.perf_counter()
                pvp_action(PvpActionRequest(user_id=uid, match_id=match, action={"type": "move", "move": mv}))
                times.append((time.perf_counter() - t0) * 1000)
            except Exception as e:
                errors.append(repr(e))


threads = [threading.Thread(target=play, args=(x, y, m)) for (x, y), m in zip(pairs, mids)]
t0 = time.perf_counter()
[t.start() for t in threads]
[t.join() for t in threads]
wall = time.perf_counter() - t0
times.sort()
print(f"{N} matches at once ({len(times)} moves, {len(errors)} errors): median {statistics.median(times):.0f} ms, "
      f"95th percentile {times[int(len(times) * 0.95) - 1]:.0f} ms, wall {wall:.1f} s")
