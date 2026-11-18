import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Battle formats, team selection, preview, queue, turn ids, timers, ratings: the engine and the API on top of it.
import asyncio, random, threading, time
import index
from index import *
import pvp_formats as F
import pvp_system as P
import notifier
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
    except P.PvpError: return 400
random.seed(11)
index.notify_telegram = lambda *a, **k: None
def user(name, mons):
    u = auth_register(RegisterRequest(username=name, password="secret1")); uid = u["user_id"]
    p = get_or_create_player(uid)
    for i, (sp, lv) in enumerate(mons):
        m = PokemonInstance(sp, lv, uid)
        (p.add_pokemon_to_team if i < 6 else p.pokemon_collection.append)(m)
    persist_player(p)
    return uid, {"authorization": "Bearer " + u["token"]}
SIX = [("charmander", 30), ("pidgey", 28), ("rattata", 25), ("geodude", 27), ("zubat", 26), ("machop", 24)]
ua, ha = user("Ash_F", SIX + [("squirtle", 50)])
ub, hb = user("Gary_F", [("bulbasaur", 30), ("pikachu", 29), ("eevee", 27), ("abra", 26), ("gastly", 25), ("growlithe", 24)])
uc, hc = user("Misty_F", [("psyduck", 20)])
pa, pb = get_or_create_player(ua), get_or_create_player(ub)
ida = [m.id for m in pa.active_team]; idb = [m.id for m in pb.active_team]
big = pa.pokemon_collection[0].id

# ── formats and validation ──
ok([f["id"] for f in pvp_formats_list()["formats"]] == ["quick_duel", "singles_3v3", "singles_6v6", "friendly"], "four formats are offered (the classic duel is not listed)")
sel = lambda fmt, ids, p=pa, **kw: F.check_selection(p, F.get(fmt), ids, **kw)
def bad(fn):
    try: fn(); return None
    except F.FormatError as e: return str(e)
ok(len(sel("singles_3v3", ida[:5])) == 5, "3v3 lets you bring up to six")
ok("at most 6" in (bad(lambda: sel("singles_3v3", ida + [big])) or ""), "…but not seven")
ok("exactly 6" in (bad(lambda: sel("singles_6v6", ida[:5])) or ""), "6v6 needs a full six")
ok("at most 1" in (bad(lambda: sel("quick_duel", ida[:2])) or ""), "a Quick Duel is one Pokémon")
ok("isn't yours" in (bad(lambda: sel("singles_3v3", ida[:2] + idb[:1])) or ""), "someone else's Pokémon are refused")
ok("twice" in (bad(lambda: sel("singles_3v3", [ida[0], ida[0]])) or ""), "the same Pokémon twice is refused")
ok(bad(lambda: sel("singles_3v3", ["nope"])) and bad(lambda: sel("singles_3v3", [])) and bad(lambda: sel("singles_3v3", "x")), "junk and empty selections are refused")
pa.pokemon_collection.append(PokemonInstance("charmander", 12, ua))
dup = [ida[0], pa.pokemon_collection[-1].id]
ok("Only one" in (bad(lambda: sel("singles_3v3", dup)) or ""), "the species clause: one of each")
cap = F.with_rules(F.get("friendly"), {"pick": 3, "level_cap": 29})
ok("over the level 29" in (bad(lambda: F.check_selection(pa, cap, ida[:2])) or ""), "a level cap refuses stronger Pokémon (level 30 vs cap 29)")
nohold = F.with_rules(F.get("friendly"), {"held_items": False})
pa.active_team[3].held_item = "oran-berry"
ok("Held items" in (bad(lambda: F.check_selection(pa, nohold, [ida[3]])) or ""), "banning held items refuses a Pokémon that holds one")
pa.active_team[3].held_item = None
ok(bad(lambda: F.with_rules(F.get("friendly"), {"pick": 9})) and bad(lambda: F.with_rules(F.get("friendly"), {"level_cap": 2})), "friendly rules stay inside their limits")
ok(F.with_rules(F.get("quick_duel"), {"pick": 6}) == F.get("quick_duel"), "ranked formats ignore custom rules")
rows = {r["id"]: r for r in F.describe(pa, cap)}
ok(rows[big]["eligible"] is False and rows[big]["reasons"] and rows[ida[1]]["eligible"], "the builder gets a verdict and a reason for every Pokémon")
ok(rows[ida[0]]["moves"] and rows[ida[0]]["types"] and rows[ida[0]]["dex_id"], "…with moves, types and its Pokédex number for the sprite")
pa.pokemon_collection.pop()

