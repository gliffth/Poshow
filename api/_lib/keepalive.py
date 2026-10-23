"""
Keep-alive pinger for a host that sleeps when idle (Render's free web service sleeps after 15 minutes).

It must run in a process that is itself always on — the Telegram bot, a VPS, a Termux session. It sends one cheap GET
(/api/health: no database) every few minutes. It runs in its own daemon thread, never raises, and logs only when the
service goes up or down, not on every ping.

It is a best effort: it is not part of the web API, and a free instance can still be restarted by the host.
"""

import logging
import os
import random
import threading
import time
from typing import Callable, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger("keepalive")

DEFAULT_INTERVAL = 600.0      # 10 minutes
MIN_INTERVAL = 60.0           # never hammer the service
MAX_INTERVAL = 840.0          # 14 minutes: anything longer lets a 15-minute idle timer fire
COLD_START_TIMEOUT = 75.0     # a sleeping instance needs about a minute to wake
RETRY_DELAY = 30.0            # after a failed ping, try again sooner (the instance may be waking up)
RETRIES = 3


def normalise_url(raw: Optional[str]) -> Optional[str]:
    """`https://x.onrender.com` or `https://x.onrender.com/api/health` -> the health URL; anything else -> None."""
    if not raw:
        return None
    raw = raw.strip()
    u = urlparse(raw)
    if u.scheme not in ("http", "https") or not u.netloc:
        return None
    if u.path in ("", "/"):
        return raw.rstrip("/") + "/api/health"
    return raw


class KeepAlive:
    def __init__(self, url: str, interval: float = DEFAULT_INTERVAL, timeout: float = COLD_START_TIMEOUT,
                 min_interval: float = MIN_INTERVAL, retry_delay: float = RETRY_DELAY,
                 get: Optional[Callable] = None):
        self.url = normalise_url(url) or url
        self.interval = min(MAX_INTERVAL, max(min_interval, float(interval)))
        self.timeout = timeout
        self.retry_delay = retry_delay
        self._get = get or requests.get
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.up: Optional[bool] = None          # None until the first answer
        self.pings = 0
        self.failures = 0

    def ping(self) -> bool:
        """One request. True if the service answered 2xx. Never raises."""
        self.pings += 1
        try:
            res = self._get(self.url, timeout=self.timeout)
            ok = 200 <= res.status_code < 300
        except Exception as e:                   # noqa: BLE001 — a failed ping must never crash the bot
            ok = False
            err = type(e).__name__
        else:
            err = f"HTTP {res.status_code}"
        if not ok:
            self.failures += 1
        if ok != self.up:                        # log only the transitions
            (logger.info if ok else logger.warning)("keep-alive: %s is %s%s", self.url, "UP" if ok else "DOWN",
                                                    "" if ok else f" ({err})")
            self.up = ok
        return ok

    def _wait(self, seconds: float) -> bool:
        """Sleep; True if we were asked to stop meanwhile."""
        return self._stop.wait(seconds)

    def _run(self) -> None:
        if self._wait(min(5.0, self.interval)):             # let the bot finish starting, then wake the service
            return
        while not self._stop.is_set():
            ok = self.ping()
            tries = 0
            while not ok and tries < RETRIES and not self._stop.is_set():
                if self._wait(self.retry_delay):
                    return
                tries += 1
                ok = self.ping()
            if self._wait(self.interval * random.uniform(0.9, 1.1)):     # a little jitter
                return

    def start(self) -> "KeepAlive":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="keepalive", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


def start_from_env() -> Optional[KeepAlive]:
    """Start the pinger when KEEPALIVE_URL is set (the API's base URL or its /api/health URL). KEEPALIVE_INTERVAL is in
    seconds (clamped to 60..840, default 600)."""
    raw = os.environ.get("KEEPALIVE_URL")
    if not raw:
        return None
    url = normalise_url(raw)
    if not url:
        logger.warning("KEEPALIVE_URL is not a valid http(s) URL — keep-alive is off")
        return None
    try:
        interval = float(os.environ.get("KEEPALIVE_INTERVAL", DEFAULT_INTERVAL))
    except ValueError:
        interval = DEFAULT_INTERVAL
    ka = KeepAlive(url, interval).start()
    logger.info("keep-alive: pinging %s every %.0f s", url, ka.interval)
    return ka
