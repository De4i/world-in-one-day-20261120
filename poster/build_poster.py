#!/usr/bin/env python3
"""
World in One Day — poster builder (v3).

Renders entry.png (1024 x 1024), a one-page newspaper that sums up the
world news of Friday 20 November 2026, from the structured story data in
poster/data/stories.json.

Design notes (v3)
-----------------
* Cream newspaper front page: paper background, ink-navy text, red
  accents, a big serif masthead ("Friday 20 November 2026") under a red
  kicker ("THE WORLD IN ONE DAY") and a standfirst naming the leads.
* Everything is drawn with Pillow primitives: no photographs, no
  external assets, so the render is fully deterministic — two runs
  produce a byte-identical PNG.
* The three lead stories get full scene panels that fill their frames:
  a map-style Bay of Bengal panel (coastline, cyclone spiral kept fully
  inside the frame, Gopalpur marker, red LANDFALL banner), a Kyiv night
  scene (skyline, glowing missile trails, "~30 MISSILES · 7 WAVES"
  tag), and a COP31 panel (big thermometer, clashing deadlock arrows,
  red "FINAL DAY · DEADLOCK" badge, "$120BN FINANCE GAP" tag).
* Each of the ten feature cards carries a full illustration occupying
  roughly the top half of the card, drawn for its own story: Asia AI
  sell-off down-chart with index labels, BepiColombo/Mercury orbit
  diagram, EU and UK flags, Japan CPI bars against the 2% target line,
  China LPR curve (1Y 3.00% / 5Y 3.50%), Wellington cricket scene,
  Bukele 2027 ballot graphic, Senegal migrant boat, Italy CGIL strike
  flags ("100 SQUARES"), Barcelona cancer capsule ("60.7% RESPONSE").
* The world map is drawn as simplified solid-fill continent polygons
  (tan/khaki fill, navy outline) with numbered pins 1-13 on top.
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

PAPER = (246, 241, 230)        # cream newsprint (#f6f1e6)
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

LEAD_ART_H = 112               # lead scene panel height
FEAT_ART_H = 62                # feature illustration height (~half a card)

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


def chip(draw, box, text: str, fill, ink=WHITE, start: int = 11) -> None:
    """A solid tag chip with one centred line of bold text."""
    draw.rectangle(box, fill=fill)
    fnt = fit_font(draw, text, SANS_BOLD, start, box[2] - box[0] - 10)
    centred_text(draw, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2,
                 text, fnt, ink)


# --------------------------------------------------------------------------
# Lead illustrations — full scene panels filling their frames
# --------------------------------------------------------------------------

def art_cyclone(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Map-style panel: Odisha coast, Bay of Bengal, storm, landfall banner."""
    x0, y0, x1, y1 = box
    banner_h = 16
    sea_bot = y1 - banner_h
    draw.rectangle(box, fill=(186, 214, 228))
    # landmass on the right: sand coast with a greener inland inset
    coast = [(x1 - 118, y0), (x1 - 94, y0 + 30), (x1 - 106, y0 + 62),
             (x1 - 90, sea_bot)]
    draw.polygon(coast + [(x1, sea_bot), (x1, y0)], fill=(203, 186, 128))
    draw.polygon([(x1 - 74, y0 + 6), (x1 - 8, y0 + 6), (x1 - 8, sea_bot - 6),
                  (x1 - 62, sea_bot - 6), (x1 - 76, y0 + 58), (x1 - 66, y0 + 30)],
                 fill=(150, 168, 100))
    draw.line(coast, fill=INK_SOFT, width=2)
    # sea label and coast label
    draw.text((x0 + 12, y0 + 8), "BAY OF BENGAL",
              font=font(SANS_BOLD, 13), fill=(30, 70, 110))
    draw.text((x1 - 52, y0 + 10), "ODISHA",
              font=font(SANS_BOLD, 10), fill=INK_SOFT)
    # faint swell arcs low over the sea, clear of the spiral
    for wy in (sea_bot - 14, sea_bot - 6):
        for wx in range(x0 + 176, x1 - 128, 26):
            draw.arc([wx, wy - 4, wx + 16, wy + 4], start=180, end=360,
                     fill=(150, 190, 215), width=2)
    # the cyclone spiral, kept fully inside the panel and clear of the
    # BAY OF BENGAL label: centre x0+92, y0+56 with outer radius 33 and
    # stroke 7 spans x 55..129, y 19..93 of the frame
    cx, cy = x0 + 92, y0 + 56
    for radius, start, colour, width in (
            (33, 15, (255, 255, 255), 7), (33, 195, (120, 160, 200), 7),
            (26, 105, (255, 255, 255), 6), (26, 285, (100, 145, 190), 6),
            (19, 30, (255, 255, 255), 5), (19, 215, (85, 130, 180), 5),
            (12, 130, (255, 255, 255), 4), (12, 320, (110, 150, 195), 4)):
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius],
                 start=start, end=start + 140, fill=colour, width=width)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=WHITE)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=RED)
    # dashed forecast track from the eye to the Gopalpur landfall marker
    mx, my = x1 - 100, y0 + 56
    steps = 6
    for i in range(steps):
        t0, t1 = i / steps, (i + 0.55) / steps
        draw.line([(cx + 30 + (mx - cx - 30) * t0, cy + (my - cy) * t0),
                   (cx + 30 + (mx - cx - 30) * t1, cy + (my - cy) * t1)],
                  fill=RED_DARK, width=2)
    draw.ellipse([mx - 6, my - 6, mx + 6, my + 6], outline=RED, width=2)
    draw.ellipse([mx - 2, my - 2, mx + 2, my + 2], fill=RED)
    # place label on a white tag over the land
    tag = (x1 - 84, y0 + 70, x1 - 8, y0 + 84)
    draw.rectangle(tag, fill=WHITE, outline=INK_SOFT)
    centred_text(draw, (tag[0] + tag[2]) / 2, (tag[1] + tag[3]) / 2,
                 "GOPALPUR", font(SANS_BOLD, 10), INK)
    # bottom banner strip
    chip(draw, (x0, sea_bot, x1, y1), "LANDFALL · GUSTS 110 KM/H", RED)
    draw.rectangle(box, outline=RULE)


