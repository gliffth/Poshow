"""
Tiny JSON-document store for turn-based shared state (PvP matches, trades).

Rows look like {"id", "a", "b", "status", "state", "ts"}. Supabase tables `pvp_matches` and `trades`
(see database/schema.sql) in production, plain dicts when Supabase isn't configured (local dev).
The same code serves the website and the Telegram bot, so a Telegram player and a web player can share
one match or trade.
"""

import logging
import time
from typing import Dict, List, Optional

import requests
import http_client as dbhttp

from database import DatabaseError

logger = logging.getLogger(__name__)


class DocStore:
    def __init__(self, table: str, url: Optional[str] = None, key: Optional[str] = None):
        self.table = table
        self.url = url
        self.headers = ({"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                        if url and key else None)
        self._mem: Dict[str, Dict] = {}

    @property
    def remote(self) -> bool:
        return self.headers is not None

    def _row(self, doc: Dict) -> Dict:
        return {"id": doc["id"], "user_a": doc["a"], "user_b": doc["b"], "status": doc["status"],
                "state": doc["state"], "ts": int(doc.get("ts") or time.time())}

    def atomic_row(self, doc: Dict) -> Dict:
        """The table row for `doc`, to be written INSIDE a multi-player transaction (see save_players_atomic)."""
        doc["ts"] = int(time.time())
        return self._row(doc)

    @staticmethod
    def _doc(row: Dict) -> Dict:
        return {"id": row["id"], "a": int(row["user_a"]), "b": int(row["user_b"]), "status": row["status"],
                "state": row["state"], "ts": int(row.get("ts") or 0)}

    def save(self, doc: Dict) -> bool:
        """True when stored. Raises DatabaseError when it was NOT — an invitation, turn or trade must never look
        accepted when its state was never written."""
        doc["ts"] = int(time.time())
        if not self.remote:
            self._mem[doc["id"]] = {**doc, "state": __import__("json").loads(__import__("json").dumps(doc["state"]))}
            return True
        try:
            res = dbhttp.post(f"{self.url}/rest/v1/{self.table}?on_conflict=id",
                                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                                json=self._row(doc), timeout=15)
            if res.status_code not in (200, 201, 204):
                logger.error(f"❌ {self.table} save failed ({res.status_code}): {res.text[:300]}")
                raise DatabaseError(f"{self.table} save failed ({res.status_code}): {res.text[:200]}")
            return True
        except requests.RequestException as e:
            logger.error(f"{self.table} save error: {e}")
            raise DatabaseError(f"{self.table} save failed: {e}") from e

    def load(self, doc_id: str) -> Optional[Dict]:
        if not self.remote:
            d = self._mem.get(doc_id)
            return __import__("json").loads(__import__("json").dumps(d)) if d else None
        """None means "no such document" — and only that. A database error raises DatabaseError instead of
        pretending the duel/trade doesn't exist."""
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/{self.table}", params={"id": f"eq.{doc_id}", "select": "*"},
                               headers=self.headers, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"{self.table} load failed: {e}") from e
        if res.status_code != 200:
            logger.error(f"{self.table} load failed ({res.status_code}): {res.text[:200]}")
            raise DatabaseError(f"{self.table} load failed ({res.status_code}): {res.text[:200]}")
        rows = res.json()
        return self._doc(rows[0]) if rows else None

    def for_user(self, user_id: int, statuses: Optional[List[str]] = None, max_age_s: int = 86400) -> List[Dict]:
        since = int(time.time()) - max_age_s
        if not self.remote:
            out = [d for d in self._mem.values()
                   if user_id in (d["a"], d["b"]) and d["ts"] >= since and (not statuses or d["status"] in statuses)]
            return __import__("json").loads(__import__("json").dumps(out))
        params = {"or": f"(user_a.eq.{user_id},user_b.eq.{user_id})", "ts": f"gte.{since}", "select": "*"}
        if statuses:
            params["status"] = f"in.({','.join(statuses)})"
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/{self.table}", params=params, headers=self.headers, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"{self.table} list failed: {e}") from e
        if res.status_code != 200:
            logger.error(f"{self.table} list failed ({res.status_code}): {res.text[:200]}")
            raise DatabaseError(f"{self.table} list failed ({res.status_code}): {res.text[:200]}")
        return [self._doc(r) for r in res.json()]

    def delete(self, doc_id: str) -> None:
        if not self.remote:
            self._mem.pop(doc_id, None)
            return
        try:
            res = dbhttp.delete(f"{self.url}/rest/v1/{self.table}?id=eq.{doc_id}", headers=self.headers, timeout=15)
        except requests.RequestException as e:
            raise DatabaseError(f"{self.table} delete failed: {e}") from e
        if res.status_code not in (200, 204):
            raise DatabaseError(f"{self.table} delete failed ({res.status_code}): {res.text[:200]}")
