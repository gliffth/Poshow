"""
POSHOW — trainer avatars (original pixel art, generated from code)

One 16x20 sprite template + six palettes. There are no image files to host or license:
  * the web app loads  GET /api/avatars/<id>.png
  * the Telegram bot sends the same PNG bytes
  * later, story scenes will use this sprite as the player character
"""

import struct
import zlib
from typing import Dict, List, Tuple

# O outline, C cap, H hair, K skin, W eye-white, S shirt, P pants, B shoes, A shirt accent, . transparent
_TEMPLATE = [
    "......OOOO......",
    "....OOCCCCOO....",
    "...OCCCCCCCCO...",
    "..OCCCCCCCCCCO..",
    "..OCCCCCCCCCCO..",
    "..OHHOOOOOOHHO..",
    "..OHKKKKKKKKHO..",
    "..OKKWOKKOWKKO..",
    "...OKKKKKKKKO...",
    "....OKKKKKKO....",
    "....OSSAASSO....",
    "...OSSSAASSSO...",
    "..OKOSSSSSSOKO..",
    "..OKOSSSSSSOKO..",
    "..OOOSSSSSSOOO..",
    "....OPPPPPPO....",
    "....OPPOOPPO....",
    "....OPPO.OPPO...",
    "....OBBO.OBBO...",
    "....OOO...OOO...",
]
WIDTH, HEIGHT = len(_TEMPLATE[0]), len(_TEMPLATE)
assert all(len(r) == WIDTH for r in _TEMPLATE)

_BASE = {"O": "#1b1b24", "W": "#ffffff", "B": "#3a2f2a"}

AVATARS: Dict[str, Dict] = {
    "ember":  {"name": "Ember",  "pal": {"C": "#d94b3a", "H": "#2a1d18", "K": "#f1c9a1", "S": "#2f6fb5", "A": "#e8e8e8", "P": "#3b4a73"}},
    "marina": {"name": "Marina", "pal": {"C": "#3d8fd1", "H": "#6a3f26", "K": "#d9a577", "S": "#f2f2f2", "A": "#3d8fd1", "P": "#2e4a6b"}},
    "sprout": {"name": "Sprout", "pal": {"C": "#4da34f", "H": "#1d1d1d", "K": "#8d5a3b", "S": "#e6c34a", "A": "#4da34f", "P": "#4a4036"}},
    "dusk":   {"name": "Dusk",   "pal": {"C": "#6b4fa8", "H": "#e8e0f0", "K": "#f4d6bd", "S": "#2b2b3a", "A": "#b79cf0", "P": "#23232f"}},
    "sunny":  {"name": "Sunny",  "pal": {"C": "#f2b632", "H": "#b5651d", "K": "#c98a5e", "S": "#d9573f", "A": "#f2b632", "P": "#355a4b"}},
    "frost":  {"name": "Frost",  "pal": {"C": "#5fc4c9", "H": "#243b55", "K": "#e9bfa0", "S": "#7a8fa6", "A": "#e8f4f5", "P": "#3b4a5c"}},
}
DEFAULT_AVATAR = "ember"


def is_valid(avatar_id) -> bool:
    return avatar_id in AVATARS


def list_avatars() -> List[Dict[str, str]]:
    return [{"id": k, "name": v["name"]} for k, v in AVATARS.items()]


def _rgba(hex_color: str) -> Tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255


def _pixels(avatar_id: str) -> List[List[Tuple[int, int, int, int]]]:
    pal = {**_BASE, **AVATARS.get(avatar_id, AVATARS[DEFAULT_AVATAR])["pal"]}
    clear = (0, 0, 0, 0)
    return [[(_rgba(pal[ch]) if ch in pal else clear) for ch in row] for row in _TEMPLATE]


def _png(rows: List[List[Tuple[int, int, int, int]]]) -> bytes:
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _scale(rows, k: int):
    out = []
    for row in rows:
        wide = [px for px in row for _ in range(k)]
        out.extend([list(wide) for _ in range(k)])
    return out


def render_png(avatar_id: str, scale: int = 8) -> bytes:
    """Nearest-neighbour upscaled sprite, transparent background."""
    return _png(_scale(_pixels(avatar_id), max(1, min(32, scale))))


def render_sheet(scale: int = 6, gap: int = 2, bg: str = "#2a2f33") -> bytes:
    """All avatars side by side on a solid background — one image for Telegram's picker."""
    ids = list(AVATARS)
    cell_w = WIDTH + gap
    total_w = cell_w * len(ids) + gap
    total_h = HEIGHT + gap * 2
    canvas = [[_rgba(bg)] * total_w for _ in range(total_h)]
    for n, aid in enumerate(ids):
        px = _pixels(aid)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if px[y][x][3]:
                    canvas[gap + y][gap + n * cell_w + x] = px[y][x]
    return _png(_scale(canvas, max(1, scale)))