def art_missiles(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Night scene: skyline silhouette, glowing missile trails, tag chip."""
    x0, y0, x1, y1 = box
    wdt, hgt = x1 - x0, y1 - y0
    draw.rectangle(box, fill=(13, 20, 42))
    # deterministic star field (arithmetic pattern, never random)
    for i in range(64):
        sx = x0 + (i * 53 + 11) % max(1, wdt - 8) + 4
        sy = y0 + (i * 29 + 7) % max(1, int(hgt * 0.5)) + 3
        draw.point((sx, sy), fill=(220, 228, 245))
    # crescent moon, top left
    draw.ellipse([x0 + 15, y0 + 5, x0 + 29, y0 + 19], fill=(228, 233, 245))
    draw.ellipse([x0 + 20, y0 + 3, x0 + 34, y0 + 17], fill=(13, 20, 42))
    # skyline: black blocks with lit windows, standing over the river band
    base = y1 - 14
    widths = [40, 28, 46, 32, 54, 30, 44, 34, 52]
    heights = [32, 46, 25, 40, 32, 48, 27, 42, 26]
    bx = x0
    for w, h in zip(widths, heights):
        draw.rectangle([bx, base - h, bx + w - 2, base], fill=(5, 8, 16))
        for wy in range(base - h + 5, base - 5, 9):
            for wx in (bx + 6, bx + w - 11):
                if (wx + wy) % 3:
                    draw.rectangle([wx, wy, wx + 2, wy + 2], fill=(250, 210, 110))
        bx += w
    # river band along the bottom, with light sparkles
    draw.rectangle([x0, base, x1, y1], fill=(24, 50, 82))
    for i in range(6):
        rx = x0 + 18 + i * 52
        draw.line([(rx, y1 - 6), (rx + 16, y1 - 6)], fill=(170, 200, 225), width=1)
    # six missile trails arcing down toward the city, with glow heads
    trails = [(0.10, 0.04, 0.24, 0.58), (0.26, 0.02, 0.38, 0.63),
              (0.44, 0.05, 0.52, 0.57), (0.60, 0.02, 0.68, 0.62),
              (0.76, 0.04, 0.82, 0.58), (0.90, 0.03, 0.93, 0.61)]
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
    # tag chip over the lower-left skyline
    chip(draw, (x0 + 8, y1 - 24, x0 + 172, y1 - 8), "~30 MISSILES · 7 WAVES", RED)
    draw.rectangle(box, outline=RULE)


def art_climate(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Thermometer, sun, clashing deadlock arrows, red badge, finance tag."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(243, 226, 199))
    # sun, top right
    sx, sy = x1 - 26, y0 + 52
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                   (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
        draw.line([(sx + dx * 13, sy + dy * 13), (sx + dx * 18, sy + dy * 18)],
                  fill=(217, 119, 6), width=2)
    draw.ellipse([sx - 10, sy - 10, sx + 10, sy + 10], fill=(240, 160, 40),
                 outline=(217, 119, 6), width=1)
    # thermometer: white tube, mercury high in the red, big bulb
    tx = x0 + 46
    draw.rectangle([tx - 8, y0 + 12, tx + 8, y0 + 72], fill=WHITE,
                   outline=INK, width=2)
    draw.rectangle([tx - 3, y0 + 22, tx + 3, y0 + 84], fill=RED)
    draw.ellipse([tx - 13, y0 + 68, tx + 13, y0 + 94], fill=RED,
                 outline=INK, width=2)
    for i in range(5):
        ty = y0 + 18 + i * 11
        draw.line([(tx + 10, ty), (tx + 16, ty)], fill=INK, width=1)
    # bold red badge across the top of the panel
    chip(draw, (x0 + 92, y0 + 10, x1 - 10, y0 + 34),
         "FINAL DAY · DEADLOCK", RED, start=13)
    # two arrows driving at each other, split by a crack: the deadlock
    ay = y0 + 58
    draw.polygon([(x0 + 92, ay - 6), (x0 + 138, ay - 6), (x0 + 138, ay - 12),
                  (x0 + 156, ay), (x0 + 138, ay + 12), (x0 + 138, ay + 6),
                  (x0 + 92, ay + 6)], fill=RED)
    draw.polygon([(x1 - 92, ay - 6), (x1 - 138, ay - 6), (x1 - 138, ay - 12),
                  (x1 - 156, ay), (x1 - 138, ay + 12), (x1 - 138, ay + 6),
                  (x1 - 92, ay + 6)], fill=INK)
    mid = (x0 + x1) // 2
    draw.line([(mid + 2, ay - 14), (mid - 3, ay - 4), (mid + 4, ay + 4),
               (mid - 2, ay + 15)], fill=INK, width=2)
    # finance-gap tag along the bottom
    chip(draw, (x0 + 92, y1 - 24, x1 - 92, y1 - 8), "$120BN FINANCE GAP", INK)
    draw.rectangle(box, outline=RULE)


LEAD_ART = {"cyclone": art_cyclone, "missiles": art_missiles, "climate": art_climate}

# --------------------------------------------------------------------------
# Feature illustrations — a full graphic in the top half of each card
# --------------------------------------------------------------------------

def feat_chart(draw, box) -> None:
    """04 — Asia AI sell-off: plunging red line, Nikkei/KOSPI labels."""
    x0, y0, x1, y1 = box
    wdt, hgt = x1 - x0, y1 - y0
    draw.rectangle(box, fill=(22, 30, 50))
    for gx in range(x0 + 12, x1, 24):
        draw.line([(gx, y0 + 3), (gx, y1 - 3)], fill=(48, 60, 88), width=1)
    for gy in range(y0 + 8, y1, 15):
        draw.line([(x0 + 3, gy), (x1 - 3, gy)], fill=(48, 60, 88), width=1)
    draw.line([(x0 + 10, y0 + 19), (x0 + 56, y0 + 24), (x0 + 100, y0 + 22)],
              fill=(120, 130, 155), width=1)
    pts = [(x0 + 10, y0 + 22), (x0 + 56, y0 + 28), (x0 + 100, y0 + 25),
           (x0 + 142, y0 + 38), (x1 - 14, y1 - 10)]
    draw.line(pts, fill=RED, width=3, joint="curve")
    for px, py in pts[:-1]:
        draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=WHITE)
    draw.polygon([(x1 - 14, y1 - 10), (x1 - 26, y1 - 11), (x1 - 19, y1 - 21)],
                 fill=RED)
    draw.text((x0 + 8, y0 + 4), "NIKKEI -4.5%", font=font(SANS_BOLD, 10),
              fill=WHITE)
    draw.text((x0 + 8, y1 - 15), "KOSPI -4.7%", font=font(SANS_BOLD, 10),
              fill=(255, 150, 150))
    draw.rectangle(box, outline=RULE)


def feat_orbit(draw, box) -> None:
    """05 — BepiColombo: Mercury disc, orbit arc, probe on its way in."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(15, 23, 45))
    for i in range(22):
        sx = x0 + (i * 41 + 7) % max(1, (x1 - x0 - 6)) + 3
        sy = y0 + (i * 23 + 5) % max(1, (y1 - y0 - 8)) + 3
        draw.point((sx, sy), fill=(205, 215, 235))
    cx, cy = x0 + 58, (y0 + y1) // 2
    draw.arc([x0 + 6, y0 + 4, x0 + 132, y1 - 4], start=300, end=235,
             fill=WHITE, width=2)
    draw.ellipse([cx - 19, cy - 19, cx + 19, cy + 19], fill=(219, 144, 62))
    for dy, half in ((-8, 15), (0, 18), (8, 15)):
        draw.line([(cx - half, cy + dy), (cx + half, cy + dy)],
                  fill=(178, 102, 42), width=3)
    # the probe, out at the end of its long arc, panel and antenna dish
    px, py = x0 + 152, y0 + 15
    draw.line([(px, py), (px - 9, py - 7)], fill=WHITE, width=1)
    draw.rectangle([px - 10, py + 4, px - 2, py + 10], fill=(140, 200, 255))
    draw.rectangle([px + 3, py + 4, px + 11, py + 10], fill=(140, 200, 255))
    draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=WHITE)
    draw.text((x0 + 8, y0 + 5), "MERCURY", font=font(SANS_BOLD, 10),
              fill=(200, 210, 230))
    draw.rectangle(box, outline=RULE)


