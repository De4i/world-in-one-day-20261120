#!/usr/bin/env python3
"""
World in One Day — poster builder.

Renders entry.png (1024 x 1024), a one-page newspaper that sums up the
world news of Friday 20 November 2026, from the structured story data in
poster/data/stories.json.

Design notes
------------
* Cream newsprint background, dark-navy ink, red accents.
* Everything is drawn with Pillow primitives: no photographs, no external
  assets, so the render is fully deterministic — two runs produce a
  byte-identical PNG.
* The three lead stories get full illustration bands (a complete cyclone
  spiral over the Bay of Bengal coast with a Gopalpur landfall marker,
  missile trails and fire glows over a night skyline and river, and a
  COP31 panel with a big thermometer, clashing deadlock arrows and a
  "COP31 · FINAL DAY" banner).  Each of the ten feature modules gets its
  own drawn graphic band specific to its story (falling chart, Mercury
  orbit, EU/UK flags, rising bars, rate lines, cricket, tribunal,
  migrant boat, strike placards, capsule pill).
* The world map is a halftone dot grid: a coarse lattice of dots is kept
  only where it falls inside one of the hand-coded continent polygons,
  then numbered pins for stories 01-13 are stamped on top.
* If the plain RGB PNG ever exceeds the 1 MiB competition limit, the
  image is palette-quantised (224 colours, median-cut, Floyd-Steinberg
  dithering) inside this script, so the output is always in budget.

Run:  python3 poster/build_poster.py
Out:  entry.png next to main.ts, at the repository root.
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Paths, canvas, palette
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent          # poster/
ROOT = HERE.parent                               # repository root
DATA_PATH = HERE / "data" / "stories.json"
OUT_PATH = ROOT / "entry.png"

SIZE = 1024
MAX_BYTES = 1_048_576

PAPER = (247, 241, 222)        # cream newsprint
PAPER_DARK = (238, 229, 203)   # slightly deeper cream for panels
INK = (20, 30, 56)             # dark navy ink
INK_SOFT = (52, 64, 92)        # softer navy for body copy
RED = (177, 28, 35)            # headline red
RED_DARK = (140, 20, 28)
RULE = (196, 183, 148)         # hairline colour
WHITE = (255, 255, 255)

FONT_DIR = Path("/usr/share/fonts/truetype")
SERIF_BOLD = FONT_DIR / "liberation" / "LiberationSerif-Bold.ttf"
SERIF_ITALIC = FONT_DIR / "liberation" / "LiberationSerif-Italic.ttf"
SANS = FONT_DIR / "liberation" / "LiberationSans-Regular.ttf"
SANS_BOLD = FONT_DIR / "liberation" / "LiberationSans-Bold.ttf"
SANS_ITALIC = FONT_DIR / "liberation" / "LiberationSans-Italic.ttf"

MARGIN = 16
X1 = SIZE - MARGIN
INNER = X1 - MARGIN

LEAD_ART_H = 95                # lead illustration band height (95-110)
FEAT_ART_H = 50                # feature graphic band height (50-60)

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    """Cached TrueType loader (fonts are the only external input)."""
    key = (str(path), size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]


def text_w(draw: ImageDraw.ImageDraw, text: str, fnt) -> float:
    return draw.textlength(text, font=fnt)


def fit_font(draw, text: str, path: Path, start: int, max_width: float,
             minimum: int = 9) -> ImageFont.FreeTypeFont:
    """Largest size <= start at which *text* still fits *max_width*."""
    size = start
    while size > minimum and text_w(draw, text, font(path, size)) > max_width:
        size -= 1
    return font(path, size)


def wrap(draw, text: str, fnt, max_width: float) -> list[str]:
    """Greedy word wrap measured with the real font metrics."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else current + " " + word
        if text_w(draw, trial, fnt) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_lines(draw, lines: list[str], x: int, y: int, fnt,
               fill, leading: int) -> int:
    """Draw pre-wrapped lines; returns the y just past the last line."""
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += leading
    return y


def centred_text(draw, cx: float, y: float, text: str, fnt, fill) -> None:
    """Draw *text* horizontally centred on *cx* with its ink centred."""
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (bbox[2] - bbox[0]) / 2 - bbox[0], y - bbox[1]),
              text, font=fnt, fill=fill)


# --------------------------------------------------------------------------
# Lead illustrations — full bands, hand-drawn with Pillow shapes
# --------------------------------------------------------------------------

