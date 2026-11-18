"""
PvP — turn-based trainer battles, shared by the website and the Telegram bot.

One engine runs every format (see pvp_formats.py). Flow: challenge or matchmaking queue -> both bring Pokémon ->
team preview (when more are brought than used) -> both pick a move or a switch each turn -> the turn resolves when
both have chosen -> a fainted Pokémon forces a switch -> the last trainer standing wins. Your real Pokémon are never
touched: a battle uses copies, so there is no injury, no condition loss and no XP.

The old "classic" duel (the first three healthy Pokémon, no preview) is kept for the Telegram bot.

State is a JSON document (see doc_store.py):
  sides.a / sides.b : {uid, name, team: [pokemon dicts], active, choice, picked, last_rid}
  phase             : "preview" | "choose" (both pick) | "switch" (a fainted side must pick) | "done"
  seq               : bumped on every change, so clients (and the long poll) can tell what is new
"""

import random
import time
import uuid
from typing import Dict, List, Optional, Tuple

import care
import pvp_formats as F
from battle_system import BattleSystem, Move
from doc_store import DocStore
from pokemon_model import PokemonInstance

TEAM_SIZE = 3
QUEUE_TTL = 10 * 60
HISTORY_KEEP = 20
REPEAT_WINDOW = 24 * 3600
MAX_PRESETS = 10
REPEAT_LIMIT = 3                # after this many rated games against one opponent in a day, ratings stop moving
INVITE_TTL = 15 * 60            # an unanswered challenge expires
TURN_TIMEOUT = 5 * 60           # a trainer who stops answering can be beaten by walkover
K_FACTOR = 32


class PvpError(ValueError):
    pass


def new_store(url=None, key=None) -> DocStore:
    return DocStore("pvp_matches", url, key)


# ── helpers ─────────────────────────────────────────────────────────

def _mon(d: Dict) -> PokemonInstance:
    return PokemonInstance.from_dict(d)


def _alive(side: Dict) -> List[int]:
    return [i for i, m in enumerate(side["team"]) if m["current_hp"] > 0]


def pick_team(player) -> List[Dict]:
    """First three healthy Pokémon on the team, at their current HP and level."""
    team = [m for m in player.active_team if m.current_hp > 0 and not m.is_fainted][:TEAM_SIZE]
    out = []
    for m in team:
        m.bt = None
        d = m.to_dict()
        d["bt"] = None
        out.append(d)
    return out


def _side(player, team: List[Dict]) -> Dict:
    return {"uid": player.user_id, "name": (player.username or "Trainer")[:20], "team": team, "active": 0,
            "choice": None, "ready_at": int(time.time())}


def _key(doc: Dict, uid: int) -> str:
    if uid == doc["a"]:
        return "a"
    if uid == doc["b"]:
        return "b"
    raise PvpError("You're not part of this match.")


def _other(k: str) -> str:
    return "b" if k == "a" else "a"


# ── lifecycle ───────────────────────────────────────────────────────

def clean_name(name: str) -> str:
    name = " ".join(str(name or "").split())[:24]
    if not name:
        raise PvpError("Give the team a name.")
    return name


def _fmt(st: Dict) -> F.Format:
    return F.from_state(st["format"]) if st.get("format") else F.get("classic")


def _check(fn, *a, **k):
    try:
        return fn(*a, **k)
    except F.FormatError as e:
        raise PvpError(str(e)) from None


def challenge(store: DocStore, challenger, opponent_id: int, opponent_name: str,
              format_id: str = "classic", ids: Optional[List[str]] = None, rules: Optional[Dict] = None) -> Dict:
    if opponent_id == challenger.user_id:
        raise PvpError("You can't challenge yourself.")
    fmt = _check(F.get, format_id)
    if not fmt.legacy:
        if fmt.id != "friendly":
            raise PvpError("Rated formats are played through the matchmaking queue.")
        fmt = _check(F.with_rules, fmt, rules)
        _check(F.check_selection, challenger, fmt, ids or [])
    elif not pick_team(challenger):
        raise PvpError("You need at least one healthy Pokémon on your team to duel.")
    for d in store.for_user(challenger.user_id, ["pending", "active"]):
        if d["status"] == "active":
            raise PvpError("Finish your current duel first.")
        if d["status"] == "pending" and d["a"] == challenger.user_id and d["b"] == opponent_id \
                and time.time() - d["ts"] < INVITE_TTL:
            raise PvpError(f"You already challenged {opponent_name}.")
    doc = {"id": uuid.uuid4().hex[:12], "a": challenger.user_id, "b": opponent_id, "status": "pending",
           "state": {"names": {"a": challenger.username, "b": opponent_name}, "log": [], "seq": 1}}
    if not fmt.legacy:
        doc["state"].update({"format": fmt.public(), "brought": {"a": list(ids)}})
    store.save(doc)
    return doc


