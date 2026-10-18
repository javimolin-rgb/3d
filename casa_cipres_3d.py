"""Escena 3D de Casa Cipres + vuelo de dron (Blender 4.x, Cycles).

Uso:
  blender -b -P casa_cipres_3d.py -- --out frames/ [--res 1080x1920]
          [--samples 32] [--frames 1-192] [--still 120] [--save escena.blend]

Medidas tomadas de "Planta con Cotas" y "Lámina Casa Cipres" (escala 1:50):
  - largo 12,18 m (eje X), fondo 7,24 m (eje Y), frente (terraza) hacia -Y
  - techo de una agua: 2,58 m sobre piso en X=0, 5,27 m en X=12,18
  - piso elevado 0,5 m sobre pilotes; terraza de 2 m al frente, porch atrás
  - vanos del frente según cotas 0,27 / 2,27 / 0,8 / 5,5 / 0,8 / 2,27 / 0,27
Paisaje inspirado en los renders: bosque de pinos, lago, cordillera nevada,
luz de atardecer con el interior encendido.
"""
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"step": "1", "out": "//frames/", "res": "1080x1920", "samples": "32", "frames": "1-192",
        "still": None, "save": None}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(7)
L, D = 12.18, 7.24          # largo y fondo de la caja
FLOOR = 0.5                 # nivel de piso terminado
H0, H1 = 2.58, 5.27         # altura exterior del techo sobre el piso (x=0 / x=L)
ROOF_T = 0.30               # espesor del techo / marco negro
WALL_T = 0.25               # espesor de muros laterales negros
FRONT_Y = 0.90              # fachada frontal retranqueada (terraza cubierta)
BACK_Y = D - 1.10           # fachada posterior retranqueada (porch)
WARM = (1.0, 0.62, 0.32)
WB_TEMP = float(opts.get("wb", "7600"))  # balance de blancos cálido
SUN_ELEV, SUN_AZ = 8.0, -115.0  # azimut desde +Y hacia +X: sol de atardecer desde la izquierda


def roof_top(x):
    return FLOOR + H0 + (H1 - H0) * x / L


def roof_under(x):
    return roof_top(x) - ROOF_T


# ---------------------------------------------------------------- utilidades
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, mat=None, coll=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    if mat:
        ob.data.materials.append(mat)
    return link(ob, coll)


def box(name, x0, x1, y0, y1, z0, z1, mat=None, coll=None):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return mesh_obj(name, v, f, mat, coll)


def prism_xz(name, pts, y0, y1, mat=None, coll=None):
    """Polígono en el plano XZ extruido entre y0 e y1."""
    n = len(pts)
    v = [(x, y0, z) for x, z in pts] + [(x, y1, z) for x, z in pts]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_obj(name, v, f, mat, coll)


def prism_yz(name, pts, x0, x1, mat=None, coll=None):
    n = len(pts)
    v = [(x0, y, z) for y, z in pts] + [(x1, y, z) for y, z in pts]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_obj(name, v, f, mat, coll)


def cut(obj, cutters):
    for c in cutters:
        m = obj.modifiers.new("cut", "BOOLEAN")
        m.operation, m.solver, m.object = "DIFFERENCE", "EXACT", c
        c.hide_render = True
        c.hide_viewport = True


# --------------------------------------------------------------- materiales
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links