# the collection endpoint and the browser never decides legality
c = pvp_collection(ua, "singles_3v3", authorization=ha["authorization"])
ok(len(c["pokemon"]) == 7 and all("eligible" in r for r in c["pokemon"]), "collection endpoint lists the whole collection (team + stored)")
ok(code(lambda: pvp_collection(ua, "nope", authorization=ha["authorization"])) == 400, "unknown format is 400")
cc = pvp_collection(ua, "friendly", level_cap=29, authorization=ha["authorization"])
ok(any(not r["eligible"] and "level 29" in r["reasons"][0] for r in cc["pokemon"]) and cc["format"]["level_cap"] == 29, "a friendly battle's own level cap is applied to the verdicts")
ok(code(lambda: pvp_collection(ua, "friendly", level_cap=2, authorization=ha["authorization"])) == 400, "custom rules outside their limits are refused")
index.REQUIRE_AUTH = True
ok(code(lambda: pvp_collection(ua, "singles_3v3", authorization=hb["authorization"])) == 403 and code(lambda: pvp_collection(ua, "singles_3v3", authorization=None)) == 401, "you can't read another player's collection")
ok(code(lambda: pvp_collection(ua, "singles_3v3", authorization=ha["authorization"])) == 200, "…but you can read your own")
index.REQUIRE_AUTH = False

# ── saved teams ──
r = pvp_save_team(PvpTeamRequest(user_id=ua, name="  My   Squad ", format_id="singles_3v3", ids=ida[:3]), ha["authorization"])
ok(r["teams"][0]["name"] == "My Squad", "a team preset is saved (name tidied)")
ok(code(lambda: pvp_save_team(PvpTeamRequest(user_id=ua, name="x", format_id="singles_3v3", ids=idb[:2]), ha["authorization"])) == 400, "a preset with someone else's Pokémon is refused")
ok(code(lambda: pvp_save_team(PvpTeamRequest(user_id=ua, name="", format_id="singles_3v3", ids=ida[:2]), ha["authorization"])) == 400, "a preset needs a name")
pvp_save_team(PvpTeamRequest(user_id=ua, name="my squad", format_id="singles_6v6", ids=ida), ha["authorization"])
prof = pvp_profile(ua, ha["authorization"])
ok(len(prof["teams"]) == 1 and prof["teams"][0]["format_id"] == "singles_6v6", "saving under the same name replaces the preset")
for i in range(12):
    try: pvp_save_team(PvpTeamRequest(user_id=ua, name=f"t{i}", format_id="singles_3v3", ids=ida[:3]), ha["authorization"])
    except HTTPException: pass
ok(len(pvp_profile(ua, ha["authorization"])["teams"]) == P.MAX_PRESETS, "at most ten presets")
pvp_delete_team(ua, "t0", ha["authorization"])
ok(all(t["name"] != "t0" for t in pvp_profile(ua, ha["authorization"])["teams"]), "a preset can be deleted")
get_or_create_player(ua).pokemon_collection.append(PokemonInstance("pidgey", 5, ua))
pa = get_or_create_player(ua); pa.story["pvp"]["teams"].append({"name": "ghost", "format_id": "singles_3v3", "ids": ["gone"]}); persist_player(pa)
ok(any(t["name"] == "ghost" and t["stale"] for t in pvp_profile(ua, ha["authorization"])["teams"]), "a preset naming a Pokémon you no longer have is flagged stale")

