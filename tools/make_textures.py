#!/usr/bin/env python3
"""Genera texturas con transparencia para la vegetación (ramitas con agujas, hojas).

Uso: python3 tools/make_textures.py <carpeta_salida>
"""
import math
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1]
random.seed(3)


def green(base, var=0.18):
    r, g, b = base
    k = 1 + random.uniform(-var, var)
    return (int(min(255, r * k)), int(min(255, g * k)), int(min(255, b * k)), 255)


def sprig(name, needle_len, spacing, base, twig_color, density_side=2, curve=0.05, size=(512, 1024)):
    """Ramita vista desde arriba: eje central y agujas a ambos lados."""
    w, h = size
    im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    W, H = w * 2, h * 2
    cx = W / 2

    def axis_x(y):
        return cx + math.sin(y / H * math.pi) * W * curve

    # ramitas laterales secundarias
    branches = [(0, H * 0.04, H * 0.98, 0)]
    for k in range(5):
        y0 = H * (0.2 + 0.14 * k)
        side = -1 if k % 2 else 1
        branches.append((side, y0, y0 + H * 0.35, side))
    for side, y0, y1, _ in branches:
        pts = []
        steps = 60
        for i in range(steps + 1):
            t = i / steps
            y = y0 + (y1 - y0) * t
            if side == 0:
                x = axis_x(y)
            else:
                x = axis_x(y0) + side * t * W * 0.28
                y = y0 + (y1 - y0) * t * 0.75
            pts.append((x, y))
        # agujas
        n = int(math.dist(pts[0], pts[-1]) / spacing)
        for i in range(n):
            t = i / max(n - 1, 1)
            px, py = pts[int(t * steps)]
            nx, ny = pts[min(int(t * steps) + 1, steps)]
            ang = math.atan2(ny - py, nx - px)
            taper = 0.55 + 0.45 * math.sin(min(1, t * 1.15) * math.pi * 0.9 + 0.1)
            for s in (-1, 1):
                for _ in range(density_side):
                    a = ang + s * math.radians(random.uniform(50, 80))
                    L = needle_len * taper * random.uniform(0.75, 1.1) * (0.8 if side else 1.0)
                    ex, ey = px + math.cos(a) * L, py + math.sin(a) * L
                    col = green(base)
                    d.line([(px, py), (ex, ey)], fill=col, width=random.choice((5, 6, 7)))
                    # brillo en la punta
                    d.line([((px + ex) / 2, (py + ey) / 2), (ex, ey)],
                           fill=green((base[0] * 1.35, base[1] * 1.3, base[2] * 1.2)), width=3)
        d.line(pts, fill=twig_color, width=9 if side == 0 else 6)
    im = im.resize((w, h), Image.LANCZOS)
    im.save(f"{OUT}/{name}.png")


def broad_leaf(name, base, size=512):
    W = size * 2
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    for i in range(80):
        t = i / 79 * math.pi * 2
        r = math.sin(t / 2) ** 0.8
        x = W / 2 + math.sin(t) * W * 0.32 * (0.6 + 0.4 * math.sin(t / 2))
        y = W * 0.06 + (1 - math.cos(t / 2) * 0 - (math.cos(t) * 0.5 + 0.5)) * W * 0.88
        pts.append((x, y))
    d.polygon(pts, fill=base + (255,))
    mask = im.getchannel("A")
    # nervaduras (recortadas por la silueta de la hoja)
    vein = tuple(min(255, int(c * 1.35)) for c in base) + (255,)
    d.line([(W / 2, W * 0.06), (W / 2, W * 0.94)], fill=vein, width=10)
    for k in range(7):
        y = W * (0.2 + 0.1 * k)
        for s in (-1, 1):
            d.line([(W / 2, y), (W / 2 + s * W * 0.22, y - W * 0.1)], fill=vein, width=5)
    im.putalpha(mask)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    im = im.resize((size, size), Image.LANCZOS)
    im.save(f"{OUT}/{name}.png")


sprig("abeto_ramita", needle_len=52, spacing=5, density_side=3, base=(38, 66, 30), twig_color=(70, 52, 34, 255))
sprig("pino_ramita", needle_len=120, spacing=10, base=(52, 78, 36), twig_color=(88, 64, 40, 255), density_side=3,
      curve=0.02)
broad_leaf("hoja", (58, 88, 30))
broad_leaf("hoja_seca", (120, 104, 46))
print("ok")
