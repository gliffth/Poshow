"""
One pooled HTTP client for all Supabase traffic, plus request- and operation-level timing.

* Real `requests`: a single shared Session (keep-alive connections are reused instead of a new TLS handshake per
  call), bounded pool, retries ONLY for connection errors (the request was never sent, so retrying is safe).
* Anything without `Session` (the test doubles) is used directly, so tests can still patch get/post/patch/delete.
* Every call is labelled with its database operation ("rpc:save_player_atomic", "GET battle_sessions", ...) and
  recorded: latency, rows read / written, response size, errors by kind, connections in flight. The numbers feed the
  request's Server-Timing header and /api/metrics. Request bodies and tokens are never recorded.
"""

import contextvars
import logging
import os
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional

import requests

logger = logging.getLogger("dbhttp")

DB_TARGET_MS = float(os.environ.get("DB_TARGET_MS", "80"))       # latency objective for a single database call
SLOW_DB_MS = float(os.environ.get("SLOW_DB_MS", "250"))          # calls above this are logged with their operation
_MAX_JSON_BYTES = 512 * 1024                                     # larger responses aren't parsed for a row count

POOL_SIZE = 32
_session = None
_lock = threading.Lock()

# the current request's timing record (set by the middleware; None outside a request)
CURRENT: contextvars.ContextVar = contextvars.ContextVar("poshow_request_timing", default=None)


def _backend():
    global _session
    if not hasattr(requests, "Session"):
        return requests                     # a test double
    if _session is None:
        with _lock:
            if _session is None:
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry
                s = requests.Session()
                retry = Retry(total=2, connect=2, read=0, status=0, redirect=0, backoff_factor=0.15)
                adapter = HTTPAdapter(pool_connections=4, pool_maxsize=POOL_SIZE, max_retries=retry)
                s.mount("https://", adapter)
                s.mount("http://", adapter)
                _session = s
    return _session


def label(method: str, url: str) -> str:
    """The database operation behind a REST call: 'rpc:<function>' or '<METHOD> <table>'."""
    path = url.split("?", 1)[0]
    tail = path.split("/rest/v1/", 1)[-1].strip("/")
    if tail.startswith("rpc/"):
        return "rpc:" + tail[4:]
    return f"{method.upper()} {tail.split('/')[0] or 'unknown'}"


def _rows_written(op: str, body) -> Optional[int]:
    """Rows a write sends, counted from the request (never stored). None when it can't be told."""
    if not isinstance(body, (dict, list)):
        return None
    if isinstance(body, list):
        return len(body)
    if op == "rpc:save_player_atomic":
        return 1 + len(body.get("p_pokemon") or [])
    if op == "rpc:save_players_atomic":
        n = sum(1 + len(i.get("pokemon") or []) for i in (body.get("p_batch") or []))
        return n + (1 if body.get("p_trade") else 0)
    if op.startswith("rpc:"):
        return 1
    return 1


def _rows_read(res) -> Optional[int]:
    """Rows a read returned. Uses Content-Range when PostgREST sends it, otherwise parses the JSON ONCE (and caches
    that parse on the response so the caller doesn't repeat it)."""
    try:
        cr = (getattr(res, "headers", None) or {}).get("content-range")
        if cr and "/" in cr and cr.split("/")[-1].isdigit():
            return int(cr.split("/")[-1])
        if getattr(res, "status_code", 0) != 200:
            return None
        size = len(getattr(res, "content", b"") or b"")
        if size > _MAX_JSON_BYTES:
            return None
        data = res.json()
        res.json = lambda *a, **k: data                                  # cached: callers get the same object
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            pk = data.get("pokemon")
            return 1 + (len(pk) if isinstance(pk, list) else 0)
        return 0 if data is None else 1
    except Exception:                                                    # noqa: BLE001 — metrics must never break a call
        return None


def _timed(method: str, url: str, **kw):
    op = label(method, url)
    t0 = time.perf_counter()
    STATS.enter()
    res = None
    err = None
    try:
        res = getattr(_backend(), method)(url, **kw)
        return res
    except requests.RequestException as e:
        kind = type(e).__name__                       # by name: the test doubles don't define every requests exception
        err = "timeout" if "Timeout" in kind else "connection" if "Connection" in kind else "other"
        raise
    finally:
        ms = (time.perf_counter() - t0) * 1000
        STATS.leave()
        status = getattr(res, "status_code", None)
        if err is None and status is not None and status >= 400:
            err = f"http_{status // 100}xx"
        written = _rows_written(op, kw.get("json")) if method != "get" else None
        read = _rows_read(res) if (res is not None and method == "get" or op.startswith("rpc:load")) and res is not None else None
        nbytes = len(getattr(res, "content", b"") or b"") if res is not None else 0
        rec = CURRENT.get()
        if rec is not None:
            rec["db_ms"] += ms
            rec["db_calls"] += 1
            if ms > rec.get("db_max_ms", 0):
                rec["db_max_ms"], rec["db_max_op"] = ms, op
        STATS.record_db(ms, op=op, rows_read=read, rows_written=written, nbytes=nbytes, error=err)
        if ms >= SLOW_DB_MS:
            logger.warning("slow db op %s: %.0f ms (rows read %s, written %s, %d bytes, status %s)",
                           op, ms, read, written, nbytes, status if status is not None else "no response")


def get(url, **kw):
    return _timed("get", url, **kw)


def post(url, **kw):
    return _timed("post", url, **kw)


def patch(url, **kw):
    return _timed("patch", url, **kw)


def delete(url, **kw):
    return _timed("delete", url, **kw)