def respond(store: DocStore, match_id: str, player, accept: bool, ids: Optional[List[str]] = None) -> Dict:
    doc = store.load(match_id)
    if not doc or doc["b"] != player.user_id:
        raise PvpError("That challenge isn't for you.")
    if doc["status"] != "pending":
        raise PvpError("That challenge is no longer open.")
    if time.time() - doc["ts"] > INVITE_TTL:
        doc["status"] = "expired"
        store.save(doc)
        raise PvpError("That challenge expired.")
    if not accept:
        doc["status"] = "declined"
        store.save(doc)
        return doc
    for d in store.for_user(player.user_id, ["active"]):
        raise PvpError("Finish your current duel first.")
    st = doc["state"]
    if st.get("format"):
        _check(F.check_selection, player, _fmt(st), ids or [])
        st["brought"]["b"] = list(ids)
        store.save(doc)
    return doc


def _build(doc: Dict, a_player, b_player) -> None:
    """Fill in the battle state for a match whose two sides have brought their Pokémon."""
    st = doc["state"]
    fmt = _fmt(st)
    now = int(time.time())
    if fmt.legacy:
        ta, tb = pick_team(a_player), pick_team(b_player)
        if not ta or not tb:
            raise PvpError("Both trainers need a healthy Pokémon.")
        sides = {"a": _side(a_player, ta), "b": _side(b_player, tb)}
        phase = "choose"
    else:
        sides = {}
        for k, player in (("a", a_player), ("b", b_player)):
            chosen = _check(F.check_selection, player, fmt, st["brought"][k])
            sides[k] = _side(player, [F.battle_copy(fmt, m) for m in chosen])
            sides[k]["picked"] = len(chosen) <= fmt.pick
            if sides[k]["picked"]:
                sides[k]["team"] = sides[k]["team"][:fmt.pick]
        phase = "choose" if all(sides[k]["picked"] for k in "ab") else "preview"
    names = st.get("names") or {}
    doc["status"] = "active"
    doc["state"] = {**{k: v for k, v in st.items() if k in ("format", "brought")}, "names": names, "sides": sides,
                    "turn": 1, "phase": phase, "seq": st.get("seq", 0) + 1, "winner": None, "last_move_at": now,
                    "log": [f"{a_player.username} and {b_player.username} face off!"]
                           + (["Team preview: choose who to bring."] if phase == "preview" else [])}


def start(store: DocStore, match_id: str, a_player, b_player) -> Dict:
    """Both trainers loaded -> build the duel."""
    doc = store.load(match_id)
    _build(doc, a_player, b_player)
    store.save(doc)
    return doc


# ── choices ─────────────────────────────────────────────────────────

def _deadline(doc: Dict) -> Optional[int]:
    st = doc["state"]
    if doc["status"] != "active" or "sides" not in st:
        return None
    fmt = _fmt(st)
    return max(0, int(st.get("last_move_at", 0) + (fmt.turn_timer if not fmt.legacy else TURN_TIMEOUT) - time.time()))


