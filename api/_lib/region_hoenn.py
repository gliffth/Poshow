"""
Hoenn campaign data (Pokémon Emerald order): map, wild tables, gym leaders, rival, Elite Four, Champion.
Pure data — journey.py turns it into trainers and routes. Same shape as region_kalos.py.
Authored from the games' rosters and level curve without a data source to check against; check them against the games before relying on exact teams.
"""

REGION = "hoenn"
START = "littleroot_town"
LEAGUE_AT = "hoenn_pokemon_league"

MAP = {
    "littleroot_town": {"name": "Littleroot Town", "kind": "town", "heal": "Your house", "desc": "A quiet town where the wind carries the scent of fresh grass.", "exits": ["hoenn_route_101"]},
    "hoenn_route_101": {"name": "Route 101", "kind": "route", "encounter": "hoenn_route_101", "desc": "A short road of tall grass beside the first trees.", "exits": ["littleroot_town", "oldale_town"]},
    "oldale_town": {"name": "Oldale Town", "kind": "town", "heal": "Pokémon Center", "desc": "A small town where three roads meet.", "exits": ["hoenn_route_101", "hoenn_route_102", "hoenn_route_103"]},
    "hoenn_route_103": {"name": "Route 103", "kind": "route", "encounter": "hoenn_route_103", "desc": "A seaside road where trainers like to practise.", "exits": ["oldale_town"]},
    "hoenn_route_102": {"name": "Route 102", "kind": "route", "encounter": "hoenn_route_102", "desc": "A pond-side road leading west.", "exits": ["oldale_town", "petalburg_city"]},
    "petalburg_city": {"name": "Petalburg City", "kind": "town", "heal": "Pokémon Center", "desc": "A bustling city with a Gym at its heart.", "exits": ["hoenn_route_102", "hoenn_route_104", "hoenn_route_105", "hoenn_route_112"]},
    "hoenn_route_104": {"name": "Route 104", "kind": "route", "encounter": "hoenn_route_104", "req": {"defeated": "h_rival_1"}, "desc": "A coastal path with a flower shop at the far end.", "exits": ["petalburg_city", "petalburg_woods"]},
    "petalburg_woods": {"name": "Petalburg Woods", "kind": "route", "encounter": "petalburg_woods", "desc": "A dim forest where little Pokémon hide in the leaves.", "exits": ["hoenn_route_104", "rustboro_city"]},
    "rustboro_city": {"name": "Rustboro City", "kind": "town", "heal": "Pokémon Center", "desc": "A city of stone buildings and a famous rock-hard Gym.", "exits": ["petalburg_woods", "hoenn_route_116"]},
    "hoenn_route_105": {"name": "Route 105", "kind": "route", "encounter": "hoenn_route_105", "req": {"defeated": "roxanne"}, "desc": "A sea route of warm water and shallow reefs.", "exits": ["petalburg_city", "dewford_town"]},
    "dewford_town": {"name": "Dewford Town", "kind": "town", "heal": "Pokémon Center", "desc": "A small island town where the surf never stops.", "exits": ["hoenn_route_105"]},
    "hoenn_route_116": {"name": "Route 116", "kind": "route", "encounter": "hoenn_route_116", "req": {"defeated": "roxanne"}, "desc": "A road of trees and a rumbling tunnel entrance.", "exits": ["rustboro_city", "rusturf_tunnel"]},
    "rusturf_tunnel": {"name": "Rusturf Tunnel", "kind": "route", "encounter": "rusturf_tunnel", "desc": "A dark tunnel dug by someone who loves a quiet town.", "exits": ["hoenn_route_116", "verdanturf_town"]},
    "verdanturf_town": {"name": "Verdanturf Town", "kind": "town", "heal": "Pokémon Center", "desc": "A peaceful town where the air is always clean.", "exits": ["rusturf_tunnel", "hoenn_route_117"]},
    "hoenn_route_117": {"name": "Route 117", "kind": "route", "encounter": "hoenn_route_117", "desc": "A flowery road with a Pokémon Day Care.", "exits": ["verdanturf_town", "mauville_city"]},
    "mauville_city": {"name": "Mauville City", "kind": "town", "heal": "Pokémon Center", "desc": "A lively city of lights, bikes and a very electric Gym.", "exits": ["hoenn_route_117", "hoenn_route_110", "hoenn_route_111", "hoenn_route_118"]},
    "hoenn_route_110": {"name": "Route 110", "kind": "route", "encounter": "hoenn_route_110", "desc": "A long road beside a cycling lane.", "exits": ["mauville_city"]},
    "hoenn_route_111": {"name": "Route 111", "kind": "route", "encounter": "hoenn_route_111", "req": {"defeated": "wattson"}, "desc": "A road that turns into a hot desert.", "exits": ["mauville_city", "lavaridge_town"]},
    "lavaridge_town": {"name": "Lavaridge Town", "kind": "town", "heal": "Pokémon Center", "desc": "A hot-spring town beneath a smoking mountain.", "exits": ["hoenn_route_111", "hoenn_route_112"]},
    "hoenn_route_112": {"name": "Route 112", "kind": "route", "encounter": "hoenn_route_112", "req": {"defeated": "flannery"}, "desc": "A rocky path along the foot of the volcano.", "exits": ["lavaridge_town", "petalburg_city"]},
    "hoenn_route_118": {"name": "Route 118", "kind": "route", "encounter": "hoenn_route_118", "req": {"defeated": "norman"}, "desc": "A river road leading east of the city.", "exits": ["mauville_city", "hoenn_route_119"]},
    "hoenn_route_119": {"name": "Route 119", "kind": "route", "encounter": "hoenn_route_119", "desc": "A rainy jungle road with a river running through it.", "exits": ["hoenn_route_118", "fortree_city"]},
    "fortree_city": {"name": "Fortree City", "kind": "town", "heal": "Pokémon Center", "desc": "A city of houses built in the treetops.", "exits": ["hoenn_route_119", "hoenn_route_120"]},
    "hoenn_route_120": {"name": "Route 120", "kind": "route", "encounter": "hoenn_route_120", "req": {"defeated": "winona"}, "desc": "A misty road with a small stream.", "exits": ["fortree_city", "hoenn_route_121"]},
    "hoenn_route_121": {"name": "Route 121", "kind": "route", "encounter": "hoenn_route_121", "desc": "A road of long grass that ends at the sea.", "exits": ["hoenn_route_120", "lilycove_city"]},
    "lilycove_city": {"name": "Lilycove City", "kind": "town", "heal": "Pokémon Center", "desc": "A harbour city with a grand department store.", "exits": ["hoenn_route_121", "hoenn_route_124"]},
    "hoenn_route_124": {"name": "Route 124", "kind": "route", "encounter": "hoenn_route_124", "desc": "Open water with coral reefs below.", "exits": ["lilycove_city", "mossdeep_city"]},
    "mossdeep_city": {"name": "Mossdeep City", "kind": "town", "heal": "Pokémon Center", "desc": "An island city with a space centre on the cliff.", "exits": ["hoenn_route_124", "hoenn_route_126"]},
    "hoenn_route_126": {"name": "Route 126", "kind": "route", "encounter": "hoenn_route_126", "req": {"defeated": "tate_liza"}, "desc": "Deep blue water above a hidden crater.", "exits": ["mossdeep_city", "sootopolis_city"]},
    "sootopolis_city": {"name": "Sootopolis City", "kind": "town", "heal": "Pokémon Center", "desc": "A city inside a volcano crater, ringed by water.", "exits": ["hoenn_route_126", "hoenn_route_128"]},
    "hoenn_route_128": {"name": "Route 128", "kind": "route", "encounter": "hoenn_route_128", "req": {"gyms": 8}, "desc": "A wide sea passage toward the League.", "exits": ["sootopolis_city", "hoenn_victory_road"]},
    "hoenn_victory_road": {"name": "Victory Road", "kind": "route", "encounter": "hoenn_victory_road", "desc": "A great cave. Only trainers with eight badges ever see its end.", "exits": ["hoenn_route_128", "hoenn_pokemon_league"]},
    "hoenn_pokemon_league": {"name": "Hoenn Pokémon League", "kind": "town", "heal": "League lobby", "desc": "The League. Four masters and a Champion wait beyond the doors.", "exits": ["hoenn_victory_road"]},
}

