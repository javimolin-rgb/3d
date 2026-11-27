"""Escena 3D de Casa Maitén en la costa rocosa (Blender 5.x, Cycles).

Uso:
  python casa_maiten_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  (vistas: izq / der = tomas fijas de dron desde el mar, a cada lado del frente;
   izq_atras / der_atras = desde el acceso mirando al mar)
  python casa_maiten_3d.py -- --vista dron --tramo s1 --out frames_maiten/s1/f_ [--cuadro 80]
  (recorrido de dron por secciones, ver SECCIONES; --cuadro N renderiza sólo ese cuadro;
   el tramo s3p es s3 con las pausas del barrido sobre cada piso)

La casa sale del modelo STL de Neorigen (assets/maiten/casa.blend, generado con
tools/extraer_maiten_stl.py): 16,27 m de ancho por 11,84 de fondo y **8,10 de alto, la más alta
de las nueve**. Es de dos pisos (piso terminado en z = 1,10, losa del segundo en 3,85), con la
cumbrera a 7,82 en x = 8,38 y faldones de 19° y 20°. La terraza corre a todo el ancho por el
frente (y < 3,20) mirando al mar; el acceso es **lateral**, por el porch de x < 2,70; y el anexo
del lavadero queda en x > 13,80.

Emplazamiento: **mar roca**. La casa se para sobre una plataforma de roca unos 4,5 m sobre el mar,
y entre ella y el agua hay afloramientos que suben hasta ~3 m sobre la plataforma. Eso es el
enganche hecho terreno: con 8,10 m de alto la casa **mira por encima de la roca** —desde el
segundo piso y la doble altura se ve el mar entero, desde la terraza se ve la piedra—, que es
justo lo que la salva de quedar encajonada contra el farellón.

Del mar de Casa Huingán se hereda todo (oleaje en tres escalas, espuma, fondo, cielo mezclado con
HDRI). Lo que cambia es la orilla: en vez de la parábola suave de arena, roca. Y con ella la
espuma, que en una playa se calcula por profundidad del agua y acá tiene que **concentrarse donde
el agua golpea la piedra**: los afloramientos son explícitos (`ROCAS`), así que el shader del agua
sabe exactamente dónde están y les arma el collar de espuma alrededor (ver `rocas_nodes`).
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
CASA = os.path.join(ROOT, "assets", "maiten", "casa.blend")
CAMPO = os.path.join(ROOT, "assets", "campo", "pastos_botaniq.blend")
PH = os.path.join(ROOT, "assets", "playa", "ph")   # recursos de Poly Haven (tools/get_assets_playa.sh)
# Acantilado de costa, CC0. De los cinco HDRI de costa es el que calza con "mar roca" y todavía
# trae sol de verdad: `cape_hill` tiene el carácter pero el sol a 4,2°, casi en el horizonte, y
# con eso la casa queda sin modelado. Medidos con tools/medir_sol_hdri.py.
HDRI = os.path.join(PH, "hdri", "white_cliff_top_2k.exr")
HDRI_SUN_U = 0.6243          # columna del sol en el HDRI (0-1)
SUN_ELEV = 23.2              # elevación del sol en el HDRI
SKY_GAIN = 0.06              # brillo del cielo físico (horizonte) para empatar con el HDRI
SUN_AZ = 205.0               # sol desde adelante-izquierda: deja brillo en el agua y moja la roca
WB_TEMP = float(opts["wb"])
L, D = 16.27, 11.84          # ancho y fondo total del casco (porch + caja + anexo) x (terraza + caja)
HC = Vector((L / 2, D / 2))  # centro de la casa en planta
PISO, PISO2 = 1.10, 3.85     # pisos terminados (la casa es de dos pisos)
GROUND = 0.0                 # plataforma de roca bajo la casa (el zócalo del STL arranca en z = 0)
SEA = -7.0                   # nivel del mar: la plataforma queda 7 m sobre el agua
SHORE_Y = -9.0               # línea de agua frente a la casa: la casa se para **en el borde**
SHORE_K = 520.0              # la orilla se abre hacia +Y a ambos lados: y = SHORE_Y + (x - XC)² / K
XC = 8.1
FPS = 24

# Afloramientos de roca entre la casa y el agua. Van **explícitos** y no como ruido porque la
# firma visual del emplazamiento es la ola reventando contra la piedra, y para eso el shader del
# agua tiene que saber dónde está cada roca y armarle el collar de espuma alrededor (rocas_nodes).
# Con ruido, la espuma cae donde no hay roca y la roca queda sin espuma.
#   (x, y, radio, alto sobre el nivel del mar)
#   (x, y, radio, alto sobre el nivel del mar).  Con SEA = -7, un alto de 8,8 deja la cima 1,8 m
#   sobre la plataforma: por encima del piso de la terraza (1,10) y muy por debajo del segundo
#   piso (3,85). Eso es el enganche medido: desde la terraza se ve piedra, desde arriba, mar.
ROCAS = [
    (1.0, -6.0, 4.4, 8.8),       # la grande de la izquierda, la que hay que mirar por encima
    (10.0, -5.0, 3.6, 8.4),
    (18.0, -8.0, 4.0, 7.2),
    (-5.0, -12.0, 3.4, 4.5),     # ya en el agua: rompen solas
    (6.0, -13.5, 3.0, 3.5),
    (21.0, -14.0, 3.8, 4.2),
    (-10.0, -2.0, 4.0, 8.6),     # cierra el encuadre por la izquierda
    (25.0, -2.0, 4.4, 8.9),      # y por la derecha
]


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
    return (SHORE_Y + (x - XC) ** 2 / SHORE_K + 2.0 * math.sin(x / 17.0 + 1.3)
            + 5.5 * noise.noise(Vector((x / 23.0, 0.0, 1.7)))
            + 2.0 * noise.noise(Vector((x / 7.0, 0.0, 5.2))))


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


def rocas_h(x, y):
    """Altura absoluta del afloramiento de `ROCAS` que cubre (x, y); muy abajo si no hay ninguno.

    Cada roca es un domo que arranca en el nivel del mar y sube `alto`, con el radio modulado por
    ruido para que la planta no sea un círculo. El terreno se queda con el máximo entre su perfil
    y esto, así la misma función sirve para las rocas que emergen del agua y para las que se
    apoyan en la plataforma."""
    top = SEA - 99.0
    for cx, cy, r, alto in ROCAS:
        # planta elíptica y girada, distinta en cada roca: en círculo todas salían iguales
        ang = cx * 0.73 + cy * 0.19
        ca, sa = math.cos(ang), math.sin(ang)
        dx, dy = x - cx, y - cy
        u, v = dx * ca + dy * sa, (-dx * sa + dy * ca) * 1.45
        rr = r * (0.80 + 0.40 * (0.5 + 0.5 * noise.noise(Vector((x / 4.5, y / 4.5, cx * 3.7)))))
        t = math.hypot(u, v) / rr
        if t >= 1.0:
            continue
        # Perfil de **meseta con falda empinada**, no de campana: una roca de costa tiene lomo
        # plano y caras verticales. Con (1 - t²)^0,6 salían huevos.
        perfil = min(1.0, (1.0 - t * t) * 1.45) ** 0.45
        # y se rompe con ruido en la altura, en dos escalas: un elipsoide limpio se lee como una
        # burbuja de plastilina, y a 30 m de la cámara es lo primero que canta
        perfil *= (0.76 + 0.32 * noise.noise(Vector((x / 2.8, y / 2.8, cx * 1.7)))
                   + 0.20 * noise.noise(Vector((x / 1.1, y / 1.1, cx * 5.3))))
        top = max(top, SEA + alto * max(0.0, perfil))
    return top


def rocas_nodes(N, sep):
    """0-1: cuán cerca está el punto de un afloramiento, en nodos. Es el collar de espuma.

    Es la razón de que `ROCAS` sea una lista explícita y no ruido: el shader del agua necesita
    saber dónde está cada piedra para reventar ahí y no a cinco metros."""
    f = None
    for cx, cy, r, _alto in ROCAS:
        dx = N.math("SUBTRACT", sep.outputs["X"], cx)
        dy = N.math("SUBTRACT", sep.outputs["Y"], cy)
        d = N.math("SQRT", N.math("ADD", N.math("MULTIPLY", dx, dx), N.math("MULTIPLY", dy, dy)))
        g = N.math("SUBTRACT", 1.0, N.smooth(d, r, r * 1.95))
        f = g if f is None else N.math("MAXIMUM", f, g)
    return f


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


def rock_mat():
    """Roca de costa: la plataforma y el farellón donde se para la casa.

    Reemplaza a `sand_mat()` de Huingán y es el cambio de fondo del emplazamiento. Cuatro cosas
    la hacen leer como piedra y no como arena oscura:

    - **Estratos.** Bandas horizontales con la cota, dobladas por ruido. Es lo que primero delata
      una roca sedimentaria de costa.
    - **Franja mojada.** Bajo la cota de la marea la piedra está mojada: mucho más oscura y con
      la rugosidad por el piso, que es de donde sale el brillo de la rompiente.
    - **Encaje de espuma** en la línea de agua, roto por ruido, para que el agua no termine en un
      corte limpio contra la piedra.
    - **Líquenes** arriba, donde la roca está seca: manchones ocres y pálidos. Sin ellos la roca
      se ve de plastilina gris.

    Conserva los atributos `veg` y `camino` que usan la vegetación y el sendero."""
    m, n, l = new_mat("Roca")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    z = sep.outputs["Z"]
    dcosta = shore_d_nodes(N, sep)          # distancia tierra adentro desde la línea de agua
    grande = N.noise(tc.outputs["Object"], 0.09, 4)
    medio = N.noise(tc.outputs["Object"], 0.8, 6)
    fino = N.noise(tc.outputs["Object"], 7.0, 5)
    # estratos: bandas con la cota, onduladas por el ruido grande
    zb = N.math("ADD", z, N.math("MULTIPLY_ADD", grande, 5.0, -2.5))
    banda = n.new("ShaderNodeTexWave")
    banda.bands_direction = "Z"
    banda.inputs["Scale"].default_value = 0.55
    banda.inputs["Distortion"].default_value = 7.0
    banda.inputs["Detail"].default_value = 4.0
    mpb = n.new("ShaderNodeCombineXYZ")
    l.new(zb, mpb.inputs[2])
    l.new(mpb.outputs[0], banda.inputs["Vector"])
    seca = N.mix(N.math("MULTIPLY_ADD", grande, 1.7, -0.35), (0.062, 0.057, 0.048), (0.175, 0.152, 0.116))
    seca = N.mix(N.math("MULTIPLY", banda.outputs["Fac"], 0.26), seca, (0.12, 0.11, 0.105))
    seca = N.mix(N.math("MULTIPLY", medio, 0.35), seca, (0.155, 0.128, 0.092))
    # líquenes sólo en la roca alta y seca
    liq = N.math("MULTIPLY", N.smooth(z, SEA + 2.2, SEA + 4.0),
                 N.smooth(N.noise(tc.outputs["Object"], 1.6, 5, 0.7), 0.52, 0.68))
    seca = N.mix(N.math("MULTIPLY", liq, 0.6), seca, (0.33, 0.29, 0.14))
    liq2 = N.math("MULTIPLY", N.smooth(z, SEA + 2.6, SEA + 4.5),
                  N.smooth(N.noise(tc.outputs["Object"], 3.1, 4, 0.6), 0.60, 0.74))
    seca = N.mix(N.math("MULTIPLY", liq2, 0.45), seca, (0.42, 0.43, 0.38))
    # Grietas y facetas. Sin esto la piedra es un bulto liso con anillos de estrato, que de lejos
    # se lee como una curva de nivel y no como roca partida. La Voronoi de "distancia al borde" da
    # la red de grietas; la de F1, bloques con alturas distintas, que es lo que le pone caras
    # planas y aristas al volumen.
    # El vector de las Voronoi va **deformado por ruido**: sin eso las celdas salen parejas y la
    # roca se lee como enchape de piedra con junta de mortero (se probó y era exactamente eso).
    warp = n.new("ShaderNodeVectorMath")
    warp.operation = "ADD"
    wn = n.new("ShaderNodeTexNoise")
    wn.inputs["Scale"].default_value = 0.35
    wn.inputs["Detail"].default_value = 4.0
    l.new(tc.outputs["Object"], wn.inputs["Vector"])
    ws = n.new("ShaderNodeVectorMath")
    ws.operation = "SCALE"
    ws.inputs["Scale"].default_value = 2.2
    l.new(wn.outputs["Color"], ws.inputs[0])
    l.new(tc.outputs["Object"], warp.inputs[0])
    l.new(ws.outputs["Vector"], warp.inputs[1])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 0.45
    l.new(warp.outputs["Vector"], vor.inputs["Vector"])
    # Las grietas son sólo de la roca que trabaja la ola: tierra adentro, sobre la plataforma con
    # tierra y matorral, se leían como barro seco agrietado. Se apagan a 25 m de la línea de agua.
    cerca = N.math("SUBTRACT", 1.0, N.smooth(dcosta, 6.0, 25.0))
    grieta = N.smooth(vor.outputs["Distance"], 0.0, 0.022)       # 0 en la grieta, 1 fuera
    grieta = N.math("SUBTRACT", 1.0, N.math("MULTIPLY", N.math("SUBTRACT", 1.0, grieta), cerca)) 
    bloq = n.new("ShaderNodeTexVoronoi")
    bloq.feature = "F1"
    bloq.inputs["Scale"].default_value = 0.30
    bloq.inputs["Randomness"].default_value = 1.0
    l.new(warp.outputs["Vector"], bloq.inputs["Vector"])
    # cada bloque con su tono: la roca de una sola nota se lee como hormigón
    bw = n.new("ShaderNodeRGBToBW")
    l.new(bloq.outputs["Color"], bw.inputs[0])
    seca = N.mix(N.math("MULTIPLY_ADD", bw.outputs[0], 0.85, 0.05), seca, (0.185, 0.145, 0.092))
    seca = N.mix(N.math("MULTIPLY", N.math("SUBTRACT", 1.0, grieta), 0.35), seca, (0.030, 0.027, 0.024))
    # mojado bajo la cota de marea
    moja = N.math("SUBTRACT", 1.0, N.smooth(z, SEA + 0.5, SEA + 1.9))
    col = N.mix(moja, seca, (0.045, 0.045, 0.043))
    # encaje de espuma justo en la línea de agua
    enc = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", z, SEA + 0.25)), 0.15, 0.85)),
                 N.smooth(N.math("ADD", N.noise(tc.outputs["Object"], 2.2, 6, 0.7), N.math("MULTIPLY", fino, 0.4)), 0.46, 0.60))
    col = N.mix(N.math("MULTIPLY", enc, 0.85), col, (0.80, 0.82, 0.81))
    # bajo el agua la roca se apaga y se tiñe de verde
    bajo = N.math("SUBTRACT", 1.0, N.smooth(z, SEA - 3.0, SEA - 0.2))
    col = N.mix(N.math("MULTIPLY", bajo, 0.8), col, (0.015, 0.05, 0.045))
    # tierra y pasto donde hay vegetación, y el sendero pisado
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "veg"
    suelo = N.mix(N.smooth(N.noise(tc.outputs["Object"], 2.0, 5), 0.35, 0.6), (0.16, 0.14, 0.08), (0.08, 0.09, 0.05))
    col = N.mix(N.math("MULTIPLY", at.outputs["Fac"], 0.7), col, suelo)
    cm = n.new("ShaderNodeAttribute")
    cm.attribute_name = "camino"
    col = N.mix(N.math("MULTIPLY", cm.outputs["Fac"], 0.75), col, (0.24, 0.22, 0.19))
    # oclusión barata en las hendiduras: sin esto la roca no tiene sombra propia y se ve de yeso
    col = N.mix(N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(medio, 0.30, 0.62)), 0.45),
                col, (0.030, 0.026, 0.021))
    l.new(col, b.inputs["Base Color"])
    # la piedra mojada es lo único brillante de la escena en tierra
    rough = N.math("ADD", 0.92, N.math("MULTIPLY", moja, -0.70))
    rough = N.math("ADD", rough, N.math("MULTIPLY", enc, -0.1))
    l.new(rough, b.inputs["Roughness"])
    h = N.math("ADD", N.math("MULTIPLY", banda.outputs["Fac"], 0.25),
               N.math("ADD", N.math("MULTIPLY", medio, 0.6), N.math("MULTIPLY", fino, 0.25)))
    h = N.math("ADD", h, N.math("MULTIPLY", bloq.outputs["Distance"], 0.45))  # bloques con cara plana
    h = N.math("MULTIPLY", h, N.math("ADD", 0.70, N.math("MULTIPLY", grieta, 0.30)))
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.65
    bmp.inputs["Distance"].default_value = 0.11
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
    # + reflejo del cielo según Fresnel; el color del agua lo da el fondo (rock_mat)
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
    # Agua opaca a partir de ~4 m de hondo. Es la lección de Casa Boldo (RECETA.md §5) y acá no
    # es opcional: el farellón cae 0,45 m por metro, así que a diez metros de la orilla ya hay
    # cinco de agua. Con el agua transparente de Huingán —pensada para una playa de arena donde el
    # fondo se ve y tiñe el agua de turquesa— lo que se veía era la **roca sumergida**, y el mar
    # entero se leía como una explanada mojada en vez de como mar. Además saca la varianza del
    # Mix Shader entre transparente y reflejo, que a 32 muestras no la limpia el denoiser.
    hondo = n.new("ShaderNodeBsdfPrincipled")
    hondo.inputs["Base Color"].default_value = (0.006, 0.022, 0.030, 1)
    hondo.inputs["Roughness"].default_value = 0.055
    l.new(nrm, hondo.inputs["Normal"])
    mix_h = n.new("ShaderNodeMixShader")
    l.new(N.smooth(depth, 1.6, 4.5), mix_h.inputs["Fac"])
    l.new(wat.outputs[0], mix_h.inputs[1])
    l.new(hondo.outputs[0], mix_h.inputs[2])
    wat = mix_h
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
    # 4) rompiente contra la piedra: collar de espuma alrededor de cada afloramiento de ROCAS,
    # desflecado por las mismas vetas y el mismo grano que la espuma de orilla. Es la firma del
    # emplazamiento —"mar roca"— y lo que la espuma por profundidad no puede dar: con un fondo que
    # cae a 0,45 m por metro, la franja de agua baja mide dos metros y la ola reventaría contra
    # nada. Acá revienta donde está la piedra, porque el shader sabe dónde está.
    rk = rocas_nodes(N, sep)
    collar = N.math("MULTIPLY", N.smooth(rk, 0.30, 0.82),
                    N.smooth(N.math("ADD", streak, N.math("MULTIPLY", grain, 0.75)), 0.42, 0.78))
    surf = N.math("MAXIMUM", surf, collar)
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
        "roca": rock_mat(),
        "mar": water_mat(),
        "cerros": hills_mat(),
        "pastoDuna": dune_grass_mat(),
        "matorral": scrub_mat(),
        "pasarela": boards_mat("Pasarela", (0.38, 0.32, 0.25), (0.55, 0.48, 0.38), "X", 4.0, 0.75, 0.4),
    }
    return M


# ---------------------------------------------------------------- casa
def load_house(M):
    """Casa del STL con los materiales de la escena (por nombre de material del .blend)."""
    with bpy.data.libraries.load(CASA) as (a, b):
        b.objects = a.objects
    swap = {"Ma_ChapaNegra": M["chapa"], "Ma_MaderaFachada": M["fachada"], "Ma_MaderaCielo": M["cielo"],
            "Ma_Deck": M["deck"], "Ma_PisoInterior": M["piso"], "Ma_MuroInterior": M["muroint"],
            "Ma_Vidrio": M["vidrio"], "Ma_Pilote": M["hormigon"]}
    coll = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(coll)
    for o in b.objects:
        coll.objects.link(o)
        for sl in o.material_slots:
            if sl.material and sl.material.name in swap:
                sl.material = swap[sl.material.name]
    # Luces interiores tibias. Son ocho y no cuatro porque la casa es de dos pisos: cuatro en el
    # primero (living, comedor y los dos dormitorios de atrás) y cuatro en el segundo. La del
    # living va alta, en el vacío de doble altura, que es lo que se ve desde el mar.
    for x, y, z, p in ((5.2, 5.2, 5.6, 200), (11.0, 5.2, 3.2, 110), (4.6, 8.8, 3.2, 80),
                       (11.8, 8.8, 3.2, 80), (4.6, 8.8, 5.9, 80), (8.4, 8.6, 5.9, 70),
                       (11.8, 6.4, 5.9, 80), (2.0, 5.0, 2.6, 50)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.0
        lt.data.color = (1.0, 0.72, 0.45)
    return coll


def build_boardwalk(M):
    """Pasarela de tablas que baja de la terraza a la roca, entre los dos afloramientos grandes.

    En Huingán era una pasarela recta sobre la duna; acá sigue el eje de `path_x` y, como la roca
    cae fuerte, va de escalones: donde el terreno baja más de 9 cm entre tabla y tabla, la tabla
    se queda a nivel y el desnivel se resuelve con la contrahuella. Sin eso la pasarela se hunde
    en la piedra en los tramos empinados."""
    coll = bpy.data.collections.new("Pasarela")
    bpy.context.scene.collection.children.link(coll)
    y = -0.6
    i = 0
    z = terrain_h(path_x(y), y) + 0.14
    while y > -15.0:
        cx = path_x(y)
        zt = terrain_h(cx, y) + 0.14
        if zt < z - 0.09:                       # escalón: la tabla se mantiene, baja la siguiente
            z = max(zt, z - 0.17)
            box(f"Contra{i}", cx - 0.75, cx + 0.75, y - 0.04, y, z, z + 0.17, M["pasarela"], coll)
        else:
            z = zt if zt > z else z
        box(f"Tabla{i}", cx - 0.75, cx + 0.75, y - 0.15, y, z, z + 0.04, M["pasarela"], coll)
        if i % 7 == 0:
            zs = terrain_h(cx, y)
            for xp in (cx - 0.72, cx + 0.65):
                box(f"Poste{i}", xp, xp + 0.07, y - 0.12, y - 0.05, zs - 0.4, z, M["pasarela"], coll)
        y -= 0.175
        i += 1
    return coll


# ---------------------------------------------------------------- terreno
def house_dist(x, y):
    """Distancia (m) al rectángulo de la casa (con un margen de 0,6 m)."""
    dx = max(-0.6 - x, 0, x - (L + 0.6))
    dy = max(-0.6 - y, 0, y - (D + 0.6))
    return math.hypot(dx, dy)


FORE = 0.45      # pendiente del farellón: sigue cayendo bajo el agua, no es una playa tendida
BEACH = 4.0      # ancho de la franja de rompiente sobre la línea de agua (m)
SLOPE_W = 7.0    # 7 m de la línea de agua a la plataforma: 45°, un farellón de verdad


def terrain_base(x, y):
    """Perfil sin accidentes: el farellón cae del borde de la plataforma al agua y sigue bajando.

    Nada que ver con el de Huingán, que era fondo marino < playa < ladera de duna < meseta: acá no
    hay playa. La plataforma de roca llega hasta el borde y de ahí baja de golpe."""
    d = shore_d(x, y)
    if d < 0:
        return SEA + max(d * FORE, -11.0)          # bajo el agua
    t = min(1.0, d / SLOPE_W)
    t = t * t * (3 - 2 * t)
    return SEA + t * (GROUND - SEA)


def path_x(y):
    """Eje de la escalera y el sendero que bajan de la terraza a la roca, entre los dos
    afloramientos grandes (los de x = 2,0 y x = 10,5)."""
    return 6.3 + 1.6 * math.sin(y / 7.0)


def path_dist(x, y):
    """Distancia (m) al eje del sendero; lejos en la plataforma detrás de la terraza."""
    if y > -0.6:
        return math.hypot(x - path_x(-0.6), y + 0.6)
    return abs(x - path_x(y))


def terrain_h(x, y):
    h = terrain_base(x, y)
    d = shore_d(x, y)
    pd = path_dist(x, y)
    flat = min(1.0, max(0.0, (house_dist(x, y) - 1.0) / 7.0))
    flat = min(flat, 0.3 + 0.7 * min(1.0, max(0.0, (pd - 1.2) / 4.0)))     # el sendero corta la roca
    if 1.5 < y < 140:
        flat = min(flat, 0.2 + 0.8 * min(1.0, max(0.0, (road_dist(x, y) - 2.5) / 6.0)))   # y el camino
    # Relieve de roca: dos escalas de ruido y, encima, **escalones**. Los escalones son lo que
    # separa una costa de roca de una duna: sin ellos la misma malla con otro color se sigue
    # leyendo como arena. Se aplican cerca del agua y se apagan hacia la plataforma de la casa.
    gr = (noise.noise(Vector((x / 14.0, y / 11.0, 2.3))) + 0.55 * noise.noise(Vector((x / 4.2, y / 3.6, 6.1)))
          + 0.30 * noise.noise(Vector((x / 1.5, y / 1.4, 8.8))))
    # Ruido "ridged" (1 - |n|): deja **aristas y lomos**, no bultos. El ruido normal da colinas
    # redondas, que es lo que hacía que la roca se leyera como duna gris.
    ridge = (1.0 - abs(noise.noise(Vector((x / 7.0, y / 6.0, 11.0))))
             + 0.6 * (1.0 - abs(noise.noise(Vector((x / 2.6, y / 2.3, 13.0)))))
             + 0.35 * (1.0 - abs(noise.noise(Vector((x / 1.05, y / 0.95, 17.0))))))
    h += flat * (1.15 * gr + 0.95 * (ridge - 1.0))
    esc = min(1.0, max(0.0, (18.0 - d) / 16.0)) * flat
    if esc > 0.01:
        paso = 1.15
        quant = paso * math.floor(h / paso + 0.45)
        h += (quant - h) * 0.33 * esc
    rh = rocas_h(x, y)
    if rh > h:                                     # los afloramientos mandan donde los hay
        h = rh + (0.55 * noise.noise(Vector((x / 2.2, y / 2.2, 3.3)))
                  + 0.30 * (1.0 - abs(noise.noise(Vector((x / 0.95, y / 0.9, 5.9)))) - 0.5)
                  + 0.16 * noise.noise(Vector((x / 0.42, y / 0.40, 7.4))))
    if d > BEACH:                                  # huella del sendero, apenas hundida
        h -= 0.07 * max(0.0, 1.0 - pd / 1.1)
    # cerros costeros al fondo, tierra adentro
    if y > 280:
        r = min(1.0, (y - 280) / 300.0)
        hn = 0.5 + 0.5 * noise.noise(Vector((x / 180.0, y / 140.0, 3.1)))
        h += r * r * (30 + 90 * hn) * min(1.0, max(0.0, (d - 40.0) / 160.0))
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
    md.wave_scale = 0.80          # mar más movido que la playa de Huingán: acá la ola revienta
    md.wind_velocity = 11.0
    md.choppiness = 1.0
    md.wave_alignment = 0.55
    md.wave_direction = math.radians(90.0)   # avanzan hacia la costa (+Y)
    md.damping = 0.3
    md.use_normals = True
    md.use_foam = True
    md.foam_coverage = 0.20
    md.foam_layer_name = "espuma"
    md.time = float(opts.get("t_mar", "3.0"))
    # el modificador genera la malla desde (-tile/2, -tile/2) hacia +X/+Y
    o.location = (OCEAN_X + OCEAN_TILE / 2, OCEAN_Y + OCEAN_TILE / 2, SEA)
    o.data.materials.append(M["mar"])
    fade_ocean_edges(o)
    x0, y0 = OCEAN_X, OCEAN_Y
    x1, y1 = x0 + OCEAN_TILE * OCEAN_REP, y0 + OCEAN_TILE * OCEAN_REP
    R = 400000   # hasta más allá del horizonte (si no, queda una línea del cielo bajo el horizonte)
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
    # Tres mallas y no dos. La del medio, a 0,25 m, cubre sólo la roca de la rompiente: con los
    # 0,6 m de la malla cercana el relieve de escala corta —el que le da aristas a la piedra— no
    # llegaba a existir en la silueta y la roca se leía como arcilla lisa con las grietas pintadas
    # encima. Es la zona por la que además pasa más cerca el dron.
    fina = (-46, 63, -35, 7)
    near = (-175, 128, -78, 95)
    en_fina = lambda x, y: fina[0] < x < fina[1] and fina[2] < y < fina[3]   # noqa: E731
    sand = grid("Roca", *near, 0.6, M["roca"], coll, skip=en_fina, sink=en_fina)
    grid("RocaFina", *fina, 0.25, M["roca"], coll)
    # lejos: playa y dunas hacia los costados + cerros (sin el hueco del terreno cercano)
    inside = lambda x, y: near[0] < x < near[1] and near[2] < y < near[3]  # noqa: E731
    far = grid("Lejos", -2100, 2100, -600, 2700, 15.0, M["roca"], coll, skip=inside, sink=inside)
    far.data.materials.append(M["cerros"])
    for p in far.data.polygons:
        if shore_d(p.center.x, p.center.y) > BEACH + 18:
            p.material_index = 1
    fondo = principled("FondoMar", (0.006, 0.03, 0.04), 0.9)
    # más hondo que en Huingán: con el farellón cayendo a 0,45 m por metro el lecho llega a
    # SEA - 11, y a SEA - 6,5 el plano del fondo asomaba por encima del terreno sumergido
    mesh_obj("FondoMar", [(-40000, -40000, SEA - 12.0), (40000, -40000, SEA - 12.0), (40000, 40000, SEA - 12.0), (-40000, 40000, SEA - 12.0)],
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
    """Bolones sobre los afloramientos y en la rompiente, y dos formaciones de costa a lo lejos.

    ⚠️ `coast_rocks_01` **no es una roca suelta**: es una formación de 60 x 42 m. Usarla como
    detalle alrededor de cada afloramiento (24 copias a escala 1,7) tapó el mar entero y la escena
    se leía como una explanada de piedra. Va sólo dos veces, lejos y a los costados, igual que en
    Huingán. El detalle cercano lo pone `namaqualand_boulder_02`, que mide 2,5 x 1,2 x 0,9 m."""
    coll = bpy.data.collections.new("Rocas")
    bpy.context.scene.collection.children.link(coll)
    bo = load_ph(coll_lib, "namaqualand_boulder_02", "LOD1")
    rnd = random.Random(11)
    for cx, cy, r, _alto in ROCAS:
        for _ in range(3):
            a = rnd.uniform(0, 6.28)
            rad = r * rnd.uniform(0.55, 1.25)
            x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
            o = bo.objects[0].copy()
            coll.objects.link(o)
            o.location = (x, y, terrain_h(x, y) - rnd.uniform(0.35, 0.9))
            o.rotation_euler = (rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), rnd.uniform(0, 6.28))
            sc = rnd.uniform(0.5, 1.2)
            o.scale = (sc, sc, sc * rnd.uniform(0.7, 1.3))
    # bloques sueltos sobre la plataforma, al costado del acceso y del anexo
    for x, y, sc in ((-7.5, 15.0, 1.4), (23.5, 17.0, 1.0), (-13.0, 6.0, 1.1), (29.0, 7.0, 1.2)):
        o = bo.objects[0].copy()
        coll.objects.link(o)
        o.location = (x, y, terrain_h(x, y) - 0.35)
        o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
        o.scale = (sc, sc, sc)
    # `coast_rocks_01` es una **plataforma de abrasión escaneada** de 60 x 42 x 3,3 m: no sirve de
    # roca suelta, pero es exactamente lo que hay al pie de un farellón, con el detalle y el color
    # que la roca procedural no da. Va en la línea de agua, delante del farellón, que es donde
    # revienta la ola y donde la cámara pasa más cerca; y dos más lejos, cerrando la costa.
    rk = load_ph(coll_lib, "coast_rocks_01", "LOD2")
    for x, rot, sc, dy in ((-28.0, 0.4, 0.50, -5.0), (12.0, 2.9, 0.46, -6.0), (52.0, 1.5, 0.52, -4.0),
                           (-125.0, 0.5, 0.55, -4.0), (150.0, 2.3, 0.45, -4.0)):
        o = rk.objects[0].copy()
        coll.objects.link(o)
        o.location = (x, shore_y(x) + dy, SEA + 0.25)
        o.rotation_euler = (0, 0, rot)
        o.scale = (sc, sc, sc * 1.15)
    tr = load_ph(coll_lib, "dead_tree_trunk")
    for x, y, rot in ((-14.0, 4.0, 0.7), (27.0, 3.0, 2.4)):
        o = tr.objects[0].copy()
        coll.objects.link(o)
        o.location = (x, y, terrain_h(x, y) + 0.05)
        o.rotation_euler = (0, 0, rot)


def build_vegetation(sand, bq, ph):
    """Pastos de duna y arbustos con nodos de geometría sobre el terreno cercano, según un
    atributo 'veg' (0 en la playa, la pasarela y bajo la casa; 1 en la duna)."""
    me = sand.data
    nrm = me.vertex_normals
    veg, cam = [], []
    for i, v in enumerate(me.vertices):
        x, y = v.co.x, v.co.y
        d = shore_d(x, y)
        w = min(1.0, max(0.0, (d - BEACH - 1.5) / 5.0))
        w *= min(1.0, max(0.0, (house_dist(x, y) - 0.2) / 1.5))
        # En la roca no crece nada en cualquier parte: sólo en las repisas donde se junta tierra.
        # Dos condiciones, y son las que separan una costa de piedra de una duna repintada de
        # gris: cero sobre los afloramientos, y cero donde la pendiente pasa de ~30°.
        if rocas_h(x, y) > terrain_base(x, y) + 0.1:
            w = 0.0
        nz = max(0.05, nrm[i].vector.z)
        pend = math.sqrt(max(0.0, 1.0 - nz * nz)) / nz
        w *= min(1.0, max(0.0, (0.62 - pend) / 0.40))
        # sendero desde la escalera de la terraza hasta la roca
        pd = path_dist(x, y)
        w *= min(1.0, max(0.0, (pd - 0.9) / 1.3))
        if 2 < y < 95:
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
    scatter(bq["Grass_Tall_A"], 8.0, 1.2, 2.1, 21, 0.38, 0.62)
    scatter(bq["Grass_Karl-foerster_B"], 1.6, 0.7, 1.1, 24, 0.38, 0.6, 0.25)
    scatter(ph["flor"], 0.4, 0.8, 1.2, 27, 0.5, 0.62, 0.2)
    # matorral costero: arbustos agrupados
    scatter(ph["searsia"], 0.16, 0.9, 1.6, 31, 0.38, 0.58, 0.06, 0.06)
    scatter(ph["didelta"], 0.06, 0.6, 1.1, 32, 0.42, 0.6, 0.05, 0.05)
    scatter(ph["othonna"], 0.35, 1.0, 1.6, 34, 0.38, 0.6, 0.1, 0.06)
    scatter(ph["rooibos"], 0.45, 1.5, 2.4, 35, 0.38, 0.6, 0.1, 0.06)
    # rastreras tipo doca (alfombras) y suculentas en los bordes con arena
    scatter(ph["doca"], 7.0, 1.6, 2.8, 36, 0.46, 0.58, 0.1, 0.02)
    scatter(ph["cheiri"], 0.8, 0.9, 1.4, 37, 0.42, 0.62, 0.15, 0.03)
    scatter(ph["roca"], 0.004, 0.4, 1.0, 40, 0.55, 0.62, 0.05, 0.4)
    Lk.new(join.outputs[0], go.inputs[0])
    md = sand.modifiers.new("Duna", "NODES")
    md.node_group = ng



# ---------------------------------------------------------------- contexto: camino, vecinos, árboles
# camino de tierra que llega por detrás de la casa (porch de acceso) y sube hacia los cerros
# El camino llega al **porch, que está en -X**: en Maitén el acceso es lateral, no por un testero
# como en Huingán y Boldo. Así que el camino baja de tierra adentro, rodea la casa por el costado
# del porch y termina en la explanada de la izquierda, sin cruzar nunca el frente al mar.
ROAD = [(-5.5, 5.0), (-11.0, 12.0), (-12.5, 26.0), (-3.0, 48.0), (9.0, 78.0), (0.0, 120.0),
        (-40.0, 175.0), (-95.0, 250.0), (-140.0, 340.0), (-200.0, 450.0), (-260.0, 620.0),
        (-300.0, 800.0)]


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
    if y < 1.5 or y > 140:
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
        lift = 0.05 if p.y < 85 else 0.35        # sobre el terreno lejano (malla gruesa) va más alto
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

    # bruma = 0,62 · (1 − e^(−(z − 60) / 900)), sobre todo lo que no es cielo (z < 10 km de cámara
    # para el cielo no hay superficie: su profundidad es enorme). Crece sin corte hasta el horizonte.
    sc.view_layers[0].use_pass_z = True
    zrel = mnode("SUBTRACT", 60.0)
    pos = mnode("MAXIMUM", 0.0)
    sc_ = mnode("DIVIDE", -900.0)
    ex = mnode("EXPONENT", 0.0)
    one = mnode("SUBTRACT", 1.0)
    sky = mnode("LESS_THAN", 1.0e7)
    mul = mnode("MULTIPLY", 1.0)
    amt = mnode("MULTIPLY", 0.62)
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
    # + una bruma de lejanía que funde el mar con el cielo en el horizonte: 0,33 · (1 − e^(−z / 6000))
    far_s = mnode("DIVIDE", -6000.0)
    far_e = mnode("EXPONENT", 0.0)
    far_1 = mnode("SUBTRACT", 1.0)
    far_1.inputs[0].default_value = 1.0
    far_a = mnode("MULTIPLY", 0.33)
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


# Tomas fijas de dron, abiertas a propósito para poder reencuadrar en la edición. Van **más bajas
# que en Huingán** (11-15 m contra 16-17) y mirando algo hacia arriba: Maitén mide 8,10 m y el
# enganche es la altura, que desde un dron alto se pierde (ENGANCHES.md, "si es la altura").
VISTAS = {
    "izq": ((-26.0, -46.0, 2.5), (5.0, 3.0, 4.6), 30),        # desde el agua, por el lado del porch
    "der": ((40.0, -44.0, 3.0), (11.0, 3.0, 4.6), 30),        # desde el agua, por el lado del anexo
    # opuestas: desde el acceso (el porch está en -X) y desde tierra adentro, con el mar detrás
    "izq_atras": ((-44.0, 28.0, 9.0), (6.0, 4.0, 3.6), 30),
    "der_atras": ((44.0, 40.0, 11.0), (10.0, 5.0, 3.6), 30),
    # las mismas dos del agua pero **más cerca y algo más altas** (pedido de la revisión): a 31 m
    # la casa ocupa ~0,85 del ancho de pantalla, y a 8 m la cámara pasa de mirar hacia arriba a
    # quedar apenas por encima del punto de mira, sin perder el farellón del primer plano
    "izq_cerca": ((-11.6, -23.2, 8.0), (6.0, 3.5, 4.4), 30),
    "der_cerca": ((27.3, -23.5, 8.5), (10.5, 3.5, 4.4), 30),
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
CASA_BOX = (0.0, L, -1.2, D + 0.8, GROUND, 8.2)      # caja de la casa (con escaleras) para encuadrar
CASA_C = Vector((L / 2, D / 2, 3.4))                 # punto al que mira el dron: a media altura
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


# El arco del dron va espejado respecto de Huingán y Boldo, y no es un capricho: el acceso de
# Maitén está en **-X** (el porch), así que el recorrido tiene que terminar de ese lado. Rodea por
# +X → frente al mar → -X, y por eso todos los azimuts de RUTA son negativos después del frente.
S1_AZ = (118.0, 42.0)        # azimut (0 = de frente, la cámara hacia -Y = el mar)
S1_EL = (26.0, 11.0)         # elevación (°): termina bajo, mirando hacia arriba (casa de 8,10 m)
S1_D0 = 190.0                # distancia inicial (m)


def pose_s1(f, n):
    """Aproximación en espiral: el giro avanza parejo y la distancia cae en escala logarítmica con
    salida suave (el dron frena al llegar). El punto de mira pasa de la playa a la casa."""
    u = f / (n - 1)
    ua = u * u * (3 - 2 * u)
    az = math.radians(S1_AZ[0] + (S1_AZ[1] - S1_AZ[0]) * ua)
    el = math.radians(S1_EL[0] + (S1_EL[1] - S1_EL[0]) * ua)
    direc = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    ud = 1 - (1 - u) ** 2.2                          # rápido al comienzo, frena al final
    tgt = Vector((L / 2, -16.0, -0.5)).lerp(CASA_C, smootherstep(min(1.0, u * 1.25)))
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
# Altura del corte. CUT_TOP va sobre la cumbrera (7,82) y CUT_LOW a media altura del primer piso
# (piso terminado 1,10), que es donde se lee su planta en 3D. El barrido entre los dos cruza el
# segundo piso, y ahí van las pausas (ver PAUSA_* más abajo).
CUT_TOP, CUT_LOW = 8.6, 2.3
# claves: (cuadro global, azimut°, elevación°, distancia, altura de corte, parar)
#   distancia: número (m) o ("fit", factor): la del encuadre adaptable en esa dirección
#   parar=True: la cámara llega quieta a esa clave (fin de s3, antes del paso a la planta)
RUTA = [
    (0, S1_AZ[1], S1_EL[1], ("fit", 1.0), CUT_TOP, True),     # = último cuadro de s1
    (90, -5.0, 13.0, ("frente", 1.0), CUT_TOP, False),        # de frente al testero vidriado, bajo
    (192, -68.0, 14.0, ("frente", 1.0), CUT_TOP, False),      # fin s2: costado del porch
    (262, -80.0, 42.0, ("fit", 1.05), CUT_TOP, False),
    (352, -88.0, 78.0, ("fit", 1.0), CUT_LOW, False),
    (432, -90.0, 89.5, ("fit", 1.0), CUT_LOW, True),          # fin s3: cenital, casa a lo largo de la pantalla
    (500, -118.0, 55.0, ("fit", 1.15), CUT_TOP, False),
    (624, -152.0, 16.0, ("fit", 1.0), CUT_TOP, True),         # fin s5: el porch de acceso y el camino
]
# El corte llega a CUT_LOW en el cuadro de ruta 356 y no en 370 (que es lo que heredaba de
# Huingán): con 370 el primer piso quedaba abierto 2,92 s contando el HOLD0 de la sección 4, bajo
# los 3 s que pide RECETA.md §1. Medido con tools/medir_pausas.py.
CUT_KEYS = [(0, CUT_TOP), (250, CUT_TOP), (356, CUT_LOW), (432, CUT_LOW), (460, CUT_LOW), (540, CUT_TOP), (624, CUT_TOP)]


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
    frente = max(fit_distance(_dir(a, 14.0), CASA_C, lens, w / h) for a in range(-75, 45, 5))
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


def apply_section(frames, g0, corte=None):
    """Corte animado de la casa: shader en sus materiales (no en el paisaje) y, en las piezas, se
    borran con nodos de geometría las caras enteras sobre el corte (no se apilan transparencias)."""
    house = list(bpy.data.collections["Casa"].objects)
    groups = section_groups()
    capped = {"ChapaNegra", "MaderaFachada", "MaderaCielo", "MuroInterior", "Ma_MarcoNegro", "Ma_PuertaMadera"}
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
        if o.type == "MESH" and o.name != "Maiten_Casco":
            o.modifiers.new("Corte", "NODES").node_group = ng
    socks = [zval.outputs[0]] + [g.nodes["AlturaCorte"].outputs[0] for g in groups.values()]
    for f in range(frames):
        for sk in socks:
            sk.default_value = cut_z(corte[f] if corte else g0 + f)
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


# --- Pausas del barrido del corte, dentro de s3 ------------------------------------------------
# Maitén es de dos pisos, así que RECETA.md §1 pide que el barrido **pause en cada piso**, uno por
# uno, tres segundos, para poder rotularlos con flechas en edición. Lo que se detiene es el corte,
# no la cámara: el dron sigue volando (congelar un cuadro se probó en Boldo y el usuario lo
# rechazó). En cada pausa el corte se queda quieto a la altura donde ese piso se ve entero, la
# cámara sigue más lenta, y al terminar el corte retoma tantos cuadros de ruta más atrás como
# avanzó la cámara mientras tanto; con dos pausas ese desfase **se acumula**.
#
# El mecanismo es el de Boldo generalizado a una lista, pero **medido** con tools/medir_pausas.py,
# que es lo que RECETA.md §1 manda hacer antes de agregar una pausa. Lo que midió en Maitén:
#
#   - 2do piso: el corte lo deja limpio (z entre 3,95 y 4,85 — el techo arranca en 4,90 y la losa
#     del segundo está en 3,85) durante **11 cuadros, 0,46 s**. Va pausa explícita, en el 124, que
#     es el medio de esa ventana. Con la pausa pasa a 3,67 s.
#   - 1er piso: **sale solo**, igual que en Boldo. El corte satura en CUT_LOW en el cuadro 251 de
#     312 y se queda ahí 2,58 s, más 1 s de HOLD0 al abrir la sección 4 = **3,58 s** con el primer
#     piso abierto y limpio, por encima de los 3 s que pide la receta. Por eso Maitén cumple la
#     regla de "una pausa por piso" con una sola pausa programada.
#
# s3p dura entonces 312 cuadros (13 s) y la secuencia completa 1200 (50 s), como Boldo.
#
#   (cuadro de s3p donde se para el corte, cuántos cuadros dura)
PAUSAS = [(124, 72)]
PAUSA_FRENO = 18      # cuadros de frenada y de aceleración de la cámara
PAUSA_V = 0.35        # velocidad de la cámara durante la pausa, fracción de la de s3


def _vel_pausa(v2, n):
    """Velocidad de la cámara cuadro a cuadro de s3 con pausas (1,0 = la de s3), suavizada.

    Antes de la primera pausa va a 1,0 —así esos cuadros son idénticos a los de s3 y se
    reaprovechan— y después de cada pausa a v2, que es la única incógnita de la bisección."""
    ks = [(1, 1.0)]
    v_prev = 1.0
    for d, m in PAUSAS:
        ks += [(d, v_prev), (d + PAUSA_FRENO, PAUSA_V),
               (d + m, PAUSA_V), (d + m + PAUSA_FRENO, v2)]
        v_prev = v2
    ks.append((n, v2))
    out = []
    for f in range(1, n + 1):
        i = min(max(j for j in range(len(ks) - 1) if ks[j][0] <= f), len(ks) - 2)
        (f0, a), (f1, b) = ks[i], ks[i + 1]
        t = min(max((f - f0) / max(f1 - f0, 1), 0.0), 1.0)
        out.append(a + (b - a) * t * t * (3 - 2 * t))
    return out


def pausa_mapas():
    """Posición en la ruta de la cámara y del corte, cuadro a cuadro de s3 con las pausas.

    La cámara recorre lo mismo que s3 (de INICIO["s3"] al cenital) pero en más cuadros: la
    velocidad de crucero posterior a las pausas se despeja por **bisección** para que el recorrido
    cierre justo en el cenital, así el último cuadro es el mismo que el de s3 y la sección 4 —que
    se arma sobre él— no cambia."""
    n = SECCIONES["s3"] + sum(m for _, m in PAUSAS)
    g0, g1 = INICIO["s3"], INICIO["s3"] + SECCIONES["s3"]
    lo, hi, cam = 0.05, 1.0, None
    for _ in range(60):
        v2 = (lo + hi) / 2
        cam = [float(g0)]
        for v in _vel_pausa(v2, n)[1:]:
            cam.append(cam[-1] + v)
        if cam[-1] < g1:
            lo = v2
        else:
            hi = v2
    corte, desfase = [], 0.0
    for f, g in enumerate(cam):
        fr = f + 1
        act = next(((d, m) for d, m in PAUSAS if d <= fr < d + m), None)
        if act is not None:
            corte.append(cam[act[0] - 1] - desfase)       # el corte, quieto
        else:
            corte.append(g - desfase)
        if act is None and any(fr == d + m for d, m in PAUSAS):
            d, m = next((d, m) for d, m in PAUSAS if fr == d + m)
            desfase += cam[d + m - 1] - cam[d - 1]         # lo que avanzó la cámara en la pausa
    return cam, corte


def build_drone(cam):
    """Anima la cámara cuadro a cuadro según la sección pedida y el oleaje en el tiempo."""
    sc = bpy.context.scene
    tramo = opts["tramo"]
    pausa = tramo == "s3p"              # s3 con las pausas del barrido sobre cada piso
    base = "s3" if pausa else tramo
    cam_g, corte_g = pausa_mapas() if pausa else (None, None)
    n = SECCIONES[base] + (sum(m for _, m in PAUSAS) if pausa else 0)
    sc.frame_start, sc.frame_end = 1, n
    sc.frame_step = int(opts.get("step", "1"))   # >1 para previsualizaciones rápidas
    w, h = (int(v) for v in opts["res"].split("x"))
    lens = 30.0
    cam.data.lens = lens
    if base in SETUP:
        SETUP[base](w, h, lens)
    for f in range(n):
        pose = ruta_pose(cam_g[f]) if pausa else POSES[base](f, n)
        direc, tgt = pose[0], pose[1]
        dist = pose[2] if len(pose) > 2 else fit_distance(direc, tgt, lens, w / h)
        cam.location = tgt + direc * dist
        cam.rotation_euler = (-direc).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=f + 1)
        cam.keyframe_insert("rotation_euler", frame=f + 1)
    # oleaje: el tiempo del océano avanza con el video (cada sección sigue donde quedó la anterior)
    md = bpy.data.objects["MarOleaje"].modifiers["Oleaje"]
    t0 = float(opts.get("t_mar", "3.0")) + sum(SECCIONES[k] for k in sorted(SECCIONES) if k < base) / FPS
    for f, t in ((1, t0), (n, t0 + (n - 1) / FPS)):
        md.time = t
        md.keyframe_insert("time", frame=f)
    for fc in list(cam.animation_data.action.fcurves if hasattr(cam.animation_data.action, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    act = bpy.data.objects["MarOleaje"].animation_data.action
    for fc in getattr(act, "fcurves", []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    if base in ("s3", "s5"):
        apply_section(n, INICIO[base], corte_g)
    if base == "s3":   # dónde cae la casa en la cenital final: para calzar la planta (tools/plano_maiten.py)
        import json
        from bpy_extras.object_utils import world_to_camera_view
        direc, tgt, dist = ruta_pose(cam_g[-1] if pausa else INICIO["s3"] + n - 1)
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
    sand = build_landscape(M)
    bq, ph = load_assets(M)
    build_vegetation(sand, bq, ph)
    place_props(bpy.data.collections["Biblioteca"])
    build_context(M)
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
