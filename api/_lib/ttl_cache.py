"""
Small in-process cache with a time-to-live, for data that is read often and changes rarely (site images, the
leaderboard). Per process: with several instances, an entry can be stale for at most its TTL. A loader that raises
is never cached, so a database outage is reported as an outage rather than served from memory.
"""

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, name: str):
        self.name = name
        self._lock = threading.Lock()
        self._data: Dict[Any, Tuple[float, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get_or_load(self, key: Any, ttl: float, loader: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit and now - hit[0] < ttl:
                self.hits += 1
                return hit[1]
            self.misses += 1
        value = loader()                      # outside the lock: a slow load must not block other keys
        with self._lock:
            self._data[key] = (time.monotonic(), value)
        return value

    def invalidate(self, key: Optional[Any] = None) -> None:
        with self._lock:
            if key is None:
                self._data.clear()
            else:
                self._data.pop(key, None)

    def stats(self) -> Dict:
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses, "hit_pct": round(100.0 * self.hits / total, 1) if total else None,
                "entries": len(self._data)}