def feat_flags(draw, box) -> None:
    """06 — EU circle of stars beside a Union Jack."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(226, 233, 240))
    eu = (x0 + 10, y0 + 7, x0 + 84, y1 - 7)
    draw.rectangle(eu, fill=(32, 62, 142))
    ccx, ccy = (eu[0] + eu[2]) // 2, (eu[1] + eu[3]) // 2
    for i in range(12):
        ang = math.radians(i * 30 - 90)
        sx = ccx + 14 * math.cos(ang)
        sy = ccy + 14 * math.sin(ang)
        draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(250, 206, 64))
    draw.ellipse([ccx - 2, ccy - 2, ccx + 2, ccy + 2], fill=(250, 206, 64))
    uk = (x0 + 104, y0 + 7, x1 - 10, y1 - 7)
    draw.rectangle(uk, fill=(33, 52, 110))
    draw.line([(uk[0], uk[1]), (uk[2], uk[3])], fill=WHITE, width=6)
    draw.line([(uk[0], uk[3]), (uk[2], uk[1])], fill=WHITE, width=6)
    draw.line([(uk[0], uk[1]), (uk[2], uk[3])], fill=(200, 40, 50), width=2)
    draw.line([(uk[0], uk[3]), (uk[2], uk[1])], fill=(200, 40, 50), width=2)
    ucx, ucy = (uk[0] + uk[2]) // 2, (uk[1] + uk[3]) // 2
    draw.rectangle([ucx - 6, uk[1], ucx + 6, uk[3]], fill=WHITE)
    draw.rectangle([uk[0], ucy - 6, uk[2], ucy + 6], fill=WHITE)
    draw.rectangle([ucx - 3, uk[1], ucx + 3, uk[3]], fill=(200, 30, 45))
    draw.rectangle([uk[0], ucy - 3, uk[2], ucy + 3], fill=(200, 30, 45))
    draw.rectangle(eu, outline=INK_SOFT)
    draw.rectangle(uk, outline=INK_SOFT)
    draw.rectangle(box, outline=RULE)


def feat_bars(draw, box) -> None:
    """07 — Japan CPI bars climbing past the dashed 2% target line."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(250, 241, 222))
    base = y1 - 10
    top = y0 + 14
    def y_of(v: float) -> float:
        return base - (v - 1.6) / (2.6 - 1.6) * (base - top)
    draw.line([(x0 + 12, base), (x1 - 12, base)], fill=INK_SOFT, width=2)
    # dashed 2% target line, its label clear at the left end
    ty = y_of(2.0)
    for dx in range(x0 + 80, x1 - 12, 10):
        draw.line([(dx, ty), (dx + 6, ty)], fill=RED, width=2)
    draw.text((x0 + 12, ty - 13), "2% TARGET", font=font(SANS_BOLD, 10),
              fill=RED)
    colours = [(232, 186, 96), (226, 146, 52), (214, 106, 30), (196, 54, 28)]
    for i, (v, colour) in enumerate(zip((1.9, 2.0, 2.1, 2.3), colours)):
        bx = x0 + 22 + i * 34
        draw.rectangle([bx, y_of(v), bx + 24, base], fill=colour)
        label = f"{v:.1f}"
        lw = text_w(draw, label, font(SANS_BOLD, 10))
        draw.text((bx + 12 - lw / 2, y_of(v) + 3), label,
                  font=font(SANS_BOLD, 10), fill=WHITE)
    draw.rectangle(box, outline=RULE)


