#!/usr/bin/env python3
"""
World in One Day — poster builder.

Renders entry.png (1024 x 1024), a one-page newspaper that sums up the
world news of Friday 20 November 2026, from the structured story data in
poster/data/stories.json.

Design notes
------------
* V6: v2's page — cream newsprint, dark-navy ink, red accents,
  same layout — with the art density of the top entries.  The three lead
  stories and all ten feature modules now carry full dark-navy art
  panels with bold in-art data tags in the rank-4 style (a labelled
  map panel for the cyclone with a "LANDFALL · GUSTS 110 KM/H" banner,
  a Kyiv night panel tagged "~30 MISSILES · 7 WAVES", a COP31 panel
  with thermometer, deadlock arrows, a red "FINAL DAY · DEADLOCK"
  badge and a "$120BN FINANCE GAP" tag; feature bands carry their own
  numbers: index falls, CPI bars against a dashed 2% target, the LPR
  curve, the 118, the 2027 ballot, "100 SQUARES", "60.7% RESPONSE").
* Everything is drawn with Pillow primitives: no photographs, no external
  assets, so the render is fully deterministic — two runs produce a
  byte-identical PNG.
* The world map is solid-fill: hand-coded continent polygons in muted
  blue-grey on a deep-navy ocean, with numbered pins for stories 01-13
  stamped on top.
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
PANEL = (17, 31, 57)           # deep navy art panel
PANEL_LINE = (52, 74, 110)     # faint line work on a dark panel
LAND_DARK = (108, 126, 150)    # muted blue-grey continents
OCEAN = (13, 22, 44)           # deep navy ocean

FONT_DIR = Path("/usr/share/fonts/truetype")
SERIF_BOLD = FONT_DIR / "liberation" / "LiberationSerif-Bold.ttf"
SERIF_ITALIC = FONT_DIR / "liberation" / "LiberationSerif-Italic.ttf"
SANS = FONT_DIR / "liberation" / "LiberationSans-Regular.ttf"
SANS_BOLD = FONT_DIR / "liberation" / "LiberationSans-Bold.ttf"
SANS_ITALIC = FONT_DIR / "liberation" / "LiberationSans-Italic.ttf"

MARGIN = 16
X1 = SIZE - MARGIN
INNER = X1 - MARGIN

LEAD_ART_H = 98               # lead illustration band height (v6: taller, rank-1 density)
FEAT_ART_H = 54                # feature graphic band height (v6: taller, rank-1 density)

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


def tag(draw, x: int, y: int, text: str, fnt, bg, fg) -> int:
    """Filled in-art data tag with its top-left at (x, y); returns width."""
    tw = text_w(draw, text, fnt)
    w = int(tw) + 12
    h = fnt.size + 7
    draw.rectangle([x, y, x + w, y + h], fill=bg)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x + 6 - bbox[0], y + (h - (bbox[3] - bbox[1])) / 2 - bbox[1]),
              text, font=fnt, fill=fg)
    return w


def banner(draw, x: int, y: int, text: str, fnt) -> int:
    """Red in-art headline banner, top-left of a panel (rank-1 pattern)."""
    w = int(text_w(draw, text, fnt)) + 14
    h = fnt.size + 6
    draw.rectangle([x, y, x + w, y + h], fill=RED)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x + 7 - bbox[0], y + (h - (bbox[3] - bbox[1])) / 2 - bbox[1]),
              text, font=fnt, fill=WHITE)
    return w


def chip(draw, x: int, y: int, text: str) -> int:
    """Small black source/evidence chip inside a panel (rank-1 pattern)."""
    fnt = font(SANS, 8)
    w = int(text_w(draw, text, fnt)) + 10
    draw.rectangle([x, y, x + w, y + 12], fill=(8, 10, 14))
    draw.text((x + 5, y + 2), text, font=fnt, fill=(235, 235, 235))
    return w


def chip_w(draw, text: str) -> int:
    return int(text_w(draw, text, font(SANS, 8))) + 10


def num_chip(draw, cx: float, cy: float, r: int, n: str, fnt) -> None:
    """Blue circle story-number chip (rank-1 pattern)."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(27, 58, 128))
    label = str(int(n))
    tw = text_w(draw, label, fnt)
    bbox = draw.textbbox((0, 0), label, font=fnt)
    draw.text((cx - tw / 2 - bbox[0], cy - (bbox[3] - bbox[1]) / 2 - bbox[1]),
              label, font=fnt, fill=WHITE)


# --------------------------------------------------------------------------
# Lead illustrations — full bands, hand-drawn with Pillow shapes
# --------------------------------------------------------------------------