def principled(name, color, rough=0.5, metal=0.0):
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def boards_mat(name, c1, c2, axis, scale, rough=0.6, bump=0.25, distort=2.0):
    """Tablas (revestimiento o deck): bandas + veta con ruido."""
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = axis
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 0.0
    grain = n.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 3.0
    grain.inputs["Detail"].default_value = 8
    grain.inputs["Distortion"].default_value = distort
    mapg = n.new("ShaderNodeMapping")
    mapg.inputs["Scale"].default_value = (1, 1, 14) if axis == "X" else (14, 1, 1)
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    seam = n.new("ShaderNodeMath")
    seam.operation = "GREATER_THAN"
    seam.inputs[1].default_value = 0.96
    dark = n.new("ShaderNodeMixRGB")
    dark.blend_type = "MULTIPLY"
    dark.inputs["Color2"].default_value = (0.35, 0.3, 0.25, 1)
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    l.new(tc.outputs["Object"], mapg.inputs["Vector"])
    l.new(mapg.outputs["Vector"], grain.inputs["Vector"])
    l.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    l.new(wave.outputs["Fac"], seam.inputs[0])
    l.new(ramp.outputs["Color"], dark.inputs["Color1"])
    l.new(seam.outputs["Value"], dark.inputs["Fac"])
    l.new(dark.outputs["Color"], b.inputs["Base Color"])
    l.new(seam.outputs["Value"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m


def ribbed_metal(name):
    """Plancha negra acanalada (muros laterales)."""
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Metallic"].default_value = 0.3
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 14
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.35
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    l.new(wave.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def glass_mat():
    m, n, l = new_mat("Vidrio")
    n.remove(n["Principled BSDF"])
    out = n["Material Output"]
    fr = n.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.6
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.86, 0.9, 0.9, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.02
    mix = n.new("ShaderNodeMixShader")
    l.new(fr.outputs["Fac"], mix.inputs["Fac"])
    l.new(tr.outputs[0], mix.inputs[1])
    l.new(gl.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])
    m.blend_method = "BLEND"
    return m


def emit_mat(name, color, strength):
    m, n, l = new_mat(name)
    n.remove(n["Principled BSDF"])
    e = n.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    l.new(e.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def foliage_mat(name, c1, c2):
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    info = n.new("ShaderNodeObjectInfo")
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 6
    add = n.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.5
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    l.new(nz.outputs["Fac"], add.inputs[0])
    l.new(info.outputs["Random"], add.inputs[2])
    l.new(add.outputs[0], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.6
    l.new(nz.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


PHOTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "photo")


def terrain_mat():
    """Suelo: pasto fotográfico (dos escalas para que no se note la repetición) con manchones
    secos; en altura: bosque oscuro, roca con estratos y nieve sólo en cumbres y laderas suaves."""
    m, n, l = new_mat("Terreno")
    b = n["Principled BSDF"]
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["Position"], sep.inputs[0])
    nrm = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["True Normal"], nrm.inputs[0])
    tc = n.new("ShaderNodeTexCoord")
    img = bpy.data.images.load(os.path.join(PHOTO, "grasslight-big.jpg"), check_existing=True)

    def photo(size, rot):
        mp = n.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / size, 1 / size, 1)
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(rot))
        t = n.new("ShaderNodeTexImage")
        t.image = img
        l.new(tc.outputs["Object"], mp.inputs["Vector"])
        l.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t

    p1, p2 = photo(2.6, 0), photo(9.0, 37)
    mixp = n.new("ShaderNodeMixRGB")
    mixp.inputs["Fac"].default_value = 0.45
    l.new(p1.outputs["Color"], mixp.inputs["Color1"])
    l.new(p2.outputs["Color"], mixp.inputs["Color2"])
    # baja la saturación del pasto fotográfico y lo oscurece un poco
    hsv = n.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 0.78
    hsv.inputs["Value"].default_value = 0.62
    hsv.inputs["Hue"].default_value = 0.49
    l.new(mixp.outputs["Color"], hsv.inputs["Color"])
    # manchones secos/terrosos a gran escala
    big = n.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.06
    big.inputs["Detail"].default_value = 6
    l.new(tc.outputs["Object"], big.inputs["Vector"])
    dry_f = n.new("ShaderNodeMapRange")
    dry_f.inputs[1].default_value, dry_f.inputs[2].default_value = 0.5, 0.68
    dry_f.inputs[4].default_value = 0.55
    l.new(big.outputs["Fac"], dry_f.inputs[0])
    dry = n.new("ShaderNodeMixRGB")
    dry.blend_type = "MULTIPLY"
    dry.inputs["Color2"].default_value = (1.35, 0.95, 0.55, 1)
    l.new(dry_f.outputs[0], dry.inputs["Fac"])
    l.new(hsv.outputs["Color"], dry.inputs["Color1"])
    # roca con estratos
    fine = n.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 0.08
    fine.inputs["Detail"].default_value = 12
    fine.inputs["Roughness"].default_value = 0.65
    l.new(tc.outputs["Object"], fine.inputs["Vector"])
    strata = n.new("ShaderNodeTexWave")
    strata.bands_direction = "Z"
    strata.inputs["Scale"].default_value = 0.02
    strata.inputs["Distortion"].default_value = 6
    strata.inputs["Detail"].default_value = 4
    l.new(tc.outputs["Object"], strata.inputs["Vector"])
    rk = n.new("ShaderNodeMath")
    rk.operation = "MULTIPLY_ADD"
    rk.inputs[1].default_value = 0.06
    l.new(strata.outputs["Fac"], rk.inputs[0])
    l.new(fine.outputs["Fac"], rk.inputs[2])
    rock = n.new("ShaderNodeValToRGB")
    e = rock.color_ramp.elements
    e[0].position, e[0].color = 0.35, (0.035, 0.035, 0.04, 1)
    e[1].position, e[1].color = 0.95, (0.2, 0.18, 0.16, 1)
    e.new(0.65).color = (0.09, 0.085, 0.08, 1)
    l.new(rk.outputs[0], rock.inputs["Fac"])
    forest = n.new("ShaderNodeValToRGB")
    forest.color_ramp.elements[0].color = (0.012, 0.022, 0.01, 1)
    forest.color_ramp.elements[1].color = (0.04, 0.06, 0.025, 1)
    l.new(fine.outputs["Fac"], forest.inputs["Fac"])
    # pasto -> bosque (faldas) -> roca, según altura y pendiente
    h_for = n.new("ShaderNodeMapRange")
    h_for.inputs[1].default_value, h_for.inputs[2].default_value = 25, 60
    l.new(sep.outputs["Z"], h_for.inputs[0])
    m0 = n.new("ShaderNodeMixRGB")
    l.new(h_for.outputs[0], m0.inputs["Fac"])
    l.new(dry.outputs["Color"], m0.inputs["Color1"])
    l.new(forest.outputs["Color"], m0.inputs["Color2"])
    h_rock = n.new("ShaderNodeMath")
    h_rock.operation = "MULTIPLY_ADD"
    h_rock.inputs[1].default_value = 80
    l.new(fine.outputs["Fac"], h_rock.inputs[0])
    l.new(sep.outputs["Z"], h_rock.inputs[2])
    rk_f = n.new("ShaderNodeMapRange")
    rk_f.inputs[1].default_value, rk_f.inputs[2].default_value = 150, 230
    l.new(h_rock.outputs[0], rk_f.inputs[0])
    steep = n.new("ShaderNodeMapRange")  # pendientes fuertes: roca aunque estén bajas
    steep.inputs[1].default_value, steep.inputs[2].default_value = 0.8, 0.6
    l.new(nrm.outputs["Z"], steep.inputs[0])
    hmask = n.new("ShaderNodeMapRange")
    hmask.inputs[1].default_value, hmask.inputs[2].default_value = 60, 110
    l.new(sep.outputs["Z"], hmask.inputs[0])
    steep_h = n.new("ShaderNodeMath")
    steep_h.operation = "MULTIPLY"
    l.new(steep.outputs[0], steep_h.inputs[0])
    l.new(hmask.outputs[0], steep_h.inputs[1])
    rk_any = n.new("ShaderNodeMath")
    rk_any.operation = "MAXIMUM"
    l.new(rk_f.outputs[0], rk_any.inputs[0])
    l.new(steep_h.outputs[0], rk_any.inputs[1])
    m1 = n.new("ShaderNodeMixRGB")
    l.new(rk_any.outputs[0], m1.inputs["Fac"])
    l.new(m0.outputs["Color"], m1.inputs["Color1"])
    l.new(rock.outputs["Color"], m1.inputs["Color2"])
    # nieve: altura (con ruido) y sólo donde la pendiente la deja asentarse
    snow_h = n.new("ShaderNodeMath")
    snow_h.operation = "MULTIPLY_ADD"
    snow_h.inputs[1].default_value = 140
    l.new(fine.outputs["Fac"], snow_h.inputs[0])
    l.new(sep.outputs["Z"], snow_h.inputs[2])
    sh = n.new("ShaderNodeMapRange")
    sh.inputs[1].default_value, sh.inputs[2].default_value = 230, 290
    l.new(snow_h.outputs[0], sh.inputs[0])
    sn = n.new("ShaderNodeMapRange")
    sn.inputs[1].default_value, sn.inputs[2].default_value = 0.5, 0.72
    l.new(nrm.outputs["Z"], sn.inputs[0])
    snow = n.new("ShaderNodeMath")
    snow.operation = "MULTIPLY"
    l.new(sh.outputs[0], snow.inputs[0])
    l.new(sn.outputs[0], snow.inputs[1])
    m2 = n.new("ShaderNodeMixRGB")
    m2.inputs["Color2"].default_value = (0.82, 0.85, 0.9, 1)
    l.new(snow.outputs[0], m2.inputs["Fac"])
    l.new(m1.outputs["Color"], m2.inputs["Color1"])
    l.new(m2.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.3
    l.new(p1.outputs["Color"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


# ------------------------------------------------------------------- casa
def build_house(M):
    hc = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(hc)

    # Marco negro: techo inclinado, muros laterales y losa
    prism_xz("Techo", [(0, roof_under(0)), (L, roof_under(L)), (L, roof_top(L)), (0, roof_top(0))],
             -0.05, D + 0.05, M["negro"], hc)
    for x0, x1, nm in ((0, WALL_T, "MuroIzq"), (L - WALL_T, L, "MuroDer")):
        zt = roof_top((x0 + x1) / 2)
        wall = prism_yz(nm, [(0, 0.25), (D, 0.25), (D, zt), (0, zt)], x0, x1, M["chapa"], hc)
        # ventanas laterales (lámina: 2 por piso en el lado alto, 2 abajo en el bajo)
        cutters, glass = [], []
        rows = [(1.0, 2.3)] + ([(3.0, 4.3)] if nm == "MuroDer" else [])
        for yc in (D * 0.3, D * 0.7):
            for z0, z1 in rows:
                cutters.append(box("cutL", x0 - 0.1, x1 + 0.1, yc - 0.28, yc + 0.28, FLOOR + z0, FLOOR + z1, coll=hc))
                xm = (x0 + x1) / 2
                glass.append(box("VidrioLat", xm - 0.01, xm + 0.01, yc - 0.28, yc + 0.28, FLOOR + z0, FLOOR + z1, M["vidrio"], hc))
                box("Travesaño", xm - 0.04, xm + 0.04, yc - 0.28, yc + 0.28,
                    FLOOR + (z0 + z1) / 2 - 0.03, FLOOR + (z0 + z1) / 2 + 0.03, M["perfil"], hc)
        cut(wall, cutters)
    box("Losa", 0, L, 0, D, 0.25, FLOOR, M["negro"], hc)

    # Fachada frontal de madera con vanos (cotas de la planta)
    zf = lambda x: roof_under(x)
    front = prism_xz("FachadaFrontal", [(WALL_T, FLOOR), (L - WALL_T, FLOOR), (L - WALL_T, zf(L)), (WALL_T, zf(0))],
                     FRONT_Y, FRONT_Y + 0.15, M["madera"], hc)
    DOOR_H = 2.23
    openings = [(0.27, 2.54, 0, DOOR_H), (3.34, 8.84, 0, DOOR_H), (9.64, 11.91, 0, DOOR_H),
                (9.64, 11.91, 2.78, 3.72)]
    clere = [(3.34, 5.13), (5.21, 6.97), (7.05, 8.84)]
    cutters = []
    for x0, x1, z0, z1 in openings:
        cutters.append(box("cut", x0, x1, FRONT_Y - 0.2, FRONT_Y + 0.4, FLOOR + z0, FLOOR + z1, coll=hc))
    for x0, x1 in clere:
        top = lambda x: zf(x) - 0.22
        cutters.append(prism_xz("cutC", [(x0, FLOOR + 2.33), (x1, FLOOR + 2.33), (x1, top(x1)), (x0, top(x0))],
                                FRONT_Y - 0.2, FRONT_Y + 0.4, coll=hc))
    cut(front, cutters)

    def frame_and_glass(x0, x1, z0, z1, mullions, ztop=None):
        yg = FRONT_Y + 0.07
        if ztop is None:
            mesh_glass = box("VidrioF", x0, x1, yg - 0.005, yg + 0.005, z0, z1, M["vidrio"], hc)
        else:
            mesh_glass = prism_xz("VidrioF", [(x0, z0), (x1, z0), (x1, ztop(x1)), (x0, ztop(x0))],
                                  yg - 0.005, yg + 0.005, M["vidrio"], hc)
        t = 0.05
        box("PerfilInf", x0, x1, yg - 0.04, yg + 0.04, z0, z0 + t, M["perfil"], hc)
        if ztop is None:
            box("PerfilSup", x0, x1, yg - 0.04, yg + 0.04, z1 - t, z1, M["perfil"], hc)
        for xm in [x0 + t / 2, x1 - t / 2] + mullions:
            zt = z1 if ztop is None else ztop(xm)
            box("Montante", xm - t / 2, xm + t / 2, yg - 0.04, yg + 0.04, z0, zt, M["perfil"], hc)
        return mesh_glass

    frame_and_glass(0.27, 2.54, FLOOR, FLOOR + DOOR_H, [1.405])
    frame_and_glass(3.34, 8.84, FLOOR, FLOOR + DOOR_H, [4.24, 5.17, 7.01, 7.93])
    frame_and_glass(9.64, 11.91, FLOOR, FLOOR + DOOR_H, [10.775])
    frame_and_glass(9.64, 11.91, FLOOR + 2.78, FLOOR + 3.72, [])
    for x0, x1 in clere:
        frame_and_glass(x0, x1, FLOOR + 2.33, None, [], ztop=lambda x: zf(x) - 0.22)

    # Fachada posterior (acceso) con puerta y ventanas
    back = prism_xz("FachadaPost", [(WALL_T, FLOOR), (L - WALL_T, FLOOR), (L - WALL_T, zf(L)), (WALL_T, zf(0))],
                    BACK_Y - 0.15, BACK_Y, M["madera"], hc)
    cb = [box("cutB", 7.7, 9.7, BACK_Y - 0.4, BACK_Y + 0.2, FLOOR, FLOOR + 2.4, coll=hc),
          box("cutB", 4.6, 5.6, BACK_Y - 0.4, BACK_Y + 0.2, FLOOR + 1.3, FLOOR + 1.8, coll=hc),
          box("cutB", 2.5, 4.0, BACK_Y - 0.4, BACK_Y + 0.2, FLOOR + 2.4, FLOOR + 2.9, coll=hc)]
    cut(back, cb)
    for x0, x1, z0, z1 in ((7.7, 9.7, 0, 2.4), (4.6, 5.6, 1.3, 1.8), (2.5, 4.0, 2.4, 2.9)):
        box("VidrioB", x0, x1, BACK_Y - 0.08, BACK_Y - 0.07, FLOOR + z0, FLOOR + z1, M["vidrio"], hc)

    # Interior (lo que se ve a través de los ventanales)
    yi0, yi1 = FRONT_Y + 0.15, BACK_Y - 0.15
    box("PisoInt", WALL_T, L - WALL_T, yi0, yi1, FLOOR - 0.01, FLOOR + 0.005, M["piso"], hc)
    prism_xz("CieloInt", [(WALL_T, zf(0) - 0.02), (L - WALL_T, zf(L) - 0.02), (L - WALL_T, zf(L)), (WALL_T, zf(0))],
             yi0, yi1, M["maderaInt"], hc)
    for x in (WALL_T, L - WALL_T - 0.02):
        box("RevInt", x, x + 0.02, yi0, yi1, FLOOR, roof_top(x), M["maderaInt"], hc)
    for x0 in (3.2, 8.84):
        box("Tabique", x0, x0 + 0.14, yi0, yi1, FLOOR, zf(x0 + 0.07), M["maderaInt"], hc)
    box("Altillo", 8.84, L - WALL_T, yi0, yi1, FLOOR + 2.55, FLOOR + 2.75, M["maderaInt"], hc)
    box("Baranda", 8.84, L - WALL_T, yi0 + 0.6, yi0 + 0.64, FLOOR + 3.6, FLOOR + 3.65, M["perfil"], hc)
    # muebles
    box("Sofa", 4.3, 6.6, 3.0, 3.9, FLOOR, FLOOR + 0.45, M["tela"], hc)
    box("SofaResp", 4.3, 6.6, 3.7, 3.95, FLOOR, FLOOR + 0.85, M["tela"], hc)
    box("Mesa", 4.9, 6.0, 2.2, 2.8, FLOOR, FLOOR + 0.38, M["maderaOsc"], hc)
    box("Isla", 5.0, 7.2, 4.6, 5.3, FLOOR, FLOOR + 0.92, M["piedra"], hc)
    box("Muebles", 3.4, 8.6, 5.65, 5.99, FLOOR, FLOOR + 0.9, M["maderaOsc"], hc)
    box("Cuadro", 7.3, 8.3, 5.98, 6.0, FLOOR + 1.4, FLOOR + 2.1, M["cuadro"], hc)
    for x0, x1 in ((0.6, 2.6), (9.4, 11.4)):
        box("Cama", x0, x1, 3.2, 5.4, FLOOR, FLOOR + 0.55, M["tela"], hc)
        box("Cabecera", x0, x1, 5.4, 5.5, FLOOR, FLOOR + 1.1, M["maderaOsc"], hc)
    box("SofaAlt", 9.3, 11.5, 4.9, 5.7, FLOOR + 2.75, FLOOR + 3.5, M["telaAzul"], hc)
    for i, x in enumerate((5.4, 6.1, 6.8)):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.17, location=(x, 4.95, FLOOR + 2.5))
        bpy.context.object.data.materials.append(M["lampara"])
    for x, y, z, p in ((1.6, 3.5, 2.3, 120), (6.0, 3.5, 3.2, 260), (10.5, 3.5, 2.3, 110), (10.5, 3.5, 4.4, 120)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, FLOOR + z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.5
        lt.data.color = WARM
    # spots empotrados (puntos emisivos en el cielo)
    for x in [1.0, 2.2, 4.0, 5.5, 7.0, 8.2, 9.8, 11.2]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.05, depth=0.02,
                                            location=(x, FRONT_Y + 0.9, zf(x) - 0.03))
        bpy.context.object.data.materials.append(M["spot"])

    # Apliques de muro en la fachada (luz arriba y abajo, como en los renders)
    for x in (2.94, 9.24):
        box("Aplique", x - 0.06, x + 0.06, FRONT_Y - 0.1, FRONT_Y, FLOOR + 1.9, FLOOR + 2.15, M["negro"], hc)
        for direction, dz in ((math.pi, -0.02), (0, 0.27)):
            bpy.ops.object.light_add(type="SPOT", location=(x, FRONT_Y - 0.08, FLOOR + 1.9 + dz))
            sp = bpy.context.object
            sp.rotation_euler = (direction, 0, 0)
            sp.data.energy, sp.data.spot_size, sp.data.spot_blend = 35, math.radians(35), 0.6
            sp.data.color = WARM
            sp.data.shadow_soft_size = 0.02

    # Terraza frontal (2 m + 0,9 m cubierta), porch posterior, pilotes y escaleras
    box("Terraza", 0, L, -2.0, FRONT_Y, FLOOR - 0.1, FLOOR + 0.005, M["deck"], hc)
    box("Porch", WALL_T, L - WALL_T, BACK_Y, D, FLOOR - 0.1, FLOOR + 0.005, M["deck"], hc)
    box("CantoTerraza", 0, L, -2.04, -2.0, FLOOR - 0.16, FLOOR + 0.005, M["maderaOsc"], hc)
    for x in [0.1 + i * (L - 0.2) / 8 for i in range(9)]:
        for y in (-1.9, 0.1, D / 2, D - 0.1):
            box("Pilote", x - 0.08, x + 0.08, y - 0.08, y + 0.08, -0.4, 0.27, M["pilote"], hc)
    for i, (h, d) in enumerate(((0.375, 0.3), (0.25, 0.6), (0.125, 0.9))):
        box("Escalon", 0.05, 2.0, -2.0 - d, -2.0 - d + 0.3, h - 0.04, h, M["deck"], hc)
        box("Escalon", 7.7, 9.7, D + d - 0.3, D + d, h - 0.04, h, M["deck"], hc)
    for i in range(10):
        x = 0.6 + i * 1.22
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.035, depth=0.012, location=(x, -1.82, FLOOR + 0.006))
        bpy.context.object.data.materials.append(M["ledDeck"])
    # sillas de terraza (como en los renders)
    for x in (10.2, 11.3):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.42, location=(x, -0.6, FLOOR + 0.55))
        ch = bpy.context.object
        ch.scale = (1, 1, 0.55)
        ch.data.materials.append(M["perfil"])
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.3, depth=0.04, location=(10.75, -1.1, FLOOR + 0.5))
    bpy.context.object.data.materials.append(M["perfil"])
    return hc