def view(doc: Dict, uid: int) -> Dict:
    """What one trainer is allowed to see (never the other side's pending choice or hidden moves)."""
    me = _key(doc, uid)
    st = doc["state"]
    if doc["status"] in ("pending", "queued"):
        fmt = st.get("format")
        return {"id": doc["id"], "status": doc["status"], "you": me, "names": st.get("names", {}), "log": [],
                "seq": st.get("seq", 0), "format": fmt and {k: fmt[k] for k in ("id", "name", "bring", "pick", "level_cap", "turn_timer", "rated")}}
    sides = st["sides"]
    fmt = _fmt(st)
    other = _other(me)
    preview = st["phase"] == "preview"

    def pub(k, hidden: bool):
        s = sides[k]
        team = []
        for m in s["team"]:
            row = {"species": m["species_name"], "nickname": m["nickname"], "level": m["level"],
                   "hp": m["current_hp"], "max_hp": m["max_hp"], "status": m.get("status"),
                   "dex_id": (m.get("api_data") or {}).get("id")}
            if not hidden:
                row["moves"] = [{"id": mv, "pp": (m.get("bt") or {}).get("pp", {}).get(mv.lower().replace("_", "-"))} for mv in m["moves"]]
                row["ability"] = m.get("ability")
                row["held_item"] = m.get("held_item")
            else:
                row["moves"] = []
                if preview:
                    row = {"species": row["species"], "level": row["level"], "dex_id": row["dex_id"], "moves": []}
            team.append(row)
        return {"name": s["name"], "active": s["active"], "chosen": s["choice"] is not None, "picked": bool(s.get("picked", True)),
                "team": team}

    mine = sides[me]
    needs_switch = st["phase"] == "switch" and mine["team"][mine["active"]]["current_hp"] <= 0
    return {"id": doc["id"], "status": doc["status"], "you": me, "turn": st["turn"], "phase": st["phase"],
            "winner": st["winner"], "log": st["log"][-12:], "seq": st.get("seq", 0),
            "format": {k: getattr(fmt, k) for k in ("id", "name", "bring", "pick", "level_cap", "turn_timer", "rated")},
            "me": pub(me, False), "foe": pub(other, True), "deadline": _deadline(doc),
            "waiting": (mine["choice"] is not None or (preview and bool(mine.get("picked")))) and st["phase"] != "done",
            "needs_pick": preview and not mine.get("picked"),
            "needs_switch": needs_switch, "elo": st.get("elo")}


def submit(store: DocStore, match_id: str, uid: int, action: Dict, players: Dict[str, object],
           save_finished: bool = True, doc: Optional[Dict] = None, turn: Optional[int] = None,
           request_id: Optional[str] = None) -> Dict:
    """action: {"type": "move", "move": name} | {"type": "switch", "to": index} | {"type": "pick", "order": [i, ...]}.
    Resolves the turn when ready. `turn` and `request_id` make a retry harmless: the same request twice changes
    nothing, and an action for a turn that already resolved is refused instead of applied to the next one."""
    doc = doc or store.load(match_id)
    if not doc or doc["status"] != "active":
        raise PvpError("This duel isn't active.")
    me = _key(doc, uid)
    st = doc["state"]
    side = st["sides"][me]
    if request_id and side.get("last_rid") == request_id:
        return doc                                           # a retry of an action that already went through
    if turn is not None and st["phase"] != "preview" and turn != st["turn"]:
        raise PvpError("That turn has already been played. Your screen is out of date.")
    if st["phase"] == "preview":
        return _preview_pick(store, doc, me, action, request_id, save_finished)
    active = side["team"][side["active"]]

    if st["phase"] == "switch":
        if active["current_hp"] > 0:
            raise PvpError("Waiting for your opponent to send out a Pokémon.")
        if action.get("type") != "switch":
            raise PvpError("Your Pokémon fainted — choose who to send out.")
    if side["choice"] is not None:
        raise PvpError("You already chose — waiting for your opponent.")

    if action.get("type") == "switch":
        to = action.get("to")
        if not isinstance(to, int) or not 0 <= to < len(side["team"]):
            raise PvpError("Pick one of your Pokémon.")
        if to == side["active"] and active["current_hp"] > 0:
            raise PvpError("That Pokémon is already out.")
        if side["team"][to]["current_hp"] <= 0:
            raise PvpError("That Pokémon can't battle.")
        side["choice"] = {"type": "switch", "to": to}
    elif action.get("type") == "move":
        name = str(action.get("move", "")).lower().replace("_", "-")
        names = [m.lower().replace("_", "-") for m in active["moves"]]
        if name not in names and name != "struggle":
            raise PvpError("Your Pokémon doesn't know that move.")
        side["choice"] = {"type": "move", "move": name}
    else:
        raise PvpError("Unknown action.")
    st["last_move_at"] = int(time.time())
    side["last_rid"] = request_id or side.get("last_rid")
    st["seq"] = st.get("seq", 0) + 1

    _resolve_if_ready(doc, players)
    if not (doc["status"] == "finished" and not save_finished):     # the caller stores a finished duel with the players
        store.save(doc)
    return doc