def feat_percent(draw, box) -> None:
    """08 — China LPR curve: 1Y at 3.00%, 5Y at 3.50%."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(229, 241, 239))
    base = y1 - 12
    top = y0 + 16
    def y_of(v: float) -> float:
        return base - (v - 2.8) / (3.7 - 2.8) * (base - top)
    ax = x0 + 30
    draw.line([(ax, y0 + 6), (ax, base)], fill=INK_SOFT, width=1)
    draw.line([(ax, base), (x1 - 10, base)], fill=INK_SOFT, width=1)
    teal = (15, 118, 110)
    p1 = (x0 + 58, y_of(3.00))
    p2 = (x0 + 112, y_of(3.28))
    p3 = (x1 - 44, y_of(3.50))
    draw.line([p1, p2, p3], fill=teal, width=3, joint="curve")
    for px, py in (p1, p3):
        draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=teal)
    draw.text((p1[0] - 24, p1[1] - 15), "1Y 3.00%", font=font(SANS_BOLD, 11),
              fill=INK)
    draw.text((p3[0] - 30, p3[1] - 16), "5Y 3.50%", font=font(SANS_BOLD, 11),
              fill=teal)
    draw.rectangle(box, outline=RULE)


def feat_cricket(draw, box) -> None:
    """09 — Wellington cricket: stumps, bat, ball and the big 118."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(233, 241, 221))
    # pitch strip across the middle
    draw.rectangle([x0 + 8, y0 + 36, x1 - 78, y0 + 46], fill=(216, 196, 150))
    # stumps at the left end of the pitch
    for i in range(3):
        sx = x0 + 16 + i * 5
        draw.line([(sx, y0 + 22), (sx, y0 + 38)], fill=(150, 110, 40), width=2)
    draw.line([(x0 + 15, y0 + 21), (x0 + 27, y0 + 21)], fill=(150, 110, 40),
              width=2)
    # bat, angled over the crease
    draw.line([(x0 + 74, y0 + 8), (x0 + 62, y0 + 22)], fill=INK, width=3)
    draw.polygon([(x0 + 56, y0 + 20), (x0 + 70, y0 + 23), (x0 + 64, y1 - 10),
                  (x0 + 48, y1 - 13)], fill=(214, 184, 124), outline=INK_SOFT)
    # ball flying off the bat
    bx, by = x0 + 100, y0 + 16
    draw.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill=RED)
    draw.arc([bx - 4, by - 5, bx + 4, by + 5], start=300, end=120,
             fill=WHITE, width=1)
    nf = fit_font(draw, "118", SERIF_BOLD, 36, 62, minimum=22)
    draw.text((x1 - 68, y0 + 12), "118", font=nf, fill=INK)
    draw.rectangle(box, outline=RULE)


