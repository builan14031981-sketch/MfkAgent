# -*- coding: utf-8 -*-
"""Xuantong Gate (玄通·门) icon family generator for MFKagent.
Apple-style cool-white monochrome + single rebellion-red accent (#E5484D).
One source of truth -> SVG master + PNG previews + multi-size .ico.
Render: numpy 2.5 + Pillow 12.3 (no external renderer needed).
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
S = 2048            # supersample canvas
F = 1024            # final size
ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
CX = CY = S // 2

# ---- palette ----
LIGHT_TOP = (243, 245, 248)
LIGHT_BOT = (216, 222, 232)
DARK_TOP  = (26, 30, 39)
DARK_BOT  = (12, 14, 19)
INK_ON_LIGHT = (44, 51, 66)
INK_ON_DARK  = (233, 237, 243)
RED = (229, 72, 77)          # E5484D
FAINT = (150, 158, 172)
RIM_LIGHT = (255, 255, 255)
RIM_DARK = (60, 68, 84)


def squircle_points(cx, cy, rx, ry, n=5.0, steps=360):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c = math.cos(t)
        s = math.sin(t)
        x = cx + rx * np.sign(c) * (abs(c) ** (2 / n))
        y = cy + ry * np.sign(s) * (abs(s) ** (2 / n))
        pts.append((float(x), float(y)))
    return pts


def vgrad(top, bot):
    t = np.linspace(0.0, 1.0, S, dtype=np.float32)[:, None]
    arr = np.zeros((S, S, 3), dtype=np.float32)
    for k in range(3):
        arr[:, :, k] = top[k] + (bot[k] - top[k]) * t
    return arr.astype(np.uint8)


def apply_mask(img_arr, mask):
    out = np.zeros_like(img_arr)
    out[mask] = img_arr[mask]
    return out


def container(bg, rim):
    """Filled squircle with vertical gradient + subtle rim, square canvas."""
    arr = vgrad(bg[0], bg[1])
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(squircle_points(CX, CY, 1000, 1000), fill=255)
    arr = apply_mask(arr, np.array(mask) > 0)
    img = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(img)
    # subtle inner rim for depth
    d.line(squircle_points(CX, CY, 992, 992), fill=rim, width=6, joint="curve")
    return img, d


def ring_arc(d, r, width, col, gap_center=None, gap_half=34):
    """Broken circle ring (enso). gap at top by default."""
    if gap_center is None:
        d.ellipse([CX - r, CY - r, CX + r, CY + r], outline=col, width=width)
    else:
        start = (gap_center + gap_half) % 360
        end = (gap_center - gap_half) % 360
        d.arc([CX - r, CY - r, CX + r, CY + r], start=start, end=end,
              fill=col, width=width)


def ring_squircle(d, r, width, col, gap_center=None, gap_half=34):
    pts = squircle_points(CX, CY, r, r, n=4.2)
    if gap_center is not None:
        def ang(p):
            a = math.degrees(math.atan2(p[1] - CY, p[0] - CX)) % 360
            # normalize distance from gap_center
            diff = (a - gap_center + 540) % 360 - 180
            return abs(diff) > gap_half
        pts = [p for p in pts if ang(p)]
    d.line(pts, fill=col, width=width, joint="curve")


def bar_v(d, width, height, col, top=None):
    top = CY - height // 2 if top is None else top
    d.rounded_rectangle([CX - width // 2, top, CX + width // 2, top + height],
                        radius=width // 2, fill=col)


def bar_h(d, width, length, col, left=None):
    left = CX - length // 2 if left is None else left
    d.rounded_rectangle([left, CY - width // 2, left + length, CY + width // 2],
                        radius=width // 2, fill=col)


def dot(d, r, col, x, y):
    d.ellipse([x - r, y - r, x + r, y + r], fill=col)


# ---------------------------------------------------------------------------
# Variant specs. Each: id, bg kind, ring, accent.
# bg: 'light' | 'dark' | 'mono'  (mono = single ink on transparent-ish white)
# ring: ('circle', r, w, gap_center|None) or ('squircle', r, w, gap_center|None)
# accent: ('bar_v', w, h, color, gap_bool) | ('bar_h',...) | ('dot', r, color, pos)
#         | ('arc_red', gap_center) | ('none',)
# ---------------------------------------------------------------------------

def specs():
    I = INK_ON_LIGHT
    W = INK_ON_DARK
    R = RED
    base_r, base_w = 560, 80
    out = []

    # 1 base: light, broken circle gap top, red vertical bar through gap
    out.append(("01_light_bar", "light", ("circle", base_r, base_w, 270),
                ("bar_v", base_w, 1500, R, True)))
    # 2 dark version of base
    out.append(("02_dark_bar", "dark", ("circle", base_r, base_w, 270),
                ("bar_v", base_w, 1500, R, True)))
    # 3 monochrome (no red): ink ring + ink bar
    out.append(("03_mono_ink", "light", ("circle", base_r, base_w, 270),
                ("bar_v", base_w, 1500, I, True)))
    # 4 light, full ring (no gap) + red bar (portal)
    out.append(("04_full_ring_red", "light", ("circle", base_r, base_w, None),
                ("bar_v", base_w, 1500, R, False)))
    # 5 dark, full ring white + red bar
    out.append(("05_dark_full", "dark", ("circle", base_r, base_w, None),
                ("bar_v", base_w, 1500, R, False)))
    # 6 light, double concentric ring + red bar
    out.append(("06_double_ring", "light", ("circle", base_r, base_w, 270),
                ("inner_ring", 380, 46, I, 270)))
    out[-1] = ("06_double_ring", "light",
               ("circle", base_r, base_w, 270),
               ("bar_v_double", base_w, 1500, R, True, 380, 46, I))
    # 7 light, squircle ring + red bar
    out.append(("07_squircle_ring", "light", ("squircle", base_r, base_w, 270),
                ("bar_v", base_w, 1500, R, True)))
    # 8 light, broken ring + red DOT at gap (spark)
    out.append(("08_red_spark", "light", ("circle", base_r, base_w, 270),
                ("dot", 70, R, CX, CY - base_r - 40)))
    # 9 dark, broken ring + red spark dot
    out.append(("09_dark_spark", "dark", ("circle", base_r, base_w, 270),
                ("dot", 70, R, CX, CY - base_r - 40)))
    # 10 light, broken ring + red ARC filling the gap
    out.append(("10_red_arc", "light", ("circle", base_r, base_w, 270),
                ("arc_red", 270)))
    # 11 light, thick ring + thin red bar
    out.append(("11_thick_thin", "light", ("circle", base_r, 130, 270),
                ("bar_v", 46, 1380, R, True)))
    # 12 light, thin ring + thick red bar
    out.append(("12_thin_thick", "light", ("circle", base_r, 42, 270),
                ("bar_v", 130, 1520, R, True)))
    # 13 light, gap at RIGHT, red bar vertical through gap
    out.append(("13_gap_right", "light", ("circle", base_r, base_w, 0),
                ("bar_v", base_w, 1500, R, True)))
    # 14 light, gap at BOTTOM, red bar
    out.append(("14_gap_bottom", "light", ("circle", base_r, base_w, 90),
                ("bar_v", base_w, 1500, R, True)))
    # 15 light, diagonal red bar (45) through gap-top
    out.append(("15_diag_bar", "light", ("circle", base_r, base_w, 270),
                ("bar_diag", base_w, 1500, R)))
    # 16 light, bar extends beyond ring (long line) red
    out.append(("16_long_line", "light", ("circle", base_r, base_w, 270),
                ("bar_v", 56, 1820, R, True)))
    # 17 dark, monochrome white ring + red bar, high contrast
    out.append(("17_dark_white", "dark", ("circle", base_r, base_w, 270),
                ("bar_v", base_w, 1500, R, True)))
    # 18 light, two nested gates (玄通) + red bar through both
    out.append(("18_two_gates", "light", ("circle", base_r, base_w, 270),
                ("bar_v_double", base_w, 1500, R, True, 360, 44, I)))
    # 19 light, enso with rotated gap (offset ends) + red bar
    out.append(("19_offset_enso", "light", ("circle", base_r, base_w, 225),
                ("bar_v", base_w, 1500, R, True)))
    # 20 light, ring + red bar + small tick marks (compass/portal)
    out.append(("20_portal_ticks", "light", ("circle", base_r, base_w, 270),
                ("bar_v", base_w, 1500, R, True)))
    out[-1] = ("20_portal_ticks", "light", ("circle", base_r, base_w, 270),
               ("bar_v_ticks", base_w, 1500, R, True, I))
    # 21 minimal: faint gray ring + bold red vertical line
    out.append(("21_minimal", "light", ("circle", base_r, 36, 270),
                ("bar_v", 60, 1500, R, True)))
    # 22 dark, faint ring + red bar (sparse, lonely)
    out.append(("22_dark_minimal", "dark", ("circle", base_r, 36, 270),
                ("bar_v", 60, 1500, R, True)))
    # 23 light, GATE motif: two ink posts + red crossbar (门)
    out.append(("23_gate", "light", ("gate", None, None, None),
                ("gate_red", I, R)))
    # 24 dark GATE
    out.append(("24_dark_gate", "dark", ("gate", None, None, None),
                ("gate_red", W, R)))
    # 25 light, ring + red bar + tiny red dot spark at top of bar
    out.append(("25_bar_spark", "light", ("circle", base_r, base_w, 270),
                ("bar_v_spark", base_w, 1500, R, True)))
    # 26 light, rounded-square ring (squircle) no gap + red bar (modern)
    out.append(("26_sq_full", "light", ("squircle", base_r, base_w, None),
                ("bar_v", base_w, 1500, R, False)))
    return out


def draw_spec(spec):
    name, bgk, ring, accent = spec
    if bgk == "light":
        img, d = container((LIGHT_TOP, LIGHT_BOT), RIM_LIGHT)
        ink = INK_ON_LIGHT
    elif bgk == "dark":
        img, d = container((DARK_TOP, DARK_BOT), RIM_DARK)
        ink = INK_ON_DARK
    else:
        img, d = container((LIGHT_TOP, LIGHT_BOT), RIM_LIGHT)
        ink = INK_ON_LIGHT

    r, w = (ring[1], ring[2]) if ring[0] != "gate" else (0, 0)
    gap = ring[3] if ring[0] != "gate" else None

    # ---- ring ----
    if ring[0] == "circle":
        ring_arc(d, r, w, ink, gap_center=gap)
    elif ring[0] == "squircle":
        ring_squircle(d, r, w, ink, gap_center=gap)
    elif ring[0] == "gate":
        # two vertical posts + top lintel (ink) -> a gateway
        pw = 86
        ph = 1180
        post_gap = 720
        lc = INK_ON_LIGHT if bgk != "dark" else INK_ON_DARK
        d.rounded_rectangle([CX - post_gap // 2 - pw, CY - ph // 2,
                             CX - post_gap // 2, CY + ph // 2],
                            radius=pw // 2, fill=lc)
        d.rounded_rectangle([CX + post_gap // 2, CY - ph // 2,
                             CX + post_gap // 2 + pw, CY + ph // 2],
                            radius=pw // 2, fill=lc)
        d.rounded_rectangle([CX - post_gap // 2 - pw, CY - ph // 2,
                             CX + post_gap // 2 + pw, CY - ph // 2 + pw],
                            radius=pw // 2, fill=lc)

    # ---- accent ----
    at = accent[0]
    if at == "bar_v":
        bar_v(d, accent[1], accent[2], accent[3])
    elif at == "bar_h":
        bar_h(d, accent[1], accent[2], accent[3])
    elif at == "dot":
        dot(d, accent[1], accent[2], accent[3], accent[4])
    elif at == "arc_red":
        ring_arc(d, r, w, RED, gap_center=accent[1])
    elif at == "bar_diag":
        d.line([(CX - 760, CY + 760), (CX + 760, CY - 760)], fill=accent[3],
               width=accent[1], joint="curve")
    elif at == "bar_v_double":
        # red bar + inner ink ring
        bar_v(d, accent[1], accent[2], accent[3])
        ring_arc(d, accent[5], accent[6], accent[7], gap_center=gap)
    elif at == "bar_v_ticks":
        bar_v(d, accent[1], accent[2], accent[3])
        for a in (0, 90, 180, 270):
            x = CX + (r + 70) * math.cos(math.radians(a))
            y = CY + (r + 70) * math.sin(math.radians(a))
            dot(d, 16, accent[5], int(x), int(y))
    elif at == "bar_v_spark":
        bar_v(d, accent[1], accent[2], accent[3])
        dot(d, 70, RED, CX, CY - accent[2] // 2)
    elif at == "gate_red":
        # red crossbar over the gate
        pw = 86
        post_gap = 720
        d.rounded_rectangle([CX - post_gap // 2 - pw, CY - 60,
                             CX + post_gap // 2 + pw, CY + 60],
                            radius=60, fill=RED)
    return img, name


def main():
    specs_list = specs()
    finals = []
    for spec in specs_list:
        img, name = draw_spec(spec)
        final = img.resize((F, F), Image.LANCZOS)
        png = os.path.join(OUT, name + ".png")
        ico = os.path.join(OUT, name + ".ico")
        final.save(png)
        final.save(ico, sizes=ICO_SIZES)
        finals.append((name, final))
        print("saved", name)

    # contact sheet: 6 columns
    cols = 6
    rows = math.ceil(len(finals) / cols)
    cell = 200
    pad = 16
    sheet = Image.new("RGB", (cols * (cell + pad) + pad,
                              rows * (cell + pad) + pad), (235, 238, 242))
    for i, (name, final) in enumerate(finals):
        thumb = final.resize((cell, cell), Image.LANCZOS)
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + pad)
        sheet.paste(thumb, (x, y))
    sheet.save(os.path.join(OUT, "preview_grid.png"))
    print("saved preview_grid.png with", len(finals), "icons")


if __name__ == "__main__":
    main()
