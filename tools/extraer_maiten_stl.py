"""Convierte el modelo STL de Casa Maitén en una casa con materiales, lista para casa_maiten_3d.py.

Mismo procedimiento que `tools/extraer_boldo_stl.py` (ver RECETA.md §2): se recentra con el
criterio de `tools/medir_stl.py` —la casa es la masa densa, percentil 0,5-99,5 de los centroides—,
se descartan los restos, el casco se pinta cara a cara decidiendo con dos rayos (BVH sobre el
propio casco) cuál es el lado de afuera, y las piezas sueltas se clasifican por forma y recinto.

Lo que cambia respecto de Boldo, y por qué:

- **El acceso es lateral, no por un testero.** En Boldo la casa se recorría de testero a testero
  (terraza en y chico, porch en y grande). Acá el porch está al costado, en x < 2,70, y las dos
  fachadas largas son el frente al mar (y = 3,20, a todo el ancho) y el fondo (y = 10,35). Así que
  los planos de fachada son **cuatro**, no dos, y `en_fachada()` los prueba todos.
- **El casco no es una sola pieza.** En Boldo el casco era el objeto suelto más voluminoso y con
  eso alcanzaba. El STL de Maitén lo trae partido en placas: el zócalo, la losa del deck, la del
  segundo piso, el muro de fachada entero y los dos faldones vienen separados, así que quedarse
  con "la pieza más grande" dejaba un casco de 939 caras y 11,3 m —de 16,27 que mide la casa— y
  mandaba el resto de la envolvente a clasificarse como mobiliario (salía casi toda negra).
  `es_casco()` se queda con **toda placa o volumen grande**, los une en un solo objeto y recién
  sobre esa unión arma el BVH con que se decide qué cara mira afuera.
- **Los dos pisos no repiten la planta.** Boldo apilaba el mismo esquema; en Maitén el segundo
  piso mete el dormitorio 1 justo encima del comedor y la cocina, y deja un vacío de doble altura
  sobre el living. Por eso `clasificar()` ramifica por piso y no sólo por recinto.

Cotas medidas al convertir, ya recentradas (x = 0..16,27 a lo ancho, y = 0..11,84 del mar al
fondo, z = 0 en la base del zócalo):

  piso terminado   1,10      (la terraza va al mismo nivel que el interior)
  losa 2do piso    3,85      (cielo del primer piso en 3,65)
  cumbrera         7,81 en x = 8,31, con los faldones a 19,3° y 19,8°
  punto más alto   8,10      — es la más alta de las nueve
  terraza          y < 3,20, a todo el ancho, mirando al mar
  materiales       testeros (y = 3,20 y 10,35) en tabla de pino clara; muros largos, techo,
                   porch y anexo en negro; todos los cantos, marcos y aleros negros
  cuerpo principal x 2,70..14,00 · y 3,20..10,35 · dos pisos
  porch (acceso)   x < 2,70, techo propio más tendido (17°), corona en 4,3
  anexo            x > 13,80 (lavadero abajo, terraza alta arriba), corona en 4,5

Planta, de la lámina `assets/maiten/planta_sin_cotas.png`:

  1er piso   terraza  y < 3,20                      · living  x 2,70..7,40, y 3,20..7,15
             comedor y cocina  x 7,40..13,80, y 3,20..7,15  · lavadero  x > 13,80
             dormitorio 3  x < 6,20, y 7,15..10,35  · baños 2 y 3  x 6,20..9,90
             dormitorio 2  x > 9,90, y 7,15..10,35
  2do piso   vacío de doble altura sobre el living  · dormitorio 4  x < 6,20, y > 7,15
             baño 4 y estar  x 6,20..9,90, y > 7,15 · baño 1 y w.cl.  x > 9,90, y > 7,15
             dormitorio 1  x > 9,50, y 3,20..7,15   (sobre el comedor)

Uso:
  python tools/extraer_maiten_stl.py -- "stl/Modelo Casa Maiten + Ventana .stl" assets/maiten/casa.blend
"""
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

