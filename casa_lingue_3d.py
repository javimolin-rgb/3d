"""Escena 3D de Casa Lingue en el campo + vuelo de dron (Blender 4.x / 5.x, Cycles).

Uso:
  blender -b -P casa_lingue_3d.py -- --out frames/ [--res 1080x1920]
          [--samples 32] [--frames 1-192] [--still 120] [--save escena.blend]
  (o con el módulo bpy de PyPI: python casa_lingue_3d.py -- --still 120 ...)

Medidas tomadas de "Planta con Cotas" y "Lámina Casa Lingue" (escala 1:50):
  - ancho 4,40 m (eje X), caja de 8,50 m de fondo (eje Y), frente hacia -Y
  - frente retranqueado 1,10 m (vidriado doble altura con marco negro y
    revestimiento de madera), porch posterior de 0,50 m
  - techo a dos aguas: alero a 4,93 m y cumbrera a 6,15 m sobre el piso
  - piso elevado 0,55 m; terraza de 2 m al frente y pasillo lateral de 1 m
  - entrepiso a 2,30-2,82 m (dormitorio en el 2do piso)
Paisaje: campo chileno a la hora dorada (potreros, álamos, cercos de palo,
fardos, cerros bajos y cordillera al fondo).
"""
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"step": "1", "wb": "7200", "out": "//frames/", "res": "1080x1920", "samples": "32", "frames": "1-192",
        "still": None, "save": None}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(11)
ROOT = os.path.dirname(os.path.abspath(__file__))
PHOTO = os.path.join(ROOT, "assets", "photo")
WB_TEMP = float(opts["wb"])  # balance de blancos cálido
W, D = 4.40, 8.50           # ancho y fondo de la caja (marco negro)
T = 0.20                    # espesor de muros / techo
FLOOR = 0.55                # nivel de piso terminado sobre el terreno
EAVE, RIDGE = 4.93, 6.15    # alero y cumbrera sobre el piso
FRONT_Y = 1.10              # vidriado frontal retranqueado
BACK_Y = D - 0.50           # fachada de acceso (porch)
SLAB0, SLAB1 = 2.30, 2.82   # entrepiso (sobre el piso)
DECK_X1 = W + 1.0           # pasillo lateral de 1 m
WARM = (1.0, 0.62, 0.32)
SUN_ELEV, SUN_AZ = 11.0, 128.0   # sol bajo desde adelante-derecha (azimut desde +Y hacia +X)
SLOPE = (RIDGE - EAVE) / (W / 2)


def roof_out(x):
    """Cara superior del techo (sobre el terreno)."""
    return FLOOR + RIDGE - SLOPE * abs(x - W / 2)


def roof_in(x):
    """Cara inferior del techo / cielo interior."""
    return roof_out(x) - T * math.sqrt(1 + SLOPE ** 2)


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


def cut(obj, cutters):
    for c in cutters:
        m = obj.modifiers.new("cut", "BOOLEAN")
        m.operation, m.solver, m.object = "DIFFERENCE", "EXACT", c
        c.hide_render = True
        c.hide_viewport = True


def gable(x0, x1, z0, top):
    """Pentágono (en XZ) entre x0 y x1, desde z0 hasta la línea de techo `top`."""
    return [(x0, z0), (x1, z0), (x1, top(x1)), (W / 2, top(W / 2)), (x0, top(x0))]


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


