"""
In-app information panel content (guide, changelog, links) and community ideas with votes.

Content documents live in `site_content` (defaults ship in code, so the panel works before anyone edits it).
Ideas live in `ideas` / `idea_votes`; the vote toggle is the SQL function `toggle_idea_vote`. Both fall back to
plain dicts when Supabase isn't configured.
"""

import json
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
import http_client as dbhttp

from database import DatabaseError

ICONS = ("book", "map", "sword", "ball", "backpack", "users", "star", "scroll", "shield", "bug", "link", "sparkles",
         "shopping", "handshake", "message", "trophy", "heart", "compass", "flame", "zap")
CONTENT_KEYS = ("guide", "changelog", "links")
CHANGE_KINDS = ("new", "improved", "fixed", "known")
MAX_CONTENT_BYTES = 60 * 1024

STATUSES = ("pending", "under_consideration", "planned", "in_development", "implemented", "declined", "archived")
VOTABLE = ("under_consideration", "planned", "in_development")
HIDDEN = ("pending", "archived")
STATUS_LABELS = {
    "pending": "Waiting for review", "under_consideration": "Under consideration", "planned": "Planned",
    "in_development": "In development", "implemented": "Implemented", "declined": "Declined", "archived": "Archived",
}
STATUS_ORDER = ("in_development", "planned", "under_consideration", "implemented", "declined")
TITLE_MIN, TITLE_MAX, BODY_MAX = 6, 80, 600
PER_DAY = 3
DUPLICATE_OVERLAP = 0.8

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]*)\)")
_SLUG_BAD = re.compile(r"[^a-z0-9_-]+")


class CommunityError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def clean_text(text, limit: int, multiline: bool = False) -> str:
    text = _CTRL.sub("", text if isinstance(text, str) else "")
    if not multiline:
        text = re.sub(r"\s+", " ", text)
    return text.strip()[:limit]


# ── default documents ──

DEFAULT_GUIDE = {"sections": [
    {"id": "what-is-poshow", "title": "What POSHOW is", "icon": "book",
     "body": "POSHOW is a Pokémon-inspired adventure that runs in your browser and in Telegram. Both use the same "
             "account, so you can start on one and carry on from the other."},
    {"id": "starting-out", "title": "Starting out", "icon": "compass",
     "body": "Create an account, pick a starter, and head out. Your progress is saved on the server, not on your device."},
    {"id": "journey", "title": "The journey", "icon": "map",
     "body": "A map of towns and routes with wild encounters, trainers, a rival, eight gyms, the Elite Four and a Champion.\n\n"
             "> Campaigns exist for Kanto, Johto, Hoenn and Kalos. The other regions are free-roam scouting only."},
    {"id": "battles", "title": "Battles", "icon": "sword",
     "body": "Choose Fight, Bag, Switch or Run.\n\n- Using an item costs your turn.\n- Switching costs your turn.\n"
             "- A failed escape costs your turn.\n\nType matchups, STAB, critical hits, status conditions, natures, IVs and EVs all apply."},
    {"id": "catching", "title": "Catching", "icon": "ball",
     "body": "Throw a ball at a wild Pokémon. A weakened target with a status condition is easier to catch. "
             "Better balls help, and every ball you throw is used up."},
    {"id": "your-team", "title": "Your team", "icon": "users",
     "body": "Your team holds the Pokémon you battle with. The rest wait in storage. Move them between the two from the Storage screen."},
    {"id": "evolution", "title": "Evolution", "icon": "sparkles",
     "body": "Pokémon evolve by level, by evolution stone, or by trade with a Trade Cable."},
    {"id": "items-and-shop", "title": "Items and shop", "icon": "shopping",
     "body": "Spend coins on balls, potions, EXP All and Rare Candy. A held item can be given to a Pokémon from its page."},
    {"id": "quests-and-bosses", "title": "Quests and bosses", "icon": "scroll",
     "body": "The quest board lists goals with rewards you claim yourself. The daily boss and the endless Battle Gym give extra rewards."},
    {"id": "trading-market-duels", "title": "Trading, market and duels", "icon": "handshake",
     "body": "Trade Pokémon with another player, list one on the market for coins, or challenge someone to a duel."},
    {"id": "telegram-and-account", "title": "Telegram and your account", "icon": "message",
     "body": "Link your web account to Telegram from your profile to play from both. Use the login code from the bot to sign in on the web."},
    {"id": "something-wrong", "title": "Something wrong?", "icon": "bug",
     "body": "Send a report from Settings. If the server seems slow, give it a moment: it may have been asleep."},
]}