def _preview_pick(store: DocStore, doc: Dict, me: str, action: Dict, request_id: Optional[str], save_finished: bool) -> Dict:
    """Team preview: choose which of the brought Pokémon fight, and in what order (the first one leads)."""
    st = doc["state"]
    side = st["sides"][me]
    if side.get("picked"):
        raise PvpError("You already chose — waiting for your opponent.")
    if action.get("type") != "pick":
        raise PvpError("Choose your team first.")
    fmt = _fmt(st)
    order = _check(F.check_pick, fmt, side["team"], action.get("order"))
    side["team"] = [side["team"][i] for i in order]
    side["active"] = 0
    side["picked"] = True
    side["last_rid"] = request_id or side.get("last_rid")
    st["last_move_at"] = int(time.time())
    st["seq"] = st.get("seq", 0) + 1
    if all(st["sides"][k].get("picked") for k in "ab"):
        st["phase"] = "choose"
        st["log"].append("The battle begins!")
    store.save(doc)
    return doc


def _resolve_if_ready(doc: Dict, players: Dict[str, object]):
    st = doc["state"]
    sides = st["sides"]
    if st["phase"] == "switch":
        need = [k for k in "ab" if sides[k]["team"][sides[k]["active"]]["current_hp"] <= 0]
        if all(sides[k]["choice"] for k in need):
            for k in need:
                c = sides[k]["choice"]
                sides[k]["active"] = c["to"]
                sides[k]["choice"] = None
                st["log"].append(f"{sides[k]['name']} sent out {sides[k]['team'][c['to']]['nickname'].upper()}!")
            st["phase"] = "choose"
            st["turn"] += 1
        return
    if not (sides["a"]["choice"] and sides["b"]["choice"]):
        return
    st["seq"] = st.get("seq", 0) + 1

    log: List[str] = [f"— Turn {st['turn']} —"]
    # switches resolve first
    for k in "ab":
        c = sides[k]["choice"]
        if c["type"] == "switch":
            old = sides[k]["team"][sides[k]["active"]]["nickname"].upper()
            sides[k]["active"] = c["to"]
            log.append(f"{sides[k]['name']} withdrew {old} and sent out {sides[k]['team'][c['to']]['nickname'].upper()}!")

    ma = _mon(sides["a"]["team"][sides["a"]["active"]])
    mb = _mon(sides["b"]["team"][sides["b"]["active"]])
    labels = (f"{sides['a']['name']}'s {ma.nickname.upper()}", f"{sides['b']['name']}'s {mb.nickname.upper()}")
    bs = BattleSystem(ma, mb, smart=False, labels=labels)
    mv = {k: (Move.from_name(sides[k]["choice"]["move"]) if sides[k]["choice"]["type"] == "move" else None) for k in "ab"}
    if mv["a"] or mv["b"]:
        result = bs.execute_turn(mv["a"], mv["b"])
        log.extend(l for l in result["log"] if not l.startswith("\nTurn"))
    # write the results back into the stored copies
    for k, mon in (("a", ma), ("b", mb)):
        mon.current_hp = bs.player_hp if k == "a" else bs.wild_hp
        mon.is_fainted = mon.current_hp <= 0
        d = mon.to_dict()
        sides[k]["team"][sides[k]["active"]] = d
        sides[k]["choice"] = None

    st["log"].extend(log)
    st["log"] = st["log"][-40:]
    # faints / victory
    down = [k for k in "ab" if sides[k]["team"][sides[k]["active"]]["current_hp"] <= 0]
    for k in down:
        if not _alive(sides[k]):
            winner = _other(k)
            _finish(doc, winner, players)
            return
    if down:
        st["phase"] = "switch"
        for k in down:
            st["log"].append(f"{sides[k]['name']}'s {sides[k]['team'][sides[k]['active']]['nickname'].upper()} fainted!")
    else:
        st["turn"] += 1