STARTER_LINES = {
    "grass": ("treecko", "grovyle", "sceptile"),
    "fire": ("torchic", "combusken", "blaziken"),
    "water": ("mudkip", "marshtomp", "swampert"),
}

GYMS = [
    dict(id="roxanne", name="Roxanne", title="Rustboro City Gym Leader", at="rustboro_city", badge="Stone Badge",
         team=[("geodude", 12), ("geodude", 12), ("nosepass", 15)], coins=800, items={"potion": 3},
         requires={"defeated": "h_rival_1"},
         intro="I'm Roxanne. I study rocks, and I battle as carefully as I study. Show me what you've learned.",
         win="So I was beaten... Please take the Stone Badge."),
    dict(id="brawly", name="Brawly", title="Dewford Town Gym Leader", at="dewford_town", badge="Knuckle Badge",
         team=[("machop", 16), ("meditite", 16), ("makuhita", 19)], coins=1200, items={"potion": 3},
         intro="I'm Brawly! Dewford's waves made me strong, and I'm going to ride you right off the board!",
         win="Whoa, you wiped me out! The Knuckle Badge is yours."),
    dict(id="wattson", name="Wattson", title="Mauville City Gym Leader", at="mauville_city", badge="Dynamo Badge",
         team=[("voltorb", 20), ("electrike", 20), ("magneton", 22), ("manectric", 24)], coins=1800, items={"superpotion": 2},
         requires={"defeated": "brawly"},
         intro="Wahahahah! I'm Wattson, and I'm going to give you a shock to remember!",
         win="Wahahahah! You've charged me up! The Dynamo Badge is yours."),
    dict(id="flannery", name="Flannery", title="Lavaridge Town Gym Leader", at="lavaridge_town", badge="Heat Badge",
         team=[("numel", 24), ("slugma", 24), ("camerupt", 26), ("torkoal", 29)], coins=2400, items={"superpotion": 3},
         intro="I'm Flannery! I'm new here, but my fire is as hot as any leader's. Let's burn!",
         win="Oh... I guess I need to heat up my training! Take the Heat Badge."),
    dict(id="norman", name="Norman", title="Petalburg City Gym Leader", at="petalburg_city", badge="Balance Badge",
         team=[("spinda", 27), ("vigoroth", 27), ("linoone", 29), ("slaking", 31)], coins=3000, items={"hyperpotion": 2},
         requires={"defeated": "flannery"},
         intro="I'm Norman. Every trainer who walks in here has grown. Show me how far you've come.",
         win="I lost... You've outgrown this Gym. The Balance Badge is yours."),
    dict(id="winona", name="Winona", title="Fortree City Gym Leader", at="fortree_city", badge="Feather Badge",
         team=[("swablu", 29), ("tropius", 29), ("pelipper", 30), ("skarmory", 31), ("altaria", 33)], coins=3600, items={"hyperpotion": 2},
         requires={"defeated": "h_rival_3"},
         intro="I'm Winona. I fly with the wind, and my Pokémon do too. Can you keep up?",
         win="No one has ever flown past me. The Feather Badge is yours."),
    dict(id="tate_liza", name="Tate & Liza", title="Mossdeep City Gym Leaders", at="mossdeep_city", badge="Mind Badge",
         team=[("solrock", 42), ("lunatone", 42), ("claydol", 41), ("xatu", 41)], coins=4400, items={"hyperpotion": 3},
         intro="We are Tate and Liza. Two minds, one battle. Can you handle us both?",
         win="Our minds were not enough. Take the Mind Badge."),
    dict(id="juan", name="Juan", title="Sootopolis City Gym Leader", at="sootopolis_city", badge="Rain Badge",
         team=[("luvdisc", 41), ("whiscash", 41), ("sealeo", 43), ("crawdaunt", 43), ("kingdra", 46)], coins=5200, items={"rare_candy": 2},
         requires={"gyms": 7}, perfect=True,
         intro="I am Juan. Water bends and so do I, but I do not break. Show me your art.",
         win="Bravo. The Rain Badge is yours."),
]

