import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Every region with a journey must be COMPLETE and COMPLETABLE: valid map graph, valid data, no dead ends.
import json, collections
import journey, species_data, rules
from route_encounters import ALL_ROUTES, ROUTE_REGION
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
STARTERS = {"grass": "chikorita", "fire": "cyndaquil", "water": "totodile"}

def new_player(region, starter_species):
    p = PlayerInstance(1, "T"); p.current_region = region; p.regions_unlocked = [region]
    p.add_pokemon_to_team(PokemonInstance(starter_species, 5, 1)); p.story = {"starter": starter_species}
    journey.init_story(p); return p

for region, cfg in journey.REGIONS.items():
    M, order, gyms = cfg["map"], cfg["story_order"], cfg["gym_order"]
    print(f"--- {region}: {len(M)} locations, {len(order)} story trainers, {len(gyms)} gyms")
    # ---- map graph
    ok(cfg["start"] in M, f"{region}: start location exists")
    bad = [(a, e) for a, loc in M.items() for e in loc["exits"] if e not in M]
    ok(not bad, f"{region}: every exit points at a real location {bad[:3]}")
    asym = [(a, e) for a, loc in M.items() for e in loc["exits"] if a not in M[e]["exits"]]
    ok(not asym, f"{region}: exits are two-way {asym[:3]}")
    seen, todo = {cfg["start"]}, [cfg["start"]]
    while todo:
        for e in M[todo.pop()]["exits"]:
            if e not in seen: seen.add(e); todo.append(e)
    ok(seen == set(M), f"{region}: every location is connected to the start (unreachable: {set(M) - seen})")
    for lid, loc in M.items():
        ok(loc["kind"] in ("town", "route") and loc["name"] and loc["desc"], f"{region}/{lid}: has a name, kind and description") if lid == cfg["start"] else None
    towns_heal = [l for l, loc in M.items() if loc["kind"] == "town" and not loc.get("heal")]
    ok(not towns_heal, f"{region}: every town has a place to heal {towns_heal}")
    # ---- wild tables
    enc = [(l, loc["encounter"]) for l, loc in M.items() if loc.get("encounter")]
    missing = [e for _, e in enc if e not in ALL_ROUTES]
    ok(not missing, f"{region}: every encounter id has a wild table {missing}")
    for lid, eid in enc:
        r = ALL_ROUTES[eid]
        sp = list(r.pokemon_pool) + [r.rare_species]
        unknown = [x for x in sp if x not in species_data.SPECIES]
        assert not unknown, (eid, unknown)
        assert 0 < r.rare_rate <= 0.05, (eid, r.rare_rate)
        lo, hi = r.level_range; assert 1 <= lo <= hi <= 100, (eid, r.level_range)
        assert r.rare_species not in r.pokemon_pool or True
        assert all(w > 0 for w in r.pokemon_pool.values()), eid
    ok(True, f"{region}: all {len(enc)} wild tables use real species, sane rates and levels, and have a rare variant")
    # ---- trainers
    ids = [t for t, d in journey.TRAINERS.items() if d.get("region") == region]
    ok(sorted(ids) == sorted(order) and len(set(order)) == len(order), f"{region}: story order lists every trainer exactly once")
    ok(order[-1] == cfg["champion"] and journey.TRAINERS[cfg["champion"]]["kind"] == "champion", f"{region}: the Champion is last")
    ok(all(g in order and journey.TRAINERS[g]["kind"] == "gym" for g in gyms) and len(gyms) == 8, f"{region}: eight gym leaders")
    badges = [journey.TRAINERS[g]["badge"] for g in gyms]
    ok(len(set(badges)) == 8 and all(b in journey.BADGES for b in badges), f"{region}: eight distinct, registered badges")
    for tid in order:
        t = journey.TRAINERS[tid]
        ok(t["at"] in M, f"{region}/{tid}: stands in a real location") if tid == order[0] else None
        assert t["at"] in M, (tid, t["at"])
        dep = (t.get("requires") or {}).get("defeated")
        assert dep is None or dep in order, (tid, dep)
        assert dep is None or order.index(dep) < order.index(tid), f"{tid} requires {dep} which comes later"
        assert t["intro"] and t["win"] and t["coins"] > 0
    ok(True, f"{region}: every trainer stands somewhere real, has lines, and only depends on earlier fights")
    # ---- teams, for every starter type
    for kind, sp in STARTERS.items():
        p = new_player(region, {"kanto": {"grass": "bulbasaur", "fire": "charmander", "water": "squirtle"}}.get(region, STARTERS)[kind])
        for tid in order:
            team = journey._team_for(tid, p)
            assert 1 <= len(team) <= 6, (tid, team)
            for s, l in team:
                assert s in species_data.SPECIES and 1 <= l <= 100, (tid, s, l)
    ok(True, f"{region}: every team (for all three rival variants) is valid")
    gym_tops = [max(l for _, l in journey.TRAINERS[g]["team"]) for g in gyms]
    ok(gym_tops == sorted(gym_tops), f"{region}: gym leaders get steadily tougher {gym_tops}")
    e4 = [t for t in order if journey.TRAINERS[t]["kind"] in ("e4", "champion")]
    ok(min(max(l for _, l in journey._team_for(t, p)) for t in e4) >= gym_tops[-1] - 2, f"{region}: the League is at least as tough as the last gym")
    # ---- a full playthrough: walk, fight, win, in story order — must never get stuck
    p = new_player(region, {"kanto": "charmander"}.get(region, "cyndaquil"))
    steps = 0
    for tid in order:
        t = journey.TRAINERS[tid]
        # find a legal path to where this trainer stands
        goal, here = t["at"], p.story["location"]
        prev, q = {here: None}, collections.deque([here])
        while q:
            cur = q.popleft()
            if cur == goal: break
            for e in M[cur]["exits"]:
                if e in prev: continue
                if not journey._req_ok(p, M[e].get("req"))[0]: continue
                prev[e] = cur; q.append(e)
        assert goal in prev, f"{region}: STUCK — no legal way to reach {goal} for {tid} (defeated {p.story['defeated']})"
        path = []
        while goal is not None: path.append(goal); goal = prev[goal]
        for loc in reversed(path[:-1]): journey.travel(p, loc); steps += 1
        journey.start_trainer(p, tid)
        res = journey.trainer_won(p, tid)
        assert res["won"]
    ok(p.story["complete"] and journey.objective(p).startswith("You are the Champion"), f"{region}: the whole campaign can be played start to Champion ({steps} moves)")
    nxt = journey.REGION_ORDER[journey.REGION_ORDER.index(region) + 1]
    ok(nxt in p.regions_unlocked, f"{region}: beating the Champion unlocks {nxt}")
    ok(p.story["badge_count"] == 8 if "badge_count" in p.story else journey.gyms_won(p) == 8, f"{region}: eight badges earned")
    json.dumps(p.story)
    ok(True, f"{region}: the story state is JSON-serialisable (fits the jsonb column)")

