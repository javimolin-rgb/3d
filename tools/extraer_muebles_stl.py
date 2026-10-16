"""Extrae los muebles de la terraza del modelo STL de Casa Lingue y los guarda con materiales.

El STL (exportado de SketchUp con ImageToStl) viene en milímetros, sin materiales y con el
origen en la esquina del deck. Se toman las piezas sueltas que están sobre la terraza
(sillas tipo Acapulco con cojines, mesa de centro y lo que hay sobre ella), se clasifican por
forma y se dejan en coordenadas de casa_lingue_3d.py (y - 2,00 m, z + 0,32 m).

Uso: python tools/extraer_muebles_stl.py -- "<Modelo Casa Lingue.stl>" assets/casa/muebles_terraza.blend
"""
import sys

import bpy

stl, out = sys.argv[-2], sys.argv[-1]
DY, DZ = -2.0, 0.32  # STL -> escena (frente del vidriado en y = 1,10 m, piso en z = 0,55 m)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.stl_import(filepath=stl)
src = bpy.context.selected_objects[0]
bpy.context.view_layer.objects.active = src
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")


def mat(name, color, rough, metal=0.0, sheen=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sheen and "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = sheen
    return m


M = {
    "metal": mat("SillaMetalNegro", (0.012, 0.012, 0.012), 0.35, 0.8),
    "cojin": mat("CojinGris", (0.32, 0.31, 0.3), 0.9, sheen=0.5),
    "mesa": mat("MesaMadera", (0.16, 0.09, 0.05), 0.45),
    "deco": mat("Ceramica", (0.78, 0.76, 0.72), 0.3),
}
groups = {k: [] for k in M}
for ob in list(bpy.context.scene.objects):
    vs = ob.data.vertices
    xs = [v.co.x / 1000 for v in vs]
    ys = [v.co.y / 1000 for v in vs]
    zs = [v.co.z / 1000 for v in vs]
    x0, x1, y0, y1, z0, z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    keep = y1 < 2.05 and z1 > 0.3 and z0 > 0.2 and -0.1 < x0 and x1 < 2.6
    if not keep:
        bpy.data.objects.remove(ob)
        continue
    n = len(ob.data.polygons)
    if n in (1968, 1180):
        k = "cojin"
    elif n in (928, 6987, 12) and z1 - z0 < 0.05 and x1 - x0 > 0.6:
        k = "mesa"
    elif z1 < 0.62 or n in (92, 184, 276, 284, 1152):
        k = "metal"
    else:
        k = "deco"
    groups[k].append(ob)

bpy.ops.object.select_all(action="DESELECT")
keep = []
for k, obs in groups.items():
    if not obs:
        continue
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    j = bpy.context.object
    j.name = "Terraza_" + k
    j.data.materials.clear()
    j.data.materials.append(M[k])
    j.scale = (0.001, 0.001, 0.001)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    j.location = (0, DY, DZ)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    bpy.ops.object.shade_smooth()
    keep.append(j)
    print(j.name, len(obs), "piezas", len(j.data.polygons), "caras")
    bpy.ops.object.select_all(action="DESELECT")
bpy.data.libraries.write(out, set(keep), compress=True)