def elo_change(winner_elo: int, loser_elo: int) -> Tuple[int, int]:
    expected = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    gain = max(1, round(K_FACTOR * (1 - expected)))
    return gain, gain


def _pvp_story(player) -> Dict:
    if not isinstance(player.story, dict):
        player.story = {}
    rec = player.story.setdefault("pvp", {})
    rec.setdefault("ratings", {})
    rec.setdefault("history", [])
    return rec


def rating_of(player, fmt_id: str) -> Dict:
    return _pvp_story(player)["ratings"].setdefault(fmt_id, {"elo": 1000, "w": 0, "l": 0})


def _recent_games(winner, loser_uid: int) -> int:
    cutoff = time.time() - REPEAT_WINDOW
    return sum(1 for h in _pvp_story(winner)["history"] if h.get("opp_id") == loser_uid and h.get("rated") and h.get("ts", 0) >= cutoff)


def _remember(player, opp, fmt: F.Format, won: bool, delta: int, now: int) -> None:
    hist = _pvp_story(player)["history"]
    hist.append({"ts": now, "opp_id": opp.user_id, "opp": opp.username, "format": fmt.id, "won": won,
                 "delta": delta, "rated": fmt.rated})
    del hist[:-HISTORY_KEEP]


def _finish(doc: Dict, winner: str, players: Dict[str, object], reason: str = ""):
    st = doc["state"]
    fmt = _fmt(st)
    st["winner"] = winner
    st["phase"] = "done"
    st["seq"] = st.get("seq", 0) + 1
    doc["status"] = "finished"
    loser = _other(winner)
    if fmt.legacy:
        w, l = players[winner], players[loser]
        gain, loss = elo_change(w.elo, l.elo)
        w.elo += gain
        l.elo = max(100, l.elo - loss)
        w.wins += 1
        l.losses += 1
        st["elo"] = {winner: {"name": w.username, "now": w.elo, "delta": gain},
                     loser: {"name": l.username, "now": l.elo, "delta": -loss}}
    elif fmt.rated:
        w, l = players[winner], players[loser]
        rw, rl = rating_of(w, fmt.id), rating_of(l, fmt.id)
        farming = _recent_games(w, l.user_id) >= REPEAT_LIMIT
        gain, loss = (0, 0) if farming else elo_change(rw["elo"], rl["elo"])
        rw["elo"] += gain
        rl["elo"] = max(100, rl["elo"] - loss)
        rw["w"] += 1
        rl["l"] += 1
        w.elo += gain
        l.elo = max(100, l.elo - loss)
        w.wins += 1
        l.losses += 1
        now = int(time.time())
        _remember(w, l, fmt, True, gain, now)
        _remember(l, w, fmt, False, -loss, now)
        st["elo"] = {winner: {"name": w.username, "now": rw["elo"], "delta": gain},
                     loser: {"name": l.username, "now": rl["elo"], "delta": -loss}}
        if farming:
            st["log"].append("Ratings didn't change: you've played this opponent several times today.")
    st["log"].append(f"{st['sides'][winner]['name']} wins the battle!{(' ' + reason) if reason else ''}")


def settles_players(doc: Dict) -> bool:
    """Does finishing this match change the two players' saved records (so they must be written with it)?"""
    st = doc["state"]
    if "format" not in st:
        return True
    return bool(st["format"].get("rated"))


def sweep(doc: Dict, players: Dict[str, object]) -> bool:
    """Settle a match whose turn timer ran out (no background worker needed: any request that touches the match
    does it). One side silent -> the other wins. Both silent -> the match is abandoned, with no rating change.
    Returns True when the match changed. The classic duel keeps its manual claim."""
    st = doc["state"]
    if doc["status"] != "active" or "sides" not in st:
        return False
    fmt = _fmt(st)
    if fmt.legacy or time.time() - st.get("last_move_at", 0) < fmt.turn_timer:
        return False
    sides = st["sides"]
    if st["phase"] == "preview":
        owing = [k for k in "ab" if not sides[k].get("picked")]
    elif st["phase"] == "switch":
        owing = [k for k in "ab" if sides[k]["team"][sides[k]["active"]]["current_hp"] <= 0 and not sides[k]["choice"]]
    else:
        owing = [k for k in "ab" if not sides[k]["choice"]]
    if len(owing) == 1:
        _finish(doc, _other(owing[0]), players, "(opponent timed out)")
    else:
        doc["status"] = "abandoned"
        st["phase"] = "done"
        st["seq"] = st.get("seq", 0) + 1
        st["log"].append("Neither trainer answered in time. The battle was abandoned; no ratings changed.")
    return True


