#!/usr/bin/env python3
"""Sección 4 del recorrido de Casa Peumo: de la cenital con el techo cortado a la planta de arquitectura.

Toma el último cuadro de s3 (cenital cortada, casa a lo largo de la pantalla) y la planta sin cotas
(assets/peumo/planta_sin_cotas.pdf, rasterizada a 300 dpi), la calza encima con las esquinas que
guarda el render de s3 (frames_peumo/s3/plano.json) y arma la transición, sin textos (para editar):
  cenital quieta -> el entorno se funde a Azul Origen y aparece la planta en líneas Niebla sobre la casa
  -> planta quieta -> vuelve a la cenital (empalma con el primer cuadro de s5).

Uso: python3 tools/plano_peumo.py [frames_peumo/s3] [frames_peumo/s4]
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
S3 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "frames_peumo", "s3")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "frames_peumo", "s4")
PDF = os.path.join(ROOT, "assets", "peumo", "planta_sin_cotas.pdf")
L, D = 9.49, 13.04
# planta a 300 dpi: esquina terraza-izquierda (x = 0, y = 0) y escala, medidas sobre el dibujo
PX0, PY0, PPM = 2454.0, 5444.0, 394.0
AZUL = np.array([1, 30, 47], float)          # Azul Origen #011E2F
NIEBLA = np.array([241, 244, 243], float)    # Niebla #F1F4F3
HOLD0, FADE_IN, HOLD1, FADE_OUT = 24, 36, 60, 24


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def planta_png():
    tmp = tempfile.mkdtemp()
    subprocess.run(["pdftoppm", "-r", "300", "-png", "-singlefile", PDF, os.path.join(tmp, "p")], check=True)
    return Image.open(os.path.join(tmp, "p.png")).convert("L")


def main():
    frames = sorted(f for f in os.listdir(S3) if f.startswith("f_") and f.endswith(".png"))
    base = Image.open(os.path.join(S3, frames[-1])).convert("RGB")
    W, H = base.size
    info = json.load(open(os.path.join(S3, "plano.json")))
    sx, sy = W / info["res"][0], H / info["res"][1]
    o, ex, ey = (np.array(info["pts"][k]) * (sx, sy) for k in ("o", "x", "y"))
    # afín pantalla -> planta: pantalla = o + (ex - o) * x / L + (ey - o) * y / D, con
    # planta: px = PX0 + x * PPM, py = PY0 - y * PPM
    A = np.column_stack([(ex - o) / L, (ey - o) / D])          # 2x2: (x, y) metros -> pantalla
    Ainv = np.linalg.inv(A)
    # para cada pixel de pantalla: metros = Ainv @ (p - o); planta = (PX0 + mx * PPM, PY0 - my * PPM)
    M = np.array([[PPM, 0], [0, -PPM]]) @ Ainv
    off = np.array([PX0, PY0]) - M @ o
    plan = planta_png().filter(ImageFilter.MinFilter(9))          # líneas más gruesas: se leen a 720 px
    # se reduce con antialias a ~2 px por pixel de pantalla antes de la afín (sin escalones)
    ppm_scr = float(np.linalg.norm(ex - o)) / L
    k = min(1.0, 2.0 * ppm_scr / PPM)
    plan = plan.resize((round(plan.width * k), round(plan.height * k)), Image.LANCZOS)
    M, off = M * k, off * k
    # Image.transform AFFINE recibe (a, b, c, d, e, f): entrada = (a x + b y + c, d x + e y + f)
    warped = plan.transform((W, H), Image.AFFINE, (M[0, 0], M[0, 1], off[0], M[1, 0], M[1, 1], off[1]),
                            resample=Image.BICUBIC, fillcolor=255)
    ink = 1.0 - np.asarray(warped, float)[..., None] / 255.0      # 1 = línea negra del dibujo
    # máscara de la casa (para que la cenital se apague más lento sobre la casa que en el entorno)
    yy, xx = np.mgrid[0:H, 0:W]
    m = np.einsum("ij,jhw->ihw", Ainv, np.stack([xx - o[0], yy - o[1]]))
    # de la lámina sólo la planta (con terraza, porch y escaleras): sin título, logo ni rótulos de hoja
    planta = ((m[0] > -0.4) & (m[0] < L + 0.4) & (m[1] > -1.0) & (m[1] < D + 1.0)).astype(float)[..., None]
    ink = ink * planta
    lamina = AZUL * (1 - ink) + NIEBLA * ink
    casa = ((m[0] > -0.3) & (m[0] < L + 0.3) & (m[1] > -1.0) & (m[1] < D + 1.0)).astype(float)[..., None]
    render = np.asarray(base, float)
    os.makedirs(OUT, exist_ok=True)
    n = HOLD0 + FADE_IN + HOLD1 + FADE_OUT
    for f in range(n):
        if f < HOLD0:
            a_env = a_casa = 0.0
        elif f < HOLD0 + FADE_IN:
            t = (f - HOLD0) / FADE_IN
            a_env, a_casa = smooth(t * 1.4), smooth(t * 1.4 - 0.4)
        elif f < HOLD0 + FADE_IN + HOLD1:
            a_env = a_casa = 1.0
        else:
            t = 1 - (f - HOLD0 - FADE_IN - HOLD1) / FADE_OUT
            a_env, a_casa = smooth(t * 1.4 - 0.4), smooth(t * 1.4)
        a = a_env * (1 - casa) + a_casa * casa
        img = render * (1 - a) + lamina * a
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(os.path.join(OUT, f"f_{f + 1:04d}.png"))
    print("listo:", n, "cuadros en", OUT)


main()
