"""Escena 3D de Casa Boldo en un lago del sur (Blender 5.x, Cycles).

Uso:
  python casa_boldo_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  (vistas: izq / der = tomas fijas de dron sobre el agua, a cada lado del testero vidriado;
   atras / der_atras = desde el acceso y el camino, con el lago de fondo)
  python casa_boldo_3d.py -- --vista dron --tramo s1 --out frames_boldo/s1/f_ [--cuadro 80]
  (recorrido de dron por secciones, ver SECCIONES; --cuadro N renderiza sólo ese cuadro.
  El recorrido se afina después de que el usuario apruebe las fotos fijas: RECETA.md §0.)

La casa sale del modelo STL de Neorigen (assets/boldo/casa.blend, generado con
tools/extraer_boldo_stl.py): 7,49 m de ancho por 14,33 de fondo —la más angosta y alargada de las
nueve—, terraza de 3,1 m hacia -Y (el lago) bajo el testero vidriado, porch de acceso hacia +Y,
techo a dos aguas muy asimétrico con la cumbrera corriendo en el eje Y (corrida a x = 5,60: el
faldón largo sube 32° desde el alero bajo de 3,00 m y el corto baja al alero alto de 5,38 m),
piso terminado en z = 0,55, segundo piso en 3,25 y terreno en z = 0.

Paisaje: lago del sur de Chile. Lo que manda no es la espuma —como en la playa de Huingán— sino
el reflejo: el agua va casi espejo (oleaje mínimo) y la mitad de la imagen es lo que se refleja
en ella, así que la **ribera opuesta** es parte del trabajo, no fondo: cerros con bosque nativo a
unos 860 m, y la cordillera atrás. De este lado, una ribera de canto rodado, talud con pradera y
matorral, muelle de madera que entra al agua, bosque alrededor del claro y el camino de tierra
que baja desde los cerros al porch de acceso.

El enganche (ENGANCHES.md) es que todo apunta al agua: el vidrio está concentrado en un solo
testero —los dos pisos— así que la casa funciona como un visor al lago, y las tomas se plantan
sobre el agua, frente a ese testero.
Vegetación y rocas de Poly Haven (CC0, tools/get_assets_playa.sh) y pastos Botaniq de
assets/campo. HDRI lakeside de Poly Haven (tools/get_assets_hdri.sh lago).
"""
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"vista": "izq", "out": "//cuadro.png", "res": "720x1280", "samples": "32", "still": "1",
        "wb": "6150", "save": None}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(8)
ROOT = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.join(ROOT, "assets", "boldo", "casa.blend")
CAMPO = os.path.join(ROOT, "assets", "campo", "pastos_botaniq.blend")
PH = os.path.join(ROOT, "assets", "playa", "ph")    # matorral y rocas (tools/get_assets_playa.sh)
PHL = os.path.join(ROOT, "assets", "lago", "ph")    # árboles y sotobosque (tools/get_assets_lago.sh)
HDRI = os.path.join(ROOT, "assets", "hdri", "lago", "lakeside_2k.exr")   # día claro de lago, CC0
HDRI_SUN_U = 0.6001          # columna del sol en el HDRI (0-1), medida con tools/medir_sol_hdri.py
SUN_ELEV = 31.8              # elevación del sol en el HDRI
SKY_GAIN = 0.06              # brillo del cielo físico (horizonte) para empatar con el HDRI
# Azimut desde +Y hacia +X. El testero vidriado mira a -Y y el faldón largo del techo mira a -X,
# así que el sol tiene que estar en ese cuadrante para iluminar los dos: a 215° entra de refilón
# al vidrio, baña el faldón largo y tira la sombra cruzando la pradera hacia atrás y a la derecha.
SUN_AZ = 215.0
WB_TEMP = float(opts["wb"])
L, D = 7.49, 14.33           # ancho y fondo total del casco (terraza + caja + porch)
HC = Vector((L / 2, D / 2))  # centro de la casa en planta
GROUND = 0.0                 # terreno de la ribera, bajo la casa
PISO = 0.55                  # piso terminado
PISO2 = 3.25                 # segundo piso (las dos plantas repiten el esquema)
LAGO = -2.40                 # nivel del agua: la terraza queda 2,4 m sobre el lago
# El lago es una elipse con el centro mar adentro, así que la orilla cercana pasa justo frente al
# testero (y = -14) y la opuesta —la que se refleja— a 860 m (y = -874). A los costados el agua se
# cierra contra los cerros, como un lago y no como un mar abierto: así no hay línea de horizonte
# de agua, que es lo que delataría el truco.
LKX, LKY = L / 2, -444.0     # centro del lago en planta
LKA, LKB = 700.0, 430.0      # semiejes (el lago mide 1400 x 860 m)
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


# Amplitud de las ensenadas de la orilla, en unidades del radio de la elipse (0,012 son unos 5 m
# en la orilla cercana): sin esto la orilla sería un arco perfecto y se leería como una piscina.
ENS = (0.012, 23.0, 1.1, 0.007, 31.0)


def lake_d(x, y):
    """Distancia aproximada (m) a la orilla del lago, positiva tierra adentro, negativa en el
    agua. La orilla es la elipse r = 1 con ensenadas; la distancia sale de (r - orilla) dividido
    por el gradiente de r, que es lo que convierte unidades de elipse en metros."""
    u, v = (x - LKX) / LKA, (y - LKY) / LKB
    r = math.hypot(u, v)
    if r < 1e-6:
        return -LKB
    g = math.hypot(u / LKA, v / LKB) / r
    a, wx, ph, b, wy = ENS
    orilla = 1.0 + a * math.sin(x / wx + ph) + b * math.sin(y / wy)
    return (r - orilla) / g


def lake_d_nodes(N, sep):
    """Mismo lake_d(x, y) en nodos."""
    a, wx, ph, b, wy = ENS
    u = N.math("DIVIDE", N.math("SUBTRACT", sep.outputs["X"], LKX), LKA)
    v = N.math("DIVIDE", N.math("SUBTRACT", sep.outputs["Y"], LKY), LKB)
    r = N.math("SQRT", N.math("ADD", N.math("MULTIPLY", u, u), N.math("MULTIPLY", v, v)))
    gu = N.math("DIVIDE", u, LKA)
    gv = N.math("DIVIDE", v, LKB)
    g = N.math("DIVIDE", N.math("SQRT", N.math("ADD", N.math("MULTIPLY", gu, gu),
                                               N.math("MULTIPLY", gv, gv))), r)
    sx = N.math("MULTIPLY", N.math("SINE", N.math("ADD", N.math("DIVIDE", sep.outputs["X"], wx), ph)), a)
    sy = N.math("MULTIPLY", N.math("SINE", N.math("DIVIDE", sep.outputs["Y"], wy)), b)
    orilla = N.math("ADD", N.math("ADD", 1.0, sx), sy)
    return N.math("DIVIDE", N.math("SUBTRACT", r, orilla), g)


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


def madera_mat(name, eje="X", paso=0.14, estira=(9.0, 9.0, 0.22), claro=(0.46, 0.31, 0.17),
               medio=(0.3, 0.19, 0.1), oscuro=(0.17, 0.1, 0.052), rough=0.55, bump=0.5):
    """Madera con tablas de tono propio, veta a lo largo y junta marcada.

    `boards_mat` pinta bandas parejas y una veta global, y a pleno sol eso se lee como un plano
    blanco albayalde en vez de madera —fue lo que pidió corregir la revisión—. Acá cada tabla saca
    su tono de un ruido blanco sobre el **número de tabla** (floor(coord / paso)): es lo mismo que
    hace Object Info > Random en el muelle, pero sirviendo para una malla entera, donde no hay un
    objeto por tabla. `estira` alarga la veta en el sentido de la tabla."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    u = N.math("DIVIDE", sep.outputs[eje], paso)
    idx = N.math("FLOOR", u)
    wn = n.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "1D"
    l.new(idx, wn.inputs["W"])
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = estira
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    veta = N.noise(mp.outputs["Vector"], 4.0, 8, 0.6, 1.4)
    fina = N.noise(mp.outputs["Vector"], 20.0, 4, 0.5, 0.7)
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].color, e[1].color = (*oscuro, 1), (*claro, 1)
    e.new(0.5).color = (*medio, 1)
    l.new(N.math("ADD", N.math("MULTIPLY", wn.outputs["Value"], 0.62),
                 N.math("MULTIPLY", veta, 0.38)), ramp.inputs["Fac"])
    col = N.mix(N.math("MULTIPLY", fina, 0.3), ramp.outputs["Color"], oscuro)
    # junta entre tablas: una línea oscura y un rebaje
    f = N.math("FRACT", u)
    junta = N.math("MAXIMUM", N.math("SUBTRACT", 1.0, N.smooth(f, 0.0, 0.055)),
                   N.smooth(f, 0.945, 1.0))
    col = N.mix(N.math("MULTIPLY", junta, 0.75), col, (0.055, 0.035, 0.02))
    l.new(col, b.inputs["Base Color"])
    l.new(N.math("ADD", rough, N.math("MULTIPLY", fina, 0.2)), b.inputs["Roughness"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.01
    l.new(N.math("ADD", N.math("MULTIPLY", N.math("SUBTRACT", 1.0, junta), 0.25),
                 N.math("MULTIPLY", veta, 0.45)), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
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


def chapa_nervada(name, pitch=0.21, rib=0.03, flank=0.016):
    """Chapa negra mate con nervios, y el eje de los nervios **elegido por la normal de la cara**,
    no fijado a mano: en los muros corren en vertical (tapajuntas, como en la foto de referencia) y
    en el techo por la línea de máxima pendiente. Con el eje fijo de Huingán no había forma de
    acertarle a las dos cosas: los muros largos salían lisos (su coordenada no cambia a lo ancho de
    la cara) y el techo salía rayado a lo ancho, que fue lo que marcó la revisión.

    La regla es una sola: si la cara mira más en X que en Y —muros largos y faldones del techo,
    porque la cumbrera corre en Y— las rayas van sobre la coordenada Y; si mira más en Y
    —los testeros— van sobre la X. En ambos casos la raya queda vertical o bajando el faldón.
    Mate y con poco metal: el brillo especular de la chapa de Huingán era lo que leía como blanco
    sobre el techo."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.016, 0.016, 0.018, 1)
    b.inputs["Metallic"].default_value = 0.2
    tc = n.new("ShaderNodeTexCoord")
    pos = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], pos.inputs[0])
    geo = n.new("ShaderNodeNewGeometry")
    nrm = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["Normal"], nrm.inputs[0])
    usa_y = N.math("GREATER_THAN", N.math("ABSOLUTE", nrm.outputs["X"]),
                   N.math("ABSOLUTE", nrm.outputs["Y"]))
    coord = N.math("ADD", pos.outputs["X"],
                   N.math("MULTIPLY", usa_y, N.math("SUBTRACT", pos.outputs["Y"], pos.outputs["X"])))
    u = N.math("FRACT", N.math("DIVIDE", coord, pitch))
    d = N.math("MULTIPLY", N.math("ABSOLUTE", N.math("SUBTRACT", u, 0.5)), pitch)
    d = N.math("MULTIPLY", N.math("SUBTRACT", d, pitch / 2), -1.0)
    top = N.math("SUBTRACT", 1.0, N.math("DIVIDE", N.math("MAXIMUM", N.math("SUBTRACT", d, rib / 2), 0.0), flank))
    top = N.math("MAXIMUM", top, 0.0)
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.9
    bmp.inputs["Distance"].default_value = 0.018
    l.new(top, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    polvo = N.noise(tc.outputs["Object"], 1.5)
    l.new(N.math("ADD", 0.52, N.math("MULTIPLY", polvo, 0.12)), b.inputs["Roughness"])
    return m


def glass_mat(entintado=False):
    m, n, l = new_mat("VidrioTecho" if entintado else "Vidrio")
    n.remove(n["Principled BSDF"])
    out = n["Material Output"]
    fr = n.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.45
    att = n.new("ShaderNodeMath")
    att.operation = "MULTIPLY"
    att.inputs[1].default_value = 0.5
    l.new(fr.outputs["Fac"], att.inputs[0])
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.2, 0.23, 0.24, 1) if entintado else (0.86, 0.9, 0.9, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.12 if entintado else 0.02
    if entintado:
        gl.inputs["Color"].default_value = (0.3, 0.32, 0.34, 1)
        att.inputs[1].default_value = 0.32
    mix = n.new("ShaderNodeMixShader")
    l.new(att.outputs[0], mix.inputs["Fac"])
    l.new(tr.outputs[0], mix.inputs[1])
    l.new(gl.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])
    return m