def art_cyclone(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Dark map panel: Odisha coast, spiral fully inside, landfall banner."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    # faint swell arcs low in the frame, clear of the banner
    for wy in (y1 - 30, y1 - 25):
        for wx in range(x0 + 8, x0 + 108, 26):
            draw.arc([wx, wy - 4, wx + 16, wy + 4], start=180, end=360,
                     fill=(58, 92, 138), width=2)
    # landmass on the right (the Odisha coast, abstracted): blue-grey
    # land with a lighter inland inset and a pale coastline stroke
    coast = [(x1 - 96, y0), (x1 - 78, y0 + 24), (x1 - 60, y1 - 62),
             (x1 - 74, y1 - 38), (x1 - 58, y1)]
    draw.polygon(coast + [(x1, y1), (x1, y0)], fill=(104, 116, 138))
    draw.polygon([(x1 - 56, y0 + 8), (x1 - 8, y0 + 8), (x1 - 8, y1 - 27),
                  (x1 - 42, y1 - 27), (x1 - 54, y1 - 45), (x1 - 44, y1 - 62)],
                 fill=(126, 136, 156))
    draw.line(coast, fill=(196, 210, 228), width=2)
    draw.text((x1 - 50, y0 + 9), "ODISHA", font=font(SANS_BOLD, 9),
              fill=(226, 234, 244))
    # the full spiral: concentric broken arcs tightening to the eye,
    # sized and centred so nothing spills past the panel edges
    cx, cy = x0 + 86, y0 + 41
    for radius, start, colour, width in (
            (35, 15, (255, 255, 255), 7), (35, 195, (130, 170, 215), 7),
            (28, 105, (255, 255, 255), 6), (28, 285, (110, 155, 205), 6),
            (21, 30, (255, 255, 255), 5), (21, 215, (95, 140, 195), 5),
            (14, 130, (255, 255, 255), 4), (14, 320, (120, 160, 210), 4),
            (8, 60, (255, 255, 255), 3)):
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius],
                 start=start, end=start + 140, fill=colour, width=width)
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=WHITE)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=RED)
    # sea label on a sea-coloured plate, stamped over the spiral's rim
    tag(draw, x0 + 8, y0 + 28, "BAY OF BENGAL", font(SANS_BOLD, 11),
        PANEL, (226, 234, 244))
    # dashed forecast track from the eye to the landfall marker
    mx, my = x1 - 64, y0 + 44
    steps = 6
    for i in range(steps):
        t0, t1 = i / steps, (i + 0.55) / steps
        draw.line([(cx + 29 + (mx - cx - 29) * t0, cy + 3 + (my - cy - 3) * t0),
                   (cx + 29 + (mx - cx - 29) * t1, cy + 3 + (my - cy - 3) * t1)],
                  fill=(255, 120, 120), width=2)
    draw.ellipse([mx - 6, my - 6, mx + 6, my + 6], outline=(255, 120, 120),
                 width=2)
    draw.ellipse([mx - 2, my - 2, mx + 2, my + 2], fill=RED)
    # place label on a white tag over the land, below the marker
    tag(draw, x1 - 88, y0 + 56, "GOPALPUR", font(SANS_BOLD, 9), WHITE, INK)
    # red banner along the bottom of the panel, rank-4 style
    draw.rectangle([x0, y1 - 19, x1, y1], fill=RED)
    centred_text(draw, (x0 + x1) / 2, y1 - 16,
                 "LANDFALL · GUSTS 110 KM/H", font(SANS_BOLD, 12), WHITE)
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
    draw.ellipse([x0 + 74, y0 + 5, x0 + 88, y0 + 19], fill=(228, 233, 245))
    draw.ellipse([x0 + 79, y0 + 3, x0 + 93, y0 + 17], fill=(13, 20, 42))
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
    # red data tag over the river band, bottom left
    tag(draw, x0 + 6, y1 - 18, "~30 MISSILES · 7 WAVES",
        font(SANS_BOLD, 11), RED, WHITE)
    draw.rectangle(box, outline=RULE)


