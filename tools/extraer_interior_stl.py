"""Extrae el interior del modelo STL de Casa Lingue (muebles, escalera, tabiques y altillo) y
lo guarda con materiales asignados por zona, en coordenadas de casa_lingue_3d.py.

El STL no trae materiales: se separan las piezas sueltas y se clasifican por forma y por la
zona de la planta en que están (coordenadas del STL, en metros, con el vidriado frontal en
y = 3,05 y el piso en z = 0,23). Las piezas muy densas (ropa de cama, cojines, grifería) se
simplifican con Decimate para que el render no se alargue.

Uso: python tools/extraer_interior_stl.py -- "<Modelo Casa Lingue.stl>" assets/casa/interior.blend
"""
import sys

import bpy

stl, out = sys.argv[-2], sys.argv[-1]
DY, DZ = -2.0, 0.32  # STL -> escena
MAX_FACES = 2500     # piezas con más caras se simplifican
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
    if sheen and "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = sheen
    return m


# Paleta tomada de los renders de Neorigen (Render 1 y 4 de Casa Lingue)
M = {
    "muro": mat("IntMuroBlanco", (0.78, 0.76, 0.72), 0.85),
    "altillo": mat("IntAltilloMadera", (0.5, 0.33, 0.18), 0.6),
    "escalera": mat("IntEscaleraMadera", (0.32, 0.2, 0.11), 0.55),
    "metal": mat("IntMetalNegro", (0.012, 0.012, 0.012), 0.35, 0.7),
    "negro": mat("IntNegroMate", (0.025, 0.025, 0.027), 0.6),
    "telaClara": mat("IntTelaGrisClaro", (0.6, 0.58, 0.55), 0.95, sheen=0.4),
    "telaMedia": mat("IntTelaGris", (0.3, 0.29, 0.28), 0.95, sheen=0.4),
    "sabanas": mat("IntSabanas", (0.82, 0.8, 0.77), 0.9, sheen=0.3),
    "maderaOsc": mat("IntMaderaOscura", (0.14, 0.08, 0.045), 0.5),
    "maderaClara": mat("IntMaderaClara", (0.55, 0.4, 0.26), 0.55),
    "piedra": mat("IntCubiertaPiedra", (0.62, 0.6, 0.56), 0.3),
    "ceramica": mat("IntCeramicaBlanca", (0.85, 0.85, 0.83), 0.15),
    "acero": mat("IntAcero", (0.6, 0.6, 0.62), 0.25, 1.0),
    "lampara": mat("IntLampara", (0.95, 0.85, 0.7), 0.4, emit=6.0),
}


def classify(x0, x1, y0, y1, z0, z1):
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ext = sorted((dx, dy, dz))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    alto = z0 > 2.6
    # estructura: planos grandes
    if dx > 1.0 and dy > 1.0 and dz < 0.3:
        return "altillo"
    if ext[2] > 1.0 and ext[1] > 0.9 and ext[0] < 0.25:
        return "muro"
    # barandas, patas y perfiles: largos y delgados
    if ext[2] > 0.4 and ext[1] < 0.06:
        return "metal"
    if not alto:
        if cx < 0.95 and cy < 6.5:
            return "escalera"
        if 3.45 < cx < 4.25 and cy < 3.75:
            return "negro"                                   # estufa y cañón
        if z0 > 1.45 and z1 < 2.75 and ext[2] < 0.5:
            return "lampara"                                 # colgantes
        if 1.6 < x0 and x1 < 3.45 and 4.4 < y0 and y1 < 5.35:
            return "telaClara"                               # sofá
        if 3.25 < x0 and 3.85 < cy < 4.6:
            return "telaMedia"                               # sillón
        if (cx - 2.55) ** 2 + (cy - 3.85) ** 2 < 0.4 ** 2:
            return "maderaOsc"                               # mesa de centro
        if 0.9 < x0 and x1 < 1.7 and y1 < 4.3:
            return "maderaOsc"                               # mueble bajo
        if 2.2 < x0 and x1 < 3.5 and 5.3 < y0 and y1 < 6.9:
            return "maderaClara" if dx > 0.6 and dy > 0.6 else "negro"   # comedor
        if y0 > 6.6 and y1 < 8.15 and x0 > 1.6:
            if dz < 0.07 and 0.8 < z0 < 1.0:
                return "piedra"                              # cubierta
            return "acero" if ext[2] < 0.35 else "negro"     # grifería / muebles de cocina
        if y0 > 8.1:
            return "ceramica"                                # lavadero
        return "maderaOsc"
    # segundo piso
    if x0 > 1.9 and 5.3 < y0 and y1 < 7.45:
        return "sabanas" if z1 > 3.35 else "maderaOsc"     # cama
    if x0 > 3.5 and (4.8 < cy < 5.35 or 7.3 < cy < 7.95):
        return "lampara" if z0 > 3.5 else "maderaClara"    # veladores y lámparas
    if y0 > 8.3 and x0 > 1.85:
        return "ceramica"                                    # baño
    if y0 > 9.0 and x1 < 1.9:
        return "telaMedia" if dz > 0.3 and ext[0] < 0.1 else "maderaClara"   # clóset
    if z0 > 3.6 and ext[2] < 0.5:
        return "lampara"
    return "maderaClara"


bpy.ops.wm.stl_import(filepath=stl)
src = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = src
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")

groups = {k: [] for k in M}
for ob in list(bpy.context.scene.objects):
    vs = ob.data.vertices
    xs = [v.co.x / 1000 for v in vs]
    ys = [v.co.y / 1000 for v in vs]
    zs = [v.co.z / 1000 for v in vs]
    x0, x1, y0, y1, z0, z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    inside = x0 > 0.15 and x1 < 4.25 and y0 > 3.0 and y1 < 9.9 and z0 > 0.2
    vidriado = y1 < 3.3 and (x1 - x0) > 1.0  # paños del ventanal frontal (los pone la escena)
    if not inside or vidriado:
        bpy.data.objects.remove(ob)
        continue
    if len(ob.data.polygons) > MAX_FACES:
        d = ob.modifiers.new("dec", "DECIMATE")
        d.ratio = max(0.08, MAX_FACES / len(ob.data.polygons))
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="dec")
    groups[classify(x0, x1, y0, y1, z0, z1)].append(ob)

keep = []
for k, obs in groups.items():
    if not obs:
        continue
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    j = bpy.context.object
    j.name = "Interior_" + k
    j.data.materials.clear()
    j.data.materials.append(M[k])
    j.scale = (0.001, 0.001, 0.001)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    j.location = (0, DY, DZ)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    if k in ("telaClara", "telaMedia", "sabanas", "ceramica", "lampara"):
        bpy.ops.object.shade_smooth()  # telas y loza: suaves; lo demás queda con caras planas
    keep.append(j)
    print(j.name, len(obs), "piezas", len(j.data.polygons), "caras")
bpy.data.libraries.write(out, set(keep), compress=True)
print("TOTAL", sum(len(j.data.polygons) for j in keep))