def mix_rgb(n, blend="MIX"):
    """Nodo de mezcla de color (compatible 4.x / 5.x). Devuelve (nodo, fac, a, b, out)."""
    mx = n.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = blend
    return mx, mx.inputs[0], mx.inputs[6], mx.inputs[7], mx.outputs[2]


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
    mapg.inputs["Scale"].default_value = {"X": (1, 14, 14), "Y": (14, 1, 14), "Z": (14, 14, 1)}[axis]
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    seam = n.new("ShaderNodeMath")
    seam.operation = "GREATER_THAN"
    seam.inputs[1].default_value = 0.96
    _, fac, ca, cb, out = mix_rgb(n, "MULTIPLY")
    cb.default_value = (0.35, 0.3, 0.25, 1)
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    l.new(tc.outputs["Object"], mapg.inputs["Vector"])
    l.new(mapg.outputs["Vector"], grain.inputs["Vector"])
    l.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    l.new(wave.outputs["Fac"], seam.inputs[0])
    l.new(ramp.outputs["Color"], ca)
    l.new(seam.outputs["Value"], fac)
    l.new(out, b.inputs["Base Color"])
    l.new(seam.outputs["Value"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m


def ribbed_metal(name):
    """Plancha negra acanalada (muros y techo): estrías verticales cada ~7 cm."""
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.016, 0.016, 0.018, 1)
    b.inputs["Roughness"].default_value = 0.4
    b.inputs["Metallic"].default_value = 0.35
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 14
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.4
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


def foliage_mat(name, c1, c2, translucent=0.25):
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
    # hojas a contraluz (translucidez)
    tr = n.new("ShaderNodeBsdfTranslucent")
    l.new(ramp.outputs["Color"], tr.inputs["Color"])
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = translucent
    l.new(b.outputs[0], mix.inputs[1])
    l.new(tr.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def terrain_mat():
    """Potreros: parches de pasto verde, rastrojo dorado y tierra arada; cerros y nieve lejanos."""
    m, n, l = new_mat("Terreno")
    b = n["Principled BSDF"]
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["Position"], sep.inputs[0])
    # parcelas (celdas de Voronoi grandes, levemente deformadas)
    warp = n.new("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = 0.004
    warp_mix = n.new("ShaderNodeVectorMath")
    warp_mix.operation = "MULTIPLY_ADD"
    warp_mix.inputs[1].default_value = (35, 35, 0)
    l.new(warp.outputs["Color"], warp_mix.inputs[0])
    l.new(geo.outputs["Position"], warp_mix.inputs[2])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 0.0065
    l.new(warp_mix.outputs[0], vor.inputs["Vector"])
    fields = n.new("ShaderNodeValToRGB")
    fields.color_ramp.interpolation = "CONSTANT"
    e = fields.color_ramp.elements
    e[0].position, e[0].color = 0.0, (0.09, 0.13, 0.035, 1)      # pradera verde
    e[1].position, e[1].color = 0.82, (0.17, 0.11, 0.06, 1)     # tierra arada
    e.new(0.3).color = (0.36, 0.27, 0.1, 1)                      # rastrojo dorado
    e.new(0.55).color = (0.16, 0.17, 0.05, 1)                    # pasto seco / verde oliva
    l.new(vor.outputs["Color"], fields.inputs["Fac"])
    # variación fina dentro de cada potrero
    fine = n.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 0.35
    fine.inputs["Detail"].default_value = 8
    var = n.new("ShaderNodeMapRange")
    var.inputs[3].default_value, var.inputs[4].default_value = 0.65, 1.25
    l.new(fine.outputs["Fac"], var.inputs[0])
    _, f1, a1, b1, o1 = mix_rgb(n, "MULTIPLY")
    f1.default_value = 1.0
    l.new(fields.outputs["Color"], a1)
    l.new(var.outputs[0], b1)
    # cerca de la casa: pasto fotográfico CC0 en dos escalas (como en Casa Cipres)
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
    _, fp, ap, bp, op = mix_rgb(n)
    fp.default_value = 0.45
    l.new(p1.outputs["Color"], ap)
    l.new(p2.outputs["Color"], bp)
    hsv = n.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 0.8
    hsv.inputs["Value"].default_value = 0.6
    hsv.inputs["Hue"].default_value = 0.49
    l.new(op, hsv.inputs["Color"])
    big = n.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.06
    big.inputs["Detail"].default_value = 6
    l.new(tc.outputs["Object"], big.inputs["Vector"])
    dry_f = n.new("ShaderNodeMapRange")
    dry_f.inputs[1].default_value, dry_f.inputs[2].default_value = 0.5, 0.68
    dry_f.inputs[4].default_value = 0.6
    l.new(big.outputs["Fac"], dry_f.inputs[0])
    _, fd, ad, bd, od = mix_rgb(n, "MULTIPLY")
    bd.default_value = (1.35, 0.95, 0.55, 1)
    l.new(dry_f.outputs[0], fd)
    l.new(hsv.outputs["Color"], ad)
    geo_d = n.new("ShaderNodeVectorMath")
    geo_d.operation = "LENGTH"
    l.new(geo.outputs["Position"], geo_d.inputs[0])
    near = n.new("ShaderNodeMapRange")
    near.inputs[1].default_value, near.inputs[2].default_value = 60, 140
    near.inputs[3].default_value, near.inputs[4].default_value = 1.0, 0.0
    l.new(geo_d.outputs["Value"], near.inputs[0])
    _, f2, a2, b2, o2 = mix_rgb(n)
    l.new(near.outputs[0], f2)
    l.new(o1, a2)
    l.new(od, b2)
    # cerros boscosos -> roca -> nieve, según altura
    rock_c = n.new("ShaderNodeValToRGB")
    rock_c.color_ramp.elements[0].color = (0.03, 0.03, 0.035, 1)
    rock_c.color_ramp.elements[1].color = (0.2, 0.18, 0.16, 1)
    l.new(fine.outputs["Fac"], rock_c.inputs["Fac"])
    h_rock = n.new("ShaderNodeMapRange")
    h_rock.inputs[1].default_value, h_rock.inputs[2].default_value = 35, 160
    l.new(sep.outputs["Z"], h_rock.inputs[0])
    _, f3, a3, b3, o3 = mix_rgb(n)
    l.new(h_rock.outputs[0], f3)
    l.new(o2, a3)
    l.new(rock_c.outputs["Color"], b3)
    snow_n = n.new("ShaderNodeMath")
    snow_n.operation = "MULTIPLY_ADD"
    snow_n.inputs[1].default_value = 260
    l.new(fine.outputs["Fac"], snow_n.inputs[0])
    l.new(sep.outputs["Z"], snow_n.inputs[2])
    h_snow = n.new("ShaderNodeMapRange")
    h_snow.inputs[1].default_value, h_snow.inputs[2].default_value = 700, 820
    l.new(snow_n.outputs[0], h_snow.inputs[0])
    nrm = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["True Normal"], nrm.inputs[0])
    sn = n.new("ShaderNodeMapRange")
    sn.inputs[1].default_value, sn.inputs[2].default_value = 0.55, 0.75
    l.new(nrm.outputs["Z"], sn.inputs[0])
    snow = n.new("ShaderNodeMath")
    snow.operation = "MULTIPLY"
    l.new(h_snow.outputs[0], snow.inputs[0])
    l.new(sn.outputs[0], snow.inputs[1])
    _, f4, a4, b4, o4 = mix_rgb(n)
    b4.default_value = (0.8, 0.83, 0.88, 1)
    l.new(snow.outputs[0], f4)
    l.new(o3, a4)
    l.new(o4, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.92
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.4
    l.new(p1.outputs["Color"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def gravel_mat():
    m, n, l = new_mat("Maicillo")
    b = n["Principled BSDF"]
    v = n.new("ShaderNodeTexVoronoi")
    v.inputs["Scale"].default_value = 45
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.13, 0.095, 0.065, 1)
    ramp.color_ramp.elements[1].color = (0.32, 0.25, 0.18, 1)
    l.new(v.outputs["Distance"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.5
    l.new(v.outputs["Distance"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.95
    return m


# ------------------------------------------------------------------- casa
def build_house(M):
    hc = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(hc)
    z_in = lambda x: roof_in(x)
    z_out = lambda x: roof_out(x)

    # Marco negro: dos mitades (muro + faldón) de chapa acanalada
    half_l = [(0, FLOOR - 0.2), (T, FLOOR - 0.2), (T, z_in(T)), (W / 2, z_in(W / 2)),
              (W / 2, z_out(W / 2)), (0, z_out(0))]
    half_r = [(W - x, z) for x, z in half_l]
    shell_l = prism_xz("MarcoIzq", half_l, 0, D, M["chapa"], hc)
    shell_r = prism_xz("MarcoDer", half_r, 0, D, M["chapa"], hc)
    # canto frontal del marco (negro liso, como en los renders)
    rim = [(0, FLOOR - 0.2), (T, FLOOR - 0.2), (T, z_in(T)), (W / 2, z_in(W / 2)),
           (W - T, z_in(W - T)), (W - T, FLOOR - 0.2), (W, FLOOR - 0.2), (W, z_out(W)),
           (W / 2, z_out(W / 2)), (0, z_out(0))]
    prism_xz("CantoMarco", rim, -0.01, 0.0, M["negro"], hc)
    box("Losa", 0, W, 0, D, FLOOR - 0.25, FLOOR, M["negro"], hc)

    # revestimiento interior de madera (se ve en el retranqueo y a través de los vidrios)
    lin_l = box("RevIzq", T, T + 0.02, 0, BACK_Y, FLOOR, z_in(T + 0.02), M["maderaRev"], hc)
    lin_r = box("RevDer", W - T - 0.02, W - T, 0, BACK_Y, FLOOR, z_in(W - T - 0.02), M["maderaRev"], hc)
    ceil = [(T, z_in(T) - 0.02), (W / 2, z_in(W / 2) - 0.02), (W - T, z_in(W - T) - 0.02),
            (W - T, z_in(W - T)), (W / 2, z_in(W / 2)), (T, z_in(T))]
    prism_xz("Cielo", ceil, 0, BACK_Y, M["maderaCielo"], hc)

    # ventanas laterales (Elevación Lateral 1 = muro +X, Lateral 2 = muro -X)
    def side_windows(xa, xb, wins, wall_objs):
        cutters = []
        for y0, y1, z0, z1 in wins:
            cutters.append(box("cutLat", xa - 0.1, xb + 0.1, y0, y1, FLOOR + z0, FLOOR + z1, coll=hc))
            xm = (xa + xb) / 2
            box("VidrioLat", xm - 0.006, xm + 0.006, y0, y1, FLOOR + z0, FLOOR + z1, M["vidrio"], hc)
            for yy in (y0, y1 - 0.045):
                box("PerfilLat", xm - 0.03, xm + 0.03, yy, yy + 0.045, FLOOR + z0, FLOOR + z1, M["perfil"], hc)
            for zz in (z0, z1 - 0.045):
                box("PerfilLat", xm - 0.03, xm + 0.03, y0, y1, FLOOR + zz, FLOOR + zz + 0.045, M["perfil"], hc)
        for ob in wall_objs:
            cut(ob, cutters)

    side_windows(W - T - 0.02, W, [
        (2.60, 3.10, 2.88, 4.50), (5.70, 6.20, 2.88, 4.50),   # 2do piso: ventanas altas
        (2.60, 3.10, 1.08, 2.30), (4.50, 5.70, 1.08, 2.30),   # 1er piso
        (6.40, 7.26, 0.00, 2.25),                              # puerta lateral (vidriada)
    ], [shell_r, lin_r])
    side_windows(0, T + 0.02, [(5.95, 6.40, 2.80, 4.50), (5.95, 6.40, 0.30, 2.25)], [shell_l, lin_l])

    # Vidriado frontal doble altura (Elevación Frontal + render)
    yg = FRONT_Y
    x0, x1 = T + 0.02, W - T - 0.02
    prism_xz("VidrioInf", [(x0, FLOOR), (x1, FLOOR), (x1, FLOOR + SLAB0), (x0, FLOOR + SLAB0)],
             yg - 0.005, yg + 0.005, M["vidrio"], hc)
    prism_xz("VidrioSup", gable(x0, x1, FLOOR + SLAB1, lambda x: z_in(x) - 0.02),
             yg - 0.005, yg + 0.005, M["vidrio"], hc)
    t = 0.06
    # banda de entrepiso revestida en madera
    box("BandaEntrepiso", x0, x1, yg - 0.06, yg + 0.06, FLOOR + SLAB0, FLOOR + SLAB1, M["maderaRev"], hc)
    for xm in (x0 + t / 2, W / 2, x1 - t / 2):
        box("Montante", xm - t / 2, xm + t / 2, yg - 0.04, yg + 0.04, FLOOR, FLOOR + SLAB0, M["perfil"], hc)
        box("Montante", xm - t / 2, xm + t / 2, yg - 0.04, yg + 0.04, FLOOR + SLAB1, z_in(xm), M["perfil"], hc)
    for zz in (FLOOR, FLOOR + SLAB0 - t, FLOOR + SLAB1, FLOOR + EAVE - 0.3):
        box("Travesaño", x0, x1, yg - 0.04, yg + 0.04, zz, zz + t, M["perfil"], hc)
    # perfiles inclinados bajo el techo
    for xa, xb in ((x0, W / 2), (W / 2, x1)):
        za, zb = z_in(xa) - 0.02, z_in(xb) - 0.02
        prism_xz("PerfilGable", [(xa, za - t), (xb, zb - t), (xb, zb), (xa, za)],
                 yg - 0.04, yg + 0.04, M["perfil"], hc)

    # Fachada de acceso (Elevación Acceso): madera con puerta y ventanas
    back = prism_xz("FachadaAcceso", gable(T, W - T, FLOOR, z_in), BACK_Y, BACK_Y + 0.12, M["maderaRev"], hc)
    openings = [(0.22, 1.08, 0.0, 2.25), (1.12, 1.68, 1.05, 2.30), (1.84, 3.32, 2.00, 2.50), (2.72, 3.32, 3.60, 4.82)]
    cut(back, [box("cutB", a, b, BACK_Y - 0.2, BACK_Y + 0.3, FLOOR + c, FLOOR + d, coll=hc)
               for a, b, c, d in openings])
    for a, b, c, d in openings[1:]:
        box("VidrioB", a, b, BACK_Y + 0.05, BACK_Y + 0.06, FLOOR + c, FLOOR + d, M["vidrio"], hc)
    box("PuertaAcceso", 0.22, 1.08, BACK_Y + 0.08, BACK_Y + 0.12, FLOOR, FLOOR + 2.25, M["negro"], hc)

    # Interior: pisos, entrepiso con hueco de escalera, muebles
    yi0, yi1 = FRONT_Y + 0.06, BACK_Y
    box("PisoInt", T, W - T, yi0, yi1, FLOOR - 0.01, FLOOR + 0.005, M["piso"], hc)
    box("Entrepiso", T, W - T, 5.3, yi1, FLOOR + SLAB0, FLOOR + SLAB1, M["maderaCielo"], hc)
    box("Entrepiso", 1.0, W - T, yi0, 5.3, FLOOR + SLAB0, FLOOR + SLAB1, M["maderaCielo"], hc)
    box("PisoAlto", T, W - T, yi0, yi1, FLOOR + SLAB1, FLOOR + SLAB1 + 0.005, M["piso"], hc)
    for k in range(13):  # escalera de un tramo junto al muro -X
        y = 5.2 - k * 0.22
        z = FLOOR + (k + 1) * (SLAB1 / 13)
        box("Peldaño", T + 0.02, 0.95, y - 0.24, y, z - 0.04, z, M["maderaOsc"], hc)
    box("Baranda", 1.0, 1.03, 2.6, 5.3, FLOOR + SLAB1, FLOOR + SLAB1 + 0.95, M["perfil"], hc)
    # baranda negra del dormitorio (render)
    box("BarandaDorm", T, W - T, yi0 + 0.25, yi0 + 0.28, FLOOR + SLAB1 + 0.92, FLOOR + SLAB1 + 0.96, M["perfil"], hc)
    for x in (T + 0.05, W / 2, W - T - 0.08):
        box("ParanteDorm", x, x + 0.03, yi0 + 0.25, yi0 + 0.28, FLOOR + SLAB1, FLOOR + SLAB1 + 0.95, M["perfil"], hc)
    # 1er piso: living, comedor, cocina, estufa
    box("Sofa", 1.5, 3.4, 2.9, 3.75, FLOOR, FLOOR + 0.42, M["tela"], hc)
    box("SofaResp", 1.5, 3.4, 3.55, 3.8, FLOOR, FLOOR + 0.82, M["tela"], hc)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.4, depth=0.04, location=(2.4, 2.2, FLOOR + 0.4))
    bpy.context.object.data.materials.append(M["maderaOsc"])
    box("Alfombra", 1.3, 3.6, 1.6, 3.9, FLOOR + 0.005, FLOOR + 0.012, M["alfombra"], hc)
    box("Estufa", 3.6, 4.05, 1.7, 2.1, FLOOR, FLOOR + 0.9, M["negro"], hc)
    box("CañonEstufa", 3.78, 3.88, 1.85, 1.95, FLOOR + 0.9, FLOOR + SLAB0, M["negro"], hc)
    box("MesaComedor", 2.0, 3.4, 4.3, 5.1, FLOOR + 0.72, FLOOR + 0.76, M["maderaOsc"], hc)
    box("Cocina", 2.2, W - T, 5.55, 6.15, FLOOR, FLOOR + 0.9, M["negro"], hc)
    box("Cubierta", 2.2, W - T, 5.55, 6.15, FLOOR + 0.9, FLOOR + 0.94, M["piedra"], hc)
    box("TabiqueCocina", 1.1, W - T, 6.15, 6.25, FLOOR, FLOOR + SLAB0, M["maderaRev"], hc)
    # 2do piso: dormitorio
    zf = FLOOR + SLAB1
    box("Cama", 2.2, 3.9, 3.0, 5.0, zf, zf + 0.5, M["sabanas"], hc)
    box("Respaldo", 2.2, 3.9, 5.0, 5.1, zf, zf + 1.1, M["maderaOsc"], hc)
    box("Pie", 2.2, 3.9, 3.0, 3.6, zf + 0.5, zf + 0.53, M["telaAzul"], hc)
    box("Velador", 3.95, 4.15, 4.6, 5.0, zf, zf + 0.5, M["maderaOsc"], hc)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.15, depth=0.25, location=(4.05, 4.8, zf + 0.8))
    bpy.context.object.data.materials.append(M["lampara"])
    # luces interiores cálidas
    for x, y, z, p in ((2.2, 3.0, 2.1, 140), (2.8, 5.0, 2.1, 110), (2.2, 3.5, 5.0, 110), (2.6, 7.2, 2.1, 50)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, FLOOR + z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.2
        lt.data.color = WARM
    for x, y in ((1.2, 2.2), (3.2, 2.2), (1.2, 4.5), (3.2, 4.5), (2.2, 6.8)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.045, depth=0.02,
                                            location=(x, y, FLOOR + SLAB0 - 0.01))
        bpy.context.object.data.materials.append(M["spot"])
    # spots en el cielo del retranqueo + aplique en el muro (como en el render)
    for x in (1.1, W / 2, 3.3):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.045, depth=0.02,
                                            location=(x, 0.55, z_in(x) - 0.03))
        bpy.context.object.data.materials.append(M["spot"])
    box("Aplique", W - T - 0.1, W - T - 0.02, 0.5, 0.62, FLOOR + 2.0, FLOOR + 2.2, M["negro"], hc)
    for direction, dz in ((math.pi, -0.02), (0, 0.22)):
        bpy.ops.object.light_add(type="SPOT", location=(W - T - 0.12, 0.56, FLOOR + 2.0 + dz))
        sp = bpy.context.object
        sp.rotation_euler = (direction, 0, 0)
        sp.data.energy, sp.data.spot_size, sp.data.spot_blend = 25, math.radians(40), 0.6
        sp.data.color = WARM
        sp.data.shadow_soft_size = 0.02

    # Deck: terraza frontal 2 m, pasillo lateral 1 m, porch; estructura negra y escalera
    box("Deck", 0, DECK_X1, -2.0, D + 0.5, FLOOR - 0.06, FLOOR - 0.0, M["deck"], hc)
    box("CantoDeck", -0.02, DECK_X1 + 0.02, -2.03, D + 0.53, FLOOR - 0.25, FLOOR - 0.05, M["negro"], hc)
    for x in (0.1, W / 2, W - 0.1, DECK_X1 - 0.1):
        for y in (-1.9, 0.0, 2.2, 4.4, 6.6, D + 0.4):
            box("Pilote", x - 0.08, x + 0.08, y - 0.08, y + 0.08, -0.5, FLOOR - 0.2, M["negro"], hc)
    for k, (h, d) in enumerate(((0.41, 0.3), (0.27, 0.6), (0.13, 0.9))):
        box("Escalon", DECK_X1 + d - 0.3, DECK_X1 + d, -2.0, -0.8, h - 0.04, h, M["deck"], hc)
    # sillas de terraza y mesa (render)
    for x, y in ((0.9, -1.0), (3.0, -1.1)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.4, location=(x, y, FLOOR + 0.5))
        ch = bpy.context.object
        ch.scale = (1, 1, 0.5)
        ch.rotation_euler.x = math.radians(-15)
        ch.data.materials.append(M["perfil"])
        for a in range(4):
            ang = a * math.pi / 2 + 0.6
            bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.012, depth=0.5,
                                                location=(x + 0.25 * math.cos(ang), y + 0.25 * math.sin(ang), FLOOR + 0.22))
            bpy.context.object.data.materials.append(M["perfil"])
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.32, depth=0.03, location=(1.95, -1.25, FLOOR + 0.45))
    bpy.context.object.data.materials.append(M["maderaOsc"])
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.03, depth=0.45, location=(1.95, -1.25, FLOOR + 0.22))
    bpy.context.object.data.materials.append(M["perfil"])
    # maceteros (la planta se agrega en main, con los arbustos Sapling)
    for x, y in MACETEROS:
        box("Macetero", x - 0.18, x + 0.18, y - 0.18, y + 0.18, FLOOR, FLOOR + 0.45, M["negro"], hc)
    return hc


# --------------------------------------------------------------- paisaje
HC = Vector((W / 2, D / 2))
MACETEROS = ((W - 0.35, -0.3), (0.35, -0.3))
PATH = [Vector(p) for p in ((DECK_X1 + 1.1, -1.4), (8.5, -5.0), (10.5, -11.0), (11.5, -18.0),
                            (14.0, -28.0), (20.0, -45.0), (30.0, -70.0))]


def path_dist(x, y):
    p = Vector((x, y))
    best = 1e9
    for a, b in zip(PATH, PATH[1:]):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        best = min(best, (p - (a + ab * t)).length)
    return best


def mountain_h(x, y):
    """Cordillera: crestas con deformación de dominio, cumbres afiladas y erosión fina (Casa Cipres)."""
    q = Vector((x / 2600, y / 2600, 3.1))
    w = noise.noise_vector(q * 0.7) * 0.4
    r = noise.ridged_multi_fractal(q + w, 0.85, 2.05, 7, 1.0, 2.2)
    peaks = min(max(0.0, r) ** 1.35 * 600, 1400)
    gullies = noise.ridged_multi_fractal(Vector((x / 500, y / 500, 9.3)), 0.9, 2.2, 5, 1.0, 2.0)
    return peaks + gullies * 35 * min(1.0, peaks / 300)


def terrain_h(x, y):
    p = Vector((x, y))
    d = (p - HC).length
    flat = max(0.0, min(1.0, (d - 18) / 140))
    rolling = noise.fractal(Vector((x / 260, y / 260, 0.3)), 0.6, 2.0, 5) * 10 * flat
    # lomas bajas (cerros de la costa / precordillera) a media distancia
    hills_m = max(0.0, min(1.0, (d - 450) / 900))
    hills = (noise.fractal(Vector((x / 900, y / 900, 2.1)), 0.55, 2.0, 6) + 0.45) * 150 * hills_m
    # cordillera sólo al fondo (+Y)
    mtn_m = max(0.0, min(1.0, (y - 3300) / 2600)) * max(0.0, min(1.0, 1.3 - abs(x) / 7000))
    mtn = mountain_h(x, y) * mtn_m if mtn_m > 0 else 0.0
    micro = noise.noise(Vector((x / 6, y / 6, 0))) * 0.12 * min(1, d / 12)
    return max(rolling + hills + mtn, -3) + micro


def build_landscape(M):
    lc = bpy.data.collections.new("Paisaje")
    bpy.context.scene.collection.children.link(lc)
    steps, x = [], 0.0
    while x < 2000:
        steps.append(x)
        x += 0.6 + x * 0.035
    coords = sorted(set([-s for s in steps] + steps))
    cx, cy = HC
    verts = [(cx + u, cy + v, terrain_h(cx + u, cy + v)) for v in coords for u in coords]
    n = len(coords)
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
             for j in range(n - 1) for i in range(n - 1)
             if math.hypot((coords[i] + coords[i + 1]) / 2, (coords[j] + coords[j + 1]) / 2) < 1430]
    mesh_obj("Terreno", verts, faces, M["terreno"], lc, smooth=True)
    # lejos: malla polar de alta resolución en azimut (cerros y cordillera con detalle)
    radii, r = [], 1400.0
    while r < 9000:
        radii.append(r)
        r += 6 + r * 0.008
    na = 1400
    verts = []
    for r in radii:
        for k in range(na):
            a = 2 * math.pi * k / na
            x, y = cx + r * math.sin(a), cy + r * math.cos(a)
            verts.append((x, y, terrain_h(x, y)))
    faces = [(j * na + k, j * na + (k + 1) % na, (j + 1) * na + (k + 1) % na, (j + 1) * na + k)
             for j in range(len(radii) - 1) for k in range(na)]
    mesh_obj("Cordillera", verts, faces, M["terreno"], lc, smooth=True)
    # camino de maicillo desde la escalera de la terraza
    pts = []
    for a, b in zip(PATH, PATH[1:]):
        for k in range(12):
            pts.append(a.lerp(b, k / 12))
    pts.append(PATH[-1])
    verts, faces = [], []
    for i, p in enumerate(pts):
        q = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        side = Vector((-q.y, q.x)).normalized() * (0.65 + 0.15 * noise.noise(Vector((p.x, p.y, 0.5))))
        for s in (-1, 1):
            v = p + side * s
            verts.append((v.x, v.y, terrain_h(v.x, v.y) + 0.025))
        if i:
            faces.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
    mesh_obj("Camino", verts, faces, M["maicillo"], lc)
    return lc


def grass_mat(name="Pasto", dry=False):
    m, n, l = new_mat(name)
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
    if dry:  # pasto seco/espigado del campo en verano
        for el, c in zip(e, ((0.16, 0.12, 0.04), (0.5, 0.4, 0.2), (0.3, 0.24, 0.09), (0.38, 0.3, 0.13))):
            el.color = (*c, 1)
    base = n.new("ShaderNodeMapRange")
    base.inputs[1].default_value, base.inputs[2].default_value = 0.0, 0.25
    base.inputs[3].default_value, base.inputs[4].default_value = 0.35, 1.0
    l.new(sep.outputs["Z"], base.inputs[0])
    _, fac, ca, cb, out = mix_rgb(n, "MULTIPLY")
    fac.default_value = 1.0
    l.new(ramp.outputs["Color"], ca)
    l.new(base.outputs[0], cb)
    l.new(out, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.65
    tr = n.new("ShaderNodeBsdfTranslucent")
    l.new(out, tr.inputs["Color"])
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.3
    l.new(b.outputs[0], mix.inputs[1])
    l.new(tr.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def grass_tuft(M, name, mat, blades=34, hmin=0.04, hmax=0.15, flower=None):
    """Mata de pasto: hojas finas y curvas (dos tramos), con distinta altura e inclinación."""
    verts, faces, tips = [], [], []
    for k in range(blades):
        a = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, 0.09)
        x, y = r * math.cos(a), r * math.sin(a)
        h = random.uniform(hmin, hmax)
        lean = random.uniform(0.15, 0.55) * h
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
        if flower and k % 6 == 0:
            tips.append(verts[-1])
    t = mesh_obj(name, verts, faces, mat)
    if flower:
        t.data.materials.append(flower)
        bm = bmesh.new()
        bm.from_mesh(t.data)
        for (x, y, z) in tips:
            for j in range(5):  # florcita de 5 pétalos
                a0 = j * 2 * math.pi / 5
                vs = [bm.verts.new((x, y, z)),
                      bm.verts.new((x + 0.012 * math.cos(a0 - 0.3), y + 0.012 * math.sin(a0 - 0.3), z + 0.002)),
                      bm.verts.new((x + 0.012 * math.cos(a0 + 0.3), y + 0.012 * math.sin(a0 + 0.3), z + 0.002))]
                bm.faces.new(vs).material_index = 1
        bm.to_mesh(t.data)
        bm.free()
    t.hide_render = True
    t.hide_viewport = True
    return t


def build_grass(M):
    """Pradera alrededor de la casa (matas instanciadas con nodos de geometría)."""
    xs = [-30 + i * 1.0 for i in range(71)]
    ys = [-34 + j * 1.0 for j in range(67)]
    verts = [(x, y, terrain_h(x, y) + 0.01) for y in ys for x in xs]
    n = len(xs)
    faces = []
    for j in range(len(ys) - 1):
        for i in range(n - 1):
            xc, yc = xs[i] + 0.5, ys[j] + 0.5
            if -0.4 < xc < DECK_X1 + 1.3 and -2.4 < yc < D + 0.9:
                continue
            if path_dist(xc, yc) < 1.1:
                continue
            faces.append((j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i))
    g = mesh_obj("Pradera", verts, faces, M["terreno"])
    if g.data.polygons[0].normal.z < 0:
        g.data.flip_normals()
    tufts = [grass_tuft(M, "MataPasto", M["pasto"]),
             grass_tuft(M, "MataPasto2", M["pasto"], 30, 0.05, 0.18),
             grass_tuft(M, "MataPasto3", M["pasto"], 34, 0.03, 0.12),
             grass_tuft(M, "MataSeca", M["pastoSeco"], 22, 0.12, 0.32),
             grass_tuft(M, "MataFlor", M["pasto"], 24, 0.05, 0.16, flower=M["flor"])]
    tc = bpy.data.collections.new("Matas")
    bpy.context.scene.collection.children.link(tc)
    for t in tufts:
        for c in t.users_collection:
            c.objects.unlink(t)
        tc.objects.link(t)
        t.hide_render = False
        t.hide_viewport = False
    tc.hide_render = True
    tc.hide_viewport = True
    ng = bpy.data.node_groups.new("Pasto", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.2
    mr = N.new("ShaderNodeMapRange")
    mr.inputs[1].default_value, mr.inputs[2].default_value = 0.3, 0.6
    mr.inputs[3].default_value, mr.inputs[4].default_value = 30, 70
    Lk.new(nz.outputs["Fac"], mr.inputs[0])
    Lk.new(mr.outputs[0], dist.inputs["Density"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = tc
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    inst.inputs["Pick Instance"].default_value = True
    rrot = N.new("FunctionNodeRandomValue")
    rrot.data_type = "FLOAT_VECTOR"
    rrot.inputs["Max"].default_value = (0.18, 0.18, 6.28)
    rsc = N.new("FunctionNodeRandomValue")
    rsc.data_type = "FLOAT"
    for sk in rsc.inputs:
        if sk.type == "VALUE" and sk.name in ("Min", "Max"):
            sk.default_value = 0.6 if sk.name == "Min" else 1.3
    ridx = N.new("FunctionNodeRandomValue")
    ridx.data_type = "INT"
    for sk in ridx.inputs:
        if sk.type == "INT" and sk.name in ("Min", "Max"):
            sk.default_value = 0 if sk.name == "Min" else 13
    # índice 0-13 -> 0..4: mayoría pasto verde, 3/14 pasto seco, 1/14 con flores
    idx_map = N.new("ShaderNodeMath")
    idx_map.operation = "MULTIPLY"
    idx_map.inputs[1].default_value = 0.31
    idx_fl = N.new("ShaderNodeMath")
    idx_fl.operation = "FLOOR"
    Lk.new(next(o for o in ridx.outputs if o.type == "INT"), idx_map.inputs[0])
    Lk.new(idx_map.outputs[0], idx_fl.inputs[0])
    Lk.new(idx_fl.outputs[0], inst.inputs["Instance Index"])
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    Lk.new(dist.outputs["Points"], inst.inputs["Points"])
    Lk.new(ci.outputs[0], inst.inputs["Instance"])
    Lk.new(rrot.outputs[0], inst.inputs["Rotation"])
    Lk.new(next(o for o in rsc.outputs if o.type == "VALUE"), inst.inputs["Scale"])
    Lk.new(gi.outputs[0], join.inputs[0])
    Lk.new(inst.outputs[0], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = g.modifiers.new("Pasto", "NODES")
    md.node_group = ng


def finish_tree(t, coll, radius, tex, tex_fine):
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    sub = t.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    disp = t.modifiers.new("disp", "DISPLACE")
    disp.texture, disp.strength, disp.mid_level = tex, radius * 0.4, 0.5
    disp.texture_coords = "LOCAL"
    fine = t.modifiers.new("fine", "DISPLACE")
    fine.texture, fine.strength, fine.mid_level = tex_fine, radius * 0.14, 0.5
    fine.texture_coords = "LOCAL"
    for md in ("sub", "disp", "fine"):
        bpy.ops.object.modifier_apply(modifier=md)
    bpy.ops.object.shade_smooth()
    for c2 in t.users_collection:
        c2.objects.unlink(t)
    coll.objects.link(t)
    t.location = (0, 0, 0)
    return t


def join_parts(parts, name):
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[-1]
    bpy.ops.object.join()
    t = bpy.context.object
    t.name = name
    return t


def make_tree_variants(M, coll):
    """Árboles de campo: copas redondas (robles, quillayes), álamos y algún pino."""
    tex = bpy.data.textures.new("ramas", "CLOUDS")
    tex.noise_scale = 0.45
    tex.noise_depth = 3
    tex_fine = bpy.data.textures.new("ramitas", "CLOUDS")
    tex_fine.noise_scale = 0.1
    tex_fine.noise_depth = 2

    def round_tree(name, h, r, blobs):
        parts = []
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=r * 0.09, depth=h * 0.55, location=(0, 0, h * 0.27))
        trunk = bpy.context.object
        trunk.data.materials.append(M["tronco"])
        parts.append(trunk)
        for k in range(blobs):
            a = random.uniform(0, 6.28)
            rr = r * random.uniform(0.2, 0.55)
            bpy.ops.mesh.primitive_ico_sphere_add(
                subdivisions=2, radius=r * random.uniform(0.5, 0.75),
                location=(rr * math.cos(a), rr * math.sin(a), h * random.uniform(0.55, 0.8)))
            c = bpy.context.object
            c.scale.z = 0.75
            c.data.materials.append(M["follaje"])
            parts.append(c)
        return finish_tree(join_parts(parts, name), coll, r, tex, tex_fine)

    def poplar(name, h, r):
        parts = []
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=h * 0.3, location=(0, 0, h * 0.15))
        trunk = bpy.context.object
        trunk.data.materials.append(M["tronco"])
        parts.append(trunk)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=1, location=(0, 0, h * 0.58))
        c = bpy.context.object
        c.scale = (r, r, h * 0.45)
        bpy.ops.object.transform_apply(scale=True)
        c.data.materials.append(M["alamo"])
        parts.append(c)
        return finish_tree(join_parts(parts, name), coll, r * 0.8, tex, tex_fine)

    def pine(name, h, r, layers):
        parts = []
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=r * 0.08, depth=h * 0.35, location=(0, 0, h * 0.17))
        trunk = bpy.context.object
        trunk.data.materials.append(M["tronco"])
        parts.append(trunk)
        for k in range(layers):
            f = k / layers
            rr = r * (1 - f) ** 0.9 + 0.15
            z0, dz = h * (0.12 + 0.82 * f), h * 0.36
            bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=rr, radius2=0.05, depth=dz, location=(0, 0, z0 + dz / 2))
            c = bpy.context.object
            c.data.materials.append(M["pino"])
            parts.append(c)
        return finish_tree(join_parts(parts, name), coll, r * 0.9, tex, tex_fine)

    rounds = [round_tree(f"Roble{i}", h, r, b) for i, (h, r, b) in
              enumerate(((9, 4.5, 7), (11, 5.5, 8), (7, 3.6, 6)))]
    poplars = [poplar(f"Alamo{i}", h, r) for i, (h, r) in enumerate(((20, 1.5), (23, 1.7)))]
    pines = [pine("Pino0", 13, 3.2, 7)]
    return rounds, poplars, pines


def build_vegetation(lib):
    """Árboles y arbustos realistas con Sapling Tree Gen (ver vegetacion.py, igual que Casa Cipres)."""
    import vegetacion as vg
    bark = vg.bark_material("Corteza")
    bark_l = vg.bark_material("CortezaClara", (0.05, 0.045, 0.04), (0.22, 0.2, 0.17))
    leaf = vg.foliage_material("Hojas", "hoja.png", (1, 1, 1), (1.4, 1.1, 0.6), 0.45)
    leaf_d = vg.foliage_material("HojasRoble", "hoja.png", (0.75, 0.85, 0.6), (1.1, 1.0, 0.6), 0.4)
    leaf_p = vg.foliage_material("HojasAlamo", "hoja.png", (1.2, 1.15, 0.65), (1.5, 1.25, 0.55), 0.5)
    dry = vg.foliage_material("HojasSecas", "hoja_seca.png", (1, 1, 1), (0.9, 0.8, 0.7), 0.4)
    pine_leaf = vg.foliage_material("AgujasPino", "pino_ramita.png", (1, 1, 1), (1.15, 1.05, 0.7))
    V = {"roble": [], "alamo": [], "sauce": [], "pino": [], "arbusto": []}
    oak = dict(leaves=80, leafScale=0.5, leafScaleX=0.8)
    for i, (sd, h) in enumerate(((3, 11), (7, 13), (12, 9))):
        V["roble"].append(vg.make_plant(f"Roble{i}", "small_maple", sd, h, leaf_d, bark, oak, lib))
    # álamo chileno (columnar): álamo temblón de Sapling comprimido en planta
    asp = dict(leaves=80, leafScale=0.42, leafScaleX=0.8)
    for i, (sd, h) in enumerate(((4, 21), (14, 24))):
        t = vg.make_plant(f"Alamo{i}", "quaking_aspen", sd, h, leaf_p, bark_l, asp, lib)
        t.scale = (0.38, 0.38, 1.0)
        bpy.ops.object.select_all(action="DESELECT")
        t.select_set(True)
        bpy.context.view_layer.objects.active = t
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        V["alamo"].append(t)
    V["sauce"].append(vg.make_plant("Sauce0", "weeping_willow", 5, 11, leaf, bark_l,
                                    dict(leaves=110, leafScale=0.3), lib))
    pine = dict(leaves=90, leafScale=0.12, leafScaleX=0.5)
    for i, (sd, h) in enumerate(((5, 13), (8, 10))):
        V["pino"].append(vg.make_plant(f"Pino{i}", "small_pine", sd, h, pine_leaf, bark, pine, lib))
    shrub = dict(leaves=30, leafScale=0.3, leafScaleX=0.75, scale=3.0, scaleV=1.0)
    for i, (sd, h, mat) in enumerate(((2, 1.4, leaf), (6, 1.0, leaf), (9, 1.2, dry))):
        V["arbusto"].append(vg.make_plant(f"Arbusto{i}", "small_maple", sd, h, mat, bark_l, shrub, lib))
    return V


def instance(src, loc, scale, rot, coll):
    ob = bpy.data.objects.new("inst", src.data)
    ob.location, ob.scale = loc, (scale, scale, scale * random.uniform(0.9, 1.15))
    ob.rotation_euler.z = rot
    coll.objects.link(ob)
    return ob


def in_sun_corridor(x, y, max_r):
    """Sector por donde entra el sol: sin árboles cercanos para que la casa quede iluminada."""
    dx, dy = x - HC.x, y - HC.y
    r = math.hypot(dx, dy)
    ang = (math.degrees(math.atan2(dx, dy)) - SUN_AZ + 180) % 360 - 180
    return r < max_r and abs(ang) < 35


def scatter_trees(veg, lod, coll, avoid):
    """Cerca (< 600 m) árboles Sapling; lejos, las versiones livianas."""
    rounds, poplars, pines = lod
    near = 600

    def pick(kind, r):
        if kind == "alamo":
            return random.choice(veg["alamo"] if r < near else poplars)
        if kind == "pino":
            return random.choice(veg["pino"] if r < near else pines)
        if r < near:
            return random.choice(veg["roble"] * 3 + veg["sauce"])
        return random.choice(rounds)

    # alamedas: hileras de álamos que bordean potreros (típico del campo chileno)
    rows = [((-90, 75), (170, 95)), ((-120, 150), (-40, 420)), ((120, 130), (380, 260)),
            ((-260, 60), (-420, 300)), ((40, 260), (420, 520)), ((-200, -60), (-500, 40)),
            ((220, -20), (520, 90))]
    for a, b in rows:
        a, b = Vector(a), Vector(b)
        n = int((b - a).length / 5.0)
        for k in range(n):
            p = a.lerp(b, k / n) + Vector((random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6)))
            if in_sun_corridor(p.x, p.y, 400):
                continue
            r = (p - HC).length
            instance(pick("alamo", r), (p.x, p.y, terrain_h(p.x, p.y) - 0.3),
                     random.uniform(0.85, 1.15), random.uniform(0, 6.3), coll)
    # árboles sueltos y bosquetes en los potreros
    placed = 0
    while placed < 650:
        ang = random.uniform(0, 2 * math.pi)
        r = 110 + (random.random() ** 1.3) * 1500
        x, y = HC.x + r * math.cos(ang), HC.y + r * math.sin(ang)
        if y < -60 and r < 250:  # detrás de la cámara: despejado
            continue
        if any((Vector((x, y)) - a).length < rad for a, rad in avoid):
            continue
        if in_sun_corridor(x, y, 400):
            continue
        cluster = 1 + (random.random() < 0.35) * random.randint(2, 7)
        for _ in range(cluster):
            px, py = x + random.uniform(-9, 9) * (cluster > 1), y + random.uniform(-9, 9) * (cluster > 1)
            src = pick("roble" if random.random() < 0.85 else "pino", r)
            instance(src, (px, py, terrain_h(px, py) - 0.3), random.uniform(0.75, 1.2), random.uniform(0, 6.3), coll)
        placed += 1
    # árboles grandes que enmarcan la casa (atrás y a los lados)
    for x, y, s, src in ((-24, 30, 1.1, veg["roble"][1]), (20, 34, 1.0, veg["roble"][0]),
                         (-9, 48, 1.0, veg["pino"][0]), (34, 12, 0.9, veg["sauce"][0])):
        instance(src, (x, y, terrain_h(x, y) - 0.2), s, random.uniform(0, 6.3), coll)