DEFAULT_CHANGELOG = {
    "version": "0.20",
    "entries": [{"version": "0.20", "date": "", "title": "Safer purchases and a clearer connection",
                 "items": [{"kind": "new", "text": "An information panel with a guide, updates and community ideas."},
                           {"kind": "new", "text": "A connection indicator that tells slow apart from unreachable."},
                           {"kind": "improved", "text": "A purchase or battle action that gets no answer is retried safely and never charged twice."}]}],
    "upcoming": [],
    "known": [],
}

DEFAULT_LINKS = {"repo": ""}

DEFAULTS = {"guide": DEFAULT_GUIDE, "changelog": DEFAULT_CHANGELOG, "links": DEFAULT_LINKS}


# ── content validation ──

def _check_markup(body: str) -> None:
    for url in _MD_LINK.findall(body):
        if not url.strip().startswith("https://"):
            raise CommunityError("Links must start with https://")


def _clean_guide(value: Dict) -> Dict:
    sections = value.get("sections") if isinstance(value, dict) else None
    if not isinstance(sections, list) or not 1 <= len(sections) <= 30:
        raise CommunityError("A guide needs between 1 and 30 sections.")
    out, seen = [], set()
    for i, s in enumerate(sections, 1):
        if not isinstance(s, dict):
            raise CommunityError(f"Section {i} is not valid.")
        title = clean_text(s.get("title"), 80)
        body = clean_text(s.get("body"), 4000, multiline=True)
        if not title:
            raise CommunityError(f"Section {i} needs a title.")
        sid = _SLUG_BAD.sub("-", clean_text(s.get("id") or title, 60).lower()).strip("-")
        if not sid:
            raise CommunityError(f"Section {i} needs an id.")
        if sid in seen:
            raise CommunityError(f"Two sections share the id '{sid}'.")
        seen.add(sid)
        _check_markup(body)
        icon = s.get("icon") if s.get("icon") in ICONS else "book"
        out.append({"id": sid, "title": title, "icon": icon, "body": body})
    return {"sections": out}


def _clean_lines(raw, what: str, limit: int = 30, size: int = 200) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > limit:
        raise CommunityError(f"'{what}' must be a list of at most {limit} lines.")
    return [t for t in (clean_text(x, size) for x in raw) if t]


def _clean_changelog(value: Dict) -> Dict:
    if not isinstance(value, dict):
        raise CommunityError("The changelog is not valid.")
    version = clean_text(value.get("version"), 20)
    if not version:
        raise CommunityError("The changelog needs a version.")
    raw = value.get("entries", [])
    if not isinstance(raw, list) or len(raw) > 50:
        raise CommunityError("A changelog holds at most 50 entries.")
    entries = []
    for i, e in enumerate(raw, 1):
        if not isinstance(e, dict):
            raise CommunityError(f"Entry {i} is not valid.")
        items = e.get("items", [])
        if not isinstance(items, list) or len(items) > 30:
            raise CommunityError(f"Entry {i} holds at most 30 items.")
        clean_items = []
        for it in items:
            kind = it.get("kind") if isinstance(it, dict) else None
            if kind not in CHANGE_KINDS:
                raise CommunityError(f"Entry {i}: each item must be one of {', '.join(CHANGE_KINDS)}.")
            text = clean_text(it.get("text"), 300)
            if text:
                clean_items.append({"kind": kind, "text": text})
        entries.append({"version": clean_text(e.get("version"), 20), "date": clean_text(e.get("date"), 20),
                        "title": clean_text(e.get("title"), 80), "items": clean_items})
    return {"version": version, "entries": entries,
            "upcoming": _clean_lines(value.get("upcoming"), "upcoming"), "known": _clean_lines(value.get("known"), "known")}


def _clean_links(value: Dict) -> Dict:
    repo = clean_text(value.get("repo") if isinstance(value, dict) else "", 300)
    if repo and not (repo.startswith("https://") and " " not in repo):
        raise CommunityError("The repository link must start with https://")
    return {"repo": repo}


_CLEANERS = {"guide": _clean_guide, "changelog": _clean_changelog, "links": _clean_links}


