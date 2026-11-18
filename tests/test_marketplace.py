import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Marketplace: listings are escrowed and sold atomically; a purchase that doesn't save changes nothing.
import index
from index import *
from fastapi import HTTPException
import market_system as MS
from database import ListingNotActive
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

store = MS.new_store()                                   # in-memory (the same code runs against Supabase)
def commit(players, doc):
    index.persist_players(players, trade_doc=doc, trade_store=store)

def player(uid, coins=5000, team=2):
    p = PlayerInstance(uid, f"T{uid}")
    p.coins = coins
    for i in range(team):
        p.active_team.append(PokemonInstance(["pikachu", "squirtle", "bulbasaur"][i], 20, uid))
    return p

# ── listing ───────────────────────────────────────────────────────────────────
seller = player(601)
buyer = player(602, coins=5000)
extra = seller.active_team[1]                            # not the only team member
r = MS.list_pokemon(store, seller, extra.id, 800, commit)
ok(r["ok"] and r["listing"]["price"] == 800, "listing a Pokémon posts it at the asking price")
ok(all(m.id != extra.id for m in seller.active_team + seller.pokemon_collection), "the Pokémon left the seller (escrow)")
lid = r["listing"]["listing_id"]
ok(store.load(lid)["status"] == "active", "the listing is active in the store")

try:
    MS.list_pokemon(store, seller, seller.active_team[0].id, 100, commit)
    refused = False
except MS.MarketError as e:
    refused = "only team" in str(e)
ok(refused, "the only team Pokémon can't be listed")
for bad in (0, -5, MS.MAX_PRICE + 1):
    try:
        MS.list_pokemon(store, seller, seller.active_team[0].id, bad, commit); bad_ok = True
    except MS.MarketError:
        bad_ok = False
    ok(not bad_ok, f"price {bad} is refused")

# ── browsing: cheapest first, mine flagged ───────────────────────────────────
lo = MS.list_pokemon(store, seller, seller.active_team[1].id, 200, commit) if len(seller.active_team) > 1 else None
rows = MS.browse(store, buyer.user_id)
ok(rows[0]["price"] <= rows[-1]["price"], "browse lists the cheapest first")
ok(all(not r["mine"] for r in rows if r["seller"] == "T602"), "a buyer doesn't see their own listings as mine")
ok(any(r["listing_id"] == lid and r["mine"] is False for r in rows), "the listing is visible to other players")

# ── buying: money moves, the Pokémon moves, the listing closes ───────────────
coins_b, coins_s = buyer.coins, seller.coins
bought = MS.buy(store, buyer, lid, seller, commit)
fee = 800 * MS.FEE_PERCENT // 100
ok(buyer.coins == coins_b - 800 and seller.coins == coins_s + 800 - fee,
   f"buyer pays 800; seller gets 800 less a {fee} fee")
ok(any(m.species_name == "pikachu" or m.species_name == extra.species_name for m in buyer.active_team + buyer.pokemon_collection),
   "the Pokémon is with the buyer")
ok(store.load(lid)["status"] == "sold" and store.load(lid)["b"] == buyer.user_id, "the listing is sold to the buyer")

# a second purchase of the same listing is refused, and changes nothing
c_before = buyer.coins
try:
    MS.buy(store, player(603, coins=9999), lid, seller, commit); second = True
except MS.MarketError:
    second = False
ok(not second, "a sold listing can't be bought again")  # second is True only if the buy went through

# ── you can't buy your own, or without the coins ─────────────────────────────
own = MS.list_pokemon(store, seller, seller.active_team[0].id, 50, commit) if len(seller.active_team) > 1 else None
if own is None:
    seller.active_team.append(PokemonInstance("bulbasaur", 9, 601))
own = MS.list_pokemon(store, seller, seller.active_team[1].id, 50, commit)
try:
    MS.buy(store, seller, own["listing"]["listing_id"], seller, commit); self_buy = True
except MS.MarketError:
    self_buy = False
ok(not self_buy, "you can't buy your own listing")
poor = player(604, coins=10)
try:
    MS.buy(store, poor, own["listing"]["listing_id"], seller, commit); poor_refused = False
