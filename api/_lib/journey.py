"""
🗺️ POSHOW — Journey engine (Kanto first)

The journey is a graph of locations (towns and routes). You start in your home town, walk to the next
location, fight wild Pokémon on routes, heal in towns, and beat story trainers (gym leaders, rival,
Elite Four, Champion) to unlock the way forward. Everything is DATA below + a few small functions;
the web app and the Telegram bot are just two ways of showing the same state.

Player state lives in one dict, `player.story` (jsonb column `story`):
  mode        "journey" | "free_roam" (regions that don't have a map yet keep the old route-picker)
  location    current location id         last_town   where you wake up after a blackout
  visited     location ids you've been to  defeated    trainer ids you've beaten (story badges = defeated gyms)
  progress    {"trainer": id|None, "idx": n}  how far into a trainer's team you got
  starter     species you chose            complete    True once the region's Champion is beaten
"""

import random
from typing import Dict, List, Optional, Tuple

from pokemon_model import PokemonInstance
from moves_database import MOVES_DATABASE
from route_encounters import ALL_ROUTES

REGION_ORDER = ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "paldea"]

BADGES = ["Boulder Badge", "Cascade Badge", "Thunder Badge", "Rainbow Badge",
          "Soul Badge", "Marsh Badge", "Volcano Badge", "Earth Badge"]

# ── locations ─────────────────────────────────────────────────────────
# kind: "town" | "route".  encounter: key into route_encounters.ALL_ROUTES (wild Pokémon here).
# req (to ENTER): {"defeated": trainer_id} | {"gyms": n}.   heal: label of the healing spot, if any.
KANTO: Dict[str, Dict] = {
    "pallet_town": {"name": "Pallet Town", "kind": "town", "heal": "Mom's kitchen",
                    "desc": "A quiet town where your journey begins.",
                    "exits": ["route_1"]},
    "route_1": {"name": "Route 1", "kind": "route", "encounter": "route_1",
                "desc": "A short path through tall grass between Pallet Town and Viridian City.",
                "exits": ["pallet_town", "viridian_city"]},
    "viridian_city": {"name": "Viridian City", "kind": "town", "heal": "Pokémon Center",
                      "desc": "The city at the edge of the wild. Its gym stays shut for now.",
                      "exits": ["route_1", "route_2", "victory_road", "cinnabar_island"]},
    "route_2": {"name": "Route 2", "kind": "route", "encounter": "route_2",
                "desc": "Grass and trees lead north toward a dense forest.",
                "exits": ["viridian_city", "viridian_forest"]},
    "viridian_forest": {"name": "Viridian Forest", "kind": "route", "encounter": "viridian_forest",
                        "desc": "A maze of trees full of Bug Pokémon.",
                        "exits": ["route_2", "pewter_city"]},
    "pewter_city": {"name": "Pewter City", "kind": "town", "heal": "Pokémon Center",
                    "desc": "A grey stone city. Its gym trains the sturdy.",
                    "exits": ["viridian_forest", "route_3"]},
    "route_3": {"name": "Route 3", "kind": "route", "encounter": "route_3", "req": {"defeated": "brock"},
                "desc": "A rocky trail toward the mountains.",
                "exits": ["pewter_city", "route_4"]},
    "route_4": {"name": "Route 4", "kind": "route", "encounter": "route_4",
                "desc": "The trail drops out of the hills.",
                "exits": ["route_3", "cerulean_city"]},
    "cerulean_city": {"name": "Cerulean City", "kind": "town", "heal": "Pokémon Center",
                      "desc": "A city of rivers and bridges.",
                      "exits": ["route_4", "route_5"]},
    "route_5": {"name": "Route 5", "kind": "route", "encounter": "route_5", "req": {"defeated": "rival_1"},
                "desc": "A road south, busy with trainers.",
                "exits": ["cerulean_city", "route_6"]},
    "route_6": {"name": "Route 6", "kind": "route", "encounter": "route_6",
                "desc": "You can smell the sea ahead.",
                "exits": ["route_5", "vermilion_city"]},
    "vermilion_city": {"name": "Vermilion City", "kind": "town", "heal": "Pokémon Center",
                       "desc": "A harbour town with a great ship in port.",
                       "exits": ["route_6", "route_7"]},
    "route_7": {"name": "Route 7", "kind": "route", "encounter": "route_7", "req": {"defeated": "rival_2"},
                "desc": "A short road west.",
                "exits": ["vermilion_city", "celadon_city"]},
    "celadon_city": {"name": "Celadon City", "kind": "town", "heal": "Pokémon Center",
                     "desc": "A big, bright city that smells of flowers.",
                     "exits": ["route_7", "route_8"]},
    "route_8": {"name": "Route 8", "kind": "route", "encounter": "route_8", "req": {"defeated": "erika"},
                "desc": "The road bends toward the coast.",
                "exits": ["celadon_city", "fuchsia_city"]},
    "fuchsia_city": {"name": "Fuchsia City", "kind": "town", "heal": "Pokémon Center",
                     "desc": "A seaside town known for its safari.",
                     "exits": ["route_8", "route_9"]},
    "route_9": {"name": "Route 9", "kind": "route", "encounter": "route_9", "req": {"defeated": "koga"},
                "desc": "A winding path inland.",
                "exits": ["fuchsia_city", "route_10"]},
    "route_10": {"name": "Route 10", "kind": "route", "encounter": "route_10",
                 "desc": "Open ground below the great city.",
                 "exits": ["route_9", "saffron_city"]},
    "saffron_city": {"name": "Saffron City", "kind": "town", "heal": "Pokémon Center",
                     "desc": "The metropolis at the heart of the region.",
                     "exits": ["route_10", "cinnabar_island"]},
    "cinnabar_island": {"name": "Cinnabar Island", "kind": "town", "heal": "Pokémon Center",
                        "req": {"defeated": "sabrina"},
                        "desc": "A volcanic island reached by sea.",
                        "exits": ["saffron_city", "viridian_city"]},
    "victory_road": {"name": "Victory Road", "kind": "route", "encounter": "route_10",
                     "req": {"gyms": 8},
                     "desc": "The last road before the Pokémon League. Only trainers with eight badges are let in.",
                     "exits": ["viridian_city", "indigo_plateau"]},
    "indigo_plateau": {"name": "Indigo Plateau", "kind": "town", "heal": "League lobby",
                       "desc": "The Pokémon League. Four masters and a Champion wait inside.",
                       "exits": ["victory_road"]},
}

