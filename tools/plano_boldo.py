#!/usr/bin/env python3
"""Sección 4 del recorrido de Casa Boldo: de la cenital con el techo cortado a la lámina de plantas.

Toma el último cuadro de s3 (cenital cortada) y la lámina de planta sin cotas, la calza encima con
las esquinas que guarda el render de s3 (frames_boldo/s3/plano.json) y arma la transición:

  cenital quieta -> el entorno se funde a Azul Origen y aparece el 1er piso calzado sobre la casa
  -> pasa por el azul limpio a la lámina: **los dos pisos lado a lado**, como están dibujados, con el bloque de título
  y el rótulo de cada piso -> se queda ahí (es la pausa larga de la sección) -> vuelve a la planta
  calzada y a la cenital (empalma con el primer cuadro de s5).

La lámina con los dos pisos es la misma figura con la que cierra Casa Lingue (`tools/video_corte.py`,
`paper()`): 1er piso a la izquierda, 2do entrando por la derecha, títulos y logo. Acá el papel es
Azul Origen y las líneas Niebla, porque la sección viene del fondo azul del recorrido.

**No se gira la planta.** La versión anterior la hacía crecer y girar un cuarto de vuelta para
rotular los recintos uno a uno; la revisión pidió sacar ese movimiento y mostrar las dos plantas.
Con las dos lado a lado cada piso mide 39 px/m (contra los 77 px/m de la lámina), así que los
nombres que trae impresos el dibujo quedan de letra chica y no se les agregan cápsulas de rótulo:
a 22 px —el mínimo de marca a 720x1280— un nombre como "Dormitorio 1" mide cuatro metros de planta
y se comería la pieza que nombra. Los recintos del 2do piso se señalan en la pausa del barrido 3D
(ver `--tramo pausa` en `casa_boldo_3d.py`), que para eso se queda tres segundos quieta.

A diferencia de Huingán y Peumo, la lámina acá es **PNG** —se baja del sitio con
`tools/get_planos_web.py`, no viene del Drive—, así que se abre directo en vez de rasterizar un PDF
con `pdftoppm`. Eso cambia la escala de trabajo: la del sitio son ~77 px/m contra los 374 px/m de
un PDF a 300 dpi, y por eso el engrosado de líneas baja de MinFilter(9) a MinFilter(3). Con 9 las
paredes se dibujarían de doce centímetros.

Uso: python3 tools/plano_boldo.py [frames_boldo/s3] [frames_boldo/s4]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
S3 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "frames_boldo", "s3")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "frames_boldo", "s4")
LAMINA = os.path.join(ROOT, "assets", "boldo", "planta_sin_cotas.png")
FUENTES = os.path.join(ROOT, "assets", "fuentes")
LOGO_PNG = os.path.join(ROOT, "assets", "marca", "LOGO_FINAL_NEORIGEN-02.png")
L, D = 7.49, 14.33

# Calibración de cada piso dentro de la lámina, en píxeles de la imagen entera y píxeles por metro.
# Salen de `tools/calibrar_planta.py frames_boldo/s3 assets/boldo/planta_sin_cotas.png <mitad> 7.49
# 14.33`, con FRANJA=0.13 para que la banda azul de marca no le compita al dibujo en la correlación.
# A lo que imprime esa herramienta hay que sumarle lo que recortó: 210 filas de la franja, y 700
# columnas en el caso del 2do piso, que vive en la mitad derecha. Los dos dibujos **no** están a la
# misma escala (76,8 contra 79,1 px/m), que es justo lo que advierte calibrar_planta.py sobre
# heredar constantes entre láminas. Alineación 12,0 y 10,2; las dos verificadas mirando el
# diagnóstico encima del render.
#
# La ventana en metros deja fuera lo que no es la planta: la banda de marca (y > 17), el otro piso
# (que cae más allá en x) y el rótulo de hoja. En el 1er piso el rótulo "PRIMER PISO" está en
# y 14,6..14,9 y el dibujo termina en el borde del porch, y = 14,2: de ahí el corte en 14,45, medido
# contando tinta por fila. A ojo se habría comido el porch. Es la misma ventana para los dos pisos,
# así que los dos recortes salen con el mismo tamaño en metros y se muestran a la misma escala.
PISOS = {
    # piso: (PX0, PY0, PPM, MX0, MX1, MY0, MY1)
    "p1": (60.1, 1488.9, 76.8, -0.50, 7.95, -0.60, 14.45),
    "p2": (734.3, 1514.1, 79.1, -0.50, 7.95, -0.60, 14.45),
}
ROTULOS_PISO = {"p1": "PRIMER PISO", "p2": "SEGUNDO PISO"}
TITULO = ("PLANTAS DE ARQUITECTURA", "Casa Boldo",
          "Cuatro dormitorios, dos baños y doble altura sobre el estar")
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

    # Los dos pisos recortados de la lámina por su ventana en metros y llevados a la misma escala:
    # lado a lado caben a 39 px/m, poco más de un tercio de los 77 px/m del dibujo original.
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
