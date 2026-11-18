"""
Wake waiting requests when something changes. A battle client holds one request open; the moment the opponent acts the
server completes it, so the next state arrives without waiting for a poll.

This only reaches requests served by the same process. To stay correct with several processes (or a missed
wake-up) every waiter also re-checks the stored state every few seconds, so the worst case is a short poll.
"""

import asyncio
import threading
import time
from typing import Awaitable, Callable, Dict, List, Optional, Tuple


class Notifier:
    def __init__(self):
        self._lock = threading.Lock()
        self._waiters: Dict[str, List[Tuple[asyncio.AbstractEventLoop, asyncio.Future]]] = {}

    def notify(self, key: str) -> None:
        """Safe to call from any thread."""
        with self._lock:
            items = self._waiters.pop(key, [])
        for loop, fut in items:
            loop.call_soon_threadsafe(lambda f=fut: f.done() or f.set_result(True))

    def _register(self, key: str) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        with self._lock:
            self._waiters.setdefault(key, []).append((loop, fut))
        return fut

    def _unregister(self, key: str, fut: asyncio.Future) -> None:
        with self._lock:
            items = self._waiters.get(key)
            if items:
                self._waiters[key] = [(l, f) for (l, f) in items if f is not fut]
                if not self._waiters[key]:
                    self._waiters.pop(key, None)

    async def wait_for(self, key: str, check: Callable[[], Awaitable[Optional[dict]]], timeout: float,
                       recheck_s: float = 4.0):
        """Return the first non-None result of `check()`, or None after `timeout` seconds.
        The waiter is registered before each check, so a change can never slip between the check and the wait."""
        end = time.monotonic() + timeout
        while True:
            fut = self._register(key)
            try:
                result = await check()
                if result is not None:
                    return result
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return None
                try:
                    await asyncio.wait_for(fut, min(recheck_s, remaining))
                except asyncio.TimeoutError:
                    pass
            finally:
                self._unregister(key, fut)
