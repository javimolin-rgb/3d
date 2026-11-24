#!/usr/bin/env python3
"""Sección 4 del recorrido de Casa Roble: de la cenital con el techo cortado a la lámina de plantas.

Toma el último cuadro de s3p (la cenital con la que cierra el barrido del corte) y la lámina de
planta sin cotas, la calza encima con las esquinas que guarda el render en
`frames_roble/s3p/plano.json` y arma la transición:

  cenital quieta -> el entorno se funde a Azul Origen y aparece el 1er piso calzado sobre la casa
  -> pasa por el azul limpio a la lámina: **los dos pisos lado a lado**, como están dibujados, con
  el bloque de título y el rótulo de cada piso -> se queda ahí (es la pausa larga de la sección)
  -> vuelve a la planta calzada y a la cenital (empalma con el primer cuadro de s5).

Es la misma figura con la que cierran Casa Lingue (`tools/video_corte.py`, `paper()`) y Casa
Boldo: 1er piso a la izquierda, 2do entrando por la derecha, títulos y logo, papel Azul Origen y
líneas Niebla, porque la sección viene del fondo azul del recorrido.

**La planta no se gira** y los recintos no llevan cápsulas de rótulo. Es la decisión que se tomó
en Boldo y vale igual acá: con los dos pisos lado a lado el dibujo queda a poco más de un tercio
de la escala de la lámina, así que un rótulo de 22 px —el mínimo de marca a 720x1280— mide varios
metros de planta y se come la pieza que nombra. Quedan los nombres que el dibujo ya trae impresos,
de letra chica, y los recintos del 2do piso se señalan en la **pausa del barrido 3D** de s3p, que
para eso se queda tres segundos quieta en cada piso.

El paso de la planta calzada a la lámina **pasa por el azul limpio**, sin fundido cruzado: calzada
sobre la casa la planta está apaisada y en la lámina va vertical, y un cruce deja los dos dibujos
del mismo piso superpuestos en distinta orientación.

La lámina es **PNG**, bajada del sitio con `tools/get_planos_web.py`, así que se abre directo en
vez de rasterizar un PDF con `pdftoppm`, y el engrosado de líneas va con MinFilter(3) y no (9):
la del sitio está a una fracción de los 374 px/m de un PDF a 300 dpi, y con 9 las paredes saldrían
de doce centímetros.

Uso: python3 tools/plano_roble.py [frames_roble/s3p] [frames_roble/s4]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
S3 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "frames_roble", "s3p")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "frames_roble", "s4")
LAMINA = os.path.join(ROOT, "assets", "roble", "planta_sin_cotas.png")
FUENTES = os.path.join(ROOT, "assets", "fuentes")
LOGO_PNG = os.path.join(ROOT, "assets", "marca", "LOGO_FINAL_NEORIGEN-02.png")
L, D = 8.79, 16.81

# Calibración de cada piso dentro de la lámina: dónde cae el origen del modelo en píxeles de la
# imagen entera, la escala en píxeles por metro, y la ventana en metros que recorta el dibujo de
# ese piso dejando fuera la banda de marca, el otro piso y el rótulo de hoja.
#
# **Hay que calibrarlos contra el cenital de esta casa**, un piso por vez, y mirar el
# `calibracion_diag.png` que deja la herramienta:
#
#   FRANJA=0.12 python3 tools/calibrar_planta.py frames_roble/s3p \
#       assets/roble/planta_sin_cotas.png izq 8.79 16.81
#   FRANJA=0.12 python3 tools/calibrar_planta.py frames_roble/s3p \
#       assets/roble/planta_sin_cotas.png der 8.79 16.81
#
# FRANJA recorta la banda azul de marca, que es un bloque de tinta grande y sin estructura y le
# compite al dibujo en la correlación; en esta lámina (1400x1621) la banda termina cerca de la
# fila 175, de ahí el 0,12. A lo que imprime la herramienta hay que **sumarle lo recortado**: las
# filas de la franja, y 700 columnas en el caso del 2do piso, que vive en la mitad derecha.
#
# No heredar estos valores de Boldo ni de ninguna otra casa, ni medirlos a ojo: cada lámina tiene
# su escala y su encuadre, los dos dibujos de una misma lámina pueden no estar a la misma escala
# (en Boldo daban 76,8 y 79,1 px/m), y con los de otra casa el ajuste parece casi bien.
#
# La ventana en metros tiene que ser **la misma para los dos pisos**, para que los dos recortes
# salgan del mismo tamaño en metros y se muestren a la misma escala. El borde de abajo se mide
# contando tinta por fila, no a ojo: en Boldo el rótulo de hoja caía apenas debajo del porch y a
# ojo el corte se lo comía.
PISOS = {
    # piso: (PX0, PY0, PPM, MX0, MX1, MY0, MY1)  -- SIN CALIBRAR todavía
    "p1": None,
    "p2": None,
}
ROTULOS_PISO = {"p1": "PRIMER PISO", "p2": "SEGUNDO PISO"}
TITULO = ("PLANTAS DE ARQUITECTURA", "Casa Roble",
          "Tres dormitorios, escritorio y el testero vidriado mirando a la pista")
AZUL = np.array([1, 30, 47], float)          # Azul Origen #011E2F
NIEBLA = np.array([241, 244, 243], float)    # Niebla #F1F4F3
MADERA = (169, 118, 74)                      # Madera #A9764A
MARGEN = 56
BORDE, HUECO = 20, 20                        # margen y separación de las dos plantas en la lámina
Y_PLANTAS = 404                              # dónde arrancan los dibujos
# Cuadros: cenital quieta, fundido a la planta calzada, paso a la lámina, entrada del 2do piso,
# la pausa larga con los dos pisos, y la vuelta.
HOLD0, FADE1, CALZ, PASO, ENTRA, HOLD2, SALE, VUELTA, FADE_OUT = 24, 24, 18, 24, 30, 96, 20, 24, 18
N = HOLD0 + FADE1 + CALZ + PASO + ENTRA + HOLD2 + SALE + VUELTA + FADE_OUT


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


_fuentes = {}


def font(nombre, size):
    archivo = {"titulo": "Fraunces-Titulo.ttf", "texto": "WorkSans-Regular.ttf",
               "texto-medio": "WorkSans-Medium.ttf", "mono": "IBMPlexMono-Medium.ttf"}[nombre]
    if (archivo, size) not in _fuentes:
        _fuentes[archivo, size] = ImageFont.truetype(os.path.join(FUENTES, archivo), size)
    return _fuentes[archivo, size]


def rgba(col, a):
    return (*tuple(int(v) for v in col), int(round(255 * a)))


def entintar(gris):
    """Grises de la lámina -> líneas Niebla sobre Azul Origen."""
    ink = 1.0 - np.asarray(gris, float)[..., None] / 255.0
    return Image.fromarray(np.clip(AZUL * (1 - ink) + NIEBLA * ink, 0, 255).astype(np.uint8))


def main():
    if any(v is None for v in PISOS.values()):
        raise SystemExit(
            "plano_roble.py: faltan las constantes de PISOS.\n"
            "No se heredan de otra casa: cada lámina tiene su escala y su encuadre, y ésta trae\n"
            "los dos pisos, con lo que los valores de otra caen entre medio y el resultado parece\n"
            "casi bien. Calibrar contra el cenital de s3p, un piso por vez:\n"
            "  FRANJA=0.12 python3 tools/calibrar_planta.py frames_roble/s3p \\\n"
            "      assets/roble/planta_sin_cotas.png izq 8.79 16.81\n"
            "  FRANJA=0.12 python3 tools/calibrar_planta.py frames_roble/s3p \\\n"
            "      assets/roble/planta_sin_cotas.png der 8.79 16.81\n"
            "A lo que imprime hay que sumarle lo recortado: las filas de la franja de marca, y\n"
            "700 columnas para el piso de la derecha. Y hay que MIRAR calibracion_diag.png.")
    frames = sorted(f for f in os.listdir(S3) if f.startswith("f_") and f.endswith(".png"))
    base = Image.open(os.path.join(S3, frames[-1])).convert("RGB")
    W, H = base.size
    info = json.load(open(os.path.join(S3, "plano.json")))
    sx, sy = W / info["res"][0], H / info["res"][1]
    o, ex, ey = (np.array(info["pts"][k]) * (sx, sy) for k in ("o", "x", "y"))
    # afín metros -> pantalla: pantalla = o + (ex - o) * x / L + (ey - o) * y / D
    A = np.column_stack([(ex - o) / L, (ey - o) / D])
    Ainv = np.linalg.inv(A)
    ppm_scr = float(np.linalg.norm(ex - o)) / L
    lamina = Image.open(LAMINA).convert("L").filter(ImageFilter.MinFilter(3))

    def calzado():
        """El 1er piso deformado para caer exactamente sobre la casa de la cenital."""
        px0, py0, ppm, mx0, mx1, my0, my1 = PISOS["p1"]
        M = np.array([[ppm, 0], [0, -ppm]]) @ Ainv
        off = np.array([px0, py0]) - M @ o
        k = min(1.0, 2.0 * ppm_scr / ppm)                  # ~2 px de lámina por px de pantalla
        pl = lamina.resize((round(lamina.width * k), round(lamina.height * k)), Image.LANCZOS)
        Mk, offk = M * k, off * k
        w = pl.transform((W, H), Image.AFFINE,
                         (Mk[0, 0], Mk[0, 1], offk[0], Mk[1, 0], Mk[1, 1], offk[1]),
                         resample=Image.BICUBIC, fillcolor=255)
        ink = 1.0 - np.asarray(w, float)[..., None] / 255.0
        yy, xx = np.mgrid[0:H, 0:W]
        m = np.einsum("ij,jhw->ihw", Ainv, np.stack([xx - o[0], yy - o[1]]))
        dentro = ((m[0] > mx0) & (m[0] < mx1) & (m[1] > my0) & (m[1] < my1)).astype(float)[..., None]
        ink = ink * dentro
        return AZUL * (1 - ink) + NIEBLA * ink

    # Los dos pisos recortados de la lámina por su ventana en metros y llevados a la misma
    # escala: lado a lado entran a poco más de un tercio de la escala del dibujo original.
    ancho = (W - 2 * BORDE - HUECO) // 2
    recortes = {}
    for piso, (px0, py0, ppm, mx0, mx1, my0, my1) in PISOS.items():
        caja = (round(px0 + ppm * mx0), round(py0 - ppm * my1),
                round(px0 + ppm * mx1), round(py0 - ppm * my0))
        r = lamina.crop(caja)
        alto = round(r.height * ancho / r.width)
        recortes[piso] = entintar(r.resize((ancho, alto), Image.LANCZOS))
    alto = recortes["p1"].height
    X1, X2 = BORDE, W - BORDE - ancho

    lg = Image.open(LOGO_PNG).convert("L")                 # logo oficial: trazos claros sobre azul
    fondo = sorted(lg.getcolors(1 << 16))[-1][1]
    lg = lg.point(lambda v: max(0, min(255, round((v - fondo) * 255 / (255 - fondo)))))
    lg = lg.crop(lg.point(lambda v: 255 if v > 128 else 0).getbbox())
    lg = lg.resize((200, round(lg.height * 200 / lg.width)), Image.LANCZOS)

    def pagina(a2, a_txt):
        """La lámina: 1er piso a la izquierda, 2do entrando por la derecha, títulos y logo."""
        canvas = Image.new("RGB", (W, H), tuple(int(v) for v in AZUL))
        canvas.paste(recortes["p1"], (X1, Y_PLANTAS))
        if a2 > 0:
            bx = X2 + round((1 - a2) * 90)                 # entra deslizándose, como en Lingue
            capa = Image.new("RGB", (W, H), tuple(int(v) for v in AZUL))
            capa.paste(recortes["p2"], (bx, Y_PLANTAS))
            mask = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mask).rectangle((bx, Y_PLANTAS, bx + ancho, Y_PLANTAS + alto),
                                           fill=int(255 * a2))
            canvas = Image.composite(capa, canvas, mask)
        if a_txt > 0:
            dy = (1 - a_txt) * 12                          # los textos suben 12 px al entrar
            t = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(t)
            rotulo, titulo, bajada = TITULO
            d.text((MARGEN, 150 + dy), rotulo, font=font("mono", 20),
                   fill=rgba(NIEBLA, 0.8 * a_txt), anchor="la")
            d.text((MARGEN, 254 + dy), titulo, font=font("titulo", 64),
                   fill=rgba(NIEBLA, a_txt), anchor="ls")
            d.rectangle((MARGEN, 278 + dy, MARGEN + 63, 281 + dy), fill=rgba(MADERA, a_txt))
            d.text((MARGEN, 304 + dy), bajada, font=font("texto", 22),
                   fill=rgba(NIEBLA, a_txt), anchor="la")
            yb = Y_PLANTAS + alto + 34 + dy
            d.text((X1 + ancho / 2, yb), ROTULOS_PISO["p1"], font=font("mono", 22),
                   fill=rgba(NIEBLA, a_txt), anchor="mm")
            d.text((X2 + ancho / 2, yb), ROTULOS_PISO["p2"], font=font("mono", 22),
                   fill=rgba(NIEBLA, min(a_txt, a2)), anchor="mm")
            logo = Image.new("RGBA", lg.size, (*tuple(int(v) for v in NIEBLA), 255))
            logo.putalpha(lg.point(lambda v: int(v * a_txt)))
            t.alpha_composite(logo, (MARGEN, int(H - MARGEN - logo.height + dy)))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), t).convert("RGB")
        return np.asarray(canvas, float)

    render = np.asarray(base, float)
    calz = calzado()
    pag0 = pagina(0.0, 0.0)
    pag1 = pagina(1.0, 1.0)
    os.makedirs(OUT, exist_ok=True)
    # hitos del guion, en cuadros
    t1 = HOLD0                      # empieza el fundido a la planta calzada
    t2 = t1 + FADE1                 # planta calzada, completa
    t3 = t2 + CALZ                  # empieza el paso a la lámina
    t4 = t3 + PASO                  # lámina con el 1er piso en su sitio
    t5 = t4 + ENTRA                 # los dos pisos y los textos
    t6 = t5 + HOLD2                 # empieza la salida del 2do piso
    t7 = t6 + SALE                  # lámina con el 1er piso solo
    t8 = t7 + VUELTA                # planta calzada de nuevo

    for f in range(N):
        if f < t1:
            img = render
        elif f < t2:
            a = smooth((f - t1) / FADE1)
            img = render * (1 - a) + calz * a
        elif f < t3:
            img = calz
        elif f < t4:
            # el paso pasa por el azul limpio, no funde una planta en la otra: calzada sobre la
            # casa la planta está apaisada y en la lámina va vertical, así que un fundido cruzado
            # deja los dos dibujos del mismo piso superpuestos en distinta orientación
            a = (f - t3) / PASO
            img = (calz * (1 - smooth(2 * a)) + AZUL * smooth(2 * a) if a < 0.5 else
                   AZUL * (1 - smooth(2 * a - 1)) + pag0 * smooth(2 * a - 1))
        elif f < t5:
            a2 = smooth((f - t4) / ENTRA)
            img = pagina(a2, smooth((f - t4 - 8) / (ENTRA - 8)))
        elif f < t6:
            img = pag1
        elif f < t7:
            u = smooth(1 - (f - t6) / SALE)
            img = pagina(u, u)
        elif f < t8:
            a = (f - t7) / VUELTA
            img = (pag0 * (1 - smooth(2 * a)) + AZUL * smooth(2 * a) if a < 0.5 else
                   AZUL * (1 - smooth(2 * a - 1)) + calz * smooth(2 * a - 1))
        else:
            # +1 para que el último cuadro quede exactamente en 0: si no, conserva un uno por
            # ciento de tinta y el empalme con s5 se mide peor que la variación entre vecinos
            a = smooth(1 - (f - t8 + 1) / FADE_OUT)
            img = render * (1 - a) + calz * a
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(
            os.path.join(OUT, f"f_{f + 1:04d}.png"))
    print("listo:", N, "cuadros en", OUT)


main()