# --------------------------------------------------------------- paisaje
LAKE = Vector((150, 320))


def mountain_h(x, y):
    """Cordillera: crestas con deformación de dominio, cumbres afiladas y erosión fina."""
    q = Vector((x / 1500, y / 1500, 3.1))
    w = noise.noise_vector(q * 0.7) * 0.4
    r = noise.ridged_multi_fractal(q + w, 0.85, 2.05, 7, 1.0, 2.2)
    peaks = max(0.0, r) ** 1.35 * 210
    gullies = noise.ridged_multi_fractal(Vector((x / 220, y / 220, 9.3)), 0.9, 2.2, 5, 1.0, 2.0)
    return peaks + gullies * 14 * min(1.0, peaks / 120)


def terrain_h(x, y):
    p = Vector((x, y))
    d = (p - Vector((L / 2, D / 2))).length
    flat = max(0.0, min(1.0, (d - 25) / 120))
    hills = noise.fractal(Vector((x / 180, y / 180, 0.3)), 0.6, 2.0, 5) * 12 * flat
    mtn_mask = max(0.0, min(1.0, (d - 1100) / 1300))
    # cordillera sólo al fondo y a los lados: el valle queda abierto hacia el sol
    cos_back = (y - D / 2) / max(d, 1.0)
    mtn_mask *= max(0.0, min(1.0, (cos_back + 0.25) / 0.6))
    # valle abierto en la dirección del sol poniente (si no, la cordillera lo tapa)
    ang = math.degrees(math.atan2(x - L / 2, y - D / 2)) - SUN_AZ
    ang = (ang + 180) % 360 - 180
    mtn_mask *= 1 - 0.92 * math.exp(-(ang / 22) ** 2)
    mtn = mountain_h(x, y) * mtn_mask if mtn_mask > 0 else 0.0
    lake_d = (p - LAKE).length
    basin = -6 * max(0.0, 1 - (lake_d / 230) ** 2)
    return hills + mtn + basin + noise.noise(Vector((x / 6, y / 6, 0))) * 0.15 * min(1, d / 15)


