"""
Player-to-player trading, shared by the website and the Telegram bot.

A trade is a small shared document (doc_store.py, table `trades`):
  invite -> both open the trade -> each side offers up to ONE Pokémon (optional) plus credits and items
  -> both LOCK -> both CONFIRM -> the swap happens in one step.

Safety rules:
  * changing an offer un-locks everybody (you can never be switched on at the last second)
  * you can only offer Pokémon that are yours and not critical / resting
  * nobody can trade away their last team member
  * the swap re-checks everything against the live players and either completes fully or not at all
  * a received Pokémon that evolves by trade evolves on the spot (the trade itself is the "cable")
"""

import time
import uuid
from typing import Dict, List, Optional

import care
import rules
from doc_store import DocStore

INVITE_TTL = 15 * 60
IDLE_TTL = 30 * 60
MAX_COINS = 100000


class TradeError(ValueError):
    pass


def new_store(url=None, key=None) -> DocStore:
    return DocStore("trades", url, key)


def _side_key(doc: Dict, uid: int) -> str:
    if uid == doc["a"]:
        return "a"
    if uid == doc["b"]:
        return "b"
    raise TradeError("You're not part of this trade.")


def _other(k: str) -> str:
    return "b" if k == "a" else "a"


def _empty_offer() -> Dict:
    return {"pokemon_id": None, "coins": 0, "items": {}}


def invite(store: DocStore, inviter, other_id: int, other_name: str) -> Dict:
    if other_id == inviter.user_id:
        raise TradeError("You can't trade with yourself.")
    for d in store.for_user(inviter.user_id, ["pending", "open"], IDLE_TTL):
        if d["status"] == "open":
            raise TradeError("Finish or cancel your current trade first.")
        if d["a"] == inviter.user_id and d["b"] == other_id and time.time() - d["ts"] < INVITE_TTL:
            raise TradeError(f"You already invited {other_name}.")
    doc = {"id": uuid.uuid4().hex[:12], "a": inviter.user_id, "b": other_id, "status": "pending",
           "state": {"names": {"a": inviter.username, "b": other_name}, "offers": {"a": _empty_offer(), "b": _empty_offer()},
                     "locked": {"a": False, "b": False}, "confirmed": {"a": False, "b": False}, "log": []}}
    store.save(doc)
    return doc


def respond(store: DocStore, trade_id: str, player, accept: bool) -> Dict:
    doc = store.load(trade_id)
    if not doc or doc["b"] != player.user_id:
        raise TradeError("That invitation isn't for you.")
    if doc["status"] != "pending":
        raise TradeError("That invitation is no longer open.")
    if time.time() - doc["ts"] > INVITE_TTL:
        doc["status"] = "expired"
        store.save(doc)
        raise TradeError("That invitation expired.")
    if accept:
        for d in store.for_user(player.user_id, ["open"], IDLE_TTL):
            raise TradeError("Finish or cancel your current trade first.")
    doc["status"] = "open" if accept else "declined"
    store.save(doc)
    return doc


def _owned(player, mon_id: str):
    for m in list(player.active_team) + list(player.pokemon_collection):
        if m.id == mon_id:
            return m
    return None


def _validate_offer_pokemon(player, mon_id: str):
    mon = _owned(player, mon_id)
    if mon is None:
        raise TradeError("That Pokémon isn't yours.")
    if care.is_critical(player, mon):
        raise TradeError(f"{mon.nickname} is critical — it needs Nurse Joy before it can travel.")
    if care.is_resting(player, mon):
        raise TradeError(f"{mon.nickname} is sleeping in its ball — take it out first.")
    return mon


def set_offer(store: DocStore, trade_id: str, player, pokemon_id: Optional[str] = None, clear_pokemon: bool = False,
              coins: Optional[int] = None, items: Optional[Dict[str, int]] = None) -> Dict:
    doc = store.load(trade_id)
    if not doc or doc["status"] != "open":
        raise TradeError("This trade isn't open.")
    k = _side_key(doc, player.user_id)
    st = doc["state"]
    offer = st["offers"][k]
    if pokemon_id:
        _validate_offer_pokemon(player, pokemon_id)
        offer["pokemon_id"] = pokemon_id
    if clear_pokemon:
        offer["pokemon_id"] = None
    if coins is not None:
        coins = int(coins)
        if coins < 0 or coins > MAX_COINS:
            raise TradeError(f"Credits must be between 0 and {MAX_COINS}.")
        if coins > player.coins:
            raise TradeError("You don't have that many credits.")
        offer["coins"] = coins
    if items is not None:
        clean = {}
        for name, qty in items.items():
            qty = int(qty)
            if qty <= 0:
                continue
            if str(name).startswith("_"):
                raise TradeError("That can't be traded.")
            if player.inventory.get(name, 0) < qty:
                raise TradeError(f"You don't have {qty} × {name.replace('_', ' ')}.")
            clean[name] = qty
        offer["items"] = clean
    # any change un-locks everyone
    st["locked"] = {"a": False, "b": False}
    st["confirmed"] = {"a": False, "b": False}
    store.save(doc)
    return doc


def lock(store: DocStore, trade_id: str, player, locked: bool = True) -> Dict:
    doc = store.load(trade_id)
    if not doc or doc["status"] != "open":
        raise TradeError("This trade isn't open.")
    k = _side_key(doc, player.user_id)
    st = doc["state"]
    st["locked"][k] = bool(locked)
    if not locked:
        st["confirmed"] = {"a": False, "b": False}
    store.save(doc)
    return doc