def art_cyclone(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Full spiral storm over the Bay of Bengal coast, landfall at Gopalpur."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(188, 216, 230))
    # sea shading: two faint swell lines low in the frame
    for wy in (y1 - 18, y1 - 9):
        for wx in range(x0 + 10, x0 + 120, 26):
            draw.arc([wx, wy - 4, wx + 16, wy + 4], start=180, end=360,
                     fill=(150, 190, 215), width=2)
    # landmass on the right (the Odisha coast, abstracted): sand, then
    # a greener inland inset, with the coastline stroked through its points
    coast = [(x1 - 96, y0), (x1 - 78, y0 + 26), (x1 - 60, y1 - 55),
             (x1 - 74, y1 - 30), (x1 - 58, y1)]
    draw.polygon(coast + [(x1, y1), (x1, y0)], fill=(203, 186, 128))
    draw.polygon([(x1 - 56, y0 + 8), (x1 - 8, y0 + 8), (x1 - 8, y1 - 8),
                  (x1 - 42, y1 - 8), (x1 - 54, y1 - 34), (x1 - 44, y1 - 58)],
                 fill=(150, 168, 100))
    draw.line(coast, fill=INK_SOFT, width=2)
    # the full spiral: concentric broken arcs tightening to the eye
    cx, cy = x0 + 92, y0 + 48
    for radius, start, colour, width in (
            (44, 15, (255, 255, 255), 8), (44, 195, (120, 160, 200), 8),
            (36, 105, (255, 255, 255), 7), (36, 285, (100, 145, 190), 7),
            (28, 30, (255, 255, 255), 6), (28, 215, (85, 130, 180), 6),
            (20, 130, (255, 255, 255), 5), (20, 320, (110, 150, 195), 5),
            (12, 60, (255, 255, 255), 4)):
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius],
                 start=start, end=start + 140, fill=colour, width=width)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=WHITE)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=RED)
    # dashed forecast track from the eye to the landfall marker
    mx, my = x1 - 64, y0 + 52
    steps = 6
    for i in range(steps):
        t0, t1 = i / steps, (i + 0.55) / steps
        draw.line([(cx + 36 + (mx - cx - 36) * t0, cy + 6 + (my - cy - 6) * t0),
                   (cx + 36 + (mx - cx - 36) * t1, cy + 6 + (my - cy - 6) * t1)],
                  fill=RED_DARK, width=2)
    draw.ellipse([mx - 6, my - 6, mx + 6, my + 6], outline=RED, width=2)
    draw.ellipse([mx - 2, my - 2, mx + 2, my + 2], fill=RED)
    # place label on a white tag over the land
    tag = (x1 - 84, y1 - 20, x1 - 6, y1 - 6)
    draw.rectangle(tag, fill=WHITE, outline=INK_SOFT)
    centred_text(draw, (tag[0] + tag[2]) / 2, (tag[1] + tag[3]) / 2 - 5,
                 "GOPALPUR", font(SANS_BOLD, 9), INK)
    draw.rectangle(box, outline=RULE)