def feat_ballot(draw, box) -> None:
    """10 — Bukele 2027: tribunal building beside a ballot box."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(239, 234, 246))
    # tribunal building, left
    cx = x0 + 52
    draw.polygon([(x0 + 14, y0 + 16), (x0 + 90, y0 + 16), (cx, y0 + 5)],
                 fill=(124, 77, 158))
    draw.rectangle([x0 + 14, y0 + 16, x0 + 90, y0 + 20], fill=(106, 62, 140))
    for i in range(4):
        bx = x0 + 20 + i * 17
        draw.rectangle([bx, y0 + 22, bx + 8, y1 - 14], fill=WHITE,
                       outline=INK_SOFT)
    draw.rectangle([x0 + 10, y1 - 14, x0 + 94, y1 - 8], fill=(124, 77, 158))
    # ballot box, right: paper with a tick dropping into the slot
    bx0, by0, bx1, by1 = x0 + 112, y0 + 26, x1 - 12, y1 - 8
    draw.rectangle([bx0 + 16, y0 + 6, bx0 + 44, y0 + 28], fill=WHITE,
                   outline=INK_SOFT)
    draw.line([(bx0 + 22, y0 + 18), (bx0 + 28, y0 + 24), (bx0 + 39, y0 + 11)],
              fill=RED, width=2)
    draw.rectangle([bx0, by0, bx1, by1], fill=(90, 60, 130))
    draw.rectangle([bx0 + 8, by0 + 3, bx1 - 8, by0 + 7], fill=(30, 20, 45))
    centred_text(draw, (bx0 + bx1) / 2, (by0 + by1) / 2,
                 "2027", font(SANS_BOLD, 16), WHITE)
    draw.rectangle(box, outline=RULE)


def feat_boat(draw, box) -> None:
    """11 — Senegal migrant boat: sail, hull, passengers, waves."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(213, 231, 240))
    draw.ellipse([x1 - 27, y0 + 5, x1 - 17, y0 + 15], fill=(240, 180, 80))
    cx = (x0 + x1) // 2
    draw.line([(cx, y0 + 5), (cx, y0 + 26)], fill=INK, width=2)
    draw.polygon([(cx, y0 + 5), (cx + 13, y0 + 9), (cx, y0 + 14)], fill=RED)
    draw.polygon([(cx, y0 + 8), (cx - 11, y0 + 12), (cx, y0 + 16)],
                 fill=WHITE, outline=INK_SOFT)
    for hx in (cx - 26, cx - 9, cx + 9, cx + 26):
        draw.ellipse([hx - 3, y0 + 19, hx + 3, y0 + 25], fill=INK)
    draw.rectangle([x0 + 38, y0 + 26, x1 - 38, y0 + 30], fill=(110, 44, 28))
    draw.polygon([(x0 + 44, y0 + 30), (x1 - 44, y0 + 30), (x1 - 58, y1 - 13),
                  (x0 + 58, y1 - 13)], fill=(148, 62, 40))
    for row, wy in enumerate((y1 - 17, y1 - 9)):
        for wx in range(x0 + 6 + row * 11, x1 - 18, 22):
            draw.arc([wx, wy - 4, wx + 16, wy + 5], start=180, end=360,
                     fill=(20, 110, 150), width=2)
    draw.rectangle(box, outline=RULE)