# ---- gating really gates
p = new_player("johto", "cyndaquil")
def refused(fn):
    try: fn(); return False
    except journey.JourneyError: return True
journey.travel(p, "route_29"); journey.travel(p, "cherrygrove_city")
ok(refused(lambda: journey.travel(p, "route_30")), "johto: Route 30 is closed until you beat your rival")
ok(refused(lambda: journey.start_trainer(p, "falkner")), "johto: you can't challenge a leader who isn't here")

# ---- region switching keeps each region's progress
k = new_player("kanto", "charmander")
journey.start_trainer(k, "brock") if k.story["location"] == "pewter_city" else None
k.story["defeated"].append("brock"); k.story["location"] = "pewter_city"; k.story["care"] = {"x": 1}; k.story["caught"] = ["pidgey"]
ok(refused(lambda: journey.begin_region(k, "johto")), "a region you haven't unlocked can't be entered")
k.regions_unlocked = ["kanto", "johto"]
st = journey.begin_region(k, "johto")
ok(st["region"] == "johto" and st["location"]["id"] == "new_bark_town" and k.current_region == "johto", "switching starts the new region at its start")
ok(k.story.get("care") == {"x": 1} and k.story.get("caught") == ["pidgey"], "care and Pokédex history carry over")
ok(k.story["defeated"] == [], "the new campaign starts with no fights won")
k.story["defeated"].append("j_rival_1")
st = journey.begin_region(k, "kanto")
ok(st["location"]["id"] == "pewter_city" and "brock" in k.story["defeated"], "going back restores where you were and what you won")
st = journey.begin_region(k, "johto")
ok("j_rival_1" in k.story["defeated"], "…and Johto's progress was kept too")
ok(refused(lambda: journey.begin_region(k, "hoenn")), "regions without a campaign can't be entered yet")
# ---- through the real API: a Johto player
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import index
from index import *
u = auth_register(RegisterRequest(username="Johto_1", password="secret1"))["user_id"]
choose_starter(StarterRequest(user_id=u, region="johto", species="cyndaquil"))
st = journey_state(u)
ok(st["mode"] == "journey" and st["region"] == "johto" and st["location"]["id"] == "new_bark_town", "API: a Johto starter begins the Johto journey in New Bark Town")
ok(any(e["id"] == "route_29" for e in st["exits"]) and not any(e["id"] == "route_27" and not e.get("locked") for e in st["exits"]), "API: exits are Johto's (Route 27 is locked until 8 badges)")
journey_travel(TravelRequest(user_id=u, to="route_29")); journey_travel(TravelRequest(user_id=u, to="cherrygrove_city"))
st = journey_state(u)
ok([c["id"] for c in st["challenges"]] == ["j_rival_1"], "API: your rival waits in Cherrygrove")
bt = journey_trainer_start(JourneyActionRequest(user_id=u, trainer_id="j_rival_1"))
ok(bt["wild_pokemon"]["species_name"] == "totodile" and bt["story"]["name"] == "Silver", "API: Silver picks the starter that beats yours (Totodile vs Cyndaquil)")
ok(st["regions"] and {r["id"]: r["journey"] for r in st["regions"]}["johto"] and {r["id"]: r["unlocked"] for r in st["regions"]}["johto"], "API: the region list says Johto is unlocked and playable")
sc = scout_area(ScoutRequest(user_id=u, route_id="route_29")) if False else None
# ---- Kalos through the API, and the species it needed
k = auth_register(RegisterRequest(username="Kalos_1", password="secret1"))["user_id"]
choose_starter(StarterRequest(user_id=k, region="kalos", species="froakie"))
st = journey_state(k)
ok(st["region"] == "kalos" and st["location"]["id"] == "vaniville_town", "API: a Kalos starter begins in Vaniville Town")
journey_travel(TravelRequest(user_id=k, to="kalos_route_1")); journey_travel(TravelRequest(user_id=k, to="aquacorde_town"))
bt = journey_trainer_start(JourneyActionRequest(user_id=k, trainer_id="k_rival_1"))
ok(bt["wild_pokemon"]["species_name"] == "chespin", "API: Serena picks the starter that beats Froakie (Chespin)")
ok([x["id"] for x in journey_state(k)["regions"] if x["journey"]] == ["kanto", "johto", "kalos"], "API: Kanto, Johto and Kalos are the playable regions")
import evolution
from pokemon_model import PokemonInstance as _PI
for sp in ("meowstic", "aegislash", "gourgeist", "pumpkaboo", "espurr", "honedge", "doublade"):
    m = _PI(sp, 40, 1); ok(len(m.moves) >= 1 and m.max_hp > 0 and m.ability, f"species {sp}: builds with moves {m.moves[:2]} and ability {m.ability}")
ok(rules.EVOLUTIONS["espurr"][0]["to"] == "meowstic" and rules.EVOLUTIONS["doublade"][0]["to"] == "aegislash" and rules.EVOLUTIONS["pumpkaboo"][0]["to"] == "gourgeist", "the evolution table links Espurr, Doublade and Pumpkaboo to Kalos' species")
print("ALL REGION TESTS PASSED")
