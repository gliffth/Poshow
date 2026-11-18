import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import copy, index, community, admin_system
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
def reg(name):
    u = auth_register(RegisterRequest(username=name, password="secret1")); return u["user_id"], "Bearer " + u["token"]
def set_admins(*ids):
    os.environ["ADMIN_USER_IDS"] = ",".join(map(str, ids))
    admin_system._env_ids.cache_clear() if hasattr(admin_system._env_ids, "cache_clear") else None

adm_id, adm = reg("Boss_1"); p1_id, p1 = reg("Player_1"); p2_id, p2 = reg("Player_2")
set_admins(adm_id)

# ── information content ──
info = get_info()
ok(info["version"] == community.DEFAULT_CHANGELOG["version"] and len(info["guide"]["sections"]) >= 10, "the panel works with the shipped defaults")
ok(info["links"]["repo"] == "", "the repository link is empty by default")
guide = {"sections": [{"title": "Hello there", "icon": "nope", "body": "## Hi\n- one\n[site](https://example.com)"},
                      {"id": "Second Part", "title": "Second", "icon": "map", "body": "x\x00y"}]}
ok(code(lambda: admin_put_info("guide", InfoContentRequest(value=guide), None)) == 401, "editing without a login is 401")
ok(code(lambda: admin_put_info("guide", InfoContentRequest(value=guide), p1)) == 403, "a non-admin edit is 403")
r = admin_put_info("guide", InfoContentRequest(value=guide), adm)
s = r["value"]["sections"]
ok(s[0]["id"] == "hello-there" and s[0]["icon"] == "book", "ids are slugged lowercase and an unknown icon falls back to book")
ok(s[1]["id"] == "second-part" and s[1]["body"] == "xy", "ids are normalised and control characters stripped")
ok(get_info()["guide"]["sections"][0]["title"] == "Hello there", "an admin edit shows up at once (cache cleared)")
ok("guide" in fake.rows["site_content"][0]["key"] and fake.rows["site_content"][0]["updated_by"] == adm_id, "the edit is stored with the admin id")
bad = lambda v, k="guide": code(lambda: admin_put_info(k, InfoContentRequest(value=v), adm))
ok(bad({"sections": []}) == 400, "an empty guide is refused")
ok(bad({"sections": [{"title": "a", "body": ""}] * 2}) == 400, "duplicate section ids are refused")
ok(bad({"sections": [{"title": f"S{i}", "body": ""} for i in range(31)]}) == 400, "more than 30 sections is refused")
ok(bad({"sections": [{"title": "T", "body": "[x](http://insecure.example)"}]}) == 400, "a non-https link in the markup is refused")
ok(bad({"sections": [{"title": "T", "body": "[x](javascript:alert(1))"}]}) == 400, "a script link is refused")
ok(bad({"sections": [{"title": "T", "body": "a" * 4001}]}) == 200 and len(get_info()["guide"]["sections"][0]["body"]) == 4000, "a body is cut at 4000 characters")
ok(bad({"sections": [{"title": f"S{i}", "body": "é" * 4000} for i in range(30)]}) == 400, "over 60 KB in total is refused")
ok(bad({"version": "1.0", "entries": [{"version": "1.0", "items": [{"kind": "wow", "text": "x"}]}]}, "changelog") == 400, "an unknown change kind is refused")
ok(bad({"version": "", "entries": []}, "changelog") == 400, "a changelog needs a version")
ok(bad({"version": "2.0", "entries": [{"version": "2.0", "date": "2026-11-13", "title": "T", "items": [{"kind": "new", "text": "A thing"}]}], "upcoming": ["Soon"], "known": ["Bug"]}, "changelog") == 200, "a valid changelog is accepted")
ok(get_info()["version"] == "2.0", "the version comes from the changelog")
ok(bad({"repo": "http://x.example"}, "links") == 400 and bad({"repo": "ftp://x"}, "links") == 400, "the repository link must be https")
ok(bad({"repo": "https://github.com/gliffth/Poshow"}, "links") == 200 and get_info()["links"]["repo"].startswith("https://"), "a valid repository link is stored")
ok(bad({"x": 1}, "other") == 404, "an unknown content key is 404")
r = admin_delete_info("changelog", adm)
ok(r["value"]["version"] == community.DEFAULT_CHANGELOG["version"] and get_info()["version"] == r["value"]["version"], "reset returns to the default")
ok(code(lambda: admin_delete_info("changelog", p1)) == 403, "a non-admin reset is 403")