def art_climate(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Dark panel: thermometer, deadlock arrows, red COP31 badge, gap tag."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    # sun, top right, clear of the badge below it
    sx, sy = x1 - 26, y0 + 14
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                   (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
        draw.line([(sx + dx * 11, sy + dy * 11), (sx + dx * 16, sy + dy * 16)],
                  fill=(240, 170, 60), width=2)
    draw.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=(245, 178, 60))
    # thermometer: white tube, mercury high in the red, big bulb
    tx = x0 + 52
    draw.rectangle([tx - 7, y0 + 24, tx + 7, y0 + 66], fill=WHITE)
    draw.rectangle([tx - 3, y0 + 30, tx + 3, y0 + 76], fill=RED)
    draw.ellipse([tx - 12, y0 + 64, tx + 12, y0 + 88], fill=RED,
                 outline=WHITE, width=2)
    for i in range(4):
        ty = y0 + 29 + i * 11
        draw.line([(tx + 10, ty), (tx + 16, ty)], fill=(200, 212, 230),
                  width=1)
    # two arrows driving at each other, split by a crack: the deadlock
    ax, bx = x0 + 104, x0 + 196
    draw.polygon([(ax, y0 + 36), (ax + 34, y0 + 36), (ax + 34, y0 + 30),
                  (ax + 48, y0 + 42), (ax + 34, y0 + 54), (ax + 34, y0 + 48),
                  (ax, y0 + 48)], fill=RED)
    draw.polygon([(bx, y0 + 36), (bx - 34, y0 + 36), (bx - 34, y0 + 30),
                  (bx - 48, y0 + 42), (bx - 34, y0 + 54), (bx - 34, y0 + 48),
                  (bx, y0 + 48)], fill=(226, 234, 244))
    draw.line([(x0 + 152, y0 + 28), (x0 + 149, y0 + 38), (x0 + 156, y0 + 46),
               (x0 + 151, y0 + 58)], fill=(240, 200, 90), width=2)
    # red badge, two lines, and the finance-gap tag under it
    badge = (x0 + 206, y0 + 32, x1 - 10, y0 + 62)
    draw.rectangle(badge, fill=RED)
    bcx = (badge[0] + badge[2]) / 2
    centred_text(draw, bcx, y0 + 36, "FINAL DAY", font(SANS_BOLD, 11), WHITE)
    centred_text(draw, bcx, y0 + 49, "DEADLOCK", font(SANS_BOLD, 11), WHITE)
    tag(draw, x0 + 206, y0 + 68, "$120BN FINANCE GAP", font(SANS_BOLD, 9),
        (10, 16, 30), (255, 190, 90))
    draw.rectangle(box, outline=RULE)


LEAD_ART = {"cyclone": art_cyclone, "missiles": art_missiles, "climate": art_climate}

LEAD_BANNERS = {"01": "CYCLONE AKVAN", "02": "KYIV", "03": "COP31: DEADLOCK"}
FEAT_BANNERS = {"04": "AI SELL-OFF", "05": "MERCURY", "06": "EU-UK RESET",
                "07": "JAPAN: +2.3%", "08": "CHINA RATES", "09": "PHILLIPS: 118",
                "10": "BUKELE: 3RD BID", "11": "SENEGAL BOAT",
                "12": "ITALY: STRIKE", "13": "CANCER PILL"}

# --------------------------------------------------------------------------
# Feature graphics — one drawn band per story, specific to its subject
# --------------------------------------------------------------------------

def feat_chart(draw, box) -> None:
    """04 — falling red chart line on a dark grid, index falls labelled."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    for gx in range(x0 + 12, x1, 24):
        draw.line([(gx, y0 + 3), (gx, y1 - 3)], fill=PANEL_LINE, width=1)
    for gy in range(y0 + 6, y1, 12):
        draw.line([(x0 + 3, gy), (x1 - 3, gy)], fill=PANEL_LINE, width=1)
    draw.line([(x0 + 96, y0 + 8), (x0 + 128, y0 + 13), (x0 + 158, y0 + 12),
               (x1 - 14, y0 + 22)], fill=(120, 130, 155), width=1)
    pts = [(x0 + 96, y0 + 12), (x0 + 128, y0 + 18), (x0 + 158, y0 + 16),
           (x0 + 172, y0 + 30), (x1 - 14, y1 - 8)]
    draw.line(pts, fill=RED, width=3, joint="curve")
    for px, py in pts[:-1]:
        draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=WHITE)
    draw.polygon([(x1 - 14, y1 - 8), (x1 - 25, y1 - 9), (x1 - 18, y1 - 18)],
                 fill=RED)
    # the two index falls, as in-art data labels
    draw.text((x0 + 8, y0 + 24), "NIKKEI -4.5%", font=font(SANS_BOLD, 11),
              fill=WHITE)
    draw.text((x0 + 8, y0 + 38), "KOSPI -4.7%", font=font(SANS_BOLD, 11),
              fill=(255, 150, 150))
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
    tag(draw, x0 + 8, y1 - 18, "6BN MILES", font(SANS_BOLD, 9), RED, WHITE)
    draw.rectangle(box, outline=RULE)


def feat_flags(draw, box) -> None:
    """06 — EU circle of stars beside a Union Jack, on a dark panel."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    # EU flag block
    eu = (x0 + 10, y0 + 7, x0 + 84, y1 - 7)
    draw.rectangle(eu, fill=(32, 62, 142))
    ccx, ccy = (eu[0] + eu[2]) // 2, (eu[1] + eu[3]) // 2
    for i in range(12):
        ang = math.radians(i * 30 - 90)
        sx = ccx + 12 * math.cos(ang)
        sy = ccy + 12 * math.sin(ang)
        draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(250, 206, 64))
    draw.ellipse([ccx - 2, ccy - 2, ccx + 2, ccy + 2], fill=(250, 206, 64))
    # Union Jack block: blue field, white diagonals and cross, red over
    uk = (x0 + 100, y0 + 7, x1 - 10, y1 - 7)
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
    draw.rectangle(eu, outline=(200, 212, 230))
    draw.rectangle(uk, outline=(200, 212, 230))
    tag(draw, x0 + 57, y1 - 17, "RESET TALKS", font(SANS_BOLD, 8), RED, WHITE)
    draw.rectangle(box, outline=RULE)


