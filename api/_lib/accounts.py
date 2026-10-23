"""
Web accounts + Telegram link login

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
from urllib.parse import parse_qsl

import requests
import http_client as dbhttp

from database import DatabaseError

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
        if len(explicit) < 16 and (os.environ.get("RENDER") or os.environ.get("VERCEL") or os.environ.get("PRODUCTION")):
            logger.warning("AUTH_SECRET is shorter than 16 characters — use a long random value")
        return explicit.encode()
    # stable across restarts/cold starts without extra config: derived from the server-side DB key
    # (a secret the client never sees). The one thing that must never happen is signing tokens with a value that is
    # public in this repository, so production refuses to run without either AUTH_SECRET or SUPABASE_KEY.
    on_prod = bool(os.environ.get("RENDER") or os.environ.get("VERCEL") or os.environ.get("PRODUCTION"))
    if on_prod and not os.environ.get("SUPABASE_KEY"):
        raise RuntimeError("AUTH_SECRET (or SUPABASE_KEY) must be set in production — refusing to sign tokens with the "
                           "built-in development secret")
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


# ── Telegram Mini App identity ───────────────────────────────────────

def verify_webapp_init_data(init_data: Optional[str], bot_token: Optional[str], max_age: int = 86400,
                            now: Optional[float] = None) -> Optional[Dict]:
    """Verify Telegram's signed `initData` (Mini App). Returns {"id", "name", "username"} or None.
    The signature is HMAC-SHA256 over the sorted key=value lines, keyed by HMAC("WebAppData", bot_token)."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        theirs = pairs.pop("hash", None)
        if not theirs:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        mine = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mine, theirs):
            return None
        t = time.time() if now is None else now
        auth_date = int(pairs.get("auth_date", 0))
        if auth_date <= 0 or t - auth_date > max_age or auth_date > t + 300:
            return None
        user = json.loads(pairs["user"])
        return {"id": int(user["id"]),
                "name": str(user.get("first_name") or user.get("username") or "TRAINER")[:40],
                "username": user.get("username")}
    except Exception:
        return None


# ── encounter tokens (a scanned wild Pokémon is "signed" so the client can't invent one) ──

ENCOUNTER_TTL = 10 * 60


def make_encounter_token(user_id: int, species: str, level: int) -> str:
    payload = _b64(json.dumps({"u": user_id, "s": species, "l": int(level), "e": int(time.time()) + ENCOUNTER_TTL,
                               "n": secrets.token_hex(6)},
                              separators=(",", ":")).encode())
    return payload + "." + _b64(hmac.new(_secret(), b"enc|" + payload.encode(), hashlib.sha256).digest())


