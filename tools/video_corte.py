#!/usr/bin/env python3
"""Post del video de recintos de Casa Lingue (modo --vista corte de casa_lingue_3d.py).

1. Rotula los recintos sobre los cuadros 3D (posiciones en rotulos.json) y titula cada piso.
2. Calza la planta del 1er piso sobre la vista cenital final y funde de 3D a plano.
3. Arma la lámina final: plantas 1er y 2do piso, superficies y logo.

Marca Neorigen: Azul Origen, Niebla, Verde Pino y Madera; Fraunces (títulos), Work Sans (textos y
rótulos) e IBM Plex Mono (datos y rótulos en mayúsculas), en assets/fuentes/ (instancias estáticas
generadas con tools/instanciar_fuentes.py).

Uso: python3 tools/video_corte.py <cuadros_3d> <salida_cuadros> [planta.png] [--sin-textos]
                                   [--papel azul] [--hold N] [--vuelta cuadro_3d.png]
  --sin-textos: sin rótulos, sin título por piso y sin textos ni logo en la lámina (para editar el reel).
  --papel azul: planta en líneas Niebla sobre Azul Origen (como la lámina del reel).
  --vuelta: después de la lámina fija, la planta vuelve a calzarse sobre la casa y se funde con ese
            cuadro 3D (el primero del conector c3 de casa_lingue_3d.py --vista reel).
Luego: VIGNETA_HASTA=11 LOOK=dia tools/armar_video.sh <salida_cuadros> output/casa_lingue_recintos.mp4 24
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

OPC = {"--papel": "niebla", "--hold": None, "--vuelta": None}
ARGS, _argv = [], sys.argv[1:]
while _argv:
    a = _argv.pop(0)
    if a in OPC:
        OPC[a] = _argv.pop(0)
    elif not a.startswith("--"):
        ARGS.append(a)
SIN_TEXTOS = "--sin-textos" in sys.argv
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC, OUT = ARGS[0], ARGS[1]
PLAN = ARGS[2] if len(ARGS) > 2 else os.path.join(ROOT, "assets", "plano", "planta_lingue_superficies.png")
LOGO_PNG = os.path.join(ROOT, "assets", "marca", "LOGO_FINAL_NEORIGEN-02.png")
FUENTES = os.path.join(ROOT, "assets", "fuentes")
TRANS, LAYOUT, HOLD = 24, 48, 84         # cuadros: fundido a plano, paso a lámina, lámina fija
if OPC["--hold"]:
    HOLD = int(OPC["--hold"])
K = 6623 / 2000                          # px de la planta (200 dpi) por px de las cotas medidas
# recortes en la planta (medidos a 2000 px de ancho)
CROP1 = (190, 200, 700, 1140)            # 1er piso (incluye escalera de la terraza)
CROP2 = (812, 200, 1322, 1140)           # 2do piso
DECK_L, DECK_R, DECK_FRONT = 207, 636, 1125   # bordes del deck en la planta (1er piso)

# marca Neorigen
AZUL = (1, 30, 47)          # Azul Origen #011E2F
NIEBLA = (241, 244, 243)    # Niebla #F1F4F3
PINO = (60, 74, 62)         # Verde Pino #3C4A3E
MADERA = (169, 118, 74)     # Madera #A9764A
PAPEL, TINTA = (AZUL, NIEBLA) if OPC["--papel"] == "azul" else (NIEBLA, AZUL)
MARGEN = 56
NOMBRES = {"Walk-in closet": "Walking closet", "Living-comedor": "Estar comedor"}   # nombres de neorigen.cl


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


_fuentes = {}


def font(nombre, size):
    """nombre: 'titulo' (Fraunces), 'texto' / 'texto-medio' (Work Sans), 'mono' (IBM Plex Mono Medium)."""
    archivo = {"titulo": "Fraunces-Titulo.ttf", "texto": "WorkSans-Regular.ttf",
               "texto-medio": "WorkSans-Medium.ttf", "mono": "IBMPlexMono-Medium.ttf"}[nombre]
    if (archivo, size) not in _fuentes:
        _fuentes[archivo, size] = ImageFont.truetype(os.path.join(FUENTES, archivo), size)
    return _fuentes[archivo, size]


def rgba(col, a):
    return (*col, int(round(255 * a)))


def crop(im, box):
    return im.crop(tuple(int(v * K) for v in box))


def entintar(gris):
    """Planta en grises -> líneas en TINTA sobre PAPEL (tinta = 1 - luminancia)."""
    tinta = ImageOps.invert(gris)
    return Image.composite(Image.new("RGB", gris.size, TINTA), Image.new("RGB", gris.size, PAPEL), tinta)


def _curva_extremos():
    """Pie y hombro suaves: 0..40 -> 18..40 y 230..255 -> 230..244; el resto no cambia."""
    v = np.arange(256, dtype=float)
    lut = np.where(v < 40, 18 + v * (40 - 18) / 40, v)
    lut = np.where(v > 230, 230 + (v - 230) * (244 - 230) / 25, lut)
    return np.round(lut).astype(np.uint8)


CURVA = _curva_extremos()


def sin_extremos(im):
    """Sin negro ni blanco puros, también tras el look del video (contraste y viñeta de armar_video.sh):
    solo toca sombras profundas (CN900) y brillos del render."""
    a = np.asarray(im).copy()
    a[..., :3] = CURVA[a[..., :3]]
    return Image.fromarray(a)


def pill(xy, text, alpha, size=22):
    """Rótulo: cápsula Azul Origen (88 %) con texto Niebla y punto de anclaje Niebla con borde Madera."""
    f = font("texto-medio", size)
    x, y = xy
    tw = f.getlength(text)
    pad, h = 12, size + 14
    layer = Image.new("RGBA", BASE_SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x - tw / 2 - pad, y - h - 10, x + tw / 2 + pad, y - 10), radius=4,
                        fill=rgba(AZUL, 0.88 * alpha))
    d.text((x, y - h / 2 - 10), text, font=f, fill=rgba(NIEBLA, alpha), anchor="mm")
    d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=rgba(NIEBLA, alpha), outline=rgba(MADERA, alpha), width=2)
    return layer


def gradiente_superior():
    """Degradado Azul Origen: 92 % en el borde superior a 0 % en y = 520."""
    g = Image.new("L", (1, 520))
    for yy in range(520):
        g.putpixel((0, yy), int(round(255 * 0.92 * (1 - yy / 519))))
    return g.resize((W, 520))


def title(rotulo, titulo, bajada, alpha):
    """Título por piso: bloque a la izquierda sobre el degradado superior."""
    layer = Image.new("RGBA", BASE_SIZE, (0, 0, 0, 0))
    grad = Image.new("RGBA", (W, 520), (*AZUL, 255))
    grad.putalpha(GRAD.point(lambda v: int(v * alpha)))
    layer.paste(grad, (0, 0))
    d = ImageDraw.Draw(layer)
    d.text((MARGEN, 150), rotulo, font=font("mono", 20), fill=rgba(NIEBLA, alpha), anchor="la")
    d.text((MARGEN, 254), titulo, font=font("titulo", 64), fill=rgba(NIEBLA, alpha), anchor="ls")
    d.rectangle((MARGEN, 278, MARGEN + 63, 281), fill=rgba(MADERA, alpha))
    d.text((MARGEN, 304), bajada, font=font("texto", 22), fill=rgba(NIEBLA, alpha), anchor="la")
    return layer


def alpha_win(f, a0, a1, b0, b1):
    """0 -> 1 entre a0..a1, 1 -> 0 entre b0..b1."""
    return min(ease((f - a0) / max(a1 - a0, 1)), 1 - ease((f - b0) / max(b1 - b0, 1)))


os.makedirs(OUT, exist_ok=True)
meta = json.load(open(os.path.join(SRC, "rotulos.json")))
frames = sorted(p for p in os.listdir(SRC) if p.endswith(".png") and p.startswith("f_"))
n3d = len(frames)
BASE_SIZE = Image.open(os.path.join(SRC, frames[0])).size
W, H = BASE_SIZE
GRAD = gradiente_superior()
STAGES = {"alto": (100, 116, 150, 160), "bajo": (198, 214, n3d - 10, n3d)}
TITULOS = {"alto": ("2DO PISO", "Dormitorio en suite", "Baño y walking closet"),
           "bajo": ("1ER PISO", "Estar comedor", "Cocina integrada y lavadero")}

# 1) cuadros 3D rotulados
for i, name in enumerate(frames):
    im = sin_extremos(Image.open(os.path.join(SRC, name)).convert("RGBA"))
    row = meta["frames"][min(i, len(meta["frames"]) - 1)]
    for nivel, (a0, a1, b0, b1) in STAGES.items():
        a = alpha_win(i, a0, a1, b0, b1)
        if a <= 0 or SIN_TEXTOS:
            continue
        im = Image.alpha_composite(im, title(*TITULOS[nivel], a))
        for label, (u, v, lv) in row.items():
            if lv == nivel and 0 < u < 1 and 0 < v < 1:
                im = Image.alpha_composite(im, pill((u * W, v * H), NOMBRES.get(label, label), a))
    sin_extremos(im.convert("RGB")).save(os.path.join(OUT, f"c_{i + 1:04d}.png"))

# 2) planta calzada sobre la cenital y fundido 3D -> plano
plan = Image.open(PLAN).convert("L")
p1, p2 = crop(plan, CROP1), crop(plan, CROP2)             # en grises; se entintan ya escaladas
# logo oficial (trazos claros sobre Azul Origen) -> trazos Azul Origen sobre transparente, 220 px de ancho
lg = Image.open(LOGO_PNG).convert("L")
fondo = sorted(lg.getcolors(1 << 16))[-1][1]                   # luminancia del fondo azul del archivo
lg = lg.point(lambda v: max(0, min(255, round((v - fondo) * 255 / (255 - fondo)))))
lg = lg.crop(lg.point(lambda v: 255 if v > 128 else 0).getbbox())
lg = lg.resize((220, round(lg.height * 220 / lg.width)), Image.LANCZOS)
LOGO_MASK = lg
dk = meta["deck"]
fl, fr = dk["frente_izq"], dk["frente_der"]
s_al = (fr[0] - fl[0]) * W / ((DECK_R - DECK_L) * K)          # escala planta -> pantalla
ax = fl[0] * W - (DECK_L - CROP1[0]) * K * s_al                # esquina sup. izq. del recorte
ay = fl[1] * H - (DECK_FRONT - CROP1[1]) * K * s_al
last = sin_extremos(Image.open(os.path.join(SRC, frames[-1])).convert("RGB"))


def paper(rect1, a2, a_txt):
    """Lámina: papel Niebla, 1er piso en rect1 (x, y, escala), 2do piso y textos con alpha."""
    canvas = Image.new("RGB", BASE_SIZE, PAPEL)
    x, y, sc = rect1
    a = entintar(p1.resize((int(p1.width * sc), int(p1.height * sc)), Image.LANCZOS))
    canvas.paste(a, (int(x), int(y)))
    if a2 > 0:
        b = entintar(p2.resize((int(p2.width * sc), int(p2.height * sc)), Image.LANCZOS))
        bx = W - 20 - b.width + int((1 - a2) * 120)
        layer = Image.new("RGB", BASE_SIZE, PAPEL)
        layer.paste(b, (bx, int(y)))
        mask = Image.new("L", BASE_SIZE, 0)
        ImageDraw.Draw(mask).rectangle((bx, int(y), bx + b.width, int(y) + b.height), fill=int(255 * a2))
        canvas = Image.composite(layer, canvas, mask)
    if a_txt > 0 and not SIN_TEXTOS:
        dy = (1 - a_txt) * 12                                   # los textos suben 12 px al entrar
        t = Image.new("RGBA", BASE_SIZE, (0, 0, 0, 0))
        d = ImageDraw.Draw(t)
        ink = rgba(TINTA, a_txt)
        d.text((MARGEN, 40 + dy), "PLANTAS DE ARQUITECTURA", font=font("mono", 18), fill=rgba(PINO, a_txt),
               anchor="la")
        d.text((MARGEN, 122 + dy), "Casa Lingue", font=font("titulo", 56), fill=ink, anchor="ls")
        yb = y + p1.height * sc + 22 + dy
        d.text((20 + p1.width * sc / 2, yb), "1ER PISO", font=font("mono", 18), fill=ink, anchor="mm")
        d.text((W - 20 - p2.width * sc / 2, yb), "2DO PISO", font=font("mono", 18), fill=ink, anchor="mm")
        rows = (("Superficie útil", "57,39 m²"), ("Terrazas", "29,07 m²"), ("Total construido", "86,46 m²"))
        ty = yb + 70
        for k, (lab, val) in enumerate(rows):
            yy = ty + k * 52
            if k == 2:
                d.rectangle((MARGEN, yy - 27, MARGEN + 63, yy - 24), fill=rgba(MADERA, a_txt))
            d.text((MARGEN, yy), lab, font=font("texto-medio" if k == 2 else "texto", 22), fill=ink, anchor="lm")
            d.text((W - MARGEN, yy), val, font=font("mono", 22), fill=ink, anchor="rm")
            if k == 0:
                d.line((MARGEN, yy + 26, W - MARGEN, yy + 26), fill=rgba(TINTA, 0.2 * a_txt), width=1)
        logo = Image.new("RGBA", LOGO_MASK.size, (*TINTA, 255))
        logo.putalpha(LOGO_MASK.point(lambda v: int(v * a_txt)))
        t.alpha_composite(logo, (MARGEN, int(H - MARGEN - logo.height + dy)))
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
if OPC["--vuelta"]:  # la planta vuelve a calzarse sobre la casa y se funde con el 3D
    base = sin_extremos(Image.open(OPC["--vuelta"]).convert("RGB"))
    for k in reversed(range(LAYOUT)):
        t = ease(k / (LAYOUT - 1))
        rect = (ax + (20 - ax) * t, ay + (y_fin - ay) * t, s_al + (sc_fin - s_al) * t)
        n += 1
        paper(rect, ease((k - 12) / 30), ease((k - 24) / 24)).save(os.path.join(OUT, f"c_{n:04d}.png"))
    for k in reversed(range(TRANS)):
        n += 1
        Image.blend(base, paper((ax, ay, s_al), 0, 0), ease(k / (TRANS - 1))).save(os.path.join(OUT, f"c_{n:04d}.png"))
print("cuadros:", n)
