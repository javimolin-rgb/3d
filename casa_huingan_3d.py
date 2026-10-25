"""Escena 3D de Casa Huingan en la playa (Blender 5.x, Cycles).

Uso:
  python casa_huingan_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  (vistas: izq / der = tomas fijas de dron desde el mar, a cada lado del frente)

La casa sale del modelo STL de Neorigen (assets/huingan/casa.blend, generado con
tools/extraer_huingan_stl.py): 12,18 m de ancho, terraza de 2 m hacia -Y (el mar), porch de acceso
hacia +Y, techo a dos aguas asimétrico (cumbrera en x = 8,9 m), piso terminado en z = 0,23 y
terreno en z = -0,31.
Paisaje: costa chilena de zona central. Playa de arena con orilla curva y espuma, duna baja con
pastos dorados y arbustos alrededor de la casa, pasarela de madera hasta la arena y cerros con
bosque al fondo. Arbusto shrub_03 de Poly Haven (CC0) y pastos y rocas Botaniq de assets/campo.
"""
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"vista": "izq", "out": "//cuadro.png", "res": "720x1280", "samples": "32", "still": "1",
        "wb": "5900", "save": None}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(5)
ROOT = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.join(ROOT, "assets", "huingan", "casa.blend")
CAMPO = os.path.join(ROOT, "assets", "campo", "pastos_botaniq.blend")
PH = os.path.join(ROOT, "assets", "playa", "ph")   # recursos de Poly Haven (tools/get_assets_playa.sh)
HDRI = os.path.join(PH, "hdri", "sundowner_overlook_2k.exr")   # tarde despejada de costa, CC0
HDRI_SUN_U = 0.6001          # columna del sol en el HDRI (0-1)
SUN_ELEV = 27.0              # elevación del sol en el HDRI
SKY_GAIN = 0.06              # brillo del cielo físico (horizonte) para empatar con el HDRI
SUN_AZ = 215.0               # sol desde adelante-izquierda (azimut desde +Y hacia +X)
WB_TEMP = float(opts["wb"])
L, D = 12.18, 9.24           # ancho y fondo total del casco (terraza + caja + porch)
HC = Vector((L / 2, 4.6))    # centro de la casa en planta
GROUND = -0.31               # terreno bajo la casa
SEA = -5.0                   # nivel del mar (la casa está en una meseta de duna sobre la playa)
SHORE_Y = -33.0              # orilla frente a la casa: la punta de la península
SHORE_K = 420.0              # la orilla se abre hacia +Y a ambos lados: y = SHORE_Y + (x - XC)² / K
XC = 6.0
FPS = 24


# ---------------------------------------------------------------- utilidades
def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, mat=None, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me), coll)
    if mat:
        me.materials.append(mat)
    return o


def box(name, x0, x1, y0, y1, z0, z1, mat=None, coll=None):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_obj(name, v, f, mat, coll)


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