def build_fences(M, coll):
    """Cercos de palo con alambre (postes de madera rústica y tres hebras)."""
    lines = [((-40, 20), (45, 20)), ((-22, -40), (-22, 20)), ((45, 20), (45, -40))]
    for a, b in lines:
        a, b = Vector(a), Vector(b)
        n = int((b - a).length / 2.6)
        posts = []
        for k in range(n + 1):
            p = a.lerp(b, k / n)
            z = terrain_h(p.x, p.y)
            bpy.ops.mesh.primitive_cylinder_add(vertices=7, radius=0.06, depth=1.5, location=(p.x, p.y, z + 0.55))
            o = bpy.context.object
            o.rotation_euler = (random.uniform(-0.04, 0.04), random.uniform(-0.04, 0.04), random.uniform(0, 6))
            o.data.materials.append(M["poste"])
            for c in o.users_collection:
                c.objects.unlink(o)
            coll.objects.link(o)
            posts.append(Vector((p.x, p.y, z)))
        for h in (0.45, 0.8, 1.15):
            verts, edges = [], []
            for i, p in enumerate(posts):
                verts.append((p.x, p.y, p.z + h - 0.02 * math.sin(i)))
                if i:
                    edges.append((i - 1, i))
            me = bpy.data.meshes.new("Alambre")
            me.from_pydata(verts, edges, [])
            ob = bpy.data.objects.new("Alambre", me)
            coll.objects.link(ob)
            sk = ob.modifiers.new("skin", "SKIN")
            for v in me.skin_vertices[0].data:
                v.radius = (0.006, 0.006)
            ob.data.materials.append(M["perfil"])