# ── Quick Duel through the queue ──
lead = pa.active_team[2].id                                                  # NOT the first Pokémon on the team
q = pvp_queue_join(PvpQueueRequest(user_id=ua, format_id="quick_duel", ids=[lead]), ha["authorization"])
ok(q["matched"] is False and q["queue"]["status"] == "queued", "joining the queue with nobody waiting just waits")
ok(code(lambda: pvp_queue_join(PvpQueueRequest(user_id=ua, format_id="friendly", ids=[lead]), ha["authorization"])) == 400, "friendly battles have no queue")
ok(code(lambda: pvp_queue_join(PvpQueueRequest(user_id=ub, format_id="quick_duel", ids=idb[:2]), hb["authorization"])) == 400, "a Quick Duel queue entry with two Pokémon is refused")
m = pvp_queue_join(PvpQueueRequest(user_id=ub, format_id="quick_duel", ids=[idb[4]]), hb["authorization"])
ok(m["matched"] and m["match"]["status"] == "active" and m["match"]["format"]["id"] == "quick_duel", "a second player in the same format is matched at once")
v = m["match"]
ok(len(v["me"]["team"]) == 1 and v["me"]["team"][0]["species"] == "gastly", "you fight with the Pokémon you chose, not the first on your team")
sa = pvp_state(ua, authorization=ha["authorization"])
ok(sa["active"]["me"]["team"][0]["nickname"].lower() == pa.active_team[2].nickname.lower() and sa["queue"] is None, "the waiting player is told the match started and the queue entry is gone")
mid = v["id"]
ok(code(lambda: pvp_queue_join(PvpQueueRequest(user_id=uc, format_id="quick_duel", ids=[get_or_create_player(uc).active_team[0].id]), hc["authorization"])) == 200, "a third player can queue while others fight")
pvp_queue_leave(PvpQueueRequest(user_id=uc), hc["authorization"])
ok(pvp_state(uc, authorization=hc["authorization"])["queue"] is None, "leaving the queue removes the entry")

# full health, real Pokémon untouched
hp0 = pa.active_team[2].current_hp
doc = index._pvp.load(mid)
ok(doc["state"]["sides"]["a"]["team"][0]["current_hp"] == doc["state"]["sides"]["a"]["team"][0]["max_hp"], "battle copies start at full health")

# ── turn ids and retries ──
act = lambda uid, h, action, **kw: pvp_action(PvpActionRequest(user_id=uid, match_id=mid, action=action, **kw), h["authorization"])
mv = lambda who: who["me"]["team"][who["me"]["active"]]["moves"][0]["id"]
va = pvp_state(ua, authorization=ha["authorization"])["active"]; vb = pvp_state(ub, authorization=hb["authorization"])["active"]
t = va["turn"]; seq0 = va["seq"]
act(ua, ha, {"type": "move", "move": mv(va)}, turn=t, request_id="r1")
ok(pvp_state(ua, authorization=ha["authorization"])["active"]["seq"] > seq0 and pvp_state(ua, authorization=ha["authorization"])["active"]["waiting"], "choosing a move acknowledges at once and shows waiting")
again = act(ua, ha, {"type": "move", "move": mv(va)}, turn=t, request_id="r1")
ok(again["waiting"], "the same request sent twice is harmless")
ok(code(lambda: act(ua, ha, {"type": "move", "move": mv(va)}, turn=t, request_id="r2")) == 400, "a different second request this turn is refused")
act(ub, hb, {"type": "move", "move": mv(vb)}, turn=t, request_id="q1")
now = pvp_state(ua, authorization=ha["authorization"])["active"]
ok(now["turn"] > t or now["status"] == "finished", "both chose -> the turn resolved")
ok(code(lambda: act(ua, ha, {"type": "move", "move": mv(va)}, turn=t, request_id="r9")) == 400, "an action for a turn that already resolved is refused")
r = act(ua, ha, {"type": "move", "move": mv(va)}, turn=t, request_id="r1")
ok(r["turn"] == now["turn"], "a late retry of an action that already went through returns the current state, not an error")
ok(pvp_state(ua, since=now["seq"], authorization=ha["authorization"]).get("unchanged") is True, "state with the current seq is a tiny 'unchanged' reply")
ok(pvp_state(ua, since=now["seq"] - 1, authorization=ha["authorization"]).get("active"), "state with an old seq returns the full match")

