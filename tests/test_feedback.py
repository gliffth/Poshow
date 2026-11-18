import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import types, index, feedback
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="1.2.3.4"))
u = auth_register(RegisterRequest(username="Reporter_1", password="secret1")); tok = "Bearer " + u["token"]
ctx = {"view": "battle", "theme": "weathered", "ua": "x" * 500, "evil": "<script>", "screen": "390x844"}
r = post_feedback(FeedbackRequest(category="bug", message="The potion button did nothing in battle.", context=ctx), req, tok)
ok(r["ok"], "a logged-in player can report a bug")
rows = fake.rows["feedback"]
ok(len(rows) == 1 and rows[0]["user_id"] == u["user_id"] and rows[0]["username"] == "Reporter_1", "the report is stored with the player's id and name")
ok("evil" not in rows[0]["context"] and len(rows[0]["context"]["ua"]) == 200, "context is whitelisted and truncated")
ok(post_feedback(FeedbackRequest(category="idea", message="Add a night mode for routes please"), req, None)["ok"], "guests can report too (no token)")
ok(fake.rows["feedback"][1]["user_id"] is None, "…stored anonymously")
ok(code(lambda: post_feedback(FeedbackRequest(category="bug", message="hi"), req, tok)) == 400, "too short is refused")
ok(code(lambda: post_feedback(FeedbackRequest(category="bug", message="x" * 1001), req, tok)) == 400, "too long is refused")
ok(code(lambda: post_feedback(FeedbackRequest(category="hack", message="this is a long enough message"), req, tok)) == 400, "unknown category refused")
ok(feedback.FeedbackStore.clean("a\x00b\x07c") == "abc", "control characters are stripped")
for i in range(10):
    c = code(lambda: post_feedback(FeedbackRequest(category="bug", message=f"spam report number {i} here"), req, tok))
    if c == 429: break
ok(c == 429, "a sender is rate limited (429)")
os.environ["ADMIN_USER_IDS"] = str(u["user_id"])
import admin_system; admin_system._env_ids.cache_clear() if hasattr(admin_system._env_ids, "cache_clear") else None
lst = admin_feedback(10, tok)
ok(len(lst["feedback"]) >= 2, "an admin can read the reports")
os.environ["ADMIN_USER_IDS"] = ""
ok(code(lambda: admin_feedback(10, tok)) == 403, "a non-admin cannot")
print("ALL FEEDBACK TESTS PASSED")
