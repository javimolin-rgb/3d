"""Convierte el modelo STL de Casa Peumo en una casa con materiales, lista para casa_peumo_3d.py.

El STL (exportado de SketchUp con ImageToStl, en mm) no trae materiales, viene desplazado del
origen y arrastra restos sueltos (ver el aviso de RECETA.md §2). Acá se recentra con el mismo
criterio de tools/medir_stl.py —la casa es la masa densa, percentil 0,5-99,5 de los centroides—,
se descartan los restos, el casco (muros, techo, deck y pilotes) se pinta cara a cara, y el resto
se separa en piezas y se clasifica por forma y por recinto.

El casco no se puede pintar por coordenadas como en Huingán: acá los muros están retranqueados
respecto del alero y del deck, así que "estar en el borde de la caja" no distingue afuera de
adentro. En vez de eso cada cara se prueba con dos rayos (BVH sobre el propio casco): si el rayo
en el sentido de la normal escapa y el contrario choca, la cara mira al exterior, y ese sentido
—no la normal del STL, que no es confiable— es el que manda el material.

Cotas, ya recentradas (x = 0..9,49 a lo ancho, y = 0..13,04 de la terraza al porch, z = 0 en la
base de los pilotes): piso terminado 0,60 · segundo piso 3,00 · cumbrera 6,54 · frente vidriado
en y = 2,05 · fachada de acceso en y = 12,35. Techo a dos aguas asimétrico con la cumbrera corrida
en x y la línea de cumbrera corriendo en el eje Y (faldón largo 28°, faldón corto 33°).

Planta:
  1er piso  terraza y < 2,05 · estar x < 7,05 · dormitorio.2 x > 7,05 · baño.2 y hall x > 6,3 e
            y > 8,2 · cocina y lavadero x < 6,3 e y > 8,2 · porch y > 12,35
  2do piso  dormitorio principal, W.cl. y baño sobre el ala x > 7,05; el estar es doble altura.

Uso:
  python tools/extraer_peumo_stl.py -- "stl/Modelo Casa Peumo (Ventanal Grande) .stl" \
      assets/peumo/casa.blend
"""
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree

