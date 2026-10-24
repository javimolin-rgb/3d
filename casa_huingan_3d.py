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
        "wb": "6300", "save": None}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(5)
ROOT = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.join(ROOT, "assets", "huingan", "casa.blend")
CAMPO = os.path.join(ROOT, "assets", "campo", "pastos_botaniq.blend")
ARBUSTO = os.path.join(ROOT, "assets", "playa", "shrub_03", "shrub_03_2k.blend")
HDRI = os.path.join(ROOT, "assets", "cielo", "DaySkyHDRI065A_2K_HDR.exr")  # ambientCG, CC0
HDRI_SUN_U = 0.4983          # columna del sol en el HDRI (0-1); elevación 59,5°
SUN_AZ = 215.0               # sol desde adelante-izquierda (azimut desde +Y hacia +X)
WB_TEMP = float(opts["wb"])
L, D = 12.18, 9.24           # ancho y fondo total del casco (terraza + caja + porch)
HC = Vector((L / 2, 4.6))    # centro de la casa en planta
GROUND = -0.31               # terreno bajo la casa
SEA = -7.0                   # nivel del mar (la casa está en una meseta de duna sobre la playa)
SHORE_Y = -45.0              # orilla frente a la casa: la punta de la península
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
    dry = N.mix(N.math("MULTIPLY_ADD", big, 1.6, -0.3), (0.4, 0.32, 0.22), (0.53, 0.43, 0.3))
    dry = N.mix(N.math("MULTIPLY", mid, 0.35), dry, (0.33, 0.26, 0.18))
    wet = (0.22, 0.19, 0.14)
    wet_f = N.math("SUBTRACT", 1.0, N.smooth(d, 0.6, 4.5))
    col = N.mix(wet_f, dry, wet)
    # línea de marea: restos oscuros discontinuos
    tide = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", d, 5.5)), 0.0, 0.6)),
                  N.smooth(N.noise(tc.outputs["Object"], 1.3, 3), 0.55, 0.62))
    col = N.mix(N.math("MULTIPLY", tide, 0.7), col, (0.12, 0.1, 0.07))
    depth = N.math("MULTIPLY", d, -1.0)
    col = N.mix(N.smooth(depth, 0.0, 7.0), col, (0.14, 0.24, 0.19))
    col = N.mix(N.smooth(depth, 5.0, 45.0), col, (0.015, 0.07, 0.075))
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "veg"
    soil = N.mix(N.smooth(N.noise(tc.outputs["Object"], 2.0, 5), 0.35, 0.6), (0.2, 0.17, 0.11), (0.1, 0.11, 0.06))
    col = N.mix(N.math("MULTIPLY", at.outputs["Fac"], 0.75), col, soil)
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
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    d = N.math("MULTIPLY", shore_d_nodes(N, sep), -1.0)  # distancia mar adentro (m)
    # superficie: transparente (deja pasar el sol, así el fondo de arena se ilumina sin cáusticas)
    # + reflejo del cielo según Fresnel; el color del agua lo da el fondo (sand_mat)
    n.remove(b)
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.82, 0.93, 0.9, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.05
    fr = n.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.333
    wat = n.new("ShaderNodeMixShader")
    l.new(fr.outputs["Fac"], wat.inputs["Fac"])
    l.new(tr.outputs[0], wat.inputs[1])
    l.new(gl.outputs[0], wat.inputs[2])
    # olas: paralelas a la orilla, con ruido
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.35, 1.0, 1.0)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    w1 = N.noise(mp.outputs["Vector"], 0.35, 7, 0.6)
    w2 = N.noise(tc.outputs["Object"], 1.6, 5, 0.55)
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.6
    bmp.inputs["Distance"].default_value = 0.6
    l.new(N.math("ADD", w1, N.math("MULTIPLY", w2, 0.3)), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], gl.inputs["Normal"])
    l.new(bmp.outputs["Normal"], fr.inputs["Normal"])
    # espuma: borde de la orilla + dos líneas de rompiente, rotas por ruido
    mf = n.new("ShaderNodeMapping")
    mf.inputs["Scale"].default_value = (0.12, 1.0, 1.0)
    l.new(tc.outputs["Object"], mf.inputs["Vector"])
    brk = N.noise(mf.outputs["Vector"], 1.2, 6, 0.65, 0.8)
    lace = N.noise(tc.outputs["Object"], 3.0, 8, 0.7, 2.0)
    edge = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(d, 0.3, 0.9)), N.smooth(d, 0.0, 0.25))
    lines = 0
    for c, wdt in ((7.0, 0.9), (15.0, 1.3), (26.0, 1.6)):
        band = N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", d, c)), 0.0, wdt))
        lines = band if lines == 0 else N.math("MAXIMUM", lines, band)
    foam = N.math("MAXIMUM", N.math("MULTIPLY", edge, N.smooth(brk, 0.4, 0.55)),
                  N.math("MULTIPLY", lines, N.smooth(brk, 0.45, 0.6)))
    foam = N.math("MULTIPLY", foam, N.smooth(lace, 0.35, 0.6))
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
    """Cerros costeros: bosque de pinos oscuro con claros de pasto seco."""
    m, n, l = new_mat("Cerros")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    f = N.noise(tc.outputs["Object"], 0.012, 6, 0.6)
    g = N.noise(tc.outputs["Object"], 0.15, 4)
    col = N.mix(N.smooth(f, 0.32, 0.46), (0.22, 0.2, 0.11), (0.012, 0.03, 0.014))
    col = N.mix(N.math("MULTIPLY", g, 0.4), col, (0.02, 0.035, 0.02))
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
    col = N.mix(N.smooth(f, 0.45, 0.6), (0.45, 0.39, 0.24), (0.12, 0.16, 0.07))
    col = N.mix(N.math("MULTIPLY", g, 0.35), col, (0.06, 0.08, 0.04))
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
    e[0].color, e[1].color = (0.25, 0.3, 0.14, 1), (0.6, 0.48, 0.27, 1)
    e.new(0.45).color = (0.47, 0.42, 0.22, 1)
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