def confirm(store: DocStore, trade_id: str, player, players: Dict[str, object], save_done: bool = True) -> Dict:
    """Second step: only possible once BOTH sides are locked. When both confirmed, the swap runs.
    With save_done=False a COMPLETED trade is not stored here: the caller writes it inside the same database
    transaction as both players (so "done" can never exist without the assets having moved, or vice-versa)."""
    doc = store.load(trade_id)
    if not doc or doc["status"] != "open":
        raise TradeError("This trade isn't open.")
    k = _side_key(doc, player.user_id)
    st = doc["state"]
    if not (st["locked"]["a"] and st["locked"]["b"]):
        raise TradeError("Both trainers must lock their offers first.")
    st["confirmed"][k] = True
    if st["confirmed"]["a"] and st["confirmed"]["b"]:
        result = execute(doc, players)
        st["result"] = result
        doc["status"] = "done"
        if not save_done:
            return doc
    store.save(doc)
    return doc


def cancel(store: DocStore, trade_id: str, uid: int) -> Dict:
    doc = store.load(trade_id)
    if not doc or doc["status"] not in ("pending", "open"):
        raise TradeError("This trade isn't open.")
    _side_key(doc, uid)
    doc["status"] = "cancelled"
    store.save(doc)
    return doc


def _take_pokemon(player, mon_id: str):
    """Remove the Pokémon from the player EVERYWHERE. Team members are also in `pokemon_collection`, so popping
    from the first list only left it in the sender's collection — and the sender's next save then re-claimed the row
    the receiver had just been given (the Pokémon ended up owned by the wrong account / duplicated)."""
    taken = None
    for lst in (player.active_team, player.pokemon_collection):
        for i in range(len(lst) - 1, -1, -1):
            if lst[i].id == mon_id:
                m = lst.pop(i)
                taken = taken or m
    return taken


def execute(doc: Dict, players: Dict[str, object]) -> Dict:
    """Atomically swap the offers (all checks first, changes after)."""
    st = doc["state"]
    offers = st["offers"]
    a, b = players["a"], players["b"]

    # ---- validate everything against the LIVE players ----
    mons = {}
    for k, p in (("a", a), ("b", b)):
        o = offers[k]
        if o["pokemon_id"]:
            mons[k] = _validate_offer_pokemon(p, o["pokemon_id"])
        if o["coins"] > p.coins:
            raise TradeError(f"{p.username} no longer has the offered credits.")
        for name, qty in o["items"].items():
            if p.inventory.get(name, 0) < qty:
                raise TradeError(f"{p.username} no longer has {qty} × {name}.")
        if k in mons and mons[k] in p.active_team and len(p.active_team) <= 1 and not offers[_other(k)]["pokemon_id"]:
            raise TradeError(f"{p.username} can't trade away their only team Pokémon.")
    # nobody may end with an empty team
    for k, p in (("a", a), ("b", b)):
        leaving = 1 if (k in mons and mons[k] in p.active_team) else 0
        arriving = 1 if _other(k) in mons else 0
        remaining_team = len(p.active_team) - leaving
        if remaining_team + arriving <= 0:
            raise TradeError(f"{p.username} would be left with no Pokémon on their team.")

    # ---- apply ----
    received: Dict[str, Optional[object]] = {"a": None, "b": None}
    for k in "ab":
        p, q = players[k], players[_other(k)]
        o = offers[k]
        if o["pokemon_id"]:
            mon = _take_pokemon(p, o["pokemon_id"])
            mon.trainer_id = q.user_id
            received[_other(k)] = mon
        p.coins -= o["coins"]
        q.coins += o["coins"]
        for name, qty in o["items"].items():
            p.remove_item(name, qty)
            q.add_item(name, qty)
    evolved = []
    for k in "ab":
        mon = received[k]
        if mon is None:
            continue
        q = players[k]
        if len(q.active_team) < 6:
            q.active_team.append(mon)
        else:
            q.pokemon_collection.append(mon)
        dex = (mon.api_data or {}).get("id")
        if dex:
            q.pokedex_seen.add(dex)
        q.record_caught(mon.species_name)
        # evolution by trade
        import evolution
        for e in rules.evolutions_for(mon.species_name):
            if e["rule"][0] == "trade":
                before = mon.species_name
                q.inventory["trade_cable"] = q.inventory.get("trade_cable", 0) + 1     # the trade is the cable…
                res = evolution.evolve(q, mon.id, e["to"])                              # …and it is consumed here
                if res["ok"]:
                    evolved.append({"for": q.username, "from": before, "to": e["to"]})
                else:
                    q.inventory["trade_cable"] = max(0, q.inventory.get("trade_cable", 1) - 1)
                break
    return {"ok": True, "evolved": evolved,
            "received": {k: (received[k].nickname if received[k] else None) for k in "ab"}}


def view(doc: Dict, uid: int, players: Optional[Dict[str, object]] = None) -> Dict:
    me = _side_key(doc, uid)
    st = doc["state"]
    out = {"id": doc["id"], "status": doc["status"], "you": me, "names": st["names"],
           "locked": st["locked"], "confirmed": st["confirmed"], "offers": st["offers"], "result": st.get("result")}
    if players:
        details = {}
        for k in "ab":
            pid = st["offers"][k]["pokemon_id"]
            mon = _owned(players[k], pid) if pid else None
            details[k] = ({"id": mon.id, "species": mon.species_name, "nickname": mon.nickname, "level": mon.level,
                           "shiny": bool(mon.is_shiny), "hp": mon.current_hp, "max_hp": mon.max_hp,
                           "nature": mon.nature} if mon else None)
        out["pokemon"] = details
    return out