def art_missiles(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Night sky, skyline silhouette, missile trails, fire glows, river."""
    x0, y0, x1, y1 = box
    wdt, hgt = x1 - x0, y1 - y0
    draw.rectangle(box, fill=(13, 20, 42))
    # deterministic star field (arithmetic pattern, never random)
    for i in range(56):
        sx = x0 + (i * 53 + 11) % max(1, wdt - 8) + 4
        sy = y0 + (i * 29 + 7) % max(1, int(hgt * 0.55)) + 3
        draw.point((sx, sy), fill=(220, 228, 245))
    # crescent moon, top left
    draw.ellipse([x0 + 15, y0 + 5, x0 + 29, y0 + 19], fill=(228, 233, 245))
    draw.ellipse([x0 + 20, y0 + 3, x0 + 34, y0 + 17], fill=(13, 20, 42))
    # skyline: black blocks with lit windows, standing over the river band
    base = y1 - 12
    widths = [36, 24, 42, 28, 50, 26, 40, 30, 48]
    heights = [26, 38, 20, 32, 26, 40, 22, 34, 21]
    bx = x0
    for w, h in zip(widths, heights):
        draw.rectangle([bx, base - h, bx + w - 2, base], fill=(5, 8, 16))
        for wy in range(base - h + 5, base - 5, 8):
            for wx in (bx + 6, bx + w - 11):
                if (wx + wy) % 3:
                    draw.rectangle([wx, wy, wx + 2, wy + 2], fill=(250, 210, 110))
        bx += w
    # river band along the bottom, with light sparkles
    draw.rectangle([x0, base, x1, y1], fill=(24, 50, 82))
    for i in range(6):
        rx = x0 + 18 + i * 52
        draw.line([(rx, y1 - 6), (rx + 16, y1 - 6)], fill=(170, 200, 225), width=1)
    # six missile trails dropping toward the city, with glow heads
    trails = [(0.10, 0.04, 0.24, 0.60), (0.26, 0.02, 0.38, 0.65),
              (0.44, 0.05, 0.52, 0.59), (0.60, 0.02, 0.68, 0.64),
              (0.76, 0.04, 0.82, 0.60), (0.90, 0.03, 0.93, 0.63)]
    for j, (fx0, fy0, fx1, fy1) in enumerate(trails):
        sx, sy = x0 + fx0 * wdt, y0 + fy0 * hgt
        ex, ey = x0 + fx1 * wdt, y0 + fy1 * hgt
        draw.line([(sx, sy), (ex, ey)], fill=(255, 122, 60), width=3)
        draw.line([(sx, sy), (ex, ey)], fill=(255, 205, 120), width=1)
        draw.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=(255, 170, 60))
        draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=WHITE)
        if j % 2 == 1:  # fire glow where this trail meets the city
            draw.ellipse([ex - 10, ey + 2, ex + 10, ey + 9], fill=(255, 120, 40))
            draw.ellipse([ex - 5, ey + 3, ex + 5, ey + 8], fill=(255, 190, 90))
    draw.rectangle(box, outline=RULE)


def art_climate(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Big thermometer, sun, clashing deadlock arrows, COP31 banner."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(243, 226, 199))
    # sun, top right
    sx, sy = x1 - 28, y0 + 18
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                   (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
        draw.line([(sx + dx * 12, sy + dy * 12), (sx + dx * 17, sy + dy * 17)],
                  fill=(217, 119, 6), width=2)
    draw.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill=(240, 160, 40),
                 outline=(217, 119, 6), width=1)
    # thermometer: white tube, mercury high in the red, big bulb
    tx = x0 + 58
    draw.rectangle([tx - 7, y0 + 10, tx + 7, y0 + 66], fill=WHITE,
                   outline=INK, width=2)
    draw.rectangle([tx - 3, y0 + 20, tx + 3, y0 + 78], fill=RED)
    draw.ellipse([tx - 12, y0 + 64, tx + 12, y0 + 88], fill=RED,
                 outline=INK, width=2)
    for i in range(4):
        ty = y0 + 16 + i * 11
        draw.line([(tx + 9, ty), (tx + 15, ty)], fill=INK, width=1)
    # two arrows driving at each other, split by a crack: the deadlock
    ax, bx = x0 + 120, x1 - 72
    draw.polygon([(ax, y0 + 34), (ax + 40, y0 + 34), (ax + 40, y0 + 28),
                  (ax + 56, y0 + 40), (ax + 40, y0 + 52), (ax + 40, y0 + 46),
                  (ax, y0 + 46)], fill=RED)
    draw.polygon([(bx, y0 + 34), (bx - 40, y0 + 34), (bx - 40, y0 + 28),
                  (bx - 56, y0 + 40), (bx - 40, y0 + 52), (bx - 40, y0 + 46),
                  (bx, y0 + 46)], fill=INK)
    draw.line([(x0 + 186, y0 + 26), (x0 + 182, y0 + 36), (x0 + 190, y0 + 44),
               (x0 + 184, y0 + 56)], fill=INK, width=2)
    # banner along the bottom of the panel
    banner = (x0 + 96, y1 - 26, x1 - 10, y1 - 6)
    draw.rectangle(banner, fill=RED)
    label = "COP31 · FINAL DAY"
    lf = fit_font(draw, label, SANS_BOLD, 17, banner[2] - banner[0] - 14,
                  minimum=11)
    centred_text(draw, (banner[0] + banner[2]) / 2,
                 (banner[1] + banner[3]) / 2 - lf.size // 2 + 1,
                 label, lf, WHITE)
    draw.rectangle(box, outline=RULE)


LEAD_ART = {"cyclone": art_cyclone, "missiles": art_missiles, "climate": art_climate}

# --------------------------------------------------------------------------
# Feature graphics — one drawn band per story, specific to its subject
# --------------------------------------------------------------------------

def feat_chart(draw, box) -> None:
    """04 — falling red chart line on a dark grid."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(22, 30, 50))
    for gx in range(x0 + 12, x1, 24):
        draw.line([(gx, y0 + 3), (gx, y1 - 3)], fill=(48, 60, 88), width=1)
    for gy in range(y0 + 6, y1, 12):
        draw.line([(x0 + 3, gy), (x1 - 3, gy)], fill=(48, 60, 88), width=1)
    draw.line([(x0 + 12, y0 + 5), (x0 + 58, y0 + 11), (x0 + 104, y0 + 10),
               (x0 + 150, y0 + 22)], fill=(120, 130, 155), width=1)
    pts = [(x0 + 12, y0 + 9), (x0 + 58, y0 + 16), (x0 + 104, y0 + 14),
           (x0 + 150, y0 + 30), (x1 - 16, y1 - 9)]
    draw.line(pts, fill=RED, width=3, joint="curve")
    for px, py in pts[:-1]:
        draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=WHITE)
    draw.polygon([(x1 - 16, y1 - 9), (x1 - 27, y1 - 10), (x1 - 20, y1 - 19)],
                 fill=RED)
    draw.rectangle(box, outline=RULE)