# Hunting grounds the existing code treats as "routes" but that live inside towns are not used here.

# ── trainers ──────────────────────────────────────────────────────────
STARTER_LINES = {"grass": ("ivysaur", "venusaur"), "fire": ("charmeleon", "charizard"), "water": ("wartortle", "blastoise")}
COUNTER = {"grass": "fire", "fire": "water", "water": "grass"}    # the rival picks what beats your starter


def _g(name, title, at, badge, team, coins, items=None, requires=None, intro="", win="", perfect=False):
    return {"name": name, "title": title, "kind": "gym", "at": at, "badge": badge, "team": team, "coins": coins,
            "items": items or {}, "requires": requires or {}, "intro": intro, "win": win, "perfect": perfect}


TRAINERS: Dict[str, Dict] = {
    "brock": _g("Brock", "Pewter City Gym Leader", "pewter_city", "Boulder Badge",
                [("geodude", 12), ("onix", 14)], 700, {"potion": 3},
                intro="I'm Brock! My rock-hard willpower is evident even in my Pokémon!",
                win="You've earned the Boulder Badge. Your bond with your Pokémon is solid."),
    "misty": _g("Misty", "Cerulean City Gym Leader", "cerulean_city", "Cascade Badge",
                [("staryu", 18), ("starmie", 21)], 1100, {"potion": 3},
                intro="My policy is an all-out offensive with Water-type Pokémon!",
                win="Fine. The Cascade Badge is yours."),
    "surge": _g("Lt. Surge", "Vermilion City Gym Leader", "vermilion_city", "Thunder Badge",
                [("voltorb", 21), ("pikachu", 18), ("raichu", 24)], 1500, {"superpotion": 2},
                intro="Hey, kid! My Electric Pokémon saved me during the war!",
                win="Now that's a shocking performance! Take the Thunder Badge."),
    "erika": _g("Erika", "Celadon City Gym Leader", "celadon_city", "Rainbow Badge",
                [("victreebel", 29), ("tangela", 24), ("vileplume", 29)], 2000, {"superpotion": 2},
                intro="I'm Erika. I love arranging flowers... and battling with Grass Pokémon.",
                win="I concede defeat. The Rainbow Badge is yours."),
    "koga": _g("Koga", "Fuchsia City Gym Leader", "fuchsia_city", "Soul Badge",
               [("koffing", 37), ("muk", 39), ("koffing", 37), ("weezing", 43)], 2600, {"superpotion": 3},
               intro="Fwahahaha! A trainer must master the art of the unseen!",
               win="Humph! You have proven your worth. The Soul Badge is yours."),
    "sabrina": _g("Sabrina", "Saffron City Gym Leader", "saffron_city", "Marsh Badge",
                  [("kadabra", 38), ("mr-mime", 37), ("venomoth", 38), ("alakazam", 43)], 3200, {"superpotion": 3},
                  intro="I had a vision of your arrival. I won't hold back.",
                  win="Your power... it's real. Take the Marsh Badge."),
    "blaine": _g("Blaine", "Cinnabar Island Gym Leader", "cinnabar_island", "Volcano Badge",
                 [("growlithe", 42), ("ponyta", 40), ("rapidash", 42), ("arcanine", 47)], 3800, {"superpotion": 3},
                 intro="Hah! I'm Blaine, the hot-headed leader! My fire will incinerate all challengers!",
                 win="I've burnt out! You've earned the Volcano Badge."),
    "giovanni": _g("Giovanni", "Viridian City Gym Leader", "viridian_city", "Earth Badge",
                   [("rhyhorn", 45), ("dugtrio", 42), ("nidoqueen", 44), ("nidoking", 45), ("rhydon", 50)], 4500,
                   {"rare_candy": 2}, requires={"gyms": 7}, perfect=True,
                   intro="So you've come this far. I am Giovanni, and this gym is the last test.",
                   win="Ha! That was a truly intense fight. The Earth Badge is yours."),
}

