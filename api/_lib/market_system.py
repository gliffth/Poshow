"""
Marketplace (roadmap §6.10): fixed-price Pokémon listings.

  list    the Pokémon leaves the seller's team/storage and is held in escrow on a listing (one transaction)
  buy     the buyer pays, the seller is credited less a fee, and the Pokémon moves to the buyer (one transaction)
  cancel  the seller takes the Pokémon back, if the listing is still active (one transaction)

A listing is a shared document in the `market_listings` table (see database/schema.sql), stored with the same
DocStore as trades. The commit step is passed in by the caller, so the rules here run with or without a database.

Safety:
  * every change saves the players AND the listing together, or not at all
  * a listing can be bought or cancelled only while it is active; the database enforces this too (a second
    purchase of the same listing fails with ListingNotActive, and the first one's changes stand)
  * the seller's own row is in every purchase, so two purchases of one seller's state can't both commit
    (optimistic version check), and a stale buyer gets a retryable error rather than a double sale
  * expired listings can't be bought; the seller takes the Pokémon back with cancel
  * the same team rules as trades apply: no critical or resting Pokémon, and nobody is left without a team member
"""

import time
import uuid
from typing import Callable, Dict, List, Optional

from database import ConcurrentUpdateError, ListingNotActive
from doc_store import DocStore
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
import trade_system

FEE_PERCENT = 5                 # taken from the seller's proceeds (a coin sink)
LISTING_TTL = 3 * 24 * 3600     # listings run for three days
MIN_PRICE = 1
MAX_PRICE = 1_000_000
MAX_ACTIVE_PER_PLAYER = 10


class MarketError(ValueError):
    pass


def new_store(url=None, key=None) -> DocStore:
    return DocStore("market_listings", url, key)


def _now() -> int:
    return int(time.time())


def _find(player: PlayerInstance, mon_id: str):
    return next((m for m in list(player.active_team) + list(player.pokemon_collection) if m.id == mon_id), None)


def _put_back(player: PlayerInstance, mon) -> None:
    """Return a Pokémon to the player: the team if there is room, otherwise storage."""
    if len(player.active_team) < 6:
        player.active_team.append(mon)
    else:
        player.pokemon_collection.append(mon)


def _public(doc: Dict, viewer_id: Optional[int] = None) -> Dict:
    st = doc["state"]
    return {"listing_id": doc["id"], "species": st["species"], "level": st["level"], "price": st["price"],
            "seller": st["seller_name"], "expires": st["expires"], "expired": _now() >= st["expires"],
            "mine": viewer_id is not None and doc["a"] == viewer_id}


def list_pokemon(store: DocStore, seller: PlayerInstance, pokemon_id: str, price: int,
                 commit: Callable[[List[PlayerInstance], Dict], None]) -> Dict:
    if not isinstance(price, int) or price < MIN_PRICE or price > MAX_PRICE:
        raise MarketError(f"The price must be between {MIN_PRICE} and {MAX_PRICE} coins.")
    mine = [d for d in store.for_user(seller.user_id, statuses=["active"], max_age_s=LISTING_TTL + 86400)
            if d["a"] == seller.user_id]
    if len(mine) >= MAX_ACTIVE_PER_PLAYER:
        raise MarketError(f"You can have {MAX_ACTIVE_PER_PLAYER} listings at once. Cancel one first.")
    mon = _find(seller, pokemon_id)
    if mon is None:
        raise MarketError("That Pokémon isn't yours.")
    try:
        trade_system._validate_offer_pokemon(seller, pokemon_id)
    except trade_system.TradeError as e:
        raise MarketError(str(e)) from e
    if mon in seller.active_team and len(seller.active_team) <= 1:
        raise MarketError("You can't list your only team Pokémon. Put another one on your team first.")
    taken = trade_system._take_pokemon(seller, pokemon_id)
    doc = {"id": str(uuid.uuid4()), "a": seller.user_id, "b": 0, "status": "active",
           "state": {"pokemon": taken.to_dict(), "species": taken.species_name, "level": taken.level,
                     "price": price, "seller_name": seller.username, "expires": _now() + LISTING_TTL},
           "ts": _now()}
    try:
        commit([seller], doc)
    except Exception:
        _put_back(seller, taken)            # the escrow didn't save: the Pokémon is still the seller's
        raise
    return {"ok": True, "message": f"{taken.nickname} is listed for {price} coins.", "listing": _public(doc, seller.user_id)}


