#!/usr/bin/env python3
"""Sección 4 del recorrido de Casa Boldo: de la cenital con el techo cortado a la planta.

Toma el último cuadro de s3 (cenital cortada, casa a lo largo de la pantalla) y la lámina de planta
sin cotas, la calza encima con las esquinas que guarda el render de s3 (frames_boldo/s3/plano.json)
y arma la transición, sin textos de edición:

  cenital quieta -> el entorno se funde a Azul Origen y aparece el 1er piso calzado sobre la casa
  -> la planta crece y gira a vertical, que es como está dibujada la lámina, y se detiene rotulada
  -> **pasa al 2do piso y se detiene más rato ahí**, rotulado -> vuelve a la posición de la casa y
  a la cenital (empalma con el primer cuadro de s5).

  El giro y el acercamiento no son adorno: calzada sobre la casa, la planta ocupa un quinto del
  cuadro y los rótulos se pisan unos a otros. Girada a vertical usa el formato del video, que es
  vertical, y queda sitio para los nombres.

Los dos pisos van calzados sobre la misma casa, uno después del otro, en vez de mostrar sólo la
planta baja: el segundo piso es la mitad del programa de esta casa y no se veía en ninguna parte
del recorrido. La pausa sobre el 2do piso es más larga que la del 1ro porque es la única vez que
aparece, y lleva los rótulos de los recintos que salen de él.

Los rótulos son los de Casa Lingue (`tools/video_corte.py`): cápsula Azul Origen con texto Niebla y
punto de anclaje con borde Madera, más un bloque de título por piso sobre un degradado superior.
Las posiciones de los recintos están en metros del modelo y se llevan a pantalla con la misma afín
que calza la planta, así que no hay que medirlas de nuevo si cambia el encuadre.

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
L, D = 7.49, 14.33

# Calibración de cada piso dentro de la lámina, en píxeles de la imagen entera y píxeles por metro.
# Salen de `tools/calibrar_planta.py frames_boldo/s3 assets/boldo/planta_sin_cotas.png <mitad> 7.49
# 14.33`, con FRANJA=0.13 para que la banda azul de marca no le compita al dibujo en la correlación.
# A lo que imprime esa herramienta hay que sumarle lo que recortó: 210 filas de la franja, y 700
# columnas en el caso del 2do piso, que vive en la mitad derecha. Los dos dibujos **no** están a la
# misma escala (76,8 contra 79,1 px/m), que es justo lo que advierte calibrar_planta.py sobre
# heredar constantes entre láminas. Alineación 12,0 y 10,2; las dos verificadas mirando el
# diagnóstico encima del render.
PISOS = {
    # piso: (PX0, PY0, PPM, MX0, MX1, MY0, MY1)
    # El recorte en metros deja fuera lo que no es la planta: la banda de marca (y > 17), el otro
    # piso (que cae más allá en x) y el rótulo de hoja. En el 1er piso el rótulo "PRIMER PISO" está
    # en y 14,6..14,9 y el dibujo termina en el borde del porch, y = 14,2: de ahí el corte en 14,45,
    # medido contando tinta por fila. A ojo se habría comido el porch.
    "p1": (60.1, 1488.9, 76.8, -0.50, 7.95, -0.60, 14.45),
    "p2": (734.3, 1514.1, 79.1, -0.50, 7.95, -0.60, 14.45),
}
# Recintos de cada piso, en metros del modelo (leídos sobre la lámina con una grilla métrica).
ROTULOS = {
    "p1": [("Terraza", 3.6, 1.6), ("Estar", 2.2, 4.9), ("Dormitorio 1", 6.0, 4.2),
           ("Cocina", 2.1, 7.9), ("Baño 1", 6.9, 8.5), ("Hall", 3.0, 10.2),
           ("Dormitorio 2", 6.5, 11.2), ("Lavadero", 1.6, 12.2), ("Porch", 3.5, 13.6)],
    "p2": [("Doble altura", 2.3, 6.8), ("Dormitorio 3", 5.9, 4.1), ("Baño", 6.2, 8.0),
           ("Escalera", 3.6, 9.3), ("Dormitorio 4", 6.2, 11.2), ("Porch", 3.9, 13.3)],
}
TITULOS = {
    "p1": ("1ER PISO", "Estar y cocina", "Dormitorios 1 y 2, baño y lavadero"),
    "p2": ("2DO PISO", "Dormitorios 3 y 4", "Baño, clósets y doble altura sobre el estar"),
}
AZUL = np.array([1, 30, 47], float)          # Azul Origen #011E2F
NIEBLA = np.array([241, 244, 243], float)    # Niebla #F1F4F3
MADERA = (169, 118, 74)                      # Madera #A9764A
MARGEN = 56
# Cuadros: cenital quieta, fundido a planta, 1er piso, paso al 2do, 2do piso (la pausa larga que
# pidió la revisión: es el único momento del recorrido donde se ve), y vuelta a la cenital.
HOLD0, FADE1, ZOOM, HOLD1, CAMBIO, HOLD2, ZOOM_OUT, FADE_OUT = 24, 24, 24, 54, 24, 72, 24, 18
N = HOLD0 + FADE1 + ZOOM + HOLD1 + CAMBIO + HOLD2 + ZOOM_OUT + FADE_OUT
ROT_IN = 12          # cuadros que tarda un rótulo en aparecer o irse
# A dónde va la planta cuando se la mira de cerca: 2,05 veces más grande, girada un cuarto de
# vuelta (el porch queda arriba, como en la lámina) y centrada bajo el bloque de título.
SFILL, CENTRO = 2.05, (360.0, 772.0)


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
    lamina_gris = Image.open(LAMINA).convert("L").filter(ImageFilter.MinFilter(3))

    # Transformación de pantalla: de la planta calzada sobre la casa (u = 0) a la planta grande y
    # girada un cuarto de vuelta (u = 1). pantalla' = Cm + s · R · (pantalla - c0).
    c0 = o + A @ np.array([L / 2, D / 2])          # centro de la casa en pantalla
    CFIN = np.array(CENTRO)

    def vista(u):
        s_ = 1.0 + (SFILL - 1.0) * u
        th = -np.pi / 2 * u
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        return s_ * R, c0 + (CFIN - c0) * u

    def capa(piso, u):
        """La lámina de un piso deformada a pantalla: fondo Azul Origen, líneas Niebla."""
        px0, py0, ppm, mx0, mx1, my0, my1 = PISOS[piso]
        SR, Cm = vista(u)
        Au, ou = SR @ A, Cm + SR @ (o - c0)        # afín metros -> pantalla con la vista aplicada
        Ainv_u = np.linalg.inv(Au)
        M = np.array([[ppm, 0], [0, -ppm]]) @ Ainv_u
        off = np.array([px0, py0]) - M @ ou
        k = min(1.0, 2.0 * ppm_scr * (1.0 + (SFILL - 1.0) * u) / ppm)   # ~2 px de lámina por px
        pl = lamina_gris.resize((round(lamina_gris.width * k), round(lamina_gris.height * k)),
                                Image.LANCZOS)
        Mk, offk = M * k, off * k
        w = pl.transform((W, H), Image.AFFINE,
                         (Mk[0, 0], Mk[0, 1], offk[0], Mk[1, 0], Mk[1, 1], offk[1]),
                         resample=Image.BICUBIC, fillcolor=255)
        ink = 1.0 - np.asarray(w, float)[..., None] / 255.0
        yy, xx = np.mgrid[0:H, 0:W]
        m = np.einsum("ij,jhw->ihw", Ainv_u, np.stack([xx - ou[0], yy - ou[1]]))
        dentro = ((m[0] > mx0) & (m[0] < mx1) & (m[1] > my0) & (m[1] < my1)).astype(float)[..., None]
        ink = ink * dentro
        return AZUL * (1 - ink) + NIEBLA * ink

    def a_pantalla(x, y, u):
        SR, Cm = vista(u)
        return tuple(Cm + SR @ (o + A @ np.array([x, y], float) - c0))

    def pill(xy, text, alpha, size=22):
        """Rótulo de Casa Lingue: cápsula Azul Origen con texto Niebla y punto de anclaje."""
        f = font("texto-medio", size)
        x, y = xy
        tw = f.getlength(text)
        pad, h = 12, size + 14
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((x - tw / 2 - pad, y - h - 10, x + tw / 2 + pad, y - 10), radius=4,
                            fill=rgba(AZUL, 0.88 * alpha))
        d.text((x, y - h / 2 - 10), text, font=f, fill=rgba(NIEBLA, alpha), anchor="mm")
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=rgba(NIEBLA, alpha),
                  outline=rgba(MADERA, alpha), width=2)
        return layer

    grad = Image.new("L", (1, 520))
    for yy in range(520):
        grad.putpixel((0, yy), int(round(255 * 0.92 * (1 - yy / 519))))
    grad = grad.resize((W, 520))

    def title(piso, alpha):
        rotulo, titulo, bajada = TITULOS[piso]
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = Image.new("RGBA", (W, 520), (*tuple(int(v) for v in AZUL), 255))
        g.putalpha(grad.point(lambda v: int(v * alpha)))
        layer.paste(g, (0, 0))
        d = ImageDraw.Draw(layer)
        d.text((MARGEN, 150), rotulo, font=font("mono", 20), fill=rgba(NIEBLA, alpha), anchor="la")
        d.text((MARGEN, 254), titulo, font=font("titulo", 64), fill=rgba(NIEBLA, alpha), anchor="ls")
        d.rectangle((MARGEN, 278, MARGEN + 63, 281), fill=rgba(MADERA, alpha))
        d.text((MARGEN, 304), bajada, font=font("texto", 22), fill=rgba(NIEBLA, alpha), anchor="la")
        return layer

    render = np.asarray(base, float)
    os.makedirs(OUT, exist_ok=True)
    # hitos del guion, en cuadros
    t1 = HOLD0                      # empieza el fundido a planta
    t2 = t1 + FADE1                 # planta calzada, completa
    t3 = t2 + ZOOM                  # planta grande y girada
    t4 = t3 + HOLD1                 # empieza el paso al 2do piso
    t5 = t4 + CAMBIO                # 2do piso
    t6 = t5 + HOLD2                 # empieza la vuelta
    t7 = t6 + ZOOM_OUT              # planta de nuevo calzada
    cache = {}

    def plano_de(piso, u):
        k = (piso, round(u, 3))
        if k not in cache:
            cache[k] = capa(piso, u)
            if len(cache) > 8:                     # sólo se repiten las poses quietas
                cache.pop(next(iter(cache)))
        return cache[k]

    for f in range(N):
        if f < t1:
            a, u = 0.0, 0.0
        elif f < t2:
            a, u = smooth((f - t1) / FADE1), 0.0
        elif f < t3:
            a, u = 1.0, smooth((f - t2) / ZOOM)
        elif f < t6:
            a, u = 1.0, 1.0
        elif f < t7:
            a, u = 1.0, smooth(1 - (f - t6) / ZOOM_OUT)
        else:
            # +1 para que el último cuadro quede exactamente en 0: si no, conserva un uno por
            # ciento de tinta y el empalme con s5 se mide peor que la variación entre vecinos
            a, u = smooth(1 - (f - t7 + 1) / FADE_OUT), 0.0
        w2 = 0.0 if f < t4 else (1.0 if f >= t5 else smooth((f - t4) / CAMBIO))
        if w2 <= 0.0:
            plano = plano_de("p1", u)
        elif w2 >= 1.0:
            plano = plano_de("p2", u)
        else:
            plano = plano_de("p1", u) * (1 - w2) + plano_de("p2", u) * w2
        img = render * (1 - a) + plano * a
        # rótulos: sólo cuando la planta está quieta y grande, y nunca los dos pisos a la vez
        a1 = min(smooth((f - t3) / ROT_IN), smooth((t4 - f) / ROT_IN))
        a2 = min(smooth((f - t5) / ROT_IN), smooth((t6 - f) / ROT_IN))
        cap = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
        for piso, al in (("p1", a1), ("p2", a2)):
            if al <= 0.01:
                continue
            cap = Image.alpha_composite(cap, title(piso, al))
            for nombre, mx, my in ROTULOS[piso]:
                cap = Image.alpha_composite(cap, pill(a_pantalla(mx, my, u), nombre, al))
        cap.convert("RGB").save(os.path.join(OUT, f"f_{f + 1:04d}.png"))
    print("listo:", N, "cuadros en", OUT)


main()