stl, out = sys.argv[-2], sys.argv[-1]
MAX_FACES = 2500
HOLGURA = 2.0                     # igual que tools/medir_stl.py
PISO, PISO2 = 1.10, 3.85          # pisos terminados
Y_MAR = 3.20                      # plano de la fachada vidriada que mira al mar
Y_FONDO = 10.35                   # muro de fondo
Y_NOCHE = 7.15                    # tabique entre la banda de día y la de dormitorios
X_PORCH = 2.70                    # muro del cuerpo principal contra el porch (acceso, -X)
X_ANEXO = 13.80                   # muro del cuerpo principal contra el anexo (+X)
X_LIVING = 7.40                   # living a la izquierda, comedor y cocina a la derecha
X_BANO0, X_BANO1 = 6.20, 9.90     # franja central de baños en la banda de dormitorios
bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color, rough, metal=0.0, emit=0.0, sheen=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (1.0, 0.75, 0.45, 1)
        b.inputs["Emission Strength"].default_value = emit
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    return m


# Paleta Neorigen, la misma de Boldo: casco de chapa negra, frontón y cielo de madera clara,
# deck de madera, interior forrado en madera. casa_maiten_3d.py reemplaza por nombre los
# materiales que llevan textura procedural.
M = {
    "chapa": mat("Ma_ChapaNegra", (0.018, 0.018, 0.02), 0.45, 0.3),
    "madera": mat("Ma_MaderaFachada", (0.55, 0.4, 0.26), 0.6),
    "cielo": mat("Ma_MaderaCielo", (0.55, 0.4, 0.26), 0.6),
    "deck": mat("Ma_Deck", (0.4, 0.27, 0.16), 0.6),
    "decknegro": mat("Ma_DeckBorde", (0.05, 0.045, 0.04), 0.7),
    "piso": mat("Ma_PisoInterior", (0.5, 0.36, 0.23), 0.45),
    "muroint": mat("Ma_MuroInterior", (0.6, 0.46, 0.31), 0.6),
    "pilote": mat("Ma_Pilote", (0.55, 0.54, 0.52), 0.9),
    "marco": mat("Ma_MarcoNegro", (0.012, 0.012, 0.013), 0.35, 0.6),
    "vidrio": mat("Ma_Vidrio", (0.9, 0.92, 0.92), 0.02),
    "vidrioTecho": mat("Ma_VidrioTecho", (0.25, 0.28, 0.29), 0.12),
    "puerta": mat("Ma_PuertaMadera", (0.36, 0.23, 0.13), 0.5),
    "telaClara": mat("Ma_TelaClara", (0.62, 0.6, 0.56), 0.95, sheen=0.4),
    "telaMedia": mat("Ma_TelaGris", (0.3, 0.29, 0.28), 0.95, sheen=0.4),
    "sabanas": mat("Ma_Sabanas", (0.82, 0.8, 0.77), 0.9, sheen=0.3),
    "maderaOsc": mat("Ma_MaderaOscura", (0.14, 0.08, 0.045), 0.5),
    "maderaClara": mat("Ma_MaderaClara", (0.55, 0.4, 0.26), 0.55),
    "negro": mat("Ma_NegroMate", (0.025, 0.025, 0.027), 0.6),
    "ceramica": mat("Ma_Ceramica", (0.85, 0.85, 0.83), 0.15),
    "acero": mat("Ma_Acero", (0.6, 0.6, 0.62), 0.25, 1.0),
    "planta": mat("Ma_Planta", (0.06, 0.16, 0.05), 0.6),
    "lampara": mat("Ma_Lampara", (0.95, 0.85, 0.7), 0.4, emit=6.0),
}
ORDEN = list(M)


def plano(c, n):
    """Pendiente e intercepto (z en x = 0) del plano de una cara inclinada.

    La cumbrera de Maitén corre paralela a Y, así que la pendiente que importa es la del eje X,
    igual que en Boldo."""
    s = -n.x / n.z
    return round(s, 2), c.z - s * c.x