def feat_orbit(draw, box) -> None:
    """05 — planet disc, orbit arc and probe dot."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(15, 23, 45))
    for i in range(18):
        sx = x0 + (i * 41 + 7) % max(1, (x1 - x0 - 6)) + 3
        sy = y0 + (i * 23 + 5) % max(1, (y1 - y0 - 8)) + 3
        draw.point((sx, sy), fill=(205, 215, 235))
    cx, cy = x0 + 62, y0 + 25
    draw.arc([x0 + 14, y0 + 7, x0 + 110, y1 - 7], start=310, end=230,
             fill=WHITE, width=2)
    draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=(219, 144, 62))
    for dy, half in ((-6, 13), (0, 15), (6, 13)):
        draw.line([(cx - half, cy + dy), (cx + half, cy + dy)],
                  fill=(178, 102, 42), width=3)
    # the probe, out at the end of its long arc, with a panel and antenna
    px, py = x0 + 150, y0 + 13
    draw.line([(px, py), (px - 8, py - 6)], fill=WHITE, width=1)
    draw.rectangle([px - 9, py + 3, px - 2, py + 8], fill=(140, 200, 255))
    draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=WHITE)
    draw.ellipse([x1 - 29, y1 - 19, x1 - 19, y1 - 9], fill=(200, 205, 215))
    draw.rectangle(box, outline=RULE)


def feat_flags(draw, box) -> None:
    """06 — EU circle of stars beside a Union Jack suggestion."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(226, 233, 240))
    # EU flag block
    eu = (x0 + 12, y0 + 8, x0 + 82, y1 - 8)
    draw.rectangle(eu, fill=(32, 62, 142))
    ccx, ccy = (eu[0] + eu[2]) // 2, (eu[1] + eu[3]) // 2
    for i in range(12):
        ang = math.radians(i * 30 - 90)
        sx = ccx + 12 * math.cos(ang)
        sy = ccy + 12 * math.sin(ang)
        draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(250, 206, 64))
    draw.ellipse([ccx - 2, ccy - 2, ccx + 2, ccy + 2], fill=(250, 206, 64))
    # Union Jack block: blue field, white diagonals and cross, red over
    uk = (x0 + 110, y0 + 8, x1 - 12, y1 - 8)
    draw.rectangle(uk, fill=(33, 52, 110))
    draw.line([(uk[0], uk[1]), (uk[2], uk[3])], fill=WHITE, width=5)
    draw.line([(uk[0], uk[3]), (uk[2], uk[1])], fill=WHITE, width=5)
    draw.line([(uk[0], uk[1]), (uk[2], uk[3])], fill=(200, 40, 50), width=2)
    draw.line([(uk[0], uk[3]), (uk[2], uk[1])], fill=(200, 40, 50), width=2)
    ucx, ucy = (uk[0] + uk[2]) // 2, (uk[1] + uk[3]) // 2
    draw.rectangle([ucx - 5, uk[1], ucx + 5, uk[3]], fill=WHITE)
    draw.rectangle([uk[0], ucy - 5, uk[2], ucy + 5], fill=WHITE)
    draw.rectangle([ucx - 2, uk[1], ucx + 2, uk[3]], fill=(200, 30, 45))
    draw.rectangle([uk[0], ucy - 2, uk[2], ucy + 2], fill=(200, 30, 45))
    draw.rectangle(eu, outline=INK_SOFT)
    draw.rectangle(uk, outline=INK_SOFT)
    draw.rectangle(box, outline=RULE)


def feat_bars(draw, box) -> None:
    """07 — rising bars, heights carrying the 2.3% story."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(250, 241, 222))
    base = y1 - 9
    draw.line([(x0 + 14, base), (x1 - 14, base)], fill=INK_SOFT, width=2)
    colours = [(232, 186, 96), (226, 146, 52), (214, 106, 30), (196, 54, 28)]
    for i, (h, colour) in enumerate(zip((12, 20, 28, 38), colours)):
        bx = x0 + 34 + i * 34
        draw.rectangle([bx, base - h, bx + 24, base], fill=colour)
    draw.line([(x0 + 30, y0 + 20), (x1 - 30, y0 + 7)], fill=RED, width=2)
    draw.polygon([(x1 - 30, y0 + 7), (x1 - 41, y0 + 6), (x1 - 38, y0 + 15)],
                 fill=RED)
    draw.rectangle(box, outline=RULE)


def feat_percent(draw, box) -> None:
    """08 — two flat rate lines, 3.5 above 3.0, heights as the labels."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(229, 241, 239))
    draw.text((x0 + 8, y0 + 8), "%", font=font(SANS_BOLD, 30),
              fill=(140, 195, 188))
    teal = (15, 118, 110)
    for yy, colour, label in ((y0 + 15, teal, "3.5"), (y0 + 35, INK, "3.0")):
        draw.line([(x0 + 52, yy), (x1 - 52, yy)], fill=colour, width=4)
        draw.ellipse([x1 - 55, yy - 3, x1 - 49, yy + 3], fill=colour)
        draw.text((x1 - 44, yy - 8), label, font=font(SANS_BOLD, 15),
                  fill=colour)
    draw.rectangle(box, outline=RULE)