def feat_bars(draw, box) -> None:
    """07 — CPI bars on a dark panel, dashed 2% target line, 2.3% tagged."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    base = y1 - 6
    draw.line([(x0 + 12, base), (x1 - 12, base)], fill=(150, 168, 195),
              width=2)
    colours = [(232, 186, 96), (226, 146, 52), (214, 106, 30), (196, 54, 28)]
    heights = (12, 17, 22, 30)
    # dashed target line at the second bar's height (the BoJ's 2%),
    # drawn first so the taller bars occlude it like a real chart
    ty = base - heights[1]
    for dx in range(x0 + 14, x1 - 14, 10):
        draw.line([(dx, ty), (dx + 5, ty)], fill=WHITE, width=1)
    for i, (h, colour) in enumerate(zip(heights, colours)):
        bx = x0 + 28 + i * 37
        draw.rectangle([bx, base - h, bx + 24, base], fill=colour)
    draw.text((x0 + 12, y0 + 4), "2% TARGET", font=font(SANS_BOLD, 8),
              fill=WHITE)
    # the headline 2.3% over the last, tallest bar
    draw.text((x0 + 28 + 3 * 37, base - heights[3] - 11), "2.3%",
              font=font(SANS_BOLD, 10), fill=WHITE)
    draw.rectangle(box, outline=RULE)


def feat_percent(draw, box) -> None:
    """08 — LPR curve on a dark panel: 1Y 3.00% rising to 5Y 3.50%."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    draw.text((x0 + 6, y0 + 4), "%", font=font(SANS_BOLD, 26),
              fill=PANEL_LINE)
    teal = (64, 200, 188)
    p1 = (x0 + 44, y0 + 31)
    p2 = (x1 - 54, y0 + 14)
    draw.line([p1, (x0 + 100, y0 + 25), p2], fill=teal, width=3,
              joint="curve")
    for px, py in (p1, p2):
        draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=WHITE)
    draw.text((p1[0] - 18, p1[1] + 7), "1Y 3.00%", font=font(SANS_BOLD, 10),
              fill=WHITE)
    draw.text((p2[0] - 32, p2[1] - 14), "5Y 3.50%", font=font(SANS_BOLD, 10),
              fill=WHITE)
    draw.rectangle(box, outline=RULE)


def feat_cricket(draw, box) -> None:
    """09 — bat, ball, and the big 118, floodlit on a dark panel."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(18, 36, 32))
    draw.rectangle([x0 + 10, y0 + 31, x1 - 10, y0 + 39], fill=(196, 176, 130))
    draw.line([(x0 + 66, y0 + 5), (x0 + 56, y0 + 16)], fill=(230, 235, 240),
              width=3)
    draw.polygon([(x0 + 50, y0 + 14), (x0 + 62, y0 + 16), (x0 + 58, y1 - 8),
                  (x0 + 44, y1 - 10)], fill=(214, 184, 124),
                 outline=(200, 212, 230))
    bx, by = x0 + 104, y0 + 15
    draw.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill=RED)
    draw.arc([bx - 4, by - 5, bx + 4, by + 5], start=300, end=120,
             fill=WHITE, width=1)
    nf = fit_font(draw, "118", SANS_BOLD, 32, 58, minimum=20)
    draw.text((x1 - 64, y0 + 9), "118", font=nf, fill=WHITE)
    draw.rectangle(box, outline=RULE)


def feat_ballot(draw, box) -> None:
    """10 — tribunal building: pediment, columns, and a 2027 banner."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    cx = (x0 + x1) // 2
    draw.polygon([(x0 + 34, y0 + 15), (x1 - 34, y0 + 15), (cx, y0 + 4)],
                 fill=(150, 110, 190))
    draw.rectangle([x0 + 34, y0 + 15, x1 - 34, y0 + 19], fill=(130, 92, 168))
    for i in range(4):
        bx = x0 + 44 + i * 32
        draw.rectangle([bx, y0 + 21, bx + 9, y1 - 13], fill=WHITE,
                       outline=(170, 180, 200))
    draw.rectangle([x0 + 30, y1 - 13, x1 - 30, y1 - 7], fill=(150, 110, 190))
    banner = (cx - 36, y0 + 25, cx + 36, y0 + 41)
    draw.rectangle(banner, fill=RED)
    centred_text(draw, cx, (banner[1] + banner[3]) / 2 - 7,
                 "2027", font(SANS_BOLD, 15), WHITE)
    draw.rectangle(box, outline=RULE)