def build_bales(M, coll):
    """Fardos de paja redondos en el potrero de atrás."""
    for _ in range(26):
        x, y = random.uniform(-30, 60), random.uniform(32, 140)
        if abs(x - 3) < 12 and y < 45:
            continue
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.75, depth=1.25,
                                            location=(x, y, terrain_h(x, y) + 0.68))
        o = bpy.context.object
        o.rotation_euler = (math.pi / 2, 0, random.uniform(0, 6.3))
        bv = o.modifiers.new("bev", "BEVEL")
        bv.width, bv.segments = 0.12, 3
        o.data.materials.append(M["paja"])
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)


def scatter_small(M, coll, shrubs):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
    rock = bpy.context.object
    rock.name = "Roca"
    d = rock.modifiers.new("d", "DISPLACE")
    d.texture = bpy.data.textures.new("roc", "VORONOI")
    d.strength = 0.35
    bpy.ops.object.modifier_apply(modifier="d")
    rock.data.materials.append(M["roca"])
    rock.hide_render = True
    rock.hide_viewport = True
    for _ in range(110):
        x, y = random.uniform(-20, 30), random.uniform(-25, 22)
        if -1.5 < x < DECK_X1 + 1.5 and -3.0 < y < D + 1.5:
            continue
        if path_dist(x, y) < 1.3:
            continue
        if random.random() < 0.75:
            o = instance(random.choice(shrubs), (x, y, terrain_h(x, y) - 0.05), random.uniform(0.6, 1.4),
                         random.uniform(0, 6.3), coll)
        else:
            s = random.uniform(0.08, 0.25)
            o = instance(rock, (x, y, terrain_h(x, y) + s * 0.2), s, random.uniform(0, 6.3), coll)
            o.scale.z *= 0.6
        o.hide_render = False
    # arbustos al pie del deck
    for x, y in ((-0.8, -1.0), (-0.9, 3.0), (-0.8, 7.2), (DECK_X1 + 0.8, 2.5), (DECK_X1 + 0.9, 6.5), (2.0, -2.7)):
        o = instance(random.choice(shrubs), (x, y, 0.0), random.uniform(0.9, 1.2), random.uniform(0, 6.3), coll)
        o.hide_render = False
    return shrubs[0], rock