class _PoolWarnings(logging.Handler):
    """urllib3 logs 'Connection pool is full, discarding connection' when more calls overlap than the pool holds."""

    def __init__(self, stats):
        super().__init__(level=logging.WARNING)
        self.stats = stats

    def emit(self, record):
        if "pool is full" in record.getMessage().lower():
            self.stats.pool_full += 1


class _Op:
    __slots__ = ("lat", "n", "errors", "rows_read", "rows_written", "bytes")

    def __init__(self, keep):
        self.lat: Deque[float] = deque(maxlen=keep)
        self.n = 0
        self.errors: Dict[str, int] = {}
        self.rows_read = 0
        self.rows_written = 0
        self.bytes = 0


class Stats:
    """Rolling in-process statistics: the last N requests per route and the last N database calls per operation."""

    KEEP = 500

    def __init__(self):
        self._lock = threading.Lock()
        self.routes: Dict[str, Deque[float]] = {}
        self.ops: Dict[str, _Op] = {}
        self.db: Deque[float] = deque(maxlen=self.KEEP * 4)
        self.lock_wait: Deque[float] = deque(maxlen=self.KEEP * 4)
        self.status: Dict[str, int] = {}
        self.started = time.time()
        self.inflight = 0
        self.peak_inflight = 0
        self.pool_full = 0
        self._req_times: Deque[float] = deque(maxlen=20000)
        self._db_times: Deque[float] = deque(maxlen=20000)

    # ── recording ──
    def enter(self):
        with self._lock:
            self.inflight += 1
            self.peak_inflight = max(self.peak_inflight, self.inflight)

    def leave(self):
        with self._lock:
            self.inflight = max(0, self.inflight - 1)

    def record_db(self, ms: float, op: Optional[str] = None, rows_read: Optional[int] = None,
                  rows_written: Optional[int] = None, nbytes: int = 0, error: Optional[str] = None):
        now = time.time()
        with self._lock:
            self.db.append(ms)
            self._db_times.append(now)
            if op:
                o = self.ops.get(op)
                if o is None:
                    o = self.ops[op] = _Op(self.KEEP)
                o.lat.append(ms)
                o.n += 1
                o.bytes += nbytes
                if rows_read:
                    o.rows_read += rows_read
                if rows_written:
                    o.rows_written += rows_written
                if error:
                    o.errors[error] = o.errors.get(error, 0) + 1

    def record_lock(self, ms: float):
        self.lock_wait.append(ms)

    def record_request(self, route: str, ms: float, status: int):
        with self._lock:
            self.routes.setdefault(route, deque(maxlen=self.KEEP)).append(ms)
            self._req_times.append(time.time())
            key = f"{status // 100}xx" if status != 409 else "409"
            self.status[key] = self.status.get(key, 0) + 1

    # ── reporting ──
    @staticmethod
    def _pct(values, q: float) -> Optional[float]:
        v = sorted(values)
        if not v:
            return None
        return round(v[min(len(v) - 1, int(q * len(v)))], 1)

    @classmethod
    def _dist(cls, values) -> Dict:
        return {"n": len(values), "p50": cls._pct(values, .5), "p95": cls._pct(values, .95), "p99": cls._pct(values, .99)}

    @staticmethod
    def _rate(times, window: float = 60.0) -> float:
        now = time.time()
        recent = sum(1 for t in list(times) if now - t <= window)
        return round(recent / window, 2)

    def summary(self) -> Dict:
        with self._lock:
            routes = {r: self._dist(d) for r, d in self.routes.items()}
            ops = {}
            for name, o in self.ops.items():
                lat = list(o.lat)
                d = self._dist(lat)
                d.update({
                    "calls": o.n,
                    "over_target_pct": round(100.0 * sum(1 for x in lat if x > DB_TARGET_MS) / len(lat), 1) if lat else 0.0,
                    "rows_read": o.rows_read, "rows_written": o.rows_written, "kb": round(o.bytes / 1024, 1),
                    "errors": dict(o.errors),
                })
                ops[name] = d
            db_all = list(self.db)
            inflight, peak, full = self.inflight, self.peak_inflight, self.pool_full
        slowest = dict(sorted(routes.items(), key=lambda kv: -(kv[1]["p95"] or 0))[:15])
        by_p95 = dict(sorted(ops.items(), key=lambda kv: -(kv[1]["p95"] or 0)))
        dist = self._dist(db_all)
        worst = next(iter(by_p95.items()), (None, {}))
        return {
            "uptime_s": int(time.time() - self.started),
            "status": dict(self.status),
            "throughput": {"requests_per_s": self._rate(self._req_times), "db_calls_per_s": self._rate(self._db_times)},
            "db_call_ms": {**dist, "target_ms": DB_TARGET_MS,
                           "over_target_pct": round(100.0 * sum(1 for x in db_all if x > DB_TARGET_MS) / len(db_all), 1) if db_all else 0.0,
                           "meets_target_p95": (dist["p95"] is not None and dist["p95"] <= DB_TARGET_MS) if db_all else None,
                           "note": "measured from this server: includes the network round trip to the database"},
            "db_operations": by_p95,
            "slowest_operation": {"op": worst[0], "p95": worst[1].get("p95")} if worst[0] else None,
            "pool": {"size": POOL_SIZE, "in_flight": inflight, "peak_in_flight": peak,
                     "saturation_pct": round(100.0 * peak / POOL_SIZE, 1), "pool_full_warnings": full},
            "lock_wait_ms": self._dist(list(self.lock_wait)),
            "slowest_routes_by_p95_ms": slowest,
        }


STATS = Stats()
logging.getLogger("urllib3.connectionpool").addHandler(_PoolWarnings(STATS))


def start_request() -> dict:
    rec = {"t0": time.perf_counter(), "db_ms": 0.0, "db_calls": 0, "lock_ms": 0.0}
    CURRENT.set(rec)
    return rec