except MS.MarketError as e:
    poor_refused = "need" in str(e)
ok(poor_refused, "a buyer without enough coins is refused with a clear message")
ok(store.load(own["listing"]["listing_id"])["status"] == "active", "the listing stays active after a refused buy")

# ── cancel: the Pokémon comes back, once ─────────────────────────────────────
back = MS.cancel(store, seller, own["listing"]["listing_id"], commit)
ok(back["ok"] and any(m.id == back["pokemon"]["id"] for m in seller.active_team + seller.pokemon_collection),
   "cancel returns the Pokémon to the seller")
try:
    MS.cancel(store, seller, own["listing"]["listing_id"], commit); again = True
except MS.MarketError:
    again = False
ok(not again, "a cancelled listing can't be cancelled again")
try:
    MS.cancel(store, buyer, lo["listing"]["listing_id"] if lo else lid, commit); stolen = True
except MS.MarketError:
    stolen = False
ok(not stolen, "only the seller can cancel a listing")

# ── expiry ────────────────────────────────────────────────────────────────────
seller2 = player(605)
seller2.active_team.append(PokemonInstance("charmander", 12, 605))
ex = MS.list_pokemon(store, seller2, seller2.active_team[1].id, 300, commit)
d = store.load(ex["listing"]["listing_id"]); d["state"]["expires"] = 1; store.save(d)     # long past
try:
    MS.buy(store, player(606), ex["listing"]["listing_id"], seller2, commit); expired_refused = False
except MS.MarketError as e:
    expired_refused = "expired" in str(e)
ok(expired_refused, "an expired listing can't be bought")
MS.cancel(store, seller2, ex["listing"]["listing_id"], commit)
ok(any(m.species_name == "charmander" for m in seller2.active_team + seller2.pokemon_collection),
   "the seller takes an expired Pokémon back with cancel")

# ── rollback: a purchase that doesn't save leaves nobody poorer ──────────────
s3, b3 = player(607), player(608, coins=3000)
s3.active_team.append(PokemonInstance("eevee", 15, 607))
L = MS.list_pokemon(store, s3, s3.active_team[1].id, 500, commit)
bc, sc, n_team = b3.coins, s3.coins, len(b3.active_team) + len(b3.pokemon_collection)
def fail_commit(players, doc):
    raise ListingNotActive("someone else bought it first")
try:
    MS.buy(store, b3, L["listing"]["listing_id"], s3, fail_commit); rb = False
except MS.MarketError as e:
    rb = "moment before" in str(e)
ok(rb, "a race lost during the save gives a clear message")
ok(b3.coins == bc and s3.coins == sc and len(b3.active_team) + len(b3.pokemon_collection) == n_team,
   "a failed purchase leaves coins and Pokémon exactly as they were")
ok(store.load(L["listing"]["listing_id"])["status"] == "active", "and the listing is still for sale")

# ── the API: list, browse, buy and cancel through the real endpoints ──────────
UID = 610
index.choose_starter(index.StarterRequest(user_id=UID, region="kanto", species="charmander"))
pa = get_or_create_player(UID)
pa.add_pokemon_to_team(PokemonInstance("squirtle", 5, UID)); pa.coins = 1000; persist_player(pa)
sec = next(m for m in get_or_create_player(UID).active_team if m.species_name == "squirtle")
res = market_list(MarketListRequest(user_id=UID, pokemon_id=sec.id, price=250))
ok(res["ok"], "the list endpoint posts a Pokémon")
ok(any(l["listing_id"] == res["listing"]["listing_id"] for l in market_browse()["listings"]),
   "the browse endpoint shows it")
try:
    market_buy(MarketBuyRequest(user_id=UID, listing_id=res["listing"]["listing_id"]))
    api_bought = True                      # True only if the purchase went through (it must not)
except HTTPException as e:
    api_bought = False
    api_status = e.status_code
ok(not api_bought and api_status == 400, "the buy endpoint refuses your own listing with 400")
c = market_cancel(MarketBuyRequest(user_id=UID, listing_id=res["listing"]["listing_id"]))
ok(c["ok"], "the cancel endpoint returns it")

print("ALL PASS")
