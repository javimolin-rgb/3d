"""Mide dónde está el sol en un HDRI equirectangular, para calzar el cielo físico con él.

Las escenas necesitan dos números por HDRI (ver RECETA.md §3): HDRI_SUN_U, la columna del sol
en la imagen (0-1, desde el borde izquierdo), y SUN_ELEV, su elevación en grados sobre el
horizonte. Con ellos el `ShaderNodeTexSky` pone su sol en el mismo lugar que el del HDRI y la
mezcla de los dos cielos no se nota.

Busca el centroide del disco solar: toma los píxeles más brillantes (el sol en un HDRI está
órdenes de magnitud sobre el resto) y promedia sus posiciones, ponderando por luminancia. El
promedio circular en la horizontal evita que un sol partido por el borde dé un valor sin sentido.

Uso: python tools/medir_sol_hdri.py assets/hdri/nieve/snowy_forest_2k.exr [...]
     (con el python que tiene bpy: /opt/bpyvenv/bin/python)
"""
import math
import sys

import bpy
import numpy as np


def medir(ruta):
    img = bpy.data.images.load(ruta, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[:, :, :3]
    lum = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    bpy.data.images.remove(img)

    # el disco solar es la cola de arriba del histograma; 99.99 % deja ~fracción de un por mil
    umbral = max(np.percentile(lum, 99.99), lum.max() * 0.5)
    ys, xs = np.nonzero(lum >= umbral)
    if len(xs) == 0:
        return None
    p = lum[ys, xs]

    # promedio circular en u: el sol puede caer sobre la costura del borde
    ang = (xs + 0.5) / w * 2 * math.pi
    u = (math.atan2((p * np.sin(ang)).sum(), (p * np.cos(ang)).sum()) / (2 * math.pi)) % 1.0
    # la fila 0 del array de Blender es la de abajo: v=0 es el polo sur, v=1 el norte.
    # En equirectangular la vertical es lineal en latitud (no en su seno), así que la
    # elevación sale directo de v. Verificado contra sundowner_overlook, cuyos valores en
    # casa_huingan_3d.py se midieron a mano: da 0.6003 / 27.2 contra 0.6001 / 27.0.
    v = ((p * (ys + 0.5)).sum() / p.sum()) / h
    elev = (2 * v - 1) * 90.0
    return u, elev, float(lum.max()), len(xs)


for ruta in sys.argv[1:]:
    r = medir(ruta)
    nombre = ruta.rsplit("/", 1)[-1]
    if r is None:
        print(f"{nombre:34s} sin sol definido (cielo nublado): usar luz difusa, sin sol direccional")
        continue
    u, elev, mx, n = r
    aviso = "  <- nublado?" if mx < 50 else ""
    print(f"{nombre:34s} HDRI_SUN_U = {u:.4f}   SUN_ELEV = {elev:.1f}   (pico {mx:.0f}, {n} px){aviso}")