def lecho_mat():
    """Ribera y lecho del lago: canto rodado claro en la playita, piedra mojada y más oscura
    donde el agua lame, el fondo que se va a verde oscuro con la profundidad, y tierra de pradera
    en el talud que sube a la casa. El color del agua lo da este material (el agua es
    transparente), así que la profundidad se tiñe acá y no en el shader del lago."""
    m, n, l = new_mat("Ribera")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    d = lake_d_nodes(N, sep)
    big = N.noise(tc.outputs["Object"], 0.09, 3)
    mid = N.noise(tc.outputs["Object"], 0.8, 6)
    # canto rodado: gris pardo con manchones y piedras sueltas
    seco = N.mix(N.math("MULTIPLY_ADD", big, 1.6, -0.3), (0.085, 0.082, 0.07), (0.15, 0.14, 0.115))
    seco = N.mix(N.math("MULTIPLY", mid, 0.45), seco, (0.06, 0.058, 0.05))
    mojado = (0.05, 0.05, 0.045)
    moj_f = N.math("SUBTRACT", 1.0, N.smooth(d, 0.3, 2.0))
    col = N.mix(moj_f, seco, mojado)
    # talud y pradera: tierra con pasto, que arriba domina
    prado = N.mix(N.smooth(N.noise(tc.outputs["Object"], 1.6, 5), 0.35, 0.6), (0.105, 0.125, 0.055),
                  (0.05, 0.075, 0.03))
    col = N.mix(N.smooth(d, 0.8, 3.0), col, prado)
    # bajo el agua: el fondo se apaga a verde oscuro con la profundidad (es el color del lago)
    prof = N.math("MULTIPLY", d, -1.0)
    col = N.mix(N.smooth(prof, 0.0, 2.0), col, (0.03, 0.055, 0.05))
    col = N.mix(N.smooth(prof, 1.5, 14.0), col, (0.005, 0.016, 0.016))
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "veg"
    suelo = N.mix(N.smooth(N.noise(tc.outputs["Object"], 2.0, 5), 0.35, 0.6), (0.12, 0.13, 0.065),
                  (0.055, 0.075, 0.035))
    col = N.mix(N.math("MULTIPLY", at.outputs["Fac"], 0.8), col, suelo)
    # huella pisada del muelle al porch: tierra a la vista
    cm = n.new("ShaderNodeAttribute")
    cm.attribute_name = "camino"
    pisado = N.smooth(N.noise(tc.outputs["Object"], 5.0, 3), 0.5, 0.7)
    col = N.mix(N.math("MULTIPLY", cm.outputs["Fac"], N.math("ADD", 0.8, N.math("MULTIPLY", pisado, 0.2))),
                col, (0.155, 0.125, 0.088))
    l.new(col, b.inputs["Base Color"])
    # la piedra mojada brilla: es lo que dibuja la línea de agua
    l.new(N.math("ADD", 0.92, N.math("MULTIPLY", moj_f, -0.68)), b.inputs["Roughness"])
    # relieve: cantos rodados en la orilla (gruesos) y grano fino en todo el resto
    cantos = N.noise(tc.outputs["Object"], 7.0, 6, 0.7)
    grano = N.noise(tc.outputs["Object"], 55.0, 2)
    h = N.math("ADD", N.math("MULTIPLY", cantos, N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(d, 2.0, 9.0)), 0.8)),
               N.math("MULTIPLY", grano, 0.25))
    bmp = n.new("ShaderNodeBump")
    cam_d = n.new("ShaderNodeCameraData")
    cerca = N.math("SUBTRACT", 1.0, N.smooth(cam_d.outputs["View Z Depth"], 50.0, 200.0))
    l.new(N.math("MULTIPLY", cerca, 0.4), bmp.inputs["Strength"])
    bmp.inputs["Distance"].default_value = 0.05
    l.new(h, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def lago_mat():
    """Agua de lago: casi espejo. Es el cambio de fondo respecto del mar de Huingán —allá mandaba
    la espuma, acá manda el reflejo—, así que el oleaje se baja a una ondulación larga y rizos
    finos, y de espuma queda sólo la línea mojada donde el agua toca la piedra."""
    m, n, l = new_mat("Lago")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    out = n["Material Output"]
    tc = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Position"], sep.inputs[0])
    d = N.math("MULTIPLY", lake_d_nodes(N, sep), -1.0)   # distancia lago adentro (m)
    # transparente (deja ver el lecho y lo deja iluminarse) + reflejo por Fresnel
    n.remove(b)
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.78, 0.88, 0.84, 1)   # el agua dulce tira a verde
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.035                # casi espejo, pero sin sal y pimienta
    # La banda de sal y pimienta que salía a media distancia no era ni el agua ni el lecho: es el
    # bosque de la ribera de enfrente **reflejado**, que a esa distancia entra comprimido y cada
    # copa cae en un píxel. Apagar el relieve con la distancia no basta —y por sí solo empeora,
    # porque quita el detalle sin devolver nada—: hay que cambiarlo por rugosidad, que es lo mismo
    # que hacen las normales de sub-píxel en la realidad. De 0,035 en primer plano a 0,11 lejos.
    fr = n.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.333
    cam_d = n.new("ShaderNodeCameraData")
    wat = n.new("ShaderNodeMixShader")
    geo = n.new("ShaderNodeNewGeometry")
    lpw = n.new("ShaderNodeLightPath")
    fac = N.math("MULTIPLY", fr.outputs["Fac"], N.math("SUBTRACT", 1.0, geo.outputs["Backfacing"]))
    fac = N.math("MULTIPLY", fac, N.math("SUBTRACT", 1.0, lpw.outputs["Is Shadow Ray"]))
    l.new(fac, wat.inputs["Fac"])
    l.new(tr.outputs[0], wat.inputs[1])
    l.new(gl.outputs[0], wat.inputs[2])
    # ondulación en tres escalas, toda ella mínima: la larga estira el reflejo de los cerros,
    # la media lo quiebra en bandas y los rizos dan el centelleo del sol
    def bump_layer(scale, stretch, strength, dist, normal=None, detail=6, lejos=None):
        mp = n.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = stretch
        l.new(tc.outputs["Position"], mp.inputs["Vector"])
        bp = n.new("ShaderNodeBump")
        if lejos is None:
            bp.inputs["Strength"].default_value = strength
        else:   # se apaga con la distancia a cámara (lejos, (desde, hasta))
            f = N.math("SUBTRACT", 1.0, N.smooth(cam_d.outputs["View Z Depth"], *lejos))
            l.new(N.math("MULTIPLY", f, strength), bp.inputs["Strength"])
        bp.inputs["Distance"].default_value = dist
        l.new(N.noise(mp.outputs["Vector"], scale, detail, 0.55, 0.2), bp.inputs["Height"])
        if normal is not None:
            l.new(normal, bp.inputs["Normal"])
        return bp.outputs["Normal"]

    rug = n.new("ShaderNodeMapRange")
    rug.interpolation_type = "SMOOTHSTEP"
    rug.inputs[1].default_value, rug.inputs[2].default_value = 60.0, 420.0
    rug.inputs[3].default_value, rug.inputs[4].default_value = 0.035, 0.11
    l.new(cam_d.outputs["View Z Depth"], rug.inputs[0])
    l.new(rug.outputs[0], gl.inputs["Roughness"])
    nrm = bump_layer(0.035, (0.35, 1.0, 1.0), 0.08, 0.45)                          # ondulación larga
    nrm = bump_layer(0.45, (0.6, 1.0, 1.0), 0.09, 0.05, nrm, lejos=(40.0, 190.0))   # bandas de brisa
    nrm = bump_layer(4.5, (1.0, 1.0, 1.0), 0.08, 0.008, nrm, 4, lejos=(20.0, 90.0))   # rizos
    l.new(nrm, gl.inputs["Normal"])
    # lo único que queda de espuma: la línea mojada donde el agua lame la piedra
    zrel = N.math("SUBTRACT", sep.outputs["Z"], LAGO)
    prof = N.math("ADD", zrel, N.math("MULTIPLY", d, FORE))
    grano = N.noise(tc.outputs["Position"], 7.0, 6, 0.7)
    orla = N.math("SUBTRACT", 1.0, N.smooth(prof, 0.005, 0.05))
    orla = N.math("MULTIPLY", orla, N.smooth(grano, 0.42, 0.62))
    # Mar adentro el agua es opaca. Además de ser lo que se ve en un lago de verdad —el fondo se
    # pierde a los pocos metros—, arregla la banda de sal y pimienta que salía a media distancia:
    # el Mix Shader entre "transparente" (fondo casi negro) y "reflejo" (cielo y cerros claros) se
    # resuelve tirando un rayo por una rama o por la otra, y con esa diferencia de brillo la
    # varianza es tal que ni 32 muestras ni el denoiser la tapan (a 128 recién se limpiaba). Donde
    # el agua pasa de 5 m de hondo se usa un solo Principled oscuro: una sola rama, sin varianza.
    hondo = n.new("ShaderNodeBsdfPrincipled")
    hondo.inputs["Base Color"].default_value = (0.006, 0.019, 0.018, 1)
    hondo.inputs["IOR"].default_value = 1.333
    l.new(rug.outputs[0], hondo.inputs["Roughness"])
    l.new(nrm, hondo.inputs["Normal"])
    agua = n.new("ShaderNodeMixShader")
    l.new(N.smooth(prof, 1.5, 5.0), agua.inputs["Fac"])
    l.new(wat.outputs[0], agua.inputs[1])
    l.new(hondo.outputs[0], agua.inputs[2])
    fb = n.new("ShaderNodeBsdfPrincipled")
    fb.inputs["Base Color"].default_value = (0.8, 0.83, 0.82, 1)
    fb.inputs["Roughness"].default_value = 0.75
    mx = n.new("ShaderNodeMixShader")
    l.new(N.math("MULTIPLY", orla, 0.3), mx.inputs["Fac"])
    l.new(agua.outputs[0], mx.inputs[1])
    l.new(fb.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs["Surface"])
    return m


