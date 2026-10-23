"""
Compile extra per-species data from a PokeAPI-derived dump (the "Pokego" reference data) into small files:

    POKEGO_DATA=/path/to/Pokego/data/pokemon python tools/build_pokego.py

Writes api/_lib/data/species_extra.json:
    c  real capture rate        a  abilities [[name, is_hidden], ...]     g  gender rate (-1 genderless, 0-8 = eighths female)
    e  egg groups               l  level-up learnset [[level, move], ...] (most recent game that has one)

…and api/_lib/data/abilities_info.json (ability -> short description, from the PokeDex).
Only the compact result is committed; the 25 MB dump is not needed at runtime.
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "api", "_lib", "data")
SRC = os.environ.get("POKEGO_DATA")
VG_ORDER = ["scarlet-violet", "sword-shield", "ultra-sun-ultra-moon", "brilliant-diamond-shining-pearl",
            "omega-ruby-alpha-sapphire", "heartgold-soulsilver", "firered-leafgreen"]


def main():
    if not SRC or not os.path.isdir(SRC):
        raise SystemExit("Set POKEGO_DATA to the folder containing the per-species JSON files.")
    extra = {}
    for path in glob.glob(os.path.join(SRC, "*.json")):
        d = json.load(open(path, encoding="utf-8"))
        name = d["name"]
        by_vg = {}
        for m in d.get("moves", []):
            for l in m.get("learn", []):
                if l["method"] == "level-up":
                    by_vg.setdefault(l["version_group"], set()).add((int(l["level"]), m["name"]))
        learn = []
        for vg in VG_ORDER:
            if len(by_vg.get(vg, ())) >= 3:
                learn = sorted(by_vg[vg])
                break
        if not learn and by_vg:
            learn = sorted(max(by_vg.values(), key=len))
        extra[name] = {
            "c": d.get("capture_rate", 45),
            "a": [[a["name"], bool(a.get("is_hidden"))] for a in sorted(d.get("abilities", []), key=lambda a: a.get("slot", 9))],
            "g": d.get("gender_rate", -1),
            "e": d.get("egg_groups", []),
            "l": [[lv, mv] for lv, mv in learn],
        }
    with open(os.path.join(OUT, "species_extra.json"), "w", encoding="utf-8") as f:
        json.dump(extra, f, separators=(",", ":"), ensure_ascii=False)
    print(f"species_extra: {len(extra)} species, {os.path.getsize(os.path.join(OUT, 'species_extra.json')) // 1024} KB")

    # ability descriptions from the PokeDex
    dex = os.path.join(ROOT, "PokeDex", "Ability", "abilities.json")
    if os.path.exists(dex):
        info = {}
        for a in json.load(open(dex, encoding="utf-8")):
            key = re.sub(r"[^a-z0-9]+", "_", a["name"].lower()).strip("_")
            info[key] = {"n": a["name"], "d": (a.get("short_description") or a.get("effect") or "")[:160]}
        with open(os.path.join(OUT, "abilities_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, separators=(",", ":"), ensure_ascii=False)
        print(f"abilities_info: {len(info)} abilities")


if __name__ == "__main__":
    main()