def afuera(bvh, c, n):
    """(exterior, hacia_afuera) de una cara: tira un rayo en el sentido de la normal y otro en
    contra. El lado por el que el rayo escapa del casco es el lado de afuera; las normales del STL
    no son confiables, así que la dirección que vuelve es la que hay que usar, no n."""
    esc = []
    for d in (n, -n):
        hit = bvh.ray_cast(c + d * 0.02, d, 40.0)[0]
        esc.append(hit is None)
    if esc[0] and not esc[1]:
        return True, n
    if esc[1] and not esc[0]:
        return True, -n
    if esc[0] and esc[1]:
        return False, n      # suelta: se trata como interior
    # Los dos rayos chocan. Puede ser una cara interior de verdad... o una cara de la envolvente
    # que tiene su gemela a pocos centímetros: el STL trae varios muros en **dos hojas** (el del
    # porch viene en x = 2,70 y x = 3,10) y el rayo que sale hacia afuera se come la hoja de al
    # lado antes de escapar. Sin este desempate, parte del muro alto del porch salía pintada de
    # madera interior y en el render se leía como "una sombra clara extraña en el alero".
    # Desempate por geometría: si la cara está **en** un plano de la envolvente y mira hacia
    # afuera de la casa, es exterior. Los planos interiores quedan fuera por la holgura.
    for val, eje, signo in ((X_PORCH, 0, -1), (X_ANEXO, 0, 1), (Y_MAR, 1, -1), (Y_FONDO, 1, 1)):
        if abs(c[eje] - val) > 0.12:
            continue
        if n[eje] * signo > 0.7:
            return True, n
        if -n[eje] * signo > 0.7:
            return True, -n
    return False, n          # encerrada: interior de verdad


def en_fachada(c, n, holgura=0.12):
    """¿La cara **es** uno de los dos testeros, que son los que van forrados en madera?

    Las imágenes oficiales del modelo (neorigen.cl/modelo-maiten) reparten los materiales así:
    los testeros —el vidriado que mira al mar y el del fondo, los dos planos y = const, que son
    los que la cumbrera deja triangulares— van en tabla de pino clara, y **los muros largos van
    negros**, en tabla y tapajunta, igual que el techo, el porch y el anexo.

    ⚠️ Dos errores que tuvo esta función, los dos visibles en el render:
    1. Daba madera a los **cuatro** planos del cuerpo y la casa salía clara por los cuatro
       costados. Los planos x = const (X_PORCH y X_ANEXO) ya no entran: caen al "chapa" del
       final de casco_cara(), que es lo que corresponde.
    2. Miraba sólo la **posición** del centro de la cara, no hacia dónde da. Una cara del muro
       del porch (plano x = 0,50) cuyo centro caía a menos de 12 cm de y = 3,20 pasaba el filtro
       y salía de madera: en el render era una cuña clara pegada al anexo. Por eso ahora se
       exige además que la normal vaya en ±Y, que es lo que hace que la cara **esté en** el
       plano del testero y no que apenas lo roce."""
    if abs(n.y) < 0.7:
        return False
    return abs(c.y - Y_MAR) < holgura or abs(c.y - Y_FONDO) < holgura


def vuela(c, margen=0.6):
    """¿La cara vuela por delante de la envolvente del cuerpo principal? Son los cantos del alero
    y del sotecho: desde afuera no se leen como cielo de madera sino como el grosor del techo, y
    la revisión de Boldo fijó que van negros."""
    return (c.y < Y_MAR - margen or c.y > Y_FONDO + margen
            or c.x < X_PORCH - margen or c.x > X_ANEXO + margen)


def es_casco(dx, dy, dz):
    """¿La pieza es parte de la envolvente y no mobiliario?

    El STL trae el casco partido en placas, así que no sirve quedarse con la pieza más grande.
    Los umbrales están puestos contra las piezas reales de este modelo (ver el encabezado):
    entran las placas finas —muros, losas, faldones, tapas—, los pilares que cruzan la casa de
    punta a punta y los volúmenes enteros (cuerpo principal, porch y anexo); quedan fuera los
    paños de cristal, que se pintan aparte, y los muebles grandes, como la isla de la cocina
    (2,73 x 2,55 x 0,90), que por ancha que sea no es ni placa ni volumen de casco."""
    e = sorted((dx, dy, dz))
    if e[0] < 0.012:                      # paño de cristal: lo resuelve clasificar()
        return False
    if e[2] < 2.4:                        # pieza chica: mobiliario
        return False
    if e[0] < 0.30:                       # placa: muro, losa, faldón, tapa, canto
        return True
    if e[2] > 6.0 and e[0] < 0.80:        # pilar o placa gruesa que cruza la casa entera
        return True
    return e[1] > 2.0 and e[2] > 4.0      # volumen entero: cuerpo principal, porch, anexo


