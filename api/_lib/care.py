"""
Pokémon care: condition, Nurse Joy's Care Center, resting in the ball

A Pokémon's *HP* is its health in a fight. Its *condition* (vitality) is its life: every time it is
knocked out it loses a point. Strong, high-level Pokémon have lots of points, so good Pokémon don't
die easily — a weak Lv5 starter has 3, a Lv50 dragon around 10.

  healthy        HP above half
  hurt           HP at or below half
  injured        knocked out (0 HP) but with condition left — "severely injured": it needs rest or care
  critical       knocked out with NO condition left — close to dying. Normal healing can't reach it:
                 it needs Nurse Joy's intensive care (good odds, better with a Revive)
  resting        sleeping in its Poké Ball, slowly recovering

Nurse Joy's free check-up heals every Pokémon that isn't critical and restores its condition.
Resting in the ball heals ~2% HP per minute and a condition point every 15 minutes (not during a battle).

State lives in player.story["care"] = {"vit": {pokemon_id: points}, "rest": {pokemon_id: start_ts}}
so no database migration is needed (it rides along in the `story` jsonb column).
"""

import random
import time
from typing import Dict, List, Optional

REST_HP_PER_MIN = 0.02
REST_MINUTES_PER_VIT = 15
TEAM_LIMIT = 6


def _care(player) -> Dict:
    st = player.story if isinstance(player.story, dict) else {}
    if not isinstance(player.story, dict):
        player.story = st
    care = st.setdefault("care", {})
    care.setdefault("vit", {})
    care.setdefault("rest", {})
    return care


def _bst(mon) -> int:
    base = (getattr(mon, "api_data", None) or {}).get("base_stats") or {}
    if isinstance(base, dict) and base:
        return int(sum(v for v in base.values() if isinstance(v, (int, float))))
    return 400


def max_vitality(mon) -> int:
    bst = _bst(mon)
    tier = 3 if bst >= 600 else 2 if bst >= 500 else 1 if bst >= 400 else 0
    return 3 + int(mon.level) // 12 + tier


def vitality(player, mon) -> int:
    cap = max_vitality(mon)
    v = _care(player)["vit"].get(mon.id)
    return cap if v is None else max(0, min(cap, int(v)))


def _set_vit(player, mon, value: int):
    cap = max_vitality(mon)
    value = max(0, min(cap, int(value)))
    vit = _care(player)["vit"]
    if value >= cap:
        vit.pop(mon.id, None)          # full condition isn't stored
    else:
        vit[mon.id] = value


def is_critical(player, mon) -> bool:
    return bool(mon.is_fainted or mon.current_hp <= 0) and vitality(player, mon) <= 0


def is_resting(player, mon) -> bool:
    return mon.id in _care(player)["rest"]


def condition(player, mon) -> Dict:
    cap, vit = max_vitality(mon), vitality(player, mon)
    ko = bool(mon.is_fainted or mon.current_hp <= 0)
    frac = mon.current_hp / max(1, mon.max_hp)
    if is_resting(player, mon):
        state, label = "resting", "Resting in its Poké Ball"
    elif ko and vit <= 0:
        state, label = "critical", "Critical — needs Nurse Joy"
    elif ko:
        state, label = "injured", "Severely injured"
    elif frac <= 0.5:
        state, label = "hurt", "Hurt"
    else:
        state, label = "healthy", "Healthy"
    return {"state": state, "label": label, "vit": vit, "vit_max": cap,
            "ko_left": vit,                        # knockouts it can take before it is critical
            "resting": is_resting(player, mon),
            "revive_chance": round(revive_chance(mon), 2), "care_cost": care_cost(mon)}


# ── events ──────────────────────────────────────────────────────────

def on_faint(player, mon) -> Dict:
    """Call whenever one of the player's Pokémon is knocked out in a battle."""
    mon.is_fainted = True
    mon.current_hp = 0
    _set_vit(player, mon, vitality(player, mon) - 1)
    return condition(player, mon)


def heal_all(player) -> Dict:
    """Nurse Joy's free check-up: everyone on the team who isn't critical is fully healed."""
    healed, skipped = [], []
    for mon in player.active_team:
        if is_critical(player, mon):
            skipped.append(mon.nickname)
            continue
        mon.restore_hp()
        _set_vit(player, mon, max_vitality(mon))
        healed.append(mon.nickname)
    return {"healed": healed, "critical": skipped}


def revive_chance(mon) -> float:
    return min(0.95, 0.55 + int(mon.level) * 0.004 + _bst(mon) / 1000 * 0.2)


def care_cost(mon) -> int:
    return 150 + 15 * int(mon.level)


