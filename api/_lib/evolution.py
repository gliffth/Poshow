"""
Evolution (level, evolution stones, Trade Cable)

Evolution data comes from the PokeDex (compiled into data/evolutions.json). A Pokémon evolves when:
  * level : it has reached the level
  * item  : the player owns the stone / item (it is used up)
  * trade : the player owns a Trade Cable (used up) — the cable stands in for a trade, so species that
            evolve by trade (Kadabra, Machoke, Graveler, Haunter, Onix + Metal Coat…) can evolve solo
Evolving keeps the Pokémon's identity (id, IVs/EVs, nature, shininess, XP, moves, nickname if custom).
"""

from typing import Dict, List, Optional

import rules
from pokemon_model import PokemonInstance

STONES = ["fire_stone", "water_stone", "thunder_stone", "leaf_stone", "moon_stone", "sun_stone",
          "shiny_stone", "dusk_stone", "dawn_stone", "ice_stone"]
TRADE_ITEM = "trade_cable"
SHOP_PRICES = {s: 800 for s in STONES}
SHOP_PRICES[TRADE_ITEM] = 1500


def options(player, mon) -> List[Dict]:
    out = []
    for e in rules.evolutions_for(mon.species_name):
        kind, need = e["rule"][0], e["rule"][1] if len(e["rule"]) > 1 else None
        if kind == "level":
            ready, label = mon.level >= need, f"Lv {need}"
        elif kind == "item":
            ready, label = player.inventory.get(need, 0) > 0, str(need).replace("_", " ").title()
        else:
            ready, label = player.inventory.get(TRADE_ITEM, 0) > 0, "Trade Cable"
        out.append({"to": e["to"], "kind": kind, "need": need, "label": label, "ready": bool(ready)})
    return out


def pending(player) -> List[str]:
    """Pokémon on the team that can evolve right now by level."""
    return [m.id for m in player.active_team if any(o["ready"] and o["kind"] == "level" for o in options(player, m))]


def _find(player, mon_id: str):
    for lst in (player.active_team, player.pokemon_collection):
        for i, m in enumerate(lst):
            if m.id == mon_id:
                return lst, i, m
    return None, -1, None


def evolve(player, mon_id: str, to: str) -> Dict:
    lst, idx, mon = _find(player, mon_id)
    if mon is None:
        return {"ok": False, "message": "That Pokémon isn't yours."}
    choice = next((o for o in options(player, mon) if o["to"] == to), None)
    if not choice:
        return {"ok": False, "message": f"{mon.nickname} can't evolve into {to}."}
    if not choice["ready"]:
        return {"ok": False, "message": f"{mon.nickname} isn't ready: needs {choice['label']}."}

    old_name = mon.species_name
    new = PokemonInstance(to, mon.level, mon.trainer_id)
    # keep who it is
    new.id = mon.id
    new.ability = new._resolve_ability()      # abilities derive from the (kept) id, not the throw-away one
    new.iv, new.ev, new.nature = mon.iv, mon.ev, mon.nature
    new.is_shiny = mon.is_shiny
    new.experience = mon.experience
    new.moves = list(mon.moves)
    new.pending_moves = list(getattr(mon, 'pending_moves', []))
    # The evolved form's own level-up moves: fill FREE slots with the most recent ones it knows at this level
    # (never overwrites a move the player has; a full moveset is left alone).
    try:
        import species_data, rules
        known = set(new.moves) | set(new.pending_moves)
        fresh = sorted(((lv, mv) for lv, mv in species_data.learnset(to)
                        if lv <= mon.level and mv in rules.MOVE_DATA and mv not in known), reverse=True)
        for _lv, mv in fresh:
            if len(new.moves) >= 4:
                break
            if mv not in new.moves:
                new.moves.append(mv)
    except Exception:                      # a missing learnset must never block an evolution
        pass
    new.status = mon.status
    custom_name = mon.nickname and mon.nickname.lower() != old_name.lower()
    if custom_name:
        new.nickname = mon.nickname
    ratio = mon.current_hp / max(1, mon.max_hp)
    new.recalculate_stats()
    new.current_hp = max(1 if mon.current_hp > 0 else 0, int(new.max_hp * ratio))
    new.is_fainted = mon.is_fainted and new.current_hp <= 0

    if choice["kind"] == "item":
        player.remove_item(choice["need"], 1)
    elif choice["kind"] == "trade":
        player.remove_item(TRADE_ITEM, 1)
    lst[idx] = new
    dex = (new.api_data or {}).get("id")
    if dex:
        player.pokedex_seen.add(dex)
    player.record_caught(old_name)      # the old form stays in the Pokédex history (this also backfills old saves)
    player.record_caught(to)
    return {"ok": True, "from": old_name, "to": to, "level": new.level,
            "message": f"What? {old_name.title()} is evolving… Congratulations! It became {to.title()}!"}