# ── ideas: submitting ──
ok(code(lambda: post_idea(IdeaRequest(title="A night mode please"), None)) == 401, "a guest cannot submit")
ok(code(lambda: post_idea(IdeaRequest(title="short"), p1)) == 400, "a title under 6 characters is refused")
ok(code(lambda: post_idea(IdeaRequest(title="x" * 81), p1)) == 400, "a title over 80 characters is refused")
ok(code(lambda: post_idea(IdeaRequest(title="A fine title", body="y" * 601), p1)) == 400, "a description over 600 characters is refused")
a = post_idea(IdeaRequest(title="Add a night mode", body="Dark\x00 routes"), p1)["idea"]
ok(a["status"] == "pending" and a["mine"] and not a["votable"] and a["body"] == "Dark routes", "a new idea is pending, votable only after review")
ok(code(lambda: post_idea(IdeaRequest(title="add a NIGHT mode!!"), p1)) == 409, "the same title after normalising is a duplicate")
post_idea(IdeaRequest(title="Rename the Care Center building"), p1)
ok(code(lambda: post_idea(IdeaRequest(title="Rename the Care Center building now"), p1)) == 409, "a title sharing 80% of its words is a duplicate")
ok(code(lambda: post_idea(IdeaRequest(title="Add trading by link"), p1)) == 200, "a different idea is accepted")
ok(code(lambda: post_idea(IdeaRequest(title="Something else entirely"), p1)) == 429, "the fourth idea in a day is 429")
ok(post_idea(IdeaRequest(title="Another player idea"), p2)["ok"], "the limit is per player")
ok(fake.rows["ideas"][0]["user_id"] == p1_id and fake.rows["ideas"][0]["username"] == "Player_1", "ideas store the author")

# ── ideas: visibility ──
ids = lambda tok: [i["title"] for i in get_ideas(tok)["ideas"]]
ok(len(ids(p1)) == 3 and all(i["mine"] for i in get_ideas(p1)["ideas"]), "an author sees their own pending ideas")
ok(ids(p2) == ["Another player idea"], "other players see only their own pending idea")
ok(ids(None) == [] and get_ideas(None)["can_post"] is False, "a guest sees no pending ideas and cannot post")
night = next(i for i in fake.rows["ideas"] if i["title"] == "Add a night mode")["id"]
ok(code(lambda: vote_idea(night, p2)) == 404, "another player's pending idea is invisible to voting (404)")
ok(code(lambda: vote_idea(night, p1)) == 409, "the author cannot vote while it is pending (409)")
ok(code(lambda: vote_idea(night, None)) == 401, "a guest cannot vote")
ok(code(lambda: vote_idea(99999, p1)) == 404, "an unknown idea is 404")

