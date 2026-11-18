import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# Data guards: the game's encounter/trainer tables must only name species the offline data can serve, and
# legacy names must keep loading. These run against the real data files (no network).
import json
import pokeapi_manager as _pm
# The harness swaps PokéAPI for a small fake. These tests must exercise the real offline path
# (pokeapi_manager.get_pokemon reads species_data first), so put the real method back for this file.
_pm.pokeapi.get_pokemon = type(_pm.pokeapi).get_pokemon.__get__(_pm.pokeapi)
import species_data as sd
import rules
from pokemon_model import PokemonInstance
from route_encounters import ALL_ROUTES
import region_kalos

ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

# ── the audit itself reports no errors (this is the guard for every future data change)
sys.path.insert(0, os.path.join(root, "tools"))
import audit_species
report = audit_species.audit()
ok(not report["errors"], f"species audit has no errors {report['errors'][:3]}")
ok(report["referenced_count"] > 200, f"audit reads the real game tables ({report['referenced_count']} species)")

# ── the mangled key is gone everywhere it was used
ok("flabb" not in sd.SPECIES and "flabebe" in sd.SPECIES, "species.json uses flabebe, not flabb")
ok("flabb" not in sd.EXTRA, "species_extra.json has no flabb stub")
kalos_pools = [pool for _, pool, *_ in region_kalos.WILD.values()]
ok(all("flabb" not in p for p in kalos_pools) and any("flabebe" in p for p in kalos_pools),
   "Kalos wild tables use flabebe")
evo = json.load(open(os.path.join(root, "api", "_lib", "data", "evolutions.json")))
ok(any(e["to"] == "floette" for e in evo.get("flabebe", [])), "Flabébé still evolves into Floette")

# ── a saved Pokémon from before the rename still loads, with its real data
ok(sd.canonical("flabb") == "flabebe" and sd.resolve_legacy_name("flabb") == "flabebe", "legacy name maps to flabebe")
ok(sd.resolve_legacy_name("pikachu") == "pikachu", "unrelated names are left exactly as stored")
legacy = PokemonInstance("flabb", 20, 1)
ok(legacy.species_name == "flabebe", "a constructed legacy Pokémon is stored under flabebe")
ok(legacy.ability in ("flower_veil", "flower-veil", "symbiosis"), f"legacy Flabébé has its real ability (got {legacy.ability})")
ok(any(m for _, m in sd.learnset("flabb")), "legacy Flabébé has its learnset")
restored = PokemonInstance.from_dict({"species_name": "flabb", "level": 20, "trainer_id": 1,
                                      "id": "11111111-1111-1111-1111-111111111111", "iv": {}, "ev": {}})
ok(restored.species_name == "flabebe", "a saved 'flabb' row reloads as flabebe")

# ── evolution inheritance still works through the renamed key
ok("moonblast" in [m for _, m in sd.learnset_inherited("floette")], "Floette inherits Flabébé's moves")

# ── the audit's own error detection actually fires (guards against a silently empty audit)
saved = dict(sd.SPECIES)
try:
    sd.SPECIES["flabb"] = {"id": 669, "t": ["fairy"], "s": [1, 1, 1, 1, 1, 1], "a": []}
    ok(any("legacy key" in e for e in audit_species.audit()["errors"]), "audit flags a legacy key in species.json")
finally:
    sd.SPECIES.clear(); sd.SPECIES.update(saved)
saved_routes = dict(ALL_ROUTES)
try:
    region_kalos.WILD["kalos_route_1"][1]["nosuchmon"] = 5
    ok(any("nosuchmon" in e for e in audit_species.audit()["errors"]),
       "audit flags a game table that names a species missing from species.json")
finally:
    region_kalos.WILD["kalos_route_1"][1].pop("nosuchmon", None)

# ── the name slug used by the generator folds accents instead of dropping letters
import importlib.util
spec = importlib.util.spec_from_file_location("build_data_check", os.path.join(root, "tools", "build_data.py"))
src = open(spec.origin, encoding="utf-8").read()
slug_ns = {"__file__": spec.origin}
exec(src.split("# ── moves")[0].replace('os.makedirs(OUT, exist_ok=True)', ''), slug_ns)
slug = slug_ns["slug"]
ok(slug("Flabébé") == "flabebe", "generator slug: Flabébé -> flabebe")
ok(slug("Nidoran♀") == "nidoran-f" and slug("Nidoran♂") == "nidoran-m", "generator slug keeps Nidoran's gender suffixes")
ok(slug("Farfetch’d") == "farfetchd" and slug("Mr. Mime") == "mr-mime", "generator slug keeps the usual names")

print("ALL PASS")