def verify_encounter_token(token: Optional[str], user_id: int):
    """-> (species, level) for a valid, unexpired token issued to this player, else None."""
    try:
        payload, sig = (token or "").split(".")
        good = _b64(hmac.new(_secret(), b"enc|" + payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(good, sig):
            return None
        d = json.loads(_unb64(payload))
        if int(d["u"]) != int(user_id) or int(d["e"]) < time.time():
            return None
        return str(d["s"]), int(d["l"])
    except Exception:
        return None


def encounter_token_id(token: Optional[str]) -> Optional[str]:
    """A stable id for a token (its signature — unique per token because of the nonce). Used to consume it ONCE:
    the caller records the id with the player's saved state, so a token can't start a second battle."""
    try:
        return (token or "").split(".")[1] or None
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
        res = dbhttp.get(f"{self.url}/rest/v1/accounts?username_lower=eq.{username_lower}",
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
            res = dbhttp.post(f"{self.url}/rest/v1/accounts", headers={**self.headers, "Prefer": "return=minimal"},
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
            res = dbhttp.post(f"{self.url}/rest/v1/login_codes", headers={**self.headers, "Prefer": "return=minimal"},
                                json=row, timeout=15)
            if res.status_code not in (200, 201, 204):
                logger.error(f"login_codes insert failed ({res.status_code}): {res.text[:300]}")
                raise AccountError("Telegram login isn't set up on the server yet — run database/schema.sql.", 503)
        return {"code": code, "expires_in": CODE_TTL}

    def _get_code(self, code: str) -> Optional[Dict]:
        """The code row, or None ONLY when the database answered and there is no such code. A database error
        raises AccountError(503) — an outage must never be reported to the player as "your code expired"."""
        code = (code or "").strip().upper()
        if not code:
            return None
        if not self.remote:
            return self._codes.get(code)
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/login_codes?code=eq.{code}", headers=self.headers, timeout=15)
        except requests.RequestException as e:
            logger.error(f"login_codes lookup failed: {e}")
            raise AccountError("Login service is temporarily unavailable — try again in a moment.", 503) from e
        if res.status_code != 200:
            logger.error(f"login_codes lookup failed ({res.status_code}): {res.text[:200]}")
            raise AccountError("Login service is temporarily unavailable — try again in a moment.", 503)
        rows = res.json()
        return rows[0] if rows else None

    # -- one player across web and Telegram ------------------------------------------------------------

    LINKS_TTL = 30

    def _links(self) -> Dict[int, Dict]:
        """alias_id -> {"user_id", "kind"}. Cached for LINKS_TTL seconds; a stale copy is used if the database
        hiccups, and no copy at all is a DatabaseError (we can't know who a Telegram account plays as)."""
        cache = getattr(self, "_links_cache", None)
        if cache and time.time() - cache[0] < self.LINKS_TTL:
            return cache[1]
        if not self.remote:
            data = getattr(self, "_mem_links", {})
            self._links_cache = (time.time(), data)
            return data
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/identity_links?select=alias_id,user_id,kind",
                               headers=self.headers, timeout=10)
        except requests.RequestException as e:
            if cache:
                return cache[1]
            raise DatabaseError(f"identity links unavailable: {e}") from e
        if res.status_code != 200:
            if res.status_code in (404, 400) and ("identity_links" in (res.text or "") or res.status_code == 404):
                logger.warning("identity_links table missing — account linking is off until schema.sql is run")
                data: Dict[int, Dict] = {}
            elif cache:
                return cache[1]
            else:
                raise DatabaseError(f"identity links unavailable ({res.status_code}): {res.text[:200]}")
        else:
            data = {int(r["alias_id"]): {"user_id": int(r["user_id"]), "kind": r.get("kind", "telegram")} for r in res.json()}
        self._links_cache = (time.time(), data)
        return data

    def forget_links(self) -> None:
        self._links_cache = None

    def canonical(self, user_id: int) -> int:
        """The player this id actually plays as (itself unless it is a linked alias)."""
        link = self._links().get(int(user_id))
        return link["user_id"] if link else int(user_id)

    def is_alias(self, user_id: int) -> bool:
        return int(user_id) in self._links()

    def telegram_for(self, user_id: int) -> Optional[int]:
        """The Telegram account that plays as this web player, if one is linked (for notifications)."""
        for alias, link in self._links().items():
            if link["user_id"] == int(user_id) and link["kind"] == "telegram":
                return alias
        return int(user_id) if int(user_id) < WEB_ID_BASE else None

    def start_link(self, web_user_id: int) -> Dict:
        """A one-time code the logged-in web player sends to the bot (/link CODE) to join the two accounts."""
        if not self.remote:
            raise AccountError("Linking needs the database.", 503)
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        row = {"code": code, "user_id": None, "username": None, "expires_at": int(time.time()) + CODE_TTL,
               "link_user_id": int(web_user_id)}
        try:
            res = dbhttp.post(f"{self.url}/rest/v1/login_codes", headers={**self.headers, "Prefer": "return=minimal"},
                                json=row, timeout=15)
        except requests.RequestException as e:
            raise AccountError("Linking is temporarily unavailable — try again in a moment.", 503) from e
        if res.status_code not in (200, 201, 204):
            logger.error(f"link code insert failed ({res.status_code}): {res.text[:300]}")
            raise AccountError("Linking isn't set up on the server yet — run database/schema.sql.", 503)
        return {"code": code, "expires_in": CODE_TTL}

    def confirm_link(self, code: str, telegram_id: int, tg_name: str, keep: Optional[str] = None) -> Dict:
        """Called by the bot. All the work (checks, archiving the losing side, the link) is ONE database function,
        so a failure can't leave half a merge. -> {"status": ..., ...} (see link_identity in schema.sql)."""
        if not self.remote:
            raise AccountError("Linking needs the database.", 503)
        keep = keep if keep in ("web", "telegram") else None
        try:
            res = dbhttp.post(f"{self.url}/rest/v1/rpc/link_identity", headers=self.headers, timeout=20,
                                json={"p_code": (code or "").strip().upper(), "p_telegram_id": int(telegram_id),
                                      "p_tg_name": (tg_name or "TRAINER")[:40], "p_keep": keep})
        except requests.RequestException as e:
            raise DatabaseError(f"link failed: {e}") from e
        if res.status_code == 404 or "PGRST202" in (res.text or ""):
            raise AccountError("Linking isn't set up on the server yet — run database/schema.sql.", 503)
        if res.status_code != 200:
            logger.error(f"link_identity failed ({res.status_code}): {res.text[:300]}")
            raise DatabaseError(f"link failed ({res.status_code})")
        self.forget_links()
        return res.json()

    def confirm_telegram_login(self, code: str, telegram_id: int, username: str) -> bool:
        """Called by the bot after the user opens the deep link / sends /weblogin CODE. Only the FIRST confirmation
        of a code wins (the update is conditional on nobody having claimed it yet)."""
        code = (code or "").strip().upper()
        row = self._get_code(code)
        if not row or int(row.get("expires_at", 0)) < time.time() or row.get("user_id") or row.get("link_user_id"):
            return False
        # a Telegram account linked to a web player logs in AS that player
        who = self.canonical(telegram_id)
        if who != telegram_id:
            name = self._name_for(who) or username
        else:
            name = username
        if not self.remote:
            row["user_id"], row["username"] = who, name
            return True
        try:
            res = dbhttp.patch(f"{self.url}/rest/v1/login_codes?code=eq.{code}&user_id=is.null",
                                 headers={**self.headers, "Prefer": "return=representation"},
                                 json={"user_id": who, "username": name}, timeout=15)
        except requests.RequestException as e:
            raise AccountError("Login service is temporarily unavailable — try again in a moment.", 503) from e
        if res.status_code not in (200, 204):
            raise AccountError("Login service is temporarily unavailable — try again in a moment.", 503)
        try:
            return bool(res.json())          # empty = someone else claimed it between our read and our write
        except ValueError:
            return res.status_code == 204

    def _name_for(self, user_id: int) -> Optional[str]:
        """The web username of this player, if it has an account."""
        if not self.remote:
            return next((a["username"] for a in self._accounts.values() if a.get("user_id") == user_id), None)
        try:
            res = dbhttp.get(f"{self.url}/rest/v1/accounts?user_id=eq.{int(user_id)}&select=username",
                               headers=self.headers, timeout=10)
            rows = res.json() if res.status_code == 200 else []
        except (requests.RequestException, ValueError):
            return None
        return rows[0]["username"] if rows else None

    def webapp_login(self, init_data: str, bot_token: Optional[str]) -> Dict:
        """Mini App sign-in from VERIFIED initData -> {"user_id", "username"} (the canonical player)."""
        if not bot_token:
            raise AccountError("Telegram sign-in isn't configured on the server.", 503)
        info = verify_webapp_init_data(init_data, bot_token)
        if not info:
            raise AccountError("Telegram couldn't verify that sign-in — reopen the app from the bot.", 401)
        who = self.canonical(info["id"])
        name = (self._name_for(who) if who != info["id"] else None) or info["name"]
        return {"user_id": who, "username": name, "telegram_id": info["id"]}

    def poll_telegram_login(self, code: str) -> Dict:
        row = self._get_code(code)           # raises AccountError(503) on an outage, never "expired"
        if not row or int(row.get("expires_at", 0)) < time.time():
            return {"status": "expired"}
        if not row.get("user_id"):
            return {"status": "pending"}
        # one-time: consume it ATOMICALLY. DELETE ... RETURNING hands the row to exactly one caller; a second
        # concurrent poll gets an empty result and must NOT be logged in.
        c = code.strip().upper()
        if not self.remote:
            if self._codes.pop(c, None) is None:
                return {"status": "expired"}
        else:
            try:
                res = dbhttp.delete(f"{self.url}/rest/v1/login_codes?code=eq.{c}&user_id=not.is.null",
                                      headers={**self.headers, "Prefer": "return=representation"}, timeout=15)
            except requests.RequestException as e:
                raise AccountError("Login service is temporarily unavailable — try again in a moment.", 503) from e
            if res.status_code not in (200, 204):
                raise AccountError("Login service is temporarily unavailable — try again in a moment.", 503)
            try:
                consumed = res.json() if res.status_code == 200 else []
            except ValueError:
                consumed = []
            if not consumed:
                return {"status": "expired"}      # another tab already used this code
            row = consumed[0]
        return {"status": "ok", "user_id": int(row["user_id"]), "username": row.get("username") or "TRAINER"}