stl, out = sys.argv[-2], sys.argv[-1]
MAX_FACES = 2500
HOLGURA = 2.0                     # igual que tools/medir_stl.py
PISO, PISO2 = 0.60, 3.00          # pisos terminados
Y_VID, Y_ACC = 2.05, 12.35        # frente vidriado (terraza) y fachada de acceso (porch)
X_ALA = 7.05                      # tabique que parte la planta: estar/cocina | dormitorios
X_SERV = 6.30                     # tabique del ala de servicio en el fondo
Y_NOCHE = 8.20                    # fondo del estar y del dormitorio.2
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
# interior forrado en madera. casa_peumo_3d.py reemplaza por nombre los materiales con textura.
M = {
    "chapa": mat("Pm_ChapaNegra", (0.018, 0.018, 0.02), 0.45, 0.3),
    "madera": mat("Pm_MaderaFachada", (0.55, 0.4, 0.26), 0.6),
    "cielo": mat("Pm_MaderaCielo", (0.55, 0.4, 0.26), 0.6),
    "deck": mat("Pm_Deck", (0.4, 0.27, 0.16), 0.6),
    "decknegro": mat("Pm_DeckBorde", (0.05, 0.045, 0.04), 0.7),
    "piso": mat("Pm_PisoInterior", (0.5, 0.36, 0.23), 0.45),
    "muroint": mat("Pm_MuroInterior", (0.6, 0.46, 0.31), 0.6),
    "pilote": mat("Pm_Pilote", (0.55, 0.54, 0.52), 0.9),
    "marco": mat("Pm_MarcoNegro", (0.012, 0.012, 0.013), 0.35, 0.6),
    "vidrio": mat("Pm_Vidrio", (0.9, 0.92, 0.92), 0.02),
    "puerta": mat("Pm_PuertaMadera", (0.36, 0.23, 0.13), 0.5),
    "telaClara": mat("Pm_TelaClara", (0.62, 0.6, 0.56), 0.95, sheen=0.4),
    "telaMedia": mat("Pm_TelaGris", (0.3, 0.29, 0.28), 0.95, sheen=0.4),
    "sabanas": mat("Pm_Sabanas", (0.82, 0.8, 0.77), 0.9, sheen=0.3),
    "maderaOsc": mat("Pm_MaderaOscura", (0.14, 0.08, 0.045), 0.5),
    "maderaClara": mat("Pm_MaderaClara", (0.55, 0.4, 0.26), 0.55),
    "negro": mat("Pm_NegroMate", (0.025, 0.025, 0.027), 0.6),
    "ceramica": mat("Pm_Ceramica", (0.85, 0.85, 0.83), 0.15),
    "acero": mat("Pm_Acero", (0.6, 0.6, 0.62), 0.25, 1.0),
    "planta": mat("Pm_Planta", (0.06, 0.16, 0.05), 0.6),
    "lampara": mat("Pm_Lampara", (0.95, 0.85, 0.7), 0.4, emit=6.0),
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


def casco_cara(c, n, bvh, techo):
    """Material de una cara del casco, por su posición y por hacia dónde da."""
    ext, o = afuera(bvh, c, n)
    inclinada = 0.25 < abs(n.z) < 0.98 and c.z > 1.8
    if inclinada:                                            # faldones del techo
        s, zi = plano(c, n)
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
        return "madera"                                      # testero del ventanal y del porch
    return "chapa"                                           # el resto de la envolvente


def clasificar(x0, x1, y0, y1, z0, z1, nf, area):
    """Material de una pieza suelta, por forma y por recinto."""
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ext = sorted((dx, dy, dz))
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    if ext[0] < 0.012 and area > 0.25:
        return "vidrio"                                       # paños de cristal
    if dz > 1.8 and ext[0] < 0.09 and 0.5 < ext[1] < 1.2:
        return "puerta"
    fachada = y1 < Y_VID + 0.25 or y0 > Y_ACC - 0.25 or x1 < 0.9 or x0 > 8.6
    if fachada and ext[0] < 0.2 and z1 > PISO + 0.4:
        return "marco"                                        # perfilería de ventanas
    if ext[2] > 0.4 and ext[1] < 0.08:
        return "negro" if z1 < PISO + 1.2 else "marco"        # patas, barandas, perfiles
    if z0 < PISO - 0.2 and (y1 < Y_VID or y0 > Y_ACC):
        return "deck"                                         # escaleras de terraza y porch
    if cy < Y_VID:                                            # ---- terraza
        if nf > 2000:
            return "telaClara"
        return "planta" if dz > 0.5 and ext[0] < 0.6 and z0 > PISO else "negro"
    if cz > PISO2:                                            # ---- segundo piso
        if cx > X_ALA and cy > 10.4:
            return "ceramica"                                 # baño
        if nf > 2500 or (dx > 1.2 and dy > 1.2 and z1 < PISO2 + 0.8):
            return "sabanas" if z1 > PISO2 + 0.45 else "maderaOsc"
        if z0 > PISO2 + 1.5 and ext[2] < 0.6:
            return "lampara"
        return "maderaOsc" if z1 < PISO2 + 0.9 else "maderaClara"
    if cx > X_SERV and cy > Y_NOCHE:                          # ---- baño.2 y hall
        return "ceramica" if nf > 300 else "maderaClara"
    if cx > X_ALA:                                            # ---- dormitorio.2
        if nf > 2500 or (dx > 1.0 and dy > 1.0 and z1 < PISO + 0.9):
            return "sabanas" if z1 > PISO + 0.5 else "maderaOsc"
        if z0 > PISO + 1.5 and ext[2] < 0.5:
            return "lampara"
        return "maderaOsc" if z1 < PISO + 0.9 else "maderaClara"
    if cy > Y_NOCHE:                                          # ---- cocina y lavadero
        if dz < 0.09 and PISO + 0.7 < z0 < PISO + 1.15:
            return "ceramica"                                 # cubiertas
        return "acero" if ext[2] < 0.45 and nf > 200 else "maderaOsc"
    if z0 > PISO + 1.6 and ext[2] < 0.6:
        return "lampara"                                      # colgantes del estar
    if nf > 1800:
        return "telaClara" if dx > 0.9 or dy > 0.9 else "telaMedia"
    return "maderaOsc"                                        # ---- estar


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
casco.name = "Peumo_Casco"
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
    f.material_index = ORDEN.index(casco_cara(f.calc_center_median(), f.normal, bvh, techo))
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
    j.name = "Peumo_" + k
    j.data.materials.clear()
    j.data.materials.append(M[k])
    if k in ("telaClara", "telaMedia", "sabanas", "ceramica", "lampara", "planta", "acero"):
        bpy.ops.object.shade_smooth()
    keep.append(j)
    print("  %-18s %4d piezas  %7d caras" % (j.name, len(lst), len(j.data.polygons)))
bpy.data.libraries.write(out, set(keep), compress=True)
print("TOTAL %d caras -> %s" % (sum(len(j.data.polygons) for j in keep), out))
