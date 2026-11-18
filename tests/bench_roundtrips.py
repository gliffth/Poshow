import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Counts database round trips per game action (run: python3 tests/bench_roundtrips.py). Not a pass/fail test.
sys.path.insert(0, os.path.join(root, "tests"))
import fake_supabase as F
fake = F.install(F.GOOD); os.environ["SUPABASE_URL"] = "http://fake"; os.environ["SUPABASE_KEY"] = "k"
import random, accounts, requests as rq, index
from index import *
random.seed(2)
calls = []
def wrap(name):
    real = getattr(rq, name)
    def f(url, *a, **k):
        calls.append((name.upper(), url.split("/rest/v1/")[-1].split("?")[0])); return real(url, *a, **k)
    setattr(rq, name, f)
for n in ("get", "post", "patch", "delete"): wrap(n)
def count(label, fn):
    calls.clear(); out = fn(); n = len(calls); print(f"{n:3d}  {label}   {[c[1] for c in calls]}"); return out
u = auth_register(RegisterRequest(username="Bench_1", password="secret1"))["user_id"]
choose_starter(StarterRequest(user_id=u, region="kanto", species="charmander"))
p = get_or_create_player(u)
for sp in ("pidgey", "rattata", "zubat", "abra", "onix", "geodude", "meowth", "mankey"):
    p.catch_pokemon(PokemonInstance(sp, 12, u)); p.pokemon_collection.append(p.active_team[-1]) if False else None
    p.pokemon_collection.append(PokemonInstance(sp, 12, u))
p.pokeballs["pokeball"] = 50; p.inventory["potion"] = 20; persist_player(p)
count("roster", lambda: get_roster(u))
count("journey state", lambda: journey_state(u))
count("travel", lambda: journey_travel(TravelRequest(user_id=u, to="route_1")))
tok = accounts.make_encounter_token(u, "pidgey", 5)
bt = count("start battle", lambda: start_battle(StartBattleRequest(user_id=u, target_species="pidgey", target_level=5, encounter_token=tok)))
bid = bt["battle_id"]; mv = next(m["id"] for m in bt["player_pokemon"]["moves"] if (m.get("power") or 0) > 0)
count("battle move (turn goes on)", lambda: battle_move(MoveRequest(battle_id=bid, move_name=mv)))
count("battle item", lambda: battle_item(ItemRequest(battle_id=bid, item_type="potion")))
count("failed catch", lambda: battle_catch(CatchRequest(battle_id=bid, ball_type="pokeball")))
tok = accounts.make_encounter_token(u, "pidgey", 5)
bt = start_battle(StartBattleRequest(user_id=u, target_species="pidgey", target_level=5, encounter_token=tok)); bid = bt["battle_id"]
rec = index._sessions.load(bid); rec["wild_pokemon"]["current_hp"] = 1; index._sessions.save(bid, u, rec["player_pokemon"], rec["wild_pokemon"])
count("battle move (win)", lambda: battle_move(MoveRequest(battle_id=bid, move_name=mv)))
count("care state", lambda: care_state(u) if "care_state" in dir(index) else None)
count("shop buy", lambda: shop_buy(BuyRequest(user_id=u, item_id="potion", quantity=1)) if "shop_buy" in dir(index) else None)
print("players in DB:", len(fake.rows["players"]), "| pokemon rows:", len(fake.rows["pokemon"]))