# finish it, check rating
guard = 0
while pvp_state(ua, authorization=ha["authorization"])["active"]["status"] == "active" and guard < 200:
    guard += 1
    for uid, h in ((ua, ha), (ub, hb)):
        cur = pvp_state(uid, authorization=h["authorization"])["active"]
        if cur["status"] != "active" or cur["waiting"]: continue
        act(uid, h, {"type": "move", "move": mv(cur)}, turn=cur["turn"], request_id=f"{guard}{uid}")
fin = pvp_state(ua, authorization=ha["authorization"])["active"]
ok(fin["status"] == "finished" and fin["winner"] in "ab", "the Quick Duel plays to a result")
winner_uid = ua if fin["winner"] == fin["you"] else ub
W, L = get_or_create_player(winner_uid), get_or_create_player(ub if winner_uid == ua else ua)
ok(P.rating_of(W, "quick_duel")["elo"] > 1000 and P.rating_of(L, "quick_duel")["elo"] < 1000, "the winner's Quick Duel rating rose and the loser's fell")
ok(P.rating_of(W, "singles_3v3")["elo"] == 1000 and W.elo > 1000, "…other formats' ratings are separate; the overall rating moved")
ok(W.story["pvp"]["history"][-1]["won"] and not L.story["pvp"]["history"][-1]["won"], "both players have the battle in their history")
ok((W.wins, L.losses) == (1, 1) or (W.wins >= 1 and L.losses >= 1), "wins and losses recorded")
prof = pvp_profile(winner_uid, ha["authorization"] if winner_uid == ua else hb["authorization"])
ok(prof["history"][0]["format"] == "quick_duel" and prof["ratings"]["quick_duel"]["w"] == 1, "the profile shows the history (newest first) and per-format record")
ok(pa.active_team[2].current_hp == hp0, "your real Pokémon were not touched")

# ── 3v3 with team preview ──
def clean():
    for uid in (ua, ub, uc):
        for d in index._pvp.for_user(uid, ["active", "pending", "queued", "finished", "abandoned"]): index._pvp.delete(d["id"])
clean()
qa = pvp_queue_join(PvpQueueRequest(user_id=ua, format_id="singles_3v3", ids=ida), ha["authorization"])
mb = pvp_queue_join(PvpQueueRequest(user_id=ub, format_id="singles_3v3", ids=idb), hb["authorization"])
v = mb["match"]; mid = v["id"]
ok(v["phase"] == "preview" and v["needs_pick"] and len(v["me"]["team"]) == 6, "6 brought -> team preview, you see your six")
ok(all(set(r) <= {"species", "level", "dex_id", "moves"} and r["moves"] == [] for r in v["foe"]["team"]) and len(v["foe"]["team"]) == 6, "…and only species and level of the opponent's six")
ok(code(lambda: act(ub, hb, {"type": "move", "move": "tackle"})) == 400, "no moves during preview")
ok(code(lambda: act(ub, hb, {"type": "pick", "order": [0, 1]})) == 400 and code(lambda: act(ub, hb, {"type": "pick", "order": [0, 0, 1]})) == 400 and code(lambda: act(ub, hb, {"type": "pick", "order": [0, 1, 9]})) == 400, "wrong picks (too few, repeated, out of range) are refused")
r = act(ub, hb, {"type": "pick", "order": [4, 2, 0]}, request_id="p1")
ok(r["waiting"] and r["phase"] == "preview", "a pick is acknowledged and waits for the other side")
ok(len(r["me"]["team"]) == 3 and r["me"]["team"][0]["species"] == "gastly" and r["me"]["team"][1]["species"] == "eevee", "the picked three keep your chosen order (lead first)")
ok(act(ub, hb, {"type": "pick", "order": [4, 2, 0]}, request_id="p1")["waiting"], "retrying the pick is harmless")
r = act(ua, ha, {"type": "pick", "order": [1, 0, 2]})
ok(r["phase"] == "choose" and r["turn"] == 1 and len(r["foe"]["team"]) == 3, "both picked -> the battle begins with three each")
ok(r["me"]["team"][0]["species"] == "pidgey", "your lead is the first Pokémon you picked")

