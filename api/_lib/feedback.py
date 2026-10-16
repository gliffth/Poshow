"""
Player feedback / bug reports. Stored in the `feedback` table (in memory when there is no database).

Reports may come from anyone (a broken login is exactly when someone needs this), so the input is capped and
cleaned and each sender has a small hourly budget.
"""

import logging
import re
import time
from typing import Dict, List, Optional

import requests

from database import DatabaseError

logger = logging.getLogger(__name__)

CATEGORIES = ("bug", "idea", "other")
MIN_LEN, MAX_LEN = 5, 1000
PER_HOUR = 5
CONTEXT_KEYS = ("view", "theme", "app", "ua", "screen", "route")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FeedbackError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


class FeedbackStore:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.remote = bool(url and key)
        self.url = url
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"} if key else {}
        self._mem: List[Dict] = []
        self._sent: Dict[str, List[float]] = {}

    # ── rules ──
    def _budget(self, sender: str) -> None:
        now = time.time()
        recent = [t for t in self._sent.get(sender, []) if now - t < 3600]
        if len(recent) >= PER_HOUR:
            raise FeedbackError("You've sent a few reports already — please try again later.", 429)
        recent.append(now)
        self._sent[sender] = recent

    @staticmethod
    def clean(text: str) -> str:
        return _CTRL.sub("", (text or "")).strip()

    @staticmethod
    def clean_context(ctx: Optional[Dict]) -> Dict:
        out = {}
        for k in CONTEXT_KEYS:
            v = (ctx or {}).get(k)
            if isinstance(v, (str, int, float)):
                out[k] = FeedbackStore.clean(str(v))[:200]
        return out

    # ── api ──
    def submit(self, sender: str, user_id: Optional[int], username: Optional[str], category: str,
               message: str, context: Optional[Dict] = None) -> Dict:
        category = (category or "bug").lower()
        if category not in CATEGORIES:
            raise FeedbackError("Pick bug, idea or other.")
        message = self.clean(message)
        if len(message) < MIN_LEN:
            raise FeedbackError("Tell us a little more (at least a few words).")
        if len(message) > MAX_LEN:
            raise FeedbackError(f"Please keep it under {MAX_LEN} characters.")
        self._budget(sender)
        row = {"user_id": user_id, "username": self.clean(username or "")[:40] or None, "category": category,
               "message": message, "context": self.clean_context(context), "status": "new"}
        if not self.remote:
            row["id"] = len(self._mem) + 1
            row["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._mem.append(row)
            return row
        try:
            res = requests.post(f"{self.url}/rest/v1/feedback", headers={**self.headers, "Prefer": "return=representation"},
                                json=row, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"feedback save failed: {e}") from e
        if res.status_code not in (200, 201):
            logger.error(f"feedback save failed ({res.status_code}): {res.text[:200]}")
            raise DatabaseError(f"feedback save failed ({res.status_code})")
        try:
            return res.json()[0]
        except (ValueError, IndexError, KeyError, TypeError):
            return row

    def recent(self, limit: int = 50) -> List[Dict]:
        if not self.remote:
            return list(reversed(self._mem))[:limit]
        try:
            res = requests.get(f"{self.url}/rest/v1/feedback?order=id.desc&limit={int(limit)}", headers=self.headers, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"feedback read failed: {e}") from e
        if res.status_code != 200:
            raise DatabaseError(f"feedback read failed ({res.status_code})")
        return res.json()