def hills_mat():
    """Cerros y ribera opuesta en un solo material: bosque nativo oscuro y continuo, que es lo
    que se refleja en el agua, con quebradas más negras, claros de pasto y, bien arriba, la roca
    y la nieve de la cordillera. Los tonos son los mismos de la vegetación cercana, para que el
    paisaje no se parta en dos."""
    m, n, l = new_mat("Cerros")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    f = N.noise(tc.outputs["Object"], 0.012, 6, 0.6)
    g = N.noise(tc.outputs["Object"], 0.15, 4)
    h = N.noise(tc.outputs["Object"], 0.05, 5, 0.6)
    claro = N.mix(N.smooth(h, 0.35, 0.55), (0.105, 0.115, 0.055), (0.05, 0.075, 0.03))
    bosque = N.mix(N.smooth(f, 0.3, 0.5), (0.035, 0.055, 0.028), (0.014, 0.027, 0.014))
    col = N.mix(N.smooth(f, 0.3, 0.46), claro, bosque)
    # la cordillera: roca desnuda sobre los 260 m y nieve en las cumbres
    roca = N.mix(N.math("MULTIPLY", g, 0.6), (0.17, 0.16, 0.16), (0.09, 0.085, 0.085))
    col = N.mix(N.math("MULTIPLY", N.smooth(sep.outputs["Z"], 260.0, 420.0),
                       N.smooth(N.noise(tc.outputs["Object"], 0.03, 4), 0.3, 0.55)), col, roca)
    col = N.mix(N.math("MULTIPLY", N.smooth(sep.outputs["Z"], 540.0, 700.0),
                       N.smooth(N.noise(tc.outputs["Object"], 0.08, 4), 0.4, 0.62)), col, (0.62, 0.65, 0.7))
    col = N.mix(N.math("MULTIPLY", g, 0.3), col, (0.02, 0.03, 0.018))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.8
    bmp.inputs["Distance"].default_value = 2.0
    l.new(g, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def scrub_mat():
    """Ribera lejana cubierta de matorral y pradera (vista a distancia, sin instancias)."""
    m, n, l = new_mat("Matorral")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    f = N.noise(tc.outputs["Object"], 0.08, 6, 0.65)
    g = N.noise(tc.outputs["Object"], 0.9, 4)
    col = N.mix(N.smooth(f, 0.28, 0.45), (0.14, 0.15, 0.07), (0.035, 0.055, 0.025))
    col = N.mix(N.math("MULTIPLY", g, 0.5), col, (0.025, 0.04, 0.018))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.6
    l.new(g, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def meadow_grass_mat():
    """Pasto de ribera: verde húmedo del sur, con matas más claras y algunas pajizas (cada mata
    con su tono). No es el dorado de la duna de Huingán: junto a un lago el pasto está verde."""
    m, n, l = new_mat("PastoRibera")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    info = n.new("ShaderNodeObjectInfo")
    tc = n.new("ShaderNodeTexCoord")
    v = N.math("ADD", N.math("MULTIPLY", info.outputs["Random"], 0.7), N.math("MULTIPLY", N.noise(tc.outputs["Object"], 3), 0.3))
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].color, e[1].color = (0.055, 0.1, 0.035, 1), (0.4, 0.37, 0.19, 1)
    e.new(0.55).color = (0.13, 0.17, 0.065, 1)
    l.new(v, ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    b.inputs["Subsurface Weight"].default_value = 0.12
    l.new(ramp.outputs["Color"], b.inputs["Subsurface Radius"])
    return m


def muelle_mat():
    """Madera del muelle y la pasarela: tablas de pino a la intemperie, no entablado gris.

    Cada tabla es un objeto aparte, así que el tono sale de Object Info > Random: una tabla más
    clara, la de al lado más oscura. Eso es lo que hace que un entablado se lea como madera —en un
    deck real no hay dos tablas del mismo color— y con `boards_mat` no se podía, porque dibuja
    bandas parejas sobre toda la superficie. Las juntas, además, ya están en la geometría (cada
    tabla es una caja con su luz), así que acá no se dibujan: sólo veta, que corre a lo largo de
    la tabla (eje X), y el relieve sale de esa misma veta."""
    m, n, l = new_mat("MuelleMadera")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    info = n.new("ShaderNodeObjectInfo")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.22, 9.0, 9.0)   # ruido estirado = veta
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    veta = N.noise(mp.outputs["Vector"], 5.0, 8, 0.6, 1.6)
    fina = N.noise(mp.outputs["Vector"], 24.0, 4, 0.5, 0.8)
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].color, e[1].color = (0.155, 0.09, 0.048, 1), (0.44, 0.295, 0.165, 1)
    e.new(0.5).color = (0.27, 0.175, 0.095, 1)
    l.new(N.math("ADD", N.math("MULTIPLY", info.outputs["Random"], 0.68),
                 N.math("MULTIPLY", veta, 0.32)), ramp.inputs["Fac"])
    col = N.mix(N.math("MULTIPLY", fina, 0.38), ramp.outputs["Color"], (0.175, 0.115, 0.065))
    # algo de plata de intemperie en los cantos, sin apagar el tono de la madera
    col = N.mix(N.math("MULTIPLY", N.smooth(veta, 0.62, 0.78), 0.3), col, (0.3, 0.27, 0.235))
    l.new(col, b.inputs["Base Color"])
    l.new(N.math("ADD", 0.64, N.math("MULTIPLY", fina, 0.2)), b.inputs["Roughness"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.4
    bmp.inputs["Distance"].default_value = 0.005
    l.new(N.math("ADD", N.math("MULTIPLY", veta, 0.7), N.math("MULTIPLY", fina, 0.3)), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def laja_mat():
    """Laja de piedra para los peldaños de la bajada: gris parda, con vetas y el canto gastado."""
    m, n, l = new_mat("Laja")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    grande = N.noise(tc.outputs["Object"], 1.6, 5, 0.6)
    fino = N.noise(tc.outputs["Object"], 14.0, 5, 0.55)
    col = N.mix(N.math("MULTIPLY_ADD", grande, 1.5, -0.25), (0.105, 0.1, 0.09), (0.26, 0.245, 0.225))
    col = N.mix(N.math("MULTIPLY", fino, 0.45), col, (0.075, 0.072, 0.065))
    l.new(col, b.inputs["Base Color"])
    l.new(N.math("ADD", 0.72, N.math("MULTIPLY", fino, 0.2)), b.inputs["Roughness"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.45
    bmp.inputs["Distance"].default_value = 0.012
    l.new(N.math("ADD", N.math("MULTIPLY", grande, 0.6), N.math("MULTIPLY", fino, 0.4)), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
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
        "chapa": chapa_nervada("ChapaNegra"),
        # Los marcos de ventana y el canto del techo sobre el alero: negros, mate y lisos.
        "marcoNegro": principled("MarcoNegro", (0.014, 0.014, 0.016), 0.45),
        # Tabla vertical de la fachada de acceso. Volvió a ser madera: en la primera pasada se
        # pintó negra junto con la perfilería porque en el STL comparten material, y la revisión
        # aclaró que sólo van negros los ventanales. Ahora el extractor las separa por tamaño.
        "fachada": madera_mat("MaderaFachada", "X", 0.155, (9.0, 9.0, 0.22), (0.47, 0.33, 0.185),
                              (0.32, 0.21, 0.115), (0.185, 0.115, 0.06), 0.6, 0.45),
        "cielo": madera_mat("MaderaCielo", "Y", 0.16, (0.25, 9.0, 9.0)),
        "deck": madera_mat("Deck", "Y", 0.145, (0.25, 9.0, 9.0), (0.4, 0.26, 0.14),
                           (0.26, 0.16, 0.085), (0.145, 0.085, 0.045), 0.62, 0.6),
        "piso": madera_mat("PisoInterior", "Y", 0.17, (0.25, 9.0, 9.0), (0.47, 0.32, 0.18),
                           (0.33, 0.21, 0.115), (0.2, 0.12, 0.062), 0.4, 0.3),
        "muroint": madera_mat("MuroInterior", "X", 0.15, (9.0, 9.0, 0.25), (0.5, 0.35, 0.2),
                              (0.35, 0.23, 0.125), (0.21, 0.13, 0.068), 0.55, 0.35),
        "vidrio": glass_mat(),
        # Los tragaluces miran al cielo, así que con el vidrio normal devuelven el cielo entero y
        # en el render son dos rectángulos blancos sobre el techo —justo lo que pidió sacar la
        # revisión—. Van entintados y algo más rugosos, como un cristal de techo de verdad.
        "vidrioTecho": glass_mat(entintado=True),
        "hormigon": concrete_mat(),
        "ribera": lecho_mat(),
        "lago": lago_mat(),
        "cerros": hills_mat(),
        "pastoRibera": meadow_grass_mat(),
        "matorral": scrub_mat(),
        "roca": principled("Roca", (0.16, 0.16, 0.15), 0.8),
        "muelle": muelle_mat(),
        "laja": laja_mat(),
    }
    return M


# ---------------------------------------------------------------- casa
def load_house(M):
    """Casa del STL con los materiales de la escena (por nombre de material del .blend)."""
    with bpy.data.libraries.load(CASA) as (a, b):
        b.objects = a.objects
    # "Bo_MaderaFachada" junta dos cosas en el STL: los paños grandes de tabla de la fachada de
    # acceso y los miembros finos del ventanal y del canto del techo. El extractor los separa por
    # tamaño de cara, así que acá la madera va con madera y la perfilería con el negro mate.
    swap = {"Bo_ChapaNegra": M["chapa"], "Bo_MaderaFachada": M["fachada"], "Bo_MaderaCielo": M["cielo"],
            "Bo_Deck": M["deck"], "Bo_PisoInterior": M["piso"], "Bo_MuroInterior": M["muroint"],
            "Bo_Vidrio": M["vidrio"], "Bo_Pilote": M["hormigon"], "Bo_MarcoNegro": M["marcoNegro"],
            "Bo_VidrioTecho": M["vidrioTecho"]}
    coll = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(coll)
    for o in b.objects:
        coll.objects.link(o)
        for sl in o.material_slots:
            if sl.material and sl.material.name in swap:
                sl.material = swap[sl.material.name]
    # luces interiores tibias (en el día apenas se notan, pero dan vida al interior)
    # Dos pisos con la misma planta: estar y comedor contra el testero, dormitorios al fondo.
    # Las del segundo piso van bajas a propósito: ahí el cielo **es** el faldón, y puestas a 1,8 m
    # quedaban metidas entre las dos pieles del techo, de modo que iluminaban la chapa por fuera y
    # en el render aparecían dos rectángulos blancos sobre el techo (se encontró tirando un rayo
    # desde la cámara: los píxeles daban en la chapa negra, no en otro material).
    for x, y, z, p, t in ((3.6, 4.6, PISO + 1.9, 150, 1.0), (6.0, 5.6, PISO + 1.9, 60, 1.0),
                          (3.4, 10.4, PISO + 1.8, 55, 1.0), (2.9, 4.8, PISO2 + 0.95, 70, 0.7),
                          (2.8, 10.6, PISO2 + 0.95, 40, 0.7)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, t
        lt.data.color = (1.0, 0.72, 0.45)
    return coll


def orilla_y(x, y0=-30.0, y1=10.0):
    """Donde cruza la orilla (lake_d = 0) sobre la vertical x, por bisección."""
    for _ in range(60):
        ym = (y0 + y1) / 2
        if lake_d(x, ym) < 0:
            y0 = ym
        else:
            y1 = ym
    return (y0 + y1) / 2


def build_muelle(M, ph=None):
    """Bajada al agua y muelle. En un lago el muelle no es decorado: es lo que da escala al espejo
    y lo único vertical que se refleja cerca de la cámara, y es también lo que explica la casa
    (todo apunta al agua).

    El talud **no** lleva pasarela de tablas: la revisión pidió una bajada más natural. La primera
    versión fueron piedras sueltas salteadas y no se leía —parecía escombro repartido en el pasto—,
    así que ahora es una **escalera de lajas**: peldaños alineados sobre el eje de la huella,
    apenas girados uno respecto de otro y hundidos en el terreno, que es como se ve un sendero
    hecho a mano. La huella de tierra sigue abriéndola la vegetación (atributo 'camino'). El
    entablado arranca recién sobre el agua, que es donde hace falta."""
    coll = bpy.data.collections.new("Muelle")
    bpy.context.scene.collection.children.link(coll)
    y_sh = orilla_y(path_x(-12.0))
    # 1) escalera de lajas sobre la huella, desde la escalera de la terraza hasta el agua
    rnd = random.Random(17)
    y = -1.3
    i = 0
    while y > y_sh + 0.35:
        xc = path_x(y) + rnd.uniform(-0.07, 0.07)
        z = terrain_h(xc, y)
        ancho = rnd.uniform(0.56, 0.72)         # media laja a cada lado del eje
        largo = rnd.uniform(0.28, 0.34)
        pel = box(f"Laja{i}", -ancho, ancho, -largo, largo, -0.14, 0.035, M["laja"], coll)
        pel.location = (xc, y, z)
        pel.rotation_euler = (rnd.uniform(-0.035, 0.035), rnd.uniform(-0.05, 0.05),
                              rnd.uniform(-0.09, 0.09))
        y -= rnd.uniform(0.62, 0.72)
        i += 1
    # 2) muelle: plataforma horizontal 65 cm sobre el agua, que entra 9 m en el lago
    xc = path_x(y_sh)
    zt = LAGO + 0.65
    y_pt = y_sh - 9.0
    k = 0
    y = y_sh + 0.8
    while y > y_pt:
        box(f"TablaM{k}", xc - 0.9, xc + 0.9, y - 0.15, y, zt, zt + 0.045, M["muelle"], coll)
        y -= 0.17
        k += 1
    for yp in [y_sh + 0.5 - 1.9 * t for t in range(6)]:
        if yp < y_pt + 0.2:
            break
        for xp in (xc - 0.82, xc + 0.72):
            zb = min(terrain_base(xp, yp), LAGO) - 0.4
            box(f"PilotM{int(-yp * 10)}_{xp > xc}", xp, xp + 0.11, yp - 0.11, yp, zb, zt, M["muelle"], coll)
    # barandas sólo en el tramo sobre el agua, de un lado: deja el otro libre para sentarse
    for t in range(5):
        yp = y_sh - 0.6 - 2.0 * t
        if yp < y_pt + 0.3:
            break
        box(f"BarandaP{t}", xc - 0.88, xc - 0.81, yp - 0.09, yp, zt, zt + 1.0, M["muelle"], coll)
    box("BarandaL", xc - 0.88, xc - 0.81, y_pt, y_sh - 0.5, zt + 0.93, zt + 1.0, M["muelle"], coll)
    return coll


# Cerco de campo: postes y tres corridas de palo, a lo largo del camino de acceso, con la tranquera
# atravesada donde el camino entra al claro. Lo pidió la revisión para ambientar el campo, y de
# paso explica el predio: sin cerco, la casa parece puesta en medio de la nada.
def build_cercos(M):
    """Cerco de campo: una sola corrida **a lo largo**, paralela a la orilla y casi donde se acaba
    el pasto —así lo pidió la revisión—, con la tranquera de dos hojas donde el camino la cruza.

    La primera versión iba por los dos lados del camino y cruzaba el claro en tramos cortos: se
    leía como un corral en medio del prado en vez de un deslinde."""
    coll = bpy.data.collections.new("Cercos")
    bpy.context.scene.collection.children.link(coll)
    rnd = random.Random(23)
    mad = M["muelle"]
    Y0, PASO = 31.0, 4.4            # línea del cerco y separación de postes
    HUECO = (3.5, 12.5)             # por donde pasa el camino: ahí va la tranquera

    def linea(x):
        return Y0 + 1.8 * math.sin(x / 13.0)

    def poste(x, y, alto=1.3, grosor=0.085):
        z = terrain_h(x, y)
        o = box(f"Poste_{x:.1f}", -grosor, grosor, -grosor, grosor, -0.45, alto, mad, coll)
        o.location = (x, y, z)
        o.rotation_euler = (rnd.uniform(-0.025, 0.025), rnd.uniform(-0.03, 0.03), rnd.uniform(0, 0.35))
        return z

    def palo(x0, y0, z0, x1, y1, z1, grosor=0.045):
        """Un palo entre dos postes: caja construida en el origen y después girada en su sitio."""
        largo = math.hypot(x1 - x0, y1 - y0)
        o = box(f"Palo_{x0:.1f}_{z0:.2f}", -largo / 2, largo / 2, -grosor, grosor, -grosor, grosor, mad, coll)
        o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        o.rotation_euler = (0, math.atan2(z1 - z0, largo), math.atan2(y1 - y0, x1 - x0))

    prev = None
    x = -58.0
    while x < 68.0:
        y = linea(x)
        if HUECO[0] < x < HUECO[1]:          # el claro de la tranquera
            prev = None
            x += PASO
            continue
        z = poste(x, y)
        if prev is not None:
            for h in (0.44, 0.82, 1.2):
                palo(prev[0], prev[1], prev[2] + h, x, y, z + h)
        prev = (x, y, z)
        x += PASO

    # la tranquera: dos hojas de tres palos con cruz, abiertas contra sus postes
    for lado, xp in ((-1, HUECO[0]), (1, HUECO[1])):
        yb, zb = linea(xp), terrain_h(xp, linea(xp))
        pt = box(f"PosteTranquera{lado}", -0.11, 0.11, -0.11, 0.11, -0.5, 1.5, mad, coll)
        pt.location = (xp, yb, zb)
        hoja = bpy.data.collections.new(f"Hoja{lado}")
        coll.children.link(hoja)
        for h in (0.44, 0.82, 1.2):
            box(f"HojaPalo{lado}_{h}", 0.0, 2.6, -0.045, 0.045, h - 0.045, h + 0.045, mad, hoja)
        cruz = box(f"HojaCruz{lado}", -1.4, 1.4, -0.04, 0.04, -0.04, 0.04, mad, hoja)
        cruz.location = (1.3, 0.0, 0.82)
        cruz.rotation_euler = (0, math.radians(-16.0), 0)
        for o in list(hoja.objects):
            o.location = (o.location.x + xp, o.location.y + yb, o.location.z + zb)
            o.rotation_euler.rotate_axis("Z", math.radians(-104.0 * lado))   # abiertas hacia el claro
    return coll


def house_dist(x, y):
    """Distancia (m) al rectángulo de la casa (con un margen de 0,5 m)."""
    dx = max(-0.5 - x, 0, x - (L + 0.5))
    dy = max(-1.3 - y, 0, y - (D + 1.3))
    return math.hypot(dx, dy)


FORE = 0.24      # pendiente del lecho junto a la orilla (bajo el agua)
RIBERA = 1.8     # ancho de la playita de canto rodado, apenas sobre el agua (m)
TALUD = 8.0      # ancho del talud que sube del agua a la terraza de la casa
TREE_LINE = 430.0   # sobre esta altura el bosque deja paso a la roca de la cordillera


def terrain_base(x, y):
    """Perfil sin ondulaciones: lecho del lago < playita de canto rodado < talud < terraza."""
    d = lake_d(x, y)
    if d < 0:
        return LAGO + max(d * FORE, -16.0)
    if d < RIBERA:
        return LAGO + d * FORE                     # canto rodado: sube apenas
    t = min(1.0, (d - RIBERA) / TALUD)
    t = t * t * (3 - 2 * t)
    top = LAGO + RIBERA * FORE
    return top + t * (GROUND - top)


def path_x(y):
    """Eje de la pasarela que baja de la terraza al muelle, apenas curvada."""
    return 1.9 + 0.7 * math.sin(y / 11.0)


def path_dist(x, y):
    """Distancia (m) al eje de la pasarela; lejos en la terraza, detrás de la escalera."""
    if y > -0.6:
        return math.hypot(x - path_x(-0.6), y + 0.6)
    return abs(x - path_x(y))


def terrain_h(x, y):
    h = terrain_base(x, y)
    d = lake_d(x, y)
    pd = path_dist(x, y)
    # ondulación de pradera en la terraza y el talud; se aplana junto a la casa y los senderos
    amp = min(1.0, max(0.0, (d - RIBERA - 2) / 10.0)) * (0.7 + min(1.0, max(0.0, (d - 50) / 60.0)) * 1.6)
    flat = min(1.0, max(0.0, (house_dist(x, y) - 1.0) / 8.0))
    dn = noise.noise(Vector((x / 16.0, y / 12.0, 0.3))) + 0.4 * noise.noise(Vector((x / 5.0, y / 4.0, 1.7)))
    flat = min(flat, 0.3 + 0.7 * min(1.0, max(0.0, (pd - 1.2) / 4.0)))      # la pasarela corta el talud
    if 8 < y < 140:
        flat = min(flat, 0.2 + 0.8 * min(1.0, max(0.0, (road_dist(x, y) - 2.5) / 6.0)))   # y el camino
    h += amp * flat * (0.4 + 0.7 * dn)
    if d > RIBERA:                                          # huella levemente hundida
        h -= 0.07 * max(0.0, 1.0 - pd / 1.1)
    if y < LKY:
        # ---- ribera opuesta: los cerros arrancan en el agua misma y suben rápido. Es la mitad de
        # la imagen (se refleja), así que no es un fondo plano: dos escalas de lomas y, atrás, la
        # cordillera. Sin esto el lago se leería como un mar con el horizonte vacío.
        rid = 0.5 + 0.5 * noise.noise(Vector((x / 310.0, y / 250.0, 5.3)))
        qda = 0.5 + 0.5 * noise.noise(Vector((x / 95.0, y / 80.0, 8.9)))
        r = min(1.0, max(0.0, d / 130.0))
        h += r * r * (45.0 + 150.0 * rid) * (0.65 + 0.5 * qda)
        r2 = min(1.0, max(0.0, (d - 150.0) / 900.0))
        cord = 0.5 + 0.5 * noise.noise(Vector((x / 620.0, y / 520.0, 12.4)))
        h += r2 * r2 * (220.0 + 520.0 * cord)
    else:
        # ---- de este lado: pradera, y cerros con bosque tierra adentro (detrás del camino)
        if y > 230:
            r = min(1.0, (y - 230) / 320.0)
            hn = 0.5 + 0.5 * noise.noise(Vector((x / 170.0, y / 140.0, 3.1)))
            h += r * r * (35 + 110 * hn)
        if d > 260:   # las riberas laterales también cierran el lago
            r = min(1.0, (d - 260) / 420.0)
            hn = 0.5 + 0.5 * noise.noise(Vector((x / 240.0, y / 200.0, 6.6)))
            h += r * r * (60 + 190 * hn)
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


# El lago entero cabe en una sola malla con oleaje (1760 x 1760 m, centrada en el lago): no hace
# falta el plano al horizonte que lleva el mar de Huingán, porque a los costados el agua se cierra
# contra los cerros. Resolución más baja que en el mar: el agua va casi quieta y el detalle fino
# (los rizos) lo pone el bump del shader, no la malla.
OCEAN_TILE, OCEAN_REP, OCEAN_RES = 220.0, 8, 12
OCEAN_X = LKX - OCEAN_TILE * OCEAN_REP / 2
OCEAN_Y = LKY - OCEAN_TILE * OCEAN_REP / 2


def fade_ocean_edges(o, width=120.0):
    """La ondulación se aplana hacia el borde de la malla (nodos de geometría después del Ocean),
    para que el agua llegue plana a la orilla opuesta y a las laterales."""
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


def build_lago(M, coll):
    """Superficie del lago: una malla con el modificador Ocean casi plano (ondulación larga de
    pocos centímetros, nada de espuma ni de crestas). El oleaje de mar de Huingán —olas de 1 m,
    espuma al 12 %— acá se apaga: lo que tiene que leerse es el reflejo."""
    bpy.ops.mesh.primitive_plane_add(size=2)
    o = bpy.context.object
    o.name = "LagoOleaje"
    for c in o.users_collection:
        c.objects.unlink(o)
    coll.objects.link(o)
    md = o.modifiers.new("Oleaje", "OCEAN")
    md.geometry_mode = "GENERATE"
    md.spatial_size = int(OCEAN_TILE)
    md.repeat_x = md.repeat_y = OCEAN_REP
    md.resolution = md.viewport_resolution = OCEAN_RES
    md.wave_scale = 0.028         # ondulación de pocos centímetros
    md.wind_velocity = 3.2        # brisa, no viento
    md.choppiness = 0.0           # sin crestas: una cresta ya sería ola de mar
    md.wave_alignment = 0.25
    md.wave_direction = math.radians(90.0)
    md.damping = 0.6
    md.use_normals = True
    md.use_foam = False
    md.time = float(opts.get("t_agua", "3.0"))
    o.location = (OCEAN_X + OCEAN_TILE / 2, OCEAN_Y + OCEAN_TILE / 2, LAGO)
    o.data.materials.append(M["lago"])
    fade_ocean_edges(o)
    return o


def build_landscape(M):
    coll = bpy.data.collections.new("Paisaje")
    bpy.context.scene.collection.children.link(coll)
    near = (-150, 120, -80, 95)
    ribera = grid("Ribera", *near, 0.6, M["ribera"], coll)
    # lejos: el lago entero, la ribera opuesta, las riberas laterales y la cordillera. Tiene que
    # llegar más allá del agua por todos lados: si la malla se cortara dentro del lago, aparecería
    # una línea de horizonte de agua y el lago se leería como mar.
    inside = lambda x, y: near[0] < x < near[1] and near[2] < y < near[3]  # noqa: E731
    far = grid("Lejos", -3000, 3000, -3400, 2700, 20.0, M["ribera"], coll, skip=inside, sink=inside)
    far.data.materials.append(M["cerros"])
    for p in far.data.polygons:
        if lake_d(p.center.x, p.center.y) > RIBERA + 6:
            p.material_index = 1
    fondo = principled("FondoLago", (0.006, 0.02, 0.018), 0.9)
    mesh_obj("FondoLago", [(-4000, -4000, LAGO - 16.6), (4000, -4000, LAGO - 16.6),
                           (4000, 4000, LAGO - 16.6), (-4000, 4000, LAGO - 16.6)],
             [(0, 1, 2, 3)], fondo, coll)
    build_lago(M, coll)
    return ribera


# ---------------------------------------------------------------- vegetación
def load_ph(lib, ident, lod="LOD1", tag=None, base=None, nombres=None):
    """Variantes de un modelo de Poly Haven (una por letra), en el nivel de detalle pedido, como
    colección para instanciar al azar. Se dejan en el origen. `nombres` pide objetos exactos, que
    es lo que hace falta con los árboles: sus .blend traen además ramas, acículas y troncos
    sueltos que no son el árbol entero."""
    path = os.path.join(base or PH, ident, ident + ".blend")
    with bpy.data.libraries.load(path) as (a, b):
        if nombres is not None:
            names = [n for n in a.objects if n in set(nombres)]
        else:
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
    """Pastos Botaniq (con el material de pasto de ribera, verde) y vegetación de Poly Haven:
    matorral de hoja ancha, arbustos, flores silvestres y rocas. Se dejan afuera las suculentas
    que usa Huingán (doca, cheiridopsis, othonna): son de costa seca y en un lago cantan."""
    lib = bpy.data.collections.new("Biblioteca")
    bpy.context.scene.collection.children.link(lib)
    with bpy.data.libraries.load(CAMPO) as (a, b):
        b.objects = [n for n in a.objects if n.startswith("Grass")]
    bq = {}
    for o in b.objects:
        lib.objects.link(o)
        for sl in o.material_slots:
            sl.material = M["pastoRibera"]
        for md in o.modifiers:
            if md.type == "SUBSURF":
                md.levels = md.render_levels = min(md.render_levels, 1)
        bq[o.name.split("_spring")[0]] = o
    ph = {
        "mata": load_ph(lib, "shrub_02", "LOD2"),
        "mata2": load_ph(lib, "shrub_04", "LOD2"),
        "flor": load_ph(lib, "flower_heliophila", "LOD2"),
        "roca": load_ph(lib, "namaqualand_boulder_02", "LOD2"),
        # del pack del lago: el sotobosque húmedo del sur
        "helecho": load_ph(lib, "fern_02", base=PHL),
        "nalca": load_ph(lib, "shrub_sorrel_01", base=PHL),
        "mata3": load_ph(lib, "shrub_01", "LOD2", base=PHL),
        "mata4": load_ph(lib, "shrub_03", "LOD2", base=PHL),
        "renuevo": load_ph(lib, "fir_sapling_medium", "LOD2", base=PHL),
        "renuevo2": load_ph(lib, "pine_sapling_small", base=PHL),
        "piedra": load_ph(lib, "rock_07", "LOD2", base=PHL),
    }
    for k in ("piedra",):   # piedra de lago, gris, no la arenisca del desierto
        for o in ph[k].objects:
            o.data.materials.clear()
            o.data.materials.append(M["roca"])
    lib.hide_render = lib.hide_viewport = True
    return bq, ph


def place_props(coll_lib):
    """Piedras de ribera en la orilla (medio metidas en el agua, que es donde el reflejo las
    duplica) y troncos varados en el canto rodado."""
    coll = bpy.data.collections.new("Rocas")
    bpy.context.scene.collection.children.link(coll)
    rk = load_ph(coll_lib, "coast_rocks_01", "LOD2")
    src = rk.objects[0]
    for x, rot, sc in ((-46.0, 0.5, 0.45), (38.0, 2.3, 0.35), (-17.0, 1.1, 0.25), (62.0, 3.0, 0.4)):
        o = src.copy()
        coll.objects.link(o)
        y = orilla_y(x, -60.0, 40.0) - 2.2
        o.location = (x, y, LAGO - 0.45)
        o.rotation_euler = (0, 0, rot)
        o.scale = (sc, sc, sc * 1.25)
    tr = load_ph(coll_lib, "dead_tree_trunk")
    br = load_ph(coll_lib, "dry_branches_medium_01")
    for k, (x, off, rot) in enumerate(((-28.0, 2.2, 0.4), (24.0, 1.6, 2.0), (-9.0, 3.4, 1.2))):
        y = orilla_y(x, -60.0, 40.0) + off
        src = tr.objects[0] if k < 2 else br.objects[0]
        o = src.copy()
        coll.objects.link(o)
        o.location = (x, y, terrain_h(x, y) + 0.05)
        o.rotation_euler = (0, 0, rot)


def build_vegetation(ribera, bq, ph):
    """Pradera y matorral de ribera con nodos de geometría sobre el terreno cercano, según un
    atributo 'veg': 0 en el agua y en el canto rodado (la orilla tiene que quedar limpia, es por
    donde se mira el lago), 0 bajo la casa, en la pasarela y en el camino, y 1 en la pradera."""
    me = ribera.data
    veg, cam, arb, ori = [], [], [], []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = lake_d(x, y)
        w = min(1.0, max(0.0, (d - 0.8) / 2.2))
        w *= min(1.0, max(0.0, (house_dist(x, y) - 0.2) / 1.5))
        pd = path_dist(x, y)
        w *= min(1.0, max(0.0, (pd - 1.15) / 1.3))
        if 8 < y < 95:
            w *= min(1.0, max(0.0, (road_dist(x, y) - 1.6) / 1.5))
        cam.append(min(1.0, max(0.0, 1.5 - pd / 1.35)) if d > RIBERA - 1 else 0.0)
        # piedras sueltas: sólo en la franja mojada, y menos sobre la pasarela
        ori.append(max(0.0, min(1.0, (1.0 - abs(d - 0.6) / 2.2) * min(1.0, max(0.0, (pd - 1.0) / 1.5)))))
        w *= min(1.0, max(0.0, 0.55 + 1.3 * noise.noise(Vector((x / 7.0, y / 7.0, 2.2)))
                          + 0.4 * noise.noise(Vector((x / 2.5, y / 2.5, 4.1)))))
        veg.append(max(0.0, min(1.0, w)))
        # árboles: el claro alrededor de la casa va limpio hasta 44 m (ahí pasa la órbita del
        # dron), la orilla también, y de ahí para afuera el bosque se cierra en manchones
        a = min(1.0, max(0.0, (math.hypot(x - HC.x, y - HC.y) - 34.0) / 11.0))
        a *= min(1.0, max(0.0, (d - 13.0) / 8.0))
        a *= min(1.0, max(0.0, (pd - 4.0) / 4.0))
        if 8 < y < 120:
            a *= min(1.0, max(0.0, (road_dist(x, y) - 5.0) / 5.0))
        clump = 0.5 + 0.5 * noise.noise(Vector((x / 46.0, y / 46.0, 6.1)))
        arb.append(max(0.0, min(1.0, a * (clump - 0.3) * 2.2)))
    for nombre, datos in (("veg", veg), ("camino", cam), ("arbolado", arb), ("orilla", ori)):
        at = me.attributes.new(nombre, "FLOAT", "POINT")
        at.data.foreach_set("value", datos)
    ng = bpy.data.node_groups.new("Ribera", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])

    def scatter(obj, dens, smin, smax, seed, lo=0.4, hi=0.65, nscale=0.15, tilt=0.12, attr="veg"):
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
        na.inputs["Name"].default_value = attr
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

    # pradera: pasto alto en manchones y pasto bajo parejo
    scatter(bq["Grass_Tall_A"], 30.0, 1.3, 2.3, 21, 0.2, 0.42)
    scatter(bq["Grass_Karl-foerster_B"], 16.0, 0.6, 1.1, 24, 0.22, 0.46, 0.25)
    scatter(bq["Grass_Tall_A"], 18.0, 0.5, 0.9, 25, 0.3, 0.62, 0.35)      # hierba baja entre matas
    scatter(ph["flor"], 1.2, 0.8, 1.3, 27, 0.42, 0.6, 0.2)
    # matorral de ribera: matas de hoja ancha agrupadas, más tupidas lejos de la casa
    scatter(ph["mata"], 0.4, 1.0, 1.8, 31, 0.36, 0.58, 0.09, 0.07)
    scatter(ph["mata2"], 0.3, 1.1, 2.0, 33, 0.4, 0.6, 0.08, 0.07)
    scatter(ph["mata3"], 0.35, 1.0, 1.7, 35, 0.38, 0.58, 0.08, 0.07)
    scatter(ph["mata4"], 0.3, 1.1, 1.9, 37, 0.38, 0.6, 0.09, 0.07)
    # sotobosque húmedo: helechos y nalquilla en los claros, renuevos al borde del bosque
    scatter(ph["helecho"], 1.1, 0.9, 1.6, 44, 0.42, 0.62, 0.12, 0.08)
    scatter(ph["nalca"], 0.8, 0.9, 1.5, 46, 0.44, 0.64, 0.14, 0.08)
    scatter(ph["renuevo"], 0.1, 0.8, 1.6, 48, 0.5, 0.66, 0.06, 0.04, attr="arbolado")
    scatter(ph["renuevo2"], 0.25, 0.9, 1.7, 49, 0.45, 0.65, 0.07, 0.05, attr="arbolado")
    scatter(ph["roca"], 0.006, 0.4, 1.1, 40, 0.55, 0.62, 0.05, 0.4)
    scatter(ph["piedra"], 0.5, 0.25, 0.8, 43, 0.3, 0.7, 0.3, 0.6, attr="orilla")
    Lk.new(join.outputs[0], go.inputs[0])
    md = ribera.modifiers.new("Ribera", "NODES")
    md.node_group = ng
    return ng, scatter


# ---------------------------------------------------------------- contexto: camino, vecinos, árboles
# camino de tierra que llega por detrás de la casa (porch de acceso) y sube hacia los cerros
ROAD = [(3.9, 15.8), (6.5, 27.0), (12.0, 46.0), (8.0, 78.0), (-16.0, 120.0), (-45.0, 180.0),
        (-78.0, 238.0), (-104.0, 296.0)]


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
    # el camino arranca en y = 15,8 (el porch), así que entre 8 y 15 no hay puntos cerca
    return min((math.hypot(x - p.x, y - p.y) for p in _ROAD_PTS if abs(p.y - y) < 8), default=99.0)


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
    col = N.mix(N.math("MULTIPLY", rut, 0.7), (0.27, 0.22, 0.16), (0.18, 0.15, 0.1))
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


# Cabañas vecinas: pocas y lejanas —un lago se vende por la calma—, pero las de la ribera de
# enfrente importan igual que los cerros, porque también se reflejan y dan la escala del agua.
VECINOS = [  # x, y, giro (°), ancho, fondo, alto de muro, muro, techo
    (-205.0, -22.0, 12, 9, 6, 2.6, "madera", "gris"), (238.0, -8.0, -18, 10, 7, 2.7, "negro", "gris"),
    (-355.0, 30.0, 25, 8, 6, 2.5, "madera", "teja"), (112.0, 158.0, -8, 10, 7, 2.7, "blanco", "gris"),
    (-150.0, 205.0, 15, 9, 6, 2.6, "madera", "gris"), (330.0, 118.0, 30, 11, 7, 2.8, "blanco", "teja"),
    (-96.0, -905.0, 8, 10, 7, 2.6, "madera", "gris"), (205.0, -898.0, -12, 9, 6, 2.6, "blanco", "gris"),
    (-430.0, -880.0, 20, 11, 7, 2.7, "madera", "teja"),
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


def build_trees(lib):
    """Árboles reales de Poly Haven (CC0, tools/get_assets_lago.sh), en dos bandas de detalle.

    En Huingán el bosque del fondo eran troncos con copas de esferas desplazadas, y a 300 m con
    bruma pasaba. Acá no pasa: el bosque de un lago se ve **dos veces** —el real y el que devuelve
    el agua, que es la mitad de la imagen— y además la ribera de enfrente es el fondo de casi todas
    las tomas. Así que son modelos con tronco, ramas y follaje:
      cerca  LOD1, para el bosque que rodea el claro de la casa (hasta ~120 m)
      lejos  LOD2, para la ribera opuesta, las laterales y los cerros
    Mezcla de conífera alta (fir, pine) y de copa ancha (island_tree, tree_small), que es como se
    ve un bosque nativo del sur: la conífera marca la silueta y la copa ancha llena."""
    cerca = bpy.data.collections.new("ArbolesCerca")
    lejos = bpy.data.collections.new("ArbolesLejos")
    for c in (cerca, lejos):
        lib.children.link(c)
    conif = [f"{t}_tree_01_{v}" for t in ("fir", "pine") for v in "abc"]
    ancha = ["island_tree_01", "island_tree_02", "island_tree_03"]
    for dest, lod_c, lod_a in ((cerca, "LOD1", "LOD1"), (lejos, "LOD2", "LOD1")):
        for ident in ("fir_tree_01", "pine_tree_01"):
            load_ph(dest, ident, base=PHL, nombres=[f"{n}_{lod_c}" for n in conif])
        for ident in ancha:
            load_ph(dest, ident, base=PHL, nombres=[f"{ident}_{lod_a}", f"{ident}_a_{lod_a}"])
        load_ph(dest, "tree_small_02", base=PHL, nombres=["tree_small_02_LOD1"])
    for c in (cerca, lejos):
        # las colecciones de load_ph quedan anidadas; se aplanan para que Pick Instance las vea
        for sub in list(c.children):
            for o in list(sub.objects):
                sub.objects.unlink(o)
                c.objects.link(o)
            c.children.unlink(sub)
            bpy.data.collections.remove(sub)
        alto = [round(o.dimensions.z, 1) for o in c.objects]
        print("  %-14s %2d árboles  alturas %s" % (c.name, len(c.objects), sorted(alto)))
    return cerca, lejos


def build_far_trees(far, arboles):
    """Bosque del paisaje lejano: cerrado en la ribera de enfrente (que es lo que se refleja) y
    en manchones de este lado, fuera del claro de la casa; nunca dentro del agua ni sobre la
    roca de las cumbres (atributo 'bosque')."""
    me = far.data
    w = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = lake_d(x, y)
        if d < 5.0:
            w.append(0.0)                       # nada de bosque dentro del agua
            continue
        if y < LKY:
            a = min(1.0, max(0.0, (d - 5.0) / 20.0))
            clump = 0.5 + 0.5 * noise.noise(Vector((x / 180.0, y / 180.0, 7.7)))
            base = min(1.0, 0.55 + (clump - 0.45) * 1.8)
        else:
            a = min(1.0, max(0.0, (d - 22.0) / 45.0)) * min(1.0, max(0.0, (math.hypot(x - HC.x, y - HC.y) - 90) / 70.0))
            clump = 0.5 + 0.5 * noise.noise(Vector((x / 140.0, y / 140.0, 7.7)))
            hill = min(1.0, max(0.0, (y - 230) / 250.0))
            base = min(1.0, max(0.0, (clump - 0.42) * 3.0 + 0.9 * hill))
        a *= min(1.0, max(0.0, 1.0 - (v.co.z - TREE_LINE + 120.0) / 120.0))   # línea de árboles
        a *= min(1.0, max(0.0, 1.0 - (math.hypot(x - HC.x, y - HC.y) - 2300.0) / 500.0))
        vecina = max((max(0.0, 1.0 - math.hypot(x - vx, y - vy) / 40.0) for vx, vy, *_ in VECINOS), default=0)
        w.append(max(0.0, a * base - 0.9 * vecina))
    at = me.attributes.new("bosque", "FLOAT", "POINT")
    at.data.foreach_set("value", w)
    ng = bpy.data.node_groups.new("Arboleda", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = 5.0
    dist.inputs["Density Max"].default_value = 0.08
    na = N.new("GeometryNodeInputNamedAttribute")
    na.data_type = "FLOAT"
    na.inputs["Name"].default_value = "bosque"
    Lk.new(na.outputs["Attribute"], dist.inputs["Density Factor"])
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    ins = N.new("GeometryNodeInstanceOnPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = arboles
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    ins.inputs["Pick Instance"].default_value = True
    ri = N.new("FunctionNodeRandomValue")
    ri.data_type = "INT"
    for sk in ri.inputs:
        if sk.type == "INT" and sk.name in ("Min", "Max"):
            sk.default_value = 0 if sk.name == "Min" else len(arboles.objects) - 1
    rr = N.new("FunctionNodeRandomValue")
    rr.data_type = "FLOAT_VECTOR"
    rr.inputs["Max"].default_value = (0.05, 0.05, 6.28)
    rs = N.new("FunctionNodeRandomValue")
    rs.data_type = "FLOAT"
    for sk in rs.inputs:
        if sk.type == "VALUE" and sk.name in ("Min", "Max"):
            sk.default_value = 0.65 if sk.name == "Min" else 1.25
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


def build_context(M, scatter=None):
    coll = bpy.data.collections.new("Contexto")
    bpy.context.scene.collection.children.link(coll)
    build_road(coll)
    build_neighbors(coll)
    cerca, lejos = build_trees(bpy.data.collections["Biblioteca"])
    build_far_trees(bpy.data.objects["Lejos"], lejos)
    if scatter is not None:
        # bosque del claro: los árboles de cerca sobre el terreno fino, con el atributo 'arbolado'
        # (orilla y claro limpios, bosque cerrándose de 44 m para afuera)
        scatter(cerca, 0.06, 0.7, 1.3, 51, 0.28, 0.6, 0.03, 0.03, attr="arbolado")


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
    # bajo el horizonte el cielo físico es "suelo" oscuro: los reflejos rasantes del mar lo verían
    # como una línea oscura en el horizonte. Se usa el cielo en espejo (z -> |z|).
    sxyz = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Generated"], sxyz.inputs[0])
    az_ = n.new("ShaderNodeMath")
    az_.operation = "ABSOLUTE"
    l.new(sxyz.outputs["Z"], az_.inputs[0])
    cxyz = n.new("ShaderNodeCombineXYZ")
    l.new(sxyz.outputs["X"], cxyz.inputs[0])
    l.new(sxyz.outputs["Y"], cxyz.inputs[1])
    l.new(az_.outputs[0], cxyz.inputs[2])
    l.new(cxyz.outputs[0], sky.inputs["Vector"])
    gain = n.new("ShaderNodeMix")
    gain.data_type = "RGBA"
    gain.blend_type = "MULTIPLY"
    gain.inputs[0].default_value = 1.0
    gain.inputs[7].default_value = (SKY_GAIN, SKY_GAIN, SKY_GAIN, 1)
    l.new(sky.outputs["Color"], gain.inputs[6])
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Generated"], sep.inputs[0])
    # El HDRI lakeside trae un chorreo vertical de sol: la columna del sol sigue brillando (x200
    # sobre el cielo que la rodea) hasta los 80° de elevación, y en cuadro sale como una raya
    # blanca cerca del cenit. Donde el HDRI está muchísimo más brillante que el cielo y bien
    # arriba —el disco del sol está a 31,8°, debajo de la guarda— se usa el cielo físico.
    bw = n.new("ShaderNodeRGBToBW")
    l.new(env.outputs["Color"], bw.inputs[0])
    g1 = n.new("ShaderNodeMapRange")
    g1.interpolation_type = "SMOOTHSTEP"
    g1.inputs[1].default_value, g1.inputs[2].default_value = 20.0, 60.0
    l.new(bw.outputs[0], g1.inputs[0])
    g2 = n.new("ShaderNodeMapRange")
    g2.interpolation_type = "SMOOTHSTEP"
    g2.inputs[1].default_value, g2.inputs[2].default_value = 0.54, 0.62   # seno de la elevación
    l.new(sep.outputs["Z"], g2.inputs[0])
    gmul = n.new("ShaderNodeMath")
    gmul.operation = "MULTIPLY"
    l.new(g1.outputs[0], gmul.inputs[0])
    l.new(g2.outputs[0], gmul.inputs[1])
    limpio = n.new("ShaderNodeMix")
    limpio.data_type = "RGBA"
    l.new(gmul.outputs[0], limpio.inputs[0])
    l.new(env.outputs["Color"], limpio.inputs[6])
    l.new(gain.outputs[2], limpio.inputs[7])
    hi = n.new("ShaderNodeMapRange")
    hi.interpolation_type = "SMOOTHSTEP"
    hi.inputs[1].default_value, hi.inputs[2].default_value = 0.3, 0.6   # seno de la elevación
    l.new(sep.outputs["Z"], hi.inputs[0])
    cam_sky = n.new("ShaderNodeMix")
    cam_sky.data_type = "RGBA"
    l.new(hi.outputs[0], cam_sky.inputs[0])
    l.new(gain.outputs[2], cam_sky.inputs[6])
    l.new(limpio.outputs[2], cam_sky.inputs[7])
    lp = n.new("ShaderNodeLightPath")
    pick = n.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    seen = n.new("ShaderNodeMath")          # cámara o reflejos (mar, vidrios) ven el cielo limpio
    seen.operation = "MAXIMUM"
    l.new(lp.outputs["Is Camera Ray"], seen.inputs[0])
    l.new(lp.outputs["Is Glossy Ray"], seen.inputs[1])
    l.new(seen.outputs[0], pick.inputs[0])
    l.new(limpio.outputs[2], pick.inputs[6])
    l.new(cam_sky.outputs[2], pick.inputs[7])
    l.new(pick.outputs[2], bg.inputs[0])
    w.mist_settings.start = 80
    w.mist_settings.depth = 2600
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
    sc.view_settings.exposure = 0.18
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

    # bruma = 0,26 · (1 − e^(−(z − 80) / 2600)), sobre todo lo que no es cielo (z < 10 km de cámara
    # para el cielo no hay superficie: su profundidad es enorme). Crece sin corte hasta el horizonte.
    sc.view_layers[0].use_pass_z = True
    zrel = mnode("SUBTRACT", 80.0)
    pos = mnode("MAXIMUM", 0.0)
    sc_ = mnode("DIVIDE", -2600.0)
    ex = mnode("EXPONENT", 0.0)
    one = mnode("SUBTRACT", 1.0)
    sky = mnode("LESS_THAN", 1.0e7)
    mul = mnode("MULTIPLY", 1.0)
    amt = mnode("MULTIPLY", 0.26)
    one.inputs[0].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0.66, 0.72, 0.78, 1)
    nt.links.new(rl.outputs["Depth"], zrel.inputs[0])
    nt.links.new(zrel.outputs[0], pos.inputs[0])
    nt.links.new(pos.outputs[0], sc_.inputs[0])
    nt.links.new(sc_.outputs[0], ex.inputs[0])
    nt.links.new(ex.outputs[0], one.inputs[1])
    nt.links.new(rl.outputs["Depth"], sky.inputs[0])
    nt.links.new(one.outputs[0], mul.inputs[0])
    nt.links.new(sky.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], amt.inputs[0])
    # + una bruma de lejanía para la cordillera del fondo: 0,3 · (1 − e^(−z / 9000))
    far_s = mnode("DIVIDE", -9000.0)
    far_e = mnode("EXPONENT", 0.0)
    far_1 = mnode("SUBTRACT", 1.0)
    far_1.inputs[0].default_value = 1.0
    far_a = mnode("MULTIPLY", 0.22)
    far_m = mnode("MULTIPLY", 1.0)
    tot = mnode("ADD", 0.0)
    nt.links.new(pos.outputs[0], far_s.inputs[0])
    nt.links.new(far_s.outputs[0], far_e.inputs[0])
    nt.links.new(far_e.outputs[0], far_1.inputs[1])
    nt.links.new(far_1.outputs[0], far_a.inputs[0])
    nt.links.new(far_a.outputs[0], far_m.inputs[0])
    nt.links.new(sky.outputs[0], far_m.inputs[1])
    nt.links.new(amt.outputs[0], tot.inputs[0])
    nt.links.new(far_m.outputs[0], tot.inputs[1])
    nt.links.new(tot.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[6])
    nt.links.new(mix.outputs[2], go.inputs[0])


# Tomas fijas de dron para las fotos de aprobación (RECETA.md §0), encuadres a propósito abiertos
# para poder reencuadrar y desenfocar en la edición. Las dos primeras se plantan sobre el agua,
# frente al testero vidriado, que es el enganche de la casa:
#   izq  el lado del faldón largo (la cumbrera está corrida a x = 5,6, así que el techo grande
#        baja hacia -X): se ve la casa entera de perfil, el muelle y el reflejo
#   der  el lado del alero alto (+X): la casa se ve más vertical, con la ribera opuesta detrás
#   atras  desde el camino de acceso, con el porch y el lago al fondo
VISTAS = {
    "izq": ((-17.0, -31.0, 8.0), (3.2, 5.0, 2.4), 30),
    "der": ((13.5, -33.0, 8.0), (3.6, 5.0, 2.4), 30),
    "atras": ((-19.0, 27.0, 16.0), (3.4, 6.0, 1.8), 30),
    "der_atras": ((16.0, 36.0, 12.0), (3.6, 7.0, 1.4), 30),
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


# ---------------------------------------------------------------- recorrido de dron (por secciones)
# El reel se divide en secciones que se renderizan por separado (--vista dron --tramo sN) y se unen
# en la edición como una sola toma de dron (la última pose de una es la primera de la siguiente),
# con la misma lógica del reel de Casa Lingue:
#   s1  aproximación: parte lejos y alto sobre la playa y se acerca en espiral, desacelerando,
#       hasta la diagonal frontal izquierda                                                10 s
#   s2  vuelo lento rodeando el frente hacia el costado, a distancia casi constante
#   s3  sube a la vista aérea y el techo se corta: recintos hasta la cenital
#   s4  paso a la planta y la lámina (post 2D, como tools/video_corte.py en Lingue)
#   s5  baja en espiral hacia la fachada de acceso y el camino
#   s6  sube, cruza al frente con luz de atardecer y se aleja (toma final)
# Un dron no hace zoom: la distancia cambia de forma continua y suave (nunca "respira" con el giro);
# el encuadre adaptable sólo fija la distancia final para que la casa quepa en pantalla.
SECCIONES = {"s1": 240, "s2": 192, "s3": 240, "s5": 192}
INICIO = {"s2": 0, "s3": 192, "s5": 432}      # cuadro de inicio de cada sección en la ruta continua s2..s5
CASA_BOX = (0.0, L, -0.9, D + 0.9, GROUND, 6.6)    # caja de la casa (con escaleras) para encuadrar
CASA_C = Vector((L / 2, D / 2, 2.4))                 # punto al que mira el dron
FIT = 0.74                                           # ancho de pantalla que ocupa la casa


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def fit_distance(direc, target, lens, aspect, fit=FIT):
    """Distancia a la que la caja de la casa ocupa `fit` del ancho de pantalla, mirando a `target`
    desde la dirección `direc` (vector unitario desde el objetivo hacia la cámara). De frente la
    casa muestra todo su largo y la cámara queda más lejos; en diagonal, más cerca."""
    fwd = -direc
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd)
    half_w = (36.0 * aspect / 2) / lens          # sensor ajustado al alto (vertical): tan(fov_h/2)
    half_h = (36.0 / 2) / lens
    x0, x1, y0, y1, z0, z1 = CASA_BOX
    corners = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    lo, hi = 5.0, 200.0
    for _ in range(40):
        dist = (lo + hi) / 2
        cam = target + direc * dist
        ok = True
        for c in corners:
            v = c - cam
            depth = v.dot(fwd)
            if depth <= 0.1 or abs(v.dot(right) / depth) > half_w * fit or abs(v.dot(up) / depth) > half_h * 0.9:
                ok = False
                break
        lo, hi = (dist, hi) if not ok else (lo, dist)
    return hi


def smootherstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)


S1_AZ = (-118.0, -42.0)      # azimut (0 = de frente, la cámara hacia -Y; negativo = lado izquierdo)
S1_EL = (24.0, 17.0)         # elevación (°)
S1_D0 = 165.0                # distancia inicial (m)


def pose_s1(f, n):
    """Aproximación en espiral: el giro avanza parejo y la distancia cae en escala logarítmica con
    salida suave (el dron frena al llegar). El punto de mira pasa de la playa a la casa."""
    u = f / (n - 1)
    ua = u * u * (3 - 2 * u)
    az = math.radians(S1_AZ[0] + (S1_AZ[1] - S1_AZ[0]) * ua)
    el = math.radians(S1_EL[0] + (S1_EL[1] - S1_EL[0]) * ua)
    direc = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    ud = 1 - (1 - u) ** 2.2                          # rápido al comienzo, frena al final
    tgt = Vector((L / 2, -14.0, -2.0)).lerp(CASA_C, smootherstep(min(1.0, u * 1.25)))
    d_end = S1_END_D[0]
    dist = S1_D0 * (d_end / S1_D0) ** ud
    return direc, tgt, dist


S1_END_D = [None]


def s1_setup(w, h, lens):
    """Distancia final de s1: la que deja la casa en el encuadre adaptable en la diagonal final."""
    az, el = math.radians(S1_AZ[1]), math.radians(S1_EL[1])
    direc = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    S1_END_D[0] = fit_distance(direc, CASA_C, lens, w / h)


# ------------------------------------------- ruta continua s2 -> s3 -> s5 (spline por claves)
CUT_TOP, CUT_LOW = 5.2, 1.6      # altura del corte: sobre el techo (casa entera) / a media altura (planta 3D)
# claves: (cuadro global, azimut°, elevación°, distancia, altura de corte, parar)
#   distancia: número (m) o ("fit", factor): la del encuadre adaptable en esa dirección
#   parar=True: la cámara llega quieta a esa clave (fin de s3, antes del paso a la planta)
RUTA = [
    (0, S1_AZ[1], S1_EL[1], ("fit", 1.0), CUT_TOP, True),     # = último cuadro de s1
    (90, 5.0, 16.0, ("frente", 1.0), CUT_TOP, False),
    (192, 68.0, 15.0, ("frente", 1.0), CUT_TOP, False),       # fin s2: costado derecho, sobre los pilotes
    (262, 80.0, 42.0, ("fit", 1.05), CUT_TOP, False),
    (352, 88.0, 78.0, ("fit", 1.0), CUT_LOW, False),
    (432, 90.0, 89.5, ("fit", 1.0), CUT_LOW, True),           # fin s3: cenital, casa a lo largo de la pantalla
    (500, 118.0, 55.0, ("fit", 1.15), CUT_TOP, False),
    (624, 152.0, 16.0, ("fit", 1.0), CUT_TOP, True),          # fin s5: fachada de acceso y el camino
]
CUT_KEYS = [(0, CUT_TOP), (250, CUT_TOP), (370, CUT_LOW), (432, CUT_LOW), (460, CUT_LOW), (540, CUT_TOP), (624, CUT_TOP)]


def _dir(az, el):
    az, el = math.radians(az), math.radians(el)
    return Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def _hermite_channel(keys, f):
    """Interpolación cúbica de Hermite con tangentes de Catmull-Rom (0 en claves 'parar' y extremos)."""
    ts = [k[0] for k in keys]
    if f <= ts[0]:
        return keys[0][1]
    if f >= ts[-1]:
        return keys[-1][1]
    i = max(j for j in range(len(ts) - 1) if ts[j] <= f)

    def tan(j):
        if j == 0 or j == len(keys) - 1 or keys[j][2]:
            return 0.0
        return (keys[j + 1][1] - keys[j - 1][1]) / (ts[j + 1] - ts[j - 1])

    h = ts[i + 1] - ts[i]
    t = (f - ts[i]) / h
    p0, p1, m0, m1 = keys[i][1], keys[i + 1][1], tan(i) * h, tan(i + 1) * h
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1


_RUTA_D = {}


def ruta_setup(w, h, lens):
    """Resuelve las distancias de la ruta: 'fit' en la dirección de la clave; 'frente' = el mayor
    encuadre del arco frontal (así el dron no se acerca y aleja mientras rodea la casa)."""
    s1_setup(w, h, lens)
    frente = max(fit_distance(_dir(a, 16.0), CASA_C, lens, w / h) for a in range(-45, 75, 5))
    for k in RUTA:
        kind, fac = k[3]
        d = frente if kind == "frente" else fit_distance(_dir(k[1], k[2]), CASA_C, lens, w / h)
        _RUTA_D[k[0]] = d * fac
    _RUTA_D[0] = S1_END_D[0]


def ruta_pose(g):
    """Pose en el cuadro global g de la ruta continua s2..s5 (distancia en escala logarítmica)."""
    az = _hermite_channel([(k[0], k[1], k[5]) for k in RUTA], g)
    el = _hermite_channel([(k[0], k[2], k[5]) for k in RUTA], g)
    ld = _hermite_channel([(k[0], math.log(_RUTA_D[k[0]]), k[5]) for k in RUTA], g)
    return _dir(az, min(el, 89.5)), CASA_C, math.exp(ld)


def cut_z(g):
    return _hermite_channel([(k[0], k[1], True) for k in CUT_KEYS], g)


def section_groups():
    """Grupos de shader de corte (como en Casa Lingue): lo que queda sobre el plano de corte se
    vuelve transparente; en muros y techo ('relleno') las caras interiores cortadas se ven oscuras."""
    groups = {}
    for cap in (False, True):
        ng = bpy.data.node_groups.new("Corte" + ("Relleno" if cap else ""), "ShaderNodeTree")
        ng.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
        ng.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
        n, l = ng.nodes, ng.links
        gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
        geo = n.new("ShaderNodeNewGeometry")
        sep = n.new("ShaderNodeSeparateXYZ")
        l.new(geo.outputs["Position"], sep.inputs[0])
        val = n.new("ShaderNodeValue")
        val.name = "AlturaCorte"
        gt = n.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        l.new(sep.outputs["Z"], gt.inputs[0])
        l.new(val.outputs[0], gt.inputs[1])
        shader = gi.outputs[0]
        if cap:
            em = n.new("ShaderNodeEmission")
            em.inputs["Color"].default_value = (0.03, 0.03, 0.03, 1)
            mc = n.new("ShaderNodeMixShader")
            l.new(geo.outputs["Backfacing"], mc.inputs[0])
            l.new(gi.outputs[0], mc.inputs[1])
            l.new(em.outputs[0], mc.inputs[2])
            shader = mc.outputs[0]
        tr = n.new("ShaderNodeBsdfTransparent")
        mx = n.new("ShaderNodeMixShader")
        l.new(gt.outputs[0], mx.inputs[0])
        l.new(shader, mx.inputs[1])
        l.new(tr.outputs[0], mx.inputs[2])
        l.new(mx.outputs[0], go.inputs[0])
        groups[cap] = ng
    return groups


def apply_section(frames, g0):
    """Corte animado de la casa: shader en sus materiales (no en el paisaje) y, en las piezas, se
    borran con nodos de geometría las caras enteras sobre el corte (no se apilan transparencias)."""
    house = list(bpy.data.collections["Casa"].objects)
    groups = section_groups()
    capped = {"ChapaNegra", "MaderaFachada", "MaderaCielo", "MuroInterior", "Bo_MarcoNegro", "Bo_PuertaMadera"}
    mats = {sl.material for o in house for sl in o.material_slots if sl.material}
    for m in mats:
        out = next(nd for nd in m.node_tree.nodes if nd.bl_idname == "ShaderNodeOutputMaterial" and nd.is_active_output)
        if not out.inputs["Surface"].links:
            continue
        lk = out.inputs["Surface"].links[0]
        src = lk.from_socket
        m.node_tree.links.remove(lk)
        g = m.node_tree.nodes.new("ShaderNodeGroup")
        g.node_tree = groups[m.name in capped]
        m.node_tree.links.new(src, g.inputs[0])
        m.node_tree.links.new(g.outputs[0], out.inputs["Surface"])
    ng = bpy.data.node_groups.new("CorteGeo", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pos = N.new("GeometryNodeInputPosition")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(pos.outputs[0], sep.inputs[0])
    cmp_ = N.new("FunctionNodeCompare")
    cmp_.data_type = "FLOAT"
    cmp_.operation = "GREATER_THAN"
    zval = N.new("ShaderNodeValue")
    Lk.new(sep.outputs["Z"], cmp_.inputs["A"])
    Lk.new(zval.outputs[0], cmp_.inputs["B"])
    ev = N.new("GeometryNodeFieldOnDomain")
    ev.domain = "FACE"
    ev.data_type = "BOOLEAN"
    Lk.new(cmp_.outputs[0], ev.inputs[0])
    dl = N.new("GeometryNodeDeleteGeometry")
    dl.domain = "FACE"
    Lk.new(gi.outputs[0], dl.inputs["Geometry"])
    Lk.new(ev.outputs[0], dl.inputs["Selection"])
    Lk.new(dl.outputs[0], go.inputs[0])
    for o in house:
        if o.type == "MESH" and o.name != "Boldo_Casco":
            o.modifiers.new("Corte", "NODES").node_group = ng
    socks = [zval.outputs[0]] + [g.nodes["AlturaCorte"].outputs[0] for g in groups.values()]
    for f in range(frames):
        for sk in socks:
            sk.default_value = cut_z(g0 + f)
            sk.keyframe_insert("default_value", frame=f + 1)
    for o in house:   # con el techo abierto entra el día: luces interiores suaves
        if o.type == "LIGHT":
            o.visible_camera = False
            o.data.energy *= 0.3
    bpy.context.scene.cycles.transparent_max_bounces = 24



POSES = {"s1": pose_s1}
SETUP = {"s1": s1_setup}
for _t in ("s2", "s3", "s5"):
    POSES[_t] = (lambda t: lambda f, n: ruta_pose(INICIO[t] + f))(_t)
    SETUP[_t] = ruta_setup


def build_drone(cam):
    """Anima la cámara cuadro a cuadro según la sección pedida y el oleaje en el tiempo."""
    sc = bpy.context.scene
    tramo = opts["tramo"]
    n = SECCIONES[tramo]
    sc.frame_start, sc.frame_end = 1, n
    sc.frame_step = int(opts.get("step", "1"))   # >1 para previsualizaciones rápidas
    w, h = (int(v) for v in opts["res"].split("x"))
    lens = 30.0
    cam.data.lens = lens
    if tramo in SETUP:
        SETUP[tramo](w, h, lens)
    for f in range(n):
        pose = POSES[tramo](f, n)
        direc, tgt = pose[0], pose[1]
        dist = pose[2] if len(pose) > 2 else fit_distance(direc, tgt, lens, w / h)
        cam.location = tgt + direc * dist
        cam.rotation_euler = (-direc).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=f + 1)
        cam.keyframe_insert("rotation_euler", frame=f + 1)
    # el tiempo del agua avanza con el video (cada sección sigue donde quedó la anterior)
    md = bpy.data.objects["LagoOleaje"].modifiers["Oleaje"]
    t0 = float(opts.get("t_agua", "3.0")) + sum(SECCIONES[k] for k in sorted(SECCIONES) if k < tramo) / FPS
    for f, t in ((1, t0), (n, t0 + (n - 1) / FPS)):
        md.time = t
        md.keyframe_insert("time", frame=f)
    for fc in list(cam.animation_data.action.fcurves if hasattr(cam.animation_data.action, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    act = bpy.data.objects["LagoOleaje"].animation_data.action
    for fc in getattr(act, "fcurves", []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    if tramo in ("s3", "s5"):
        apply_section(n, INICIO[tramo])
    if tramo == "s3":   # dónde cae la casa en la cenital final: para calzar la planta (tools/plano_boldo.py)
        import json
        from bpy_extras.object_utils import world_to_camera_view
        direc, tgt, dist = ruta_pose(INICIO["s3"] + n - 1)
        cam.location = tgt + direc * dist
        cam.rotation_euler = (-direc).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        pts = {}
        for k, (x, y) in {"o": (0.0, 0.0), "x": (L, 0.0), "y": (0.0, D)}.items():
            v = world_to_camera_view(sc, cam, Vector((x, y, 0.3)))
            pts[k] = [v.x * w, (1 - v.y) * h]
        out_dir = os.path.dirname(opts["out"])
        os.makedirs(out_dir, exist_ok=True)
        json.dump({"pts": pts, "res": [w, h]}, open(os.path.join(out_dir, "plano.json"), "w"))
    sc.render.use_overwrite = False      # reanudable: no vuelve a renderizar cuadros guardados
    sc.render.use_placeholder = True
    sc.render.use_persistent_data = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.35



def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = materials()
    load_house(M)
    ribera = build_landscape(M)
    bq, ph = load_assets(M)
    _, scatter = build_vegetation(ribera, bq, ph)
    place_props(bpy.data.collections["Biblioteca"])
    build_context(M, scatter)
    build_muelle(M, ph)
    build_cercos(M)
    build_world()
    setup_render()
    sc = bpy.context.scene
    if opts["vista"] == "dron":
        cam = link(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
        cam.data.clip_end = 5000
        sc.camera = cam
        build_drone(cam)
    else:
        build_camera()
    if opts["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=opts["save"])
    sc.render.filepath = opts["out"]
    if opts["vista"] == "dron" and not opts.get("cuadro"):
        bpy.ops.render.render(animation=True)
    else:
        sc.frame_set(int(opts.get("cuadro") or opts["still"]))
        bpy.ops.render.render(write_still=True)


main()
