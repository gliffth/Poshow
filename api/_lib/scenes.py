"""
POSHOW — procedural pixel-art scenery and tiny cutscene animations (PNG / GIF)

Every picture is drawn from code (original art: nothing to license, nothing to host) in a 160x90 pixel
canvas and upscaled with nearest-neighbour:

  region  landscape of one of the nine regions        route   a path through tall grass
  town    houses + a Pokémon Center                    care    Nurse Joy's counter
  lab     a research lab

`render_png(...)` gives a still, `render_gif(...)` a short looping animation (the trainer walks in, clouds
drift, Poké Balls wobble). Pure standard library — the web app and the Telegram bot both use these.
The admin can override any scene with an uploaded/hosted image (see admin_system.ASSET_KEYS).
"""

import functools
import math
import random
import struct
import zlib
from typing import Dict, List, Optional, Tuple

import avatars

W, H = 160, 90
Color = Tuple[int, int, int]


def _hex(c: str) -> Color:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))   # type: ignore


class Canvas:
    def __init__(self, w=W, h=H, bg: Color = (0, 0, 0)):
        self.w, self.h = w, h
        self.px: List[List[Color]] = [[bg] * w for _ in range(h)]

    def set(self, x: int, y: int, c: Color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def rect(self, x, y, w, h, c: Color):
        for yy in range(max(0, int(y)), min(self.h, int(y + h))):
            row = self.px[yy]
            for xx in range(max(0, int(x)), min(self.w, int(x + w))):
                row[xx] = c

    def copy(self) -> "Canvas":
        n = Canvas(self.w, self.h)
        n.px = [list(r) for r in self.px]
        return n

    def blit(self, sprite: List[List[Tuple[int, int, int, int]]], x: int, y: int, flip: bool = False):
        for sy, row in enumerate(sprite):
            for sx, p in enumerate(row[::-1] if flip else row):
                if p[3]:
                    self.set(x + sx, y + sy, p[:3])


# ── themes ──────────────────────────────────────────────────────────
THEMES: Dict[str, Dict] = {
    "kanto":  dict(sky=("#6fb3f2", "#d6ecff"), sun="#fff3b0", far="#7fa8c9", mid="#5aa05a", ground="#4f9b4a", path="#d9c28a",
                   feat="houses", tree=("#2f6b2f", "#3f8a3a"), accent="#e05a4f"),
    "johto":  dict(sky=("#f2a65a", "#ffe0b0"), sun="#fff0c0", far="#b07a5a", mid="#c9803a", ground="#a86a2a", path="#e0c08a",
                   feat="pagoda", tree=("#b5481f", "#d9822b"), accent="#7a2e2e"),
    "hoenn":  dict(sky=("#3fb8e8", "#bff0ff"), sun="#fffbd0", far="#4fa4c4", mid="#2f9e6a", ground="#3fae5a", path="#f0dca0",
                   feat="sea", tree=("#1f7a4a", "#2fa05a"), accent="#ff8a5a"),
    "sinnoh": dict(sky=("#a9bfd8", "#eef4fb"), sun="#ffffff", far="#8fa3bd", mid="#dfe8f2", ground="#f4f8fc", path="#c9d4e0",
                   feat="peaks", tree=("#1f4a3a", "#2f6a4a"), accent="#7a8fb5"),
    "unova":  dict(sky=("#3a4a8a", "#e8a0a0"), sun="#ffe0a0", far="#4a5a8a", mid="#3a4a6a", ground="#4a5568", path="#8a94a8",
                   feat="city", tree=("#2f5a3a", "#3f7a4a"), accent="#ffd24a"),
    "kalos":  dict(sky=("#e8a8d8", "#fff0f8"), sun="#fff8e0", far="#c8a8d8", mid="#9ad09a", ground="#82c282", path="#f0d8e0",
                   feat="tower", tree=("#4f8a5a", "#6fb07a"), accent="#e05a8a"),
    "alola":  dict(sky=("#ff9a5a", "#ffe08a"), sun="#fff2a0", far="#8a5a7a", mid="#2f9a7a", ground="#e8c882", path="#f4dca0",
                   feat="volcano", tree=("#1f7a4a", "#3fae6a"), accent="#ff5a8a"),
    "galar":  dict(sky=("#8a98a8", "#d8e0e8"), sun="#f0f0f0", far="#7a8a8a", mid="#5a8a5a", ground="#4a7a4a", path="#b8b0a0",
                   feat="castle", tree=("#2f5a3a", "#3f7a4a"), accent="#c04a4a"),
    "paldea": dict(sky=("#4fc0f0", "#e0f6ff"), sun="#fffbd0", far="#c98a5a", mid="#d9a45a", ground="#7aae4a", path="#e8d09a",
                   feat="mesas", tree=("#3f8a3a", "#5faa4a"), accent="#8a5ac8"),
}
OUTLINE = _hex("#1b1b24")


def _sky(c: Canvas, th: Dict, horizon: int):
    top, bot = _hex(th["sky"][0]), _hex(th["sky"][1])
    for y in range(horizon):
        t = y / max(1, horizon - 1)
        band = int(t * 7) / 7                    # banded, not smooth → reads as pixel art
        c.rect(0, y, c.w, 1, _mix(top, bot, band))


def _sun(c: Canvas, th: Dict, cx=124, cy=20, r=7):
    col = _hex(th["sun"])
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            if x * x + y * y <= r * r:
                c.set(cx + x, cy + y, col)


def _cloud(c: Canvas, x: int, y: int, light: Color = (255, 255, 255)):
    shade = _mix(light, (170, 190, 215), 0.5)
    for dx, dy, w in ((2, 0, 8), (0, 1, 14), (1, 2, 12)):
        c.rect(x + dx, y + dy, w, 1, light if dy < 2 else shade)


def _hills(c: Canvas, base: int, amp: float, color: Color, seed: int, freq=0.07):
    rnd = random.Random(seed)
    p1, p2 = rnd.random() * 6, rnd.random() * 6
    for x in range(c.w):
        h = base - int(amp * (0.6 * math.sin(x * freq + p1) + 0.4 * math.sin(x * freq * 2.3 + p2)))
        c.rect(x, h, 1, c.h - h, color)


def _tree(c: Canvas, x: int, y: int, cols: Tuple[Color, Color], pine=False):
    trunk = _hex("#5a3a24")
    c.rect(x + 2, y - 3, 2, 4, trunk)
    dark, light = cols
    if pine:
        for i, w in enumerate((3, 5, 7)):
            c.rect(x + 3 - w // 2, y - 5 - i * 3 - 2, w, 3, dark if i % 2 else light)
    else:
        c.rect(x, y - 9, 6, 7, dark)
        c.rect(x + 1, y - 10, 4, 2, light)
        c.rect(x + 1, y - 8, 2, 2, light)


def _house(c: Canvas, x: int, y: int, wall: Color, roof: Color, w=14, h=9):
    c.rect(x - 1, y - h - 5, w + 2, 1, OUTLINE)
    for i in range(5):
        c.rect(x - 1 + i, y - h - 4 + i, w + 2 - 2 * i, 1, roof)
    c.rect(x, y - h, w, h, wall)
    c.rect(x + w // 2 - 1, y - 5, 3, 5, _hex("#6a4a2a"))
    c.rect(x + 2, y - h + 2, 3, 3, _hex("#bfe4ff"))


def _center(c: Canvas, x: int, y: int):
    c.rect(x - 1, y - 18, 26, 18, OUTLINE)
    c.rect(x, y - 17, 24, 17, _hex("#f4f0e8"))
    c.rect(x - 1, y - 21, 26, 5, _hex("#e0505a"))
    c.rect(x + 8, y - 15, 8, 8, _hex("#ffffff"))
    c.rect(x + 11, y - 14, 2, 6, _hex("#e0505a"))
    c.rect(x + 9, y - 12, 6, 2, _hex("#e0505a"))
    c.rect(x + 9, y - 6, 6, 6, _hex("#7ac4e8"))


def _features(c: Canvas, th: Dict, seed: int, horizon: int):
    f = th["feat"]
    far, mid = _hex(th["far"]), _hex(th["mid"])
    if f == "peaks":
        for i, (x, hgt) in enumerate(((20, 34), (62, 42), (108, 30), (146, 38))):
            for yy in range(hgt):
                half = yy * 0.7
                c.rect(x - half, horizon - hgt + yy, half * 2, 1, far if yy > hgt * 0.3 else (255, 255, 255))
    elif f == "mesas":
        for x, w, hgt in ((14, 30, 22), (70, 24, 30), (118, 34, 20)):
            c.rect(x, horizon - hgt, w, hgt, far)
            c.rect(x, horizon - hgt, w, 3, _mix(far, (255, 230, 190), 0.5))
    elif f == "city":
        rnd = random.Random(seed)
        x = 0
        while x < c.w:
            w, hgt = rnd.randint(6, 12), rnd.randint(14, 40)
            c.rect(x, horizon - hgt, w, hgt, _mix(far, (20, 30, 60), 0.3))
            for wy in range(horizon - hgt + 3, horizon - 2, 4):
                for wx in range(x + 2, x + w - 2, 3):
                    if rnd.random() < 0.55:
                        c.set(wx, wy, _hex(th["accent"]))
            x += w + 1
    elif f == "tower":
        cx = 100
        for yy in range(46):
            half = max(1, int(14 * (1 - yy / 46) ** 1.6) + 1)
            c.rect(cx - half, horizon - 46 + yy, half * 2, 1, _mix(far, (255, 255, 255), 0.3 + 0.4 * (yy / 46)))
        c.rect(cx - 1, horizon - 52, 3, 8, far)
    elif f == "pagoda":
        for i in range(4):
            w = 22 - i * 4
            c.rect(100 - w // 2, horizon - 12 - i * 8, w, 2, _hex("#7a2e2e"))
            c.rect(100 - w // 2 + 2, horizon - 10 - i * 8, w - 4, 6, _hex("#d9b27a"))
    elif f == "castle":
        for x, w, hgt in ((84, 40, 18), (80, 6, 30), (118, 6, 30)):
            c.rect(x, horizon - hgt, w, hgt, _mix(far, (40, 40, 50), 0.25))
        for x in range(84, 124, 6):
            c.rect(x, horizon - 21, 3, 3, _mix(far, (40, 40, 50), 0.25))
    elif f == "volcano":
        for yy in range(30):
            half = 6 + yy
            c.rect(100 - half, horizon - 30 + yy, half * 2, 1, far)
        c.rect(96, horizon - 31, 9, 2, _hex("#ff6a3a"))
    elif f == "sea":
        c.rect(0, horizon - 8, c.w, 8, _hex("#2f8ac8"))
        for x in range(0, c.w, 9):
            c.rect(x, horizon - 6 + (x // 9) % 3, 4, 1, _hex("#8fd4f4"))


def _scenery(region: str, kind: str, seed: int = 7) -> Canvas:
    th = THEMES.get(region, THEMES["kanto"])
    c = Canvas()
    horizon = 52
    _sky(c, th, horizon)
    _sun(c, th)
    far = _hex(th["far"])
    c.rect(0, horizon, c.w, c.h - horizon, _mix(far, _hex(th["mid"]), 0.4))     # no gaps behind the hills
    _features(c, th, seed, horizon)
    _hills(c, horizon + 4, 6, _mix(far, _hex(th["mid"]), 0.5), seed)
    _hills(c, horizon + 10, 5, _hex(th["mid"]), seed + 3, 0.09)
    c.rect(0, horizon + 14, c.w, c.h, _hex(th["ground"]))
    # grass texture
    rnd = random.Random(seed + 11)
    g = _hex(th["ground"])
    for _ in range(260):
        x, y = rnd.randrange(c.w), rnd.randrange(horizon + 15, c.h)
        c.set(x, y, _mix(g, (255, 255, 255), 0.14))
        c.set(x + 1, y, _mix(g, (0, 0, 0), 0.12))
    tc = (_hex(th["tree"][0]), _hex(th["tree"][1]))
    pine = region in ("sinnoh",)

    if kind == "route":
        # winding lane
        pc = _hex(th["path"])
        for y in range(horizon + 14, c.h):
            t = (y - horizon - 14) / (c.h - horizon - 14)
            cx = 80 + int(math.sin(y * 0.18) * 10 * (1 - t))
            half = 10 + int(t * 26)
            c.rect(cx - half, y, half * 2, 1, pc)
            c.rect(cx - half, y, 1, 1, _mix(pc, (0, 0, 0), 0.25))
            c.rect(cx + half - 1, y, 1, 1, _mix(pc, (0, 0, 0), 0.25))
        for x, y in ((10, 62), (26, 74), (136, 64), (146, 78), (44, 82), (118, 84)):
            _tree(c, x, y, tc, pine)
        for x in range(4, 156, 11):                                   # tall grass tufts
            for y in (80, 85):
                if abs(x - 80) > 36:
                    c.rect(x, y, 1, 3, _hex(th["tree"][1]))
                    c.rect(x + 2, y + 1, 1, 2, _hex(th["tree"][0]))
    elif kind == "town":
        pc = _hex(th["path"])
        c.rect(0, 70, c.w, 8, pc)
        _center(c, 22, 70)
        wall = _hex("#f0e4d0")
        for i, x in enumerate((60, 90, 122)):
            _house(c, x, 70, wall, _hex(th["accent"]) if i % 2 == 0 else _mix(_hex(th["accent"]), (60, 60, 90), 0.5))
        for x, y in ((8, 66), (150, 66)):
            _tree(c, x, y, tc, pine)
    elif kind == "region":
        for x, y in ((12, 74), (30, 66), (128, 70), (146, 76), (60, 80)):
            _tree(c, x, y, tc, pine)
        if th["feat"] in ("houses", "sea", "mesas", "peaks", "tower"):
            _house(c, 44, 70, _hex("#f0e4d0"), _hex(th["accent"]))
            _house(c, 66, 72, _hex("#e8dcc4"), _mix(_hex(th["accent"]), (60, 60, 90), 0.5), 12, 8)
        pc = _hex(th["path"])
        for y in range(70, c.h):
            c.rect(80 - (y - 66) // 3 - 6, y, 12 + (y - 66) // 1.5, 1, pc)
    elif kind == "care":
        c = Canvas(bg=_hex("#f7e9ee"))
        c.rect(0, 0, c.w, 56, _hex("#fbeef2"))
        for x in range(0, c.w, 16):                                   # wall panels
            c.rect(x, 0, 1, 56, _hex("#f0d4de"))
        c.rect(0, 56, c.w, 34, _hex("#d8b9a0"))                       # floor
        for x in range(0, c.w, 20):
            c.rect(x, 56, 1, 34, _hex("#c4a088"))
        c.rect(0, 54, c.w, 3, _hex("#e8a0b4"))
        c.rect(20, 40, 120, 16, _hex("#f4a8be"))                       # counter
        c.rect(20, 40, 120, 2, _hex("#ffd0de"))
        c.rect(70, 8, 20, 18, OUTLINE)                                  # red-cross sign
        c.rect(71, 9, 18, 16, _hex("#ffffff"))
        c.rect(78, 11, 4, 12, _hex("#e0505a"))
        c.rect(74, 15, 12, 4, _hex("#e0505a"))
        for x in (30, 118):                                             # healing machine + balls
            c.rect(x, 30, 22, 10, OUTLINE)
            c.rect(x + 1, 31, 20, 8, _hex("#9ab4d8"))
            for i in range(3):
                c.rect(x + 3 + i * 6, 33, 4, 4, _hex("#e0505a"))
    elif kind == "lab":
        c = Canvas(bg=_hex("#c9ccd6"))
        c.rect(0, 0, c.w, 50, _hex("#aab0c0"))
        for x in range(8, 150, 40):
            c.rect(x, 8, 28, 22, OUTLINE)
            c.rect(x + 1, 9, 26, 20, _hex("#8fd0f0"))
        c.rect(0, 50, c.w, 40, _hex("#8a6a4a"))
        for x in range(0, c.w, 14):
            c.rect(x, 50, 1, 40, _hex("#6e5238"))
        c.rect(56, 54, 52, 14, _hex("#b8bcc8"))                         # table
        c.rect(56, 54, 52, 2, _hex("#dfe3ec"))
    return c


# ── drawing the trainer ──────────────────────────────────────────────
@functools.lru_cache(maxsize=64)
def _walker(avatar_id: str, frame: int):
    base = avatars._pixels(avatar_id)
    rows = [list(r) for r in base]
    clear = (0, 0, 0, 0)
    foot = rows[18]
    shoe = next((p for p in foot if p[3]), clear)
    if frame % 2:           # step: legs together, body bobs a pixel
        legs = [[clear] * 16 for _ in range(3)]
        for r, src in zip((0, 1, 2), (15, 16, 18)):
            for x in range(5, 11):
                legs[r][x] = rows[src][5] if rows[src][5][3] else rows[src][6]
        rows[17], rows[18], rows[19] = legs
        for x in range(5, 11):
            rows[18][x] = shoe
        rows = [[clear] * 16] + rows[:19]
    return rows


def _put_trainer(c: Canvas, avatar_id: str, x: int, ground_y: int, frame: int, flip=False):
    c.blit(_walker(avatar_id, frame), x, ground_y - avatars.HEIGHT, flip)


def _pokeball(c: Canvas, x: int, y: int, wobble: int = 0):
    red, white, dark = _hex("#e0505a"), _hex("#f4f4f4"), OUTLINE
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            d = dx * dx + dy * dy
            if d <= 20:
                col = dark if d > 12 else (red if dy < 0 else white)
                if abs(dy) <= 0:
                    col = dark
                c.set(x + dx + wobble, y + dy, col)
    c.set(x + wobble, y, white)
    c.set(x + wobble + 1, y, white)


# ── frames ──────────────────────────────────────────────────────────
def _frames(kind: str, region: str, avatar_id: str, n: int = 12) -> List[Canvas]:
    base = _scenery(region, kind)
    ground = {"route": 84, "town": 84, "region": 84, "care": 82, "lab": 82}.get(kind, 84)
    out = []
    for i in range(n):
        f = base.copy()
        # drifting clouds
        if kind in ("route", "town", "region"):
            for k, (cx, cy) in enumerate(((10, 8), (70, 14), (120, 6))):
                _cloud(f, int((cx + i * (1 + k) * 1.5) % 190) - 20, cy)
        if kind in ("route", "town"):
            x = int(-16 + (W + 16) * (i / (n - 1))) if kind == "route" else int(150 - (150 - 40) * (i / (n - 1)))
            _put_trainer(f, avatar_id, x, ground, i, flip=(kind == "town"))
        elif kind == "region":
            x = int(-16 + (80 + 16) * min(1.0, i / (n * 0.6)))
            _put_trainer(f, avatar_id, x, ground, i if i < n * 0.6 else 0)
            for k, bx in enumerate((104, 120, 136)):
                _pokeball(f, bx, ground - 6 + (1 if (i + k) % 3 == 0 else 0), wobble=1 if (i + k) % 4 == 0 else 0)
        elif kind == "care":
            _put_trainer(f, avatar_id, 28, ground, i // 3)
            _joy(f, 112, 56, i)
        elif kind == "lab":
            _put_trainer(f, avatar_id, 70 + (i % 2), ground, 0)
            for k, bx in enumerate((66, 82, 98)):
                _pokeball(f, bx, 58 + (1 if (i + k) % 4 == 0 else 0))
        out.append(f)
    return out


def _joy(c: Canvas, x: int, y: int, frame: int):
    """Nurse Joy: pink hair with two buns, white dress, pink cap trim (original pixel design)."""
    pink, skin, white, dark = _hex("#f49ac0"), _hex("#fbd8c0"), _hex("#ffffff"), OUTLINE
    c.rect(x - 7, y - 24, 6, 6, pink)
    c.rect(x + 3, y - 24, 6, 6, pink)
    c.rect(x - 4, y - 22, 12, 12, pink)
    c.rect(x - 3, y - 17, 10, 9, skin)
    c.rect(x - 2, y - 15, 2, 2, dark)
    c.rect(x + 3, y - 15, 2, 2, dark)
    c.rect(x - 1, y - 11, 4, 1, _hex("#e07a8a"))
    c.rect(x - 5, y - 8, 14, 14, white)
    c.rect(x - 5, y - 8, 14, 1, _hex("#f49ac0"))
    c.rect(x + 1, y - 6, 2, 6, _hex("#e0505a"))
    c.rect(x - 1, y - 4, 6, 2, _hex("#e0505a"))
    arm = -2 if frame % 4 < 2 else 0                                   # little wave
    c.rect(x + 9, y - 8 + arm, 3, 8, white)
    c.rect(x + 9, y - 10 + arm, 3, 3, skin)


# ── encoders (stdlib only) ───────────────────────────────────────────
def _png(c: Canvas, scale: int) -> bytes:
    rows = []
    for row in c.px:
        line = b"".join(bytes(p) for p in row for _ in range(scale))
        rows.extend([b"\x00" + line] * scale)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", c.w * scale, c.h * scale, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
            + chunk(b"IEND", b""))


def _quantize(frames: List[Canvas]):
    palette: Dict[Color, int] = {}
    for f in frames:
        for row in f.px:
            for p in row:
                if p not in palette:
                    palette[p] = len(palette)
    if len(palette) > 256:                                              # merge to a 6x6x6 cube + greys
        def snap(p: Color) -> Color:
            return tuple(min(255, int(round(v / 51)) * 51) for v in p)  # type: ignore
        palette = {}
        for f in frames:
            for y, row in enumerate(f.px):
                for x, p in enumerate(row):
                    q = snap(p)
                    f.px[y][x] = q
                    if q not in palette:
                        palette[q] = len(palette)
    return palette


def _lzw(indices: List[int], min_code: int) -> bytes:
    clear, end = 1 << min_code, (1 << min_code) + 1
    code_size = min_code + 1
    table = {bytes([i]): i for i in range(clear)}
    nxt = end + 1
    out_bits: List[int] = []
    buf, nbits = 0, 0
    out = bytearray()

    def emit(code: int):
        nonlocal buf, nbits
        buf |= code << nbits
        nbits += code_size
        while nbits >= 8:
            out.append(buf & 0xFF)
            buf >>= 8
            nbits -= 8

    emit(clear)
    cur = b""
    for idx in indices:
        nb = cur + bytes([idx])
        if nb in table:
            cur = nb
        else:
            emit(table[cur])
            table[nb] = nxt
            nxt += 1
            if nxt > (1 << code_size) and code_size < 12:
                code_size += 1
            if nxt >= 4095:
                emit(clear)
                table = {bytes([i]): i for i in range(clear)}
                nxt = end + 1
                code_size = min_code + 1
            cur = bytes([idx])
    if cur:
        emit(table[cur])
    emit(end)
    if nbits:
        out.append(buf & 0xFF)
    return bytes(out)


def _gif(frames: List[Canvas], scale: int, delay_cs: int) -> bytes:
    palette = _quantize(frames)
    size_bits = max(1, (len(palette) - 1).bit_length())
    table_size = 1 << size_bits
    min_code = max(2, size_bits)
    w, h = frames[0].w * scale, frames[0].h * scale
    out = bytearray(b"GIF89a")
    out += struct.pack("<HHBBB", w, h, 0x80 | 0x70 | (size_bits - 1), 0, 0)
    pal = bytearray(3 * table_size)
    for col, i in palette.items():
        pal[i * 3:i * 3 + 3] = bytes(col)
    out += pal
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"                 # loop forever
    for f in frames:
        idx: List[int] = []
        for row in f.px:
            line = [palette[p] for p in row for _ in range(scale)]
            for _ in range(scale):
                idx.extend(line)
        out += b"\x21\xf9\x04\x04" + struct.pack("<H", delay_cs) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0)
        out.append(min_code)
        data = _lzw(idx, min_code)
        for i in range(0, len(data), 255):
            blk = data[i:i + 255]
            out.append(len(blk))
            out += blk
        out.append(0)
    out.append(0x3B)
    return bytes(out)


# ── public API ───────────────────────────────────────────────────────
KINDS = ("region", "route", "town", "care", "lab")


def _norm(kind: str, region: str, avatar_id: str):
    kind = kind if kind in KINDS else "region"
    region = region if region in THEMES else "kanto"
    avatar_id = avatar_id if avatars.is_valid(avatar_id) else avatars.DEFAULT_AVATAR
    return kind, region, avatar_id


@functools.lru_cache(maxsize=128)
def render_png(kind: str = "region", region: str = "kanto", avatar_id: str = "ember", scale: int = 4) -> bytes:
    kind, region, avatar_id = _norm(kind, region, avatar_id)
    scale = max(1, min(8, int(scale)))
    frame = _frames(kind, region, avatar_id, 12)[-1 if kind in ("route", "town", "region") else 4]
    return _png(frame, scale)


@functools.lru_cache(maxsize=64)
def render_gif(kind: str = "route", region: str = "kanto", avatar_id: str = "ember", scale: int = 3) -> bytes:
    kind, region, avatar_id = _norm(kind, region, avatar_id)
    scale = max(1, min(5, int(scale)))
    return _gif(_frames(kind, region, avatar_id, 12), scale, 14)


def region_slide(region: str, scale: int = 4) -> bytes:
    """Scenery only (no trainer) for the 'pick your region' slideshow."""
    region = region if region in THEMES else "kanto"
    return _render_scenery_png(region, scale)


@functools.lru_cache(maxsize=32)
def _render_scenery_png(region: str, scale: int) -> bytes:
    c = _scenery(region, "region")
    for k in range(3):
        _pokeball(c, 104 + k * 16, 78)
    return _png(c, max(1, min(8, int(scale))))