def intensive_care(player, mon_id: str, use_revive: bool = False, rng: Optional[random.Random] = None) -> Dict:
    mon = _find(player, mon_id)
    if mon is None:
        return {"ok": False, "message": "Joy can't find that Pokémon."}
    if not is_critical(player, mon):
        return {"ok": False, "message": f"{mon.nickname} doesn't need intensive care."}
    rng = rng or random
    # nobody left who can fight and no money for treatment: Joy takes this one on the house (no soft-locks)
    usable = [m for m in list(player.active_team) + resting(player)
              if m.current_hp > 0 and not m.is_fainted]
    charity = not usable and player.coins < care_cost(mon) and not use_revive
    if use_revive:
        if player.inventory.get("revive", 0) < 1:
            return {"ok": False, "message": "You don't have a Revive."}
        player.remove_item("revive", 1)
        success, cost = True, 0
    elif charity:
        success, cost = rng.random() < revive_chance(mon), 0
    else:
        cost = care_cost(mon)
        if player.coins < cost:
            return {"ok": False, "message": f"Intensive care costs {cost}₽ — you have {player.coins}₽."}
        player.coins -= cost
        success = rng.random() < revive_chance(mon)
    if success:
        mon.restore_hp()
        _set_vit(player, mon, max(1, max_vitality(mon) // 2))
        return {"ok": True, "success": True, "cost": cost,
                "message": f"{mon.nickname} opened its eyes! Joy: \"Phew — we pulled it through. Take it easy with this one.\""}
    return {"ok": True, "success": False, "cost": cost,
            "message": f"Joy: \"I'm so sorry — {mon.nickname} isn't responding yet. We won't give up. You can try again.\""}


# ── resting in the ball ─────────────────────────────────────────────

def _find(player, mon_id: str):
    for mon in list(player.active_team) + list(player.pokemon_collection):
        if mon.id == mon_id:
            return mon
    return None


def rest(player, mon_id: str) -> Dict:
    mon = next((m for m in player.active_team if m.id == mon_id), None)
    if mon is None:
        return {"ok": False, "message": "That Pokémon isn't on your team."}
    if is_critical(player, mon):
        return {"ok": False, "message": f"{mon.nickname} is critical — it needs Nurse Joy, resting won't be enough."}
    care = _care(player)
    player.active_team = [m for m in player.active_team if m.id != mon_id]
    if all(m.id != mon_id for m in player.pokemon_collection):
        player.pokemon_collection.append(mon)
    care["rest"][mon_id] = time.time()
    return {"ok": True, "message": f"{mon.nickname} curled up in its Poké Ball to sleep."}


def withdraw(player, mon_id: str, now: Optional[float] = None) -> Dict:
    care = _care(player)
    if mon_id not in care["rest"]:
        return {"ok": False, "message": "That Pokémon isn't resting."}
    if len(player.active_team) >= TEAM_LIMIT:
        return {"ok": False, "message": "Your team is full — rest or store another Pokémon first."}
    tick(player, now)
    mon = _find(player, mon_id)
    if mon is None:
        care["rest"].pop(mon_id, None)
        return {"ok": False, "message": "Joy can't find that Pokémon."}
    care["rest"].pop(mon_id, None)
    player.pokemon_collection = [m for m in player.pokemon_collection if m.id != mon_id]
    if all(m.id != mon_id for m in player.active_team):
        player.active_team.append(mon)
    return {"ok": True, "message": f"{mon.nickname} stretched and jumped out of its Poké Ball."}


def tick(player, now: Optional[float] = None) -> None:
    """Apply the healing that resting Pokémon earned since their last tick. Idempotent."""
    care = _care(player)
    if not care["rest"]:
        return
    now = now if now is not None else time.time()
    for mon_id, since in list(care["rest"].items()):
        mon = _find(player, mon_id)
        if mon is None:
            care["rest"].pop(mon_id, None)
            continue
        minutes = max(0.0, (now - float(since)) / 60.0)
        if minutes <= 0:
            continue
        heal = int(mon.max_hp * REST_HP_PER_MIN * minutes)
        gain_vit = int(minutes // REST_MINUTES_PER_VIT)
        used = 0.0
        if heal > 0 and mon.current_hp < mon.max_hp:
            mon.current_hp = min(mon.max_hp, mon.current_hp + heal)
            if mon.current_hp > 0:
                mon.is_fainted = False
            used = minutes
        if gain_vit > 0 and vitality(player, mon) < max_vitality(mon):
            _set_vit(player, mon, vitality(player, mon) + gain_vit)
            used = minutes
        # only move the clock forward when the time was actually spent healing, so tiny ticks accumulate
        if used or (mon.current_hp >= mon.max_hp and vitality(player, mon) >= max_vitality(mon)):
            care["rest"][mon_id] = now


def resting(player) -> List:
    rest_ids = _care(player)["rest"]
    return [m for m in player.pokemon_collection if m.id in rest_ids]


def summary(player) -> Dict:
    tick(player)
    def row(m):
        return {"id": m.id, "species_name": m.species_name, "nickname": m.nickname, "level": m.level,
                "current_hp": m.current_hp, "max_hp": m.max_hp, "condition": condition(player, m)}
    return {"team": [row(m) for m in player.active_team], "resting": [row(m) for m in resting(player)]}
