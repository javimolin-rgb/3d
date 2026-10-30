"""Mide un STL de SketchUp antes de escribir su extractor: dimensiones reales, origen y basura.

Los STL exportados de SketchUp traen dos problemas que rompen el encuadre adaptable del recorrido
de dron (ver RECETA.md §2), y los dos son invisibles si uno mira solo la caja envolvente:

- **Restos sueltos**: esquirlas de geometría a decenas de metros de la casa. Inflan la caja y el
  dron termina encuadrando el vacío. En Casa Roble la caja bruta da 31 x 39 m cuando la casa
  mide 8,8 x 16,8.
- **Origen desplazado**: el modelo no viene centrado en el origen.

La casa real se estima descartando los triángulos cuyo centroide cae fuera del percentil
0,5-99,5 (con 2 m de holgura): la masa del edificio es densa y compacta, los restos no.

Uso: python3 tools/medir_stl.py stl/*.stl      (no necesita bpy)
"""
import struct
import sys

import numpy as np

HOLGURA = 2.0   # metros alrededor del rango de percentiles que se consideran parte de la casa


def leer(ruta):
    """Triángulos de un STL binario, en metros (el archivo viene en mm)."""
    with open(ruta, "rb") as f:
        cab = f.read(84)
        if cab[:5].lower() == b"solid" and b"facet" in cab.lower():
            return None                      # ASCII: no se usa en este proyecto
        n = struct.unpack("<I", cab[80:84])[0]
        datos = f.read(50 * n)
    if len(datos) < 50 * n:
        return None                          # truncado
    rec = np.frombuffer(datos, dtype=np.uint8).reshape(n, 50)
    return rec[:, 12:48].copy().view(np.float32).reshape(n, 3, 3) / 1000.0


print(f"{'archivo':42s} {'casa real (m)':>23s} {'esquina (m)':>17s}  restos")
for ruta in sys.argv[1:]:
    nombre = ruta.rsplit("/", 1)[-1].removesuffix(".stl")
    v = leer(ruta)
    if v is None:
        print(f"{nombre:42s} no es un STL binario válido, o está truncado")
        continue
    ctr = v.mean(1)
    bruto = v.reshape(-1, 3).max(0) - v.reshape(-1, 3).min(0)
    lo, hi = np.percentile(ctr, 0.5, axis=0), np.percentile(ctr, 99.5, axis=0)
    casa = np.all((ctr >= lo - HOLGURA) & (ctr <= hi + HOLGURA), axis=1)
    vv = v[casa].reshape(-1, 3)
    a, d = vv.min(0), vv.max(0) - vv.min(0)
    fuera = len(v) - casa.sum()
    aviso = "  <-- LIMPIAR" if (bruto[:2] - d[:2]).max() > 1.0 else ""
    print(f"{nombre:42s} {d[0]:6.2f} x {d[1]:6.2f} x {d[2]:5.2f} "
          f"x{a[0]:+7.1f} y{a[1]:+7.1f} z{a[2]:+5.2f}  "
          f"{fuera:5d} tri fuera, bruto {bruto[0]:.0f}x{bruto[1]:.0f}{aviso}")