# --------------------------------------------------------------- cámara
FPS, SECS = 24, 8.0
PIVOT = Vector((W / 2 + 0.6, 3.6, 0))


def ease(t):
    return t * t * (3 - 2 * t)


def cam_pose(u):
    """Órbita baja de izquierda a derecha, acercándose al frente vidriado."""
    k = ease(u)
    th = math.radians(-42 + 80 * k)
    R = 16.5 - 3.0 * k
    z = 3.8 - 0.8 * k + 0.06 * math.sin(u * 7.0)
    pos = PIVOT + Vector((R * math.sin(th), -R * math.cos(th), 0))
    pos.z = terrain_h(pos.x, pos.y) + z
    tgt = Vector((W / 2 + 0.5 * math.sin(th), 2.6, 2.7 - 0.2 * k))
    return pos, tgt


def build_camera(round_src, coll, shrub):
    cam_data = bpy.data.cameras.new("Dron")
    cam_data.lens = 22
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
        q = (tgt - pos).to_track_quat("-Z", "Y")
        e = q.to_euler()
        e.y += math.radians(0.6 * math.sin(u * 5.3))  # leve balanceo del dron
        cam.rotation_euler = e
        cam.keyframe_insert("location", frame=f + 1)
        cam.keyframe_insert("rotation_euler", frame=f + 1)
    # árbol mediano a la derecha de la casa (enmarca el final del vuelo sin tapar la casa)
    p = Vector((15.0, 1.5))
    instance(round_src, (p.x, p.y, terrain_h(p.x, p.y) - 0.2), 0.75, 0.4, coll)
    o = instance(shrub, (p.x - 1.2, p.y - 1.0, terrain_h(p.x, p.y) - 0.05), 1.1, 0, coll)
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
    sky.altitude = 300
    sky.air_density = 1.0
    if hasattr(sky, "aerosol_density"):
        sky.aerosol_density = 1.6
    else:
        sky.dust_density = 3.5
    sky.sun_size = math.radians(1.2)
    sky.sun_disc = False  # la luz directa la aporta la lámpara solar
    # degradado de atardecer: horizonte cálido, cenit azul suave
    tcw = n.new("ShaderNodeTexCoord")
    sepw = n.new("ShaderNodeSeparateXYZ")
    l.new(tcw.outputs["Generated"], sepw.inputs[0])
    grad = n.new("ShaderNodeValToRGB")
    ge = grad.color_ramp.elements
    ge[0].position, ge[0].color = 0.0, (1.5, 0.82, 0.5, 1)
    ge[1].position, ge[1].color = 0.45, (0.85, 0.88, 1.05, 1)
    ge.new(0.12).color = (1.2, 0.9, 0.72, 1)
    l.new(sepw.outputs["Z"], grad.inputs["Fac"])
    _, wf, wa, wb, wo = mix_rgb(n, "MULTIPLY")
    wf.default_value = 1.0
    l.new(sky.outputs[0], wa)
    l.new(grad.outputs["Color"], wb)
    l.new(wo, bg.inputs[0])
    bg.inputs[1].default_value = 0.3
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 13.0
    sun.data.color = (1.0, 0.58, 0.3)  # luz de atardecer, dorado anaranjado
    sun.data.angle = math.radians(1.0)
    e, a = math.radians(SUN_ELEV), math.radians(SUN_AZ)
    to_sun = Vector((math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)))
    sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    # capa de nubes altas, iluminada por el sol
    m, n, l = new_mat("Nubes")
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (1, 1, 1, 1)
    b.inputs["Roughness"].default_value = 1.0
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1, 2.2, 1)
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 7
    nz.inputs["Detail"].default_value = 12
    nz.inputs["Roughness"].default_value = 0.62
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[1].position = 0.75
    l.new(tc.outputs["Generated"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], nz.inputs["Vector"])
    l.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
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
    bpy.ops.mesh.primitive_plane_add(size=16000, location=(W / 2, 3000, 2200))
    clouds = bpy.context.object
    clouds.name = "Nubes"
    clouds.data.materials.append(m)
    clouds.visible_shadow = False
    clouds.visible_diffuse = False
    w.mist_settings.start = 40
    w.mist_settings.depth = 6500
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
    if hasattr(sc.view_settings, "use_white_balance"):
        sc.view_settings.use_white_balance = True
        sc.view_settings.white_balance_temperature = WB_TEMP
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.1
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

    lt, pw, amt = mnode("LESS_THAN", 0.999), mnode("POWER", 0.9), mnode("MULTIPLY", 0.55)
    mul = mnode("MULTIPLY", 1.0)
    haze = (0.95, 0.74, 0.58, 1)
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