# ── 6v6 ──
clean()
ok(code(lambda: pvp_queue_join(PvpQueueRequest(user_id=ua, format_id="singles_6v6", ids=ida[:5]), ha["authorization"])) == 400, "6v6 refuses five Pokémon")
pvp_queue_join(PvpQueueRequest(user_id=ua, format_id="singles_6v6", ids=ida), ha["authorization"])
m6 = pvp_queue_join(PvpQueueRequest(user_id=ub, format_id="singles_6v6", ids=idb), hb["authorization"])["match"]
ok(m6["phase"] == "choose" and len(m6["me"]["team"]) == 6 and len(m6["foe"]["team"]) == 6, "6v6 skips preview: six against six")
mid = m6["id"]

# ── rating gap blocks a match until the wait grows ──
clean()
pb = get_or_create_player(ub); P.rating_of(pb, "quick_duel")["elo"] = 1500; persist_player(pb)
pvp_queue_join(PvpQueueRequest(user_id=ua, format_id="quick_duel", ids=[ida[0]]), ha["authorization"])
far = pvp_queue_join(PvpQueueRequest(user_id=ub, format_id="quick_duel", ids=[idb[0]]), hb["authorization"])
ok(far["matched"] is False, "a 500-point rating gap isn't matched straight away")
w = index._pvp.for_user(ua, ["queued"])[0]; w["state"]["since"] -= 400; index._pvp.save(w)
w2 = index._pvp.for_user(ub, ["queued"])[0]; w2["state"]["since"] -= 400; index._pvp.save(w2)
ok(pvp_state(ua, authorization=ha["authorization"])["active"] is not None, "after a long wait the window widens and polling the queue finds the match")
clean()

pb = get_or_create_player(ub); P.rating_of(pb, "quick_duel")["elo"] = 1000; persist_player(pb)

# ── friendly battle: custom rules, never rated ──
rules = {"pick": 2, "level_cap": 40, "turn_timer": 60}
ok(code(lambda: pvp_challenge(PvpChallengeRequest(user_id=ua, username="gary_f", format_id="singles_3v3", ids=ida[:3]), ha["authorization"])) == 400, "rated formats can't be challenged directly")
ok(code(lambda: pvp_challenge(PvpChallengeRequest(user_id=ua, username="gary_f", format_id="friendly", ids=[big], rules=rules), ha["authorization"])) == 400, "the challenger's team must obey the rules they set")
c = pvp_challenge(PvpChallengeRequest(user_id=ua, username="gary_f", format_id="friendly", ids=ida[:3], rules=rules), ha["authorization"])
ok(c["format"]["pick"] == 2 and c["format"]["level_cap"] == 40 and c["format"]["turn_timer"] == 60, "the challenge carries the custom rules")
inc = pvp_state(ub, authorization=hb["authorization"])["incoming"]
ok(inc[0]["format"]["pick"] == 2 and inc[0]["format"]["level_cap"] == 40, "the opponent sees the rules before accepting")
ok(code(lambda: pvp_respond(PvpRespondRequest(user_id=ub, match_id=inc[0]["id"], ids=[]), hb["authorization"])) == 400, "accepting needs a team")
ok(code(lambda: pvp_respond(PvpRespondRequest(user_id=ub, match_id=inc[0]["id"], ids=idb[:3]), hb["authorization"])) == 200, "the opponent accepts with their team")
mid = inc[0]["id"]
cur = pvp_state(ub, authorization=hb["authorization"])["active"]
ok(cur["phase"] == "preview" and cur["format"]["rated"] is False, "friendly: bring three, pick two, not rated")
act(ub, hb, {"type": "pick", "order": [0, 2]}); act(ua, ha, {"type": "pick", "order": [2, 1]})
before = (get_or_create_player(ua).elo, get_or_create_player(ub).elo)
f = P.forfeit(index._pvp, mid, ub, index._LazyPlayers(index._pvp.load(mid)))
ok(f["status"] == "finished", "a forfeited friendly battle finishes")
ok((get_or_create_player(ua).elo, get_or_create_player(ub).elo) == before and not P.settles_players(f), "…without touching anyone's rating (and without writing the players)")