def feat_cricket(draw, box) -> None:
    """09 — bat, ball, and the big 118."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(233, 241, 221))
    draw.rectangle([x0 + 10, y0 + 31, x1 - 10, y0 + 39], fill=(216, 196, 150))
    draw.line([(x0 + 66, y0 + 5), (x0 + 56, y0 + 16)], fill=INK, width=3)
    draw.polygon([(x0 + 50, y0 + 14), (x0 + 62, y0 + 16), (x0 + 58, y1 - 8),
                  (x0 + 44, y1 - 10)], fill=(214, 184, 124), outline=INK_SOFT)
    bx, by = x0 + 104, y0 + 15
    draw.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill=RED)
    draw.arc([bx - 4, by - 5, bx + 4, by + 5], start=300, end=120,
             fill=WHITE, width=1)
    nf = fit_font(draw, "118", SANS_BOLD, 32, 58, minimum=20)
    draw.text((x1 - 64, y0 + 9), "118", font=nf, fill=INK)
    draw.rectangle(box, outline=RULE)


def feat_ballot(draw, box) -> None:
    """10 — tribunal building: pediment, columns, and a 2027 banner."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(239, 234, 246))
    cx = (x0 + x1) // 2
    draw.polygon([(x0 + 34, y0 + 15), (x1 - 34, y0 + 15), (cx, y0 + 4)],
                 fill=(124, 77, 158))
    draw.rectangle([x0 + 34, y0 + 15, x1 - 34, y0 + 19], fill=(106, 62, 140))
    for i in range(4):
        bx = x0 + 44 + i * 32
        draw.rectangle([bx, y0 + 21, bx + 9, y1 - 13], fill=WHITE,
                       outline=INK_SOFT)
    draw.rectangle([x0 + 30, y1 - 13, x1 - 30, y1 - 7], fill=(124, 77, 158))
    banner = (cx - 36, y0 + 25, cx + 36, y0 + 41)
    draw.rectangle(banner, fill=RED)
    centred_text(draw, cx, (banner[1] + banner[3]) / 2 - 7,
                 "2027", font(SANS_BOLD, 15), WHITE)
    draw.rectangle(box, outline=RULE)


def feat_boat(draw, box) -> None:
    """11 — boat hull on scalloped waves."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(213, 231, 240))
    draw.ellipse([x1 - 29, y0 + 5, x1 - 19, y0 + 15], fill=(240, 180, 80))
    cx = (x0 + x1) // 2
    draw.line([(cx, y0 + 6), (cx, y0 + 23)], fill=INK, width=2)
    draw.polygon([(cx, y0 + 6), (cx + 11, y0 + 9), (cx, y0 + 12)], fill=RED)
    for hx in (cx - 22, cx, cx + 22):
        draw.ellipse([hx - 3, y0 + 16, hx + 3, y0 + 22], fill=INK)
    draw.rectangle([x0 + 44, y0 + 23, x1 - 44, y0 + 27], fill=(110, 44, 28))
    draw.polygon([(x0 + 50, y0 + 27), (x1 - 50, y0 + 27), (x1 - 64, y1 - 9),
                  (x0 + 64, y1 - 9)], fill=(148, 62, 40))
    for row, wy in enumerate((y1 - 16, y1 - 9)):
        for wx in range(x0 + 6 + row * 11, x1 - 18, 22):
            draw.arc([wx, wy - 4, wx + 16, wy + 5], start=180, end=360,
                     fill=(20, 110, 150), width=2)
    draw.rectangle(box, outline=RULE)


def feat_placard(draw, box) -> None:
    """12 — a crowd of placards on sticks over a row of heads."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(247, 237, 225))
    for px, py in ((x0 + 16, y0 + 6), (x0 + 58, y0 + 12), (x0 + 100, y0 + 5),
                   (x0 + 142, y0 + 11)):
        draw.line([(px + 18, py + 19), (px + 18, y1 - 12)],
                  fill=(120, 90, 60), width=2)
        draw.rectangle([px, py, px + 36, py + 19], fill=WHITE, outline=INK)
        draw.line([(px + 5, py + 6), (px + 27, py + 6)], fill=RED, width=2)
        draw.line([(px + 5, py + 12), (px + 22, py + 12)], fill=INK_SOFT,
                  width=2)
    heads = [(30, 40, 70), (120, 80, 50), (70, 90, 60),
             (150, 110, 60), (90, 60, 110), (50, 70, 90)]
    for i, colour in enumerate(heads):
        hx, hy = x0 + 24 + i * 28, y1 - 10
        draw.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], fill=colour)
    draw.rectangle(box, outline=RULE)


