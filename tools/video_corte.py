#!/usr/bin/env python3
"""Post del video de recintos de Casa Lingue (modo --vista corte de casa_lingue_3d.py).

1. Rotula los recintos sobre los cuadros 3D (posiciones en rotulos.json).
2. Calza la planta del 1er piso sobre la vista cenital final y funde de 3D a plano.
3. Arma la lámina final: plantas 1er y 2do piso, superficies y logo.

Uso: python3 tools/video_corte.py <cuadros_3d> <salida_cuadros> [planta.png]
Luego: LOOK=dia tools/armar_video.sh <salida_cuadros> output/casa_lingue_recintos.mp4 24
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC, OUT = sys.argv[1], sys.argv[2]
PLAN = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), "..", "assets", "plano",
                                                           "planta_lingue_superficies.png")
FONT = "/usr/share/fonts/opentype/inter/Inter-{}.otf"
TRANS, LAYOUT, HOLD = 24, 48, 84         # cuadros: fundido a plano, paso a lámina, lámina fija
K = 6623 / 2000                          # px de la planta (200 dpi) por px de las cotas medidas
# recortes en la planta (medidos a 2000 px de ancho)
CROP1 = (190, 200, 700, 1140)            # 1er piso (incluye escalera de la terraza)
CROP2 = (812, 200, 1322, 1140)           # 2do piso
LOGO = (28, 1295, 335, 1390)
DECK_L, DECK_R, DECK_FRONT = 207, 636, 1125   # bordes del deck en la planta (1er piso)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def font(style, size):
    return ImageFont.truetype(FONT.format(style), size)


def crop(im, box):
    return im.crop(tuple(int(v * K) for v in box))


def pill(draw_im, xy, text, alpha, size=22):
    """Rótulo: texto blanco sobre cápsula oscura translúcida, con un punto."""
    if alpha <= 0:
        return
    f = font("Medium", size)
    x, y = xy
    tw = draw_im.textlength(text, font=f) if hasattr(draw_im, "textlength") else f.getlength(text)
    pad, h = 12, size + 14
    layer = Image.new("RGBA", BASE_SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x - tw / 2 - pad, y - h - 10, x + tw / 2 + pad, y - 10), radius=h / 2,
                        fill=(20, 22, 20, int(170 * alpha)))
    d.text((x, y - h / 2 - 10), text, font=f, fill=(255, 255, 255, int(255 * alpha)), anchor="mm")
    d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 255, 255, int(255 * alpha)),
              outline=(20, 22, 20, int(200 * alpha)), width=2)
    return layer


def title(layer_size, text, sub, alpha):
    layer = Image.new("RGBA", layer_size, (0, 0, 0, 0))
    if alpha <= 0:
        return layer
    d = ImageDraw.Draw(layer)
    w = layer_size[0]
    sh = Image.new("RGBA", layer_size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    for dd, col in ((ds, (0, 0, 0, int(140 * alpha))), (d, (255, 255, 255, int(255 * alpha)))):
        off = 2 if dd is ds else 0
        dd.text((w / 2 + off, 78 + off), text, font=font("SemiBold", 40), fill=col, anchor="mm")
        dd.text((w / 2 + off, 120 + off), sub, font=font("Light", 22), fill=col, anchor="mm")
    sh = sh.filter(ImageFilter.GaussianBlur(3))
    return Image.alpha_composite(sh, layer)


def alpha_win(f, a0, a1, b0, b1):
    """0 -> 1 entre a0..a1, 1 -> 0 entre b0..b1."""
    return min(ease((f - a0) / max(a1 - a0, 1)), 1 - ease((f - b0) / max(b1 - b0, 1)))


os.makedirs(OUT, exist_ok=True)
meta = json.load(open(os.path.join(SRC, "rotulos.json")))
frames = sorted(p for p in os.listdir(SRC) if p.endswith(".png") and p.startswith("f_"))
n3d = len(frames)
BASE_SIZE = Image.open(os.path.join(SRC, frames[0])).size
W, H = BASE_SIZE
STAGES = {"alto": (100, 116, 150, 160), "bajo": (198, 214, n3d - 10, n3d)}
SUBT = {"alto": ("2do piso", "dormitorio · baño · walk-in closet"),
        "bajo": ("1er piso", "living-comedor · cocina · lavadero")}

# 1) cuadros 3D rotulados
for i, name in enumerate(frames):
    im = Image.open(os.path.join(SRC, name)).convert("RGBA")
    row = meta["frames"][min(i, len(meta["frames"]) - 1)]
    for nivel, (a0, a1, b0, b1) in STAGES.items():
        a = alpha_win(i, a0, a1, b0, b1)
        if a <= 0:
            continue
        im = Image.alpha_composite(im, title(BASE_SIZE, SUBT[nivel][0].upper(), SUBT[nivel][1], a))
        for label, (u, v, lv) in row.items():
            if lv == nivel and 0 < u < 1 and 0 < v < 1:
                im = Image.alpha_composite(im, pill(ImageDraw.Draw(im), (u * W, v * H), label, a))
    im.convert("RGB").save(os.path.join(OUT, f"c_{i + 1:04d}.png"))

# 2) planta calzada sobre la cenital y fundido 3D -> plano
plan = Image.open(PLAN).convert("RGB")
p1, p2, logo = crop(plan, CROP1), crop(plan, CROP2), crop(plan, LOGO)
dk = meta["deck"]
fl, fr = dk["frente_izq"], dk["frente_der"]
s_al = (fr[0] - fl[0]) * W / ((DECK_R - DECK_L) * K)          # escala planta -> pantalla
ax = fl[0] * W - (DECK_L - CROP1[0]) * K * s_al                # esquina sup. izq. del recorte
ay = fl[1] * H - (DECK_FRONT - CROP1[1]) * K * s_al
last = Image.open(os.path.join(SRC, frames[-1])).convert("RGB")


def paper(rect1, a2, a_txt, bg_alpha=1.0, base=None):
    """Lámina: fondo blanco, 1er piso en rect1 (x, y, escala), 2do piso y textos con alpha."""
    canvas = Image.new("RGB", BASE_SIZE, (255, 255, 255))
    if base is not None and bg_alpha < 1:
        canvas = Image.blend(base, canvas, bg_alpha)
    x, y, sc = rect1
    a = p1.resize((int(p1.width * sc), int(p1.height * sc)), Image.LANCZOS)
    canvas.paste(a, (int(x), int(y)))
    if a2 > 0:
        b = p2.resize((int(p2.width * sc), int(p2.height * sc)), Image.LANCZOS)
        bx = W - 20 - b.width + int((1 - a2) * 120)
        layer = Image.new("RGB", BASE_SIZE, (255, 255, 255))
        layer.paste(b, (bx, int(y)))
        mask = Image.new("L", BASE_SIZE, 0)
        ImageDraw.Draw(mask).rectangle((bx, int(y), bx + b.width, int(y) + b.height), fill=int(255 * a2))
        canvas = Image.composite(layer, canvas, mask)
    if a_txt > 0:
        t = Image.new("RGBA", BASE_SIZE, (0, 0, 0, 0))
        d = ImageDraw.Draw(t)
        ink = (30, 32, 34, int(255 * a_txt))
        d.text((W / 2, 70), "C A S A   L I N G U E", font=font("Light", 38), fill=ink, anchor="mm")
        d.text((W / 2, 112), "plantas de arquitectura", font=font("Light", 20), fill=(90, 90, 90, int(255 * a_txt)),
               anchor="mm")
        yb = y + p1.height * sc + 18
        d.text((20 + p1.width * sc / 2, yb), "1er piso", font=font("Medium", 22), fill=ink, anchor="mm")
        d.text((W - 20 - p2.width * sc / 2, yb), "2do piso", font=font("Medium", 22), fill=ink, anchor="mm")
        rows = (("Superficie útil", "57,39 m²"), ("Terrazas", "29,07 m²"), ("Total construido", "86,46 m²"))
        ty = yb + 60
        for k, (lab, val) in enumerate(rows):
            yy = ty + k * 42
            bold = k == 2
            d.text((W / 2 - 170, yy), lab, font=font("SemiBold" if bold else "Regular", 24), fill=ink, anchor="lm")
            d.text((W / 2 + 170, yy), val, font=font("SemiBold" if bold else "Regular", 24), fill=ink, anchor="rm")
            if k < 2:
                d.line((W / 2 - 170, yy + 21, W / 2 + 170, yy + 21), fill=(180, 180, 180, int(255 * a_txt)), width=1)
        lg = logo.resize((int(logo.width * 0.28), int(logo.height * 0.28)), Image.LANCZOS).convert("RGBA")
        lg.putalpha(int(255 * a_txt))
        t.paste(lg, (int(W / 2 - lg.width / 2), H - lg.height - 40), lg)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), t).convert("RGB")
    return canvas


n = n3d
sc_fin = (W / 2 - 30) / p1.width
y_fin = 150
for k in range(TRANS):  # fundido: la planta aparece exactamente sobre la casa
    a = ease(k / (TRANS - 1))
    img = Image.blend(last, paper((ax, ay, s_al), 0, 0), a)
    n += 1
    img.save(os.path.join(OUT, f"c_{n:04d}.png"))
for k in range(LAYOUT):  # la planta se acomoda a la izquierda y entra el 2do piso
    t = ease(k / (LAYOUT - 1))
    rect = (ax + (20 - ax) * t, ay + (y_fin - ay) * t, s_al + (sc_fin - s_al) * t)
    n += 1
    paper(rect, ease((k - 12) / 30), ease((k - 24) / 24)).save(os.path.join(OUT, f"c_{n:04d}.png"))
final = paper((20, y_fin, sc_fin), 1, 1)
for k in range(HOLD):
    n += 1
    final.save(os.path.join(OUT, f"c_{n:04d}.png"))
print("cuadros:", n)