# ── matchmaking queue ──

def queue_join(store: DocStore, player, format_id: str, ids: List[str]) -> Dict:
    fmt = _check(F.get, format_id)
    if not fmt.queue:
        raise PvpError("That format has no matchmaking queue.")
    for d in store.for_user(player.user_id, ["queued", "pending", "active"], 3600):
        if d["status"] == "active":
            raise PvpError("Finish your current battle first.")
    queue_leave(store, player.user_id)
    _check(F.check_selection, player, fmt, ids)
    now = int(time.time())
    doc = {"id": uuid.uuid4().hex[:12], "a": player.user_id, "b": player.user_id, "status": "queued",
           "state": {"format": fmt.public(), "brought": {"a": list(ids)}, "names": {"a": player.username},
                     "rating": rating_of(player, fmt.id)["elo"], "since": now, "seq": 1}}
    store.save(doc)
    return doc


def queue_leave(store: DocStore, uid: int) -> int:
    n = 0
    for d in store.for_user(uid, ["queued"], 3600):
        store.delete(d["id"])
        n += 1
    return n


def _window(waited_s: float) -> int:
    return int(min(600, 150 + 30 * (waited_s / 10)))


def try_match(store: DocStore, mine: Dict, load_player) -> Optional[Dict]:
    """Pair a queued player with the closest-rated opponent in the same format, if one is close enough (the
    acceptable gap grows the longer anyone has waited). Returns the new active match, or None."""
    st = mine["state"]
    now = time.time()
    best, best_gap = None, None
    for other in store.list_status("queued"):
        o = other["state"]
        if other["id"] == mine["id"] or other["a"] == mine["a"] or o["format"]["id"] != st["format"]["id"]:
            continue
        if now - o.get("since", 0) > QUEUE_TTL:
            continue
        gap = abs(o.get("rating", 1000) - st.get("rating", 1000))
        waited = max(now - st.get("since", now), now - o.get("since", now))
        if gap <= _window(waited) and (best_gap is None or gap < best_gap):
            best, best_gap = other, gap
    if best is None:
        return None
    first, second = (best, mine) if best["state"]["since"] <= st["since"] else (mine, best)
    a_player, b_player = load_player(first["a"]), load_player(second["a"])
    match = {"id": uuid.uuid4().hex[:12], "a": first["a"], "b": second["a"], "status": "pending",
             "state": {"names": {"a": a_player.username, "b": b_player.username}, "log": [], "seq": 1,
                       "format": first["state"]["format"],
                       "brought": {"a": first["state"]["brought"]["a"], "b": second["state"]["brought"]["a"]}}}
    _build(match, a_player, b_player)
    store.save(match)
    store.delete(first["id"])
    store.delete(second["id"])
    return match


def forfeit(store: DocStore, match_id: str, uid: int, players: Dict[str, object], save_finished: bool = True) -> Dict:
    doc = store.load(match_id)
    if not doc or doc["status"] != "active":
        raise PvpError("This duel isn't active.")
    me = _key(doc, uid)
    _finish(doc, _other(me), players, "(forfeit)")
    if save_finished:
        store.save(doc)
    return doc


def claim_timeout(store: DocStore, match_id: str, uid: int, players: Dict[str, object], save_finished: bool = True) -> Dict:
    """Walkover win if the opponent hasn't answered for TURN_TIMEOUT while you have."""
    doc = store.load(match_id)
    if not doc or doc["status"] != "active":
        raise PvpError("This duel isn't active.")
    me = _key(doc, uid)
    st = doc["state"]
    if st["sides"][me]["choice"] is None and st["phase"] == "choose":
        raise PvpError("Make your own move first.")
    if time.time() - st.get("last_move_at", 0) < TURN_TIMEOUT:
        raise PvpError("Give your opponent a little longer.")
    _finish(doc, me, players, "(opponent timed out)")
    if save_finished:
        store.save(doc)
    return doc


