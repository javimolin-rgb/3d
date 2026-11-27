"""Mide el barrido del corte de s3 y dice cuánto tiempo se ve limpio cada piso.

RECETA.md §1: en una casa de más de un piso el barrido tiene que pausar en cada piso tres
segundos, y **dónde parar se mide, no se supone** —en Casa Boldo la ventana en que el segundo
piso se veía limpio era de siete cuadros de ruta— y antes de agregar una pausa explícita para el
piso de abajo hay que comprobar si no sale sola, porque el corte satura en `CUT_LOW` y se queda
ahí hasta el cenital, más el segundo de `HOLD0` con que abre la sección 4.

Un piso se ve **limpio** cuando el corte ya pasó el techo o la losa de arriba y todavía no llegó
al piso de abajo, o sea cuando `cut_z` cae en su ventana. Las ventanas salen de las cotas de la
casa, que las imprime `tools/extraer_<casa>_stl.py` al convertir el STL.

Uso:
  ./venv-bpy/bin/python tools/medir_pausas.py casa_maiten_3d.py [--detalle]
"""
import os
import sys

ARCH = next((a for a in sys.argv[1:] if a.endswith(".py")), "casa_maiten_3d.py")
DETALLE = "--detalle" in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

src = open(os.path.join(ROOT, ARCH)).read().replace("\nmain()", "")
g = {"__name__": "medir", "__file__": os.path.join(ROOT, ARCH)}
sys.argv = ["x", "--", "--vista", "dron", "--tramo", "s3"]
exec(compile(src, ARCH, "exec"), g)

PISO, PISO2 = g["PISO"], g["PISO2"]
# Ventanas en que cada piso se ve entero y solo. El techo de Maitén arranca en z = 4,90 (el alero
# más bajo), así que por debajo de eso ya salió completo.
ALERO = 4.90
VENTANAS = [("2do piso", PISO2 + 0.10, ALERO - 0.05),
            ("1er piso", PISO + 0.15, PISO2 - 0.25)]
FPS = g["FPS"]


def recorre(nombre, corte):
    print("\n=== %s: %d cuadros (%.2f s) ===" % (nombre, len(corte), len(corte) / FPS))
    zs = [g["cut_z"](c) for c in corte]
    if DETALLE:
        for f, (c, z) in enumerate(zip(corte, zs), 1):
            print("   %4d  ruta %7.2f  cut_z %6.2f" % (f, c, z))
    for et, lo, hi in VENTANAS:
        dentro = [f for f, z in enumerate(zs, 1) if lo <= z <= hi]
        if not dentro:
            print("   %-9s ventana z %.2f..%.2f: NUNCA" % (et, lo, hi))
            continue
        # tramos consecutivos
        tramos, ini, prev = [], dentro[0], dentro[0]
        for f in dentro[1:]:
            if f != prev + 1:
                tramos.append((ini, prev))
                ini = f
            prev = f
        tramos.append((ini, prev))
        total = sum(b - a + 1 for a, b in tramos)
        print("   %-9s ventana z %.2f..%.2f: %3d cuadros (%.2f s) en %s"
              % (et, lo, hi, total, total / FPS,
                 ", ".join("%d-%d" % t for t in tramos)))
    sat = [f for f, z in enumerate(zs, 1) if z <= g["CUT_LOW"] + 0.01]
    if sat:
        print("   corte saturado en CUT_LOW (%.2f) desde el cuadro %d: %d cuadros (%.2f s)"
              % (g["CUT_LOW"], sat[0], len(sat), len(sat) / FPS))
        print("   + el HOLD0 con que abre la sección 4 (1 s en Boldo) → %.2f s con el 1er piso abierto"
              % (len(sat) / FPS + 1.0))


g["SETUP"]["s3"](720, 1280, 30.0)
n3, g0 = g["SECCIONES"]["s3"], g["INICIO"]["s3"]
recorre("s3 (sin pausas)", [g0 + f for f in range(n3)])
cam, corte = g["pausa_mapas"]()
print("\nPAUSAS = %s   PAUSA_V = %.2f   PAUSA_FRENO = %d"
      % (g["PAUSAS"], g["PAUSA_V"], g["PAUSA_FRENO"]))
print("cámara: %.2f -> %.2f (s3 termina en %d)   último corte en ruta %.2f"
      % (cam[0], cam[-1], g0 + n3, corte[-1]))
recorre("s3p (con pausas)", corte)
