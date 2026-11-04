"""Convierte el modelo STL de Casa Boldo en una casa con materiales, lista para casa_boldo_3d.py.

El STL (exportado de SketchUp con ImageToStl, en mm) no trae materiales, viene desplazado del
origen y arrastra restos sueltos (ver el aviso de RECETA.md §2). Acá se recentra con el mismo
criterio de tools/medir_stl.py —la casa es la masa densa, percentil 0,5-99,5 de los centroides—,
se descartan los restos, el casco (muros, techo, deck y pilotes) se pinta cara a cara, y el resto
se separa en piezas y se clasifica por forma y por recinto.

El casco no se puede pintar por coordenadas como en Huingan: los muros están retranqueados
respecto del alero y del deck, así que "estar en el borde de la caja" no distingue afuera de
adentro. En vez de eso cada cara se prueba con dos rayos (BVH sobre el propio casco): si el rayo
en el sentido de la normal escapa y el contrario choca, la cara mira al exterior, y ese sentido
—no la normal del STL, que no es confiable— es el que manda el material.

Cotas, ya recentradas (x = 0..7,49 a lo ancho, y = 0..14,33 de la terraza al porch, z = 0 en la
base): piso terminado 0,55 · segundo piso 3,25 · cumbrera 6,55 · testero vidriado en y = 3,10 y
acceso en y = 12,40. La casa es la más angosta y alargada de las nueve y el techo es un dos aguas
muy asimétrico: la cumbrera corre en el eje Y, corrida a x = 5,63, con el faldón largo subiendo
32° desde el alero bajo (z = 3,00 en x = 0) y uno corto bajando al alero alto (z = 5,38 en
x = 7,49). El vidrio está concentrado en el testero de y = 3,10, en los dos pisos (es el enganche
de la casa: funciona como un visor al lago).

Planta (las dos plantas repiten el esquema, con el mismo mobiliario apilado):
  terraza   y < 3,10 (deck sobre la ribera)
  estar     y 3,10..6,50 — living y comedor contra el testero vidriado
  baño      x > 6,50 e y 6,50..8,50 (duchas vidriadas en los dos pisos) · hall y escalera x < 6,50
  dormit.   y 8,50..12,40
  porch     y > 12,40 (fachada de acceso, al camino)

Uso:
  python tools/extraer_boldo_stl.py -- "stl/Modelo Casa Boldo.stl" assets/boldo/casa.blend
"""
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree

stl, out = sys.argv[-2], sys.argv[-1]
MAX_FACES = 2500
HOLGURA = 2.0                     # igual que tools/medir_stl.py
PISO, PISO2 = 0.55, 3.25          # pisos terminados
Y_VID, Y_ACC = 3.10, 12.40        # testero vidriado (terraza) y fachada de acceso (porch)
Y_ESTAR = 6.50                    # fondo del estar: atrás vienen baño, hall y dormitorios
Y_NOCHE = 8.50                    # dormitorios (hasta el acceso)
X_BANO = 6.50                     # franja de baños contra el muro alto (+X)
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


# Paleta Neorigen: casco de chapa negra, frontón y cielo de madera clara, deck de madera,
# interior forrado en madera. casa_boldo_3d.py reemplaza por nombre los materiales con textura.
M = {
    "chapa": mat("Bo_ChapaNegra", (0.018, 0.018, 0.02), 0.45, 0.3),
    "madera": mat("Bo_MaderaFachada", (0.55, 0.4, 0.26), 0.6),
    "cielo": mat("Bo_MaderaCielo", (0.55, 0.4, 0.26), 0.6),
    "deck": mat("Bo_Deck", (0.4, 0.27, 0.16), 0.6),
    "decknegro": mat("Bo_DeckBorde", (0.05, 0.045, 0.04), 0.7),
    "piso": mat("Bo_PisoInterior", (0.5, 0.36, 0.23), 0.45),
    "muroint": mat("Bo_MuroInterior", (0.6, 0.46, 0.31), 0.6),
    "pilote": mat("Bo_Pilote", (0.55, 0.54, 0.52), 0.9),
    "marco": mat("Bo_MarcoNegro", (0.012, 0.012, 0.013), 0.35, 0.6),
    "vidrio": mat("Bo_Vidrio", (0.9, 0.92, 0.92), 0.02),
    "vidrioTecho": mat("Bo_VidrioTecho", (0.25, 0.28, 0.29), 0.12),
    "puerta": mat("Bo_PuertaMadera", (0.36, 0.23, 0.13), 0.5),
    "telaClara": mat("Bo_TelaClara", (0.62, 0.6, 0.56), 0.95, sheen=0.4),
    "telaMedia": mat("Bo_TelaGris", (0.3, 0.29, 0.28), 0.95, sheen=0.4),
    "sabanas": mat("Bo_Sabanas", (0.82, 0.8, 0.77), 0.9, sheen=0.3),
    "maderaOsc": mat("Bo_MaderaOscura", (0.14, 0.08, 0.045), 0.5),
    "maderaClara": mat("Bo_MaderaClara", (0.55, 0.4, 0.26), 0.55),
    "negro": mat("Bo_NegroMate", (0.025, 0.025, 0.027), 0.6),
    "ceramica": mat("Bo_Ceramica", (0.85, 0.85, 0.83), 0.15),
    "acero": mat("Bo_Acero", (0.6, 0.6, 0.62), 0.25, 1.0),
    "planta": mat("Bo_Planta", (0.06, 0.16, 0.05), 0.6),
    "lampara": mat("Bo_Lampara", (0.95, 0.85, 0.7), 0.4, emit=6.0),
}
ORDEN = list(M)


