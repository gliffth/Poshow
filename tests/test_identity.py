import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# One player across web and Telegram: signed Mini App identity, linking, merge rules, retired ids.
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import hashlib, hmac, json, time, urllib.parse
import accounts, index
from index import *
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def code_of(fn):
    try: fn(); return 200
    except HTTPException as e: return e.status_code
    except accounts.AccountError as e: return e.status
BOT = "123456:TEST-BOT-TOKEN"

def init_data(user_id, name="Ash", bot=BOT, auth_date=None, tamper=False):
    fields = {"auth_date": str(int(auth_date or time.time())), "query_id": "AAH", "user": json.dumps({"id": user_id, "first_name": name}, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if tamper: fields["user"] = json.dumps({"id": user_id + 1, "first_name": name}, separators=(",", ":"))
    return urllib.parse.urlencode(fields)

# ---- verified initData ------------------------------------------------------------------------------------------
v = accounts.verify_webapp_init_data
ok(v(init_data(777), BOT)["id"] == 777, "valid initData is accepted")
ok(v(init_data(777, tamper=True), BOT) is None, "a changed user id (tampering) is rejected")
ok(v(init_data(777), "999:OTHER") is None, "initData signed for another bot is rejected")
ok(v(init_data(777, auth_date=time.time() - 3 * 86400), BOT) is None, "old initData (> 24h) is rejected")
ok(v(init_data(777, auth_date=time.time() + 3600), BOT) is None, "initData from the future is rejected")
ok(v("user=%7B%22id%22%3A1%7D&auth_date=1", BOT) is None and v("", BOT) is None and v(None, BOT) is None, "missing hash / empty input is rejected")
index.TELEGRAM_BOT_TOKEN = BOT
r = auth_telegram_webapp(WebAppAuthRequest(init_data=init_data(4242, "Misty")))
ok(r["user_id"] == 4242 and r["token"] and r["needs_starter"], "the Mini App endpoint signs a Telegram player in from VERIFIED data")
ok(accounts.verify_token(r["token"])["uid"] == 4242, "…and the token belongs to that Telegram id")
ok(code_of(lambda: auth_telegram_webapp(WebAppAuthRequest(init_data=init_data(4242, tamper=True)))) == 401, "forged initData -> 401")
index.TELEGRAM_BOT_TOKEN = ""
ok(code_of(lambda: auth_telegram_webapp(WebAppAuthRequest(init_data=init_data(4242)))) == 503, "no bot token configured -> 503, never trusted")
index.TELEGRAM_BOT_TOKEN = BOT

# ---- linking -----------------------------------------------------------------------------------------------------
svc = index._accounts
def web_player(name, species=None):
    a = auth_register(RegisterRequest(username=name, password="secret1"))
    if species: choose_starter(StarterRequest(user_id=a["user_id"], region="kanto", species=species))
    return a
def tg_player(tid, species=None):
    if species:
        p = get_or_create_player(tid, "tg"); 
        choose_starter(StarterRequest(user_id=tid, region="kanto", species=species))
def link(web, tid, keep=None, name="TGname"):
    start = auth_link_start("Bearer " + web["token"]); return svc.confirm_link(start["code"], tid, name, keep), start["code"]
def owner_rows(uid): return sum(1 for r in fake.rows["pokemon"] if r["player_id"] == uid)

# a Telegram-id session can't start a link
tgsess = auth_telegram_webapp(WebAppAuthRequest(init_data=init_data(5555)))
ok(code_of(lambda: auth_link_start("Bearer " + tgsess["token"])) == 400, "a Telegram session has nothing to link")
ok(code_of(lambda: auth_link_start(None)) == 401, "linking needs a login")

# (1) web player with progress + brand-new Telegram account -> web player stays, Telegram plays as it
w1 = web_player("Link_A", "charmander"); T1 = 9001
res, c1 = link(w1, T1)
ok(res["status"] == "linked" and res["canonical"] == w1["user_id"] and res["kept"] == "web", "(1) web progress + fresh Telegram: the web player stays")
ok(svc.canonical(T1) == w1["user_id"], "(1) the bot now resolves that Telegram id to the web player")
ok(svc.telegram_for(w1["user_id"]) == T1, "(1) notifications for the web player reach that Telegram account")
poll = svc.poll_telegram_login(c1)
ok(poll["status"] == "ok" and poll["user_id"] == w1["user_id"], "(1) the website, polling the code, is signed in as the same player")
# the old Telegram-id session is refused (retired id), the web one works
os.environ["REQUIRE_AUTH"] = "1"; index.REQUIRE_AUTH = True
oldtg = accounts.make_token(T1, "x")
ok(code_of(lambda: get_roster(T1, "Bearer " + oldtg)) == 401, "(1) an old session for the retired Telegram id is refused (no ghost player)")
ok(code_of(lambda: get_roster(w1["user_id"], "Bearer " + w1["token"])) == 200, "(1) the web player's own token works")
ok(code_of(lambda: get_roster(w1["user_id"], "Bearer " + tgsess["token"])) == 403, "(1) another account's token still can't read it")
index.REQUIRE_AUTH = False

# (2) idempotent + (3) the same Telegram account can't join a second web account
res2, _ = link(w1, T1); ok(res2["status"] == "already_linked", "(2) linking again is harmless")
w1b = web_player("Link_A2", "squirtle")
res3, _ = link(w1b, T1); ok(res3["status"] == "linked_elsewhere", "(3) a Telegram account can't be linked to two web players")

# (4) only the Telegram side has progress -> the Telegram player stays and the web login points at it
w2 = web_player("Link_B"); T2 = 9002; tg_player(T2, "bulbasaur")
res, c2 = link(w2, T2)
ok(res["status"] == "linked" and res["canonical"] == T2 and res["kept"] == "telegram", "(4) only Telegram has Pokémon: the Telegram player stays")
login = auth_login(RegisterRequest(username="Link_B", password="secret1"))
ok(login["user_id"] == T2 and not login["needs_starter"], "(4) logging in with the web username now opens the Telegram player")
ok(svc.canonical(T2) == T2 and svc.is_alias(w2["user_id"]), "(4) the old web id is retired")
ok(svc.poll_telegram_login(c2)["user_id"] == T2, "(4) the website session switches to the Telegram player")
index.REQUIRE_AUTH = True
ok(code_of(lambda: get_roster(w2["user_id"], "Bearer " + w2["token"])) == 401, "(4) the OLD web token is refused, not turned into an empty ghost player")
index.REQUIRE_AUTH = False

# (5) both have progress -> conflict, nothing changes until a side is chosen; the other side is archived, not deleted
w3 = web_player("Link_C", "charmander"); T3 = 9003; tg_player(T3, "squirtle")
before_w, before_t = owner_rows(w3["user_id"]), owner_rows(T3)
res, c3 = link(w3, T3)
ok(res["status"] == "conflict" and owner_rows(w3["user_id"]) == before_w and owner_rows(T3) == before_t and svc.canonical(T3) == T3, "(5) both have Pokémon: conflict, nothing changed")
res, _ = (svc.confirm_link(c3, T3, "TG", "web"), c3)
ok(res["status"] == "linked" and res["kept"] == "web" and svc.canonical(T3) == w3["user_id"], "(5) keep web: the web player stays")
ok(owner_rows(-T3) == before_t and owner_rows(T3) == 0 and owner_rows(w3["user_id"]) == before_w, "(5) the Telegram player's Pokémon were ARCHIVED (negative id), not deleted")

w4 = web_player("Link_D", "charmander"); T4 = 9004; tg_player(T4, "squirtle")
start = auth_link_start("Bearer " + w4["token"])
res = svc.confirm_link(start["code"], T4, "TG", "telegram")
ok(res["status"] == "linked" and res["kept"] == "telegram" and svc.canonical(T4) == T4, "(5) keep telegram: the Telegram player stays")
ok(owner_rows(-w4["user_id"]) >= 1 and owner_rows(T4) >= 1, "(5) the web player's Pokémon were archived, the Telegram ones kept")

# (6) bad codes
ok(svc.confirm_link("NOPE1234", 9100, "x")["status"] == "expired", "(6) unknown code -> expired")
lc = svc.start_telegram_login()["code"]
ok(svc.confirm_link(lc, 9101, "x")["status"] == "not_a_link_code", "(6) a login code is not a link code")
w5 = web_player("Link_E"); s5 = auth_link_start("Bearer " + w5["token"])
fake.rows["login_codes"][-1]["expires_at"] = time.time() - 5
ok(svc.confirm_link(s5["code"], 9102, "x")["status"] == "expired", "(6) an expired link code is refused")
w6 = web_player("Link_F"); s6 = auth_link_start("Bearer " + w6["token"]); svc.confirm_link(s6["code"], 9103, "x")
ok(svc.confirm_link(s6["code"], 9104, "x")["status"] == "already_used", "(6) a link code works once")

# (7) "Continue with Telegram" for a LINKED Telegram account logs in as the linked player, with the web username
w7 = web_player("Link_G", "charmander"); T7 = 9007; link(w7, T7)
lg = svc.start_telegram_login()["code"]
ok(svc.confirm_telegram_login(lg, T7, "TGname") is True, "(7) the bot confirms a web login")
got = svc.poll_telegram_login(lg)
ok(got["status"] == "ok" and got["user_id"] == w7["user_id"] and got["username"] == "Link_G", "(7) the website signs in as the LINKED player with the web username")
# the Mini App does the same
r = auth_telegram_webapp(WebAppAuthRequest(init_data=init_data(T7, "TGname")))
ok(r["user_id"] == w7["user_id"] and r["username"] == "Link_G" and not r["needs_starter"], "(7) the Mini App opens the same linked player")

# (8) a link code can't be used to log in, and notifications reach the right Telegram account
lk = auth_link_start("Bearer " + web_player("Link_H")["token"])
ok(svc.confirm_telegram_login(lk["code"], 9200, "x") is False, "(8) a link code can't double as a login code")
sent = []
import requests as rq; real_post = rq.post
index.TELEGRAM_BOT_TOKEN = "T"
rq.post = lambda url, *a, **k: sent.append(k.get("json")) or F.Resp(200, {}) if "api.telegram.org" in url else real_post(url, *a, **k)
notify_telegram(w7["user_id"], "hello")
rq.post = real_post
ok(sent and sent[0]["chat_id"] == T7, "(8) a ping for the linked web player goes to its Telegram account")
print("ALL IDENTITY TESTS PASSED")
