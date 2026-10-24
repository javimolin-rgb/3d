"""Convierte el modelo STL de Casa Huingan en una casa con materiales, lista para casa_huingan_3d.py.

El STL (exportado de SketchUp con ImageToStl, en mm) no trae materiales. El casco (muros, techo,
deck y pilotes) es una sola pieza: sus caras se pintan según su normal y su posición. El resto se
separa en piezas sueltas y se clasifica por forma y por la zona de la planta (coordenadas en m,
x = 0..12,18 a lo ancho, frente vidriado en y = 2,1..2,3, fachada de acceso en y = 8,1,
piso terminado en z = 0,23). Las piezas muy densas se simplifican con Decimate.

Uso: python tools/extraer_huingan_stl.py -- assets/huingan/modelo_huingan.stl assets/huingan/casa.blend
"""
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh

stl, out = sys.argv[-2], sys.argv[-1]
MAX_FACES = 2500
L, Y_VID, Y_ACC = 12.18, 2.10, 8.14
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


# Paleta de los renders de Neorigen (Casa Huingan, renders 1 y 2): casco negro, frontón y
# cielo de madera clara vertical, deck de madera, interior forrado en madera clara.
# Los materiales con textura (madera, chapa negra, vidrio) los reemplaza casa_huingan_3d.py por nombre.
M = {
    "chapa": mat("Hg_ChapaNegra", (0.018, 0.018, 0.02), 0.45, 0.3),
    "madera": mat("Hg_MaderaFachada", (0.55, 0.4, 0.26), 0.6),
    "cielo": mat("Hg_MaderaCielo", (0.55, 0.4, 0.26), 0.6),
    "deck": mat("Hg_Deck", (0.4, 0.27, 0.16), 0.6),
    "decknegro": mat("Hg_DeckBorde", (0.05, 0.045, 0.04), 0.7),
    "piso": mat("Hg_PisoInterior", (0.5, 0.36, 0.23), 0.45),
    "muroint": mat("Hg_MuroInterior", (0.6, 0.46, 0.31), 0.6),
    "pilote": mat("Hg_Pilote", (0.55, 0.54, 0.52), 0.9),
    "marco": mat("Hg_MarcoNegro", (0.012, 0.012, 0.013), 0.35, 0.6),
    "vidrio": mat("Hg_Vidrio", (0.9, 0.92, 0.92), 0.02),
    "puerta": mat("Hg_PuertaMadera", (0.36, 0.23, 0.13), 0.5),
    "telaClara": mat("Hg_TelaClara", (0.62, 0.6, 0.56), 0.95, sheen=0.4),
    "telaMedia": mat("Hg_TelaGris", (0.3, 0.29, 0.28), 0.95, sheen=0.4),
    "sabanas": mat("Hg_Sabanas", (0.82, 0.8, 0.77), 0.9, sheen=0.3),
    "maderaOsc": mat("Hg_MaderaOscura", (0.14, 0.08, 0.045), 0.5),
    "maderaClara": mat("Hg_MaderaClara", (0.55, 0.4, 0.26), 0.55),
    "negro": mat("Hg_NegroMate", (0.025, 0.025, 0.027), 0.6),
    "ceramica": mat("Hg_Ceramica", (0.85, 0.85, 0.83), 0.15),
    "acero": mat("Hg_Acero", (0.6, 0.6, 0.62), 0.25, 1.0),
    "planta": mat("Hg_Planta", (0.06, 0.16, 0.05), 0.6),
    "lampara": mat("Hg_Lampara", (0.95, 0.85, 0.7), 0.4, emit=6.0),
}
ORDEN = list(M)


def plano(c, n):
    """Pendiente e intercepto (z en x = 0) del plano de una cara inclinada."""
    s = -n.x / n.z
    return round(s, 2), c.z - s * c.x


def techo_bajo(s, zi, x):
    """Altura de la cara inferior del techo (0,28 m bajo el faldón exterior) en x."""
    return zi - 0.28 + s * x


def casco_cara(c, n, techo):
    """Material de una cara del casco según su centro c, su normal n (m) y el intercepto más alto
    de cada faldón (techo). Las normales del STL no son confiables: el faldón exterior se reconoce
    por ser el plano más alto de su pendiente."""
    afuera_x = c.x < 0.06 or c.x > L - 0.06
    if c.z > 2.3 and abs(n.z) > 0.5:                      # faldones del techo
        s, zi = plano(c, n)
        return "chapa" if zi > techo.get(s, 99) - 0.05 else "cielo"
    if abs(n.x) > 0.9 and afuera_x:
        return "chapa"                                       # costados
    cielo = min(techo_bajo(s, zi, c.x) for s, zi in techo.items())  # cara inferior del techo
    marco = c.x < 0.3 or c.x > L - 0.3 or c.z > cielo - 0.02
    if abs(n.y) > 0.9 and c.z > 0.21 and (c.y < Y_VID - 0.05 or c.y > Y_ACC + 0.1) and marco:
        return "chapa"                                       # canto del marco negro
    if abs(n.y) > 0.9 and (c.y < 0.06 or c.y > 9.18):
        return "decknegro"                                   # canto del deck
    if c.z < 0.2 and abs(n.z) < 0.5:
        return "pilote" if 0.05 < c.y < 9.2 and 0.05 < c.x < L - 0.05 else "decknegro"
    if abs(n.z) > 0.9 and c.z < 0.4:
        if n.z < 0:
            return "decknegro"
        return "deck" if c.y < Y_VID + 0.1 or c.y > Y_ACC - 0.05 else "piso"
    if abs(n.z) > 0.9:
        return "cielo"
    adentro = Y_VID + 0.15 < c.y < Y_ACC - 0.05 and 0.25 < c.x < L - 0.25
    if adentro:
        return "muroint"
    return "madera"                                          # frontón, tabiques del frente y porch