def clean_content(key: str, value) -> Dict:
    if key not in _CLEANERS:
        raise CommunityError("Unknown content key.", 404)
    cleaned = _CLEANERS[key](value)
    if len(json.dumps(cleaned, ensure_ascii=False).encode("utf-8")) > MAX_CONTENT_BYTES:
        raise CommunityError("That is too long. Keep it under 60 KB.")
    return cleaned


# ── idea rules ──

def normalise_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def _words(title: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (title or "").lower()))


def is_duplicate(title: str, other: str) -> bool:
    a, b = normalise_title(title), normalise_title(other)
    if a and a == b:
        return True
    wa, wb = _words(title), _words(other)
    if len(wa) < 3 or len(wb) < 3:
        return False
    return len(wa & wb) / len(wa | wb) >= DUPLICATE_OVERLAP


def clean_idea(title, body) -> tuple:
    title, body = clean_text(title, 400), clean_text(body, 4000, multiline=True)
    if len(title) < TITLE_MIN:
        raise CommunityError(f"Give the idea a title of at least {TITLE_MIN} characters.")
    if len(title) > TITLE_MAX:
        raise CommunityError(f"Keep the title under {TITLE_MAX} characters.")
    if len(body) > BODY_MAX:
        raise CommunityError(f"Keep the description under {BODY_MAX} characters.")
    return title, body


def idea_view(row: Dict, uid: Optional[int], voted: set) -> Dict:
    status = row.get("status") or "pending"
    return {"id": row["id"], "title": row["title"], "body": row.get("body") or "", "status": status,
            "status_label": STATUS_LABELS.get(status, status), "votes": int(row.get("votes") or 0),
            "voted": row["id"] in voted, "mine": uid is not None and row.get("user_id") == uid,
            "votable": status in VOTABLE}


def sort_ideas(items: List[Dict]) -> List[Dict]:
    def rank(i: Dict):
        if i["status"] == "pending":
            return (-1, 0)
        return (STATUS_ORDER.index(i["status"]), -i["votes"])
    return sorted(items, key=rank)


def _age_seconds(ts) -> float:
    if isinstance(ts, (int, float)):
        return time.time() - ts
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return time.time() - dt.timestamp()
    except ValueError:
        return 0.0


# ── storage ──

