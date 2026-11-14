"""Escena 3D de Casa Mañío en una playa urbanizada (Blender 5.x, Cycles).

Uso:
  python casa_manio_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  (vistas: izq / der = tomas fijas de dron desde el mar, a cada lado del frente;
   izq_atras / der_atras = desde la costanera mirando al mar)
  python casa_manio_3d.py -- --vista dron --tramo s1 --out frames_manio/s1/f_ [--cuadro 80]
  (recorrido de dron por secciones, ver SECCIONES; --cuadro N renderiza sólo ese cuadro)

La casa sale del modelo STL de Neorigen (assets/manio/casa.blend, generado con
tools/extraer_manio_stl.py): 16,02 m de ancho por 11,15 de fondo, terraza corrida de 2,95 m hacia
-Y (el mar), porch de acceso hacia +Y, piso terminado en z = 0,53 y terreno en z = -0,12. El techo
**no es de una agua**: son dos faldones de 12° y 18° con la cumbrera corrida a x = 9,55.

Enganche (ENGANCHES.md): *se abre entera al frente*. No es una ventana al mar, es toda la fachada
vidriada y corrida con la terraza siguiéndola de punta a punta, y es la más baja del conjunto
(5,07 m): en una playa ya urbanizada ese perfil bajo es privacidad. Por eso el arco frontal del
dron va más abierto y más bajo que en Huingán, para que la casa cruce la pantalla a lo ancho.

Paisaje: **condominio de costa estilo Maitencillo**, no playa salvaje ni calle de ciudad. Se
heredan de casa_huingan_3d.py el mar con oleaje y espuma y la arena; lo que cambia es todo lo de
tierra adentro:
  - la duna salvaje deja lugar a un terreno aterrazado y plano, con **muro de contención** de
    hormigón sobre la playa y una escalera pública que baja a la arena;
  - en vez del camino de tierra hay un **camino angosto de asfalto** (4,6 m) con bermas de
    maicillo, sin solera ni vereda, a 42 m del frente de la casa;
  - los **vecinos están cerca pero son todos distintos**: dos predios contiguos puestos a mano y
    el resto sembrado irregular entre los pinos, con tamaño, giro, retranqueo, pendiente de techo
    y color variables;
  - la vegetación es **domesticada**: césped recortado en los antejardines, setos de deslinde,
    cierro de listones de madera hacia el camino, grupos irregulares de pinos y cipreses, algún
    ornamental de hoja ancha y maceteros en la terraza. El matorral costero silvestre queda sólo
    en los sitios baldíos y del muro hacia la playa.

⚠️ **Lo que pidió la revisión (Maca, 12-11) y por qué el script quedó así.** La primera versión
era una costanera urbana y se leyó mal; los cambios no son de gusto, son de lectura:
  - **Sin alumbrado público ni postes con tendido.** Eran la firma más fuerte de "calle de
    ciudad" y además hoy el cableado va bajo tierra. Se borró `build_alumbrado()` entero.
  - **El camino, angosto y lejos.** Era de 7,2 m con soleras y dos veredas de hormigón, a 25 m de
    la casa: "calle grande de cemento". Ahora `CALLE_W` es 2,30 (4,6 m de calzada), no hay solera
    ni vereda —bermas de maicillo— y `CALLE_Y` pasó de 25 a 42.
  - **Vecinos todos distintos.** Venían en filas regulares a distancias fijas de la orilla, con
    el mismo volumen y los mismos tres colores. Ver el comentario sobre `VECINOS`.
  - **La casa manda.** La vista `calle` tenía el camino ocupando media pantalla; todas las vistas
    se acercaron, y `calle` pasó de factor 1,45 a 1,32 con la cámara más alta.
  - **Nada de luz de noche a pleno día.** Las luces interiores bajaron a un quinto: son relleno
    para que el interior no sea una caja negra detrás del vidrio, no iluminación nocturna.
  - **Cierro de madera, no pandereta.** En un condominio de costa el deslinde a la calle es
    madera o vegetación, nunca un muro de bloques con pilares.
Recursos CC0 de Poly Haven: tools/get_assets_playa.sh (mar, arena, matorral, rocas) y
tools/get_assets_urbano.sh (alumbrado, postes, jacarandá, arbustos de jardín, maceteros, asfalto).
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
CASA = os.path.join(ROOT, "assets", "manio", "casa.blend")
CAMPO = os.path.join(ROOT, "assets", "campo", "pastos_botaniq.blend")
PH = os.path.join(ROOT, "assets", "playa", "ph")   # Poly Haven (get_assets_playa.sh + get_assets_urbano.sh)
HDRI = os.path.join(PH, "hdri", "secluded_beach_2k.exr")   # tarde de verano en la costa, CC0
HDRI_SUN_U = 0.6420          # columna del sol en el HDRI (0-1), medida con tools/medir_sol_hdri.py
SUN_ELEV = 32.0              # elevación del sol en el HDRI (más alto que en Huingán: es verano)
SKY_GAIN = 0.06              # brillo del cielo físico (horizonte) para empatar con el HDRI
SUN_AZ = 208.0               # sol desde adelante-izquierda (azimut desde +Y hacia +X)
WB_TEMP = float(opts["wb"])
L, D = 16.02, 11.15          # ancho y fondo total del casco (terraza + caja + porch)
HC = Vector((L / 2, 5.6))    # centro de la casa en planta
GROUND = -0.12               # terreno bajo la casa (la más baja de las nueve: se tiende en el sitio)
SEA = -2.80                  # nivel del mar: el predio queda ~1,9 m sobre la arena, no en una meseta
SHORE_Y = -48.0              # orilla frente a la casa
SHORE_K = 2600.0             # bahía larga y tendida (en Huingán era una punta: K = 420)
XC = 8.0
# ---- el loteo (lo que hace "urbanizada" a esta playa)
LOTE = (-11.0, 27.0)         # deslindes del predio en x; el vecino empieza ahí mismo
# La playa de un balneario es **ancha**: 32 m de arena entre el agua y el muro, contra los 13 de
# la duna de Huingán. No es un detalle de paisaje: con la playa angosta la cámara del encuadre
# adaptable se planta justo sobre el muro y el mar queda detrás de ella en todas las tomas.
MURO_D = 25.0                # distancia a la orilla donde va el muro de contención (m)
# El camino es de condominio, no costanera: angosto, sin solera ni vereda, y **lejos de la casa**.
# La primera versión lo tenía a 25 m del frente con 7,2 m de calzada y dos veredas de hormigón, y
# la revisión lo leyó como "calle grande de cemento" pegada a la casa por atrás.
CALLE_Y = 42.0               # eje del camino del condominio, detrás de la casa
CALLE_W = 2.30               # medio ancho de la calzada (4,6 m: cruzan dos autos justos)
VEREDA = 0.90                # berma de maicillo a cada lado, en vez de vereda de hormigón
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
    pa = n.new("ShaderNodeAttribute")          # césped: 1 en los antejardines
    pa.attribute_name = "pasto"
    seco = N.math("SUBTRACT", 1.0, pa.outputs["Fac"])
    # línea de marea: restos oscuros discontinuos
    tide = N.math("MULTIPLY", N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", d, 7.5)), 0.0, 0.6)),
                  N.smooth(N.noise(tc.outputs["Object"], 1.3, 3), 0.55, 0.62))
    col = N.mix(N.math("MULTIPLY", N.math("MULTIPLY", tide, seco), 0.7), col, (0.12, 0.1, 0.07))
    depth = N.math("MULTIPLY", d, -1.0)
    col = N.mix(N.smooth(depth, 0.0, 4.0), col, (0.13, 0.2, 0.17))
    col = N.mix(N.smooth(depth, 3.0, 28.0), col, (0.012, 0.055, 0.065))
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "veg"
    soil = N.mix(N.smooth(N.noise(tc.outputs["Object"], 2.0, 5), 0.35, 0.6), (0.2, 0.17, 0.11), (0.1, 0.11, 0.06))
    col = N.mix(N.math("MULTIPLY", at.outputs["Fac"], 0.75), col, soil)
    # césped de los antejardines: el terreno mismo va verde bajo las matas instanciadas. Sin esto
    # se ve la arena entre mata y mata y el jardín no cierra; es la diferencia entre un pasto
    # plantado sobre la duna y un césped regado.
    cesped = N.mix(N.math("MULTIPLY_ADD", N.noise(tc.outputs["Object"], 2.4, 5), 1.3, -0.15),
                   (0.028, 0.062, 0.016), (0.065, 0.115, 0.032))
    cesped = N.mix(N.math("MULTIPLY", N.noise(tc.outputs["Object"], 11.0, 4), 0.5), cesped,
                   (0.045, 0.09, 0.025))
    col = N.mix(N.math("MULTIPLY", pa.outputs["Fac"], 0.97), col, cesped)
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
    # Las ondas de viento y el grano son de **arena**: donde hay césped hay que apagarlas. Sin este
    # `seco` el pasto de los antejardines salía con las mismas ondas paralelas que la playa y en la
    # cenital el jardín se veía como pana rayada.
    # El ripple va sólo en la arena seca de la playa: la rampa de Huingán (1 para d > 10) servía
    # allá porque tierra adentro todo era duna, pero acá dejaba los sitios baldíos y el borde del
    # predio con ondas de viento paralelas, como un campo arado.
    playa = N.math("MULTIPLY", N.smooth(d, 6, 10),
                   N.math("SUBTRACT", 1.0, N.smooth(d, BEACH - 5.0, BEACH + 1.0)))
    h = N.math("ADD", N.math("MULTIPLY", N.math("MULTIPLY", wave.outputs["Fac"], seco),
                             N.math("MULTIPLY", playa, 0.6)),
               N.math("MULTIPLY", N.math("MULTIPLY", grain, seco), 0.25))
    h = N.math("ADD", h, N.math("MULTIPLY", N.math("MULTIPLY", N.noise(tc.outputs["Object"], 26.0, 4),
                                                   pa.outputs["Fac"]), 0.5))
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.22   # el ripple marcado se veía como pana
    bmp.inputs["Distance"].default_value = 0.025
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


# ---------------------------------------------------------------- materiales del balneario
def asphalt_mat():
    """Calzada de asfalto: árido fino, huellas de rueda algo más claras y pulidas, parches y
    borde deshilachado que se funde con el terreno (la costanera no tiene cuneta en todo el largo).
    La UV la pone build_camino: u a lo largo, v = 0..1 a lo ancho."""
    m, n, l = new_mat("Asfalto")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    uv = n.new("ShaderNodeUVMap")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(uv.outputs["UV"], sep.inputs[0])
    tc = n.new("ShaderNodeTexCoord")
    v = sep.outputs["Y"]
    grano = N.noise(tc.outputs["Object"], 55.0, 3)
    manchas = N.noise(tc.outputs["Object"], 0.6, 5, 0.7)
    # huellas: dos bandas pulidas donde pasan las ruedas
    hue = N.math("MAXIMUM",
                 N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.30)), 0.03, 0.14)),
                 N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.70)), 0.03, 0.14)))
    col = N.mix(N.math("MULTIPLY_ADD", manchas, 0.8, -0.1), (0.035, 0.034, 0.033), (0.072, 0.07, 0.068))
    col = N.mix(N.math("MULTIPLY", grano, 0.5), col, (0.1, 0.098, 0.092))
    col = N.mix(N.math("MULTIPLY", hue, 0.45), col, (0.095, 0.093, 0.09))
    l.new(col, b.inputs["Base Color"])
    l.new(N.math("SUBTRACT", 0.92, N.math("MULTIPLY", hue, 0.22)), b.inputs["Roughness"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.35
    bmp.inputs["Distance"].default_value = 0.012
    l.new(N.math("ADD", grano, N.math("MULTIPLY", N.noise(tc.outputs["Object"], 8.0, 4), 0.4)), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    l.new(N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT", v, 0.5)), 0.46, 0.5), mx.inputs["Fac"])
    l.new(b.outputs[0], mx.inputs[1])
    l.new(tr.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def paving_mat(name, pitch=1.2, tint=(0.52, 0.51, 0.48)):
    """Hormigón de vereda y de los senderos del predio: paños con junta de dilatación cada
    `pitch` metros (la junta es lo que lo hace leer como vereda y no como una cinta gris)."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    gr = N.noise(tc.outputs["Object"], 12.0, 5)
    col = N.mix(N.math("MULTIPLY_ADD", N.noise(tc.outputs["Object"], 0.9, 4), 1.2, -0.1), tint,
                tuple(c * 0.78 for c in tint))
    col = N.mix(N.math("MULTIPLY", gr, 0.35), col, tuple(c * 1.12 for c in tint))
    junta = N.math("MAXIMUM",
                   N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT",
                       N.math("FRACT", N.math("DIVIDE", sep.outputs["X"], pitch)), 0.5)), 0.44, 0.5)),
                   N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT",
                       N.math("FRACT", N.math("DIVIDE", sep.outputs["Y"], pitch)), 0.5)), 0.44, 0.5)))
    col = N.mix(N.math("MULTIPLY", junta, 0.8), col, (0.2, 0.2, 0.19))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.92
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.45
    bmp.inputs["Distance"].default_value = 0.01
    l.new(N.math("SUBTRACT", N.math("MULTIPLY", gr, 0.5), junta), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def seawall_mat():
    """Muro de contención: hormigón a la vista con las marcas del moldaje, escurrimientos de
    óxido y una franja húmeda con líquenes al pie, que es lo que delata que da a la playa."""
    m, n, l = new_mat("MuroMar")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    gr = N.noise(tc.outputs["Object"], 9.0, 5)
    col = N.mix(N.math("MULTIPLY_ADD", N.noise(tc.outputs["Object"], 1.1, 5, 0.6), 1.3, -0.15),
                (0.33, 0.32, 0.30), (0.52, 0.51, 0.48))
    # moldaje: tablas horizontales de 0,30 m
    mold = N.math("SUBTRACT", 1.0, N.smooth(N.math("ABSOLUTE", N.math("SUBTRACT",
        N.math("FRACT", N.math("DIVIDE", sep.outputs["Z"], 0.30)), 0.5)), 0.40, 0.5))
    col = N.mix(N.math("MULTIPLY", mold, 0.45), col, (0.24, 0.23, 0.22))
    # escurrimientos verticales: el mismo ruido estirado en z, que es lo que los hace chorreos
    mpc = n.new("ShaderNodeMapping")
    mpc.inputs["Scale"].default_value = (1.0, 1.0, 0.08)
    l.new(tc.outputs["Object"], mpc.inputs["Vector"])
    chorreo = N.smooth(N.noise(mpc.outputs["Vector"], 1.4, 4), 0.56, 0.68)
    col = N.mix(N.math("MULTIPLY", chorreo, 0.35), col, (0.26, 0.21, 0.15))
    # Pie húmedo con liquen. La altura se lee de un atributo que pone build_borde_mar, **no** de
    # la z del mundo: el muro corre a cota variable y su cara va de z = -2,5 a +0,2, así que con
    # la z cruda la franja de liquen cubría el muro entero y en el render se veía una faja verde
    # oscura cruzando la playa.
    alto = n.new("ShaderNodeAttribute")
    alto.attribute_name = "alto"
    pie = N.math("SUBTRACT", 1.0, N.smooth(alto.outputs["Fac"], 0.1, 0.75))
    col = N.mix(N.math("MULTIPLY", pie, N.math("ADD", 0.45, N.math("MULTIPLY", gr, 0.4))), col, (0.14, 0.16, 0.11))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.93
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.5
    bmp.inputs["Distance"].default_value = 0.02
    l.new(N.math("ADD", N.math("MULTIPLY", gr, 0.6), N.math("MULTIPLY", mold, 0.5)), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def gravel_mat():
    """Maicillo: la gravilla compactada con que se hacen las bermas y los accesos en los
    condominios de la costa. Reemplaza al hormigón de las veredas, que es lo que hacía leer el
    camino como calle de ciudad. Color tierra claro, grano grueso y borde que se funde con el
    pasto, para que no quede una cinta recortada sobre el terreno."""
    m, n, l = new_mat("Maicillo")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    gr = N.noise(tc.outputs["Object"], 38.0, 4)
    col = N.mix(N.math("MULTIPLY_ADD", N.noise(tc.outputs["Object"], 1.6, 5), 1.3, -0.15),
                (0.17, 0.13, 0.085), (0.30, 0.24, 0.16))
    col = N.mix(N.math("MULTIPLY", gr, 0.55), col, (0.24, 0.20, 0.14))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.6
    bmp.inputs["Distance"].default_value = 0.012
    l.new(gr, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def hedge_mat():
    """Seto recortado: verde oscuro parejo con hojas por bump. Lo que lo hace leer como seto y no
    como un bloque verde es el perfil irregular que le da el Displace, no el material."""
    m, n, l = new_mat("Seto")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    hoja = N.noise(tc.outputs["Object"], 28.0, 6, 0.7)
    col = N.mix(N.math("MULTIPLY_ADD", N.noise(tc.outputs["Object"], 2.2, 4), 1.3, -0.15),
                (0.022, 0.055, 0.020), (0.065, 0.125, 0.042))
    col = N.mix(N.math("MULTIPLY", hoja, 0.5), col, (0.045, 0.10, 0.032))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88
    b.inputs["Subsurface Weight"].default_value = 0.08
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 1.0
    bmp.inputs["Distance"].default_value = 0.05
    l.new(hoja, bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
    return m


def lawn_mat():
    """Césped recortado del antejardín: verde parejo con vetas de corte. Va en el terreno, debajo
    de las matas instanciadas; sin él se ve la arena entre pasto y pasto y el jardín no cierra."""
    m, n, l = new_mat("Cesped")
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    f = N.noise(tc.outputs["Object"], 3.0, 5)
    col = N.mix(N.math("MULTIPLY_ADD", f, 1.4, -0.2), (0.035, 0.075, 0.022), (0.075, 0.13, 0.04))
    l.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.5
    l.new(N.noise(tc.outputs["Object"], 30.0, 3), bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], b.inputs["Normal"])
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
        # ---- el balneario
        "asfalto": asphalt_mat(),
        "radier": paving_mat("Radier", 1.6, (0.58, 0.56, 0.52)),   # escalera pública a la playa
        "maicillo": gravel_mat(),                                  # bermas, acceso y huellas
        "muroMar": seawall_mat(),
        "seto": hedge_mat(),
        "cesped": lawn_mat(),
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
    # luces interiores tibias (en el día apenas se notan, pero dan vida al interior). Son más que
    # en Huingán porque la casa mide 16 m de largo: una por recinto de la banda que da al ventanal.
    # Potencias bajas: son un relleno para que el interior no quede como una caja negra detrás
    # del vidrio, no iluminación de noche. En la primera versión iban cinco veces más fuertes y
    # la revisión vio "la casa con luces de noche y afuera de día".
    for x, y, z, p in ((6.5, 4.6, 2.6, 38), (1.8, 4.5, 2.3, 14), (11.0, 4.5, 2.3, 14),
                       (14.3, 4.5, 2.3, 14), (6.8, 7.8, 2.6, 22), (12.5, 7.8, 2.4, 12)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.0
        lt.data.color = (1.0, 0.72, 0.45)
    return coll


SENDA_X = 7.0        # eje del sendero pavimentado que baja de la terraza al muro
ESC_W = 2.6          # ancho de la escalera pública que baja a la arena


def wall_y(x):
    """Línea del muro de contención: paralela a la orilla, a MURO_D metros de ella."""
    slope = 2 * (x - XC) / SHORE_K
    return shore_y(x) + MURO_D * math.sqrt(1 + slope * slope)


def build_borde_mar(M):
    """El borde del predio contra la playa, que es lo que reemplaza a la duna salvaje de Huingán:
    muro de contención de hormigón siguiendo la orilla, una escalera pública que baja a la arena
    y el sendero pavimentado que la une con la terraza. El muro es además lo que explica por qué
    el terreno está plano: sin él, el talud de 2 m entre el predio y la arena no se sostiene."""
    coll = bpy.data.collections.new("BordeMar")
    bpy.context.scene.collection.children.link(coll)
    z_top = GROUND + 0.32                       # el muro sobresale como parapeto sobre el césped
    X0, X1, STEP = -140.0, 170.0, 2.0
    hueco = (SENDA_X - ESC_W / 2 - 0.1, SENDA_X + ESC_W / 2 + 0.1)   # donde va la escalera
    verts, faces = [], []
    for i in range(int((X1 - X0) / STEP) + 1):
        x = X0 + i * STEP
        y = wall_y(x)
        zb = terrain_base(x, y - 1.2) - 0.6     # el pie se entierra en la arena
        verts += [(x, y, zb), (x, y, z_top), (x, y + 0.38, z_top), (x, y + 0.38, GROUND - 0.3)]
    n = 4
    for i in range(int((X1 - X0) / STEP)):
        x = X0 + i * STEP
        if hueco[0] - STEP < x < hueco[1]:
            continue
        a, b_ = i * n, (i + 1) * n
        faces += [(a, a + 1, b_ + 1, b_),        # cara vertical a la playa
                  (a + 1, a + 2, b_ + 2, b_ + 1),  # coronamiento
                  (a + 2, a + 3, b_ + 3, b_ + 2)]  # respaldo contra el terreno
    muro = mesh_obj("MuroMar", verts, faces, M["muroMar"], coll)
    at = muro.data.attributes.new("alto", "FLOAT", "POINT")
    at.data.foreach_set("value", [v[2] - verts[(i // 4) * 4][2] for i, v in enumerate(verts)])
    # escalera pública a la arena, en el eje del sendero
    y0 = wall_y(SENDA_X)
    z0, z1 = terrain_base(SENDA_X, y0 - 3.0), GROUND
    npel = 9
    for k in range(npel):
        z = z0 + (z1 - z0) * (k + 1) / npel
        yk = y0 - (npel - k - 1) * 0.30
        box(f"Peldano{k}", SENDA_X - ESC_W / 2, SENDA_X + ESC_W / 2, yk - 0.32, yk + 0.40,
            z - 0.18, z, M["radier"], coll)
    for sgn in (-1, 1):                          # murete lateral de la escalera
        xm = SENDA_X + sgn * (ESC_W / 2 + 0.11)
        box(f"MureteEsc{sgn}", xm - 0.11, xm + 0.11, y0 - npel * 0.30, y0 + 0.40,
            z0 - 0.4, z1 + 0.30, M["muroMar"], coll)
    # sendero de la terraza al muro
    verts, faces = [], []
    ys = [-0.4 - k * 1.0 for k in range(int((abs(y0) + 0.4) / 1.0) + 1)]
    for k, y in enumerate(ys):
        for sgn in (-1, 1):
            verts.append((SENDA_X + sgn * 0.60, y, GROUND + 0.02))
        if k:
            faces.append((2 * k - 2, 2 * k - 1, 2 * k + 1, 2 * k))
    mesh_obj("SendaMar", verts, faces, M["radier"], coll)
    return coll


# ---------------------------------------------------------------- terreno
def house_dist(x, y):
    """Distancia (m) al rectángulo de la casa (con un margen de 0,5 m)."""
    dx = max(-0.5 - x, 0, x - (L + 0.5))
    dy = max(-1.3 - y, 0, y - (D + 1.3))
    return math.hypot(dx, dy)


FORE = 0.08           # pendiente de la orilla (bajo el agua y donde rompe la ola)
BEACH = MURO_D - 1.2  # ancho de arena, desde la orilla hasta el pie del muro de contención
SLOPE_W = 2.0         # talud entre la arena y el predio: corto y escarpado, lo tapa el muro
CALLE_D = CALLE_Y - SHORE_Y          # distancia de la costanera a la orilla, medida en shore_d
LOTE_FONDO = CALLE_D - 5.6           # deslinde de atrás: la vereda empieza ahí


def terrain_base(x, y):
    """Perfil sin ondulaciones: fondo marino < playa < muro < predio aterrazado < costanera y el
    balneario subiendo tierra adentro. La diferencia con Huingán es el **escalón**: acá no hay
    ladera de duna de 16 m sino un talud de 2 m contenido por hormigón, y el predio queda plano."""
    d = shore_d(x, y)
    if d < 0:
        return SEA + max(d * FORE, -6.0)
    if d < 6.0:
        return SEA + d * FORE                      # orilla: pendiente fuerte, donde llega la ola
    if d < BEACH:
        return SEA + 6.0 * FORE + (d - 6.0) * 0.03
    top = SEA + 6.0 * FORE + (BEACH - 6.0) * 0.03
    t = min(1.0, (d - BEACH) / SLOPE_W)
    t = t * t * (3 - 2 * t)
    h = top + t * (GROUND - top)
    if d > CALLE_D + 10:                           # el pueblo sube en pendiente suave
        h += 0.055 * (d - CALLE_D - 10)
    return h


def path_dist(x, y):
    """Distancia (m) al sendero pavimentado que baja de la terraza al muro."""
    y0 = wall_y(SENDA_X)
    if y > -0.4:
        return math.hypot(x - SENDA_X, y + 0.4)
    if y < y0:
        return math.hypot(x - SENDA_X, y - y0)
    return abs(x - SENDA_X)


def drive_dist(x, y):
    """Distancia (m) al eje de la entrada de autos, que va de la costanera al porch por el
    costado +X de la casa (la casa ocupa x 0..16, así que el acceso rodado no la cruza)."""
    y0, y1 = D - 0.4, CALLE_Y - CALLE_W - VEREDA
    if y < y0:
        return math.hypot(x - DRIVE_X, y - y0)
    if y > y1:
        return math.hypot(x - DRIVE_X, y - y1)
    return abs(x - DRIVE_X)


DRIVE_X = 21.0        # eje de la entrada de autos
DRIVE_W = 2.6         # medio ancho de la entrada de autos


def en_lote(x, y):
    """1 en terreno loteado y mantenido, 0 en terreno silvestre. No es sólo nuestro predio: la
    primera fila corre a lo largo de toda la costanera y hay una segunda fila al otro lado, que es
    lo que convierte una playa en un balneario. Algunos sitios quedan **baldíos** (el ruido de
    `sitio`), porque una fila de jardines perfectos de punta a punta se lee falsa."""
    d = shore_d(x, y)
    frente = min(1.0, max(0.0, (d - BEACH - 1.0) / 1.5)) * min(1.0, max(0.0, (LOTE_FONDO - d) / 2.0))
    atras = min(1.0, max(0.0, (d - CALLE_D - 6.0) / 2.0)) * min(1.0, max(0.0, (CALLE_D + 46 - d) / 4.0))
    nuestro = min(1.0, max(0.0, (x - LOTE[0] + 1.0) / 2.0)) * min(1.0, max(0.0, (LOTE[1] + 1.0 - x) / 2.0))
    sitio = min(1.0, max(0.0, (0.5 + 0.9 * noise.noise(Vector((x / 46.0, d / 90.0, 5.5))) - 0.30) / 0.2))
    return max(frente, atras) * max(sitio, nuestro * frente)


def terrain_h(x, y):
    h = terrain_base(x, y)
    d = shore_d(x, y)
    # El predio y los de al lado están **aterrazados**: planos. Las ondulaciones quedan sólo en la
    # arena y tierra adentro, pasada la costanera. Es lo que distingue una playa urbanizada de una
    # duna: alguien movió la tierra.
    urb = min(1.0, max(0.0, (d - BEACH) / 3.0)) * min(1.0, max(0.0, (CALLE_D + 14 - d) / 6.0))
    amp = (1.0 - urb) * (0.35 + min(1.0, max(0.0, (d - CALLE_D - 40) / 80.0)) * 1.6)
    if d < BEACH:                                # la arena sí ondula, pero poco (playa pisada)
        amp = 0.30 * min(1.0, max(0.0, (d - 7.0) / 4.0))
    dn = noise.noise(Vector((x / 16.0, y / 12.0, 0.3))) + 0.4 * noise.noise(Vector((x / 5.0, y / 4.0, 1.7)))
    flat = min(1.0, max(0.0, (house_dist(x, y) - 1.0) / 6.0))
    h += amp * flat * (0.4 + 0.7 * dn)
    # cerros costeros al fondo: el balneario trepa por ellos. Arrancan antes que en Huingán
    # (90 m pasada la costanera) porque si no queda una explanada verde enorme entre la última
    # fila de casas y el cerro, que de lejos se lee como un desierto.
    if d > CALLE_D + 130:
        r = min(1.0, (d - CALLE_D - 130) / 300.0)
        hn = 0.5 + 0.5 * noise.noise(Vector((x / 180.0, y / 140.0, 3.1)))
        h += r * r * (26 + 78 * hn)
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
    # El terreno fino llega hasta pasada la costanera y la segunda fila de vecinos: todo eso entra
    # en cuadro desde el dron, y la calzada y las veredas se apoyan en él.
    near = (-180, 190, -62, 64)
    sand = grid("Playa", *near, 0.6, M["arena"], coll)
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
def load_ph(lib, ident, lod="LOD1", tag=None, nombres=None):
    """Variantes de un modelo de Poly Haven (una por letra), en el nivel de detalle pedido, como
    colección para instanciar al azar. Se dejan en el origen. `nombres` pide objetos exactos, que
    es lo que hace falta con los árboles: sus .blend traen además ramas, hojas y troncos sueltos
    que no son el árbol entero (si se toman todos, el Pick Instance planta troncos pelados)."""
    path = os.path.join(PH, ident, ident + ".blend")
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
        # ---- matorral costero: queda sólo del muro hacia la playa y en los sitios sin construir
        "searsia": load_ph(lib, "searsia_lucida"),
        "didelta": load_ph(lib, "didelta_spinosa"),
        "othonna": load_ph(lib, "othonna_cerarioides", "LOD2"),
        "rooibos": load_ph(lib, "wild_rooibos_bush", "LOD1"),
        "doca": load_ph(lib, "crystalline_iceplant", "LOD1"),
        "cheiri": load_ph(lib, "cheiridopsis_succulent", "LOD2"),
        "flor": load_ph(lib, "flower_heliophila", "LOD2"),
        "roca": load_ph(lib, "namaqualand_boulder_02", "LOD2"),
        # ---- jardín: lo que hace que el predio se lea cuidado y no silvestre
        "cesped": load_ph(lib, "grass_bermuda_01", tag="_small_"),
        "arbusto1": load_ph(lib, "shrub_01", "LOD2"),
        "arbusto2": load_ph(lib, "shrub_02", "LOD2"),
        "arbusto4": load_ph(lib, "shrub_04", "LOD2"),
    }
    lib.hide_render = lib.hide_viewport = True
    return bq, ph


def load_ornamentales(lib):
    """Árboles ornamentales de calle y de antejardín (Poly Haven CC0, tools/get_assets_urbano.sh).
    Se piden por nombre exacto: el .blend de cada árbol trae además el tronco y cada capa de hojas
    como objetos sueltos. El jacarandá es el árbol de vereda por excelencia en la costa chilena;
    island_tree y tree_small hacen de ornamentales de jardín."""
    coll = bpy.data.collections.new("Ornamentales")
    lib.children.link(coll)
    for ident in ("jacaranda_tree", "island_tree_01", "island_tree_02", "tree_small_02"):
        sub = load_ph(coll, ident, nombres=[ident + "_LOD1"])
        for o in list(sub.objects):
            sub.objects.unlink(o)
            coll.objects.link(o)
        coll.children.unlink(sub)
        bpy.data.collections.remove(sub)
    print("  ornamentales:", [(o.name, round(o.dimensions.z, 1)) for o in coll.objects])
    return coll


def place_props(coll_lib, M):
    """Lo suelto: roqueríos en los extremos de la playa, un par de troncos de deriva en la arena y
    los maceteros de la terraza. Los maceteros son lo único vegetal **dentro** de la casa y son
    los que dicen que esta terraza se usa: una terraza de 16 m vacía se ve de catálogo."""
    coll = bpy.data.collections.new("Props")
    bpy.context.scene.collection.children.link(coll)
    rk = load_ph(coll_lib, "coast_rocks_01", "LOD2")
    src = rk.objects[0]
    for x, rot, sc in ((-190.0, 0.5, 1.0), (215.0, 2.3, 0.8)):
        o = src.copy()
        coll.objects.link(o)
        y = shore_y(x) - 6.0
        o.location = (x, y, SEA - 1.2)
        o.rotation_euler = (0, 0, rot)
        o.scale = (sc, sc, sc * 1.4)
    tr = load_ph(coll_lib, "dead_tree_trunk")
    br = load_ph(coll_lib, "dry_branches_medium_01")
    for k, (x, off, rot) in enumerate(((-46.0, 9.0, 0.4), (53.0, 7.5, 2.0), (-18.0, 11.0, 1.2))):
        y = shore_y(x) + off
        src = tr.objects[0] if k < 2 else br.objects[0]
        o = src.copy()
        coll.objects.link(o)
        o.location = (x, y, terrain_h(x, y) + 0.05)
        o.rotation_euler = (0, 0, rot)
    mac = [load_ph(coll_lib, i).objects for i in ("potted_plant_01", "potted_plant_02")]
    for k, (x, y, s) in enumerate(((0.9, 0.7, 1.25), (15.1, 0.8, 1.1), (8.6, 0.55, 1.0),
                                   (3.4, 0.6, 0.9), (12.2, 0.75, 1.15))):
        for src in mac[k % 2]:
            o = src.copy()
            coll.objects.link(o)
            o.location = (x, y, GROUND + 0.65)
            o.rotation_euler = (0, 0, 1.1 * k)
            o.scale = (s, s, s)


def build_vegetation(sand, bq, ph):
    """Vegetación del terreno cercano con nodos de geometría, según tres atributos:
      pasto   césped recortado de los antejardines (predios, fuera de casa, senda y entrada)
      veg     matorral costero silvestre: sólo en los sitios baldíos y del muro hacia la playa
      camino  huella pisada de arena, en la bajada a la playa
    La diferencia con Huingán es cuál manda: allá el matorral cubría todo y los senderos se leían
    porque la vegetación los dejaba libres; acá manda el césped y el matorral es lo que queda
    donde nadie riega."""
    me = sand.data
    veg, pas, cam = [], [], []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = shore_d(x, y)
        pd, dd = path_dist(x, y), drive_dist(x, y)
        # El césped llega **hasta** la casa: con el margen de 1,2 m que usaba Huingán para el
        # matorral, alrededor de la casa quedaba un ruedo de tierra pelada de dos metros que en la
        # cenital se veía como una obra sin terminar.
        libre = min(1.0, max(0.0, (house_dist(x, y) - 0.0) / 0.30))
        libre *= min(1.0, max(0.0, (pd - 0.75) / 0.5))          # senda a la playa
        libre *= min(1.0, max(0.0, (dd - DRIVE_W) / 0.6))       # entrada de autos
        libre *= min(1.0, max(0.0, (abs(d - CALLE_D) - CALLE_W - VEREDA) / 1.0))   # calzada y vereda
        lote = en_lote(x, y)
        cerca = min(1.0, max(0.0, (150.0 - math.hypot(x - HC.x, y - HC.y)) / 40.0))
        p = lote * libre * cerca
        # Variación suave: un césped regado no tiene claros. Con la amplitud anterior
        # (0,75 + 0,9·ruido) medio jardín quedaba a mitad de verde y se leía pajoso.
        p *= min(1.0, max(0.0, 0.92 + 0.5 * noise.noise(Vector((x / 9.0, y / 9.0, 6.3)))))
        pas.append(max(0.0, min(1.0, p)))
        # matorral: en los sitios baldíos y en la franja de arena al pie del muro
        w = (1.0 - lote) * min(1.0, max(0.0, (d - BEACH - 0.5) / 3.0)) * libre
        w += 0.35 * min(1.0, max(0.0, (d - BEACH + 3.0) / 2.0)) * min(1.0, max(0.0, (BEACH - d) / 1.0))
        w *= min(1.0, max(0.0, 0.55 + 1.3 * noise.noise(Vector((x / 7.0, y / 7.0, 2.2)))
                          + 0.4 * noise.noise(Vector((x / 2.5, y / 2.5, 4.1)))))
        veg.append(max(0.0, min(1.0, w)))
        cam.append(min(1.0, max(0.0, 1.4 - pd / 1.1)) if d < BEACH + 1 else 0.0)
    for nombre, datos in (("veg", veg), ("pasto", pas), ("camino", cam)):
        at = me.attributes.new(nombre, "FLOAT", "POINT")
        at.data.foreach_set("value", datos)
    ng = bpy.data.node_groups.new("Duna", "GeometryNodeTree")
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

    # ---- jardín: césped parejo (el ruido apenas lo modula, un césped regado no tiene claros)
    # Las matas de bermuda son tarjetas de 6-10 caras, así que la densidad alta sale casi gratis.
    scatter(ph["cesped"], 55.0, 1.0, 1.6, 11, 0.05, 0.3, 0.6, 0.06, attr="pasto")
    scatter(bq["Grass_Karl-foerster_B"], 0.5, 0.8, 1.3, 13, 0.52, 0.66, 0.35, 0.1, attr="pasto")
    # arbustos de jardín: agrupados en macizos, no esparcidos (nscale baja = manchones grandes)
    scatter(ph["arbusto2"], 0.09, 0.8, 1.3, 15, 0.55, 0.68, 0.07, 0.05, attr="pasto")
    scatter(ph["arbusto4"], 0.07, 0.9, 1.5, 16, 0.56, 0.70, 0.07, 0.05, attr="pasto")
    scatter(ph["arbusto1"], 0.05, 0.8, 1.4, 17, 0.58, 0.72, 0.06, 0.05, attr="pasto")
    scatter(ph["flor"], 0.9, 0.8, 1.2, 18, 0.56, 0.68, 0.25, 0.12, attr="pasto")
    # ---- matorral costero silvestre: sitios baldíos y pie del muro
    scatter(bq["Grass_Tall_A"], 11.0, 1.6, 2.6, 21, 0.3, 0.55)
    scatter(ph["searsia"], 0.16, 0.9, 1.6, 31, 0.38, 0.58, 0.06, 0.06)
    scatter(ph["didelta"], 0.06, 0.6, 1.1, 32, 0.42, 0.6, 0.05, 0.05)
    scatter(ph["othonna"], 0.30, 1.0, 1.6, 34, 0.38, 0.6, 0.1, 0.06)
    scatter(ph["rooibos"], 0.40, 1.5, 2.4, 35, 0.38, 0.6, 0.1, 0.06)
    scatter(ph["doca"], 11.0, 2.0, 3.5, 36, 0.42, 0.56, 0.1, 0.02)
    scatter(ph["cheiri"], 0.7, 0.9, 1.4, 37, 0.42, 0.62, 0.15, 0.03)
    scatter(ph["roca"], 0.004, 0.4, 1.0, 40, 0.55, 0.62, 0.05, 0.4)
    Lk.new(join.outputs[0], go.inputs[0])
    md = sand.modifiers.new("Duna", "NODES")
    md.node_group = ng



# ---------------------------------------------------------------- contexto: el balneario
# En Huingán el contexto era un camino de tierra que se perdía en los cerros y casas sueltas a
# cientos de metros. Acá el contexto es una urbanización: una costanera pavimentada paralela a la
# playa, con solera, vereda, alumbrado y postes, predios deslindados con setos y pandereta, y dos
# filas de vecinos. Todo se mide con `shore_d`, así que todo queda paralelo a la orilla.


def calle_y(x):
    """Eje de la costanera: paralela a la orilla, a CALLE_D metros de ella."""
    slope = 2 * (x - XC) / SHORE_K
    return shore_y(x) + CALLE_D * math.sqrt(1 + slope * slope)


def lote_y(x, dd):
    """`y` del punto que está a `dd` metros de la orilla en la columna x (para emplazar vecinos)."""
    slope = 2 * (x - XC) / SHORE_K
    return shore_y(x) + dd * math.sqrt(1 + slope * slope)


def cinta(name, x0, x1, half_lo, half_hi, dz, mat, coll, step=4.0, uv=False, cerrar=True):
    """Cinta paralela a la costanera entre dos distancias al eje (en metros, con signo: negativo
    hacia el mar). Sirve para la calzada, las veredas y los bandejones: todas son la misma franja
    a distinta distancia, y así ninguna se cruza con otra ni con el terreno."""
    verts, faces = [], []
    n = int((x1 - x0) / step) + 1
    for i in range(n):
        x = x0 + i * step
        yc = calle_y(x)
        for h in (half_lo, half_hi):
            y = yc + h
            verts.append((x, y, terrain_h(x, y) + dz))
        if i:
            faces.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
    o = mesh_obj(name, verts, faces, mat, coll)
    if uv:
        uvl = o.data.uv_layers.new(name="UVMap")
        for poly in o.data.polygons:
            for li in poly.loop_indices:
                vi = o.data.loops[li].vertex_index
                uvl.data[li].uv = ((vi // 2) * step / 6.0, float(vi % 2))
    return o


def build_camino(M, coll):
    """El camino del condominio: una calzada **angosta** de asfalto, sin solera ni vereda, que se
    deshilacha contra el pasto, más el acceso de maicillo que entra al predio.

    La primera versión era una costanera urbana (7,2 m de calzada, soleras, dos veredas de
    hormigón y alumbrado): la revisión la leyó como "calle grande de cemento" y pidió un
    condominio estilo Maitencillo. En un condominio el camino es angosto, no tiene solera ni
    vereda y el pasto llega hasta el borde del asfalto."""
    X0, X1 = -420.0, 460.0
    cinta("Calzada", X0, X1, -CALLE_W, CALLE_W, 0.05, M["asfalto"], coll, 4.0, uv=True)
    # berma de maicillo a cada lado: es lo único que separa el asfalto del pasto
    for sgn in (-1, 1):
        s_ = sgn * CALLE_W
        cinta(f"Berma{sgn}", X0, X1, s_, s_ + sgn * VEREDA, 0.03, M["maicillo"], coll, 4.0)
    # acceso al predio: del borde del camino al porch, en maicillo y no en hormigón
    y0, y1 = D - 0.5, calle_y(DRIVE_X) - CALLE_W - VEREDA + 0.3
    verts, faces = [], []
    ny = max(2, int((y1 - y0) / 1.5))
    for k in range(ny + 1):
        y = y0 + (y1 - y0) * k / ny
        for sgn in (-1, 1):
            x = DRIVE_X + sgn * (DRIVE_W - 0.35)
            verts.append((x, y, terrain_h(x, y) + 0.03))
        if k:
            faces.append((2 * k - 2, 2 * k - 1, 2 * k + 1, 2 * k))
    mesh_obj("Acceso", verts, faces, M["maicillo"], coll)
    # huella de maicillo entre el porch y la terraza, por el costado -X
    verts, faces = [], []
    for k in range(9):
        y = -1.2 + k * 1.6
        for sgn in (-1, 1):
            x = -1.9 + sgn * 0.45
            verts.append((x, y, terrain_h(x, y) + 0.03))
        if k:
            faces.append((2 * k - 2, 2 * k - 1, 2 * k + 1, 2 * k))
    mesh_obj("Pasillo", verts, faces, M["maicillo"], coll)


def build_cierros(M, coll):
    """Deslindes: seto recortado entre predios y, hacia el camino, un cierro de **listones de
    madera** con su portón. Antes era una pandereta de albañilería con pilares; en un condominio
    de costa el deslinde a la calle es madera o vegetación, nunca un muro de bloques."""
    seto_h, seto_w = 1.55, 0.75
    for xl in (LOTE[0], LOTE[1]):
        d0, d1 = BEACH + 1.2, LOTE_FONDO - 0.2
        verts, faces = [], []
        n = 46
        for k in range(n + 1):
            dd = d0 + (d1 - d0) * k / n
            y = lote_y(xl, dd)
            z = terrain_h(xl, y)
            # perfil del seto: un prisma con el lomo algo irregular (un seto recortado no es un
            # bloque perfecto, pero tampoco una mata: la irregularidad es de centímetros)
            h = seto_h + 0.09 * noise.noise(Vector((dd / 3.0, xl / 7.0, 1.1)))
            verts += [(xl - seto_w / 2, y, z), (xl + seto_w / 2, y, z),
                      (xl + seto_w / 2, y, z + h * 0.92), (xl + seto_w / 2 - 0.1, y, z + h),
                      (xl - seto_w / 2 + 0.1, y, z + h), (xl - seto_w / 2, y, z + h * 0.92)]
            if k:
                a, b_ = (k - 1) * 6, k * 6
                for q in range(5):
                    faces.append((a + q, a + q + 1, b_ + q + 1, b_ + q))
        o = mesh_obj(f"Seto{xl:.0f}", verts, faces, M["seto"], coll)
        dsp = o.modifiers.new("hoja", "DISPLACE")
        tex = bpy.data.textures.new(f"seto{xl:.0f}", "CLOUDS")
        tex.noise_scale = 0.35
        dsp.texture, dsp.strength = tex, 0.16
        for p in o.data.polygons:
            p.use_smooth = True
    # cierro de madera hacia el camino, con el portón al eje del acceso
    ym = calle_y(0.0) - CALLE_W - VEREDA - 1.2
    for x0, x1 in ((LOTE[0], DRIVE_X - DRIVE_W - 0.3), (DRIVE_X + DRIVE_W + 0.3, LOTE[1])):
        n = max(2, int((x1 - x0) / 0.22))
        for k in range(n):
            x = x0 + (x1 - x0) * k / n
            z = terrain_h(x, ym)
            box(f"Cierro{k}", x, x + 0.11, ym - 0.03, ym + 0.03, z - 0.05, z + 1.25,
                M["fachada"], coll)
        z = terrain_h((x0 + x1) / 2, ym)
        for zt in (z + 0.45, z + 1.22):          # travesaños
            box("CierroTrav", x0, x1, ym - 0.045, ym + 0.045, zt - 0.07, zt, M["fachada"], coll)
    for sgn in (-1, 1):                          # pilares del portón, también de madera
        x = DRIVE_X + sgn * (DRIVE_W + 0.3)
        z = terrain_h(x, ym)
        box(f"Pilar{sgn}", x - 0.11, x + 0.11, ym - 0.11, ym + 0.11, z - 0.2, z + 1.55,
            M["fachada"], coll)
    z = terrain_h(DRIVE_X, ym)
    for k in range(11):                          # portón de listones
        x = DRIVE_X - DRIVE_W + 0.25 + k * (2 * DRIVE_W - 0.5) / 10
        box(f"Liston{k}", x - 0.055, x + 0.055, ym - 0.03, ym + 0.03, z + 0.08, z + 1.30,
            M["fachada"], coll)
    box("PortonTrav", DRIVE_X - DRIVE_W + 0.2, DRIVE_X + DRIVE_W - 0.2, ym - 0.04, ym + 0.04,
        z + 1.14, z + 1.30, M["fachada"], coll)


def place_ornamentales(coll, orn, pinos):
    """Arbolado del condominio. **No hay hilera de árboles de vereda**: la versión anterior
    alineaba jacarandás cada 30 m sobre la vereda y eso es lo que hace que una calle se lea como
    calle de ciudad. Acá los árboles van en grupos irregulares entre los predios y a lo largo del
    camino, con pinos y cipreses —que es lo que hay en la costa central— y algún ornamental de
    hoja ancha en los antejardines."""
    arb = list(orn.objects)
    pin = list(pinos)
    rnd = random.Random(17)

    def poner(x, y, s, fuente=None, giro=None):
        """`s` es la altura pedida en metros: los modelos de Poly Haven vienen en escalas muy
        distintas (19,5 m el jacarandá, 3,4 el island_tree_02) y mezclarlos por factor deja
        arbolitos de maqueta al lado de árboles gigantes."""
        o = rnd.choice(fuente or arb).copy()
        coll.objects.link(o)
        o.location = (x, y, terrain_h(x, y) - 0.08)
        o.rotation_euler = (0, 0, giro if giro is not None else rnd.uniform(0, 6.28))
        f = s / max(0.1, o.dimensions.z)
        o.scale = (f, f, f * rnd.uniform(0.94, 1.08))
        return o

    # grupos de pinos y cipreses a lo largo del camino, a distancias irregulares y a los dos
    # lados: es lo que da la sombra moteada de un condominio entre pinos
    x = -300.0
    while x < 360.0:
        x += rnd.uniform(14.0, 34.0)
        if abs(x - DRIVE_X) < 12:
            continue                               # no tapar el acceso del predio
        for _ in range(rnd.randint(1, 3)):
            lado = rnd.choice((-1, -1, 1))
            dd = CALLE_D + lado * rnd.uniform(CALLE_W + VEREDA + 1.5, CALLE_W + VEREDA + 9.0)
            xx = x + rnd.uniform(-5, 5)
            poner(xx, lote_y(xx, dd), rnd.uniform(9.0, 16.0), pin)
    # nuestro antejardín: a los costados, nunca delante del ventanal corrido
    for x, dd, s in ((-7.5, 40.0, 6.5), (23.5, 43.0, 5.0), (-8.5, 62.0, 7.0), (24.5, 66.0, 6.0),
                     (-7.0, 72.0, 9.0), (24.0, 76.0, 8.5)):
        poner(x, lote_y(x, dd), s, pin if s > 8 else None)
    # jardines de los vecinos, en grupos sueltos
    for k in range(26):
        xx = rnd.uniform(-190, 210)
        if -14 < xx < 30:
            continue
        dd = rnd.choice((rnd.uniform(34, 80), rnd.uniform(100, 140)))
        poner(xx, lote_y(xx, dd), rnd.uniform(5.0, 13.0), pin if rnd.random() < 0.6 else None)


# ---- vecinos del condominio. La revisión pidió sacar las "casas todas iguales atrás": antes
# venían en filas regulares a distancias fijas de la orilla, con el mismo volumen a dos aguas y
# los mismos tres colores. Ahora las dos contiguas están puestas a mano (son las que se ven en el
# arco frontal y las que fijan la escala: más chicas que Mañío a propósito, que con 16 m de frente
# es la más grande del conjunto) y el resto se siembra irregular, con tamaño, giro, retranqueo,
# pendiente de techo y color variables, y algunas con volumen anexo.
# (x, distancia a la orilla, giro°, ancho, fondo, alto de muro, muro, techo, pendiente, anexo)
VECINOS = [
    (-32.0, 52.0, -14, 11, 8, 2.9, "madera", "gris", 0.30, True),
    (48.0, 46.0, 9, 13, 9, 3.1, "negro", "gris", 0.22, False),
]
_rnd_v = random.Random(29)
# Paleta de la costa central: madera y tonos oscuros. El blanco con techo de teja es lo que
# hacía que un par de vecinos se leyeran como loteo de ciudad, así que queda como excepción.
_MUROS = ("madera", "madera", "madera", "negro", "piedra", "piedra", "blanco")
_TECHOS = ("gris", "gris", "gris", "madera", "teja")
for _k in range(78):
    if _k < 16:                      # vecinos de la primera línea, a lo largo de la playa
        _x = (-1) ** _k * (72.0 + _k * 27.0) + _rnd_v.uniform(-9, 9)
        _dd = _rnd_v.uniform(40.0, 74.0)
    elif _k < 36:                    # del camino hacia adentro, sueltos entre los pinos
        _x = _rnd_v.uniform(-230, 250)
        _dd = _rnd_v.uniform(100.0, 170.0)
    else:                            # el condominio trepando el cerro
        _x = _rnd_v.uniform(-340, 360)
        _dd = 170.0 + (_k - 36) * 7.0 + _rnd_v.uniform(-30, 30)
    VECINOS.append((_x, _dd, _rnd_v.uniform(-45, 45), _rnd_v.uniform(8, 16),
                    _rnd_v.uniform(6, 10), _rnd_v.uniform(2.5, 3.4),
                    _rnd_v.choice(_MUROS if _k < 36 else _MUROS[:5]),
                    _rnd_v.choice(_TECHOS if _k < 36 else _TECHOS[:4]),
                    _rnd_v.uniform(0.16, 0.42), _rnd_v.random() < 0.35))


def build_neighbors(coll):
    """Casas vecinas del condominio: volúmenes a dos aguas con ventanas, chimenea y, las de la
    primera línea, terraza al mar. Cada una con su pendiente de techo, su giro y su color, y
    algunas con un volumen anexo; todas distintas, que es lo que pidió la revisión."""
    mats = {"blanco": principled("VecMuroBlanco", (0.62, 0.6, 0.56), 0.8),
            "madera": principled("VecMuroMadera", (0.26, 0.18, 0.11), 0.75),
            "negro": principled("VecMuroNegro", (0.035, 0.034, 0.032), 0.6),
            "piedra": principled("VecMuroPiedra", (0.30, 0.28, 0.25), 0.9),
            "gris": principled("VecTechoGris", (0.075, 0.075, 0.08), 0.5),
            "teja": principled("VecTechoTeja", (0.20, 0.085, 0.05), 0.7),
            "vidrio": principled("VecVentana", (0.02, 0.025, 0.03), 0.1),
            "deck": principled("VecDeck", (0.34, 0.24, 0.15), 0.7)}
    mats["madera_techo"] = mats["madera"]
    rnd = random.Random(7)
    for k, (x, dd, rot, w, d, h, wall, roof, pend, anexo) in enumerate(VECINOS):
        y = lote_y(x, dd)
        cerca = dd < 80 and abs(x) < 140          # primera línea, en cuadro
        z = min(terrain_h(x + ddx, y + ddy) for ddx in (-w / 2, w / 2) for ddy in (-d / 2, d / 2)) - 0.3
        r = h + w * pend
        roof_mat = mats["madera_techo" if roof == "madera" else roof]
        verts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0),
                 (-w / 2, -d / 2, h), (w / 2, -d / 2, h), (w / 2, d / 2, h), (-w / 2, d / 2, h),
                 (0, -d / 2, r), (0, d / 2, r)]
        faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 8), (6, 7, 9)]
        piezas = [mesh_obj(f"Vecino{k}", verts, faces, mats[wall], coll)]
        roof_v = [(-w / 2 - 0.4, -d / 2 - 0.4, h - 0.2), (0, -d / 2 - 0.4, r), (0, d / 2 + 0.4, r),
                  (-w / 2 - 0.4, d / 2 + 0.4, h - 0.2), (w / 2 + 0.4, -d / 2 - 0.4, h - 0.2),
                  (w / 2 + 0.4, d / 2 + 0.4, h - 0.2)]
        t = mesh_obj(f"VecinoTecho{k}", roof_v, [(0, 1, 2, 3), (1, 4, 5, 2)], roof_mat, coll)
        t.modifiers.new("e", "SOLIDIFY").thickness = 0.15
        piezas.append(t)
        # ventanal al mar (-Y) y ventanas a los costados
        piezas.append(mesh_obj(f"VecinoVentana{k}",
                               [(-w * 0.32, -d / 2 - 0.03, 0.9), (w * 0.32, -d / 2 - 0.03, 0.9),
                                (w * 0.32, -d / 2 - 0.03, h - 0.35), (-w * 0.32, -d / 2 - 0.03, h - 0.35)],
                               [(0, 1, 2, 3)], mats["vidrio"], coll))
        if anexo:                                  # volumen menor adosado, con techo propio
            aw, ad, ah = w * rnd.uniform(0.3, 0.45), d * rnd.uniform(0.5, 0.7), h * 0.78
            ax = (w / 2 + aw / 2 - 0.1) * rnd.choice((-1, 1))
            ay = rnd.uniform(-d * 0.15, d * 0.2)
            piezas.append(box(f"VecinoAnexo{k}", ax - aw / 2, ax + aw / 2, ay - ad / 2, ay + ad / 2,
                              0.0, ah, mats[wall], coll))
            piezas.append(box(f"VecinoAnexoTecho{k}", ax - aw / 2 - 0.3, ax + aw / 2 + 0.3,
                              ay - ad / 2 - 0.3, ay + ad / 2 + 0.3, ah, ah + 0.14, roof_mat, coll))
        if cerca:
            for sgn in (-1, 1):                    # ventanas laterales
                vx = sgn * (w / 2 + 0.03)
                piezas.append(mesh_obj(f"VecinoLat{k}{sgn}",
                                       [(vx, -d * 0.18, 1.1), (vx, d * 0.22, 1.1),
                                        (vx, d * 0.22, h - 0.5), (vx, -d * 0.18, h - 0.5)],
                                       [(0, 1, 2, 3)], mats["vidrio"], coll))
            dk = box(f"VecinoDeck{k}", -w * 0.42, w * 0.42, -d / 2 - rnd.uniform(2.2, 3.6), -d / 2,
                     -0.12, 0.04, mats["deck"], coll)
            piezas.append(dk)
            cx = rnd.uniform(-w * 0.25, w * 0.25)  # chimenea
            piezas.append(box(f"VecinoChim{k}", cx - 0.3, cx + 0.3, -0.3, 0.3, h, r + 0.5,
                              mats[wall], coll))
        for ob in piezas:
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
    """Arboledas del paisaje lejano: pinos y macrocarpas entre las casas del balneario y en los
    cerros del fondo; nunca en la playa ni dentro del predio (atributo 'bosque'). En un balneario
    costero el arbolado **sigue a las casas**, así que el término que más pesa es la cercanía a un
    vecino: es lo que hace que el cerro se lea poblado y no como un bosque virgen."""
    me = far.data
    w = []
    vec_xy = [(vx, lote_y(vx, vdd)) for vx, vdd, *_ in VECINOS]
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        d = shore_d(x, y)
        # la rampa de entrada es larga a propósito: con una corta, el bosque arranca de golpe y
        # deja un borde recto cruzando el cerro
        a = min(1.0, max(0.0, (d - CALLE_D - 12) / 70.0)) * min(1.0, max(0.0, (math.hypot(x - HC.x, y - HC.y) - 90) / 50.0))
        clump = 0.5 + 0.5 * noise.noise(Vector((x / 140.0, y / 140.0, 7.7)))
        near_house = max((max(0.0, 1.0 - math.hypot(x - vx, y - vy) / 40.0) for vx, vy in vec_xy), default=0)
        hill = min(1.0, max(0.0, (d - CALLE_D - 110) / 200.0))
        w.append(a * min(1.0, max(0.0, (clump - 0.42) * 2.8 + 1.1 * hill + 1.0 * near_house)))
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
    dist.inputs["Distance Min"].default_value = 4.0
    dist.inputs["Density Max"].default_value = 0.022
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


def build_context(M, orn):
    """El condominio. Ya no hay alumbrado público ni postes con tendido: la revisión pidió
    sacarlos ("ahora se hacen bajo tierra"), y además eran lo que más empujaba la lectura de
    calle urbana."""
    coll = bpy.data.collections.new("Contexto")
    bpy.context.scene.collection.children.link(coll)
    build_camino(M, coll)
    build_cierros(M, coll)
    build_neighbors(coll)
    arboles = make_trees(bpy.data.collections["Biblioteca"])
    place_ornamentales(coll, orn, arboles)
    build_far_trees(bpy.data.objects["Lejos"], arboles)


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


# Tomas fijas para las fotos de aprobación, dadas como (azimut°, elevación°, factor de distancia)
# y resueltas con el mismo encuadre adaptable del dron. Se dan así y no con coordenadas fijas
# porque Casa Mañío es la más grande del conjunto (16,02 m de frente, era la "Huingán familiar"):
# con las coordenadas de Huingán quedaba cortada. El azimut es 0 de frente, negativo a la
# izquierda mirando desde el mar.
# El factor de distancia importa tanto como el ángulo: con la playa de 32 m, a la distancia del
# encuadre adaptable (unos 39 m) la cámara queda **dentro** del predio y el mar cae fuera de
# cuadro por abajo. Las tomas que tienen que mostrar la relación con la playa se alejan a
# propósito aunque la casa salga más chica.
# Los factores están calibrados contra las fotos aprobadas de Huingán
# (output/huingan_propuesta/): ahí la casa ocupa un tercio del ancho y el agua entra por abajo.
# Con el factor 1,0 del encuadre adaptable la cámara se planta **dentro** del predio y el mar
# queda fuera de cuadro, porque la playa de un balneario mide 32 m y no 13.
VISTAS = {
    "izq": (-32.0, 18.0, 2.1),         # diagonal frontal izquierda, desde el agua
    "der": (36.0, 17.0, 2.1),          # diagonal frontal derecha
    "frente": (2.0, 15.0, 1.9),        # de frente al ventanal corrido: el enganche
    "cerca": (-50.0, 13.0, 1.12),      # la casa de cerca, con el jardín y los vecinos
    "izq_atras": (-142.0, 19.0, 1.7),   # desde el condominio, hacia el mar
    "der_atras": (146.0, 17.0, 1.7),
    "calle": (158.0, 22.0, 1.32),      # la fachada de acceso: la casa manda, el camino acompaña
    "cenital": (90.0, 72.0, 1.30),     # la planta, con el loteo alrededor
}


def build_camera():
    sc = bpy.context.scene
    cam = link(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
    sc.camera = cam
    az, el, fac = VISTAS[opts["vista"]]
    lens = 30.0
    w, h = (int(v) for v in opts["res"].split("x"))
    direc = _dir(az, el)
    dist = fit_distance(direc, CASA_C, lens, w / h) * fac
    cam.location = CASA_C + direc * dist
    cam.rotation_euler = (-direc).to_track_quat("-Z", "Y").to_euler()
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
CASA_BOX = (0.0, L, -0.9, D + 0.9, GROUND, 5.2)     # caja de la casa (con escaleras) para encuadrar
CASA_C = Vector((L / 2, D / 2, 1.6))                 # punto al que mira el dron
# Casa Mañío es la más ancha y la más baja (16,02 x 5,07): en un cuadro vertical, con el FIT = 0,74
# de Huingán quedaba una franja chica en medio de la pantalla. ENGANCHES.md pide justo lo
# contrario —"que la casa cruce la pantalla a lo ancho"—, así que ocupa casi todo el ancho.
FIT = 0.88                                           # ancho de pantalla que ocupa la casa


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


S1_AZ = (-122.0, -40.0)      # azimut (0 = de frente, la cámara hacia -Y; negativo = lado izquierdo)
S1_EL = (21.0, 12.0)         # elevación (°): más baja que en Huingán, la casa es baja y tendida
S1_D0 = 205.0                # distancia inicial (m)


def pose_s1(f, n):
    """Aproximación en espiral: el giro avanza parejo y la distancia cae en escala logarítmica con
    salida suave (el dron frena al llegar). El punto de mira pasa de la playa a la casa."""
    u = f / (n - 1)
    ua = u * u * (3 - 2 * u)
    az = math.radians(S1_AZ[0] + (S1_AZ[1] - S1_AZ[0]) * ua)
    el = math.radians(S1_EL[0] + (S1_EL[1] - S1_EL[0]) * ua)
    direc = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    ud = 1 - (1 - u) ** 2.2                          # rápido al comienzo, frena al final
    tgt = Vector((L / 2, -18.0, -1.4)).lerp(CASA_C, smootherstep(min(1.0, u * 1.25)))
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
CUT_TOP, CUT_LOW = 5.4, 1.55     # altura del corte: sobre el techo (casa entera) / a media altura (planta 3D)
# claves: (cuadro global, azimut°, elevación°, distancia, altura de corte, parar)
#   distancia: número (m) o ("fit", factor): la del encuadre adaptable en esa dirección
#   parar=True: la cámara llega quieta a esa clave (fin de s3, antes del paso a la planta)
# El arco frontal va más bajo que el de Huingán (11-12° contra 15-16°): el enganche de Mañío es
# que se abre entera al frente y que es baja, y eso sólo se lee desde cerca del nivel de la
# terraza. La clave de 90 pasa justo por delante del ventanal corrido.
RUTA = [
    (0, S1_AZ[1], S1_EL[1], ("fit", 1.0), CUT_TOP, True),     # = último cuadro de s1
    (90, 2.0, 10.5, ("frente", 1.0), CUT_TOP, False),         # de frente al ventanal, bajo
    (192, 66.0, 12.0, ("frente", 1.0), CUT_TOP, False),       # fin s2: costado derecho
    (262, 80.0, 40.0, ("fit", 1.05), CUT_TOP, False),
    (352, 88.0, 76.0, ("fit", 1.0), CUT_LOW, False),
    (432, 90.0, 89.5, ("fit", 1.0), CUT_LOW, True),           # fin s3: cenital, casa a lo largo de la pantalla
    (500, 116.0, 50.0, ("fit", 1.15), CUT_TOP, False),
    (624, 150.0, 14.0, ("fit", 1.0), CUT_TOP, True),          # fin s5: fachada de acceso y la costanera
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
    frente = max(fit_distance(_dir(a, 11.5), CASA_C, lens, w / h) for a in range(-45, 75, 5))
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
        if o.type == "MESH" and o.name != "Manio_Casco":
            o.modifiers.new("Corte", "NODES").node_group = ng
    socks = [zval.outputs[0]] + [g.nodes["AlturaCorte"].outputs[0] for g in groups.values()]
    for f in range(frames):
        for sk in socks:
            sk.default_value = cut_z(g0 + f)
            sk.keyframe_insert("default_value", frame=f + 1)
    for o in house:   # con el techo abierto entra el día: luces interiores suaves
        if o.type == "LIGHT":
            o.visible_camera = False
            o.data.energy *= 0.6
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
    # oleaje: el tiempo del océano avanza con el video (cada sección sigue donde quedó la anterior)
    md = bpy.data.objects["MarOleaje"].modifiers["Oleaje"]
    t0 = float(opts.get("t_mar", "3.0")) + sum(SECCIONES[k] for k in sorted(SECCIONES) if k < tramo) / FPS
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
    if tramo in ("s3", "s5"):
        apply_section(n, INICIO[tramo])
    if tramo == "s3":   # dónde cae la casa en la cenital final: para calzar la planta (tools/plano_huingan.py)
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
    build_borde_mar(M)
    sand = build_landscape(M)
    bq, ph = load_assets(M)
    lib = bpy.data.collections["Biblioteca"]
    orn = load_ornamentales(lib)
    build_vegetation(sand, bq, ph)
    place_props(lib, M)
    build_context(M, orn)
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