# ── ideas: admin ──
ok(code(lambda: admin_ideas(p1)) == 403, "the admin list is admin-only")
al = admin_ideas(adm)
ok(len(al["ideas"]) == 4 and all("username" in i for i in al["ideas"]), "the admin sees every idea with its author")
ok(code(lambda: admin_update_idea(night, IdeaUpdateRequest(status="planned"), p1)) == 403, "a non-admin cannot change status")
ok(code(lambda: admin_update_idea(night, IdeaUpdateRequest(status="launched"), adm)) == 400, "an unknown status is 400")
ok(code(lambda: admin_update_idea(night, IdeaUpdateRequest(), adm)) == 400, "an empty update is 400")
ok(code(lambda: admin_update_idea(99999, IdeaUpdateRequest(status="planned"), adm)) == 404, "updating an unknown idea is 404")
ok(code(lambda: admin_update_idea(night, IdeaUpdateRequest(title="x"), adm)) == 400, "an edited title is validated too")
admin_update_idea(night, IdeaUpdateRequest(status="under_consideration", title="Add a night mode to routes"), adm)
ok(ids(p2) == ["Another player idea", "Add a night mode to routes"], "once reviewed, an idea is public")
ok(next(i for i in get_ideas(p2)["ideas"] if i["id"] == night)["votable"], "an idea under consideration can be voted on")

# ── ideas: votes ──
r = vote_idea(night, p2); ok(r["voted"] and r["votes"] == 1, "a vote counts")
r = vote_idea(night, p2); ok(not r["voted"] and r["votes"] == 0, "a second tap removes the vote")
vote_idea(night, p2); vote_idea(night, p1)
ok(next(i for i in fake.rows["ideas"] if i["id"] == night)["votes"] == 2 and len(fake.rows["idea_votes"]) == 2, "two players, two votes, one row each")
ok(next(i for i in get_ideas(p2)["ideas"] if i["id"] == night)["voted"] and not next(i for i in get_ideas(None)["ideas"] if i["id"] == night)["voted"], "voted is reported per player")
for _ in range(7): vote_idea(night, p2)
ok(len([v for v in fake.rows["idea_votes"] if v["user_id"] == p2_id]) == 0, "an odd number of taps leaves the vote off")
vote_idea(night, p2)
ok(len([v for v in fake.rows["idea_votes"] if v["user_id"] == p2_id]) == 1, "repeated taps never leave more than one row")
admin_update_idea(night, IdeaUpdateRequest(status="declined"), adm)
ok(code(lambda: vote_idea(night, p2)) == 409, "voting is closed on a declined idea")
ok(next(i for i in get_ideas(p2)["ideas"] if i["id"] == night)["status_label"] == "Declined", "the status label is readable")
admin_update_idea(night, IdeaUpdateRequest(status="archived"), adm)
ok(night not in [i["id"] for i in get_ideas(p2)["ideas"]] and code(lambda: vote_idea(night, p2)) == 404, "an archived idea disappears")

# ── ordering ──
mk = lambda **k: {"id": k["id"], "title": "t", "status": k["status"], "votes": k.get("votes", 0), "voted": False, "mine": False, "votable": True}
order = community.sort_ideas([mk(id=1, status="declined", votes=9), mk(id=2, status="planned", votes=1), mk(id=3, status="in_development"),
                              mk(id=4, status="planned", votes=5), mk(id=5, status="under_consideration", votes=2), mk(id=6, status="implemented"), mk(id=7, status="pending")])
ok([i["id"] for i in order] == [7, 3, 4, 2, 5, 6, 1], "ideas sort by status, then votes (own pending first)")

# ── duplicate rule on its own ──
ok(community.is_duplicate("Add a night mode", "add a night mode!") and not community.is_duplicate("Add a night mode", "Add dark theme"), "duplicate: exact vs different")
ok(not community.is_duplicate("Night mode", "Night modes"), "duplicate: short titles need an exact match")

# ── memory mode behaves the same ──
m = community.CommunityStore()
r1 = m.idea_add(1, "A", "Memory mode idea one", "")
try: m.idea_add(1, "A", "Memory mode idea one!", ""); dup = False
except community.CommunityError as e: dup = e.status == 409
ok(dup, "memory mode: a duplicate is 409")
m.idea_update(r1["id"], {"status": "planned"})
ok(m.idea_vote(r1["id"], 5)["votes"] == 1 and m.idea_vote(r1["id"], 5)["votes"] == 0, "memory mode: a vote toggles")
print("ALL COMMUNITY TESTS PASSED")