def perfileria(c, n, bvh_vidrio):
    """¿La cara es perfilería del ventanal (montante, travesaño o retorno) y va negra?

    Lo pidió la revisión —"porfa los marcos de las ventanas negras"— y es lo que muestran las
    imágenes del modelo: en el testero vidriado las tablas van en pino claro pero **toda la
    perfilería que separa los paños va negra**, igual que el marco que rodea el testero. Boldo
    resolvía el testero por plano y mandaba a madera "la cruz entre paños, por ancha o angosta
    que sea"; acá eso deja los montantes del color de la tabla.

    ⚠️ El criterio **no puede ser el tamaño de la cara**. Se probó (cara fina y de menos de 3 m²)
    y pintó de negro casi todo el testero: el STL tesela el revestimiento en triángulos chicos,
    la mediana de las caras del testero es de 0,09 m², así que una tabla ancha son muchas caras
    angostas y el filtro no distingue nada. La madera cayó de 83 a 17 m².

    Lo que sí distingue un montante de una tabla es **tener cristal a los dos lados**. Así que se
    tiran cuatro rayos cortos en el plano de la cara contra el BVH de los paños de vidrio: si los
    dos de un mismo eje chocan, la cara está entre dos paños y es perfilería. Una tabla pegada a
    una ventana choca por un lado solo."""
    if min(abs(c.y - Y_MAR), abs(c.y - Y_FONDO)) > 0.6:
        return False
    t1 = n.cross(Vector((0.0, 0.0, 1.0)))
    if t1.length < 1e-4:
        t1 = Vector((1.0, 0.0, 0.0))
    t1.normalize()
    t2 = n.cross(t1).normalized()
    for a, b in ((t1, -t1), (t2, -t2)):
        if (bvh_vidrio.ray_cast(c + a * 0.01, a, 0.45)[0] is not None
                and bvh_vidrio.ray_cast(c + b * 0.01, b, 0.45)[0] is not None):
            return True
    return False


def casco_cara(c, n, bvh, techo, area=1.0, bvh_vidrio=None):
    """Material de una cara del casco, por su posición, hacia dónde da y qué tan grande es."""
    if bvh_vidrio is not None and perfileria(c, n, bvh_vidrio):
        return "marco"
    ext, o = afuera(bvh, c, n)
    inclinada = 0.25 < abs(n.z) < 0.98 and c.z > 2.6
    if inclinada:                                            # faldones del techo
        s, zi = plano(c, n)
        if vuela(c):
            return "marco"                                   # canto del alero que vuela
        if ext and o.z > 0:
            # Todo lo que mira al cielo va en chapa, sea o no el plano principal del faldón: los
            # retornos de los tragaluces caen fuera del plano por unos centímetros y, si no, se
            # leen como dos manchas claras sobre el techo (pasó en Peumo y en Boldo).
            return "chapa"
        tapa = zi > techo.get(s, 99) - 0.06
        return "chapa" if tapa else "cielo"
    if abs(n.z) > 0.9:                                       # caras horizontales
        if c.z < PISO + 0.15:
            if o.z < 0:
                return "decknegro"                           # sotabanco del piso y del deck
            return "deck" if ext else "piso"                 # deck a cielo abierto / piso interior
        if PISO2 - 0.35 < c.z < PISO2 + 0.15:
            return "piso" if o.z > 0 else "cielo"            # losa del segundo piso
        return "chapa" if ext and o.z > 0 else "cielo"
    if c.z < PISO - 0.08:                                    # bajo el piso: zócalo y pilotes
        return "pilote" if ext else "decknegro"
    if not ext:
        return "muroint"
    if en_fachada(c, n):
        # Lo que está **en** el plano de la fachada es cara de tabla y va en madera (incluida la
        # cruz entre paños del ventanal); lo que vuela por delante es canto y va negro.
        return "madera"
    if vuela(c):
        return "marco"
    return "chapa"                                           # el resto de la envolvente


