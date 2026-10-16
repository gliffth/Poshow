"""
Storage box: move Pokémon between the team (max 6) and the PC box.

The box is simply `player.pokemon_collection` minus whoever is on the team; no schema change. A Pokémon that is
sleeping in its ball (care.py) is also "in the box" and comes out through care.withdraw so its healing is applied.
"""

from typing import Dict, List

import care

TEAM_LIMIT = care.TEAM_LIMIT


def box(player) -> List:
    team_ids = {m.id for m in player.active_team}
    return [m for m in player.pokemon_collection if m.id not in team_ids]


def deposit(player, mon_id: str) -> Dict:
    mon = next((m for m in player.active_team if m.id == mon_id), None)
    if mon is None:
        return {"ok": False, "message": "That Pokémon isn't on your team."}
    if len(player.active_team) <= 1:
        return {"ok": False, "message": "You can't store your last Pokémon — you'd have no one to battle with."}
    player.active_team = [m for m in player.active_team if m.id != mon_id]
    if all(m.id != mon_id for m in player.pokemon_collection):
        player.pokemon_collection.append(mon)
    return {"ok": True, "message": f"{mon.nickname} was sent to the storage box."}


def withdraw(player, mon_id: str) -> Dict:
    if any(m.id == mon_id for m in player.active_team):
        return {"ok": False, "message": "That Pokémon is already on your team."}
    mon = next((m for m in player.pokemon_collection if m.id == mon_id), None)
    if mon is None:
        return {"ok": False, "message": "That Pokémon isn't in your box."}
    if len(player.active_team) >= TEAM_LIMIT:
        return {"ok": False, "message": "Your team is full — store another Pokémon first."}
    if care.is_resting(player, mon):
        return care.withdraw(player, mon_id)
    player.active_team.append(mon)
    return {"ok": True, "message": f"{mon.nickname} joined your team."}
