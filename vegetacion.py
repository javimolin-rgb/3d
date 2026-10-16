"""Vegetación realista para la escena de Casa Cipres (Blender 5.x).

Genera árboles y arbustos con el complemento Sapling Tree Gen de Blender
(descargado por tools/get_assets.sh en assets/vendor) y les asigna materiales
de corteza y de follaje con texturas con transparencia (tools/make_textures.py).
"""
import ast
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, "assets", "vendor")
TEX = os.path.join(ROOT, "assets", "tex")

_registered = False


def _sapling():
    global _registered
    if VENDOR not in sys.path:
        sys.path.insert(0, VENDOR)
    import add_curve_sapling as sap  # noqa: E402
    if not _registered:
        try:
            sap.register()
        except ValueError:
            pass
        _registered = True
    return sap


def _preset(name):
    src = open(os.path.join(VENDOR, "add_curve_sapling", "presets", name + ".py")).read()
    return ast.literal_eval(src[src.index("{"):])


# ------------------------------------------------------------ materiales
def bark_material(name, dark=(0.018, 0.013, 0.01), light=(0.085, 0.062, 0.048)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (6, 6, 0.8)  # fisuras alargadas en vertical
    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 4
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 18
    nz.inputs["Detail"].default_value = 8
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].color = (*light, 1)
    ramp.color_ramp.elements[1].position = 0.6
    mix = n.new("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value = 0.6
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.8
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], vor.inputs["Vector"])
    l.new(mp.outputs["Vector"], nz.inputs["Vector"])
    l.new(vor.outputs["Distance"], mix.inputs[0])
    l.new(nz.outputs["Fac"], mix.inputs[2])
    l.new(mix.outputs[0], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    l.new(mix.outputs[0], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.9
    return m


def foliage_material(name, image, tint_a=(1, 1, 1), tint_b=(0.8, 0.85, 0.6), translucency=0.35):
    """Follaje con textura de transparencia + variación de color por planta y por hoja."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    out = n["Material Output"]
    b = n["Principled BSDF"]
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(TEX, image), check_existing=True)
    img.interpolation = "Cubic"
    info = n.new("ShaderNodeObjectInfo")
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.6
    fac = n.new("ShaderNodeMath")
    fac.operation = "MULTIPLY_ADD"
    fac.inputs[1].default_value = 0.6
    l.new(nz.outputs["Fac"], fac.inputs[0])
    l.new(info.outputs["Random"], fac.inputs[2])
    tint = n.new("ShaderNodeMixRGB")
    tint.inputs["Color1"].default_value = (*tint_a, 1)
    tint.inputs["Color2"].default_value = (*tint_b, 1)
    l.new(fac.outputs[0], tint.inputs["Fac"])
    col = n.new("ShaderNodeMixRGB")
    col.blend_type = "MULTIPLY"
    col.inputs["Fac"].default_value = 1.0
    l.new(img.outputs["Color"], col.inputs["Color1"])
    l.new(tint.outputs["Color"], col.inputs["Color2"])
    l.new(col.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    tr = n.new("ShaderNodeBsdfTranslucent")
    l.new(col.outputs["Color"], tr.inputs["Color"])
    leaf = n.new("ShaderNodeMixShader")
    leaf.inputs[0].default_value = translucency
    l.new(b.outputs[0], leaf.inputs[1])
    l.new(tr.outputs[0], leaf.inputs[2])
    transp = n.new("ShaderNodeBsdfTransparent")
    cut = n.new("ShaderNodeMixShader")
    l.new(img.outputs["Alpha"], cut.inputs[0])
    l.new(transp.outputs[0], cut.inputs[1])
    l.new(leaf.outputs[0], cut.inputs[2])
    l.new(cut.outputs[0], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------- plantas
def make_plant(name, preset, seed, height, leaf_mat, bark_mat, overrides=None, coll=None):
    """Genera una planta con Sapling, la convierte a malla y la deja con base en el origen."""
    _sapling()
    p = _preset(preset)
    props = bpy.ops.curve.tree_add.get_rna_type().properties.keys()
    p = {k: v for k, v in p.items() if k in props}
    p.update(seed=seed, showLeaves=True, useArm=False, bevel=True, do_update=True,
             leafShape="rect", prune=p.get("prune", False))
    if overrides:
        p.update(overrides)
    before = set(bpy.data.objects)
    bpy.ops.curve.tree_add(**p)
    new = [o for o in bpy.data.objects if o not in before]
    tree = next(o for o in new if o.type == "CURVE")
    leaves = [o for o in new if o.type == "MESH"]
    tree.data.resolution_u = 2
    tree.data.bevel_resolution = 1
    bpy.ops.object.select_all(action="DESELECT")
    tree.select_set(True)
    bpy.context.view_layer.objects.active = tree
    bpy.ops.object.convert(target="MESH")
    tree = bpy.context.object
    if not tree.data.uv_layers:
        tree.data.uv_layers.new(name="UVMap")
    tree.data.uv_layers[0].name = "UVMap"
    n_bark = len(tree.data.polygons)
    for lv in leaves:
        if lv.data.uv_layers:
            lv.data.uv_layers[0].name = "UVMap"
    bpy.ops.object.select_all(action="DESELECT")
    for lv in leaves:
        lv.select_set(True)
    tree.select_set(True)
    bpy.context.view_layer.objects.active = tree
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.join()
    obj = bpy.context.object
    # materiales: primero las ramas (objeto activo), después las hojas
    obj.data.materials.clear()
    obj.data.materials.append(bark_mat)
    obj.data.materials.append(leaf_mat)
    idx = [0 if i < n_bark else 1 for i in range(len(obj.data.polygons))]
    obj.data.polygons.foreach_set("material_index", idx)
    obj = bpy.context.object
    obj.name = name
    # escala a la altura pedida, base en z=0
    zs = [v.co.z for v in obj.data.vertices]
    k = height / (max(zs) - min(zs))
    obj.scale = (k, k, k)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    if coll is not None:
        for c in obj.users_collection:
            c.objects.unlink(obj)
        coll.objects.link(obj)
    obj.location = (0, 0, 0)
    return obj


def build_library(coll):
    """Variantes de árboles y arbustos. Devuelve dict de listas por tipo."""
    bark = bark_material("Corteza")
    bark_light = bark_material("CortezaClara", (0.05, 0.045, 0.04), (0.22, 0.2, 0.17))
    fir_leaf = foliage_material("AgujasAbeto", "abeto_ramita.png", (1, 1, 1), (0.75, 0.9, 0.7))
    pine_leaf = foliage_material("AgujasPino", "pino_ramita.png", (1, 1, 1), (1.15, 1.05, 0.7))
    shrub_leaf = foliage_material("HojasArbusto", "hoja.png", (1, 1, 1), (1.4, 1.1, 0.6), 0.45)
    dry_leaf = foliage_material("HojasSecas", "hoja_seca.png", (1, 1, 1), (0.9, 0.8, 0.7), 0.4)
    lib = {"abeto": [], "pino": [], "arbusto": [], "alamo": []}
    fir = dict(leaves=26, leafScale=1.25, leafScaleX=0.5, leafDownAngle=55)
    for i, (s, h) in enumerate(((3, 19), (11, 23), (27, 16))):
        lib["abeto"].append(make_plant(f"Abeto{i}", "douglas_fir", s, h, fir_leaf, bark, fir, coll))
    pine = dict(leaves=90, leafScale=0.12, leafScaleX=0.5)
    for i, (s, h) in enumerate(((5, 12), (8, 9))):
        lib["pino"].append(make_plant(f"Pino{i}", "small_pine", s, h, pine_leaf, bark, pine, coll))
    shrub = dict(leaves=30, leafScale=0.3, leafScaleX=0.75, scale=3.0, scaleV=1.0)
    for i, (s, h, mat) in enumerate(((2, 1.4, shrub_leaf), (6, 1.0, shrub_leaf), (9, 1.2, dry_leaf))):
        lib["arbusto"].append(make_plant(f"Arbusto{i}", "small_maple", s, h, mat, bark_light, shrub, coll))
    aspen = dict(leaves=70, leafScale=0.38, leafScaleX=0.8)
    for i, (s, h) in enumerate(((4, 13), (14, 11))):
        lib["alamo"].append(make_plant(f"Alamo{i}", "quaking_aspen", s, h, shrub_leaf, bark_light, aspen, coll))
    # árbol esbelto para el primer plano (conífera tipo ciprés)
    slim = make_plant("CipresPrimerPlano", "douglas_fir", 41, 10.5, fir_leaf, bark,
                      dict(fir, leafScale=1.0), coll)
    slim.scale = (0.42, 0.42, 1.0)
    bpy.context.view_layer.objects.active = slim
    bpy.ops.object.select_all(action="DESELECT")
    slim.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    lib["cipres"] = [slim]
    return lib