def plano(c, n):
    """Pendiente e intercepto (z en x = 0) del plano de una cara inclinada."""
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
    return False, n          # encerrada (adentro) o suelta: se trata como interior


def casco_cara(c, n, bvh, techo, area=1.0):
    """Material de una cara del casco, por su posición, hacia dónde da y qué tan grande es."""
    ext, o = afuera(bvh, c, n)
    inclinada = 0.25 < abs(n.z) < 0.98 and c.z > 1.8
    if inclinada:                                            # faldones del techo
        s, zi = plano(c, n)
        if c.y < Y_VID - 0.6 or c.y > Y_ACC + 0.6:
            # El sotecho que vuela por delante del testero: desde afuera no se lee como cielo de
            # madera sino como el **grosor del techo**, y la revisión fijó que los cantos van
            # negros. El alero de los muros largos sí queda en madera: ése sí se ve como cielo.
            return "marco"
        if ext and o.z > 0:
            # Todo lo que mira al cielo va en chapa, sea o no el plano principal del faldón: los
            # retornos de los tragaluces caían fuera del plano por unos centímetros, salían como
            # cielo de madera y en el render se leían como dos manchas blancas sobre el techo.
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
    if c.z < PISO - 0.08:                                    # bajo el piso
        return "pilote" if ext else "decknegro"
    if not ext:
        return "muroint"
    if abs(o.y) > 0.7 and (c.y < Y_VID + 0.12 or c.y > Y_ACC - 0.12):
        # El corte no es por tamaño sino por plano, que es como lo explicó la revisión: lo que está
        # **en** el plano de la fachada es cara de tabla y va en madera (incluida la cruz entre
        # paños del ventanal, por ancha o angosta que sea); lo que vuela por delante es canto y va
        # negro.
        return "marco" if c.y < Y_VID - 0.6 or c.y > Y_ACC + 0.6 else "madera"
    return "chapa"                                           # el resto de la envolvente


def en_faldon(cx, cy, cz):
    """¿La pieza se apoya en el plano de un faldón? Los tragaluces y la chimenea sí.

    Hace falta porque la regla de las lámparas —pieza chica, alta dentro del recinto— también
    atrapa los marcos de los tragaluces, y el material de lámpara emite luz. El acotado en `y` no
    es decorativo: el plano del faldón, prolongado, pasa por el vidrio alto del testero, así que
    sin él los paños del frontón salían clasificados como tragaluz."""
    if not Y_VID + 0.6 < cy < Y_ACC - 0.6:
        return False
    return cz > 3.4 and any(abs(cz - (zi + s * cx)) < 0.95 for s, zi in techo.items())