def en_faldon(cx, cy, cz):
    """¿La pieza se apoya en el plano de un faldón? Los tragaluces y la chimenea sí.

    Hace falta porque la regla de las lámparas —pieza chica, alta dentro del recinto— también
    atrapa los marcos de los tragaluces, y el material de lámpara emite luz. El acotado en y deja
    fuera el frontón: el plano del faldón, prolongado, pasa por el vidrio alto de la fachada."""
    if not Y_MAR + 0.6 < cy < Y_FONDO - 0.6:
        return False
    return cz > 4.6 and any(abs(cz - (zi + s * cx)) < 0.95 for s, zi in techo.items())


def clasificar(x0, x1, y0, y1, z0, z1, nf, area):
    """Material de una pieza suelta, por forma y por recinto."""
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ext = sorted((dx, dy, dz))
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    alto = cz > PISO2 - 0.25                          # ¿está en el segundo piso?
    piso = PISO2 if alto else PISO
    if ext[0] < 0.012 and ext[1] * ext[2] > 0.25:
        # El cristal se decide antes que nada: las reglas de canto y de faldón también atrapan
        # paños (finos, pegados a un muro y más altos que anchos), y con el orden al revés las
        # ventanas de los muros largos salen pintadas de negro, como agujeros ciegos.
        return "vidrioTecho" if en_faldon(cx, cy, cz) else "vidrio"
    # Canto a la vista por fuera: pieza fina pegada a un plano exterior y más alta que ancha.
    # "Más alta que ancha" deja fuera las tablas del deck, que son finas pero horizontales.
    if (y1 < Y_MAR - 0.2 or y0 > Y_FONDO + 0.2 or x1 < X_PORCH - 0.2 or x0 > X_ANEXO + 0.2) \
            and min(dx, dy) < 0.25 and min(dx, dy) < dz:
        return "marco"
    if en_faldon(cx, cy, cz):
        return "marco"                                        # marcos de tragaluz y chimenea
    if dz > 1.8 and ext[0] < 0.09 and 0.5 < ext[1] < 1.2:
        return "puerta"
    fachada = (y1 < Y_MAR + 0.25 or y0 > Y_FONDO - 0.25
               or x1 < X_PORCH + 0.25 or x0 > X_ANEXO - 0.25)
    if fachada and ext[0] < 0.2 and z1 > piso + 0.4:
        return "marco"                                        # perfilería de la fachada vidriada
    if ext[2] > 0.4 and ext[1] < 0.08:
        return "negro" if z1 < piso + 1.2 else "marco"        # patas, barandas, perfiles
    if z0 < piso - 0.2 and (y1 < Y_MAR or x1 < X_PORCH):
        return "deck"                                         # escaleras de la terraza y del porch
    if cy < Y_MAR:                                            # ---- terraza frente al mar
        if nf > 2000:
            return "telaClara"
        return "planta" if dz > 0.5 and ext[0] < 0.6 and z0 > piso else "negro"
    if cx < X_PORCH:                                          # ---- porch de acceso (lateral)
        return "deck" if dz < 0.2 else "maderaOsc"
    if cx > X_ANEXO:                                          # ---- anexo: lavadero y terraza alta
        return "acero" if nf > 300 and not alto else "maderaOsc"
    if cy < Y_NOCHE:                                          # ======== banda de día
        if alto:
            # En el segundo piso esta banda ya no es el living: a la izquierda está el vacío de
            # doble altura (sólo baranda, que cayó más arriba) y a la derecha el dormitorio 1.
            if nf > 2500 or (dx > 1.0 and dy > 1.4 and z1 < piso + 0.9):
                return "sabanas" if z1 > piso + 0.45 else "maderaOsc"
            if z0 > piso + 1.5 and ext[2] < 0.6:
                return "lampara"
            return "maderaOsc" if z1 < piso + 0.9 else "maderaClara"
        if z0 > piso + 1.6 and ext[2] < 0.6:
            return "lampara"                                  # colgantes sobre la mesa
        if dz < 0.09 and piso + 0.3 < z0 < piso + 0.55 and area > 0.4:
            return "vidrio"                                   # cubiertas de las mesas bajas
        if cx < X_LIVING:                                     # living contra el ventanal
            if nf > 1800:
                return "telaClara" if dx > 0.9 or dy > 0.9 else "telaMedia"
            return "maderaOsc"
        if nf > 1800:                                         # comedor y cocina
            return "telaMedia"
        return "acero" if dz < 0.12 and area > 0.25 else "maderaOsc"
    # ======== banda de dormitorios y baños (los dos pisos comparten la franja central de baños)
    if X_BANO0 < cx < X_BANO1:
        return "ceramica" if nf > 300 else "acero"
    if nf > 2500 or (dx > 1.0 and dy > 1.4 and z1 < piso + 0.9):
        return "sabanas" if z1 > piso + 0.45 else "maderaOsc"
    if z0 > piso + 1.5 and ext[2] < 0.6:
        return "lampara"
    return "maderaOsc" if z1 < piso + 0.9 else "maderaClara"