def build_landscape(M):
    lc = bpy.data.collections.new("Paisaje")
    bpy.context.scene.collection.children.link(lc)
    # malla de terreno con densidad variable (más fina cerca de la casa)
    steps = []
    x = 0.0
    while x < 2600:
        steps.append(x)
        x += 0.6 + x * 0.035
    steps = [v for v in steps if v < 560]
    coords = sorted(set([-s for s in steps] + steps))
    cx, cy = L / 2, D / 2
    verts = [(cx + u, cy + v, terrain_h(cx + u, cy + v)) for v in coords for u in coords]
    n = len(coords)
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
             for j in range(n - 1) for i in range(n - 1)
             if math.hypot((coords[i] + coords[i + 1]) / 2, (coords[j] + coords[j + 1]) / 2) < 545]
    mesh_obj("Terreno", verts, faces, M["terreno"], lc, smooth=True)
    # cordillera: malla polar (0,3° en azimut, anillos cada vez más espaciados)
    radii, r = [], 520.0
    while r < 4200:
        radii.append(r)
        r += 4 + r * 0.008
    na = 1200
    verts = []
    for r in radii:
        for k in range(na):
            a = 2 * math.pi * k / na
            x, y = cx + r * math.sin(a), cy + r * math.cos(a)
            verts.append((x, y, terrain_h(x, y)))
    faces = [(j * na + k, j * na + (k + 1) % na, (j + 1) * na + (k + 1) % na, (j + 1) * na + k)
             for j in range(len(radii) - 1) for k in range(na)]
    mesh_obj("Cordillera", verts, faces, M["terreno"], lc, smooth=True)
    # lago
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=240, fill_type="NGON", location=(LAKE.x, LAKE.y, -1.6))
    lake = bpy.context.object
    lake.data.materials.append(M["agua"])
    return lc