class Nodos:
    """Atajos para armar árboles de nodos de shader con matemática."""

    def __init__(self, n, l):
        self.n, self.l = n, l

    def math(self, op, a, b=None, c=None):
        nd = self.n.new("ShaderNodeMath")
        nd.operation = op
        for k, v in ((0, a), (1, b), (2, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[k].default_value = v
            else:
                self.l.new(v, nd.inputs[k])
        return nd.outputs[0]

    def mix(self, fac, a, b):
        mx = self.n.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        for sk, v in ((mx.inputs[0], fac), (mx.inputs[6], a), (mx.inputs[7], b)):
            if isinstance(v, (int, float)):
                sk.default_value = v
            elif isinstance(v, tuple):
                sk.default_value = (*v, 1) if len(v) == 3 else v
            else:
                self.l.new(v, sk)
        return mx.outputs[2]

    def noise(self, vec, scale, detail=4, rough=0.5, dist=0.0):
        nz = self.n.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail
        nz.inputs["Roughness"].default_value = rough
        nz.inputs["Distortion"].default_value = dist
        self.l.new(vec, nz.inputs["Vector"])
        return nz.outputs["Fac"]

    def smooth(self, x, a, b):
        """0 en x <= a, 1 en x >= b (rampa suave)."""
        mr = self.n.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs[1].default_value, mr.inputs[2].default_value = a, b
        self.l.new(x, mr.inputs[0])
        return mr.outputs[0]


def shore_y(x):
    """Línea de la orilla (y) en función de x: la casa está en una punta (península suave) con
    el mar al frente y, más lejos, a ambos costados; así el mar se ve de fondo en las tomas."""
    return SHORE_Y + (x - XC) ** 2 / SHORE_K + 2.0 * math.sin(x / 17.0 + 1.3)


def shore_d(x, y):
    """Distancia aproximada (m) a la orilla, positiva tierra adentro."""
    slope = 2 * (x - XC) / SHORE_K
    return (y - shore_y(x)) / math.sqrt(1 + slope * slope)


def shore_d_nodes(N, sep):
    """Mismo shore_d(x, y) en nodos."""
    dx = N.math("SUBTRACT", sep.outputs["X"], XC)
    s2 = N.math("SINE", N.math("ADD", N.math("DIVIDE", sep.outputs["X"], 17.0), 1.3))
    ys = N.math("ADD", N.math("ADD", N.math("DIVIDE", N.math("MULTIPLY", dx, dx), SHORE_K),
                                  N.math("MULTIPLY", s2, 2.0)), SHORE_Y)
    slope = N.math("MULTIPLY", dx, 2.0 / SHORE_K)
    norm = N.math("SQRT", N.math("ADD", N.math("MULTIPLY", slope, slope), 1.0))
    return N.math("DIVIDE", N.math("SUBTRACT", sep.outputs["Y"], ys), norm)


# ---------------------------------------------------------------- materiales
def boards_mat(name, c1, c2, axis, scale, rough=0.6, bump=0.25, distort=2.0):
    """Tablas (revestimiento o deck): bandas + veta con ruido."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = axis
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = scale
    mapg = n.new("ShaderNodeMapping")
    mapg.inputs["Scale"].default_value = {"X": (1, 14, 14), "Y": (14, 1, 14), "Z": (14, 14, 1)}[axis]
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    l.new(tc.outputs["Object"], mapg.inputs["Vector"])
    grain = N.noise(mapg.outputs["Vector"], 3.0, 8, 0.5, distort)
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    l.new(grain, ramp.inputs["Fac"])
    seam = N.math("GREATER_THAN", wave.outputs["Fac"], 0.96)
    col = N.mix(seam, ramp.outputs["Color"], (0.2, 0.17, 0.14))
    l.new(col, b.inputs["Base Color"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    l.new(seam, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m


def ribbed_metal(name, pitch=0.30, rib=0.035, flank=0.018, axis="X"):
    """Chapa negra con nervios trapezoidales cada 30 cm (como Casa Lingue)."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.022, 1)
    b.inputs["Metallic"].default_value = 0.55
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    u = N.math("FRACT", N.math("DIVIDE", sep.outputs[axis], pitch))
    d = N.math("MULTIPLY", N.math("ABSOLUTE", N.math("SUBTRACT", u, 0.5)), pitch)
    d = N.math("MULTIPLY", N.math("SUBTRACT", d, pitch / 2), -1.0)
    top = N.math("SUBTRACT", 1.0, N.math("DIVIDE", N.math("MAXIMUM", N.math("SUBTRACT", d, rib / 2), 0.0), flank))
    top = N.math("MAXIMUM", top, 0.0)
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 1.0
    bmp.inputs["Distance"].default_value = 0.02
    l.new(top, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    dust = N.noise(tc.outputs["Object"], 1.5)
    l.new(N.math("ADD", 0.34, N.math("MULTIPLY", dust, 0.1)), b.inputs["Roughness"])
    return m


def glass_mat():
    m, n, l = new_mat("Vidrio")
    n.remove(n["Principled BSDF"])
    out = n["Material Output"]
    fr = n.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.45
    att = n.new("ShaderNodeMath")
    att.operation = "MULTIPLY"
    att.inputs[1].default_value = 0.5
    l.new(fr.outputs["Fac"], att.inputs[0])
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.86, 0.9, 0.9, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.02
    mix = n.new("ShaderNodeMixShader")
    l.new(att.outputs[0], mix.inputs["Fac"])
    l.new(tr.outputs[0], mix.inputs[1])
    l.new(gl.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])
    return m


def sand_mat():
    """Arena: tono claro con manchones, ondas de viento (ripples) en la arena seca, arena húmeda
    más oscura y brillante junto a la orilla, y restos de algas en la línea de marea."""
    m, n, l = new_mat("Arena")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    d = shore_d_nodes(N, sep)
    big = N.noise(tc.outputs["Object"], 0.08, 3)
    mid = N.noise(tc.outputs["Object"], 0.7, 6)
    dry = N.mix(N.math("MULTIPLY_ADD", big, 1.6, -0.3), (0.33, 0.27, 0.19), (0.45, 0.37, 0.26))
    dry = N.mix(N.math("MULTIPLY", mid, 0.35), dry, (0.27, 0.22, 0.15))
    wet = (0.22, 0.19, 0.14)
    wet_f = N.math("SUBTRACT", 1.0, N.smooth(d, 2.5, 6.5))
    col = N.mix(wet_f, dry, wet)
    # línea de marea: restos oscuros discontinuos
    tide = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", d, 7.5)), 0.0, 0.6)),
                  N.smooth(N.noise(tc.outputs["Object"], 1.3, 3), 0.55, 0.62))
    col = N.mix(N.math("MULTIPLY", tide, 0.7), col, (0.12, 0.1, 0.07))
    depth = N.math("MULTIPLY", d, -1.0)
    col = N.mix(N.smooth(depth, 0.0, 4.0), col, (0.13, 0.2, 0.17))
    col = N.mix(N.smooth(depth, 3.0, 28.0), col, (0.012, 0.055, 0.065))
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "veg"
    soil = N.mix(N.smooth(N.noise(tc.outputs["Object"], 2.0, 5), 0.35, 0.6), (0.2, 0.17, 0.11), (0.1, 0.11, 0.06))
    col = N.mix(N.math("MULTIPLY", at.outputs["Fac"], 0.75), col, soil)
    # sendero: arena pisada, algo más oscura y con huellas
    cm = n.new("ShaderNodeAttribute")
    cm.attribute_name = "camino"
    steps = N.smooth(N.noise(tc.outputs["Object"], 5.0, 3), 0.5, 0.7)
    col = N.mix(N.math("MULTIPLY", cm.outputs["Fac"], N.math("ADD", 0.6, N.math("MULTIPLY", steps, 0.3))), col,
                (0.2, 0.16, 0.11))
    l.new(col, b.inputs["Base Color"])
    l.new(N.math("ADD", 0.9, N.math("MULTIPLY", wet_f, -0.6)), b.inputs["Roughness"])
    # ondas de viento: bandas distorsionadas sólo en arena seca
    wave = n.new("ShaderNodeTexWave")
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 3.0
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 0.6
    mpw = n.new("ShaderNodeMapping")
    mpw.inputs["Scale"].default_value = (0.25, 1.0, 1.0)
    l.new(tc.outputs["Object"], mpw.inputs["Vector"])
    l.new(mpw.outputs["Vector"], wave.inputs["Vector"])
    grain = N.noise(tc.outputs["Object"], 60.0, 2)
    h = N.math("ADD", N.math("MULTIPLY", wave.outputs["Fac"], N.math("MULTIPLY", N.smooth(d, 6, 10), 0.6)),
               N.math("MULTIPLY", grain, 0.25))
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.35
    bmp.inputs["Distance"].default_value = 0.03
    l.new(h, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def water_mat():
    """Mar: transparente en la orilla (se ve la arena), turquesa y luego azul profundo; olas por
    bump; espuma en la orilla y en dos líneas de rompiente."""
    m, n, l = new_mat("Mar")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    out = n["Material Output"]
    tc = n.new("ShaderNodeNewGeometry")   # posición de mundo: sirve igual para el oleaje y el plano lejano
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Position"], sep.inputs[0])
    d = N.math("MULTIPLY", shore_d_nodes(N, sep), -1.0)  # distancia mar adentro (m)
    # superficie: transparente (deja pasar el sol, así el fondo de arena se ilumina sin cáusticas)
    # + reflejo del cielo según Fresnel; el color del agua lo da el fondo (sand_mat)
    n.remove(b)
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.86, 0.92, 0.9, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.04
    fr = n.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.333
    wat = n.new("ShaderNodeMixShader")
    # el reflejo sólo por arriba y nunca para las sombras: visto desde el fondo, el Fresnel daría
    # reflexión total y la arena sumergida quedaría a oscuras
    geo = n.new("ShaderNodeNewGeometry")
    lpw = n.new("ShaderNodeLightPath")
    fac = N.math("MULTIPLY", fr.outputs["Fac"], N.math("SUBTRACT", 1.0, geo.outputs["Backfacing"]))
    fac = N.math("MULTIPLY", fac, N.math("SUBTRACT", 1.0, lpw.outputs["Is Shadow Ray"]))
    l.new(fac, wat.inputs["Fac"])
    l.new(tr.outputs[0], wat.inputs[1])
    l.new(gl.outputs[0], wat.inputs[2])
    # olas en tres escalas: marejada larga paralela a la orilla, olas medianas y rizos finos
    def bump_layer(scale, stretch, strength, dist, normal=None, detail=6):
        mp = n.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = stretch
        l.new(tc.outputs["Position"], mp.inputs["Vector"])
        bp = n.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = strength
        bp.inputs["Distance"].default_value = dist
        l.new(N.noise(mp.outputs["Vector"], scale, detail, 0.55, 0.3), bp.inputs["Height"])
        if normal is not None:
            l.new(normal, bp.inputs["Normal"])
        return bp.outputs["Normal"]

    nrm = bump_layer(0.05, (0.2, 1.0, 1.0), 0.25, 1.2)          # marejada (lejos, donde no hay oleaje)
    nrm = bump_layer(0.35, (0.5, 1.0, 1.0), 0.3, 0.35, nrm)     # olas
    nrm = bump_layer(3.0, (1.0, 1.0, 1.0), 0.15, 0.04, nrm, 4)  # rizos
    l.new(nrm, gl.inputs["Normal"])
    # espuma: rompiente junto a la orilla (agua blanca con encaje), dos líneas de ola rompiendo
    # más afuera, cortadas y desflecadas, y restos de espuma en encaje sobre el agua baja
    mf = n.new("ShaderNodeMapping")
    mf.inputs["Scale"].default_value = (0.08, 1.0, 1.0)
    l.new(tc.outputs["Position"], mf.inputs["Vector"])
    brk = N.noise(mf.outputs["Vector"], 1.0, 6, 0.65, 0.6)
    grain = N.noise(tc.outputs["Position"], 6.0, 6, 0.7)
    # profundidad del agua bajo cada punto de la superficie (con la ola): el fondo baja ~4,5 cm
    # por metro mar adentro, y la superficie sube y baja con el oleaje
    zrel = N.math("SUBTRACT", sep.outputs["Z"], SEA)
    depth = N.math("ADD", zrel, N.math("MULTIPLY", d, FORE))
    ms = n.new("ShaderNodeMapping")
    ms.inputs["Scale"].default_value = (0.15, 1.0, 1.0)
    l.new(tc.outputs["Position"], ms.inputs["Vector"])
    streak = N.smooth(N.noise(ms.outputs["Vector"], 2.5, 10, 0.7, 0.5), 0.5, 0.7)    # vetas de espuma
    # 1) línea fina donde el agua toca la arena
    edge = N.math("SUBTRACT", 1.0, N.smooth(depth, 0.01, 0.07))
    edge = N.math("MULTIPLY", edge, N.smooth(N.math("ADD", brk, N.math("MULTIPLY", grain, 0.5)), 0.4, 0.6))
    # 2) agua blanca donde la ola rompe: cresta (sobre el nivel medio) en agua baja
    brkz = N.math("MULTIPLY", N.smooth(zrel, 0.05, 0.3), N.math("SUBTRACT", 1.0, N.smooth(depth, 0.5, 1.3)))
    brkz = N.math("MULTIPLY", brkz, N.smooth(N.math("ADD", streak, N.math("MULTIPLY", grain, 0.4)), 0.35, 0.6))
    # 3) espuma que queda en vetas sobre el agua muy baja, detrás de la ola
    swash = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(depth, 0.05, 0.35)), N.math("MULTIPLY", streak, 0.4))
    surf = N.math("MAXIMUM", N.math("MAXIMUM", edge, brkz), swash)
    caps = n.new("ShaderNodeAttribute")
    caps.attribute_name = "espuma"
    whitecap = N.math("MULTIPLY", N.smooth(caps.outputs["Fac"], 0.55, 0.95), N.smooth(grain, 0.4, 0.65))
    foam = N.math("MAXIMUM", surf, N.math("MULTIPLY", whitecap, 0.6))
    foam = N.math("MINIMUM", foam, 1.0)
    fb = n.new("ShaderNodeBsdfPrincipled")
    fb.inputs["Base Color"].default_value = (0.85, 0.87, 0.86, 1)
    fb.inputs["Roughness"].default_value = 0.8
    mx = n.new("ShaderNodeMixShader")
    l.new(foam, mx.inputs["Fac"])
    l.new(wat.outputs[0], mx.inputs[1])
    l.new(fb.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs["Surface"])
    return m