def feat_pill(draw, box) -> None:
    """13 — one big capsule pill, split two-tone."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(249, 231, 239))
    cx = (x0 + x1) // 2
    top, bot = y0 + 13, y0 + 37
    pink = (229, 92, 132)
    draw.ellipse([x0 + 34, top, x0 + 58, bot], fill=WHITE)
    draw.ellipse([x1 - 58, top, x1 - 34, bot], fill=pink)
    draw.rectangle([x0 + 46, top, cx, bot], fill=WHITE)
    draw.rectangle([cx, top, x1 - 46, bot], fill=pink)
    draw.arc([x0 + 34, top, x0 + 58, bot], start=90, end=270, fill=INK, width=2)
    draw.arc([x1 - 58, top, x1 - 34, bot], start=270, end=90, fill=INK, width=2)
    draw.line([(x0 + 46, top), (x1 - 46, top)], fill=INK, width=2)
    draw.line([(x0 + 46, bot), (x1 - 46, bot)], fill=INK, width=2)
    draw.line([(cx, top), (cx, bot)], fill=(200, 60, 100), width=2)
    draw.ellipse([x0 + 10, y1 - 19, x0 + 22, y1 - 7], fill=(15, 118, 110))
    draw.ellipse([x1 - 22, y0 + 6, x1 - 13, y0 + 15], fill=(217, 119, 6))
    draw.rectangle(box, outline=RULE)


FEAT_ART = {"chart": feat_chart, "orbit": feat_orbit, "flags": feat_flags,
            "bars": feat_bars, "percent": feat_percent, "cricket": feat_cricket,
            "ballot": feat_ballot, "boat": feat_boat, "placard": feat_placard,
            "pill": feat_pill}

# --------------------------------------------------------------------------
# Halftone world map
# --------------------------------------------------------------------------

# Hand-coded continent polygons, normalised to the map box (x right, y down).
CONTINENTS: list[list[tuple[float, float]]] = [
    # North America
    [(0.02, 0.30), (0.10, 0.12), (0.24, 0.07), (0.34, 0.13), (0.36, 0.24),
     (0.30, 0.30), (0.33, 0.38), (0.27, 0.44), (0.22, 0.40), (0.18, 0.48),
     (0.12, 0.44), (0.07, 0.38)],
    # South America
    [(0.20, 0.50), (0.27, 0.48), (0.31, 0.56), (0.28, 0.70), (0.24, 0.84),
     (0.20, 0.89), (0.17, 0.72), (0.16, 0.58)],
    # Europe
    [(0.44, 0.22), (0.50, 0.13), (0.56, 0.15), (0.575, 0.24), (0.54, 0.31),
     (0.50, 0.30), (0.465, 0.35), (0.435, 0.29)],
    # Africa
    [(0.45, 0.40), (0.54, 0.36), (0.605, 0.43), (0.585, 0.59), (0.54, 0.75),
     (0.49, 0.79), (0.45, 0.62), (0.43, 0.48)],
    # Asia (with the Indian triangle and SE-Asian shoulder)
    [(0.575, 0.20), (0.66, 0.10), (0.80, 0.07), (0.92, 0.13), (0.95, 0.26),
     (0.87, 0.34), (0.885, 0.45), (0.81, 0.51), (0.75, 0.44), (0.685, 0.54),
     (0.645, 0.43), (0.585, 0.35)],
    # SE-Asian islands
    [(0.75, 0.57), (0.83, 0.55), (0.89, 0.60), (0.81, 0.65), (0.74, 0.62)],
    # Australia
    [(0.815, 0.69), (0.915, 0.665), (0.96, 0.75), (0.90, 0.85), (0.825, 0.81)],
    # New Zealand
    [(0.965, 0.85), (0.99, 0.89), (0.975, 0.95), (0.955, 0.90)],
]


def _inside(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    """Even-odd point-in-polygon test for the continent mask."""
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def draw_map(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
             pins: list[dict]) -> None:
    """Dot-grid world map with numbered story pins stamped on top."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(232, 238, 240), outline=RULE)
    wdt, hgt = x1 - x0, y1 - y0
    step = 7
    for gy in range(y0 + 5, y1 - 3, step):
        for gx in range(x0 + 5, x1 - 3, step):
            nx, ny = (gx - x0) / wdt, (gy - y0) / hgt
            if any(_inside(nx, ny, poly) for poly in CONTINENTS):
                draw.ellipse([gx - 1.6, gy - 1.6, gx + 1.6, gy + 1.6],
                             fill=(38, 84, 110))
    # pins for stories 01-13 (pin 05, Mercury, sits in the map's sky corner
    # as a little planet instead of a land pin)
    pin_font = font(SANS_BOLD, 9)
    for pin in pins:
        px = x0 + int(pin["x"] * wdt)
        py = y0 + int(pin["y"] * hgt)
        label = str(pin["n"])
        if pin["n"] == 5:
            draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(240, 160, 40),
                         outline=INK, width=1)
            draw.arc([px - 10, py - 4, px + 10, py + 5], start=200, end=520,
                     fill=INK, width=1)
        draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=RED, outline=WHITE, width=1)
        tw = text_w(draw, label, pin_font)
        draw.text((px - tw / 2, py - 5), label, font=pin_font, fill=WHITE)


# --------------------------------------------------------------------------
# Page sections
# --------------------------------------------------------------------------