def clasificar(x0, x1, y0, y1, z0, z1, nf, area):
    """Material de una pieza suelta, por forma y por recinto."""
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ext = sorted((dx, dy, dz))
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    piso = PISO2 if cz > PISO2 - 0.25 else PISO       # cota del piso del recinto donde está
    # Canto a la vista por fuera: pieza fina pegada a un plano exterior y más alta que ancha —el
    # marco de una ventana del muro largo, el canto del piso que corre al pie de la casa—. Van
    # negros. La condición de "más alta que ancha" deja fuera las tablas del deck, que son finas
    # pero horizontales y sí son cara de tabla.
    if (x1 < 1.15 or x0 > L - 1.15 or y1 < Y_VID - 0.2 or y0 > Y_ACC + 0.2) \
            and min(dx, dy) < 0.25 and min(dx, dy) < dz:
        return "marco"
    if en_faldon(cx, cy, cz):
        # tragaluces y pasada de chimenea: el paño va con vidrio de techo (entintado) y el resto
        # en negro. Con el vidrio normal el techo salía con dos rectángulos blancos.
        return "vidrioTecho" if ext[0] < 0.012 and area > 0.25 else "marco"
    if ext[0] < 0.012 and area > 0.25:
        return "vidrio"                                       # paños de cristal y duchas
    if dz > 1.8 and ext[0] < 0.09 and 0.5 < ext[1] < 1.2:
        return "puerta"
    fachada = y1 < Y_VID + 0.25 or y0 > Y_ACC - 0.25 or x1 < 0.9 or x0 > L - 0.9
    if fachada and ext[0] < 0.2 and z1 > piso + 0.4:
        return "marco"                                        # perfilería del testero y ventanas
    if ext[2] > 0.4 and ext[1] < 0.08:
        return "negro" if z1 < piso + 1.2 else "marco"        # patas, barandas, perfiles
    if z0 < piso - 0.2 and (y1 < Y_VID or y0 > Y_ACC):
        return "deck"                                         # escaleras de terraza y porch
    if cy < Y_VID:                                            # ---- terraza sobre la ribera
        if nf > 2000:
            return "telaClara"
        return "planta" if dz > 0.5 and ext[0] < 0.6 and z0 > piso else "negro"
    if cy > Y_ACC:                                            # ---- porch de acceso
        return "deck" if dz < 0.2 else "maderaOsc"
    if cy < Y_ESTAR:                                          # ---- estar y comedor (el testero)
        if z0 > piso + 1.6 and ext[2] < 0.6:
            return "lampara"                                  # colgantes sobre la mesa
        if dz < 0.09 and piso + 0.3 < z0 < piso + 0.55 and area > 0.4:
            return "vidrio"                                   # cubiertas de las mesas bajas
        if nf > 1800:
            return "telaClara" if dx > 0.9 or dy > 0.9 else "telaMedia"
        return "maderaOsc"
    if cy < Y_NOCHE:                                          # ---- baño (+X) y hall con escalera
        if cx > X_BANO:
            return "ceramica" if nf > 300 else "acero"
        return "maderaClara" if dz > 0.5 else "maderaOsc"
    # ---- dormitorios (los dos pisos repiten el esquema)
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

# ------------------------------------------------------------------ casco
casco = max(obs, key=lambda o: o.dimensions.x * o.dimensions.y * o.dimensions.z)
casco.name = "Boldo_Casco"
for k in ORDEN:
    casco.data.materials.append(M[k])
bm = bmesh.new()
bm.from_mesh(casco.data)
techo = {}
for f in bm.faces:
    c = f.calc_center_median()
    if 0.25 < abs(f.normal.z) < 0.98 and c.z > 1.8 and f.calc_area() > 0.05:
        s, zi = plano(c, f.normal)
        techo[s] = max(techo.get(s, -99), zi)
faldones = sorted(techo.items(), key=lambda kv: -kv[1])
print("faldones (pendiente -> z en x=0):", [(s, round(zi, 2)) for s, zi in faldones])
if len(faldones) >= 2:
    (s1, z1), (s2, z2) = faldones[0], faldones[1]
    if s1 != s2:
        xc = (z2 - z1) / (s1 - s2)
        print("CUMBRERA en x = %.2f, z = %.2f   (faldones %.0f° y %.0f°)"
              % (xc, z1 + s1 * xc, abs(np.degrees(np.arctan(s1))), abs(np.degrees(np.arctan(s2)))))
bvh = BVHTree.FromBMesh(bm)
for f in bm.faces:
    f.material_index = ORDEN.index(casco_cara(f.calc_center_median(), f.normal, bvh, techo,
                                               f.calc_area()))
bm.to_mesh(casco.data)
bm.free()
print("casco: %d caras  dim %.2f %.2f %.2f" % (len(casco.data.polygons), *casco.dimensions))

# ------------------------------------------------------------------ piezas sueltas
groups = {k: [] for k in M}
fuera = 0
for ob in obs:
    if ob is casco:
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
    j.name = "Boldo_" + k
    j.data.materials.clear()
    j.data.materials.append(M[k])
    if k in ("telaClara", "telaMedia", "sabanas", "ceramica", "lampara", "planta", "acero"):
        bpy.ops.object.shade_smooth()
    keep.append(j)
    print("  %-18s %4d piezas  %7d caras" % (j.name, len(lst), len(j.data.polygons)))
bpy.data.libraries.write(out, set(keep), compress=True)
print("TOTAL %d caras -> %s" % (sum(len(j.data.polygons) for j in keep), out))