RIVAL_NAME = "Brendan"
RIVALS = [
    dict(id="h_rival_1", at="hoenn_route_103", requires={}, coins=500, items={"potion": 2},
         intro="There you are! Let's see what our partners can do. A friendly battle!",
         win="You're good! Let's both get stronger."),
    dict(id="h_rival_2", at="hoenn_route_110", requires={"defeated": "brawly"}, coins=1500, items={"superpotion": 1},
         intro="I've been training hard since Dewford. Ready for round two?",
         win="Wow, you've really improved. I'll keep up."),
    dict(id="h_rival_3", at="hoenn_route_119", requires={"defeated": "norman"}, coins=3200, items={"hyperpotion": 2},
         intro="We keep running into each other. I won't hold back this time!",
         win="You win again... but I'm getting closer!"),
    dict(id="h_rival_4", at="hoenn_victory_road", requires={"gyms": 8}, coins=5200, items={"maxpotion": 2},
         intro="This is it. Everything I've learned goes into this battle!",
         win="I gave it my all. Go on and show the Champion what you've got."),
]
RIVAL_SPECS = {
    "h_rival_1": lambda base, mid, fin: [(base, 5)],
    "h_rival_2": lambda base, mid, fin: [("zigzagoon", 16), ("wingull", 17), (mid, 19)],
    "h_rival_3": lambda base, mid, fin: [("swellow", 28), ("kirlia", 27), ("nincada", 27), (mid, 31)],
    "h_rival_4": lambda base, mid, fin: [("swellow", 52), ("gardevoir", 51), ("ninjask", 52), ("lanturn", 51), ("breloom", 52), (fin, 55)],
}