def feat_boat(draw, box) -> None:
    """11 — boat hull on scalloped waves, night sea."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(13, 28, 52))
    tag(draw, x0 + 8, y1 - 18, "4 DEAD", font(SANS_BOLD, 10), RED, WHITE)
    draw.ellipse([x1 - 29, y0 + 5, x1 - 19, y0 + 15], fill=(225, 232, 245))
    cx = (x0 + x1) // 2
    draw.line([(cx, y0 + 6), (cx, y0 + 23)], fill=(230, 235, 240), width=2)
    draw.polygon([(cx, y0 + 6), (cx + 11, y0 + 9), (cx, y0 + 12)], fill=RED)
    for hx in (cx - 22, cx, cx + 22):
        draw.ellipse([hx - 3, y0 + 16, hx + 3, y0 + 22], fill=WHITE)
    draw.rectangle([x0 + 44, y0 + 23, x1 - 44, y0 + 27], fill=(150, 84, 52))
    draw.polygon([(x0 + 50, y0 + 27), (x1 - 50, y0 + 27), (x1 - 64, y1 - 9),
                  (x0 + 64, y1 - 9)], fill=(178, 92, 58))
    for row, wy in enumerate((y1 - 16, y1 - 9)):
        for wx in range(x0 + 6 + row * 11, x1 - 18, 22):
            draw.arc([wx, wy - 4, wx + 16, wy + 5], start=180, end=360,
                     fill=(90, 170, 220), width=2)
    draw.rectangle(box, outline=RULE)


def feat_placard(draw, box) -> None:
    """12 — placards on sticks over a row of heads; one reads 100 SQUARES."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    for px, py in ((x0 + 10, y0 + 6), (x0 + 140, y0 + 6)):
        draw.line([(px + 18, py + 19), (px + 18, y1 - 12)],
                  fill=(190, 160, 120), width=2)
        draw.rectangle([px, py, px + 36, py + 19], fill=WHITE, outline=INK)
        draw.line([(px + 5, py + 6), (px + 27, py + 6)], fill=RED, width=2)
        draw.line([(px + 5, py + 12), (px + 22, py + 12)], fill=INK_SOFT,
                  width=2)
    # the big centre placard carries the story's number
    px, py, pw, ph = x0 + 58, y0 + 9, 76, 21
    draw.line([(px + pw // 2, py + ph), (px + pw // 2, y1 - 12)],
              fill=(190, 160, 120), width=2)
    draw.rectangle([px, py, px + pw, py + ph], fill=WHITE, outline=INK)
    pf = fit_font(draw, "100 SQUARES", SANS_BOLD, 11, pw - 8, minimum=8)
    centred_text(draw, px + pw / 2, py + (ph - pf.size) / 2 + 1,
                 "100 SQUARES", pf, RED)
    heads = [(200, 90, 80), (230, 170, 80), (110, 180, 110),
             (90, 140, 210), (190, 120, 190), (240, 220, 160)]
    for i, colour in enumerate(heads):
        hx, hy = x0 + 24 + i * 28, y1 - 10
        draw.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], fill=colour)
    draw.rectangle(box, outline=RULE)