BEACH = 14.0     # ancho de la playa (m)
SLOPE_W = 26.0   # ancho de la ladera de la duna que sube desde la playa hasta la meseta


def terrain_base(x, y):
    """Perfil sin ondulaciones: fondo marino < playa < ladera de duna < meseta de la casa."""
    d = shore_d(x, y)
    if d < 0:
        return SEA + max(d * 0.05, -6.0)
    if d < BEACH:
        return SEA + d * 0.04
    t = min(1.0, (d - BEACH) / SLOPE_W)
    t = t * t * (3 - 2 * t)
    top = SEA + BEACH * 0.04
    return top + t * (GROUND - top)


def terrain_h(x, y):
    h = terrain_base(x, y)
    d = shore_d(x, y)
    # dunas suaves en la meseta y en la ladera; se aplanan junto a la casa
    amp = min(1.0, max(0.0, (d - BEACH - 3) / 12.0)) * (0.9 + min(1.0, max(0.0, (d - 60) / 60.0)) * 1.8)
    flat = min(1.0, max(0.0, (house_dist(x, y) - 1.0) / 8.0))
    dn = noise.noise(Vector((x / 16.0, y / 12.0, 0.3))) + 0.4 * noise.noise(Vector((x / 5.0, y / 4.0, 1.7)))
    h += amp * flat * (0.4 + 0.7 * dn)
    # cerros costeros al fondo, tierra adentro
    if y > 280:
        r = min(1.0, (y - 280) / 300.0)
        hn = 0.5 + 0.5 * noise.noise(Vector((x / 180.0, y / 140.0, 3.1)))
        h += r * r * (30 + 90 * hn)
    return h + 0.02 * noise.noise(Vector((x * 1.3, y * 1.3, 9.0)))


def grid(name, x0, x1, y0, y1, step, mat, coll=None, skip=None):
    nx, ny = int(round((x1 - x0) / step)) + 1, int(round((y1 - y0) / step)) + 1
    verts = [(x0 + i * step, y0 + j * step, terrain_h(x0 + i * step, y0 + j * step)) for j in range(ny) for i in range(nx)]
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            if skip and skip(x0 + (i + 0.5) * step, y0 + (j + 0.5) * step):
                continue
            faces.append((j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i))
    o = mesh_obj(name, verts, faces, mat, coll)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def build_landscape(M):
    coll = bpy.data.collections.new("Paisaje")
    bpy.context.scene.collection.children.link(coll)
    near = (-90, 110, -70, 90)
    sand = grid("Playa", *near, 0.75, M["arena"], coll)
    # lejos: playa y dunas hacia los costados + cerros (sin el hueco del terreno cercano)
    inside = lambda x, y: near[0] < x < near[1] and near[2] < y < near[3]  # noqa: E731
    far = grid("Lejos", -900, 1000, -300, 1300, 10.0, M["arena"], coll, skip=inside)
    far.data.materials.append(M["matorral"])
    far.data.materials.append(M["cerros"])
    for p in far.data.polygons:
        if p.center.y > 290:
            p.material_index = 2
        elif shore_d(p.center.x, p.center.y) > BEACH + 4:
            p.material_index = 1
    fondo = principled("FondoMar", (0.008, 0.04, 0.05), 0.9)
    mesh_obj("FondoMar", [(-3000, -3000, SEA - 6.5), (3000, -3000, SEA - 6.5), (3000, 3000, SEA - 6.5), (-3000, 3000, SEA - 6.5)],
             [(0, 1, 2, 3)], fondo, coll)
    mesh_obj("Mar", [(-3000, -3000, SEA), (3000, -3000, SEA), (3000, 3000, SEA), (-3000, 3000, SEA)],
             [(0, 1, 2, 3)], M["mar"], coll)
    return sand


