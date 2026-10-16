"""
Compile the scraped PokeDex JSON into the small data files the game ships with.

    python tools/build_data.py        # writes api/_lib/data/{moves,evolutions,natures}.json

The API and the bot load only those compact files, so deployments don't need the 6 MB PokeDex folder.
Re-run after changing anything under PokeDex/.
"""
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEX = os.path.join(ROOT, "PokeDex")
OUT = os.path.join(ROOT, "api", "_lib", "data")
os.makedirs(OUT, exist_ok=True)


def slug(name: str) -> str:
    n = name.lower().replace(" ", "-").replace("♀", "-f").replace("♂", "-m")
    return re.sub(r"[^a-z0-9-]", "", n)


# ── moves ────────────────────────────────────────────────────────────
STAT_WORDS = [("special attack", "spa"), ("special defense", "spd"), ("attack", "atk"), ("defense", "def"),
              ("speed", "spe"), ("accuracy", "acc"), ("evasiveness", "eva")]
STATUS_WORDS = [("paralyz", "par"), ("burn", "brn"), ("badly poison", "tox"), ("poison", "psn"),
                ("sleep", "slp"), ("freez", "frz")]


def parse_effects(effect: str, chance, category: str):
    """Turn the effect sentence into a small list of structured effects."""
    fx = []
    if not effect:
        return fx
    e = effect.strip()
    low = e.lower()
    ch = int(chance) if chance else (100 if category == "x" else 0)

    # stat stages
    for m in re.finditer(r"(may )?(sharply |drastically )?(raises|lowers|lower|raise) (user's|opponent's|the user's|its|their)? ?([a-z' ,]+?)(?:\.| and then|,? but| by | for |$)", low):
        may, mag, verb, who, stats = m.groups()
        n = 3 if mag and "drastic" in mag else 2 if mag else 1
        by = re.match(r"\s*(one|two|three|1|2|3) stage", low[m.end():m.end() + 20])
        if by:
            n = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}[by.group(1)]
        if verb.startswith("lower"):
            n = -n
        target = "self" if who and ("user" in who or who == "its") else "foe"
        if "all stats" in stats or "all of" in stats:
            names = ["atk", "def", "spa", "spd", "spe"]
        else:
            names = []
            rest = stats
            for word, code in STAT_WORDS:                    # longest words first (special attack before attack)
                if word in rest:
                    names.append(code)
                    rest = rest.replace(word, "")
        for code in names:
            fx.append(["stage", code, n, (ch if may or category != "x" else 100) or 100, target])
    # status conditions
    if "opponent" in low and any(k in low for k in ("paralyz", "burn", "poison", "sleep", "freez")):
        for word, code in STATUS_WORDS:
            if word in low and not (code == "psn" and "badly" in low):
                fx.append(["status", code, ch or 100, "foe"])
                break
    if "confuses opponent" in low or "may confuse" in low:
        fx.append(["confuse", ch or 100])
    if "flinch" in low:
        fx.append(["flinch", ch or 30])
    if "recovers half the hp inflicted" in low or "recovers 50% of the damage" in low:
        fx.append(["drain", 0.5])
    elif re.search(r"user recovers (half|50%)", low) and category == "x":
        fx.append(["heal", 0.5])
    if "recoil" in low:
        fx.append(["recoil", 0.25])
    if "hits 2-5 times" in low:
        fx.append(["multihit", 2, 5])
    elif "hits twice" in low:
        fx.append(["multihit", 2, 2])
    elif "hits thrice" in low:
        fx.append(["multihit", 3, 3])
    if "at least 1 hp" in low:
        fx.append(["falseswipe"])
    if "power doubles if user is burned" in low:
        fx.append(["facade"])
    if low.startswith("user faints") or "user faints" in low:
        fx.append(["selfko"])
    if "must recharge" in low:
        fx.append(["recharge"])
    return fx


def build_moves():
    raw = json.load(open(os.path.join(DEX, "Moves", "moves.json"), encoding="utf-8"))
    out = {}
    for m in raw:
        cat = {"Physical": "p", "Special": "s", "Status": "x"}.get(m.get("category"))
        name = m.get("name") or ""
        if not cat or m.get("pp") in (None, 0, 1) and not name:
            continue
        if name.startswith(("Max ", "G-Max ")) or "Z-Move" in (m.get("effect") or "") or "Max Move" in (m.get("effect") or ""):
            continue
        acc = m.get("accuracy")
        priority = 1 if (m.get("effect") or "").lower().startswith("user attacks first") else 0
        out[slug(name)] = {
            "t": (m.get("type") or "Normal").lower(),
            "c": cat,
            "p": int(m["power"]) if isinstance(m.get("power"), (int, float)) else 0,
            "a": int(acc) if isinstance(acc, (int, float)) else 0,          # 0 = never misses / self-targeting
            "pp": int(m["pp"]) if isinstance(m.get("pp"), (int, float)) and m["pp"] > 1 else 5,
            "pr": priority,
            "fx": parse_effects(m.get("effect"), m.get("effect_probability"), cat),
        }
    return out