STORY_ORDER = ["h_rival_1", "roxanne", "brawly", "h_rival_2", "wattson", "flannery", "norman", "h_rival_3", "winona",
               "tate_liza", "juan", "h_rival_4", "sidney", "phoebe", "glacia", "drake", "hoenn_champion"]

ELITE_FOUR = [
    dict(id="sidney", name="Sidney", title="Elite Four — Dark", coins=5500,
         team=[("mightyena", 46), ("shiftry", 48), ("cacturne", 46), ("crawdaunt", 48), ("absol", 49)],
         requires={"gyms": 8, "defeated": "h_rival_4"},
         intro="I'm Sidney. I don't mind a rough battle, so long as it's a good one. Let's go!",
         win="Well, how about that. You've got style. On you go."),
    dict(id="phoebe", name="Phoebe", title="Elite Four — Ghost", coins=5500,
         team=[("dusclops", 48), ("banette", 49), ("banette", 49), ("sableye", 50), ("dusclops", 51)],
         requires={"defeated": "sidney"},
         intro="I'm Phoebe. I trained on the mountain where the spirits drift. Let's see how brave you are.",
         win="Oh, my... You're stronger than the ghosts. Go ahead."),
    dict(id="glacia", name="Glacia", title="Elite Four — Ice", coins=5800,
         team=[("glalie", 50), ("sealeo", 50), ("sealeo", 52), ("glalie", 52), ("walrein", 53)],
         requires={"defeated": "phoebe"},
         intro="I'm Glacia. I came all this way for a battle that makes my blood run hot. Don't disappoint me.",
         win="You and your Pokémon... how hot your spirits burn. Go on."),
    dict(id="drake", name="Drake", title="Elite Four — Dragon", coins=6000,
         team=[("shelgon", 52), ("altaria", 54), ("flygon", 53), ("flygon", 53), ("salamence", 55)],
         requires={"defeated": "glacia"},
         intro="I'm Drake. Raising dragons takes trust, and trust takes time. Show me what you've built.",
         win="You've earned my respect. Go and face the Champion."),
]
CHAMPION = dict(id="hoenn_champion", name="Steven", title="Hoenn Pokémon League Champion", coins=12000,
                items={"rare_candy": 5, "exp_all": 1},
                team=[("skarmory", 57), ("claydol", 55), ("aggron", 56), ("cradily", 56), ("armaldo", 56), ("metagross", 58)],
                requires={"defeated": "drake"},
                intro="I'm Steven, the Champion of Hoenn. I want to see the bond between you and your Pokémon.",
                win="Congratulations. You are the new Champion of Hoenn!")