def section_top(draw, data: dict) -> int:
    """Brand strip, masthead, strapline, numbers strip, region bar."""
    ed = data["edition"]
    y = 6
    draw.text((MARGIN, y), ed["brand"], font=font(SANS_BOLD, 15), fill=INK)
    right_f = font(SANS_BOLD, 11)
    rw = text_w(draw, ed["top_right"], right_f)
    draw.text((X1 - rw, y + 2), ed["top_right"], font=right_f, fill=RED)
    y += 19
    draw.line([(MARGIN, y), (X1, y)], fill=INK, width=2)
    y += 3
    # Masthead — the biggest element on the page, sized to the full measure.
    mast = fit_font(draw, ed["masthead"], SERIF_BOLD, 74, INNER)
    mw = text_w(draw, ed["masthead"], mast)
    draw.text(((SIZE - mw) / 2, y), ed["masthead"], font=mast, fill=INK)
    y += 84  # clearance: no strapline letterform touches a masthead descender
    strap = fit_font(draw, ed["strapline"], SERIF_ITALIC, 17, INNER)
    sw = text_w(draw, ed["strapline"], strap)
    draw.text(((SIZE - sw) / 2, y), ed["strapline"], font=strap, fill=RED)
    y += 20
    draw.line([(MARGIN, y), (X1, y)], fill=RULE, width=1)
    y += 4
    # Numbers strip: six big-number cells divided by hairlines.
    cell_w = INNER / 6
    big_f = font(SANS_BOLD, 24)
    cap_f = font(SANS, 11)
    for i, cell in enumerate(data["numbers"]):
        cx = MARGIN + i * cell_w
        if i:
            draw.line([(cx - 5, y + 2), (cx - 5, y + 40)], fill=RULE, width=1)
        colour = RED if i in (1, 2) else INK
        draw.text((cx, y), cell["big"], font=big_f, fill=colour)
        lines = wrap(draw, cell["caption"], cap_f, cell_w - 12)
        draw_lines(draw, lines[:2], cx, y + 25, cap_f, INK_SOFT, 11)
    y += 48
    # Region bar: one segment per region, count inside each.  Label ink is
    # centred inside its segment and coloured for contrast against the
    # segment fill — white on dark fills, ink only on light ones.
    seg_w = INNER / len(data["regions"])
    for i, region in enumerate(data["regions"]):
        sx = MARGIN + i * seg_w
        colour = tuple(int(region["color"][j:j + 2], 16) for j in (1, 3, 5))
        draw.rectangle([sx, y, sx + seg_w - 2, y + 18], fill=colour)
        label = f'{region["name"]} {region["count"]}'
        lf = fit_font(draw, label, SANS_BOLD, 11, seg_w - 12, minimum=8)
        lum = 0.299 * colour[0] + 0.587 * colour[1] + 0.114 * colour[2]
        fill = WHITE if lum < 150 else INK
        bbox = draw.textbbox((0, 0), label, font=lf)
        tx = sx + (seg_w - 2 - (bbox[2] - bbox[0])) / 2 - bbox[0]
        ty = y + (18 - (bbox[3] - bbox[1])) / 2 - bbox[1]
        draw.text((tx, ty), label, font=lf, fill=fill)
    y += 21
    draw.line([(MARGIN, y), (X1, y)], fill=INK, width=1)
    return y + 5


def section_leads(draw, data: dict, y: int) -> int:
    """The three lead stories, each with its full illustration band."""
    gap = 10
    col_w = (INNER - 2 * gap) / 3
    head_f = font(SANS_BOLD, 28)
    kick_f = font(SANS_BOLD, 11)
    body_f = font(SANS, 13)
    bottom = y
    for i, lead in enumerate(data["leads"]):
        x = MARGIN + i * (col_w + gap)
        if i:
            draw.line([(x - gap / 2, y), (x - gap / 2, y + 236)], fill=RULE, width=1)
        art_box = (int(x), y, int(x + col_w), y + LEAD_ART_H)
        LEAD_ART[lead["art"]](draw, art_box)
        cy = y + LEAD_ART_H + 6
        draw.text((x, cy), f'{lead["n"]}  {lead["kicker"]}', font=kick_f, fill=RED)
        cy += 15
        lines = wrap(draw, lead["headline"], head_f, col_w)
        cy = draw_lines(draw, lines, x, cy, head_f, INK, 27)
        cy += 1
        caption = f'{lead["caption"]} ({lead["source"]})'
        lines = wrap(draw, caption, body_f, col_w)
        cy = draw_lines(draw, lines, x, cy, body_f, INK_SOFT, 13)
        bottom = max(bottom, cy)
    y = bottom + 2
    draw.line([(MARGIN, y), (X1, y)], fill=RULE, width=1)
    return y + 3


def section_features(draw, data: dict, y: int) -> int:
    """Ten feature modules in two rows of five, each with its own graphic."""
    gap = 8
    col_w = (INNER - 4 * gap) / 5
    head_f = font(SANS_BOLD, 18)
    body_f = font(SANS, 13)
    for row in range(2):
        row_bottom = y
        for col in range(5):
            feat = data["features"][row * 5 + col]
            x = MARGIN + col * (col_w + gap)
            if col:
                draw.line([(x - gap / 2, y), (x - gap / 2, y + 140)], fill=RULE, width=1)
            art_box = (int(x), y, int(x + col_w), y + FEAT_ART_H)
            FEAT_ART[feat["icon"]](draw, art_box)
            kick = f'{feat["n"]} · {feat["kicker"]}'
            kf = fit_font(draw, kick, SANS_BOLD, 10, col_w, minimum=8)
            draw.text((x, y + FEAT_ART_H + 3), kick, font=kf, fill=RED)
            cy = y + FEAT_ART_H + 14
            lines = wrap(draw, feat["headline"], head_f, col_w)
            cy = draw_lines(draw, lines, x, cy, head_f, INK, 18)
            caption = f'{feat["caption"]} ({feat["source"]})'
            lines = wrap(draw, caption, body_f, col_w)
            cy = draw_lines(draw, lines[:3], x, cy, body_f, INK_SOFT, 13)
            row_bottom = max(row_bottom, cy)
        y = row_bottom + 4
        if row == 0:
            draw.line([(MARGIN, y - 3), (X1, y - 3)], fill=RULE, width=1)
    draw.line([(MARGIN, y - 2), (X1, y - 2)], fill=INK, width=1)
    return y + 2