# ── timers ──
def match_with(fmt_id, picks=True):
    clean()
    pvp_queue_join(PvpQueueRequest(user_id=ua, format_id=fmt_id, ids=[ida[0]] if fmt_id == "quick_duel" else ida), ha["authorization"])
    return pvp_queue_join(PvpQueueRequest(user_id=ub, format_id=fmt_id, ids=[idb[0]] if fmt_id == "quick_duel" else idb), hb["authorization"])["match"]
m = match_with("quick_duel"); mid = m["id"]
doc = index._pvp.load(mid); doc["state"]["last_move_at"] -= 10_000; index._pvp.save(doc)
ok(index._pvp_sweep(index._pvp.load(mid))["status"] == "abandoned", "neither player answered -> abandoned")
m = match_with("quick_duel"); mid = m["id"]
act(ua, ha, {"type": "move", "move": mv(pvp_state(ua, authorization=ha["authorization"])["active"])})
doc = index._pvp.load(mid); doc["state"]["last_move_at"] -= 10_000; index._pvp.save(doc)
elo_b = P.rating_of(get_or_create_player(ub), "quick_duel")["elo"]
res = pvp_state(ua, authorization=ha["authorization"])["active"]
ok(res["status"] == "finished" and res["winner"] == res["you"], "one silent player: the one who acted wins (settled by the next request, no worker needed)")
ok(P.rating_of(get_or_create_player(ub), "quick_duel")["elo"] < elo_b, "…and the rating moved")
m = match_with("singles_3v3"); mid = m["id"]
act(ua, ha, {"type": "pick", "order": [0, 1, 2]})
doc = index._pvp.load(mid); doc["state"]["last_move_at"] -= 10_000; index._pvp.save(doc)
ok(pvp_state(ub, authorization=hb["authorization"])["active"]["winner"] == "a", "a player who never picked loses to one who did")
ok(P.sweep(index._pvp.load(mid), {}) is False, "a settled match isn't settled twice")

# ── repeat-opponent damping ──
clean()
W, L = get_or_create_player(ua), get_or_create_player(ub)
W.story["pvp"]["history"] = [{"ts": time.time(), "opp_id": ub, "opp": "x", "format": "quick_duel", "won": True, "delta": 5, "rated": True}] * 3
persist_player(W)
m = match_with("quick_duel"); mid = m["id"]
before = P.rating_of(get_or_create_player(ua), "quick_duel")["elo"]
pvp_forfeit(PvpActionRequest(user_id=ub, match_id=mid), hb["authorization"])
ok(P.rating_of(get_or_create_player(ua), "quick_duel")["elo"] == before, "after three rated wins over the same opponent in a day, ratings stop moving")

# ── notifier ──
async def waiter():
    n = notifier.Notifier(); state = {"v": None}
    async def check(): return state["v"]
    loop = asyncio.get_running_loop()
    t0 = time.monotonic()
    threading.Timer(0.15, lambda: (state.__setitem__("v", {"x": 1}), n.notify("k"))).start()
    r = await n.wait_for("k", check, 5.0, recheck_s=3.0)
    fast = time.monotonic() - t0
    none = await n.wait_for("k2", check_none, 0.3)
    state["v"] = {"y": 2}
    r3 = await n.wait_for("k", check, 1.0)
    return r, fast, none, r3
async def check_none(): return None
r, fast, none, r3 = asyncio.run(waiter())
ok(r == {"x": 1} and fast < 1.0, "a waiting request is woken the moment something is signalled (%.0f ms), not on a timer" % (fast * 1000))
ok(none is None and r3 == {"y": 2}, "no change -> times out with nothing; a change already there is returned at once")
async def lost():
    n = notifier.Notifier(); flag = {"on": False}
    async def check(): return {"ok": 1} if flag["on"] else None
    async def flip():
        await asyncio.sleep(0.1); flag["on"] = True                      # a change nobody signalled (another process)
    asyncio.get_running_loop().create_task(flip())
    t0 = time.monotonic(); r = await n.wait_for("z", check, 5.0, recheck_s=0.3); return r, time.monotonic() - t0
r, took = asyncio.run(lost())
ok(r == {"ok": 1} and took < 1.5, "a change that was never signalled is still found by the periodic re-check")
print("ALL PVP FORMAT TESTS PASSED")