# ── natures ──────────────────────────────────────────────────────────
KEYMAP = {"attack": "atk", "defense": "def", "special_attack": "spa", "special_defense": "spd", "speed": "spe"}


def build_natures():
    raw = json.load(open(os.path.join(DEX, "Nature", "natures.json"), encoding="utf-8"))["natures"]
    out = {}
    for n in raw:
        if n.get("is_neutral"):
            out[n["name"]] = {"up": None, "down": None}
        else:
            out[n["name"]] = {"up": KEYMAP.get(n["increases"]), "down": KEYMAP.get(n["decreases"])}
    out["Neutral"] = {"up": None, "down": None}
    return out


# ── evolutions ───────────────────────────────────────────────────────
DEFAULT_LEVEL = {"friendship": 28, "time": 30, "move": 30, "location": 30, "gender": 30, "battle_move": 30,
                 "attack_defense": 20, "special": 36}


def build_evolutions(valid):
    raw = json.load(open(os.path.join(DEX, "Evolutions", "evolutions.json"), encoding="utf-8"))
    out = {}
    for e in raw:
        if e["from"].get("form_name") or e["to"].get("form_name"):
            continue
        a, b = slug(e["from"]["name"]), slug(e["to"]["name"])
        if a not in valid or b not in valid:
            continue
        conds = e["conditions"]
        rule = None
        for c in conds:
            t = c["type"]
            if t == "level":
                rule = ["level", int(c["level"])]
                break
        if rule is None:
            for c in conds:
                t = c["type"]
                if t in ("stone", "item"):
                    item = c.get("item") or {}
                    rule = ["item", slug(item.get("name", "stone")).replace("-", "_")]
                    break
                if t in ("trade", "trade_item"):
                    rule = ["trade"]            # Trade Cable evolves both plain trade and trade-with-item species
                    break
        if rule is None and conds:
            rule = ["level", DEFAULT_LEVEL.get(conds[0]["type"], 30)]
        if rule:
            out.setdefault(a, [])
            if all(x["to"] != b for x in out[a]):
                out[a].append({"to": b, "rule": rule})
    return out


# ── species (offline replacement for PokeAPI in battles) ────────────
LEGENDARY = {"articuno", "zapdos", "moltres", "mewtwo", "mew", "raikou", "entei", "suicune", "lugia", "ho-oh", "celebi",
             "regirock", "regice", "registeel", "latias", "latios", "kyogre", "groudon", "rayquaza", "jirachi", "deoxys",
             "uxie", "mesprit", "azelf", "dialga", "palkia", "heatran", "regigigas", "giratina", "cresselia", "darkrai",
             "shaymin", "arceus", "cobalion", "terrakion", "virizion", "tornadus", "thundurus", "landorus", "reshiram",
             "zekrom", "kyurem", "xerneas", "yveltal", "zygarde", "solgaleo", "lunala", "necrozma", "zacian", "zamazenta",
             "eternatus", "koraidon", "miraidon"}


def build_species():
    raw = json.load(open(os.path.join(DEX, "Names", "pokemon.json"), encoding="utf-8"))
    out = {}
    for p in raw:
        if p.get("form_name"):
            continue
        b = p["base_stats"]
        out[slug(p["name"])] = {
            "id": p["pokedex_number"],
            "t": [t.lower() for t in p["types"]],
            "s": [b["hp"], b["attack"], b["defense"], b["special_attack"], b["special_defense"], b["speed"]],
            "a": [],
        }
    # abilities: each ability file entry lists the Pokémon that can have it (regular + hidden)
    import ast
    abil = json.load(open(os.path.join(DEX, "Ability", "abilities.json"), encoding="utf-8"))
    for a in abil:
        aname = slug(a["name"]).replace("-", "_")
        for field, hidden in (("pokemon", False), ("hidden_ability_pokemon", True)):
            raw_list = a.get(field)
            if not raw_list:
                continue
            try:
                lst = raw_list if isinstance(raw_list, list) else ast.literal_eval(raw_list)
            except Exception:
                continue
            for pk in lst:
                if pk.get("form_name"):
                    continue
                rec = out.get(slug(pk["name"]))
                if rec is not None and aname not in rec["a"]:
                    rec["a"].append(("~" if hidden else "") + aname)
    return out


def main():
    names = json.load(open(os.path.join(DEX, "Names", "pokemon.json"), encoding="utf-8"))
    valid = {slug(p["name"]) for p in names if not p.get("form_name")}
    moves, natures, evos, species = build_moves(), build_natures(), build_evolutions(valid), build_species()
    for name, data in (("moves", moves), ("natures", natures), ("evolutions", evos), ("species", species)):
        path = os.path.join(OUT, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
        print(f"{name}: {len(data)} entries, {os.path.getsize(path) // 1024} KB")
    kinds = Counter(r["rule"][0] for lst in evos.values() for r in lst)
    print("evolution rules:", dict(kinds))


if __name__ == "__main__":
    main()