_RIVAL = {"name": "Blue", "kind": "rival", "badge": None, "perfect": False}
TRAINERS["rival_1"] = {**_RIVAL, "title": "Your rival", "at": "cerulean_city", "coins": 800, "items": {"superpotion": 1},
                       "requires": {"defeated": "misty"}, "team": "rival_1",
                       "intro": "Hey! Smell you later? Not yet — let's see how strong you've gotten!",
                       "win": "What?! Fine... but I'm going to be the Champion."}
TRAINERS["rival_2"] = {**_RIVAL, "title": "Your rival", "at": "vermilion_city", "coins": 1200, "items": {"superpotion": 2},
                       "requires": {"defeated": "surge"}, "team": "rival_2",
                       "intro": "Well, if it isn't you! Let's see what the ship's worth of training did for me!",
                       "win": "Tch. You're getting better. I'll beat you next time."}

_E4 = {"kind": "e4", "badge": None, "at": "indigo_plateau", "perfect": True}
TRAINERS["lorelei"] = {**_E4, "name": "Lorelei", "title": "Elite Four — Ice", "coins": 3000,
                       "team": [("dewgong", 54), ("cloyster", 53), ("slowbro", 54), ("jynx", 56), ("lapras", 56)],
                       "requires": {"gyms": 8}, "items": {},
                       "intro": "Welcome to the Pokémon League. No one can best my icy Pokémon!",
                       "win": "You're better than I thought. Go on."}
TRAINERS["bruno"] = {**_E4, "name": "Bruno", "title": "Elite Four — Fighting", "coins": 3000,
                     "team": [("onix", 53), ("hitmonchan", 55), ("hitmonlee", 55), ("onix", 56), ("machamp", 58)],
                     "requires": {"defeated": "lorelei"}, "items": {},
                     "intro": "I am Bruno of the Elite Four! We will grind you down with our superior power!",
                     "win": "Why? How could I lose? Go on, move on."}
TRAINERS["agatha"] = {**_E4, "name": "Agatha", "title": "Elite Four — Ghost", "coins": 3000,
                      "team": [("gengar", 56), ("golbat", 56), ("haunter", 55), ("arbok", 58), ("gengar", 60)],
                      "requires": {"defeated": "bruno"}, "items": {},
                      "intro": "I am Agatha. Battling is about heart. Let me see yours.",
                      "win": "You're something special. Go on, the last one waits."}
TRAINERS["lance"] = {**_E4, "name": "Lance", "title": "Elite Four — Dragon", "coins": 4000,
                     "team": [("gyarados", 58), ("dragonair", 56), ("dragonair", 56), ("aerodactyl", 60), ("dragonite", 62)],
                     "requires": {"defeated": "agatha"}, "items": {},
                     "intro": "I'm Lance, the dragon master. You'll have to be strong to face my Pokémon.",
                     "win": "I still can't believe my dragons lost. The Champion is next."}