# ------------------------------------------------------------------ importar, limpiar, recentrar
bpy.ops.wm.stl_import(filepath=stl, global_scale=0.001)
src = bpy.context.selected_objects[0]
bpy.ops.object.transform_apply(scale=True)
me = src.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
idx = np.empty(len(me.polygons) * 3, dtype=np.int32)
me.polygons.foreach_get("vertices", idx)
ctr = co[idx.reshape(-1, 3)].mean(1)
lo, hi = np.percentile(ctr, 0.5, axis=0), np.percentile(ctr, 99.5, axis=0)
dentro = np.all((ctr >= lo - HOLGURA) & (ctr <= hi + HOLGURA), axis=1)
vv = co[idx.reshape(-1, 3)][dentro].reshape(-1, 3)
mn, mx = vv.min(0), vv.max(0)
L, D_CASA, H = mx - mn
print("CASA  %.2f x %.2f x %.2f m   esquina del STL (%.2f, %.2f, %.2f)  restos: %d tri"
      % (L, D_CASA, H, *mn, (~dentro).sum()))
src.location = (-mn[0], -mn[1], -mn[2])
bpy.ops.object.transform_apply(location=True)

bpy.context.view_layer.objects.active = src
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")
obs = list(bpy.context.scene.objects)
print("piezas sueltas:", len(obs))

# ------------------------------------------------------------------ casco (unión de placas)
piezas_casco = [o for o in obs if es_casco(*o.dimensions)]
# Los nombres se guardan **antes** del join: después, las piezas absorbidas quedan borradas y
# tocar la referencia de Python lanza ReferenceError.
nom_casco = {o.name for o in piezas_casco}
nom_sueltas = [o.name for o in obs if o.name not in nom_casco]
n_casco = len(piezas_casco)
bpy.ops.object.select_all(action="DESELECT")
for o in piezas_casco:
    o.select_set(True)
bpy.context.view_layer.objects.active = piezas_casco[0]
bpy.ops.object.join()
casco = bpy.context.object
casco.name = "Maiten_Casco"
print("casco: %d piezas unidas, %d caras" % (n_casco, len(casco.data.polygons)))
for k in ORDEN:
    casco.data.materials.append(M[k])
bm = bmesh.new()
bm.from_mesh(casco.data)
techo = {}
for f in bm.faces:
    c = f.calc_center_median()
    if 0.25 < abs(f.normal.z) < 0.98 and c.z > 2.6 and f.calc_area() > 0.05:
        s, zi = plano(c, f.normal)
        techo[s] = max(techo.get(s, -99), zi)