def feat_placard(draw, box) -> None:
    """12 — Italy CGIL strike: flags and placards, one reading 100 SQUARES."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(247, 237, 225))
    # two side placards with rule lines
    for px, py, w in ((x0 + 8, y0 + 10, 40), (x1 - 48, y0 + 10, 40)):
        draw.line([(px + w // 2, py + 20), (px + w // 2, y1 - 12)],
                  fill=(120, 90, 60), width=2)
        draw.rectangle([px, py, px + w, py + 20], fill=WHITE, outline=INK)
        draw.line([(px + 5, py + 7), (px + w - 7, py + 7)], fill=RED, width=2)
        draw.line([(px + 5, py + 13), (px + w - 12, py + 13)], fill=INK_SOFT,
                  width=2)
    # centre flag placard carrying the story's own number
    cx = (x0 + x1) // 2
    draw.line([(cx, y0 + 38), (cx, y1 - 12)], fill=(120, 90, 60), width=2)
    flag = (cx - 42, y0 + 4, cx + 42, y0 + 38)
    draw.rectangle(flag, fill=RED)
    centred_text(draw, cx, y0 + 7, "100", font(SERIF_BOLD, 17), WHITE)
    centred_text(draw, cx, y0 + 25, "SQUARES", font(SANS_BOLD, 10), WHITE)
    # crowd heads along the bottom
    heads = [(30, 40, 70), (120, 80, 50), (70, 90, 60),
             (150, 110, 60), (90, 60, 110), (50, 70, 90)]
    for i, colour in enumerate(heads):
        hx, hy = x0 + 22 + i * 28, y1 - 8
        draw.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], fill=colour)
    draw.rectangle(box, outline=RULE)


def feat_pill(draw, box) -> None:
    """13 — Barcelona cancer pill: big capsule and the 60.7% response."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(249, 231, 239))
    pink = (229, 92, 132)
    top, bot = y0 + 18, y0 + 44
    mid = x0 + 58
    draw.ellipse([x0 + 14, top, x0 + 40, bot], fill=WHITE)
    draw.ellipse([x0 + 76, top, x0 + 102, bot], fill=pink)
    draw.rectangle([x0 + 27, top, mid, bot], fill=WHITE)
    draw.rectangle([mid, top, x0 + 89, bot], fill=pink)
    draw.arc([x0 + 14, top, x0 + 40, bot], start=90, end=270, fill=INK, width=2)
    draw.arc([x0 + 76, top, x0 + 102, bot], start=270, end=90, fill=INK, width=2)
    draw.line([(x0 + 27, top), (x0 + 89, top)], fill=INK, width=2)
    draw.line([(x0 + 27, bot), (x0 + 89, bot)], fill=INK, width=2)
    draw.line([(mid, top), (mid, bot)], fill=(200, 60, 100), width=2)
    draw.text((x0 + 112, y0 + 10), "60.7%", font=font(SERIF_BOLD, 23), fill=RED)
    draw.text((x0 + 113, y0 + 38), "RESPONSE", font=font(SANS_BOLD, 10),
              fill=INK)
    draw.ellipse([x0 + 10, y0 + 6, x0 + 19, y0 + 15], fill=(15, 118, 110))
    draw.ellipse([x1 - 16, y1 - 15, x1 - 8, y1 - 7], fill=(217, 119, 6))
    draw.rectangle(box, outline=RULE)