def materials():
    M = {}
    M["negro"] = principled("NegroMarco", (0.012, 0.012, 0.013), 0.5)
    M["chapa"] = ribbed_metal("ChapaNegra")
    M["maderaRev"] = boards_mat("MaderaRevest", (0.42, 0.28, 0.15), (0.66, 0.48, 0.29), "X", 9.0, 0.65, 0.2)
    M["maderaCielo"] = boards_mat("MaderaCielo", (0.5, 0.33, 0.17), (0.74, 0.54, 0.32), "X", 9.0, 0.6, 0.1)
    M["maderaOsc"] = principled("MaderaOsc", (0.12, 0.06, 0.03), 0.5)
    M["deck"] = boards_mat("Deck", (0.26, 0.15, 0.07), (0.46, 0.29, 0.14), "X", 7.0, 0.55, 0.3)
    M["piso"] = boards_mat("PisoInt", (0.45, 0.28, 0.14), (0.62, 0.42, 0.22), "X", 5.0, 0.35, 0.05)
    M["perfil"] = principled("PerfilNegro", (0.01, 0.01, 0.01), 0.35, 0.6)
    M["vidrio"] = glass_mat()
    M["tela"] = principled("TelaClara", (0.7, 0.66, 0.6), 0.9)
    M["sabanas"] = principled("Sabanas", (0.8, 0.79, 0.76), 0.9)
    M["telaAzul"] = principled("TelaAzul", (0.12, 0.15, 0.24), 0.9)
    M["alfombra"] = principled("Alfombra", (0.45, 0.42, 0.38), 1.0)
    M["piedra"] = principled("Cubierta", (0.6, 0.58, 0.55), 0.3)
    M["lampara"] = emit_mat("Lampara", WARM, 10)
    M["spot"] = emit_mat("Spot", (1, 0.8, 0.55), 30)
    M["follaje"] = foliage_mat("Follaje", (0.03, 0.05, 0.015), (0.11, 0.13, 0.035))
    M["alamo"] = foliage_mat("Alamo", (0.06, 0.08, 0.02), (0.2, 0.2, 0.05), 0.35)
    M["pino"] = foliage_mat("Pino", (0.012, 0.03, 0.014), (0.05, 0.08, 0.03))
    M["arbusto"] = foliage_mat("Arbusto", (0.04, 0.06, 0.015), (0.13, 0.14, 0.04))
    M["tronco"] = principled("Tronco", (0.08, 0.06, 0.04), 0.9)
    M["poste"] = principled("Poste", (0.2, 0.17, 0.14), 0.95)
    M["paja"] = boards_mat("Paja", (0.4, 0.3, 0.12), (0.62, 0.5, 0.25), "Z", 30.0, 0.9, 0.3, 6.0)
    M["roca"] = principled("Roca", (0.16, 0.14, 0.12), 0.85)
    M["flor"] = principled("Flor", (0.9, 0.72, 0.12), 0.6)
    M["pasto"] = grass_mat()
    M["pastoSeco"] = grass_mat("PastoSeco", dry=True)
    M["terreno"] = terrain_mat()
    M["maicillo"] = gravel_mat()
    return M


def main():
    reset()
    M = materials()
    build_house(M)
    build_landscape(M)
    lib = bpy.data.collections.new("Biblioteca")
    bpy.context.scene.collection.children.link(lib)
    lod = make_tree_variants(M, lib)  # versiones livianas para lo lejano
    veg = build_vegetation(lib)
    lib.hide_render = True
    lib.hide_viewport = True
    trees = bpy.data.collections.new("Arboles")
    bpy.context.scene.collection.children.link(trees)
    shrub, rock = scatter_small(M, trees, veg["arbusto"])
    for x, y in MACETEROS:
        o = instance(veg["arbusto"][1], (x, y, FLOOR + 0.42), 0.75, random.uniform(0, 6.3), trees)
        o.hide_render = False
    cam, fg = build_camera(veg["roble"][2], trees, shrub)
    scatter_trees(veg, lod, trees, avoid=[(fg, 6), (HC, 14)] +
                  [(cam_pose(u)[0].xy, 8) for u in (0, 0.25, 0.5, 0.75, 1)])
    build_fences(M, trees)
    build_bales(M, trees)
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