def section_bottom(draw, data: dict, y: int) -> int:
    """World map (left) and the 25 one-line briefs (right, two columns)."""
    map_w = 348
    head_f = font(SANS_BOLD, 14)
    draw.text((MARGIN, y), "WHERE IT HAPPENED", font=head_f, fill=INK)
    draw.text((MARGIN, y + 15), "Pins 1-13: the leads and features above",
              font=font(SANS_ITALIC, 11), fill=INK_SOFT)
    draw_map(draw, (MARGIN, y + 30, MARGIN + map_w, y + 180), data["pins"])
    # Briefs, to the right of the map.
    bx = MARGIN + map_w + 16
    bw = X1 - bx
    draw.text((bx, y), "ALSO ON FRIDAY 20 NOVEMBER", font=head_f, fill=INK)
    draw.text((bx, y + 15), "25 more stories, in brief",
              font=font(SANS_ITALIC, 11), fill=INK_SOFT)
    col_w = (bw - 12) / 2
    num_f = font(SANS_BOLD, 12)
    place_f = font(SANS_BOLD, 12)
    per_col = math.ceil(len(data["briefs"]) / 2)
    for idx, brief in enumerate(data["briefs"]):
        col, row = divmod(idx, per_col)
        x = bx + col * (col_w + 12)
        yy = y + 33 + row * 12.5
        draw.text((x, yy), f'{brief["n"]}', font=num_f, fill=RED)
        nx = x + text_w(draw, f'{brief["n"]}', num_f) + 4
        draw.text((nx, yy), brief["place"], font=place_f, fill=INK)
        px = nx + text_w(draw, brief["place"], place_f) + 4
        # One line only: shrink just this line if it would spill over.
        bf = fit_font(draw, brief["text"], SANS, 12, x + col_w - px, minimum=9)
        draw.text((px, yy), brief["text"], font=bf, fill=INK_SOFT)
    return y + 195


def section_close(draw, data: dict, y: int) -> int:
    """Date-check box and the attribution footer."""
    dc = data["date_check"]
    box = (MARGIN, y, X1, y + 36)
    draw.rectangle(box, outline=RED, width=2)
    draw.rectangle([MARGIN, y, MARGIN + 104, y + 36], fill=RED)
    draw.text((MARGIN + 10, y + 4), "DATE", font=font(SANS_BOLD, 14), fill=WHITE)
    draw.text((MARGIN + 10, y + 20), "CHECK", font=font(SANS_BOLD, 14), fill=WHITE)
    body_f = font(SANS, 12)
    lines = wrap(draw, dc["body"], body_f, INNER - 122)
    draw_lines(draw, lines[:3], MARGIN + 114, y + 5, body_f, INK, 13)
    y += 41
    ed = data["edition"]
    claim_f = fit_font(draw, ed["footer_claim"], SANS_BOLD, 12, INNER)
    cw = text_w(draw, ed["footer_claim"], claim_f)
    draw.text(((SIZE - cw) / 2, y), ed["footer_claim"], font=claim_f, fill=INK)
    y += 14
    src_f = fit_font(draw, ed["footer_sources"], SANS, 11, INNER)
    sw = text_w(draw, ed["footer_sources"], src_f)
    draw.text(((SIZE - sw) / 2, y), ed["footer_sources"], font=src_f, fill=INK_SOFT)
    return y + 5


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build() -> Path:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    # Cross-checks: the printed counts must agree with the story list.
    total = len(data["leads"]) + len(data["features"]) + len(data["briefs"])
    assert total == 38, f"story count drifted: {total}"
    assert sum(r["count"] for r in data["regions"]) == total, "region counts drifted"
    assert len(data["numbers"]) == 6 and len(data["pins"]) == 13

    img = Image.new("RGB", (SIZE, SIZE), PAPER)
    draw = ImageDraw.Draw(img)
    # faint newsprint frame
    draw.rectangle([6, 6, SIZE - 7, SIZE - 7], outline=RULE, width=1)

    y = section_top(draw, data)
    y = section_leads(draw, data, y)
    y = section_features(draw, data, y)
    y = section_bottom(draw, data, y)
    y = section_close(draw, data, y)
    assert y <= SIZE - 8, f"page overflowed: content ends at y={y}"

    # Save, quantising only if the flat render ever busts the size budget.
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    if buf.tell() > MAX_BYTES:
        img = img.quantize(colors=224, method=Image.Quantize.MEDIANCUT,
                           dither=Image.Dither.FLOYDSTEINBERG)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
    OUT_PATH.write_bytes(buf.getvalue())
    print(f"wrote {OUT_PATH} ({buf.tell()} bytes, content ends y={y})")
    return OUT_PATH


if __name__ == "__main__":
    build()
