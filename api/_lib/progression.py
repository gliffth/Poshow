"""
Progression events after any XP / level change — ONE place that answers "what just became possible?".

Battle XP, EXP All, boss / trainer XP and Rare Candy all end in the same question: can anything on the team evolve
now? The server never evolves a Pokémon behind the player's back (evolution is a moment the player confirms, with a
cutscene); it reports `evolution_pending` and the client/bot offers it. Evolving itself is `evolution.evolve()`.
"""

from typing import Dict, List

import evolution


def pending(player) -> List[Dict]:
    """Team Pokémon that can evolve right now by level -> [{id, nickname, from, to, level}]."""
    out = []
    for mon in player.active_team:
        for opt in evolution.options(player, mon):
            if opt["ready"] and opt["kind"] == "level":
                out.append({"id": mon.id, "nickname": mon.nickname, "from": mon.species_name,
                            "to": opt["to"], "level": mon.level})
                break
    return out


def pending_moves(player) -> List[Dict]:
    """Level-up moves waiting for the player's decision (moveset was full) ->
    [{id, nickname, species, moves: [offered…], known: [current moves]}]."""
    out = []
    for mon in list(player.active_team) + list(player.pokemon_collection):
        offered = list(getattr(mon, "pending_moves", []) or [])
        if offered and not any(o["id"] == mon.id for o in out):
            out.append({"id": mon.id, "nickname": mon.nickname, "species": mon.species_name,
                        "moves": offered, "known": list(mon.moves)})
    return out


def move_events(player, clear: bool = True) -> List[Dict]:
    """Moves learned automatically by recent level-ups -> [{id, nickname, move, level}] (and forget them)."""
    out = []
    for mon in player.active_team:
        for ev in list(getattr(mon, "move_events", []) or []):
            out.append({"id": mon.id, "nickname": mon.nickname, **ev})
        if clear:
            mon.move_events = []
    return out