def hills_mat():
    """Paisaje lejano en un solo material (sin corte entre duna y cerro): arena y matorral olivo
    abajo, que con la altura se cubre de bosque de pinos y quebradas oscuras, con claros de
    pasto seco. Los mismos tonos que la vegetación cercana."""
    m, n, l = new_mat("Cerros")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    f = N.noise(tc.outputs["Object"], 0.012, 6, 0.6)
    g = N.noise(tc.outputs["Object"], 0.15, 4)
    h = N.noise(tc.outputs["Object"], 0.05, 5, 0.6)
    scrub = N.mix(N.smooth(h, 0.35, 0.55), (0.34, 0.29, 0.2), (0.12, 0.13, 0.065))
    forest = N.mix(N.smooth(f, 0.32, 0.48), (0.2, 0.18, 0.1), (0.022, 0.035, 0.018))
    up = N.math("MULTIPLY", N.smooth(sep.outputs["Z"], 2.0, 35.0), N.smooth(f, 0.25, 0.4))
    col = N.mix(up, scrub, forest)
    col = N.mix(N.math("MULTIPLY", g, 0.35), col, (0.03, 0.04, 0.022))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.8
    bmp.inputs["Distance"].default_value = 2.0
    l.new(g, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def scrub_mat():
    """Duna lejana cubierta de pastos y matorral (vista a distancia, sin instancias)."""
    m, n, l = new_mat("Matorral")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    f = N.noise(tc.outputs["Object"], 0.08, 6, 0.65)
    g = N.noise(tc.outputs["Object"], 0.9, 4)
    col = N.mix(N.smooth(f, 0.28, 0.45), (0.3, 0.27, 0.16), (0.05, 0.07, 0.03))
    col = N.mix(N.math("MULTIPLY", g, 0.5), col, (0.03, 0.045, 0.02))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.6
    l.new(g, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def dune_grass_mat():
    """Pasto de duna: dorado-pajizo con algo de verde grisáceo (cada mata con su tono)."""
    m, n, l = new_mat("PastoDuna")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    info = n.new("ShaderNodeObjectInfo")
    tc = n.new("ShaderNodeTexCoord")
    v = N.math("ADD", N.math("MULTIPLY", info.outputs["Random"], 0.7), N.math("MULTIPLY", N.noise(tc.outputs["Object"], 3), 0.3))
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].color, e[1].color = (0.22, 0.24, 0.12, 1), (0.5, 0.42, 0.25, 1)
    e.new(0.45).color = (0.38, 0.35, 0.19, 1)
    l.new(v, ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    b.inputs["Subsurface Weight"].default_value = 0.1
    l.new(ramp.outputs["Color"], b.inputs["Subsurface Radius"])
    return m


def concrete_mat():
    m, n, l = new_mat("Hormigon")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    l.new(N.mix(N.noise(tc.outputs["Object"], 6.0, 5), (0.5, 0.49, 0.46), (0.66, 0.65, 0.62)), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    return m


def materials():
    M = {
        "chapa": ribbed_metal("ChapaNegra"),
        "chapaTecho": ribbed_metal("ChapaTecho", 0.33, 0.03, 0.02, "Y"),
        "fachada": boards_mat("MaderaFachada", (0.5, 0.37, 0.24), (0.72, 0.56, 0.38), "X", 7.0, 0.65, 0.2),
        "cielo": boards_mat("MaderaCielo", (0.55, 0.41, 0.27), (0.74, 0.58, 0.4), "X", 7.0, 0.6, 0.15),
        "deck": boards_mat("Deck", (0.36, 0.25, 0.15), (0.56, 0.41, 0.27), "Y", 7.5, 0.6, 0.35),
        "piso": boards_mat("PisoInterior", (0.5, 0.37, 0.24), (0.66, 0.5, 0.33), "Y", 5.0, 0.4, 0.1),
        "muroint": boards_mat("MuroInterior", (0.62, 0.5, 0.36), (0.78, 0.65, 0.48), "X", 6.0, 0.6, 0.1),
        "vidrio": glass_mat(),
        "hormigon": concrete_mat(),
        "arena": sand_mat(),
        "mar": water_mat(),
        "cerros": hills_mat(),
        "pastoDuna": dune_grass_mat(),
        "matorral": scrub_mat(),
        "roca": principled("Roca", (0.2, 0.19, 0.17), 0.85),
        "pasarela": boards_mat("Pasarela", (0.38, 0.32, 0.25), (0.55, 0.48, 0.38), "X", 4.0, 0.75, 0.4),
    }
    return M


# ---------------------------------------------------------------- casa
def load_house(M):
    """Casa del STL con los materiales de la escena (por nombre de material del .blend)."""
    with bpy.data.libraries.load(CASA) as (a, b):
        b.objects = a.objects
    swap = {"Hg_ChapaNegra": M["chapa"], "Hg_MaderaFachada": M["fachada"], "Hg_MaderaCielo": M["cielo"],
            "Hg_Deck": M["deck"], "Hg_PisoInterior": M["piso"], "Hg_MuroInterior": M["muroint"],
            "Hg_Vidrio": M["vidrio"], "Hg_Pilote": M["hormigon"]}
    coll = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(coll)
    for o in b.objects:
        coll.objects.link(o)
        for sl in o.material_slots:
            if sl.material and sl.material.name in swap:
                sl.material = swap[sl.material.name]
    # luces interiores tibias (en el día apenas se notan, pero dan vida al interior)
    for x, y, z, p in ((6.1, 4.0, 2.4, 160), (2.0, 4.2, 2.2, 70), (10.2, 4.2, 2.2, 70), (6.5, 7.0, 2.3, 80)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.0
        lt.data.color = (1.0, 0.72, 0.45)
    return coll


def build_boardwalk(M):
    """Pasarela de tablas desde la escalera de la terraza hasta la arena (sobre la duna)."""
    coll = bpy.data.collections.new("Pasarela")
    bpy.context.scene.collection.children.link(coll)
    x0, x1 = 0.2, 1.6
    y = -0.8
    i = 0
    while y > -13.0:
        z = terrain_base(1.0, y) + 0.12
        box(f"Tabla{i}", x0, x1, y - 0.14, y, z, z + 0.035, M["pasarela"], coll)
        if i % 8 == 0:
            for xp in (x0 + 0.05, x1 - 0.12):
                box(f"Poste{i}", xp, xp + 0.07, y - 0.12, y - 0.05, z - 0.5, z, M["pasarela"], coll)
        y -= 0.165
        i += 1
    return coll


# ---------------------------------------------------------------- terreno
def house_dist(x, y):
    """Distancia (m) al rectángulo de la casa (con un margen de 0,5 m)."""
    dx = max(-0.5 - x, 0, x - (L + 0.5))
    dy = max(-1.3 - y, 0, y - (D + 1.3))
    return math.hypot(dx, dy)


FORE = 0.08     # pendiente de la orilla (bajo el agua y donde rompe la ola)
BEACH = 13.0     # ancho de la playa (m)
SLOPE_W = 16.0   # ancho de la ladera de la duna que sube desde la playa hasta la meseta


def terrain_base(x, y):
    """Perfil sin ondulaciones: fondo marino < playa < ladera de duna < meseta de la casa."""
    d = shore_d(x, y)
    if d < 0:
        return SEA + max(d * FORE, -6.0)
    if d < 6.0:
        return SEA + d * FORE                      # orilla: pendiente fuerte, donde llega la ola
    if d < BEACH:
        return SEA + 6.0 * FORE + (d - 6.0) * 0.03
    t = min(1.0, (d - BEACH) / SLOPE_W)
    t = t * t * (3 - 2 * t)
    top = SEA + 6.0 * FORE + (BEACH - 6.0) * 0.03
    return top + t * (GROUND - top)


def path_x(y):
    """Eje del sendero (x) que baja serpenteando desde la escalera de la terraza a la playa."""
    return 1.0 + 3.0 * math.sin(y / 9.0) - 0.04 * min(0.0, y) * math.sin(y / 23.0)


def path_dist(x, y):
    """Distancia (m) al eje del sendero; lejos en la meseta detrás de la escalera."""
    if y > -0.6:
        return math.hypot(x - path_x(-0.6), y + 0.6)
    return abs(x - path_x(y))


def terrain_h(x, y):
    h = terrain_base(x, y)
    d = shore_d(x, y)
    pd = path_dist(x, y)
    # dunas suaves en la meseta y en la ladera; se aplanan junto a la casa
    amp = min(1.0, max(0.0, (d - BEACH - 3) / 12.0)) * (0.9 + min(1.0, max(0.0, (d - 60) / 60.0)) * 1.8)
    flat = min(1.0, max(0.0, (house_dist(x, y) - 1.0) / 8.0))
    dn = noise.noise(Vector((x / 16.0, y / 12.0, 0.3))) + 0.4 * noise.noise(Vector((x / 5.0, y / 4.0, 1.7)))
    flat = min(flat, 0.3 + 0.7 * min(1.0, max(0.0, (pd - 1.0) / 4.0)))   # el sendero corta la duna
    if 8 < y < 140:
        flat = min(flat, 0.2 + 0.8 * min(1.0, max(0.0, (road_dist(x, y) - 2.5) / 6.0)))   # y el camino
    h += amp * flat * (0.4 + 0.7 * dn)
    if d > BEACH:                                           # huella levemente hundida
        h -= 0.07 * max(0.0, 1.0 - pd / 1.1)
    # cerros costeros al fondo, tierra adentro
    if y > 280:
        r = min(1.0, (y - 280) / 300.0)
        hn = 0.5 + 0.5 * noise.noise(Vector((x / 180.0, y / 140.0, 3.1)))
        h += r * r * (30 + 90 * hn) * min(1.0, max(0.0, (d - 40.0) / 160.0))   # sin cerros pegados al mar
    return h + 0.02 * noise.noise(Vector((x * 1.3, y * 1.3, 9.0)))


def grid(name, x0, x1, y0, y1, step, mat, coll=None, skip=None, sink=None):
    """Malla de terreno. skip(x, y): se omite el cuadro si sus cuatro esquinas caen dentro (así
    traslapa con la malla vecina en vez de dejar una rendija); sink(x, y): esas esquinas se hunden
    0,5 m para quedar bajo la malla fina."""
    nx, ny = int(round((x1 - x0) / step)) + 1, int(round((y1 - y0) / step)) + 1
    verts = []
    for j in range(ny):
        for i in range(nx):
            x, y = x0 + i * step, y0 + j * step
            verts.append((x, y, terrain_h(x, y) - (0.5 if sink and sink(x, y) else 0.0)))
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            if skip and all(skip(x0 + (i + a) * step, y0 + (j + b) * step) for a in (0, 1) for b in (0, 1)):
                continue
            faces.append((j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i))
    o = mesh_obj(name, verts, faces, mat, coll)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


OCEAN_X, OCEAN_Y, OCEAN_TILE, OCEAN_REP = -330.0, -620.0, 150.0, 5   # oleaje real: 750 x 750 m


def fade_ocean_edges(o, width=120.0):
    """Las olas se aplanan hacia el borde de la malla (nodos de geometría después del Ocean),
    para que empalme sin costura con el plano del mar lejano."""
    half = OCEAN_TILE / 2
    lo, hi = -half, -half + OCEAN_TILE * OCEAN_REP          # extensión local de la malla
    ng = bpy.data.node_groups.new("BordeOleaje", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(pos.outputs[0], sep.inputs[0])

    def mth(op, a, b=None):
        nd = N.new("ShaderNodeMath")
        nd.operation = op
        for k, v in ((0, a), (1, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[k].default_value = v
            else:
                Lk.new(v, nd.inputs[k])
        return nd.outputs[0]

    def ramp(v):   # 0 en el borde, 1 a `width` metros hacia adentro
        e = mth("MINIMUM", mth("SUBTRACT", v, lo), mth("SUBTRACT", hi, v))
        mr = N.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs[1].default_value, mr.inputs[2].default_value = 0.0, width
        Lk.new(e, mr.inputs[0])
        return mr.outputs[0]

    f = mth("MULTIPLY", ramp(sep.outputs["X"]), ramp(sep.outputs["Y"]))
    cmb = N.new("ShaderNodeCombineXYZ")
    Lk.new(sep.outputs["X"], cmb.inputs[0])
    Lk.new(sep.outputs["Y"], cmb.inputs[1])
    Lk.new(mth("MULTIPLY", sep.outputs["Z"], f), cmb.inputs[2])
    sp = N.new("GeometryNodeSetPosition")
    Lk.new(gi.outputs[0], sp.inputs["Geometry"])
    Lk.new(cmb.outputs[0], sp.inputs["Position"])
    Lk.new(sp.outputs[0], go.inputs[0])
    md = o.modifiers.new("BordeOleaje", "NODES")
    md.node_group = ng


def build_ocean(M, coll):
    """Mar: frente a la playa, una malla con oleaje real (modificador Ocean: espectro de olas,
    crestas con espuma en el atributo 'espuma'); el oleaje corta la arena de forma irregular como
    una orilla de verdad. Alrededor, hasta el horizonte, un plano con olas de bump."""
    bpy.ops.mesh.primitive_plane_add(size=2)
    o = bpy.context.object
    o.name = "MarOleaje"
    for c in o.users_collection:
        c.objects.unlink(o)
    coll.objects.link(o)
    md = o.modifiers.new("Oleaje", "OCEAN")
    md.geometry_mode = "GENERATE"
    md.spatial_size = int(OCEAN_TILE)
    md.repeat_x = md.repeat_y = OCEAN_REP
    md.resolution = md.viewport_resolution = 18
    md.wave_scale = 0.55          # olas de ~1 m
    md.wind_velocity = 9.0
    md.choppiness = 1.0
    md.wave_alignment = 0.55
    md.wave_direction = math.radians(90.0)   # avanzan hacia la costa (+Y)
    md.damping = 0.3
    md.use_normals = True
    md.use_foam = True
    md.foam_coverage = 0.12
    md.foam_layer_name = "espuma"
    md.time = float(opts.get("t_mar", "3.0"))
    # el modificador genera la malla desde (-tile/2, -tile/2) hacia +X/+Y
    o.location = (OCEAN_X + OCEAN_TILE / 2, OCEAN_Y + OCEAN_TILE / 2, SEA)
    o.data.materials.append(M["mar"])
    fade_ocean_edges(o)
    x0, y0 = OCEAN_X, OCEAN_Y
    x1, y1 = x0 + OCEAN_TILE * OCEAN_REP, y0 + OCEAN_TILE * OCEAN_REP
    R = 40000
    verts = [(-R, -R, SEA), (R, -R, SEA), (R, R, SEA), (-R, R, SEA),
             (x0, y0, SEA), (x1, y0, SEA), (x1, y1, SEA), (x0, y1, SEA)]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]   # marco alrededor del oleaje
    mar = mesh_obj("Mar", verts, faces, M["mar"], coll)
    for poly in mar.data.polygons:
        if poly.normal.z < 0:   # normal hacia arriba: si no, el Fresnel ve el agua desde abajo
            mar.data.flip_normals()
            break
    return o



def build_landscape(M):
    coll = bpy.data.collections.new("Paisaje")
    bpy.context.scene.collection.children.link(coll)
    near = (-90, 110, -70, 90)
    sand = grid("Playa", *near, 0.5, M["arena"], coll)
    # lejos: playa y dunas hacia los costados + cerros (sin el hueco del terreno cercano)
    inside = lambda x, y: near[0] < x < near[1] and near[2] < y < near[3]  # noqa: E731
    far = grid("Lejos", -2100, 2100, -600, 2700, 15.0, M["arena"], coll, skip=inside, sink=inside)
    far.data.materials.append(M["cerros"])
    for p in far.data.polygons:
        if shore_d(p.center.x, p.center.y) > BEACH + 4:
            p.material_index = 1
    fondo = principled("FondoMar", (0.008, 0.04, 0.05), 0.9)
    mesh_obj("FondoMar", [(-40000, -40000, SEA - 6.5), (40000, -40000, SEA - 6.5), (40000, 40000, SEA - 6.5), (-40000, 40000, SEA - 6.5)],
             [(0, 1, 2, 3)], fondo, coll)
    build_ocean(M, coll)
    return sand


# ---------------------------------------------------------------- vegetación
def load_ph(lib, ident, lod="LOD1", tag=None):
    """Variantes de un modelo de Poly Haven (una por letra), en el nivel de detalle pedido, como
    colección para instanciar al azar. Se dejan en el origen."""
    path = os.path.join(PH, ident, ident + ".blend")
    with bpy.data.libraries.load(path) as (a, b):
        names = [n for n in a.objects if n.endswith("_" + lod)] or [n for n in a.objects if "LOD" not in n]
        if tag:
            names = [n for n in names if tag in n]
        b.objects = names
    coll = bpy.data.collections.new("PH_" + ident)
    lib.children.link(coll)
    for o in b.objects:
        coll.objects.link(o)
        o.location = (0, 0, 0)
        o.rotation_euler = (0, 0, 0)
        o.parent = None
    return coll


def load_assets(M):
    """Pastos Botaniq (tonos dorados de duna) y vegetación costera de Poly Haven: arbustos de
    matorral, suculentas rastreras (como la doca), pastos y flores silvestres, rocas y troncos."""
    lib = bpy.data.collections.new("Biblioteca")
    bpy.context.scene.collection.children.link(lib)
    with bpy.data.libraries.load(CAMPO) as (a, b):
        b.objects = [n for n in a.objects if n.startswith("Grass")]
    bq = {}
    for o in b.objects:
        lib.objects.link(o)
        for sl in o.material_slots:
            sl.material = M["pastoDuna"]
        for md in o.modifiers:
            if md.type == "SUBSURF":
                md.levels = md.render_levels = min(md.render_levels, 1)
        bq[o.name.split("_spring")[0]] = o
    ph = {
        "searsia": load_ph(lib, "searsia_lucida"),
        "didelta": load_ph(lib, "didelta_spinosa"),
        "othonna": load_ph(lib, "othonna_cerarioides", "LOD2"),
        "rooibos": load_ph(lib, "wild_rooibos_bush", "LOD1"),
        "doca": load_ph(lib, "crystalline_iceplant", "LOD1"),
        "cheiri": load_ph(lib, "cheiridopsis_succulent", "LOD2"),
        "flor": load_ph(lib, "flower_heliophila", "LOD2"),
        "roca": load_ph(lib, "namaqualand_boulder_02", "LOD2"),
    }
    lib.hide_render = lib.hide_viewport = True
    return bq, ph


def place_props(coll_lib):
    """Rocas de costa en la punta de la playa y troncos de deriva en la arena (ubicados a mano)."""
    coll = bpy.data.collections.new("Rocas")
    bpy.context.scene.collection.children.link(coll)
    rk = load_ph(coll_lib, "coast_rocks_01", "LOD2")
    src = rk.objects[0]
    for x, rot, sc in ((-150.0, 0.5, 1.0), (175.0, 2.3, 0.8)):
        o = src.copy()
        coll.objects.link(o)
        y = shore_y(x) - 6.0
        o.location = (x, y, SEA - 1.2)
        o.rotation_euler = (0, 0, rot)
        o.scale = (sc, sc, sc * 1.4)
    tr = load_ph(coll_lib, "dead_tree_trunk")
    br = load_ph(coll_lib, "dry_branches_medium_01")
    for k, (x, off, rot) in enumerate(((-24.0, 9.0, 0.4), (31.0, 7.5, 2.0), (-6.0, 11.0, 1.2))):
        y = shore_y(x) + off
        src = tr.objects[0] if k < 2 else br.objects[0]
        o = src.copy()
        coll.objects.link(o)
        o.location = (x, y, terrain_h(x, y) + 0.05)
        o.rotation_euler = (0, 0, rot)


def build_vegetation(sand, bq, ph):
    """Pastos de duna y arbustos con nodos de geometría sobre el terreno cercano, según un
    atributo 'veg' (0 en la playa, la pasarela y bajo la casa; 1 en la duna)."""
    me = sand.data
    veg, cam = [], []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = shore_d(x, y)
        w = min(1.0, max(0.0, (d - BEACH - 1.5) / 5.0))
        w *= min(1.0, max(0.0, (house_dist(x, y) - 0.2) / 1.5))
        # sendero de arena desde la escalera de la terraza hasta la playa
        pd = path_dist(x, y)
        w *= min(1.0, max(0.0, (pd - 0.9) / 1.3))
        if 8 < y < 95:
            w *= min(1.0, max(0.0, (road_dist(x, y) - 1.6) / 1.5))
        cam.append(min(1.0, max(0.0, 1.4 - pd / 0.9)) if d > BEACH - 3 else 0.0)
        w *= min(1.0, max(0.0, 0.55 + 1.3 * noise.noise(Vector((x / 7.0, y / 7.0, 2.2)))
                          + 0.4 * noise.noise(Vector((x / 2.5, y / 2.5, 4.1)))))
        veg.append(max(0.0, min(1.0, w)))
    at = me.attributes.new("veg", "FLOAT", "POINT")
    at.data.foreach_set("value", veg)
    at = me.attributes.new("camino", "FLOAT", "POINT")
    at.data.foreach_set("value", cam)
    ng = bpy.data.node_groups.new("Duna", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])

    def scatter(obj, dens, smin, smax, seed, lo=0.4, hi=0.65, nscale=0.15, tilt=0.12):
        d = N.new("GeometryNodeDistributePointsOnFaces")
        d.inputs["Seed"].default_value = seed
        z = N.new("ShaderNodeTexNoise")
        z.noise_dimensions = "4D"
        z.inputs["W"].default_value = seed * 7.3
        z.inputs["Scale"].default_value = nscale
        r = N.new("ShaderNodeMapRange")
        r.inputs[1].default_value, r.inputs[2].default_value = lo, hi
        r.inputs[3].default_value, r.inputs[4].default_value = 0.0, dens
        Lk.new(z.outputs["Fac"], r.inputs[0])
        na = N.new("GeometryNodeInputNamedAttribute")
        na.data_type = "FLOAT"
        na.inputs["Name"].default_value = "veg"
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        Lk.new(r.outputs[0], mul.inputs[0])
        Lk.new(na.outputs["Attribute"], mul.inputs[1])
        Lk.new(mul.outputs[0], d.inputs["Density"])
        ins = N.new("GeometryNodeInstanceOnPoints")
        if isinstance(obj, bpy.types.Collection):   # una variante al azar de la colección
            oi = N.new("GeometryNodeCollectionInfo")
            oi.inputs["Collection"].default_value = obj
            oi.inputs["Separate Children"].default_value = True
            oi.inputs["Reset Children"].default_value = True
            ins.inputs["Pick Instance"].default_value = True
            ri = N.new("FunctionNodeRandomValue")
            ri.data_type = "INT"
            for sk in ri.inputs:
                if sk.type == "INT" and sk.name in ("Min", "Max"):
                    sk.default_value = 0 if sk.name == "Min" else len(obj.objects) - 1
            ri.inputs["Seed"].default_value = seed + 2
            Lk.new(next(o for o in ri.outputs if o.type == "INT"), ins.inputs["Instance Index"])
        else:
            oi = N.new("GeometryNodeObjectInfo")
            oi.inputs[0].default_value = obj
        rr = N.new("FunctionNodeRandomValue")
        rr.data_type = "FLOAT_VECTOR"
        rr.inputs["Max"].default_value = (tilt, tilt, 6.28)
        rr.inputs["Seed"].default_value = seed
        rs = N.new("FunctionNodeRandomValue")
        rs.data_type = "FLOAT"
        for sk in rs.inputs:
            if sk.type == "VALUE" and sk.name in ("Min", "Max"):
                sk.default_value = smin if sk.name == "Min" else smax
        rs.inputs["Seed"].default_value = seed + 1
        Lk.new(gi.outputs[0], d.inputs["Mesh"])
        Lk.new(d.outputs["Points"], ins.inputs["Points"])
        Lk.new(oi.outputs[0], ins.inputs["Instance"])
        Lk.new(rr.outputs[0], ins.inputs["Rotation"])
        Lk.new(next(o for o in rs.outputs if o.type == "VALUE"), ins.inputs["Scale"])
        Lk.new(ins.outputs[0], join.inputs[0])

    # pastos: dorados de duna (Botaniq) y verdes silvestres (Poly Haven), en manchones
    # (sólo los pastos Botaniq de hojas modeladas: los de tarjeta vienen sin su textura de recorte)
    scatter(bq["Grass_Tall_A"], 14.0, 1.6, 2.6, 21, 0.3, 0.55)
    scatter(bq["Grass_Karl-foerster_B"], 1.6, 0.7, 1.1, 24, 0.38, 0.6, 0.25)
    scatter(ph["flor"], 0.4, 0.8, 1.2, 27, 0.5, 0.62, 0.2)
    # matorral costero: arbustos agrupados
    scatter(ph["searsia"], 0.16, 0.9, 1.6, 31, 0.38, 0.58, 0.06, 0.06)
    scatter(ph["didelta"], 0.06, 0.6, 1.1, 32, 0.42, 0.6, 0.05, 0.05)
    scatter(ph["othonna"], 0.35, 1.0, 1.6, 34, 0.38, 0.6, 0.1, 0.06)
    scatter(ph["rooibos"], 0.45, 1.5, 2.4, 35, 0.38, 0.6, 0.1, 0.06)
    # rastreras tipo doca (alfombras) y suculentas en los bordes con arena
    scatter(ph["doca"], 14.0, 2.0, 3.5, 36, 0.42, 0.56, 0.1, 0.02)
    scatter(ph["cheiri"], 0.8, 0.9, 1.4, 37, 0.42, 0.62, 0.15, 0.03)
    scatter(ph["roca"], 0.004, 0.4, 1.0, 40, 0.55, 0.62, 0.05, 0.4)
    Lk.new(join.outputs[0], go.inputs[0])
    md = sand.modifiers.new("Duna", "NODES")
    md.node_group = ng



# ---------------------------------------------------------------- contexto: camino, vecinos, árboles
# camino de tierra que llega por detrás de la casa (porch de acceso) y sube hacia los cerros
ROAD = [(8.7, 10.5), (12.0, 30.0), (18.0, 60.0), (8.0, 100.0), (-25.0, 150.0), (-70.0, 210.0),
        (-110.0, 290.0), (-150.0, 380.0), (-210.0, 480.0), (-260.0, 620.0), (-300.0, 800.0)]


def road_points(step=1.5):
    """Puntos del eje del camino (Catmull-Rom por los nodos de ROAD)."""
    pts = []
    P = [ROAD[0]] + ROAD + [ROAD[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = (Vector(P[i - 1]), Vector(P[i]), Vector(P[i + 1]), Vector(P[i + 2]))
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n
            pts.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    pts.append(Vector(ROAD[-1]))
    return pts


_ROAD_PTS = None


def road_dist(x, y):
    """Distancia (m) al eje del camino (sólo se usa cerca de la casa)."""
    global _ROAD_PTS
    if _ROAD_PTS is None:
        _ROAD_PTS = road_points(1.0)
    if y < 8 or y > 140:
        return 99.0
    return min(math.hypot(x - p.x, y - p.y) for p in _ROAD_PTS if abs(p.y - y) < 6)


def road_mat():
    """Huella de tierra: dos surcos de ruedas más oscuros y pasto en el centro y los bordes."""
    m, n, l = new_mat("Camino")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    uv = n.new("ShaderNodeUVMap")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(uv.outputs["UV"], sep.inputs[0])
    tc = n.new("ShaderNodeTexCoord")
    v = sep.outputs["Y"]
    rut = N.math("MAXIMUM", N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.27)), 0.0, 0.12)),
                 N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.73)), 0.0, 0.12)))
    mid = N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.5)), 0.04, 0.12))
    edge = N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.5)), 0.38, 0.5)
    nz = N.noise(tc.outputs["Object"], 1.2, 5)
    col = N.mix(N.math("MULTIPLY", rut, 0.7), (0.4, 0.33, 0.24), (0.27, 0.22, 0.15))
    grass = N.math("MULTIPLY", N.math("MAXIMUM", mid, edge), N.smooth(nz, 0.35, 0.6))
    col = N.mix(grass, col, (0.16, 0.16, 0.08))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    # el borde se funde con el terreno
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    l.new(N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.5)), 0.42, 0.5), mx.inputs["Fac"])
    l.new(b.outputs[0], mx.inputs[1])
    l.new(tr.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def build_road(coll):
    pts = road_points(1.5)
    verts, faces, uvs = [], [], []
    half = 1.8
    for i, p in enumerate(pts):
        q = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        nrm = Vector((-q.y, q.x)).normalized()
        lift = 0.04 if p.y < 85 else 0.35        # sobre el terreno lejano (malla gruesa) va más alto
        for sgn in (-1, 1):
            a = p + nrm * half * sgn
            verts.append((a.x, a.y, terrain_h(a.x, a.y) + lift))
    for i in range(len(pts) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    o = mesh_obj("Camino", verts, faces, road_mat(), coll)
    uvl = o.data.uv_layers.new(name="UVMap")
    for poly in o.data.polygons:
        for li in poly.loop_indices:
            vi = o.data.loops[li].vertex_index
            uvl.data[li].uv = ((vi // 2) * 1.5 / 4.0, float(vi % 2))
    return o


VECINOS = [  # x, y, giro (°), ancho, fondo, alto de muro, muro, techo
    (55.0, 165.0, 20, 11, 7, 2.7, "blanco", "gris"), (-88.0, 245.0, -15, 9, 6, 2.6, "madera", "gris"),
    (-120.0, 262.0, 5, 12, 7, 2.8, "blanco", "teja"), (95.0, 330.0, 35, 10, 7, 2.6, "negro", "gris"),
    (-185.0, 420.0, -25, 9, 6, 2.6, "madera", "teja"), (170.0, 470.0, 10, 13, 8, 3.0, "blanco", "gris"),
    (-265.0, 530.0, 0, 10, 7, 2.7, "blanco", "teja"), (265.0, 395.0, -40, 9, 6, 2.6, "madera", "gris"),
    (-35.0, 590.0, 15, 11, 7, 2.7, "negro", "gris"), (-330.0, 650.0, 30, 10, 6, 2.6, "blanco", "teja"),
    (330.0, 560.0, -10, 12, 7, 2.8, "blanco", "gris"),
]


def build_neighbors(coll):
    """Casas vecinas lejanas (volúmenes simples a dos aguas): dan contexto sin quitar calma."""
    mats = {"blanco": principled("VecMuroBlanco", (0.62, 0.6, 0.56), 0.8),
            "madera": principled("VecMuroMadera", (0.32, 0.22, 0.14), 0.7),
            "negro": principled("VecMuroNegro", (0.03, 0.03, 0.03), 0.6),
            "gris": principled("VecTechoGris", (0.08, 0.08, 0.085), 0.5),
            "teja": principled("VecTechoTeja", (0.22, 0.09, 0.05), 0.7),
            "vidrio": principled("VecVentana", (0.02, 0.025, 0.03), 0.1)}
    for k, (x, y, rot, w, d, h, wall, roof) in enumerate(VECINOS):
        z = min(terrain_h(x + dx, y + dy) for dx in (-w / 2, w / 2) for dy in (-d / 2, d / 2)) - 0.3
        r = h + w * 0.28
        verts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0),
                 (-w / 2, -d / 2, h), (w / 2, -d / 2, h), (w / 2, d / 2, h), (-w / 2, d / 2, h),
                 (0, -d / 2, r), (0, d / 2, r)]
        faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 8), (6, 7, 9)]
        o = mesh_obj(f"Vecino{k}", verts, faces, mats[wall], coll)
        roof_v = [(-w / 2 - 0.4, -d / 2 - 0.4, h - 0.2), (0, -d / 2 - 0.4, r), (0, d / 2 + 0.4, r),
                  (-w / 2 - 0.4, d / 2 + 0.4, h - 0.2), (w / 2 + 0.4, -d / 2 - 0.4, h - 0.2), (w / 2 + 0.4, d / 2 + 0.4, h - 0.2)]
        t = mesh_obj(f"VecinoTecho{k}", roof_v, [(0, 1, 2, 3), (1, 4, 5, 2)], mats[roof], coll)
        sol = t.modifiers.new("e", "SOLIDIFY")
        sol.thickness = 0.15
        win = mesh_obj(f"VecinoVentana{k}", [(-w * 0.3, -d / 2 - 0.02, 0.9), (w * 0.3, -d / 2 - 0.02, 0.9),
                                             (w * 0.3, -d / 2 - 0.02, h - 0.4), (-w * 0.3, -d / 2 - 0.02, h - 0.4)],
                       [(0, 1, 2, 3)], mats["vidrio"], coll)
        for ob in (o, t, win):
            ob.location = (x, y, z)
            ob.rotation_euler = (0, 0, math.radians(rot))


