import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_supabase as F
fake = F.install(F.GOOD, rpc=True)
os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Marketplace against the database emulation: two buyers race for one listing. Only one sale may commit.
import copy
import market_system as MS
from database import SupabaseDB, ListingNotActive, ConcurrentUpdateError
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

db = SupabaseDB("http://fake", "k")
store = MS.new_store("http://fake", "k")
def commit(players, doc):
    db.save_players(players, trade_row=store.atomic_row(doc), doc_table="market_listings")

seller = PlayerInstance(701, "Seller"); seller.coins = 0
seller.active_team.append(PokemonInstance("pikachu", 20, 701)); seller.active_team.append(PokemonInstance("eevee", 15, 701))
b1 = PlayerInstance(702, "B1"); b1.coins = 5000
b2 = PlayerInstance(703, "B2"); b2.coins = 5000
for p in (seller, b1, b2):
    db.save_players([p])
listed = MS.list_pokemon(store, seller, seller.active_team[1].id, 400, commit)
lid = listed["listing"]["listing_id"]
ok(store.load(lid)["status"] == "active", "the listing is stored in the database")

stale = store.load(lid)                      # what the second buyer saw before the first purchase
first = MS.buy(store, b1, lid, seller, commit)
ok(first["ok"] and store.load(lid)["status"] == "sold", "the first buyer's purchase commits")
seller_after_first = seller.coins

# the second buyer acts on the stale view: the listing is now sold, so the save must refuse
store.load = lambda _id, _s=stale: copy.deepcopy(_s)
seller_before = seller.coins
try:
    MS.buy(store, b2, lid, seller, commit); second = True
except MS.MarketError:
    second = False
ok(not second, "the stale second purchase is refused")
ok(b2.coins == 5000, "the refused buyer keeps every coin")
ok(seller.coins == seller_before, "the seller is not credited twice")

# the database refuses to re-sell a sold listing even if the application check were skipped
try:
    db.save_players([], trade_row=store.atomic_row(dict(stale, status="cancelled", b=0)),
                    doc_table="market_listings")
    raised = None
except ListingNotActive as e:
    raised = "ListingNotActive"
except Exception as e:
    raised = type(e).__name__
ok(raised == "ListingNotActive", f"the database rejects a second change to a sold listing ({raised})")
print("ALL PASS")
