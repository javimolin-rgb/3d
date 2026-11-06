#!/usr/bin/env python3
"""Calibra PX0, PY0 y PPM de una lámina de planta contra el render cenital de su sección de corte.

Son los tres valores que `tools/plano_<casa>.py` necesita para calzar el dibujo de arquitectura
sobre la casa: la posición en píxeles del origen del modelo dentro de la lámina rasterizada a
300 dpi, y la escala del dibujo en píxeles por metro.

**No heredarlos de otra casa ni medirlos a ojo.** Cada lámina tiene su escala y su encuadre, y
varias traen más de un dibujo (la de Peumo lleva el 1er y el 2do piso), con lo que los valores de
otra casa caen entre medio y el resultado parece casi bien. Tampoco alcanza un registro global por
correlación: en Peumo un registro FFT sobre una grilla métrica dio un óptimo 1,4 m corrido, con
alineación 7,6 contra 16,9 del ajuste fino, y a simple vista pasaba.

El método: el render cenital guarda en plano.json la posición en pantalla de tres puntos conocidos
del modelo —(0,0), (L,0) y (0,D)—, lo que fija la afín metros→pantalla. Con eso, lo único que falta
es dónde cae el origen en la lámina y a qué escala, o sea tres números. Se ajustan por descenso por
coordenadas maximizando la correlación entre la tinta del dibujo deformado a pantalla y la magnitud
del gradiente del render: las líneas de la planta tienen que caer sobre los bordes de la casa.

Uso: python3 tools/calibrar_planta.py <carpeta_de_cuadros_s3> <lamina.pdf|.png> [mitad] [L D]
  mitad = izq | der | todo  (por defecto izq: la lámina suele traer el 1er piso a la izquierda)
  L D   = ancho y fondo de la casa en metros; por defecto los de Peumo. **Hay que pasarlos**: son
          los que fijan la afín metros→pantalla junto con plano.json, y con los de otra casa el
          ajuste converge igual pero a una escala equivocada.

Imprime los tres valores y escribe al lado de la lámina un diagnóstico `calibracion_diag.png` con
la planta en rojo sobre el render. **Hay que mirarlo**: la correlación es una guía, no una prueba.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

L, D = 9.49, 13.04        # Peumo; se pisan con los argumentos 4 y 5


def cargar_lamina(ruta, mitad, franja=0.0):
    """La lámina en gris. `franja` recorta una fracción de alto por arriba: las láminas bajadas del
    sitio traen una banda azul de marca con el logo, que es un bloque de tinta grande y sin
    estructura y le compite al dibujo en la correlación."""
    if ruta.lower().endswith(".pdf"):
        tmp = tempfile.mkdtemp()
        subprocess.run(["pdftoppm", "-r", "300", "-png", "-singlefile", ruta,
                        os.path.join(tmp, "p")], check=True)
        ruta = os.path.join(tmp, "p.png")
    im = Image.open(ruta).convert("L")
    if franja > 0:
        im = im.crop((0, int(im.height * franja), im.width, im.height))
    if mitad == "izq":
        im = im.crop((0, 0, im.width // 2, im.height))
    elif mitad == "der":
        im = im.crop((im.width // 2, 0, im.width, im.height))
    return im


def main():
    global L, D
    s3 = sys.argv[1]
    lamina = sys.argv[2]
    mitad = sys.argv[3] if len(sys.argv) > 3 else "izq"
    if len(sys.argv) > 5:
        L, D = float(sys.argv[4]), float(sys.argv[5])
    franja = float(os.environ.get("FRANJA", "0"))
    print("casa %.2f x %.2f m" % (L, D))

    info = json.load(open(os.path.join(s3, "plano.json")))
    base = Image.open(sorted(glob.glob(os.path.join(s3, "f_*.png")))[-1]).convert("RGB")
    W, H = base.size
    sx, sy = W / info["res"][0], H / info["res"][1]
    o, ex, ey = (np.array(info["pts"][k]) * (sx, sy) for k in ("o", "x", "y"))
    A = np.column_stack([(ex - o) / L, (ey - o) / D])
    Ainv = np.linalg.inv(A)

    gy, gx = np.gradient(np.asarray(base.convert("L"), float))
    E = np.hypot(gx, gy)
    E = E / (E.max() + 1e-9)
    E = E - E.mean()          # centrado: si no, gana el encuadre que tape más superficie

    # MinFilter engrosa las líneas: a 720 px de ancho una línea de 1 px del dibujo no toca el borde
    plan = cargar_lamina(lamina, mitad, franja).filter(ImageFilter.MinFilter(9))
    ppm_scr = float(np.linalg.norm(ex - o)) / L
    cache = {}

    def tinta(px0, py0, ppm):
        M = np.array([[ppm, 0], [0, -ppm]]) @ Ainv
        off = np.array([px0, py0]) - M @ o
        k = min(1.0, 2.0 * ppm_scr / ppm)      # ~2 px de lámina por px de pantalla, sin escalones
        if round(k, 5) not in cache:
            cache[round(k, 5)] = plan.resize((round(plan.width * k), round(plan.height * k)),
                                             Image.LANCZOS)
        pl = cache[round(k, 5)]
        Mk, offk = M * k, off * k
        w = pl.transform((W, H), Image.AFFINE,
                         (Mk[0, 0], Mk[0, 1], offk[0], Mk[1, 0], Mk[1, 1], offk[1]),
                         resample=Image.BILINEAR, fillcolor=255)
        return 1.0 - np.asarray(w, float) / 255.0

    def alineacion(p):
        ink = tinta(*p)
        n = np.linalg.norm(ink)
        return -1e9 if n < 1e-6 else float((E * ink).sum() / n)

    def refinar(p0, paso0=(80.0, 80.0, 12.0)):
        p, mejor = np.array(p0, float), alineacion(np.array(p0, float))
        paso = np.array(paso0)
        for _ in range(10):
            avanzo = True
            while avanzo:
                avanzo = False
                for i in range(3):
                    for s in (+1, -1):
                        q = p.copy()
                        q[i] += s * paso[i]
                        v = alineacion(q)
                        if v > mejor:
                            mejor, p, avanzo = v, q, True
                            break
                    if avanzo:
                        break
            paso = paso / 2
        return mejor, p

    # Arranques múltiples, no uno solo: el descenso por coordenadas se queda en el óptimo local del
    # que parte. Partiendo de la caja de la tinta, Peumo caía en uno de alineación 9,4 en vez de
    # 16,9, porque la caja incluye el bloque de título y el origen quedaba ~1,3 m abajo.
    ink0 = np.asarray(plan, float) < 150
    xs, ys = np.nonzero(ink0.any(0))[0], np.nonzero(ink0.any(1))[0]
    ancho, alto = xs.max() - xs.min(), ys.max() - ys.min()
    # el borde inferior del bloque de tinta más alto: es el dibujo, no el rótulo de la hoja
    filas = ink0.sum(1) > 3
    bloques, dentro = [], False
    for i, v in enumerate(filas):
        if v and not dentro:
            ini, dentro, hueco = i, True, 0
        elif not v and dentro:
            hueco += 1
            if hueco > 40:
                bloques.append((ini, i - hueco))
                dentro = False
    if dentro:
        bloques.append((ini, len(filas) - 1))
    grande = max(bloques, key=lambda b: b[1] - b[0]) if bloques else (ys.min(), ys.max())
    semillas = [(float(xs.min()), float(y0) - dy, ppm)
                for y0 in (ys.max(), grande[1])
                for dy in (0.0, alto * 0.04, alto * 0.08)
                for ppm in (ancho / L, alto / D, (grande[1] - grande[0]) / D)]
    mejor, p = max((refinar(s) for s in semillas), key=lambda t: t[0])
    # pasadas de pulido con otros pasos: el descenso por coordenadas se traba en mesetas y volver a
    # entrar con un paso distinto lo destraba (en Peumo, de 11,1 a 12,6)
    for paso0 in ((40.0, 40.0, 6.0), (16.0, 16.0, 2.0), (6.0, 6.0, 0.8)):
        v, q = refinar(p, paso0)
        if v > mejor:
            mejor, p = v, q

    print("PX0, PY0, PPM = %.1f, %.1f, %.1f" % tuple(p))
    print("alineacion = %.3f" % mejor)
    ink = tinta(*p)
    xs, ys = np.nonzero(ink.any(0))[0], np.nonzero(ink.any(1))[0]
    m = np.einsum("ij,jhw->ihw", Ainv, np.stack(np.meshgrid(np.arange(W), np.arange(H))
                                                - o[:, None, None]))
    dentro = ink > 0.05
    print("el dibujo ocupa  x de %.2f a %.2f m   y de %.2f a %.2f m"
          % (m[0][dentro].min(), m[0][dentro].max(), m[1][dentro].min(), m[1][dentro].max()))
    print("(de ahí salen MX0/MX1/MY0/MY1; no son 0..L y 0..D)")

    rgb = np.asarray(base, float).copy()
    rgb[..., 0] = rgb[..., 0] * (1 - ink) + 255 * ink
    rgb[..., 1] *= 1 - ink
    rgb[..., 2] *= 1 - ink
    diag = os.path.join(os.path.dirname(os.path.abspath(lamina)), "calibracion_diag.png")
    Image.fromarray(rgb.astype(np.uint8)).save(diag)
    print("diagnóstico:", diag, "- mirarlo antes de dar los valores por buenos")


main()