def clasificar(x0, x1, y0, y1, z0, z1, nf):
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ext = sorted((dx, dy, dz))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if ext[0] < 0.002 and nf <= 4:
        return "vidrio"
    fachada = (Y_VID - 0.05 < y0 and y1 < Y_VID + 0.25) or (Y_ACC - 0.1 < y0 and y1 < Y_ACC + 0.1) \
        or x1 < 0.4 or x0 > L - 0.4
    if fachada and ext[0] < 0.25 and z1 > 0.5:
        if ext[1] > 0.55 and dz > 1.9 and ext[0] < 0.06 and nf <= 120:
            return "puerta" if not (y1 < Y_VID + 0.25) else "marco"
        return "marco"
    if dz > 1.9 and ext[0] < 0.06 and 0.5 < ext[1] < 1.0:
        return "puerta"                                       # puertas interiores
    if ext[2] > 0.4 and ext[1] < 0.06:
        return "negro" if z1 < 1.5 else "marco"              # patas, perfiles, barandas
    if z0 < 0 and (y1 < 0.1 or y0 > 9.2):
        return "deck"                                        # escaleras de la terraza y del porch
    if cy < Y_VID:                                           # terraza
        if nf > 2500:
            return "telaClara"
        if 10.1 < cx < 10.45 and z0 > 0.6:
            return "planta"
        return "negro"
    if y0 > 6.4 and (x1 < 1.75 or x0 > 10.45):
        return "ceramica"                                    # baños
    if y0 > 6.3 and 1.7 < x0 and x1 < 4.6:
        return "ceramica" if nf > 300 else "maderaClara"     # lavadero
    if y0 > 6.9 and 4.5 < x0 and x1 < 8.7:
        if dz < 0.07 and 0.8 < z0 < 1.0:
            return "piedra" if "piedra" in M else "ceramica"
        return "acero" if ext[2] < 0.4 and nf > 200 else "maderaOsc"   # cocina
    if (x1 < 3.4 or x0 > 8.8) and Y_VID < y0 and y1 < 5.6:  # dormitorios
        if nf > 2500 or (dx > 1.2 and dy > 1.2 and z1 < 0.9):
            return "sabanas" if z1 > 0.6 else "maderaOsc"
        if z0 > 1.2 and ext[2] < 0.5:
            return "lampara"
        return "maderaOsc" if z1 < 0.9 else "maderaClara"
    if y0 > 5.3 and y1 < 7.0 and 4.6 < x0 and x1 < 8.6:     # comedor e isla
        if z0 > 1.4 and ext[2] < 0.6:
            return "lampara"
        return "telaMedia" if nf > 2000 else "maderaClara"
    if 3.3 < x0 and x1 < 8.9 and Y_VID < y0 and y1 < 5.5:   # estar
        if z0 > 1.4 and ext[2] < 0.6:
            return "lampara"
        if nf > 2000:
            return "telaClara" if dx > 0.9 or dy > 0.9 else "telaMedia"
        return "maderaOsc"
    if z0 > 2.3:
        return "negro"                                       # cañón de la estufa
    return "maderaClara"


bpy.ops.wm.stl_import(filepath=stl, global_scale=0.001)
src = bpy.context.selected_objects[0]
bpy.ops.object.transform_apply(scale=True)
bpy.context.view_layer.objects.active = src
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")

obs = list(bpy.context.scene.objects)
casco = max(obs, key=lambda o: o.dimensions.x + o.dimensions.z if o.dimensions.y > 8 else 0)
casco.name = "Huingan_Casco"
for k in ORDEN:
    casco.data.materials.append(M[k])
bm = bmesh.new()
bm.from_mesh(casco.data)
techo = {}
for f in bm.faces:
    c = f.calc_center_median()
    if c.z > 2.3 and abs(f.normal.z) > 0.5 and f.calc_area() > 0.05:
        s, zi = plano(c, f.normal)
        techo[s] = max(techo.get(s, -99), zi)
for f in bm.faces:
    f.material_index = ORDEN.index(casco_cara(f.calc_center_median(), f.normal, techo))
bm.to_mesh(casco.data)
bm.free()

groups = {k: [] for k in M}
for ob in obs:
    if ob is casco:
        continue
    vs = ob.data.vertices
    xs = [v.co.x for v in vs]
    ys = [v.co.y for v in vs]
    zs = [v.co.z for v in vs]
    nf = len(ob.data.polygons)
    k = clasificar(min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), nf)
    if nf > MAX_FACES:
        d = ob.modifiers.new("dec", "DECIMATE")
        d.ratio = max(0.08, MAX_FACES / nf)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="dec")
    groups[k].append(ob)

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
    j.name = "Huingan_" + k
    j.data.materials.clear()
    j.data.materials.append(M[k])
    if k in ("telaClara", "telaMedia", "sabanas", "ceramica", "lampara", "planta"):
        bpy.ops.object.shade_smooth()
    keep.append(j)
    print(j.name, len(lst), "piezas", len(j.data.polygons), "caras")
bpy.data.libraries.write(out, set(keep), compress=True)
print("TOTAL", sum(len(j.data.polygons) for j in keep))