def foliage_mat(name, c1, c2):
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    info = n.new("ShaderNodeObjectInfo")
    tc = n.new("ShaderNodeTexCoord")
    v = N.math("ADD", N.math("MULTIPLY", info.outputs["Random"], 0.6), N.math("MULTIPLY", N.noise(tc.outputs["Object"], 3.0, 4), 0.4))
    l.new(N.mix(v, c1, c2), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.8
    l.new(N.noise(tc.outputs["Object"], 4.0, 4), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def make_trees(lib):
    """Pinos y cipreses macrocarpa simples (sólo se ven a lo lejos): tronco + copas irregulares."""
    bark = principled("Corteza", (0.08, 0.06, 0.045), 0.9)
    pino = foliage_mat("CopaPino", (0.018, 0.03, 0.016), (0.045, 0.06, 0.03))
    cipres = foliage_mat("CopaCipres", (0.022, 0.036, 0.018), (0.055, 0.07, 0.033))
    out = []
    rnd = random.Random(3)
    for k in range(4):
        parts = []
        h = rnd.uniform(9, 15)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.22, depth=h, location=(0, 0, h / 2))
        parts.append(bpy.context.object)
        parts[-1].data.materials.append(bark)
        cyp = k >= 2
        for j in range(5 if cyp else 4):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
            c = bpy.context.object
            if cyp:   # macrocarpa: copa ancha y aplanada, en capas
                c.location = (rnd.uniform(-1.5, 1.5), rnd.uniform(-1.5, 1.5), h * rnd.uniform(0.55, 0.95))
                c.scale = (rnd.uniform(2.5, 3.5), rnd.uniform(2.5, 3.5), rnd.uniform(1.3, 1.9))
            else:     # pino: copa alta y redondeada
                c.location = (rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), h * (0.72 + 0.08 * j))
                c.scale = (rnd.uniform(1.8, 2.6), rnd.uniform(1.8, 2.6), rnd.uniform(0.9, 1.3))
            dsp = c.modifiers.new("d", "DISPLACE")
            tex = bpy.data.textures.new(f"copa{k}{j}", "CLOUDS")
            tex.noise_scale = 0.6
            dsp.texture, dsp.strength = tex, 0.6
            c.data.materials.append(cipres if cyp else pino)
            parts.append(c)
        bpy.ops.object.select_all(action="DESELECT")
        for o in parts:
            o.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.convert(target="MESH")
        bpy.ops.object.join()
        t = bpy.context.object
        t.name = f"Arbol{k}"
        for c in t.users_collection:
            c.objects.unlink(t)
        lib.objects.link(t)
        out.append(t)
    return out