class CommunityStore:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.remote = bool(url and key)
        self.url = url
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"} if key else {}
        self._lock = threading.Lock()
        self._content: Dict[str, Dict] = {}
        self._ideas: List[Dict] = []
        self._votes: set = set()

    def _call(self, method: str, path: str, **kw):
        try:
            res = getattr(dbhttp, method)(f"{self.url}/rest/v1/{path}", headers={**self.headers, **kw.pop("headers", {})},
                                          timeout=15, **kw)
        except requests.RequestException as e:
            raise DatabaseError(f"community {method} failed: {e}") from e
        return res

    def _ok(self, res, what: str, codes=(200, 201, 204)):
        if res.status_code not in codes:
            raise DatabaseError(f"{what} failed ({res.status_code})")
        return res

    # content
    def content_all(self) -> Dict[str, Dict]:
        if not self.remote:
            return dict(self._content)
        res = self._ok(self._call("get", "site_content?select=key,value"), "content read", (200,))
        return {r["key"]: r["value"] for r in res.json() if r.get("key") in CONTENT_KEYS}

    def content_put(self, key: str, value: Dict, admin_id: int) -> None:
        if not self.remote:
            self._content[key] = value
            return
        row = {"key": key, "value": value, "updated_by": admin_id, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self._ok(self._call("post", "site_content?on_conflict=key", json=row,
                            headers={"Prefer": "resolution=merge-duplicates,return=minimal"}), "content save")

    def content_delete(self, key: str) -> None:
        if not self.remote:
            self._content.pop(key, None)
            return
        self._ok(self._call("delete", f"site_content?key=eq.{key}"), "content reset")

    # ideas
    def ideas_visible(self, uid: Optional[int]) -> List[Dict]:
        if not self.remote:
            return [dict(r) for r in self._ideas if r["status"] not in HIDDEN or (r["status"] == "pending" and uid is not None and r["user_id"] == uid)]
        cols = "id,user_id,title,body,status,votes"
        rows = self._ok(self._call("get", f"ideas?select={cols}&status=not.in.(pending,archived)&limit=500"), "ideas read", (200,)).json()
        if uid is not None:
            rows += self._ok(self._call("get", f"ideas?select={cols}&status=eq.pending&user_id=eq.{uid}&limit=50"), "ideas read", (200,)).json()
        return rows

    def idea_get(self, idea_id: int) -> Optional[Dict]:
        if not self.remote:
            return next((dict(r) for r in self._ideas if r["id"] == idea_id), None)
        rows = self._ok(self._call("get", f"ideas?select=id,user_id,username,title,body,status,votes&id=eq.{int(idea_id)}"),
                        "idea read", (200,)).json()
        return rows[0] if rows else None

    def my_votes(self, uid: int) -> set:
        if not self.remote:
            return {i for (i, u) in self._votes if u == uid}
        rows = self._ok(self._call("get", f"idea_votes?select=idea_id&user_id=eq.{int(uid)}&limit=1000"), "votes read", (200,)).json()
        return {r["idea_id"] for r in rows}

    def idea_add(self, uid: int, username: Optional[str], title: str, body: str) -> Dict:
        with self._lock:
            mine_recent, others = 0, []
            for r in self._all_for_checks(uid):
                if r["user_id"] == uid and _age_seconds(r.get("created_at") or time.time()) < 86400:
                    mine_recent += 1
                if r["status"] not in HIDDEN or r["user_id"] == uid:
                    others.append(r["title"])
            if mine_recent >= PER_DAY:
                raise CommunityError("That's the limit for today. Try again tomorrow.", 429)
            if any(is_duplicate(title, t) for t in others):
                raise CommunityError("An idea like that already exists. Vote for it instead.", 409)
            row = {"user_id": uid, "username": clean_text(username, 40) or None, "title": title, "body": body, "status": "pending", "votes": 0}
            if not self.remote:
                row["id"] = len(self._ideas) + 1
                row["created_at"] = time.time()
                self._ideas.append(row)
                return dict(row)
            res = self._ok(self._call("post", "ideas", json=row, headers={"Prefer": "return=representation"}), "idea save")
            try:
                return res.json()[0]
            except (ValueError, IndexError, KeyError, TypeError):
                return row

    def _all_for_checks(self, uid: int) -> List[Dict]:
        if not self.remote:
            return self._ideas
        return self._ok(self._call("get", "ideas?select=id,user_id,title,status,created_at&limit=1000"), "ideas read", (200,)).json()

    def idea_vote(self, idea_id: int, uid: int) -> Dict:
        if not self.remote:
            with self._lock:
                row = next((r for r in self._ideas if r["id"] == idea_id), None)
                if row is None:
                    raise CommunityError("No such idea.", 404)
                if row["status"] not in VOTABLE:
                    raise CommunityError("Voting is closed for this idea.", 409)
                key = (idea_id, uid)
                voted = key not in self._votes
                (self._votes.add if voted else self._votes.discard)(key)
                row["votes"] = sum(1 for (i, _) in self._votes if i == idea_id)
                return {"voted": voted, "votes": row["votes"]}
        res = self._call("post", "rpc/toggle_idea_vote", json={"p_idea": int(idea_id), "p_user": int(uid)})
        if res.status_code == 200:
            return res.json()
        text = res.text or ""
        if "unknown_idea" in text:
            raise CommunityError("No such idea.", 404)
        if "voting_closed" in text:
            raise CommunityError("Voting is closed for this idea.", 409)
        raise DatabaseError(f"vote failed ({res.status_code})")

    def ideas_admin(self, limit: int = 300) -> List[Dict]:
        if not self.remote:
            return [dict(r) for r in reversed(self._ideas)][:limit]
        return self._ok(self._call("get", f"ideas?select=id,user_id,username,title,body,status,votes,created_at&order=id.desc&limit={int(limit)}"),
                        "ideas read", (200,)).json()

    def idea_update(self, idea_id: int, fields: Dict) -> Optional[Dict]:
        if not self.remote:
            row = next((r for r in self._ideas if r["id"] == idea_id), None)
            if row is None:
                return None
            row.update(fields)
            return dict(row)
        fields = {**fields, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        res = self._ok(self._call("patch", f"ideas?id=eq.{int(idea_id)}", json=fields, headers={"Prefer": "return=representation"}),
                       "idea update", (200,))
        rows = res.json()
        return rows[0] if rows else None
