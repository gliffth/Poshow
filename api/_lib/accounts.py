"""
POSHOW — web accounts + Telegram link login

  * username/password accounts ("guest accounts") — password stored as a salted scrypt hash
  * stateless signed tokens (HMAC-SHA256, 30 days) — no session table needed
  * "Continue with Telegram": the web app asks for a one-time code, the bot confirms it,
    the web app polls until confirmed. A Telegram login uses the player's Telegram user id,
    so web and bot share ONE player record (same team, same progress).

Storage: Supabase REST (tables `accounts`, `login_codes` — see database/schema.sql) or, when
Supabase isn't configured, in-memory dicts (local dev only).
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# web accounts live far above the Telegram id space (Telegram ids are < ~1e11) and far below
# JavaScript's safe-integer limit (9e15), so ids survive a JSON round trip in the browser.
WEB_ID_BASE = 10 ** 12
WEB_ID_SPAN = 10 ** 12

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
MIN_PASSWORD = 6
TOKEN_TTL = 30 * 24 * 3600
CODE_TTL = 10 * 60
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O/1/I


class AccountError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# ── passwords ────────────────────────────────────────────────────────

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, maxmem=64 * 1024 * 1024)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = hash_password(password, bytes.fromhex(salt_hex)).split("$")[2]
        return hmac.compare_digest(expected, digest_hex)
    except Exception:
        return False


# ── tokens ───────────────────────────────────────────────────────────

def _secret() -> bytes:
    explicit = os.environ.get("AUTH_SECRET")
    if explicit:
        return explicit.encode()
    # stable across restarts/cold starts without extra config: derived from the server-side DB key
    base = os.environ.get("SUPABASE_KEY") or "poshow-dev-only-secret"
    return hashlib.sha256(("poshow-auth|" + base).encode()).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user_id: int, username: str) -> str:
    payload = _b64(json.dumps({"uid": user_id, "name": username, "exp": int(time.time()) + TOKEN_TTL},
                              separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: Optional[str]) -> Optional[Dict]:
    """Returns {"uid", "name"} for a valid, unexpired token, else None."""
    if not token:
        return None
    if token.lower().startswith("bearer "):
        token = token[7:]
    try:
        payload, sig = token.strip().split(".")
        expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig):
            return None
        data = json.loads(_unb64(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        return {"uid": int(data["uid"]), "name": str(data.get("name", ""))}
    except Exception:
        return None


# ── service ──────────────────────────────────────────────────────────

class AccountService:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url
        self.headers = ({"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                        if url and key else None)
        self._accounts: Dict[str, Dict] = {}     # memory mode: username_lower -> row
        self._codes: Dict[str, Dict] = {}        # memory mode: code -> row
        self._failures: Dict[str, list] = {}     # username_lower -> [timestamps], login throttling

    @property
    def remote(self) -> bool:
        return self.headers is not None

    # -- accounts --

    def _get_account(self, username_lower: str) -> Optional[Dict]:
        if not self.remote:
            return self._accounts.get(username_lower)
        res = requests.get(f"{self.url}/rest/v1/accounts?username_lower=eq.{username_lower}",
                           headers=self.headers, timeout=15)
        if res.status_code != 200:
            raise AccountError(self._schema_hint(res), 503)
        rows = res.json()
        return rows[0] if rows else None

    @staticmethod
    def _schema_hint(res) -> str:
        logger.error(f"accounts table error ({res.status_code}): {res.text[:300]}")
        return ("Accounts aren't set up on the server yet — run database/schema.sql "
                "(the `accounts` table is missing).")

    def create_account(self, username: str, password: str) -> Dict:
        username = (username or "").strip()
        if not USERNAME_RE.match(username):
            raise AccountError("Username must be 3-20 characters: letters, numbers, underscore.")
        if len(password or "") < MIN_PASSWORD:
            raise AccountError(f"Password must be at least {MIN_PASSWORD} characters.")
        lower = username.lower()
        if self._get_account(lower):
            raise AccountError("That username is taken.", 409)

        user_id = WEB_ID_BASE + secrets.randbelow(WEB_ID_SPAN)
        row = {"username": username, "username_lower": lower,
               "password_hash": hash_password(password), "user_id": user_id}
        if not self.remote:
            self._accounts[lower] = row
        else:
            res = requests.post(f"{self.url}/rest/v1/accounts", headers={**self.headers, "Prefer": "return=minimal"},
                                json=row, timeout=15)
            if res.status_code == 409:
                raise AccountError("That username is taken.", 409)
            if res.status_code not in (200, 201, 204):
                raise AccountError(self._schema_hint(res), 503)
        return {"user_id": user_id, "username": username}

    def authenticate(self, username: str, password: str) -> Dict:
        lower = (username or "").strip().lower()
        now = time.time()
        recent = [t for t in self._failures.get(lower, []) if now - t < 600]
        if len(recent) >= 8:
            raise AccountError("Too many failed attempts — wait a few minutes and try again.", 429)

        row = self._get_account(lower)
        if not row or not verify_password(password or "", row.get("password_hash", "")):
            recent.append(now)
            self._failures[lower] = recent
            raise AccountError("Wrong username or password.", 401)
        self._failures.pop(lower, None)
        return {"user_id": int(row["user_id"]), "username": row["username"]}

    # -- telegram login codes --

    def start_telegram_login(self) -> Dict:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        row = {"code": code, "user_id": None, "username": None, "expires_at": int(time.time()) + CODE_TTL}
        if not self.remote:
            self._codes[code] = row
        else:
            res = requests.post(f"{self.url}/rest/v1/login_codes", headers={**self.headers, "Prefer": "return=minimal"},
                                json=row, timeout=15)
            if res.status_code not in (200, 201, 204):
                logger.error(f"login_codes insert failed ({res.status_code}): {res.text[:300]}")
                raise AccountError("Telegram login isn't set up on the server yet — run database/schema.sql.", 503)
        return {"code": code, "expires_in": CODE_TTL}

    def _get_code(self, code: str) -> Optional[Dict]:
        code = (code or "").strip().upper()
        if not code:
            return None
        if not self.remote:
            return self._codes.get(code)
        res = requests.get(f"{self.url}/rest/v1/login_codes?code=eq.{code}", headers=self.headers, timeout=15)
        if res.status_code != 200:
            return None
        rows = res.json()
        return rows[0] if rows else None

    def confirm_telegram_login(self, code: str, telegram_id: int, username: str) -> bool:
        """Called by the bot after the user opens the deep link / sends /weblogin CODE."""
        code = (code or "").strip().upper()
        row = self._get_code(code)
        if not row or int(row.get("expires_at", 0)) < time.time() or row.get("user_id"):
            return False
        if not self.remote:
            row["user_id"], row["username"] = telegram_id, username
            return True
        res = requests.patch(f"{self.url}/rest/v1/login_codes?code=eq.{code}",
                             headers={**self.headers, "Prefer": "return=minimal"},
                             json={"user_id": telegram_id, "username": username}, timeout=15)
        return res.status_code in (200, 204)

    def poll_telegram_login(self, code: str) -> Dict:
        row = self._get_code(code)
        if not row or int(row.get("expires_at", 0)) < time.time():
            return {"status": "expired"}
        if not row.get("user_id"):
            return {"status": "pending"}
        # one-time: consume it so the code can't be replayed
        c = code.strip().upper()
        if not self.remote:
            self._codes.pop(c, None)
        else:
            requests.delete(f"{self.url}/rest/v1/login_codes?code=eq.{c}", headers=self.headers, timeout=15)
        return {"status": "ok", "user_id": int(row["user_id"]), "username": row.get("username") or "TRAINER"}
