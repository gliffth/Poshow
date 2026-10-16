import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import requests as rq, index, database
from index import *
from database import DatabaseError, ConcurrentUpdateError, SchemaError
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
def raises(fn, exc=DatabaseError):
    try: fn(); return False
    except exc: return True

def mk(name, sp):
    r = auth_register(RegisterRequest(username=name, password="secret1")); u = r["user_id"]
    choose_starter(StarterRequest(user_id=u, region="kanto", species=sp)); return u
ua, ub = mk("Trader_A", "charmander"), mk("Trader_B", "squirtle")
def row(u): return next(r for r in fake.rows["players"] if r["user_id"] == u)
def trade_to_confirm():
    tid = trade_invite(TradeInviteRequest(user_id=ua, username="Trader_B"))["id"]
    trade_respond(TradeRespondRequest(user_id=ub, trade_id=tid, accept=True))
    give = get_or_create_player(ua).active_team[0].id; take = get_or_create_player(ub).active_team[0].id
    trade_offer(TradeOfferRequest(user_id=ua, trade_id=tid, pokemon_id=give, coins=25))
    trade_offer(TradeOfferRequest(user_id=ub, trade_id=tid, pokemon_id=take))
    trade_lock(TradeStepRequest(user_id=ua, trade_id=tid)); trade_lock(TradeStepRequest(user_id=ub, trade_id=tid))
    trade_confirm(TradeStepRequest(user_id=ua, trade_id=tid))
    return tid, give, take
def owner(pid): return next(r for r in fake.rows["pokemon"] if r["id"] == pid)["player_id"]
def trade_status(tid): return next(r for r in fake.rows["trades"] if r["id"] == tid)["status"]

# 1) the second player's save fails -> NOTHING changes for either account, trade not "done", can be retried
tid, give, take = trade_to_confirm(); coins_a, coins_b = row(ua)["coins"], row(ub)["coins"]
fake.fail_pokemon_write = True
ok(raises(lambda: trade_confirm(TradeStepRequest(user_id=ub, trade_id=tid))), "settlement failure -> 503")
fake.fail_pokemon_write = False
ok(owner(give) == ua and owner(take) == ub and row(ua)["coins"] == coins_a and row(ub)["coins"] == coins_b, "neither player's Pokémon or coins changed")
ok(trade_status(tid) == "open", "the trade is still open (never recorded as done)")
c = trade_confirm(TradeStepRequest(user_id=ub, trade_id=tid))
ok(c["status"] == "done" and owner(give) == ub and owner(take) == ua, "retry then swaps both Pokémon")
ok(row(ua)["coins"] == coins_a - 25 and row(ub)["coins"] == coins_b + 25, "coins moved with the Pokémon")
ok(trade_status(tid) == "done", "the trade record became 'done' in the same transaction")

# 2) one side changed elsewhere after loading -> the whole settlement is rejected, nothing written
tid, give, take = trade_to_confirm()
real_load = index._db.load_player
def stale_b(uid):
    p = real_load(uid)
    if uid == ub:                      # B is modified by another client between our load and our save
        other = real_load(ub); other.coins += 1; index._db.save_player(other)
    return p
index._db.load_player = stale_b
ok(raises(lambda: trade_confirm(TradeStepRequest(user_id=ub, trade_id=tid)), ConcurrentUpdateError), "stale player -> ConcurrentUpdateError")
index._db.load_player = real_load
ok(owner(give) == ua and owner(take) == ub and trade_status(tid) == "open", "no Pokémon moved, trade still open")

# 3) missing function -> loud SchemaError, no silent two-step fallback
fake.has_rpc = False
ok(raises(lambda: index._db.save_players([get_or_create_player(ua), get_or_create_player(ub)]), SchemaError), "no save_players_atomic -> SchemaError")
fake.has_rpc = True

# 4) a team that references a missing Pokémon row fails the load (no silently smaller team)
p = get_or_create_player(ua); extra = PokemonInstance("pidgey", 5, ua); p.add_pokemon_to_team(extra); persist_player(p)
fake.rows["pokemon"] = [r for r in fake.rows["pokemon"] if r["id"] != extra.id]
ok(raises(lambda: index._db.load_player(ua)), "missing team Pokémon -> DatabaseError, not a reduced roster")

# 5) the legacy non-atomic fallback is ignored on Render / Vercel
fake.has_rpc = False
fake.rows["pokemon"] = [r for r in fake.rows["pokemon"]]
q = index._db.load_player(ub)
os.environ["ALLOW_LEGACY_SAVE"] = "1"; os.environ["RENDER"] = "true"
ok(raises(lambda: index._db.save_player(q), SchemaError), "ALLOW_LEGACY_SAVE is ignored when RENDER is set")
del os.environ["RENDER"]
ok(index._db.save_player(q) is True, "…and still works for local development")
os.environ.pop("ALLOW_LEGACY_SAVE"); fake.has_rpc = True

# 6) leaderboard / stats: outages are errors, not empty results
real_get = rq.get
rq.get = lambda url, *a, **k: F.Resp(500, {"message": "boom"})
ok(raises(lambda: index._db.get_leaderboard()), "leaderboard outage raises")
ok(raises(lambda: index._db.get_stats()), "stats outage raises")
rq.get = real_get
print("ALL TRADE-ATOMIC TESTS PASSED")