def feat_pill(draw, box) -> None:
    """13 — one big capsule pill, split two-tone, response rate tagged."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL)
    cx = (x0 + x1) // 2
    top, bot = y0 + 7, y0 + 31
    pink = (229, 92, 132)
    draw.ellipse([x0 + 34, top, x0 + 58, bot], fill=WHITE)
    draw.ellipse([x1 - 58, top, x1 - 34, bot], fill=pink)
    draw.rectangle([x0 + 46, top, cx, bot], fill=WHITE)
    draw.rectangle([cx, top, x1 - 46, bot], fill=pink)
    draw.arc([x0 + 34, top, x0 + 58, bot], start=90, end=270,
             fill=(235, 215, 225), width=2)
    draw.arc([x1 - 58, top, x1 - 34, bot], start=270, end=90,
             fill=(235, 215, 225), width=2)
    draw.line([(x0 + 46, top), (x1 - 46, top)], fill=(235, 215, 225),
              width=2)
    draw.line([(x0 + 46, bot), (x1 - 46, bot)], fill=(235, 215, 225),
              width=2)
    draw.line([(cx, top), (cx, bot)], fill=(200, 60, 100), width=2)
    draw.ellipse([x0 + 10, y0 + 8, x0 + 19, y0 + 17], fill=(64, 200, 188))
    draw.ellipse([x1 - 22, y0 + 6, x1 - 13, y0 + 15], fill=(240, 170, 60))
    centred_text(draw, cx, y0 + 36, "60.7% RESPONSE",
                 font(SANS_BOLD, 10), (255, 150, 180))
    draw.rectangle(box, outline=RULE)


FEAT_ART = {"chart": feat_chart, "orbit": feat_orbit, "flags": feat_flags,
            "bars": feat_bars, "percent": feat_percent, "cricket": feat_cricket,
            "ballot": feat_ballot, "boat": feat_boat, "placard": feat_placard,
            "pill": feat_pill}

# --------------------------------------------------------------------------
# Solid-fill world map (dark), geographically honest
# --------------------------------------------------------------------------

# Continent polygons coded in (longitude, latitude), traced along the
# coast.  draw_map projects them equirectangularly into the map box
# (x from longitude -170..190, y from latitude 80..-60), the same
# projection the story pins use, so pins land on the right coasts.
CONTINENTS: list[list[tuple[float, float]]] = [
    # Greenland
    [(-46, 60), (-42, 63), (-36, 67), (-28, 69), (-22, 70), (-24, 75),
     (-32, 79), (-48, 80), (-56, 76), (-55, 71), (-53, 65), (-50, 61)],
    # North America (Alaska, Hudson Bay, Florida, Yucatan, Baja)
    [(-168, 66), (-162, 68), (-156, 71), (-146, 70), (-136, 69),
     (-126, 70), (-114, 68), (-102, 68), (-94, 69), (-89, 68), (-86, 66),
     (-84, 62), (-87, 58), (-85, 56), (-81, 54), (-78, 55), (-78, 59),
     (-80, 62), (-76, 64), (-70, 62), (-64, 60), (-56, 53), (-59, 49),
     (-65, 45), (-70, 44), (-73, 41), (-74, 39), (-75, 36), (-78, 34),
     (-80, 32), (-81, 29), (-80, 26), (-82, 28), (-84, 30), (-87, 30),
     (-90, 29), (-94, 29), (-97, 27), (-97, 24), (-95, 20), (-91, 19),
     (-88, 21), (-87, 20), (-88, 16), (-84, 15), (-80, 10), (-78, 8),
     (-80, 9), (-83, 10), (-85, 12), (-88, 13), (-92, 15), (-95, 16),
     (-98, 17), (-102, 19), (-105, 21), (-108, 23), (-110, 24),
     (-112, 28), (-114, 30), (-117, 33), (-120, 34), (-122, 37),
     (-124, 40), (-124, 45), (-127, 49), (-131, 54), (-136, 58),
     (-143, 60), (-150, 61), (-153, 59), (-157, 56), (-161, 55),
     (-164, 58), (-166, 61), (-168, 64)],
    # South America (Brazil bulging east, tapering south)
    [(-78, 8), (-74, 11), (-68, 11), (-62, 10), (-56, 7), (-52, 5),
     (-50, 1), (-44, -2), (-38, -5), (-35, -8), (-38, -12), (-39, -16),
     (-40, -21), (-46, -24), (-52, -28), (-57, -33), (-58, -36),
     (-62, -39), (-64, -42), (-65, -46), (-67, -50), (-68, -53),
     (-70, -54), (-72, -52), (-74, -48), (-74, -42), (-73, -36),
     (-72, -30), (-70, -24), (-70, -19), (-73, -15), (-77, -11),
     (-80, -6), (-81, -2), (-80, 2), (-78, 6)],
    # Eurasia (one landmass: Iberia, Scandinavia, the Arctic coast,
    # Kamchatka, Korea, SE Asia, the Indian triangle, Arabia)
    [(-9, 37), (-9, 43), (-4, 44), (-5, 48), (-1, 50), (2, 51), (5, 53),
     (8, 55), (8, 57), (6, 58), (5, 60), (8, 61), (12, 64), (16, 67),
     (21, 70), (28, 71), (36, 69), (44, 68), (54, 69), (64, 70),
     (72, 72), (82, 73), (92, 75), (103, 77), (113, 74), (124, 72),
     (134, 72), (144, 71), (154, 70), (164, 69), (173, 66), (178, 64),
     (171, 62), (164, 61), (160, 57), (157, 52), (155, 51), (151, 59),
     (148, 59), (143, 54), (141, 49), (139, 45), (136, 44), (132, 43),
     (129, 41), (127, 39), (126, 36), (127, 34), (124, 37), (121, 37),
     (120, 33), (121, 30), (118, 27), (114, 23), (110, 21), (107, 18),
     (109, 14), (107, 10), (104, 8), (102, 5), (100, 2), (99, 6),
     (98, 10), (96, 14), (94, 17), (92, 20), (90, 22), (87, 21),
     (85, 19), (82, 16), (80, 13), (78, 9), (76, 10), (73, 14),
     (72, 19), (70, 21), (67, 23), (61, 25), (57, 26), (54, 28),
     (51, 29), (48, 30), (50, 26), (52, 24), (56, 24), (58, 22),
     (55, 17), (52, 15), (45, 12), (43, 12), (42, 15), (39, 20),
     (35, 28), (34, 31), (36, 34), (36, 36), (33, 36), (30, 36),
     (27, 37), (25, 36), (23, 36), (22, 37), (23, 39), (20, 40),
     (18, 40), (16, 38), (15, 40), (13, 42), (11, 44), (8, 44),
     (6, 43), (3, 43), (2, 41), (0, 39), (-1, 37), (-2, 36), (-5, 36),
     (-7, 37)],
    # Africa (the Horn, the western bulge)
    [(-6, 35), (-9, 32), (-13, 28), (-16, 24), (-17, 20), (-17, 15),
     (-16, 12), (-13, 8), (-8, 5), (-4, 5), (2, 6), (6, 4), (9, 0),
     (12, -5), (13, -11), (13, -17), (14, -22), (15, -27), (17, -31),
     (19, -34), (22, -34), (26, -34), (30, -31), (32, -28), (33, -25),
     (35, -21), (36, -16), (37, -12), (39, -8), (40, -4), (41, -1),
     (44, 3), (48, 7), (51, 11), (46, 11), (43, 12), (40, 15),
     (38, 19), (36, 22), (34, 26), (33, 28), (31, 30), (30, 31),
     (26, 32), (21, 33), (16, 32), (11, 34), (10, 37), (6, 37),
     (1, 36), (-2, 35)],
    # Madagascar
    [(44, -13), (47, -14), (50, -16), (50, -20), (47, -24), (45, -25),
     (43, -23), (43, -19), (44, -15)],
    # Britain and Ireland
    [(-5, 50), (-3, 51), (0, 51), (1, 52), (-1, 54), (-2, 56),
     (-4, 58), (-6, 57), (-5, 55), (-3, 54), (-5, 52)],
    [(-10, 51), (-6, 52), (-6, 54), (-8, 55), (-10, 54), (-10, 52)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 37), (141, 39),
     (141, 41), (142, 43), (144, 44), (145, 44), (143, 42), (141, 40),
     (140, 38), (138, 36), (136, 34), (133, 33), (131, 32)],
    # Indonesia and the Philippines
    [(95, 5), (98, 3), (101, 0), (104, -3), (106, -6), (104, -5),
     (101, -1), (98, 2), (95, 4)],
    [(106, -6), (110, -7), (114, -7), (114, -9), (109, -8), (106, -7)],
    [(109, 2), (110, 4), (113, 5), (116, 6), (118, 3), (117, 0),
     (115, -3), (112, -3), (109, 0)],
    [(119, 1), (120, 2), (121, 1), (120, -1), (121, -3), (120, -4),
     (119, -2)],
    [(131, -1), (134, -2), (138, -2), (142, -3), (146, -5), (149, -8),
     (150, -10), (146, -9), (142, -7), (138, -4), (133, -3)],
    [(120, 18), (121, 16), (122, 14), (121, 12), (120, 13), (119, 15)],
    # Australia and Tasmania
    [(113, -22), (112, -25), (114, -30), (115, -33), (117, -35),
     (122, -34), (127, -32), (130, -32), (132, -31), (134, -33),
     (135, -35), (137, -35), (139, -36), (140, -38), (144, -38),
     (147, -38), (149, -37), (150, -36), (152, -33), (153, -29),
     (153, -25), (151, -22), (149, -19), (146, -18), (144, -15),
     (142, -13), (142, -11), (141, -14), (141, -17), (140, -18),
     (137, -16), (136, -14), (135, -12), (133, -11), (131, -12),
     (128, -13), (125, -15), (122, -17), (119, -19), (116, -21)],
    [(145, -41), (148, -41), (148, -43), (146, -43)],
    # New Zealand (exaggerated diagonal slivers, so the islands — and
    # pin 09 at Wellington, 174.8E 41.3S — stay visible at map scale)
    [(168, -34), (174, -35), (178, -36), (179, -38), (177, -41),
     (174, -42), (171, -40), (169, -37)],
    [(165, -44), (168, -45), (172, -44), (174, -42), (173, -40),
     (169, -42), (166, -43)],
]


def draw_map(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
             pins: list[dict]) -> None:
    """Solid-fill world map on a deep-navy ocean, true-position pins."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=OCEAN, outline=RULE)
    wdt, hgt = x1 - x0, y1 - y0

    def proj(lon: float, lat: float) -> tuple[float, float]:
        return (x0 + (lon + 170) / 360 * wdt, y0 + (80 - lat) / 140 * hgt)

    for poly in CONTINENTS:
        pts = [proj(lon, lat) for lon, lat in poly]
        draw.polygon(pts, fill=LAND_DARK, outline=(178, 198, 220), width=1)
    # pins for stories 01-13 at their true positions; a pin may carry a
    # small dx/dy nudge (a few px, east-west order preserved) where true
    # positions would overlap — the Europe cluster, the NE-Asia cluster
    pin_font = font(SANS_BOLD, 9)
    for pin in pins:
        px = x0 + int(pin["x"] * wdt) + pin.get("dx", 0)
        py = y0 + int(pin["y"] * hgt) + pin.get("dy", 0)
        label = str(pin["n"])
        draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(27, 58, 128),
                     outline=WHITE, width=1)
        tw = text_w(draw, label, pin_font)
        draw.text((px - tw / 2, py - 5), label, font=pin_font, fill=WHITE)
    # SPACE callout for story 05 (Mercury): a small plate on the empty
    # South Pacific, bottom left — the story is not a place on the map
    plate = (x0 + 5, y1 - 41, x0 + 91, y1 - 5)
    draw.rectangle(plate, fill=(10, 17, 34), outline=(150, 170, 200),
                   width=1)
    gx, gy = x0 + 17, y1 - 23
    draw.ellipse([gx - 6, gy - 6, gx + 6, gy + 6], fill=(219, 144, 62))
    draw.arc([gx - 10, gy - 4, gx + 10, gy + 5], start=200, end=520,
             fill=(220, 228, 240), width=1)
    draw.text((x0 + 30, y1 - 38), "5 · SPACE", font=font(SANS_BOLD, 8),
              fill=WHITE)
    draw.text((x0 + 30, y1 - 28), "MERCURY", font=font(SANS_BOLD, 8),
              fill=(240, 196, 130))
    draw.text((x0 + 30, y1 - 18), "BepiColombo", font=font(SANS, 8),
              fill=(200, 212, 230))


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
        banner(draw, art_box[0], art_box[1],
               LEAD_BANNERS[lead["n"]], font(SANS_BOLD, 13))
        src = lead["source"].replace(", ", " · ")
        if lead["n"] == "01":
            chip(draw, art_box[0] + 6, art_box[3] - 19 - 14, src)
        elif lead["n"] == "03":
            chip(draw, art_box[0] + 96, art_box[3] - 14, src)
        else:
            chip(draw, art_box[2] - chip_w(draw, src) - 6,
                 art_box[3] - 14, src)
        cy = y + LEAD_ART_H + 6
        num_chip(draw, x + 7, cy + 6, 7, lead["n"], font(SANS_BOLD, 9))
        draw.text((x + 18, cy), lead["kicker"], font=kick_f, fill=RED)
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
            banner(draw, art_box[0], art_box[1],
                   FEAT_BANNERS[feat["n"]], font(SANS_BOLD, 10))
            src = feat["source"].replace(", ", " · ")
            chip(draw, art_box[2] - chip_w(draw, src) - 4,
                 art_box[3] - 14, src)
            kick = feat["kicker"]
            kf = fit_font(draw, kick, SANS_BOLD, 10, col_w - 15, minimum=8)
            num_chip(draw, x + 6, y + FEAT_ART_H + 3 + 5, 6, feat["n"],
                     font(SANS_BOLD, 8))
            draw.text((x + 15, y + FEAT_ART_H + 3), kick, font=kf, fill=RED)
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
    draw.text((MARGIN, y + 15), "Each number is the story with that number on this page.",
              font=font(SANS_ITALIC, 11), fill=INK_SOFT)
    draw_map(draw, (MARGIN, y + 30, MARGIN + map_w, y + 190), data["pins"])
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
        yy = y + 33 + row * 13.4
        draw.text((x, yy), f'{brief["n"]}', font=num_f, fill=RED)
        nx = x + text_w(draw, f'{brief["n"]}', num_f) + 4
        draw.text((nx, yy), brief["place"], font=place_f, fill=INK)
        px = nx + text_w(draw, brief["place"], place_f) + 4
        # One line only: shrink just this line if it would spill over.
        bf = fit_font(draw, brief["text"], SANS, 12, x + col_w - px, minimum=9)
        draw.text((px, yy), brief["text"], font=bf, fill=INK_SOFT)
    return y + 205


def section_close(draw, data: dict, y: int) -> int:
    """Thin date-check strip (rank-1 weight) and the attribution footer."""
    dc = data["date_check"]
    draw.rectangle([MARGIN, y, X1, y + 26], outline=RED, width=1)
    draw.text((MARGIN + 8, y + 8), "DATE CHECK", font=font(SANS_BOLD, 9),
              fill=RED)
    body_f = font(SANS, 9)
    lines = wrap(draw, dc["body"], body_f, INNER - 92)
    draw_lines(draw, lines[:2], MARGIN + 84, y + 3, body_f, INK_SOFT, 11)
    y += 31
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
    assert len(data["numbers"]) == 6 and len(data["pins"]) == 12

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