def build_far_trees(far, trees):
    """Arboledas en el paisaje lejano: en manchones, más en los cerros y junto a las casas
    vecinas; nunca en la playa ni cerca de la casa (atributo 'bosque')."""
    me = far.data
    w = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = shore_d(x, y)
        a = min(1.0, max(0.0, (d - BEACH - 25) / 40.0)) * min(1.0, max(0.0, (math.hypot(x - 6, y - 4) - 110) / 80.0))
        clump = 0.5 + 0.5 * noise.noise(Vector((x / 140.0, y / 140.0, 7.7)))
        near_house = max((max(0.0, 1.0 - math.hypot(x - vx, y - vy) / 45.0) for vx, vy, *_ in VECINOS), default=0)
        hill = min(1.0, max(0.0, (y - 250) / 250.0))
        w.append(a * min(1.0, max(0.0, (clump - 0.45) * 3.0 + 0.6 * hill + 0.8 * near_house)))
    at = me.attributes.new("bosque", "FLOAT", "POINT")
    at.data.foreach_set("value", w)
    lib_c = bpy.data.collections.new("Arboles")
    bpy.data.collections["Biblioteca"].children.link(lib_c)
    for t in trees:
        for c in t.users_collection:
            c.objects.unlink(t)
        lib_c.objects.link(t)
    ng = bpy.data.node_groups.new("Arboleda", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = 5.0
    dist.inputs["Density Max"].default_value = 0.012
    na = N.new("GeometryNodeInputNamedAttribute")
    na.data_type = "FLOAT"
    na.inputs["Name"].default_value = "bosque"
    Lk.new(na.outputs["Attribute"], dist.inputs["Density Factor"])
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    ins = N.new("GeometryNodeInstanceOnPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = lib_c
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    ins.inputs["Pick Instance"].default_value = True
    ri = N.new("FunctionNodeRandomValue")
    ri.data_type = "INT"
    for sk in ri.inputs:
        if sk.type == "INT" and sk.name in ("Min", "Max"):
            sk.default_value = 0 if sk.name == "Min" else len(trees) - 1
    rr = N.new("FunctionNodeRandomValue")
    rr.data_type = "FLOAT_VECTOR"
    rr.inputs["Max"].default_value = (0.05, 0.05, 6.28)
    rs = N.new("FunctionNodeRandomValue")
    rs.data_type = "FLOAT"
    for sk in rs.inputs:
        if sk.type == "VALUE" and sk.name in ("Min", "Max"):
            sk.default_value = 0.7 if sk.name == "Min" else 1.3
    Lk.new(dist.outputs["Points"], ins.inputs["Points"])
    Lk.new(ci.outputs[0], ins.inputs["Instance"])
    Lk.new(next(o for o in ri.outputs if o.type == "INT"), ins.inputs["Instance Index"])
    Lk.new(rr.outputs[0], ins.inputs["Rotation"])
    Lk.new(next(o for o in rs.outputs if o.type == "VALUE"), ins.inputs["Scale"])
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])
    Lk.new(ins.outputs[0], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = far.modifiers.new("Arboleda", "NODES")
    md.node_group = ng


def build_context(M):
    coll = bpy.data.collections.new("Contexto")
    bpy.context.scene.collection.children.link(coll)
    build_road(coll)
    build_neighbors(coll)
    build_far_trees(bpy.data.objects["Lejos"], make_trees(bpy.data.collections["Biblioteca"]))


# ---------------------------------------------------------------- cielo, render y cámara
def build_world():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Cielo")
    sc.world = w
    n, l = w.node_tree.nodes, w.node_tree.links
    bg = n["Background"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    b = (HDRI_SUN_U - 0.5) * 2 * math.pi
    az0 = math.degrees(math.atan2(math.cos(b), -math.sin(b)))
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(SUN_AZ - az0))
    env = n.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    l.new(tc.outputs["Generated"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], env.inputs["Vector"])
    # la cámara ve el cielo del HDRI sólo en lo alto (nubes); cerca del horizonte, donde el HDRI
    # trae su propio paisaje (árboles, una pérgola), ve un cielo físico con el sol en el mismo lugar
    sky = n.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = False
    sky.sun_elevation = math.radians(SUN_ELEV)
    sky.sun_rotation = math.radians(90.0 - SUN_AZ)
    sky.aerosol_density = 2.0
    gain = n.new("ShaderNodeMix")
    gain.data_type = "RGBA"
    gain.blend_type = "MULTIPLY"
    gain.inputs[0].default_value = 1.0
    gain.inputs[7].default_value = (SKY_GAIN, SKY_GAIN, SKY_GAIN, 1)
    l.new(sky.outputs["Color"], gain.inputs[6])
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Generated"], sep.inputs[0])
    hi = n.new("ShaderNodeMapRange")
    hi.interpolation_type = "SMOOTHSTEP"
    hi.inputs[1].default_value, hi.inputs[2].default_value = 0.3, 0.6   # seno de la elevación
    l.new(sep.outputs["Z"], hi.inputs[0])
    cam_sky = n.new("ShaderNodeMix")
    cam_sky.data_type = "RGBA"
    l.new(hi.outputs[0], cam_sky.inputs[0])
    l.new(gain.outputs[2], cam_sky.inputs[6])
    l.new(env.outputs["Color"], cam_sky.inputs[7])
    lp = n.new("ShaderNodeLightPath")
    pick = n.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    seen = n.new("ShaderNodeMath")          # cámara o reflejos (mar, vidrios) ven el cielo limpio
    seen.operation = "MAXIMUM"
    l.new(lp.outputs["Is Camera Ray"], seen.inputs[0])
    l.new(lp.outputs["Is Glossy Ray"], seen.inputs[1])
    l.new(seen.outputs[0], pick.inputs[0])
    l.new(env.outputs["Color"], pick.inputs[6])
    l.new(cam_sky.outputs[2], pick.inputs[7])
    l.new(pick.outputs[2], bg.inputs[0])
    w.mist_settings.start = 60
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
    cy.max_bounces = 6
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 2
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 12
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    cy.use_denoising = True
    w, h = (int(v) for v in opts["res"].split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.use_white_balance = True
    sc.view_settings.white_balance_temperature = WB_TEMP
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.35
    sc.view_layers[0].use_pass_mist = True
    # bruma atmosférica azulada en compositor (sólo sobre el terreno lejano)
    nt = bpy.data.node_groups.new("Bruma", "CompositorNodeTree")
    nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    sc.compositing_node_group = nt
    rl = nt.nodes.new("CompositorNodeRLayers")
    go = nt.nodes.new("NodeGroupOutput")

    def mnode(op, b):
        nd = nt.nodes.new("ShaderNodeMath")
        nd.operation = op
        nd.inputs[1].default_value = b
        return nd

    lt, pw, amt, mul = mnode("LESS_THAN", 0.999), mnode("POWER", 0.9), mnode("MULTIPLY", 0.62), mnode("MULTIPLY", 1.0)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0.66, 0.72, 0.78, 1)
    nt.links.new(rl.outputs["Mist"], lt.inputs[0])
    nt.links.new(rl.outputs["Mist"], pw.inputs[0])
    nt.links.new(pw.outputs[0], mul.inputs[0])
    nt.links.new(lt.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], amt.inputs[0])
    nt.links.new(amt.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[6])
    nt.links.new(mix.outputs[2], go.inputs[0])