FEAT_ART = {"chart": feat_chart, "orbit": feat_orbit, "flags": feat_flags,
            "bars": feat_bars, "percent": feat_percent, "cricket": feat_cricket,
            "ballot": feat_ballot, "boat": feat_boat, "placard": feat_placard,
            "pill": feat_pill}

# --------------------------------------------------------------------------
# Solid-fill world map
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

LAND = (216, 198, 150)         # tan/khaki land fill
LAND_EDGE = (20, 30, 56)       # navy outline


def draw_map(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
             pins: list[dict]) -> None:
    """Solid-fill world map with numbered story pins stamped on top."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(233, 238, 238), outline=RULE)
    wdt, hgt = x1 - x0, y1 - y0
    for poly in CONTINENTS:
        pts = [(x0 + px * wdt, y0 + py * hgt) for px, py in poly]
        draw.polygon(pts, fill=LAND, outline=LAND_EDGE, width=1)
    # pins for stories 01-13 (pin 05, Mercury, sits in the map's sky corner
    # as a little ringed planet under its numbered pin)
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
        draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill=RED, outline=WHITE,
                     width=1)
        tw = text_w(draw, label, pin_font)
        draw.text((px - tw / 2, py - 5), label, font=pin_font, fill=WHITE)


# --------------------------------------------------------------------------
# Page sections
# --------------------------------------------------------------------------

def section_top(draw, data: dict) -> int:
    """Red kicker, serif masthead, standfirst, numbers strip, region bar."""
    ed = data["edition"]
    y = 6
    right_f = font(SANS_BOLD, 11)
    rw = text_w(draw, ed["top_right"], right_f)
    draw.text((X1 - rw, y), ed["top_right"], font=right_f, fill=INK_SOFT)
    y += 15
    # Red kicker: the brand, letter-spaced, centred over the masthead.
    kicker = " ".join(list(ed["brand"].replace(" ", "\u2002")))
    kf = fit_font(draw, kicker, SANS_BOLD, 17, INNER)
    kw = text_w(draw, kicker, kf)
    draw.text(((SIZE - kw) / 2, y), kicker, font=kf, fill=RED)
    y += 23
    draw.line([(MARGIN, y), (X1, y)], fill=INK, width=2)
    y += 3
    # Masthead — the biggest element on the page, sized to the full measure.
    mast = fit_font(draw, ed["masthead"], SERIF_BOLD, 66, INNER)
    mw = text_w(draw, ed["masthead"], mast)
    draw.text(((SIZE - mw) / 2, y), ed["masthead"], font=mast, fill=INK)
    y += 72  # clearance for the serif cap height and descenders
    # Standfirst naming the three leads (and the market rout).
    strap = fit_font(draw, ed["strapline"], SERIF_ITALIC, 16, INNER)
    sw = text_w(draw, ed["strapline"], strap)
    draw.text(((SIZE - sw) / 2, y), ed["strapline"], font=strap, fill=RED)
    y += 20
    draw.line([(MARGIN, y), (X1, y)], fill=RULE, width=1)
    y += 4
    # Numbers strip: six big red serif numerals divided by hairlines.
    cell_w = INNER / 6
    big_f = font(SERIF_BOLD, 25)
    cap_f = font(SANS, 11)
    for i, cell in enumerate(data["numbers"]):
        cx = MARGIN + i * cell_w
        if i:
            draw.line([(cx - 5, y + 2), (cx - 5, y + 38)], fill=RULE, width=1)
        draw.text((cx, y), cell["big"], font=big_f, fill=RED)
        lines = wrap(draw, cell["caption"], cap_f, cell_w - 12)
        draw_lines(draw, lines[:2], cx, y + 24, cap_f, INK_SOFT, 11)
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
        lf = fit_font(draw, label, SANS_BOLD, 11, seg_w - 12, minimum=9)
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
    """The three lead stories, each with its full scene panel."""
    gap = 10
    col_w = (INNER - 2 * gap) / 3
    head_f = font(SERIF_BOLD, 24)
    kick_f = font(SANS_BOLD, 11)
    body_f = font(SANS, 13)
    bottom = y
    for i, lead in enumerate(data["leads"]):
        x = MARGIN + i * (col_w + gap)
        if i:
            draw.line([(x - gap / 2, y), (x - gap / 2, y + 230)], fill=RULE,
                      width=1)
        art_box = (int(x), y, int(x + col_w), y + LEAD_ART_H)
        LEAD_ART[lead["art"]](draw, art_box)
        cy = y + LEAD_ART_H + 5
        draw.text((x, cy), f'{lead["n"]}  {lead["kicker"]}', font=kick_f,
                  fill=RED)
        cy += 15
        lines = wrap(draw, lead["headline"], head_f, col_w)
        cy = draw_lines(draw, lines, x, cy, head_f, INK, 25)
        cy += 1
        caption = f'{lead["caption"]} ({lead["source"]})'
        lines = wrap(draw, caption, body_f, col_w)
        cy = draw_lines(draw, lines, x, cy, body_f, INK_SOFT, 13)
        bottom = max(bottom, cy)
    y = bottom + 2
    draw.line([(MARGIN, y), (X1, y)], fill=RULE, width=1)
    return y + 3


def section_features(draw, data: dict, y: int) -> int:
    """Ten feature cards in two rows of five, each fully illustrated."""
    gap = 8
    col_w = (INNER - 4 * gap) / 5
    head_f = font(SANS_BOLD, 16)
    body_f = font(SANS, 13)
    for row in range(2):
        row_bottom = y
        for col in range(5):
            feat = data["features"][row * 5 + col]
            x = MARGIN + col * (col_w + gap)
            if col:
                draw.line([(x - gap / 2, y), (x - gap / 2, y + 140)], fill=RULE,
                          width=1)
            art_box = (int(x), y, int(x + col_w), y + FEAT_ART_H)
            FEAT_ART[feat["icon"]](draw, art_box)
            kick = f'{feat["n"]} · {feat["kicker"]}'
            kf = fit_font(draw, kick, SANS_BOLD, 10, col_w, minimum=8)
            draw.text((x, y + FEAT_ART_H + 3), kick, font=kf, fill=RED)
            cy = y + FEAT_ART_H + 14
            lines = wrap(draw, feat["headline"], head_f, col_w)
            cy = draw_lines(draw, lines, x, cy, head_f, INK, 16)
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
    """Solid world map (left) and the 25 one-line briefs (right)."""
    map_w = 348
    head_f = font(SANS_BOLD, 14)
    draw.text((MARGIN, y), "WHERE IT HAPPENED", font=head_f, fill=INK)
    draw.text((MARGIN, y + 15), "Pins 1-13: the leads and features above",
              font=font(SANS_ITALIC, 11), fill=INK_SOFT)
    draw_map(draw, (MARGIN, y + 30, MARGIN + map_w, y + 176), data["pins"])
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
        yy = y + 33 + row * 12.2
        draw.text((x, yy), f'{brief["n"]}', font=num_f, fill=RED)
        nx = x + text_w(draw, f'{brief["n"]}', num_f) + 4
        draw.text((nx, yy), brief["place"], font=place_f, fill=INK)
        px = nx + text_w(draw, brief["place"], place_f) + 4
        # One line only: shrink just this line if it would spill over.
        bf = fit_font(draw, brief["text"], SANS, 12, x + col_w - px, minimum=9)
        draw.text((px, yy), brief["text"], font=bf, fill=INK_SOFT)
    return y + 190


def section_close(draw, data: dict, y: int) -> int:
    """Date-check box and the attribution footer."""
    dc = data["date_check"]
    box = (MARGIN, y, X1, y + 36)
    draw.rectangle(box, outline=RED, width=2)
    draw.rectangle([MARGIN, y, MARGIN + 104, y + 36], fill=RED)
    draw.text((MARGIN + 10, y + 4), "DATE", font=font(SANS_BOLD, 14), fill=WHITE)
    draw.text((MARGIN + 10, y + 20), "CHECK", font=font(SANS_BOLD, 14),
              fill=WHITE)
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
    draw.text(((SIZE - sw) / 2, y), ed["footer_sources"], font=src_f,
              fill=INK_SOFT)
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
