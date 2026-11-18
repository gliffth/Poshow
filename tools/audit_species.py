"""
Audit the offline species data against what the game really uses.

    python tools/audit_species.py          # human-readable report; exit code 1 if there are errors

What it checks
  ERROR    a species named in a route, trainer or gym table has no entry in species.json
           (battles would fall back to the network, and a failed lookup breaks the battle)
  ERROR    a species.json key is not a PokeAPI-style slug, or a legacy alias is still used as a key
  ERROR    a species in species.json has no species_extra record (no capture rate)
  ERROR    a species named in the game tables has no capture rate
  WARNING  a species named in the game tables has no abilities or no level-up learnset
  INFO     national-dex numbers with no entry in species.json (mostly forms and alternates)

It only reads data; it never writes. The regression test in tests/test_species_audit.py uses the same checks.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.path.insert(0, os.path.join(ROOT, "api", "_lib"))

_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# species the games give no level-up moves (Ditto learns Transform, not from a level-up table)
EXPECTED_NO_LEARNSET = {"ditto"}


def _walk_teams(obj, out, depth=0):
    """Collect species from every {'team': [(species, level), ...]} structure reachable from obj."""
    if depth > 6:
        return
    if isinstance(obj, dict):
        team = obj.get("team")
        if isinstance(team, (list, tuple)):
            for item in team:
                if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
                    out.add(item[0].lower())
        for v in obj.values():
            _walk_teams(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_teams(v, out, depth + 1)


def referenced_species():
    """-> {species: [where it is used, ...]} for every species the game's tables name."""
    import route_encounters
    import route_data
    import region_johto
    import region_kalos
    from species_data import resolve_legacy_name

    where = {}

    def add(name, origin):
        if not name:
            return
        key = resolve_legacy_name(str(name)).lower()
        where.setdefault(key, set()).add(origin)

    # wild tables: region modules (tuples of name, {species: weight}, rare, rate, levels)
    for mod in (region_johto, region_kalos):
        for rid, entry in mod.WILD.items():
            pool, rare = entry[1], entry[2]
            for sp in pool:
                add(sp, f"{mod.REGION} wild {rid}")
            add(rare, f"{mod.REGION} rare {rid}")

    # Kanto and the other RouteEncounter objects
    for rid, enc in route_encounters.ALL_ROUTES.items():
        for sp in (getattr(enc, "pokemon_pool", None) or {}):
            add(sp, f"wild {rid}")
        add(getattr(enc, "rare_species", None), f"rare {rid}")

    # trainers, gym leaders, Elite Four, champions, rivals: every {'team': [...]} in the campaign modules
    for mod in (region_johto, region_kalos, route_data):
        names = set()
        _walk_teams(vars(mod), names)
        for sp in names:
            add(sp, f"{mod.__name__} trainer team")

    return where


def audit():
    import species_data as sd

    errors, warnings, info = [], [], []
    species = sd.SPECIES
    extra = sd.EXTRA

    # 1. keys in species.json must be slugs and must not be legacy aliases
    for key in species:
        if not _SLUG.match(key):
            errors.append(f"species.json key '{key}' is not a PokeAPI-style slug")
        if key in sd._ALIASES:
            errors.append(f"species.json still uses legacy key '{key}' (should be '{sd._ALIASES[key]}')")

    # 2. every base species needs a capture rate record
    for key in species:
        if key not in extra or "c" not in extra[key]:
            errors.append(f"'{key}' has no capture rate in species_extra.json")

    # 3. everything the game tables use must exist in the data, with abilities and learnset
    used = referenced_species()
    for sp in sorted(used):
        where = sorted(used[sp])
        if sp not in species:
            errors.append(f"'{sp}' is used by the game ({where[0]}) but is missing from species.json")
            continue
        ex = extra.get(sp, {})
        if not ex.get("a"):
            warnings.append(f"'{sp}' has no abilities (used by {where[0]})")
        if not ex.get("l") and sp not in EXPECTED_NO_LEARNSET:
            warnings.append(f"'{sp}' has no level-up learnset (used by {where[0]})")

    # 4. national-dex numbers with no species entry
    ids = sorted(v["id"] for v in species.values() if isinstance(v.get("id"), int))
    present = set(ids)
    absent = [n for n in range(1, (ids[-1] if ids else 0) + 1) if n not in present]
    if absent:
        info.append(f"{len(absent)} national-dex numbers have no species.json entry "
                    f"(forms and alternates): {absent}")

    return {"errors": errors, "warnings": warnings, "info": info,
            "species_count": len(species), "referenced_count": len(used)}


def main():
    r = audit()
    print(f"species.json: {r['species_count']} species; game tables reference {r['referenced_count']}")
    for level, items in (("ERROR", r["errors"]), ("WARNING", r["warnings"]), ("INFO", r["info"])):
        for msg in items:
            print(f"{level:8} {msg}")
    if not (r["errors"] or r["warnings"] or r["info"]):
        print("clean")
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
