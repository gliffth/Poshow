"""
PvP — turn-based trainer duels (3v3), shared by the website and the Telegram bot.

Flow: challenge (by username) -> accept -> both pick a move or a switch each turn -> the turn resolves when both
have chosen -> a fainted Pokémon forces a switch -> the last trainer standing wins. A win/loss moves both
trainers' ELO. Your real Pokémon are never touched: the duel uses copies at their current HP, so there is no
injury, no condition loss and no XP — it's a friendly (but ranked) fight.

State is a JSON document (see doc_store.py):
  sides.a / sides.b : {uid, name, team: [pokemon dicts], active, choice}
  phase             : "choose" (both pick) | "switch" (a fainted side must pick) | "done"
"""

import random
import time
import uuid
from typing import Dict, List, Optional, Tuple

import care
from battle_system import BattleSystem, Move
from doc_store import DocStore
from pokemon_model import PokemonInstance

TEAM_SIZE = 3
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

def challenge(store: DocStore, challenger, opponent_id: int, opponent_name: str) -> Dict:
    if opponent_id == challenger.user_id:
        raise PvpError("You can't challenge yourself.")
    if not pick_team(challenger):
        raise PvpError("You need at least one healthy Pokémon on your team to duel.")
    for d in store.for_user(challenger.user_id, ["pending", "active"]):
        if d["status"] == "active":
            raise PvpError("Finish your current duel first.")
        if d["status"] == "pending" and d["a"] == challenger.user_id and d["b"] == opponent_id \
                and time.time() - d["ts"] < INVITE_TTL:
            raise PvpError(f"You already challenged {opponent_name}.")
    doc = {"id": uuid.uuid4().hex[:12], "a": challenger.user_id, "b": opponent_id, "status": "pending",
           "state": {"names": {"a": challenger.username, "b": opponent_name}, "log": []}}
    store.save(doc)
    return doc


def respond(store: DocStore, match_id: str, player, accept: bool) -> Dict:
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
    return doc


def start(store: DocStore, match_id: str, a_player, b_player) -> Dict:
    """Both trainers loaded -> build the duel."""
    doc = store.load(match_id)
    ta, tb = pick_team(a_player), pick_team(b_player)
    if not ta or not tb:
        raise PvpError("Both trainers need a healthy Pokémon.")
    doc["status"] = "active"
    doc["state"] = {"sides": {"a": _side(a_player, ta), "b": _side(b_player, tb)}, "turn": 1, "phase": "choose",
                    "log": [f"{a_player.username} and {b_player.username} face off!"], "winner": None,
                    "last_move_at": int(time.time())}
    store.save(doc)
    return doc


# ── choices ─────────────────────────────────────────────────────────

def view(doc: Dict, uid: int) -> Dict:
    """What one trainer is allowed to see (never the other side's pending choice)."""
    me = _key(doc, uid)
    st = doc["state"]
    if doc["status"] == "pending":
        return {"id": doc["id"], "status": "pending", "you": me, "names": st["names"], "log": []}
    sides = st["sides"]
    def pub(k, hidden: bool):
        s = sides[k]
        return {"name": s["name"], "active": s["active"], "chosen": s["choice"] is not None,
                "team": [{"species": m["species_name"], "nickname": m["nickname"], "level": m["level"],
                          "hp": m["current_hp"], "max_hp": m["max_hp"], "status": m.get("status"),
                          "moves": ([{"id": mv, "pp": (m.get("bt") or {}).get("pp", {}).get(mv.lower().replace("_", "-"))}
                                     for mv in m["moves"]] if not hidden else [])}
                         for m in s["team"]]}
    other = _other(me)
    return {"id": doc["id"], "status": doc["status"], "you": me, "turn": st["turn"], "phase": st["phase"],
            "winner": st["winner"], "log": st["log"][-12:],
            "me": pub(me, False), "foe": pub(other, True),
            "waiting": sides[me]["choice"] is not None and st["phase"] != "done",
            "needs_switch": st["phase"] == "switch" and sides[me]["team"][sides[me]["active"]]["current_hp"] <= 0,
            "elo": st.get("elo")}


def submit(store: DocStore, match_id: str, uid: int, action: Dict, players: Dict[str, object]) -> Dict:
    """action: {"type": "move", "move": name} | {"type": "switch", "to": index}. Resolves the turn when ready."""
    doc = store.load(match_id)
    if not doc or doc["status"] != "active":
        raise PvpError("This duel isn't active.")
    me = _key(doc, uid)
    st = doc["state"]
    side = st["sides"][me]
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

    _resolve_if_ready(doc, players)
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


def _finish(doc: Dict, winner: str, players: Dict[str, object], reason: str = ""):
    st = doc["state"]
    st["winner"] = winner
    st["phase"] = "done"
    doc["status"] = "finished"
    w, l = players[winner], players[_other(winner)]
    gain, loss = elo_change(w.elo, l.elo)
    w.elo += gain
    l.elo = max(100, l.elo - loss)
    w.wins += 1
    l.losses += 1
    st["elo"] = {winner: {"name": w.username, "now": w.elo, "delta": gain},
                 _other(winner): {"name": l.username, "now": l.elo, "delta": -loss}}
    st["log"].append(f"{st['sides'][winner]['name']} wins the duel!{(' ' + reason) if reason else ''}")


def forfeit(store: DocStore, match_id: str, uid: int, players: Dict[str, object]) -> Dict:
    doc = store.load(match_id)
    if not doc or doc["status"] != "active":
        raise PvpError("This duel isn't active.")
    me = _key(doc, uid)
    _finish(doc, _other(me), players, "(forfeit)")
    store.save(doc)
    return doc


def claim_timeout(store: DocStore, match_id: str, uid: int, players: Dict[str, object]) -> Dict:
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
    store.save(doc)
    return doc