def grass_mat():
    m, n, l = new_mat("Pasto")
    b = n["Principled BSDF"]
    info = n.new("ShaderNodeObjectInfo")
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.12
    l.new(info.outputs["Location"], nz.inputs["Vector"])
    add = n.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.5
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.25, (0.03, 0.075, 0.012, 1)
    e[1].position, e[1].color = 0.97, (0.26, 0.22, 0.08, 1)
    e.new(0.55).color = (0.07, 0.13, 0.02, 1)
    e.new(0.8).color = (0.12, 0.17, 0.035, 1)
    l.new(nz.outputs["Fac"], add.inputs[0])
    l.new(info.outputs["Random"], add.inputs[2])
    l.new(add.outputs[0], ramp.inputs["Fac"])
    base = n.new("ShaderNodeMapRange")
    base.inputs[1].default_value, base.inputs[2].default_value = 0.0, 0.2
    base.inputs[3].default_value, base.inputs[4].default_value = 0.35, 1.0
    l.new(sep.outputs["Z"], base.inputs[0])
    mul = n.new("ShaderNodeMixRGB")
    mul.blend_type = "MULTIPLY"
    mul.inputs["Fac"].default_value = 1.0
    l.new(ramp.outputs["Color"], mul.inputs["Color1"])
    l.new(base.outputs[0], mul.inputs["Color2"])
    l.new(mul.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.65
    tr = n.new("ShaderNodeBsdfTranslucent")
    l.new(mul.outputs["Color"], tr.inputs["Color"])
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.3
    l.new(b.outputs[0], mix.inputs[1])
    l.new(tr.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def grass_tuft(M):
    """Mata de pasto: hojas finas y curvas (dos tramos), con distinta altura e inclinación."""
    verts, faces = [], []
    for k in range(34):
        a = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, 0.09)
        x, y = r * math.cos(a), r * math.sin(a)
        h = random.uniform(0.04, 0.15)
        lean = random.uniform(0.02, 0.07) * (h / 0.12)
        la = random.uniform(0, 2 * math.pi)
        w = random.uniform(0.0025, 0.0045)
        px, py = -math.sin(la) * w, math.cos(la) * w
        dx, dy = math.cos(la), math.sin(la)
        i = len(verts)
        verts += [(x - px, y - py, 0), (x + px, y + py, 0),
                  (x + dx * lean * 0.35 + px * 0.7, y + dy * lean * 0.35 + py * 0.7, h * 0.6),
                  (x + dx * lean * 0.35 - px * 0.7, y + dy * lean * 0.35 - py * 0.7, h * 0.6),
                  (x + dx * lean, y + dy * lean, h)]
        faces += [(i, i + 1, i + 2, i + 3), (i + 3, i + 2, i + 4)]
    t = mesh_obj("MataPasto", verts, faces, M["pasto"])
    t.hide_render = True
    t.hide_viewport = True
    return t


def build_grass(M):
    """Parche de pasto (matas instanciadas con nodos de geometría)."""
    xs = [-34 + i * 1.0 for i in range(81)]
    ys = [-40 + j * 1.0 for j in range(64)]
    verts = [(x, y, terrain_h(x, y) + 0.01) for y in ys for x in xs]
    n = len(xs)
    faces = []
    for j in range(len(ys) - 1):
        for i in range(n - 1):
            xc, yc = xs[i] + 0.5, ys[j] + 0.5
            if -0.2 < xc < L + 0.2 and -2.9 < yc < D + 1.0:
                continue
            faces.append((j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i))
    g = mesh_obj("Pasto", verts, faces, M["terreno"])
    if g.data.polygons[0].normal.z < 0:
        g.data.flip_normals()
    tuft = grass_tuft(M)
    ng = bpy.data.node_groups.new("Pasto", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.inputs["Density"].default_value = 28
    # densidad irregular (manchones)
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.25
    mr = N.new("ShaderNodeMapRange")
    mr.inputs[1].default_value, mr.inputs[2].default_value = 0.35, 0.6
    mr.inputs[3].default_value, mr.inputs[4].default_value = 30, 70
    Lk.new(nz.outputs["Fac"], mr.inputs[0])
    Lk.new(mr.outputs[0], dist.inputs["Density"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs[0].default_value = tuft
    rrot = N.new("FunctionNodeRandomValue")
    rrot.data_type = "FLOAT_VECTOR"
    rrot.inputs["Max"].default_value = (0.15, 0.15, 6.28)
    rsc = N.new("FunctionNodeRandomValue")
    rsc.data_type = "FLOAT"
    for sk in rsc.inputs:
        if sk.type == "VALUE" and sk.name in ("Min", "Max"):
            sk.default_value = 0.6 if sk.name == "Min" else 1.5
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    Lk.new(dist.outputs["Points"], inst.inputs["Points"])
    Lk.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    Lk.new(rrot.outputs[0], inst.inputs["Rotation"])
    Lk.new(next(o for o in rsc.outputs if o.type == "VALUE"), inst.inputs["Scale"])
    Lk.new(gi.outputs[0], join.inputs[0])
    Lk.new(inst.outputs[0], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = g.modifiers.new("Pasto", "NODES")
    md.node_group = ng


def make_tree_variants(M, coll):
    """Pinos y un ciprés: conos subdivididos con desplazamiento orgánico."""
    variants = []
    tex = bpy.data.textures.new("ramas", "CLOUDS")
    tex.noise_scale = 0.35
    tex.noise_depth = 3
    tex_fine = bpy.data.textures.new("ramitas", "CLOUDS")
    tex_fine.noise_scale = 0.09
    tex_fine.noise_depth = 2

    def tree(name, height, radius, layers, slender=False, seed=0):
        parts = []
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius * 0.08, depth=height * 0.35,
                                            location=(0, 0, height * 0.17))
        trunk = bpy.context.object
        trunk.data.materials.append(M["tronco"])
        parts.append(trunk)
        for k in range(layers):
            f = k / layers
            r = radius * (1 - f) ** (0.6 if slender else 0.9) + 0.15
            z0 = height * (0.12 + 0.82 * f) if not slender else height * (0.04 + 0.85 * f)
            dz = height * (0.36 if not slender else 0.3)
            bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=r, radius2=0.05, depth=dz,
                                            location=(0, 0, z0 + dz / 2))
            c = bpy.context.object
            c.rotation_euler.z = random.random() * 6.28
            c.data.materials.append(M["follaje"])
            parts.append(c)
        bpy.ops.object.select_all(action="DESELECT")
        for p in parts:
            p.select_set(True)
        bpy.context.view_layer.objects.active = parts[-1]
        bpy.ops.object.join()
        t = bpy.context.object
        t.name = name
        bpy.context.scene.cursor.location = (0, 0, 0)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        sub = t.modifiers.new("sub", "SUBSURF")
        sub.levels = sub.render_levels = 3
        disp = t.modifiers.new("disp", "DISPLACE")
        disp.texture, disp.strength, disp.mid_level = tex, radius * 0.35, 0.5
        disp.texture_coords = "LOCAL"
        fine = t.modifiers.new("fine", "DISPLACE")
        fine.texture, fine.strength, fine.mid_level = tex_fine, radius * 0.12, 0.5
        fine.texture_coords = "LOCAL"
        bpy.ops.object.modifier_apply(modifier="sub")
        bpy.ops.object.modifier_apply(modifier="disp")
        bpy.ops.object.modifier_apply(modifier="fine")
        bpy.ops.object.shade_smooth()
        for c2 in t.users_collection:
            c2.objects.unlink(t)
        coll.objects.link(t)
        t.location = (0, 0, 0)
        return t

    for i, (h, r, ly) in enumerate(((11, 3.0, 7), (14, 3.4, 8), (8, 2.6, 6))):
        variants.append(tree(f"Pino{i}", h, r, ly, seed=i))
    cypress = tree("Cipres", 11, 1.25, 9, slender=True)
    return variants, cypress


def instance(src_coll_obj, loc, scale, rot, coll):
    ob = bpy.data.objects.new("inst", src_coll_obj.data)
    ob.location, ob.scale = loc, (scale, scale, scale * random.uniform(0.9, 1.15))
    ob.rotation_euler.z = rot
    coll.objects.link(ob)
    return ob


def in_sun_corridor(x, y, max_r):
    """Sector por donde entra el sol: sin árboles cercanos para que la casa quede iluminada."""
    dx, dy = x - L / 2, y - D / 2
    r = math.hypot(dx, dy)
    ang = (math.degrees(math.atan2(dx, dy)) - SUN_AZ + 180) % 360 - 180
    return r < max_r and abs(ang) < 32


def scatter_trees(variants, coll, avoid, far_variants=None):
    placed = 0
    while placed < 1700:
        ang = random.uniform(0, 2 * math.pi)
        r = 32 + (random.random() ** 1.3) * 900
        x, y = L / 2 + r * math.cos(ang), D / 2 + r * math.sin(ang)
        z = terrain_h(x, y)
        if z < -0.8 or z > 160:
            continue
        if any((Vector((x, y)) - a).length < rad for a, rad in avoid):
            continue
        # el frente (hacia la cámara) queda más despejado, como un claro
        if r < 90 and random.random() < (0.9 if y < -5 else 0.6):
            continue
        if in_sun_corridor(x, y, 280):
            continue
        if far_variants and r > 220:
            instance(random.choice(far_variants), (x, y, z - 0.3), random.uniform(0.9, 1.5), random.uniform(0, 6.3), coll)
        else:
            instance(random.choice(variants), (x, y, z - 0.3), random.uniform(0.75, 1.2), random.uniform(0, 6.3), coll)
        placed += 1
    # pinos cercanos detrás y a los lados de la casa (encuadre de los renders)
    for x, y, s in ((-7, 10, 1.2), (-4, 19, 1.4), (19, 9, 1.1), (22, 16, 1.4), (-13, 3, 1.3),
                    (27, -1, 1.1), (-10, 24, 1.2), (30, 22, 1.3)):
        if not in_sun_corridor(x, y, 280):
            instance(random.choice(variants), (x, y, terrain_h(x, y) - 0.2), s * 0.8, random.uniform(0, 6.3), coll)


def scatter_small(M, coll, shrubs):
    # arbustos (Sapling) y rocas alrededor de la casa y del claro
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
    rock = bpy.context.object
    rock.name = "Roca"
    d = rock.modifiers.new("d", "DISPLACE")
    d.texture = bpy.data.textures.new("roc", "VORONOI")
    d.strength = 0.35
    bpy.ops.object.modifier_apply(modifier="d")
    rock.data.materials.append(M["roca"])
    d = rock.modifiers.new("d2", "DISPLACE")
    d.texture = bpy.data.textures.new("roc2", "CLOUDS")
    d.texture.noise_scale = 0.25
    d.strength = 0.12
    rock.modifiers.new("sub", "SUBSURF").render_levels = 1
    bpy.ops.object.modifier_apply(modifier="d2")
    bpy.ops.object.modifier_apply(modifier="sub")
    rock.hide_render = True
    rock.hide_viewport = True
    for _ in range(170):
        x, y = random.uniform(-14, 26), random.uniform(-16, 18)
        if -1.2 < x < L + 1.2 and -3.2 < y < D + 1.4:
            continue
        if min((cam_pose(u / 10)[0].xy - Vector((x, y))).length for u in range(11)) < 3.5:
            continue
        if random.random() < 0.7:
            o = instance(random.choice(shrubs), (x, y, terrain_h(x, y) - 0.05), random.uniform(0.6, 1.5),
                         random.uniform(0, 6.3), coll)
        else:
            s = random.uniform(0.08, 0.25)
            o = instance(rock, (x, y, terrain_h(x, y) + s * 0.2), s, random.uniform(0, 6.3), coll)
            o.scale.z *= 0.6
        o.hide_render = False
    # arbustos al pie de la terraza
    for x in [-0.7, 2.6, 4.5, 7.5, 10.4, 12.8]:
        o = instance(random.choice(shrubs), (x, -2.6 - random.random() * 0.6, 0.0), random.uniform(0.9, 1.3),
                     random.uniform(0, 6.3), coll)
        o.hide_render = False
    return shrubs[0], rock


# --------------------------------------------------------------- cámara
FPS, SECS = 24, 8.0
PIVOT = Vector((L / 2, D / 2 - 0.5, 0))


def ease(t):
    return t * t * (3 - 2 * t)


def cam_pose(u):
    """Órbita baja de izquierda a derecha, acercándose (como la referencia)."""
    k = ease(u)
    th = math.radians(-42 + 56 * k)
    R = 31.0 - 4.0 * k
    z = 6.2 - 1.2 * k + 0.1 * math.sin(u * 7.0)
    pos = PIVOT + Vector((R * math.sin(th), -R * math.cos(th), 0))
    pos.z = z
    tgt = Vector((L / 2, D / 2 - 0.5, 2.6))
    return pos, tgt


def build_camera(cypress_src, coll, shrub, rock):
    cam_data = bpy.data.cameras.new("Dron")
    cam_data.lens = 24
    cam_data.clip_end = 30000
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36
    cam = bpy.data.objects.new("Dron", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    nframes = int(FPS * SECS)
    for f in range(nframes):
        u = f / (nframes - 1)
        pos, tgt = cam_pose(u)
        cam.location = pos
        d = tgt - pos
        q = d.to_track_quat("-Z", "Y")
        e = q.to_euler()
        e.y += math.radians(0.6 * math.sin(u * 5.3))  # leve balanceo del dron
        cam.rotation_euler = e
        cam.keyframe_insert("location", frame=f + 1)
        cam.keyframe_insert("rotation_euler", frame=f + 1)
    # Ciprés en primer plano que cruza el cuadro (como la palmera del original)
    pos, tgt = cam_pose(0.0)
    d = (tgt - pos).xy.normalized()
    ang = math.radians(24)  # a la izquierda del eje de la cámara
    side = Vector((d.x * math.cos(ang) - d.y * math.sin(ang), d.x * math.sin(ang) + d.y * math.cos(ang)))
    p = pos.xy + side * 12.0
    p = Vector((p.x, p.y, 0))
    cyp = instance(cypress_src, (p.x, p.y, terrain_h(p.x, p.y) - 0.2), 1.0, 0.4, coll)
    cyp.scale = (1.0, 1.0, 1.0)
    # anillo de piedras a su alrededor (detalle de la referencia)
    for i in range(16):
        a = i / 16 * 2 * math.pi
        rx, ry = p.x + 1.7 * math.cos(a), p.y + 1.7 * math.sin(a)
        o = instance(rock, (rx, ry, terrain_h(rx, ry) + 0.03), random.uniform(0.13, 0.2), random.uniform(0, 6), coll)
        o.hide_render = False
        o.scale.z *= 0.6
    o = instance(shrub, (p.x + 1.0, p.y + 0.8, 0.0), 1.1, 0, coll)
    o.hide_render = False
    return cam, p


# ---------------------------------------------------------------- mundo
def build_world():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Cielo")
    sc.world = w
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    bg = n["Background"]
    sky = n.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING" if bpy.app.version >= (5, 0) else "NISHITA"
    sky.sun_elevation = math.radians(SUN_ELEV)
    sky.sun_rotation = math.radians(SUN_AZ)
    sky.altitude = 400
    sky.air_density = 1.2
    if hasattr(sky, "aerosol_density"):
        sky.aerosol_density = 1.6
    else:
        sky.dust_density = 3.5
    sky.sun_size = math.radians(1.2)
    sky.sun_disc = False  # la luz directa la aporta la lámpara solar
    # degradado de atardecer: horizonte anaranjado, cenit azul suave
    tcw = n.new("ShaderNodeTexCoord")
    sepw = n.new("ShaderNodeSeparateXYZ")
    l.new(tcw.outputs["Generated"], sepw.inputs[0])
    grad = n.new("ShaderNodeValToRGB")
    ge = grad.color_ramp.elements
    ge[0].position, ge[0].color = 0.0, (1.6, 0.8, 0.45, 1)
    ge[1].position, ge[1].color = 0.45, (0.85, 0.88, 1.05, 1)
    ge.new(0.12).color = (1.25, 0.88, 0.7, 1)
    l.new(sepw.outputs["Z"], grad.inputs["Fac"])
    warm = n.new("ShaderNodeMixRGB")
    warm.blend_type = "MULTIPLY"
    warm.inputs["Fac"].default_value = 1.0
    l.new(sky.outputs[0], warm.inputs["Color1"])
    l.new(grad.outputs["Color"], warm.inputs["Color2"])
    l.new(warm.outputs["Color"], bg.inputs[0])
    bg.inputs[1].default_value = 0.3
    # sol cálido y rasante desde la izquierda: luz lateral de hora dorada
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 14.0
    sun.data.color = (1.0, 0.56, 0.27)  # luz de atardecer, dorado anaranjado
    sun.data.angle = math.radians(1.0)
    # misma dirección que el sol del cielo (rotación 0 = +Y, positiva hacia +X)
    e, a = math.radians(SUN_ELEV), math.radians(SUN_AZ)
    to_sun = Vector((math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)))
    sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    # capa de nubes (como el cielo de la referencia), iluminada por el sol
    m, n, l = new_mat("Nubes")
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (1, 1, 1, 1)
    b.inputs["Roughness"].default_value = 1.0
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1, 1.8, 1)
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 7
    nz.inputs["Detail"].default_value = 12
    nz.inputs["Roughness"].default_value = 0.62
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.56
    ramp.color_ramp.elements[1].position = 0.74
    l.new(tc.outputs["Generated"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], nz.inputs["Vector"])
    l.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    # las nubes no proyectan sombra (el sol sigue iluminando el valle)
    lp = n.new("ShaderNodeLightPath")
    inv = n.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    l.new(lp.outputs["Is Shadow Ray"], inv.inputs[1])
    cov = n.new("ShaderNodeMath")
    cov.operation = "MULTIPLY"
    l.new(ramp.outputs["Color"], cov.inputs[0])
    l.new(inv.outputs[0], cov.inputs[1])
    l.new(cov.outputs[0], mx.inputs[0])
    l.new(tr.outputs[0], mx.inputs[1])
    l.new(b.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    bpy.ops.mesh.primitive_plane_add(size=9000, location=(L / 2, 1500, 900))
    clouds = bpy.context.object
    clouds.name = "Nubes"
    clouds.data.materials.append(m)
    clouds.visible_shadow = False
    clouds.visible_diffuse = False
    w.mist_settings.start = 35
    w.mist_settings.depth = 1400
    w.mist_settings.falloff = "LINEAR"


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = int(opts["samples"])
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.03
    cy.max_bounces = 4
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 2
    cy.transparent_max_bounces = 12
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    w, h = (int(v) for v in opts["res"].split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    # reanudable: no vuelve a renderizar cuadros ya guardados
    sc.render.use_overwrite = False
    sc.render.use_placeholder = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.05
    if hasattr(sc.view_settings, "use_white_balance"):
        sc.view_settings.use_white_balance = True
        sc.view_settings.white_balance_temperature = WB_TEMP
    sc.view_layers[0].use_pass_mist = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.35
    # bruma atmosférica en compositor (no afecta al cielo)
    if bpy.app.version >= (5, 0):
        nt = bpy.data.node_groups.new("Bruma", "CompositorNodeTree")
        nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        sc.compositing_node_group = nt
        comp_in = nt.nodes.new("NodeGroupOutput").inputs[0]
        math_t = "ShaderNodeMath"
    else:
        sc.use_nodes = True
        nt = sc.node_tree
        for nd in list(nt.nodes):
            nt.nodes.remove(nd)
        comp_in = nt.nodes.new("CompositorNodeComposite").inputs[0]
        math_t = "CompositorNodeMath"
    rl = nt.nodes.new("CompositorNodeRLayers")

    def mnode(op, b):
        nd = nt.nodes.new(math_t)
        nd.operation = op
        nd.inputs[1].default_value = b
        return nd

    lt, pw, amt = mnode("LESS_THAN", 0.999), mnode("POWER", 1.0), mnode("MULTIPLY", 0.45)
    mul = mnode("MULTIPLY", 1.0)
    haze = (0.95, 0.72, 0.55, 1)
    if bpy.app.version >= (5, 0):
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        m_fac, m_a, m_b, m_out = mix.inputs[0], mix.inputs[6], mix.inputs[7], mix.outputs[2]
    else:
        mix = nt.nodes.new("CompositorNodeMixRGB")
        m_fac, m_a, m_b, m_out = mix.inputs[0], mix.inputs[1], mix.inputs[2], mix.outputs[0]
    m_b.default_value = haze
    nt.links.new(rl.outputs["Mist"], lt.inputs[0])
    nt.links.new(rl.outputs["Mist"], pw.inputs[0])
    nt.links.new(pw.outputs[0], mul.inputs[0])
    nt.links.new(lt.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], amt.inputs[0])
    nt.links.new(amt.outputs[0], m_fac)
    nt.links.new(rl.outputs["Image"], m_a)
    nt.links.new(m_out, comp_in)


SK_TEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sketchup_tex")


def img_mat(name, image, size_m, rough=0.6, bump=0.15, rot_z=0.0, tint=(1, 1, 1)):
    """Material con una textura del modelo SketchUp, proyección en caja (tamaño real en metros)."""
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / size_m,) * 3
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rot_z))
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(SK_TEX, image), check_existing=True)
    img.projection = "BOX"
    img.projection_blend = 0.15
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], img.inputs["Vector"])
    col = n.new("ShaderNodeMixRGB")
    col.blend_type = "MULTIPLY"
    col.inputs["Fac"].default_value = 1.0
    col.inputs["Color2"].default_value = (*tint, 1)
    l.new(img.outputs["Color"], col.inputs["Color1"])
    l.new(col.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    if bump:
        bm = n.new("ShaderNodeBump")
        bm.inputs["Strength"].default_value = bump
        l.new(img.outputs["Color"], bm.inputs["Height"])
        l.new(bm.outputs["Normal"], b.inputs["Normal"])
    return m


def materials():
    M = {}
    M["negro"] = principled("NegroMarco", (0.012, 0.012, 0.013), 0.5)
    # texturas del modelo SketchUp de Casa Cipres
    M["chapa"] = img_mat("MaderaNegra", "tw_face3.png", 1.4, 0.55, 0.25)
    M["madera"] = img_mat("MaderaRevest", "tw_face0.png", 1.4, 0.65, 0.2, tint=(1.0, 0.82, 0.62))
    M["maderaInt"] = img_mat("MaderaInt", "tw_face2.png", 1.4, 0.6, 0.08)
    M["maderaOsc"] = principled("MaderaOsc", (0.12, 0.06, 0.03), 0.5)
    M["deck"] = img_mat("Deck", "tw_face2.png", 1.6, 0.6, 0.3, rot_z=90, tint=(0.62, 0.5, 0.42))
    M["piso"] = img_mat("PisoInt", "tw_face52.png", 1.2, 0.35, 0.03, rot_z=90)
    M["piedra"] = img_mat("Piedra", "tw_face53.png", 1.0, 0.3, 0.05)
    M["pilote"] = principled("Pilote", (0.08, 0.07, 0.06), 0.8)
    M["perfil"] = principled("PerfilNegro", (0.01, 0.01, 0.01), 0.35, 0.6)
    M["vidrio"] = glass_mat()
    M["tela"] = img_mat("TelaClara", "tw_face98.png", 0.4, 0.9, 0.1)
    M["telaAzul"] = img_mat("TelaAzul", "tw_face7.png", 0.6, 0.9, 0.05)
    M["cuadro"] = principled("Cuadro", (0.25, 0.35, 0.4), 0.4)
    M["lampara"] = emit_mat("Lampara", WARM, 12)
    M["spot"] = emit_mat("Spot", (1, 0.8, 0.55), 30)
    M["ledDeck"] = emit_mat("LedDeck", (1, 0.7, 0.4), 40)
    M["follaje"] = foliage_mat("Follaje", (0.012, 0.03, 0.014), (0.05, 0.08, 0.03))
    M["arbusto"] = foliage_mat("Arbusto", (0.03, 0.05, 0.015), (0.1, 0.12, 0.04))
    M["tronco"] = principled("Tronco", (0.08, 0.05, 0.03), 0.9)
    M["roca"] = principled("Roca", (0.16, 0.14, 0.12), 0.85)
    M["pasto"] = grass_mat()
    M["terreno"] = terrain_mat()
    M["agua"] = principled("Agua", (0.02, 0.04, 0.05), 0.04)
    return M


def main():
    reset()
    M = materials()
    build_house(M)
    build_landscape(M)
    lib = bpy.data.collections.new("Biblioteca")
    bpy.context.scene.collection.children.link(lib)
    import vegetacion
    veg = vegetacion.build_library(lib)
    variants = veg["abeto"] * 2 + veg["pino"] + veg["alamo"]
    cypress = veg["cipres"][0]
    lod, _ = make_tree_variants(M, lib)  # versiones livianas para el bosque lejano
    lib.hide_render = True
    lib.hide_viewport = True
    trees = bpy.data.collections.new("Arboles")
    bpy.context.scene.collection.children.link(trees)
    shrub, rock = scatter_small(M, trees, veg["arbusto"])
    cam, cyp = build_camera(cypress, trees, shrub, rock)
    scatter_trees(variants, trees, avoid=[(Vector((cyp.x, cyp.y)), 6)] +
                  [(cam_pose(u / 10)[0].xy, 13) for u in range(11)], far_variants=lod)
    build_grass(M)
    build_world()
    setup_render()
    sc = bpy.context.scene
    f0, f1 = (int(v) for v in opts["frames"].split("-"))
    sc.frame_start, sc.frame_end = f0, f1
    sc.frame_step = int(opts["step"])  # >1 para previsualizaciones rápidas
    sc.render.filepath = opts["out"]
    if opts["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=opts["save"])
    if opts["still"]:
        sc.frame_set(int(opts["still"]))
        sc.render.filepath = opts["out"]
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


main()
