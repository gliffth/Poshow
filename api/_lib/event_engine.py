"""
Event engine (roadmap §7.3 foundation, §6.5 quests, §6.6 route rewards).

Game code reports what happened with emit(player, event, key). Quest progress and route rewards are the two
consumers here; the story and narrative layer can attach to the same events later.

Events:
  "catch"   a Pokémon was caught           key: species name
  "win"     a battle was won               key: "wild" | "boss" | "gym" | "trainer"
  "evolve"  a Pokémon evolved              key: the new species name
  "visit"   the player reached a route     key: the route id

State lives in player.story (already a persisted JSON column, so no schema change):
  story["quests"]        {quest_id: {"progress", "seen", "day", "done", "claimed"}}
  story["route_rewards"] [route ids whose first-visit reward was paid]

Nothing here raises into game code: a broken quest must never block a battle or a catch (see emit()).
"""

import logging
import time
from typing import Dict, List, Optional

import route_encounters

logger = logging.getLogger(__name__)

# quest_id -> definition. target = how many events (or distinct keys, when distinct=True) complete it.
QUESTS: Dict[str, Dict] = {
    "catch_10":      {"name": "Catch 10 Pokémon",      "event": "catch",  "target": 10, "daily": False,
                      "reward": {"coins": 500}},
    "win_25":        {"name": "Win 25 battles",        "event": "win",    "target": 25, "daily": False,
                      "reward": {"coins": 800, "potion": 3}},
    "evolve_3":      {"name": "Evolve 3 Pokémon",      "event": "evolve", "target": 3,  "daily": False,
                      "reward": {"rare_candy": 1}},
    "explore_5":     {"name": "Visit 5 routes",        "event": "visit",  "target": 5,  "daily": False,
                      "distinct": True, "reward": {"coins": 600}},
    "daily_catch_3": {"name": "Catch 3 Pokémon today", "event": "catch",  "target": 3,  "daily": True,
                      "reward": {"coins": 300}},
    "daily_win_5":   {"name": "Win 5 battles today",   "event": "win",    "target": 5,  "daily": True,
                      "reward": {"coins": 250, "potion": 1}},
}

# Items a reward may grant (must be something the bag can hold).
REWARD_ITEMS = {"potion", "superpotion", "rare_candy", "exp_all"}


def today() -> str:
    """The day key for daily quests (UTC). Tests replace this to move the clock."""
    return time.strftime("%Y-%m-%d", time.gmtime())


def _quests(player) -> Dict[str, Dict]:
    if not isinstance(player.story, dict):
        player.story = {}
    return player.story.setdefault("quests", {})


def _fresh(defn: Dict) -> Dict:
    return {"progress": 0, "seen": [], "day": today() if defn["daily"] else None, "done": False, "claimed": False}


def emit(player, event: str, key: Optional[str] = None) -> List[str]:
    """Record one game event. Returns the ids of quests this event just completed. Never raises."""
    try:
        return _emit(player, event, key)
    except Exception as e:                      # noqa: BLE001 — a broken quest must never block the game
        logger.error(f"event engine: {event} for {getattr(player, 'user_id', '?')} failed: {e}")
        return []


def _emit(player, event: str, key: Optional[str]) -> List[str]:
    completed = []
    quests = _quests(player)
    for qid, defn in QUESTS.items():
        if defn["event"] != event:
            continue
        st = quests.get(qid)
        if st is None:
            st = quests[qid] = _fresh(defn)
        if defn["daily"] and st.get("day") != today():
            quests[qid] = st = _fresh(defn)                       # a new day: daily quests start over
        if st["done"]:
            continue
        if defn.get("distinct"):
            if key is None or key in st["seen"]:
                continue
            st["seen"].append(key)
            st["progress"] = len(st["seen"])
        else:
            st["progress"] += 1
        if st["progress"] >= defn["target"]:
            st["done"] = True
            completed.append(qid)
    return completed


def status(player) -> List[Dict]:
    """Every quest with its progress, for the player's quest screen."""
    quests = _quests(player)
    out = []
    for qid, defn in QUESTS.items():
        st = quests.get(qid)
        if st is None or (defn["daily"] and st.get("day") != today()):
            st = _fresh(defn)
        out.append({"id": qid, "name": defn["name"], "progress": min(st["progress"], defn["target"]),
                    "target": defn["target"], "done": st["done"], "claimed": st["claimed"],
                    "daily": defn["daily"], "reward": defn["reward"]})
    return out


def _grant(player, reward: Dict) -> Dict:
    """Pay a reward. Returns what was actually granted (coins, items)."""
    granted = {}
    for name, qty in reward.items():
        if name == "coins":
            player.coins += int(qty)
        elif name in REWARD_ITEMS:
            player.add_item(name, int(qty))
        else:
            continue
        granted[name] = granted.get(name, 0) + int(qty)
    return granted


def claim(player, quest_id: str) -> Dict:
    """Pay out a finished quest, once. Returns {ok, message, granted}."""
    defn = QUESTS.get(quest_id)
    if defn is None:
        return {"ok": False, "message": "No such quest."}
    st = _quests(player).get(quest_id)
    if st is None or (defn["daily"] and st.get("day") != today()):
        return {"ok": False, "message": "That quest isn't active today."}
    if not st["done"]:
        return {"ok": False, "message": "That quest isn't finished yet."}
    if st["claimed"]:
        return {"ok": False, "message": "You already claimed that reward."}
    granted = _grant(player, defn["reward"])
    st["claimed"] = True
    return {"ok": True, "message": f"Quest complete: {defn['name']}!", "granted": granted}


# ── route rewards: the first time a player reaches a route ───────────────────
def route_reward_coins(route_id: str) -> int:
    """Coins for a route's first visit: scales with the route's level (20 coins per average level, at least 100)."""
    enc = route_encounters.ALL_ROUTES.get(route_id)
    if enc is None:
        return 0
    lo, hi = enc.level_range
    return max(100, 20 * ((lo + hi) // 2))


def grant_route_reward(player, route_id: str) -> Optional[Dict]:
    """Pay the first-visit reward for a route, once. Towns and unknown places pay nothing.
    Returns {"route", "coins"} when paid, else None."""
    if route_id not in route_encounters.ALL_ROUTES:
        return None
    if not isinstance(player.story, dict):
        player.story = {}
    paid = player.story.setdefault("route_rewards", [])
    if route_id in paid:
        return None
    coins = route_reward_coins(route_id)
    player.coins += coins
    paid.append(route_id)
    return {"route": route_id, "coins": coins}