# ---------------------------------------------------------------- vegetación
def load_assets(M):
    lib = bpy.data.collections.new("Biblioteca")
    bpy.context.scene.collection.children.link(lib)
    with bpy.data.libraries.load(CAMPO) as (a, b):
        b.objects = a.objects
    bq = {}
    for o in b.objects:
        lib.objects.link(o)
        for sl in o.material_slots:
            sl.material = M["pastoDuna"] if o.name.startswith("Grass") else M["roca"]
        for md in o.modifiers:
            if md.type == "SUBSURF":
                md.levels = md.render_levels = min(md.render_levels, 1)
        bq[o.name.split("_spring")[0]] = o
    with bpy.data.libraries.load(ARBUSTO) as (a, b):
        b.objects = [n for n in a.objects if n.endswith("LOD1")]
    shrubs = []
    for o in b.objects:
        lib.objects.link(o)
        o.location = (0, 0, 0)
        shrubs.append(o)
    lib.hide_render = lib.hide_viewport = True
    return bq, shrubs


def build_vegetation(sand, bq, shrubs):
    """Pastos de duna y arbustos con nodos de geometría sobre el terreno cercano, según un
    atributo 'veg' (0 en la playa, la pasarela y bajo la casa; 1 en la duna)."""
    me = sand.data
    veg = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = shore_d(x, y)
        w = min(1.0, max(0.0, (d - BEACH - 1.5) / 5.0))
        w *= min(1.0, max(0.0, (house_dist(x, y) - 0.2) / 1.5))
        # sendero de arena desde la escalera de la terraza hasta la playa
        px = 1.0 + 3.0 * math.sin(y / 9.0)
        if y < 0.5:
            w *= min(1.0, max(0.0, (abs(x - px) - 0.5) / 1.2))
        w *= min(1.0, max(0.0, 0.55 + 1.3 * noise.noise(Vector((x / 7.0, y / 7.0, 2.2)))
                          + 0.4 * noise.noise(Vector((x / 2.5, y / 2.5, 4.1)))))
        veg.append(max(0.0, min(1.0, w)))
    at = me.attributes.new("veg", "FLOAT", "POINT")
    at.data.foreach_set("value", veg)
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
        Lk.new(oi.outputs["Geometry"], ins.inputs["Instance"])
        Lk.new(rr.outputs[0], ins.inputs["Rotation"])
        Lk.new(next(o for o in rs.outputs if o.type == "VALUE"), ins.inputs["Scale"])
        Lk.new(ins.outputs[0], join.inputs[0])

    scatter(bq["Grass_Tall_A"], 9.0, 0.9, 1.6, 21, 0.3, 0.55)
    scatter(bq["Grass_Wild_B"], 4.0, 0.8, 1.3, 22, 0.35, 0.6)
    scatter(bq["Grass_Wild_C"], 4.0, 0.8, 1.3, 23, 0.35, 0.6)
    scatter(bq["Grass_Karl-foerster_B"], 0.9, 0.6, 1.0, 24, 0.45, 0.62, 0.3)
    scatter(bq["Grass_Basic_A"], 2.5, 0.8, 1.3, 25, 0.4, 0.62)
    for k, s in enumerate(shrubs):
        scatter(s, 0.12, 2.5, 4.5, 30 + k, 0.45, 0.62, 0.08, 0.05)
    for k, name in enumerate(("Rock_Granite-Photoscan_F", "Rock_Granite-Photoscan_E")):
        scatter(bq[name], 0.006, 0.3, 0.8, 40 + k, 0.55, 0.62, 0.05, 0.4)
    Lk.new(join.outputs[0], go.inputs[0])
    md = sand.modifiers.new("Duna", "NODES")
    md.node_group = ng


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
    l.new(env.outputs["Color"], bg.inputs[0])
    w.mist_settings.start = 80
    w.mist_settings.depth = 1600
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

    lt, pw, amt, mul = mnode("LESS_THAN", 0.999), mnode("POWER", 0.9), mnode("MULTIPLY", 0.4), mnode("MULTIPLY", 1.0)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0.72, 0.8, 0.88, 1)
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
    "izq": ((-30.0, -26.0, 17.0), (6.6, 3.0, 0.5), 30),
    "der": ((42.0, -26.0, 17.0), (5.6, 3.0, 0.5), 30),
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
    bq, shrubs = load_assets(M)
    build_vegetation(sand, bq, shrubs)
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