# tomas fijas de dron desde el mar, a cada lado del frente (más abiertas que en Lingue, para
# poder reencuadrar y desenfocar en la edición)
VISTAS = {
    "izq": ((-22.0, -60.0, 17.0), (5.0, -8.0, -1.5), 30),
    "der": ((34.0, -60.0, 17.0), (7.0, -8.0, -1.5), 30),
    # opuestas: desde atrás (acceso y camino), mirando hacia el mar
    "izq_atras": ((36.0, 58.0, 16.0), (4.0, -6.0, -2.0), 30),
    "der_atras": ((-24.0, 58.0, 16.0), (8.0, -6.0, -2.0), 30),
}


def build_camera():
    sc = bpy.context.scene
    cam = link(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
    sc.camera = cam
    loc, tgt, lens = VISTAS[opts["vista"]]
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.clip_end = 5000
    return cam


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = materials()
    load_house(M)
    sand = build_landscape(M)
    bq, ph = load_assets(M)
    build_vegetation(sand, bq, ph)
    place_props(bpy.data.collections["Biblioteca"])
    build_context(M)
    build_world()
    setup_render()
    build_camera()
    sc = bpy.context.scene
    if opts["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=opts["save"])
    sc.frame_set(int(opts["still"]))
    sc.render.filepath = opts["out"]
    bpy.ops.render.render(write_still=True)


main()