TRAINERS["champion"] = {"name": "Blue", "title": "Pokémon League Champion", "kind": "champion", "at": "indigo_plateau",
                        "badge": None, "perfect": True, "coins": 8000, "items": {"rare_candy": 5, "exp_all": 1},
                        "requires": {"defeated": "lance"}, "team": "champion",
                        "intro": "I've been waiting for you! I beat the Elite Four to get here — now it's your turn.",
                        "win": "No... I lost? You are the new Champion."}

# Region story trainer ids that are "gym leaders" in order — used for the badge count + objective text.
GYM_ORDER = ["brock", "misty", "surge", "erika", "koga", "sabrina", "blaine", "giovanni"]
STORY_ORDER = ["brock", "misty", "rival_1", "surge", "rival_2", "erika", "koga", "sabrina", "blaine", "giovanni",
               "lorelei", "bruno", "agatha", "lance", "champion"]

JOURNEYS: Dict[str, Dict[str, Dict]] = {"kanto": KANTO}
START_LOCATION = {"kanto": "pallet_town"}


# ── starter helpers ───────────────────────────────────────────────────

def starter_type(species: Optional[str]) -> str:
    """grass / fire / water — from the position in the starter trio (every generation orders them that way)."""
    from onboarding import STARTERS
    for trio in STARTERS.values():
        for i, (sp, _) in enumerate(trio):
            if sp == species:
                return ("grass", "fire", "water")[i]
    return "grass"


def _team_for(trainer_id: str, player) -> List[Tuple[str, int]]:
    t = TRAINERS[trainer_id]
    spec = t["team"]
    if isinstance(spec, list):
        return spec
    mid, final = STARTER_LINES[COUNTER[starter_type(player.story.get("starter"))]]
    if spec == "rival_1":
        return [("pidgeotto", 18), ("abra", 15), ("rattata", 17), (mid, 18)]
    if spec == "rival_2":
        return [("pidgeotto", 19), ("raticate", 16), ("kadabra", 18), (mid, 20)]
    return [("pidgeot", 61), ("alakazam", 59), ("rhydon", 61), ("exeggutor", 61), ("gyarados", 61), (final, 63)]


# ── state ─────────────────────────────────────────────────────────────

def has_journey(region: Optional[str]) -> bool:
    return region in JOURNEYS


def init_story(player) -> Dict:
    region = player.current_region
    starter = player.story.get("starter") if player.story else None
    if not starter and player.active_team:
        starter = player.active_team[0].species_name
    if has_journey(region):
        loc = START_LOCATION[region]
        player.story = {"v": 1, "mode": "journey", "region": region, "starter": starter, "location": loc,
                        "last_town": loc, "visited": [loc], "defeated": [], "progress": {"trainer": None, "idx": 0},
                        "complete": False}
    else:
        player.story = {"v": 1, "mode": "free_roam", "region": region, "starter": starter}
    return player.story


def ensure_story(player) -> Dict:
    """Existing players (made before the journey existed) get a story the first time it's needed."""
    st = player.story or {}
    if st.get("v") != 1 or st.get("region") != player.current_region:
        init_story(player)
    return player.story


def _map(player) -> Dict[str, Dict]:
    return JOURNEYS[player.story["region"]]


def gyms_won(player) -> int:
    return sum(1 for g in GYM_ORDER if g in player.story.get("defeated", []))


def _req_ok(player, req: Optional[Dict]) -> Tuple[bool, Optional[str]]:
    if not req:
        return True, None
    if "defeated" in req and req["defeated"] not in player.story.get("defeated", []):
        who = TRAINERS[req["defeated"]]
        return False, f"Beat {who['name']} first"
    if "gyms" in req and gyms_won(player) < req["gyms"]:
        return False, f"Needs {req['gyms']} badges (you have {gyms_won(player)})"
    return True, None


def _challenges_here(player) -> List[Dict]:
    out = []
    here = player.story["location"]
    for tid, t in TRAINERS.items():
        if t["at"] != here:
            continue
        cleared = tid in player.story["defeated"]
        ok, why = _req_ok(player, t.get("requires"))
        team = _team_for(tid, player)
        out.append({
            "id": tid, "name": t["name"], "title": t["title"], "kind": t["kind"], "cleared": cleared,
            "available": ok and not cleared, "reason": None if cleared else why,
            "team_size": len(team), "top_level": max(lv for _, lv in team), "badge": t.get("badge"),
        })
    return out