WILD = {
    "hoenn_route_101": ("Route 101", {"zigzagoon": 45, "wurmple": 35, "poochyena": 30}, "ralts", 0.008, (2, 4)),
    "hoenn_route_103": ("Route 103", {"zigzagoon": 40, "poochyena": 35, "wingull": 25}, "taillow", 0.01, (3, 5)),
    "hoenn_route_102": ("Route 102", {"zigzagoon": 25, "wurmple": 25, "lotad": 25, "seedot": 25, "ralts": 8}, "surskit", 0.01, (3, 6)),
    "hoenn_route_104": ("Route 104", {"wurmple": 35, "taillow": 30, "wingull": 25, "marill": 10}, "roselia", 0.01, (4, 7)),
    "petalburg_woods": ("Petalburg Woods", {"wurmple": 25, "silcoon": 10, "cascoon": 10, "shroomish": 25, "slakoth": 15, "taillow": 20}, "breloom", 0.006, (5, 8)),
    "hoenn_route_116": ("Route 116", {"nincada": 25, "taillow": 25, "whismur": 25, "abra": 10}, "skitty", 0.01, (6, 9)),
    "rusturf_tunnel": ("Rusturf Tunnel", {"whismur": 45, "makuhita": 35, "zubat": 20}, "aron", 0.01, (8, 11)),
    "hoenn_route_105": ("Route 105", {"tentacool": 40, "wingull": 35, "wailmer": 15, "pelipper": 10}, "chinchou", 0.01, (12, 15)),
    "hoenn_route_117": ("Route 117", {"oddish": 30, "roselia": 20, "illumise": 15, "volbeat": 15, "gulpin": 20}, "ditto", 0.01, (12, 15)),
    "hoenn_route_110": ("Route 110", {"electrike": 30, "plusle": 15, "minun": 15, "gulpin": 25, "oddish": 15}, "manectric", 0.01, (13, 16)),
    "hoenn_route_111": ("Route 111", {"sandshrew": 25, "trapinch": 25, "cacnea": 20, "baltoy": 20, "silcoon": 10}, "cacturne", 0.01, (20, 24)),
    "hoenn_route_112": ("Route 112", {"numel": 40, "machop": 20, "marill": 20, "mightyena": 20}, "slugma", 0.01, (18, 22)),
    "hoenn_route_118": ("Route 118", {"electrike": 25, "linoone": 25, "wingull": 20, "zigzagoon": 15, "kecleon": 10}, "manectric", 0.01, (24, 27)),
    "hoenn_route_119": ("Route 119", {"oddish": 25, "tropius": 12, "kecleon": 20, "linoone": 20, "feebas": 8, "castform": 15}, "feebas", 0.012, (25, 28)),
    "hoenn_route_120": ("Route 120", {"oddish": 25, "marill": 20, "kecleon": 20, "absol": 5, "mightyena": 20, "seedot": 10}, "absol", 0.01, (25, 28)),
    "hoenn_route_121": ("Route 121", {"shuppet": 20, "duskull": 20, "mightyena": 20, "gloom": 20, "linoone": 20}, "kecleon", 0.01, (26, 30)),
    "hoenn_route_124": ("Route 124", {"tentacruel": 35, "wailmer": 25, "chinchou": 20, "pelipper": 20}, "clamperl", 0.01, (30, 34)),
    "hoenn_route_126": ("Route 126", {"tentacruel": 35, "wailmer": 25, "chinchou": 20, "corsola": 20}, "relicanth", 0.008, (34, 38)),
    "hoenn_route_128": ("Route 128", {"tentacruel": 30, "wailord": 25, "huntail": 15, "gorebyss": 15, "carvanha": 15}, "luvdisc", 0.01, (40, 45)),
    "hoenn_victory_road": ("Victory Road", {"golbat": 20, "hariyama": 15, "loudred": 15, "medicham": 15, "whiscash": 10, "aron": 25}, "lairon", 0.012, (40, 46)),
}