def browse(store: DocStore, viewer_id: Optional[int] = None) -> List[Dict]:
    rows = [d for d in store.list_status("active") if _now() < d["state"]["expires"] or d["a"] == viewer_id]
    rows.sort(key=lambda d: d["state"]["price"])
    return [_public(d, viewer_id) for d in rows]


def mine(store: DocStore, user_id: int) -> List[Dict]:
    rows = [d for d in store.for_user(user_id, statuses=["active"], max_age_s=LISTING_TTL + 86400) if d["a"] == user_id]
    return [_public(d, user_id) for d in rows]


def buy(store: DocStore, buyer: PlayerInstance, listing_id: str, seller: PlayerInstance,
        commit: Callable[[List[PlayerInstance], Dict], None]) -> Dict:
    doc = store.load(listing_id)
    if doc is None:
        raise MarketError("No such listing.")
    if doc["status"] != "active":
        raise MarketError("That listing has already been sold or cancelled.")
    if doc["a"] != seller.user_id:
        raise MarketError("That listing belongs to someone else.")
    st = doc["state"]
    if buyer.user_id == seller.user_id:
        raise MarketError("You can't buy your own listing — cancel it to take the Pokémon back.")
    if _now() >= st["expires"]:
        raise MarketError("That listing has expired. The seller can cancel it to take the Pokémon back.")
    price = int(st["price"])
    if buyer.coins < price:
        raise MarketError(f"You need {price} coins for this Pokémon.")
    fee = price * FEE_PERCENT // 100

    mon = PokemonInstance.from_dict(st["pokemon"])
    mon.trainer_id = buyer.user_id
    buyer.coins -= price
    seller.coins += price - fee
    _put_back(buyer, mon)
    doc["status"] = "sold"
    doc["b"] = buyer.user_id
    doc["state"] = {**st, "sold_for": price, "sold_at": _now()}
    try:
        commit([buyer, seller], doc)
    except ListingNotActive as e:
        _undo_buy(buyer, seller, mon, price, fee)
        raise MarketError("Someone else bought that Pokémon a moment before you.") from e
    except ConcurrentUpdateError as e:
        _undo_buy(buyer, seller, mon, price, fee)
        raise MarketError("The market was busy — please try that purchase again.") from e
    except Exception:
        _undo_buy(buyer, seller, mon, price, fee)
        raise
    buyer.record_caught(mon.species_name)
    dex = (mon.api_data or {}).get("id")
    if dex:
        buyer.pokedex_seen.add(dex)
    return {"ok": True, "message": f"You bought {mon.nickname} for {price} coins!",
            "pokemon": mon.to_dict(), "fee": fee}


def _undo_buy(buyer: PlayerInstance, seller: PlayerInstance, mon, price: int, fee: int) -> None:
    """A purchase that didn't save changes nothing: put the coins and the Pokémon back where they were."""
    buyer.coins += price
    seller.coins -= price - fee
    trade_system._take_pokemon(buyer, mon.id)


def cancel(store: DocStore, seller: PlayerInstance, listing_id: str,
           commit: Callable[[List[PlayerInstance], Dict], None]) -> Dict:
    doc = store.load(listing_id)
    if doc is None:
        raise MarketError("No such listing.")
    if doc["a"] != seller.user_id:
        raise MarketError("That listing isn't yours.")
    if doc["status"] != "active":
        raise MarketError("That listing has already been sold or cancelled.")
    mon = PokemonInstance.from_dict(doc["state"]["pokemon"])
    _put_back(seller, mon)
    doc["status"] = "cancelled"
    try:
        commit([seller], doc)
    except ListingNotActive as e:
        _take_back_out(seller, mon)
        raise MarketError("That listing was just sold, so it can't be cancelled.") from e
    except Exception:
        _take_back_out(seller, mon)
        raise
    return {"ok": True, "message": f"{mon.nickname} is back with you.", "pokemon": mon.to_dict()}


def _take_back_out(player: PlayerInstance, mon) -> None:
    trade_system._take_pokemon(player, mon.id)