faldones = sorted(techo.items(), key=lambda kv: -kv[1])
print("faldones (pendiente -> z en x=0):", [(s, round(zi, 2)) for s, zi in faldones[:6]])
# La cumbrera es el cruce de los dos faldones principales, y para eso tienen que ser **de signo
# opuesto**: el casco de Maitén trae tres planos que caen hacia -X (el faldón grande más los dos
# del porch y el anexo, más tendidos), y tomar los dos de mayor intercepto daba un cruce en
# x = 38,8 m, fuera de la casa.
sub = next(((s, zi) for s, zi in faldones if s > 0), None)
baj = next(((s, zi) for s, zi in faldones if s < 0), None)
if sub and baj:
    (s1, z1), (s2, z2) = sub, baj
    xc = (z2 - z1) / (s1 - s2)
    print("CUMBRERA en x = %.2f, z = %.2f   (faldones %.0f° y %.0f°)"
          % (xc, z1 + s1 * xc, abs(np.degrees(np.arctan(s1))), abs(np.degrees(np.arctan(s2)))))
bvh = BVHTree.FromBMesh(bm)
# BVH de los paños de cristal: lo necesita perfileria() para saber qué cara del testero está
# entre dos vidrios (montante) y cuál es tabla.
bm_v = bmesh.new()
n_vid = 0
for nombre in nom_sueltas:
    ob = bpy.data.objects.get(nombre)
    if ob is None or not ob.data.vertices:
        continue
    vs = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", vs)
    vs = vs.reshape(-1, 3)
    e = sorted(vs.max(0) - vs.min(0))
    if e[0] < 0.012 and e[1] * e[2] > 0.25:
        bm_v.from_mesh(ob.data)
        n_vid += 1
bvh_vidrio = BVHTree.FromBMesh(bm_v) if n_vid else None
print("paños de cristal para la perfilería:", n_vid)
for f in bm.faces:
    f.material_index = ORDEN.index(casco_cara(f.calc_center_median(), f.normal, bvh, techo,
                                               f.calc_area(), bvh_vidrio))
bm_v.free()
bm.to_mesh(casco.data)
bm.free()
print("casco: %d caras  dim %.2f %.2f %.2f" % (len(casco.data.polygons), *casco.dimensions))

# ------------------------------------------------------------------ piezas sueltas
groups = {k: [] for k in M}
fuera = 0
for nombre in nom_sueltas:
    ob = bpy.data.objects.get(nombre)
    if ob is None:
        continue
    vs = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", vs)
    vs = vs.reshape(-1, 3)
    p0, p1 = vs.min(0), vs.max(0)
    cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    if not (-1.5 < cx < L + 1.5 and -1.5 < cy < D_CASA + 1.5):
        bpy.data.objects.remove(ob, do_unlink=True)        # restos lejos de la casa
        fuera += 1
        continue
    nf = len(ob.data.polygons)
    area = sum(p.area for p in ob.data.polygons) / 2       # una cara del paño
    k = clasificar(p0[0], p1[0], p0[1], p1[1], p0[2], p1[2], nf, area)
    if nf > MAX_FACES:
        d = ob.modifiers.new("dec", "DECIMATE")
        d.ratio = max(0.04, MAX_FACES / nf)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="dec")
    groups[k].append(ob)
print("restos descartados:", fuera)

keep = [casco]
for k, lst in groups.items():
    if not lst:
        continue
    bpy.ops.object.select_all(action="DESELECT")
    for o in lst:
        o.select_set(True)
    bpy.context.view_layer.objects.active = lst[0]
    bpy.ops.object.join()
    j = bpy.context.object
    j.name = "Maiten_" + k
    j.data.materials.clear()
    j.data.materials.append(M[k])
    if k in ("telaClara", "telaMedia", "sabanas", "ceramica", "lampara", "planta", "acero"):
        bpy.ops.object.shade_smooth()
    keep.append(j)
    print("  %-18s %4d piezas  %7d caras" % (j.name, len(lst), len(j.data.polygons)))
bpy.data.libraries.write(out, set(keep), compress=True)
print("TOTAL %d caras -> %s" % (sum(len(j.data.polygons) for j in keep), out))
