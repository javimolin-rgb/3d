#!/usr/bin/env python3
"""Arma el reel de Casa Lingue como una sola toma de dron, sin textos (para editar después).

Une los cuadros ya renderizados con los conectores de casa_lingue_3d.py --vista reel:

  A   vuelo de 180°, cuadros A_INI..A_FIN (frente -> costado)        frames_lingue/f_*.png
  c1  sube y gira hasta la vista aérea de los recintos (funde REEL_OV cuadros con el corte)
  B   recintos: corte del 2do y 1er piso hasta la cenital            <plano>/c_*.png (3D)
  P   la cenital se funde con la planta, lámina, y la planta vuelve a calzarse sobre la casa
  c3  baja en espiral desde la cenital mientras la casa se cierra
  D   vuelo de 180°, cuadros D_INI..240 (fachada de acceso con el camino)
  c4  sube, cruza sobre el costado y llega al frente con luz de atardecer (+ toma final)

Uso: python3 tools/reel_continuo.py <salida_cuadros>
     (antes: los tres conectores en frames_reel/c1, c3, c4 y el post del plano en frames_reel/plano,
      ver CLAUDE.md)
Luego: VIGNETA_EXPR='<la que imprime>' LOOK=dia tools/armar_video.sh <salida_cuadros> output/casa_lingue_reel_continuo.mp4 24
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DRON = os.path.join(ROOT, "frames_lingue")
REEL = os.path.join(ROOT, "frames_reel")
PLANO = os.path.join(REEL, "plano")
OUT = sys.argv[1]
A_INI, A_FIN, D_INI, D_FIN = 45, 125, 175, 240   # mismos A_FIN / D_INI que casa_lingue_3d.py
N3D, OV = 264, 6                                 # cuadros 3D del corte; fundido c1 -> corte
FPS = 24
C4_N = 120                                       # REEL_N["c4"] de casa_lingue_3d.py (luego la toma final)


def _curva_extremos():
    """La misma curva que sin_extremos() de tools/video_corte.py (los cuadros del corte ya la traen):
    sin negro ni blanco puros, 0..40 -> 18..40 y 230..255 -> 230..244."""
    v = np.arange(256, dtype=float)
    lut = np.where(v < 40, 18 + v * (40 - 18) / 40, v)
    lut = np.where(v > 230, 230 + (v - 230) * (244 - 230) / 25, lut)
    return np.round(lut).astype(np.uint8)


CURVA = _curva_extremos()


def calido(a, k):
    """Grado de hora dorada (k: 0 día, 1 atardecer): dorado en medios tonos y sombras, el cielo
    queda azul y algo más profundo arriba. Acompaña el cambio de luz del conector c4."""
    lum = a @ np.array([0.2126, 0.7152, 0.0722])
    t = np.clip((lum - 0.55) / 0.3, 0, 1)
    w = (1 - t * t * (3 - 2 * t))[..., None] * k
    y = (a * (1 + w * np.array([0.12, 0.03, -0.17]))) ** (1 + 0.08 * w)
    top = np.clip(1 - np.arange(a.shape[0]) / (0.45 * a.shape[0]), 0, 1) ** 2
    return np.clip(y * (1 - 0.28 * k * top)[:, None, None], 0, 1)


def render(p, k=0.0):
    a = np.asarray(Image.open(p).convert("RGB"))
    if k > 0:
        a = (calido(a / 255.0, k) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(CURVA[a])


def sorted_pngs(d, prefix):
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith(prefix) and f.endswith(".png"))


os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))
n = 0
tramos = []


def put(img_or_path, curva=True):
    global n
    n += 1
    dst = os.path.join(OUT, f"r_{n:04d}.png")
    if isinstance(img_or_path, Image.Image):
        img_or_path.save(dst)
    elif curva:
        render(img_or_path).save(dst)
    else:
        shutil.copyfile(img_or_path, dst)


def tramo(nombre):
    tramos.append((nombre, n))


c1, c3, c4 = (sorted_pngs(os.path.join(REEL, t), "f_") for t in ("c1", "c3", "c4"))
plano = sorted_pngs(PLANO, "c_")
assert len(plano) > N3D, "falta el post del plano (video_corte.py ... --vuelta)"

tramo("A vuelo frente -> costado")
for f in range(A_INI, A_FIN + 1):
    put(os.path.join(DRON, f"f_{f:04d}.png"))
tramo("c1 conector a recintos")
for p in c1[:-OV]:
    put(p)
for j in range(OV):  # mismas poses: el conector (pasto completo) se funde con el corte (pasto ralo)
    a = (j + 1) / (OV + 1)
    put(Image.blend(render(c1[len(c1) - OV + j]), Image.open(plano[j]).convert("RGB"), a))
tramo("B recintos (corte)")
for p in plano[OV:N3D]:
    put(p, curva=False)
tramo("P planta (fundido, lámina y vuelta)")
for p in plano[N3D:]:
    put(p, curva=False)
tramo("c3 conector desde la cenital")
for p in c3[1:]:  # el primero ya está en el último cuadro de la vuelta del plano
    put(p)
tramo("D vuelo fachada de acceso")
for f in range(D_INI, D_FIN + 1):
    put(os.path.join(DRON, f"f_{f:04d}.png"))
tramo("c4 conector al frente al atardecer")
for i, p in enumerate(c4):  # mismo paso día -> atardecer que el cielo y el sol del render
    t = min(max((i + 1 - 0.15 * C4_N) / (0.7 * C4_N), 0.0), 1.0)
    put(render(p, t * t * (3 - 2 * t)))

info = [{"tramo": t, "desde_s": round(i / FPS, 2), "cuadro": i + 1} for t, i in tramos]
json.dump({"cuadros": n, "segundos": round(n / FPS, 2), "tramos": info},
          open(os.path.join(OUT, "tramos.json"), "w"), ensure_ascii=False, indent=1)
p0 = next(x["desde_s"] for x in info if x["tramo"].startswith("P"))
p1 = next(x["desde_s"] for x in info if x["tramo"].startswith("c3"))
for x in info:
    print(f'{x["desde_s"]:6.2f} s  {x["tramo"]}')
print("cuadros:", n, f"({n / FPS:.1f} s)")
print(f"VIGNETA_EXPR='not(between(t,{p0 + 1.0:.2f},{p1 - 1.0:.2f}))'")