def objective(player) -> str:
    if player.story.get("complete"):
        return "You are the Champion! Keep training, or take on the Battle Gym."
    for tid in STORY_ORDER:
        if tid in player.story["defeated"]:
            continue
        t = TRAINERS[tid]
        place = _map(player)[t["at"]]["name"]
        if t["kind"] == "gym":
            return f"Earn the {t['badge']}: beat {t['name']} in {place}"
        if t["kind"] == "rival":
            return f"Face your rival in {place}"
        return f"Take on {t['name']} at {place}"
    return ""


def state(player) -> Dict:
    st = ensure_story(player)
    base = {"mode": st["mode"], "region": st["region"]}
    if st["mode"] != "journey":
        return {**base, "location": None, "exits": [], "challenges": [], "badges": [], "objective": "",
                "complete": False, "can_scan": True, "pending": None}

    m = _map(player)
    here = m[st["location"]]
    exits = []
    for eid in here["exits"]:
        dest = m[eid]
        ok, why = _req_ok(player, dest.get("req"))
        exits.append({"id": eid, "name": dest["name"], "kind": dest["kind"], "locked": not ok, "reason": why})
    prog = st.get("progress") or {}
    return {
        **base,
        "location": {"id": st["location"], "name": here["name"], "kind": here["kind"], "desc": here["desc"],
                     "heal": here.get("heal"), "route_id": here.get("encounter")},
        "exits": exits,
        "challenges": _challenges_here(player),
        "badges": [TRAINERS[g]["badge"] for g in GYM_ORDER if g in st["defeated"]],
        "badge_count": gyms_won(player),
        "objective": objective(player),
        "complete": bool(st.get("complete")),
        "can_scan": bool(here.get("encounter")),
        "pending": ({"trainer": prog["trainer"], "idx": prog.get("idx", 0)} if prog.get("trainer") else None),
    }


class JourneyError(ValueError):
    pass


def current_encounter(player) -> Optional[str]:
    """Route id wild Pokémon come from at the player's location (None in towns). Only meaningful in journey mode."""
    st = ensure_story(player)
    if st["mode"] != "journey":
        return None
    return _map(player)[st["location"]].get("encounter")


def travel(player, to: str) -> Dict:
    st = ensure_story(player)
    if st["mode"] != "journey":
        raise JourneyError("This region has no journey map yet — use Scan to explore its routes.")
    m = _map(player)
    here = m[st["location"]]
    if to not in here["exits"]:
        raise JourneyError(f"You can't get to {m.get(to, {}).get('name', to)} from {here['name']}.")
    ok, why = _req_ok(player, m[to].get("req"))
    if not ok:
        raise JourneyError(f"{m[to]['name']} is closed: {why}.")
    st["location"] = to
    if to not in st["visited"]:
        st["visited"].append(to)
    if m[to]["kind"] == "town":
        st["last_town"] = to
    st["progress"] = {"trainer": None, "idx": 0}      # walking away abandons a half-finished challenge
    return state(player)


def heal(player) -> Dict:
    st = ensure_story(player)
    if st["mode"] != "journey":
        raise JourneyError("There's nowhere to rest here.")
    here = _map(player)[st["location"]]
    if not here.get("heal"):
        raise JourneyError("There's no Pokémon Center on a route — head to a town.")
    for mon in player.active_team:
        mon.restore_hp()
    st["progress"] = {"trainer": None, "idx": 0}
    return state(player)


# ── trainer battles ───────────────────────────────────────────────────

def trainer_moves(mon) -> List[str]:
    """A sensible moveset for a trainer's Pokémon. The species' default moves are just the first ten
    alphabetical PokeAPI entries ("absorb", "acid"...), which makes for toothless gym leaders."""
    types = []
    for t in (getattr(mon, "api_data", None) or {}).get("types", []):
        types.append((t if isinstance(t, str) else t.get("type", {}).get("name", "")).lower())
    cap = 55 if mon.level < 15 else 80 if mon.level < 30 else 95 if mon.level < 45 else 200
    pool = []
    for name, d in MOVES_DATABASE.items():
        power = d.get("power") or 0
        acc = d.get("accuracy", 100)
        acc = 100 if not isinstance(acc, (int, float)) else acc      # a few moves use "inf" (never miss)
        if power <= 0 or acc < 70 or power > cap:
            continue
        mtype = str(d.get("type", "normal")).lower()
        if mtype in types or mtype == "normal":
            pool.append((mtype in types, power, name))
    pool.sort(key=lambda x: (x[0], x[1]), reverse=True)
    stab = [n for s, _, n in pool if s][:3]
    rest = [n for s, _, n in pool if not s][:4 - len(stab)]
    picked = (stab + rest)[:4]
    return picked or ["tackle"]


