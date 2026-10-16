"""
POSHOW — text glyphs for battle logs and menus.

Plain monochrome Unicode symbols instead of colourful modern emoji (the chunky emoji clash with the pixel / CRT look).
They render in the game's own font colour on the website and as text on Telegram. One table, so the whole look can be
changed in one place.
"""

MOVE = "▸"        # a move is used
HIT = "◆"         # damage dealt
SUPER = "▲"       # super effective
WEAK = "▽"        # not very effective
CRIT = "★"        # critical hit
MISS = "×"        # a miss
IMMUNE = "∅"      # no effect
HP = "♥"          # HP readout
HEAL = "✚"        # healing / drain
RECOIL = "↯"      # recoil, chip damage
FAINT = "✖"       # fainted
WIN = "✔"
STATUS = "≋"      # status condition
UP = "↑"          # stat rose
DOWN = "↓"        # stat fell
WEATHER = "≈"
ABILITY = "◇"
SLEEP = "z"
POISON = "☠"