def build_opponent(player, trainer_id: str, idx: int) -> Tuple[PokemonInstance, Dict]:
    team = _team_for(trainer_id, player)
    t = TRAINERS[trainer_id]
    species, level = team[idx]
    mon = PokemonInstance(species, level, 0)
    if t.get("perfect"):
        mon.iv = {k: 31 for k in mon.iv}
    mon.moves = trainer_moves(mon)
    mon.story_ref = {"t": trainer_id, "i": idx, "n": len(team)}
    mon.recalculate_stats()
    mon.restore_hp()
    meta = {"trainer": trainer_id, "name": t["name"], "title": t["title"], "kind": t["kind"],
            "idx": idx, "size": len(team), "intro": t["intro"], "badge": t.get("badge")}
    return mon, meta


def start_trainer(player, trainer_id: str) -> Tuple[PokemonInstance, Dict]:
    st = ensure_story(player)
    if st["mode"] != "journey":
        raise JourneyError("There are no story trainers in this region yet.")
    t = TRAINERS.get(trainer_id)
    if not t or t["at"] != st["location"]:
        raise JourneyError("That trainer isn't here.")
    if trainer_id in st["defeated"]:
        raise JourneyError(f"You already beat {t['name']}.")
    ok, why = _req_ok(player, t.get("requires"))
    if not ok:
        raise JourneyError(f"{t['name']} won't battle you yet: {why}.")
    prog = st.get("progress") or {}
    same = prog.get("trainer") == trainer_id
    idx = prog.get("idx", 0) if same else 0
    st["progress"] = {"trainer": trainer_id, "idx": idx, **({"exp": True} if same and prog.get("exp") else {})}
    return build_opponent(player, trainer_id, idx)


def next_opponent(player, trainer_id: str, idx: int) -> Optional[Tuple[PokemonInstance, Dict]]:
    """After one of the trainer's Pokémon is beaten: the next one, or None if that was the last."""
    team = _team_for(trainer_id, player)
    if idx + 1 >= len(team):
        return None
    old = player.story.get("progress") or {}
    player.story["progress"] = {"trainer": trainer_id, "idx": idx + 1, **({"exp": True} if old.get("exp") else {})}
    return build_opponent(player, trainer_id, idx + 1)


def trainer_won(player, trainer_id: str) -> Dict:
    st = player.story
    t = TRAINERS[trainer_id]
    if trainer_id not in st["defeated"]:
        st["defeated"].append(trainer_id)
    st["progress"] = {"trainer": None, "idx": 0}

    player.add_coins(t["coins"])
    for item, qty in t["items"].items():
        player.add_item(item, qty)
    if t.get("badge") and t["badge"] not in player.badges:
        player.badges.append(t["badge"])

    unlocked = None
    if trainer_id == "champion":
        st["complete"] = True
        if "hall_of_fame" not in player.achievements:
            player.achievements.append("hall_of_fame")
        nxt = REGION_ORDER[REGION_ORDER.index(st["region"]) + 1] if st["region"] in REGION_ORDER[:-1] else None
        if nxt and nxt not in player.regions_unlocked:
            player.regions_unlocked.append(nxt)
            unlocked = nxt
    return {"won": True, "trainer": trainer_id, "name": t["name"], "win": t["win"], "coins": t["coins"],
            "items": dict(t["items"]), "badge": t.get("badge"), "complete": bool(st.get("complete")),
            "unlocked_region": unlocked, "badge_count": gyms_won(player)}


def trainer_lost(player) -> Dict:
    """The fighter fainted. Anyone left standing can keep going; a full wipe sends you home."""
    st = player.story
    prog = st.get("progress") or {}
    tid = prog.get("trainer")
    alive = [m for m in player.active_team if not m.is_fainted and m.current_hp > 0]
    if alive:
        return {"won": False, "blackout": False, "remaining": len(alive), "trainer": tid}
    for m in player.active_team:
        m.restore_hp()
    st["location"] = st.get("last_town") or START_LOCATION.get(st["region"], st["location"])
    st["progress"] = {"trainer": None, "idx": 0}
    where = _map(player)[st["location"]]["name"]
    return {"won": False, "blackout": True, "remaining": 0, "trainer": tid, "location": where}
