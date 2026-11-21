"""Escena 3D de Casa Roble en un centro de ski (Blender 5.x, Cycles).

Uso:
  python casa_roble_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  python casa_roble_3d.py -- --vista dron --tramo s1 --out frames_roble/s1/f_ --res 720x1280
  (vistas: izq / der = tomas fijas de dron desde el testero vidriado, que mira a la pista;
  izq_atras / der_atras = las opuestas, desde la fachada de acceso. --nevada gradúa la nieve
  cayendo: 0 la apaga, 1 es nevada normal. --dof 0 apaga el desenfoque.)

La casa sale del modelo STL de Neorigen (assets/roble/casa.blend, generado con
tools/extraer_roble_stl.py): 8,79 m de ancho por 16,81 de fondo —la más angosta y larga después
de Boldo—, terraza hacia -Y bajo el testero vidriado de doble altura, porch de acceso hacia +Y,
techo a dos aguas asimétrico (cumbrera en x = 6,88, faldones de 27° y 32°), piso terminado en
z = 0,55, segundo piso en 3,26 y cumbrera a 6,55.

Paisaje: ladera abierta de centro de ski, al sol. Es lo **opuesto** al bosque cerrado de Peumo
(RECETA.md §5): acá entra mucho más cielo, el bosque es ralo y queda a los costados, y lo que
llena el cuadro es la nieve pisada de la pista. La casa se posa en una plataforma nivelada al
borde de la pista, que baja por delante del testero: desde el estar se mira la bajada.

Lo que hace que se lea "centro de ski" y no "cerro nevado" son cuatro cosas, en este orden:
  1. la **pista pisada**: la huella del pisanieve, un acordonado fino y parejo que no existe en
     la nieve virgen de al lado. Es la firma del lugar;
  2. el **andarivel** cruzando a media distancia, con sus torres, el cable y las sillas: es lo
     único que dice que la montaña está en uso;
  3. las **balizas** al borde de la pista y las huellas de esquí que bajan de la terraza;
  4. la **cordillera** del fondo con más pistas abiertas entre el bosque.

La receta de nieve es la de Peumo y no se toca (RECETA.md §5): subsurface en el material, un
rebote difuso más y exposición baja. Lo que sí cambia es la bruma, que acá tiene que dejar ver
lejos —es una ladera abierta, no un bosque— y la cordillera del fondo.
"""
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
import bmesh
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"vista": "izq", "out": "//cuadro.png", "res": "720x1280", "samples": "32", "still": "1",
        "wb": "6250", "save": None, "dof": "1",
        "nevada": "1.0", "tramo": "s1",
        "carga": "1.0", "techo": "0.28", "techo_modo": "capa"}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(23)
ROOT = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.join(ROOT, "assets", "roble", "casa.blend")
PH = os.path.join(ROOT, "assets", "nieve", "ph")   # modelos CC0 (tools/get_assets_nieve.sh)
HDRI = os.path.join(ROOT, "assets", "hdri", "nieve", "horn-koppe_snow_2k.exr")  # CC0
# Sol de montaña, no día nublado. PENDIENTES.md recomendaba el cielo nublado porque perdona el
# ruido, pero la escena salía gris y plomiza: la casa tiene que dar ganas de ir a desconectarse,
# y eso lo hace el sol sobre la nieve —luz cálida en la cara de la casa, sombras largas y azules,
# troncos a contraluz—, no una luz plana.
# De los seis HDRI de nieve se eligió horn-koppe_snow, que es el de sol más fuerte y más alto
# (28,2°). Con los de sol rasante la nieve horizontal recibía tan poca luz directa que el ambiente
# se la comía y no había sombras: en una escena casi toda horizontal, la elevación del sol manda.
HDRI_SUN_U = 0.6000          # columna del sol en el HDRI (0-1), medida con tools/medir_sol_hdri.py
SUN_ELEV = 28.2              # elevación del sol en el HDRI
SKY_GAIN = 0.05              # brillo del cielo físico (horizonte) para empatar con el HDRI
AMBIENTE = 1.00              # cuánto del cielo ilumina (lo que ve la cámara no cambia)
# El azimut se mide desde +Y hacia +X. El testero vidriado mira a -Y, así que para que el sol le
# dé en la cara —y no lo deje a contraluz, que es lo que pasaba con el azimut heredado de Huingán—
# tiene que estar en el hemisferio -Y. Y bien corrido al costado: con el sol de frente, la
# sombra de la casa cae detrás y no se ve. A 300° le da de refilón al testero y tira la
# sombra cruzando la nieve hacia el otro lado, que es lo que se quiere ver.
SUN_AZ = 300.0
WB_TEMP = float(opts["wb"])
L, D = 8.79, 16.81           # ancho y fondo del casco (terraza + caja + porch)
HC = Vector((L / 2, D / 2))  # centro de la casa en planta
GROUND = 0.0                 # terreno bajo la casa (base de los pilotes)
PISO = 0.55                  # piso terminado
PISO2 = 3.26                 # segundo piso
CUMBRERA = (6.88, 6.55)      # x de la cumbrera y su altura
# Cotas de la fachada de acceso, medidas tirando rayos contra el modelo (no están en el STL como
# dato: hubo que buscarlas). El muro del acceso está en y = 14,76 y tiene **dos vanos abiertos**,
# modelados con sus jambas pero sin puerta ni ventana: en el render se leían como dos agujeros
# negros, que es lo que marcó la revisión. build_acceso() los cierra.
ACC_Y = 14.76                        # cara exterior del muro de acceso
VANO_PUERTA = (3.70, 4.43, 0.55, 2.56)    # x0, x1, z0, z1 — 0,73 x 2,01 m
VANO_VENT = (5.88, 7.30, 3.71, 5.11)      # x0, x1, z0, z1 — 1,42 x 1,40 m, segundo piso
TERRAZA_ACC = (1.25, 6.98, 19.60)         # x0, x1 y hasta dónde llega la terraza de entrada
# El claro tiene que dar para la órbita del dron. Con la casa de 9,5 x 13 m y lente de 30 mm, el
# encuadre adaptable deja la cámara a unos 31 m: si el claro es más chico que eso, el dron orbita
# por dentro del bosque y los árboles le tapan el lente. Así que el claro es grande, pero no es un
# potrero: adentro quedan renuevos, matas, tocones y algunos árboles grandes sueltos, y la franja
# por donde pasa la órbita es la única que va del todo despejada.
# En Peumo el bosque cerrado obligaba a abrir un claro. Acá es al revés: la ladera está abierta
# y lo que hay que decidir es hasta dónde **llega** el bosque. Queda a los costados de la pista y
# subiendo por el lomo de atrás, que es como se ve una ladera de centro de ski de verdad.
CLARO = 34.0                 # radio sin árboles grandes alrededor de la casa
ORBITA = (15.0, 46.0)        # franja radial por donde pasa el dron: sin árboles grandes
# La ladera es **asimétrica**, y no por gusto: la casa se posa en un hombro del cerro, con la
# caída fuerte por delante (la pista, que es lo que el testero mira) y una subida suave por
# detrás. Si se deja la misma pendiente para los dos lados, el talud de arriba sube catorce
# metros a veinte de la casa y el dron, que en s2 y s5 pasa a quince grados de elevación, se
# mete dentro del cerro. Medido: con 0,30 parejo, a 35 m cuesta arriba el terreno queda en 14 m
# y el dron en 10.
PEND = 0.30                  # pendiente hacia abajo, hacia -Y y la pista (17°)
PEND_ARR = 0.11              # pendiente hacia arriba, detrás de la casa (6°): el hombro del cerro
BANCO = (-9.0, 8.0)          # la plataforma nivelada: de y = HC.y - 9 a HC.y + 8
BANCO_X = 9.0                # y a 9 m a cada lado de la casa
BANCO_FUNDE = 17.0           # en cuántos metros la plataforma se funde con la ladera
PISTA_X = -19.0              # eje de la pista, a la izquierda de la casa (x negativo)
PISTA_W = 13.0               # semiancho de la pista pisada
# La nieve cae con viento: 25° de inclinación. Cayendo a plomo se ve falsa, y además en video el
# motion blur convierte cada copo en un hilo, y son esos hilos inclinados los que leen como nevada.
# La nieve se va acumulando a lo largo del video: empieza liviana y termina cargada, y en la
# quinta parte además está nevando. Aparte de contar algo, aligera las tres secciones más largas.
# No se acumula subiendo la densidad del esparcido —eso cambiaría los puntos y la nieve
# parpadearía de un cuadro a otro—: los puntos están fijos desde el principio y lo que crece es
# cuántos de ellos se muestran, con un sorteo estable por punto. Así los grumos que ya estaban
# no se mueven nunca y sólo van apareciendo los que faltan.
CARGA = (0.40, 1.0)          # carga de nieve al principio y al final del video
TECHO = float(opts["techo"])  # cuánta nieve queda en el techo; 0,28 es la elegida: los 28°
                              # descargan casi toda y queda una película que gana al alero
VIDEO_N = 1008               # cuadros del video completo (las cinco partes, s4 incluida)
VIDEO_G0 = {"s1": 0, "s2": 240, "s3": 432, "s5": 816}   # dónde empieza cada parte
VIENTO = Vector((0.82, 0.57, 0.0)).normalized()
VIENTO_TAN = 0.47            # tangente del ángulo con la vertical (25°)
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



def hielo_mat(name="Hielo"):
    """Hielo de carámbano: transmisión alta, apenas turbio y con el índice del hielo (1,31). Lo
    que lo hace leer no es el color sino que **transmita**: un carámbano opaco parece un diente."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.90, 0.95, 0.99, 1)
    b.inputs["Transmission Weight"].default_value = 0.92
    b.inputs["IOR"].default_value = 1.31
    b.inputs["Roughness"].default_value = 0.12
    tc = n.new("ShaderNodeTexCoord")
    bp = n.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.25
    l.new(N.noise(tc.outputs["Object"], 42.0, detail=4), bp.inputs["Height"])
    l.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


# ---------------------------------------------------------------- materiales de nieve y bosque
def snow_mat(name="Nieve", sss=0.16, rough=0.38, bump=0.5):
    """Nieve: lo decisivo es el subsurface. Sin translucidez la nieve se lee como yeso; con un
    scattering corto y apenas azulado aparece el brillo interno que la delata como nieve. El
    relieve son tres escalas de ruido (lomos de viento, grumos y grano) y el grano fino además
    pica la rugosidad, que es de dónde sale el destello.

    El peso del scattering está medido contra el reloj: la nieve llena casi toda la pantalla, así
    que casi todos los rayos de cámara pagan un camino aleatorio. Y en la nieve de ramas y techo
    va en cero: son grumos de dos centímetros, ahí no se distingue y se paga igual."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    v = tc.outputs["Object"]
    b.inputs["Base Color"].default_value = (0.90, 0.93, 0.97, 1)
    b.inputs["Subsurface Weight"].default_value = sss
    if sss:
        b.inputs["Subsurface Radius"].default_value = (0.09, 0.11, 0.17)  # el azul viaja más adentro
        b.inputs["Subsurface Scale"].default_value = 0.11
    b.inputs["IOR"].default_value = 1.31                                # hielo
    grano = N.noise(v, 90.0, detail=6, rough=0.7)
    l.new(N.math("ADD", N.math("MULTIPLY", rough, 1.0),
                 N.math("MULTIPLY", N.math("SUBTRACT", grano, 0.5), 0.55)), b.inputs["Roughness"])
    lomo = N.noise(v, 1.7, detail=4, rough=0.55)
    grumo = N.noise(v, 14.0, detail=5, rough=0.6)
    alt = N.math("ADD", N.math("MULTIPLY", lomo, 0.6),
                 N.math("ADD", N.math("MULTIPLY", grumo, 0.3), N.math("MULTIPLY", grano, 0.1)))
    bp = n.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.06
    l.new(alt, bp.inputs["Height"])
    l.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def terreno_mat(name="Terreno"):
    """Suelo: nieve y tierra en el mismo material, mezcladas por el atributo 'pelado' que calcula
    build_landscape. El borde entre una y otra no es la curva que dibuja el atributo sino esa
    curva mordida por dos escalas de ruido: la nieve no retrocede en línea limpia, se va en
    parches, y ese borde irregular es justamente lo que dice que alguien pisó ahí."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    out = n["Material Output"]
    tc = n.new("ShaderNodeTexCoord")
    v = tc.outputs["Object"]
    # --- la nieve, igual que snow_mat
    b.inputs["Base Color"].default_value = (0.90, 0.93, 0.97, 1)
    b.inputs["Subsurface Weight"].default_value = 0.16
    b.inputs["Subsurface Radius"].default_value = (0.09, 0.11, 0.17)
    b.inputs["Subsurface Scale"].default_value = 0.11
    b.inputs["IOR"].default_value = 1.31
    grano = N.noise(v, 90.0, detail=6, rough=0.7)   # la rugosidad se enlaza más abajo, con la pista
    lomo = N.noise(v, 1.7, detail=4, rough=0.55)
    grumo = N.noise(v, 14.0, detail=5, rough=0.6)
    alt = N.math("ADD", N.math("MULTIPLY", lomo, 0.6),
                 N.math("ADD", N.math("MULTIPLY", grumo, 0.3), N.math("MULTIPLY", grano, 0.1)))
    # --- el acordonado del pisanieve: la firma del centro de ski
    # La huella del rodillo son surcos paralelos cada veinte centímetros, en el sentido en que
    # bajó la máquina. No es un relieve profundo —a dos metros ya casi no se ve— pero contra el
    # sol rasante raya la pista entera de luz y sombra, y es exactamente lo que distingue una
    # pista de la nieve virgen de al lado. Va sobre la nieve lisa, no sobre los grumos: el
    # pisanieve justamente **borra** los grumos, así que donde hay acordonado se baja el relieve
    # natural en vez de sumarle uno nuevo.
    pis = n.new("ShaderNodeAttribute")
    pis.attribute_name = "pisado"
    # el borde del acordonado también se muerde con ruido: la máquina no pasa dos veces igual
    pisf = N.math("ADD", pis.outputs["Fac"],
                  N.math("MULTIPLY", N.math("SUBTRACT", N.noise(v, 4.5, detail=4), 0.5), 0.35))
    pisf = N.math("MINIMUM", N.math("MAXIMUM", pisf, 0.0), 1.0)
    onda = n.new("ShaderNodeTexWave")
    onda.wave_type = "BANDS"
    onda.bands_direction = "X"
    onda.wave_profile = "SIN"
    onda.inputs["Scale"].default_value = 5.0          # ~20 cm entre surcos
    onda.inputs["Distortion"].default_value = 1.4     # la máquina no baja en línea recta
    onda.inputs["Detail"].default_value = 2.0
    l.new(v, onda.inputs["Vector"])
    cord = N.math("ADD", N.math("MULTIPLY", onda.outputs["Fac"], 0.42),
                  N.math("MULTIPLY", grano, 0.08))
    alt = N.mix(pisf, alt, cord)
    bp = n.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.5
    bp.inputs["Distance"].default_value = 0.06
    l.new(alt, bp.inputs["Height"])
    l.new(bp.outputs["Normal"], b.inputs["Normal"])
    # la pista pisada además es más lisa que la nieve virgen: el rodillo la compacta
    l.new(N.math("SUBTRACT", N.math("ADD", 0.38, N.math("MULTIPLY", N.math("SUBTRACT", grano, 0.5), 0.55)),
                 N.math("MULTIPLY", pisf, 0.09)), b.inputs["Roughness"])
    # --- la tierra que asoma: barro oscuro con ripio y algo de pasto seco
    t = n.new("ShaderNodeBsdfPrincipled")
    piedra = N.noise(v, 55.0, detail=6, rough=0.75)
    barro = N.noise(v, 6.0, detail=5, rough=0.6)
    col = N.mix(barro, (0.070, 0.047, 0.030), (0.125, 0.090, 0.055))
    col = N.mix(N.smooth(piedra, 0.70, 0.84), col, (0.145, 0.128, 0.108))    # ripio claro
    # y una veta gris de roca: el mismo shader hace de tierra pisada abajo y de farellón arriba,
    # así que no puede ser sólo barro marrón
    col = N.mix(N.smooth(N.noise(v, 1.8, detail=6, rough=0.7), 0.42, 0.66), col,
                (0.105, 0.102, 0.098))
    col = N.mix(N.smooth(N.noise(v, 3.2, detail=4), 0.60, 0.78), col, (0.215, 0.165, 0.080))  # pasto seco
    l.new(col, t.inputs["Base Color"])
    t.inputs["Roughness"].default_value = 0.92
    bt = n.new("ShaderNodeBump")
    bt.inputs["Strength"].default_value = 0.8
    bt.inputs["Distance"].default_value = 0.04
    l.new(piedra, bt.inputs["Height"])
    l.new(bt.outputs["Normal"], t.inputs["Normal"])
    # --- la mezcla: el atributo, mordido por ruido para que el borde sea irregular
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "pelado"
    mordido = N.math("ADD", at.outputs["Fac"],
                     N.math("ADD", N.math("MULTIPLY", N.math("SUBTRACT", N.noise(v, 7.0, detail=5), 0.5), 0.55),
                            N.math("MULTIPLY", N.math("SUBTRACT", N.noise(v, 26.0, detail=5), 0.5), 0.3)))
    # --- roca de montaña, con shader propio
    # Antes la roca era el **mismo** barro del camino, y eso se notaba: un farellón a un
    # kilómetro no es marrón de tierra pisada, es gris azulado y mucho más quebrado. Con shader
    # propio además se puede subirle el relieve sin ensuciar el camino, que es plano.
    rk = n.new("ShaderNodeBsdfPrincipled")
    rg = N.noise(v, 2.6, detail=8, rough=0.72)
    rfino = N.noise(v, 16.0, detail=7, rough=0.70)
    rcol = N.mix(rg, (0.052, 0.050, 0.055), (0.115, 0.112, 0.118))
    rcol = N.mix(N.smooth(rfino, 0.52, 0.78), rcol, (0.165, 0.158, 0.150))   # vetas claras
    l.new(rcol, rk.inputs["Base Color"])
    rk.inputs["Roughness"].default_value = 0.88
    brk = n.new("ShaderNodeBump")
    brk.inputs["Strength"].default_value = 0.9
    brk.inputs["Distance"].default_value = 0.35
    l.new(N.math("ADD", N.math("MULTIPLY", rg, 0.7), N.math("MULTIPLY", rfino, 0.3)),
          brk.inputs["Height"])
    l.new(brk.outputs["Normal"], rk.inputs["Normal"])
    # --- bosque pintado de los faldones del fondo (ver bosque_lejano)
    bq = n.new("ShaderNodeBsdfPrincipled")
    bn = N.noise(v, 22.0, detail=7, rough=0.65)
    bcol = N.mix(bn, (0.0135, 0.0225, 0.0155), (0.030, 0.042, 0.029))
    bcol = N.mix(N.smooth(N.noise(v, 7.0, detail=6), 0.58, 0.80), bcol, (0.085, 0.098, 0.092))
    l.new(bcol, bq.inputs["Base Color"])
    bq.inputs["Roughness"].default_value = 0.92
    bbq = n.new("ShaderNodeBump")
    bbq.inputs["Strength"].default_value = 0.65
    bbq.inputs["Distance"].default_value = 0.6
    l.new(bn, bbq.inputs["Height"])
    l.new(bbq.outputs["Normal"], bq.inputs["Normal"])
    # --- la pendiente: **en un farellón la nieve no se sostiene ni crece bosque**. Es lo que
    # hace que los cerros dejen de leerse como conos de merengue. El umbral va en 0,76 de normal
    # vertical (unos 40°) y satura en 0,48 (61°).
    geo = n.new("ShaderNodeNewGeometry")
    nrm = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["Normal"], nrm.inputs[0])
    empinado = N.smooth(N.math("ABSOLUTE", nrm.outputs["Z"]), 0.76, 0.48)   # al revés: 1 = parado
    empinado = N.math("MULTIPLY", empinado,
                      N.math("ADD", 0.72, N.math("MULTIPLY", N.noise(v, 12.0, detail=5), 0.55)))
    # ...y por **altura**. Sólo con la pendiente, el macizo del fondo seguía saliendo blanco
    # entero: su cara principal no es un farellón, así que no pasaba el umbral, y una cumbre de
    # seiscientos metros toda nevada de la base al filo se ve como un merengue. Arriba de los
    # 300 m la roca empieza a ganar y la nieve queda en las canaletas, que es lo que se ve de
    # verdad; el ruido que lo muerde es el que dibuja esas canaletas.
    zxyz = n.new("ShaderNodeSeparateXYZ")
    l.new(v, zxyz.inputs[0])
    alto = N.math("MULTIPLY", N.smooth(zxyz.outputs["Z"], 300.0, 560.0),
                  N.smooth(N.noise(v, 5.5, detail=6, rough=0.65), 0.32, 0.62))
    empinado = N.math("MAXIMUM", empinado, alto)
    empinado = N.math("MINIMUM", N.math("MAXIMUM", empinado, 0.0), 1.0)
    # el bosque, mordido por ruido y apagado donde la pared está parada
    atb = n.new("ShaderNodeAttribute")
    atb.attribute_name = "bosque"
    bfac = N.math("ADD", atb.outputs["Fac"],
                  N.math("MULTIPLY", N.math("SUBTRACT", N.noise(v, 3.5, detail=6), 0.5), 0.75))
    bfac = N.math("MULTIPLY", N.smooth(bfac, 0.34, 0.62),
                  N.math("SUBTRACT", 1.0, empinado))
    # --- el apilado: nieve -> tierra pisada -> bosque -> roca
    m1 = n.new("ShaderNodeMixShader")
    l.new(N.smooth(mordido, 0.46, 0.74), m1.inputs[0])
    l.new(b.outputs[0], m1.inputs[1])
    l.new(t.outputs[0], m1.inputs[2])
    m2 = n.new("ShaderNodeMixShader")
    l.new(bfac, m2.inputs[0])
    l.new(m1.outputs[0], m2.inputs[1])
    l.new(bq.outputs[0], m2.inputs[2])
    m3 = n.new("ShaderNodeMixShader")
    l.new(empinado, m3.inputs[0])
    l.new(m2.outputs[0], m3.inputs[1])
    l.new(rk.outputs[0], m3.inputs[2])
    l.new(m3.outputs[0], out.inputs["Surface"])
    return m


def bark_mat(name="Corteza", c1=(0.085, 0.065, 0.052), c2=(0.028, 0.024, 0.022)):
    """Corteza oscura y vertical: el bosque tiene que leerse oscuro contra la nieve."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (7.0, 7.0, 0.55)    # estirado en Z: vetas verticales
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    f = N.noise(mp.outputs["Vector"], 9.0, detail=6, rough=0.75)
    l.new(N.mix(f, c1, c2), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    bp = n.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    l.new(f, bp.inputs["Height"])
    l.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def foliage_mat(name, c1, c2, translucent=0.3):
    """Follaje de conífera: verde muy oscuro y algo translúcido, para que el borde de la copa
    se encienda contra el cielo y no quede un recorte plano."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    f = N.noise(tc.outputs["Object"], 11.0, detail=5, rough=0.6)
    l.new(N.mix(f, c1, c2), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.78
    tr = n.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = (c1[0] * 1.5, c1[1] * 1.9, c1[2] * 1.3, 1)
    mixs = n.new("ShaderNodeMixShader")
    mixs.inputs[0].default_value = translucent
    out = n["Material Output"]
    l.new(b.outputs[0], mixs.inputs[1])
    l.new(tr.outputs[0], mixs.inputs[2])
    l.new(mixs.outputs[0], out.inputs["Surface"])
    return m


def materials():
    M = {}
    M["chapa"] = ribbed_metal("ChapaNegra", pitch=0.30, rib=0.035, flank=0.018, axis="Y")
    M["fachada"] = boards_mat("MaderaFachada", (0.33, 0.21, 0.115), (0.24, 0.145, 0.075), "Z", 10.0)
    M["cielo"] = boards_mat("MaderaCielo", (0.38, 0.25, 0.14), (0.29, 0.18, 0.095), "Y", 9.0)
    M["deck"] = boards_mat("Deck", (0.26, 0.17, 0.095), (0.185, 0.115, 0.062), "Y", 7.0, rough=0.72)
    M["piso"] = boards_mat("PisoInterior", (0.40, 0.27, 0.155), (0.31, 0.20, 0.11), "Y", 8.0, rough=0.5)
    M["muroint"] = boards_mat("MuroInterior", (0.46, 0.33, 0.20), (0.38, 0.26, 0.15), "Z", 9.0)
    M["vidrio"] = glass_mat()
    M["hormigon"] = principled("Hormigon", (0.21, 0.205, 0.195), 0.9)
    M["nieve"] = terreno_mat()
    M["nieve_rama"] = snow_mat("NieveRama", sss=0.0, rough=0.33, bump=0.8)
    M["copo"] = principled("Copo", (0.95, 0.96, 0.98), 0.6)
    # la nieve del techo lleva material propio, aparte de la de los árboles: así el corte de la
    # sección 3 se la puede llevar junto con el techo. Con el material compartido, al cortar la
    # casa quedaba una losa blanca flotando que tapaba los recintos, y la nieve de todo el bosque
    # se habría cortado también.
    M["nieve_techo"] = snow_mat("NieveTecho", sss=0.0, rough=0.33, bump=0.8)
    M["corteza"] = bark_mat()
    M["corteza_clara"] = bark_mat("CortezaClara", (0.16, 0.135, 0.105), (0.06, 0.05, 0.042))
    M["follaje"] = foliage_mat("Follaje", (0.022, 0.048, 0.024), (0.010, 0.025, 0.014))
    M["follaje2"] = foliage_mat("Follaje2", (0.030, 0.052, 0.028), (0.014, 0.030, 0.017))
    M["lejos"] = principled("BosqueLejos", (0.055, 0.070, 0.062), 0.9)
    # el centro de ski: acero galvanizado de las torres, asientos y balizas
    M["torre"] = principled("TorreAcero", (0.145, 0.150, 0.155), 0.42, metal=0.85)
    M["silla"] = principled("SillaAndarivel", (0.055, 0.075, 0.105), 0.55)
    M["baliza"] = principled("Baliza", (0.52, 0.17, 0.035), 0.65)
    # nieve compactada del surco de un esquí: más lisa y un punto más azul que la de al lado
    M["nieve_huella"] = snow_mat("NieveHuella", sss=0.14, rough=0.26, bump=0.35)
    M["hielo"] = hielo_mat()
    # hoja de la puerta de acceso: tablas verticales, más oscuras que la fachada, para que la
    # puerta se recorte contra el frontón claro en vez de confundirse con él
    M["puerta_acc"] = boards_mat("PuertaAcceso", (0.145, 0.088, 0.048), (0.098, 0.058, 0.030),
                                 "Z", 14.0, rough=0.55)
    M["acero"] = principled("AceroManilla", (0.56, 0.57, 0.58), 0.28, metal=1.0)
    M["decknegro"] = principled("DeckBorde", (0.045, 0.042, 0.038), 0.7)
    return M


def load_house(M):
    """Casa del STL con los materiales de la escena (por nombre de material del .blend)."""
    with bpy.data.libraries.load(CASA) as (a, b):
        b.objects = a.objects
    swap = {"Ro_ChapaNegra": M["chapa"], "Ro_MaderaFachada": M["fachada"], "Ro_MaderaCielo": M["cielo"],
            "Ro_Deck": M["deck"], "Ro_PisoInterior": M["piso"], "Ro_MuroInterior": M["muroint"],
            "Ro_Vidrio": M["vidrio"], "Ro_Pilote": M["hormigon"],
            # El paño alto del muro largo salió clasificado como vidrio de tragaluz (oscuro)
            # porque el plano del faldón, prolongado, pasa a menos de un metro de él: es la misma
            # trampa que documenta el extractor. Es una **ventana de fachada**, así que acá se le
            # devuelve el vidrio normal. El extractor ya quedó corregido para la próxima vez que
            # se extraiga la casa; no se volvió a correr sólo por esto, que tarda más de una hora.
            "Ro_VidrioTecho": M["vidrio"]}
    coll = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(coll)
    for o in b.objects:
        coll.objects.link(o)
        for sl in o.material_slots:
            if sl.material and sl.material.name in swap:
                sl.material = swap[sl.material.name]
    # nieve en el techo: una capa modelada, no grumos. Los 32° del faldón corto la descargan
    # solos —es el enganche de la casa: la forma triangular impide que la nieve se acumule—, así
    # que no es un manto parejo sino una cuña con fajas desprendidas.
    casco = next((o for o in coll.objects if "Casco" in o.name), None)
    if casco and TECHO > 0.001:
        if opts["techo_modo"] == "grano":
            # nieve granulada: muchísimos granos chicos, no las bolitas de las ramas
            nevar(casco, M, dens=2600.0 * TECHO, tam=0.018, umbral=0.5,
                  solo=M["chapa"], mat="nieve_techo")
        else:
            nieve_sobre_techo(casco, M)
    # luces interiores tibias: con el día nublado afuera, son las que hacen que el ventanal
    # se lea como una casa habitada y no como un vidrio apagado
    # (banda de día contra el testero, comedor, cocina, dormitorio-2, el 2do piso y el escritorio)
    for x, y, z, p in ((3.0, 5.6, 2.3, 150), (3.4, 8.2, 2.3, 90), (2.4, 11.2, 2.2, 70),
                       (7.3, 5.0, 2.1, 60), (6.0, 5.4, 4.8, 90), (7.0, 12.0, 4.8, 50)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.0
        lt.data.color = (1.0, 0.70, 0.42)
    return coll


# ---------------------------------------------------------------- terreno
def claro_d(x, y):
    """Distancia al entorno despejado de la casa, en una elipse estirada hacia -Y: hacia abajo se
    abre más, porque lo que el testero tiene para mirar es la bajada."""
    dx = (x - HC.x) / 1.1
    dy = (y - HC.y) / (1.5 if y < HC.y else 1.05)
    return math.hypot(dx, dy)


def cam_dist(x, y):
    """Distancia en planta a la toma más cercana. Un árbol a quince metros encuadra; uno a dos
    metros tapa la casa entera, así que alrededor de cada cámara el bosque se abre."""
    return min(math.hypot(x - v[0][0], y - v[0][1]) for v in VISTAS.values())


def house_dist(x, y):
    """Distancia (m) al rectángulo de la casa (con un margen de 0,5 m)."""
    dx = max(-0.5 - x, 0, x - (L + 0.5))
    dy = max(-0.5 - y, 0, y - (D + 0.5))
    return math.hypot(dx, dy)


# ------------------------------------------------------------------------ la pista
def pista_cx(y):
    """Eje de la pista a la altura y. No baja recta: una pista sigue la línea de máxima pendiente
    pero se va corriendo con el terreno, y esa curva es lo que la hace leer como pista y no como
    una franja pintada."""
    t = (y - HC.y) / 70.0
    return PISTA_X + 7.0 * t + 4.5 * math.sin(t * 1.5 + 0.6)


def pista_w(y):
    """Semiancho: la pista se abre hacia abajo, como un embudo. Arriba, donde sale del bosque,
    es angosta; a la altura de la casa ya está ancha."""
    t = max(0.0, min(1.0, (HC.y + 55.0 - y) / 120.0))
    return PISTA_W * (0.62 + 0.55 * t)


def pista_d(x, y):
    """Distancia al borde de la pista (0 dentro). El borde no es recto: lo muerde un ruido suave,
    porque el pisanieve no pasa dos veces por la misma línea."""
    m = 1.2 * noise.noise(Vector((x / 9.0, y / 9.0, 71.0)))
    return max(0.0, abs(x - pista_cx(y)) - pista_w(y) + m)


def camino_d(x, y):
    """Camino de acceso: llega al porch **contorneando la ladera** desde +X, no subiendo de
    frente. En un cerro el camino va por la curva de nivel; uno que suba derecho por la pendiente
    se ve dibujado encima."""
    if y > D + 2.0:
        t = max(0.0, min(1.0, (y - (D + 2.0)) / 30.0))
        px = L * 0.65 + 16.0 * t + 6.0 * math.sin(t * 2.2)
        return math.hypot(x - px, 0.0)
    t = max(0.0, min(1.0, (x - (L + 1.0)) / 34.0))
    py = D + 2.0 + 2.5 * t * t
    return math.hypot(0.0, y - py) if x > L + 1.0 else math.hypot(x - (L + 1.0), y - py)


def esqui_d(x, y):
    """Huellas de esquí: bajan de la escalera de la terraza, cruzan la plataforma y se meten en
    la pista. Son dos surcos paralelos, no una vereda: es lo que dice que de acá se sale
    esquiando."""
    u = max(0.0, min(1.0, (HC.y - 4.0 - y) / 26.0))
    qx = L * 0.30 - 13.0 * u ** 1.4 + 2.0 * math.sin(u * 3.2)
    d = math.hypot(x - qx, 0.0) if y < HC.y - 4.0 else math.hypot(x - qx, y - (HC.y - 4.0))
    return abs(d - 0.42)          # dos surcos separados 84 cm, no uno solo


def explanada_d(x, y):
    """Explanada despejada frente al acceso: donde se estaciona y se pala la nieve."""
    # Llega hasta delante de la puerta y pasa la terraza de entrada: lo que se pala es todo el
    # frente de acceso, no sólo donde se estaciona. Además así el terreno queda hundido bajo la
    # terraza nueva y no asoma por encima de las tablas.
    dx = max(1.0 - x, 0.0, x - (L + 7.5))
    dy = max(D - 1.0 - y, 0.0, y - (D + 5.4))
    return math.hypot(dx, dy)


def path_dist(x, y):
    """Distancia a lo pisado por gente o máquinas: camino, explanada, huellas de esquí o pista."""
    return min(camino_d(x, y), explanada_d(x, y), esqui_d(x, y), pista_d(x, y))


def pisado(x, y):
    """Cuánto de pisanieve tiene el suelo, de 0 (nieve virgen) a 1 (pista acordonada). Es el
    atributo que terreno_mat usa para dibujar el acordonado, y es la firma del lugar: la pista
    pisada al lado de la nieve virgen es lo que no se ve en un cerro cualquiera."""
    v = 0.0
    d = pista_d(x, y)
    if d < 6.0:
        v = max(v, min(1.0, (1.0 - d / 6.0) ** 0.5))
    # la plataforma de la casa también está pisada, pero menos: la pisa el pisanieve chico
    pl = max(house_dist(x, y) - 2.0, 0.0)
    if pl < 9.0:
        v = max(v, 0.45 * (1.0 - pl / 9.0))
    return max(0.0, min(1.0, v))


def pelado(x, y):
    """Cuánto suelo asoma bajo la nieve, de 0 (nieve limpia) a 1 (tierra pelada). En la pista
    **nunca**: una pista con tierra a la vista está cerrada.

    Los valores son mucho más bajos que en Peumo, y no es un ajuste de gusto. A la cota de un
    centro de ski el camino se mantiene **con nieve pisada**, no pelado hasta la tierra: lo que
    se ve es el hundido y los lomos de nieve palada que modela hundir_huella, no barro. Con los
    valores del bosque (0,62 en el camino, 0,58 en la explanada) el atributo quedaba justo en el
    medio de la rampa con que terreno_mat mezcla nieve y tierra, y el ruido que le muerde el
    borde lo cruzaba de un lado al otro píxel a píxel: en la toma del acceso salía un moteado
    sucio del tamaño de media pantalla, que se leía como ruido de render y no como camino.
    Bajados a 0,22 y 0,26 el atributo se queda casi siempre por debajo de la rampa y sólo asoma
    tierra en manchones sueltos, que es lo que se quería."""
    v = 0.0
    c = camino_d(x, y)
    if c < 1.9:
        v = max(v, 0.22 * (1.0 - c / 1.9) ** 0.7)
    e = explanada_d(x, y) - 0.9 * noise.noise(Vector((x / 2.6, y / 2.6, 53.0)))
    if e < 2.0:
        v = max(v, 0.26 * (1.0 - max(e, 0.0) / 2.0) ** 0.8)
    # los lomos que el viento barre, sólo fuera de la pista y fuera de la plataforma
    lomo = noise.noise(Vector((x / 13.0, y / 13.0, 41.0)))
    if lomo > 0.46 and pista_d(x, y) > 4.0 and house_dist(x, y) > 14.0:
        v = max(v, min(0.10, (lomo - 0.46) * 1.2))
    return max(0.0, min(1.0, v))


def bosque_lejano(x, y):
    """Cuánto bosque se ve pintado en el terreno, de 0 a 1. Es sólo para la cordillera del fondo.

    El bosque instanciado llega hasta los 440 m, que es donde termina la malla de la ladera; de
    ahí para afuera los cerros quedaban blancos de la base a la cumbre, y una montaña nevada sin
    una sola mancha de bosque en los faldones se lee como maqueta. Poner árboles de verdad a un
    kilómetro y medio no tiene sentido —no se distinguen y cuestan carísimo—, así que ahí el
    bosque va **pintado en el material**: una mancha oscura bajo la línea de árboles, mordida por
    ruido para que el borde sea irregular, y el propio shader la saca de las caras empinadas,
    donde no crece nada.

    La línea de árboles está a 180 m sobre la casa y se apaga en 70: arriba, roca y nieve.
    Arranca a los 300 m para **solaparse** con el bosque instanciado, que llega a 440: si las dos
    líneas sólo se tocan, en el medio queda una franja blanca que no es ni una cosa ni la otra."""
    r = math.hypot(x - HC.x, y - HC.y)
    if r < 300.0:
        return 0.0
    cerca = min(1.0, (r - 300.0) / 110.0)
    alt = ladera_h(x, y) + cordillera_h(x, y)
    linea = min(1.0, max(0.0, (180.0 - alt) / 70.0))
    # y no baja hasta el fondo del valle parejo: se abre en manchones
    mancha = 0.55 + 1.05 * noise.noise(Vector((x / 160.0, y / 160.0, 61.0)))
    return max(0.0, min(1.0, cerca * linea * mancha))


def ladera_h(x, y):
    """La ladera desnuda, sin la plataforma de la casa. Baja fuerte hacia -Y (la pista) y sube
    suave hacia +Y: la casa está en un hombro del cerro, no en medio de una rampa. Encima lleva
    tres escalas de ondulación —los lomos y las canaletas que tiene cualquier ladera."""
    dy = y - (HC.y + BANCO[0])
    h = PEND * dy if dy < 0 else PEND_ARR * dy
    # la ladera no es un plano inclinado: tiene lomos, canaletas y un cambio de pendiente
    h += (2.6 * noise.noise(Vector((x / 48.0, y / 48.0, 0.7)))
          + 0.95 * noise.noise(Vector((x / 17.0, y / 17.0, 3.1)))
          + 0.30 * noise.noise(Vector((x / 5.5, y / 5.5, 6.4))))
    # abajo la pendiente se suaviza al llegar al fondo del valle (de 0,30 a 0,14: se le **resta**
    # lo que ya se contó de más, que con el signo al revés hundía el valle a 700 m); arriba se
    # empina otra vez pasado el hombro, que es por donde sigue subiendo el cerro
    if dy < -80.0:
        h -= 0.16 * (dy + 80.0)
    if dy > 55.0:
        h += 0.21 * (dy - 55.0)
    # y cae también hacia la pista (-X): el hombro se asoma sobre la bajada
    dx = x - (L + BANCO_X)
    if dx < 0.0:
        h += 0.055 * dx * min(1.0, max(0.0, (HC.y + 40.0 - y) / 25.0))
    return h


def _aristas(x, y, esc, octavas=5, lac=2.13, gain=0.52, z=0.0):
    """Ruido de aristas (*ridged multifractal*): en vez de bultos redondos da **filos**.

    El ruido de Perlin común es una sábana de lomos y hoyos suaves, y por eso una montaña hecha
    con él sale como un merengue: lisa y redonda. Tomando 1 − |ruido| el cero del ruido pasa a
    ser un máximo con quiebre —una arista— y elevándolo al cuadrado el quiebre se afila y los
    faldones se vacían hacia abajo, que es justo la forma de un cordón: filos angostos y circos
    anchos entre medio. Las octavas van sumando aristas más chicas sobre las grandes."""
    v = w = 0.0
    a, f = 1.0, 1.0
    for k in range(octavas):
        n = 1.0 - abs(noise.noise(Vector((x / esc * f, y / esc * f, z + k * 3.7))))
        v += n * n * a
        w += a
        a *= gain
        f *= lac
    return v / w


def cordillera_h(x, y):
    """Los cerros del fondo. Es lo que da la escala de centro de ski: la casa está en una ladera
    y detrás tiene que haber montaña de verdad, no una loma. Arrancan a 420 m —más allá de donde
    llega la malla del terreno cercano— y suben hasta unos 700; la bruma de lejanía del
    compositor los funde con el cielo.

    La forma la da `_aristas`, no el ruido suave que había antes: con ruido suave, por muchas
    octavas que se le sumen, los cerros salen como conos blancos redondos. Con aristas aparecen
    los filos, los circos y los portezuelos, que es lo que el ojo reconoce como cordillera.

    Van en su propia malla (build_landscape), a 12 m de paso: a esa distancia parece mucho, pero
    con 26 m las aristas no se alcanzaban a dibujar y el perfil quedaba facetado contra el cielo."""
    r = math.hypot(x - HC.x, y - HC.y)
    if r < 400.0:
        return 0.0
    t = min(1.0, (r - 400.0) / 950.0)
    # el macizo: dónde hay cordón y dónde valle, en escala de kilómetro
    macizo = 0.42 + 0.88 * noise.noise(Vector((x / 700.0, y / 700.0, 9.2)))
    macizo = max(0.12, macizo)
    # los cordones, con sus filos; y una segunda capa más chica para las aristas secundarias
    cordon = _aristas(x, y, 430.0, octavas=4, z=15.5)
    detalle = _aristas(x, y, 130.0, octavas=4, gain=0.46, z=27.8)
    # El exponente decide si el cordón es un macizo ancho o una fila de agujas. Con 1,45 salían
    # agujas todas iguales, como dientes; con 1,12 queda la masa del macizo y los filos encima,
    # que es como se ve un cordón de verdad.
    forma = cordon ** 1.12 * (0.84 + 0.34 * detalle)
    h = 700.0 * t ** 1.30 * macizo * forma
    # los circos y las canaletas que bajan de los filos, ya en escala de ladera
    h -= 34.0 * t * (1.0 - detalle) ** 2
    return max(0.0, h)


def terrain_h(x, y):
    """Terreno: la plataforma nivelada donde se posa la casa, fundida con la ladera alrededor, y
    la cordillera al fondo. La plataforma es lo que hace que la casa no quede torcida en la
    pendiente; el talud de atrás y el borde de abajo cuentan que se cortó el cerro."""
    # cuánto manda la plataforma: 1 sobre el banco, 0 al borde del fundido
    dx = max(-BANCO_X - x, 0.0, x - (L + BANCO_X))
    dy = max((HC.y + BANCO[0]) - y, 0.0, y - (HC.y + BANCO[1]))
    d = math.hypot(dx, dy)
    w = 1.0 - min(1.0, max(0.0, d / BANCO_FUNDE)) ** 0.8
    h = ladera_h(x, y) * (1.0 - w)
    # Aun en la plataforma la nieve ondula: ventisqueros bajos. Sin esto el primer plano es una
    # mesa de billar blanca y delata que es CG. Pero **bajo la casa casi no**: con la ondulación
    # entera, las cuatro esquinas de la planta daban 59 cm de desnivel y la casa quedaba con una
    # esquina enterrada y la otra en el aire. Bajo la huella de la casa se deja un cuarto.
    sopla = (0.34 * noise.noise(Vector((x / 7.5, y / 7.5, 11.3)))
             + 0.15 * noise.noise(Vector((x / 2.6, y / 2.6, 14.7)))
             + 0.05 * noise.noise(Vector((x / 1.1, y / 1.1, 18.2))))
    bajo_casa = 1.0 - 0.75 * min(1.0, max(0.0, 1.0 - house_dist(x, y) / 3.5))
    h += sopla * (0.40 + 0.60 * w) * bajo_casa
    # Sastrugi: los lomos que el viento labra en la nieve abierta, estirados en el sentido en que
    # sopla. No son el ruido redondo de arriba —son **crestas**, con un lado tallado y otro en
    # pendiente—, y por eso se hacen con el mismo truco de aristas que los cordones. Es lo que
    # evita que la nieve virgen de fuera de la pista se vea como una rampa de yeso lisa. No van
    # ni en la pista (el pisanieve las borra) ni en la plataforma de la casa.
    libre = min(1.0, pista_d(x, y) / 5.0) * min(1.0, max(0.0, (house_dist(x, y) - 5.0) / 7.0))
    if libre > 0.01:
        u = x * VIENTO.x + y * VIENTO.y            # a favor del viento
        t_ = -x * VIENTO.y + y * VIENTO.x          # cruzado
        sas = _aristas(u * 0.55, t_ * 2.6, 3.4, octavas=3, gain=0.45, z=47.0)
        h += 0.16 * libre * (sas - 0.45)
    h += cordillera_h(x, y)
    # la nieve se amontona contra la casa y sube por los pilotes
    hd = house_dist(x, y)
    if hd < 6.0:
        amontona = (1.0 - hd / 6.0) ** 2
        amontona *= min(1.0, max(0.0, (min(camino_d(x, y), explanada_d(x, y)) - 1.6) / 2.0))
        h += (0.55 + 0.20 * noise.noise(Vector((x / 3.0, y / 3.0, 31.0)))) * amontona
    return h + GROUND


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


def build_landscape(M):
    """Suelo nevado: malla fina en la plataforma y la pista (donde se ven el acordonado y las
    huellas) y una gruesa hasta la cordillera del fondo. La gruesa llega mucho más lejos que en
    Peumo —460 m contra 230— porque acá no hay bosque que tape: la ladera se ve hasta el fondo."""
    coll = bpy.data.collections.new("Terreno")
    bpy.context.scene.collection.children.link(coll)
    cerca = grid("NieveCerca", -58.0, L + 46.0, -58.0, D + 46.0, 1.1, M["nieve"], coll)
    marcar(cerca)
    dentro = (lambda x, y: -58.0 <= x <= L + 46.0 and -58.0 <= y <= D + 46.0)
    lejos = grid("NieveLejos", -440.0, L + 440.0, -440.0, D + 440.0, 7.0, M["nieve"], coll,
                 skip=dentro, sink=dentro)
    marcar(lejos)
    # y la cordillera, en su propia malla. Va a 12 m de paso, no a 26: las aristas de los
    # cordones miden unos pocos vértices de ancho, y con el paso grueso el perfil contra el cielo
    # salía facetado en rectas largas, que es de lo que más canta que es 3D.
    medio = (lambda x, y: -440.0 <= x <= L + 440.0 and -440.0 <= y <= D + 440.0)
    cord = grid("Cordillera", -1700.0, L + 1700.0, -1700.0, D + 1700.0, 12.0, M["nieve"], coll,
                skip=medio, sink=medio)
    marcar(cord)
    hundir_huella(cerca)
    return cerca, lejos


def marcar(o):
    """Guarda por vértice los tres atributos con los que terreno_mat decide qué hay en el suelo:
    `pelado` (cuánta tierra asoma), `pisado` (cuánto pisanieve) y `bosque` (el bosque pintado de
    los faldones del fondo)."""
    me = o.data
    at = me.attributes.get("pelado") or me.attributes.new("pelado", "FLOAT", "POINT")
    at.data.foreach_set("value", [pelado(v.co.x, v.co.y) for v in me.vertices])
    at = me.attributes.get("pisado") or me.attributes.new("pisado", "FLOAT", "POINT")
    at.data.foreach_set("value", [pisado(v.co.x, v.co.y) for v in me.vertices])
    at = me.attributes.get("bosque") or me.attributes.new("bosque", "FLOAT", "POINT")
    at.data.foreach_set("value", [bosque_lejano(v.co.x, v.co.y) for v in me.vertices])


def hundir_huella(o):
    """Lo pisado no se dibuja, se hunde. El camino baja treinta centímetros y lo palado queda
    amontonado en dos lomos a los costados. La pista hace lo contrario de un camino: **se alisa**,
    porque el pisanieve corta los lomos y rellena los huecos, y ese alisado es justamente lo que
    la separa de la nieve virgen de al lado. Las huellas de esquí son dos surcos finos."""
    for v in o.data.vertices:
        x, y = v.co.x, v.co.y
        c = min(camino_d(x, y), explanada_d(x, y))
        if c < 4.2:
            v.co.z -= 0.30 * max(0.0, 1.0 - c / 2.4) ** 1.2
            v.co.z += 0.34 * max(0.0, 1.0 - abs(c - 3.0) / 1.2)     # el lomo de nieve palada
        p = pista_d(x, y)
        if p < 3.0:
            # alisado: se le quita la ondulación chica y queda el plano de la ladera
            k = (1.0 - p / 3.0) ** 0.7
            liso = (ladera_h(x, y) + 0.34 * noise.noise(Vector((x / 7.5, y / 7.5, 11.3)))
                    + cordillera_h(x, y) + GROUND)
            v.co.z += (liso - v.co.z) * 0.75 * k
            v.co.z += 0.12 * k * max(0.0, 1.0 - abs(p - 2.2) / 1.0)   # el cordón del borde
        e = esqui_d(x, y)
        if e < 0.5:
            v.co.z -= 0.09 * (1.0 - e / 0.5) ** 1.3
    o.data.update()


# ---------------------------------------------------------------- bosque nevado
def load_ph(lib, ident, nombres):
    """Objetos de un modelo de Poly Haven, en la biblioteca para instanciar. Se dejan en el
    origen, sin padre: los nodos de geometría los reparten después."""
    with bpy.data.libraries.load(os.path.join(PH, ident, ident + ".blend")) as (a, b):
        b.objects = [n for n in a.objects if n in set(nombres)]
    out = []
    for o in b.objects:
        lib.objects.link(o)
        o.location, o.rotation_euler, o.parent = (0, 0, 0), (0, 0, 0), None
        out.append(o)
    return out


def realizar(o):
    """Aplica los nodos de geometría del modelo: los árboles de Poly Haven instancian sus
    ramillas, y hay que concretarlas para poder acumularles nieve encima."""
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.convert(target="MESH")
    return bpy.context.object


def empolvar(o, M):
    """Nieve de los árboles del fondo: no es geometría, es el follaje aclarado. A más de cien
    metros con bruma nadie distingue un grumo de nieve de un tono más claro, y la geometría de
    miles de árboles nevados no entra en memoria.

    Aclarar no es reemplazar el material: las acículas son tarjetas con alfa, y cambiarles el
    material entero las dejaba opacas, lo que contra el cielo se veía como un moteado sucio en
    las copas. Se duplica el material una vez y se le mezcla blanco sólo al color base; el alfa
    y el resto del árbol de nodos quedan como estaban."""
    for sl in o.material_slots:
        m = sl.material
        if not m:
            continue
        claro = bpy.data.materials.get(m.name + "_nevado")
        if claro is None:
            claro = m.copy()
            claro.name = m.name + "_nevado"
            b = next((nd for nd in claro.node_tree.nodes
                      if nd.bl_idname == "ShaderNodeBsdfPrincipled"), None)
            if b:
                col = b.inputs["Base Color"]
                mix = claro.node_tree.nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"
                mix.inputs[0].default_value = 0.62        # cuánto blanco entra
                mix.inputs[7].default_value = (0.86, 0.89, 0.93, 1)
                if col.links:
                    claro.node_tree.links.new(col.links[0].from_socket, mix.inputs[6])
                else:
                    mix.inputs[6].default_value = col.default_value
                claro.node_tree.links.new(mix.outputs[2], col)
        sl.material = claro
    return o


def nevar(o, M, dens=110.0, tam=0.075, umbral=0.45, solo=None, mat="nieve_rama"):
    """Acumula nieve sobre lo que mira al cielo. La nieve no es una capa de pintura blanca: son
    grumos posados sobre las caras cuya normal apunta hacia arriba, con tamaño y giro al azar.
    El umbral deja los troncos y las caras verticales casi limpios, que es lo que pasa de verdad:
    la nieve se sostiene en las ramas, no en la corteza vertical. Con `solo` la nieve se limita
    a las caras de un material, que es como se le pone nieve al techo de la casa sin llenar de
    grumos el piso del living."""
    grumo = bpy.data.objects.new(o.name + "_grumo", bpy.data.meshes.new(o.name + "_grumo"))
    bpy.context.scene.collection.objects.link(grumo)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=0, radius=1.0, location=(0, 0, -900))
    src = bpy.context.object
    src.name = o.name + "_grumo"
    src.scale = (1.0, 1.0, 0.42)
    src.data.materials.append(M[mat])
    bpy.data.objects.remove(grumo, do_unlink=True)
    ng = bpy.data.node_groups.new("Nieve_" + o.name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])
    d = N.new("GeometryNodeDistributePointsOnFaces")
    d.inputs["Density"].default_value = dens
    Lk.new(gi.outputs[0], d.inputs["Mesh"])
    if solo is not None:
        msel = N.new("GeometryNodeMaterialSelection")
        msel.inputs["Material"].default_value = solo
        Lk.new(msel.outputs["Selection"], d.inputs["Selection"])
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(d.outputs["Normal"], sep.inputs[0])
    cmp = N.new("FunctionNodeCompare")
    cmp.operation = "LESS_THAN"
    cmp.inputs[1].default_value = umbral
    Lk.new(sep.outputs["Z"], cmp.inputs[0])
    # sorteo estable por punto: se borran los que caen por encima de la carga del momento
    rv = N.new("FunctionNodeRandomValue")
    rv.data_type = "FLOAT"
    rv.inputs[2].default_value, rv.inputs[3].default_value = 0.0, 1.0
    rv.inputs["Seed"].default_value = 97
    carga = N.new("ShaderNodeValue")
    carga.name = "Carga"
    carga.outputs[0].default_value = 1.0
    sin_nieve = N.new("FunctionNodeCompare")
    sin_nieve.operation = "GREATER_THAN"
    Lk.new(rv.outputs[1], sin_nieve.inputs[0])
    Lk.new(carga.outputs[0], sin_nieve.inputs[1])
    fuera = N.new("FunctionNodeBooleanMath")
    fuera.operation = "OR"
    Lk.new(cmp.outputs[0], fuera.inputs[0])
    Lk.new(sin_nieve.outputs[0], fuera.inputs[1])
    dele = N.new("GeometryNodeDeleteGeometry")
    dele.domain = "POINT"
    Lk.new(d.outputs["Points"], dele.inputs["Geometry"])
    Lk.new(fuera.outputs[0], dele.inputs["Selection"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = src
    esc = N.new("FunctionNodeRandomValue")
    esc.data_type = "FLOAT_VECTOR"
    esc.inputs[0].default_value = (tam * 0.5, tam * 0.5, tam * 0.3)
    esc.inputs[1].default_value = (tam * 1.8, tam * 1.8, tam * 1.0)
    crece = N.new("ShaderNodeVectorMath")      # y el grumo engorda con la carga
    crece.operation = "SCALE"
    Lk.new(esc.outputs["Value"], crece.inputs[0])
    med = N.new("ShaderNodeMath")
    med.operation = "MULTIPLY_ADD"
    med.inputs[1].default_value, med.inputs[2].default_value = 0.45, 0.55
    Lk.new(carga.outputs[0], med.inputs[0])
    Lk.new(med.outputs[0], crece.inputs["Scale"])
    rot = N.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT_VECTOR"
    rot.inputs[0].default_value = (0.0, 0.0, 0.0)
    rot.inputs[1].default_value = (0.35, 0.35, math.tau)
    Lk.new(dele.outputs[0], inst.inputs["Points"])
    Lk.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    Lk.new(crece.outputs[0], inst.inputs["Scale"])
    Lk.new(rot.outputs["Value"], inst.inputs["Rotation"])
    Lk.new(inst.outputs[0], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = o.modifiers.new("Nieve", "NODES")
    md.node_group = ng
    return o


def nieve_sobre_techo(casco, M):
    """Capa de nieve del techo, modelada en vez de esparcida.

    Los grumos sueltos daban una capa de bolitas que parecía plumavit. Acá la nieve es una sola
    pieza continua que se va en degradé: una cuña que arranca en nada en la cumbrera y engrosa
    contra el alero, donde se frena al deslizar, asomada por el borde en una cornisa que se dobla
    hacia abajo. Y donde adelgaza se vuelve translúcida y deja entrever la chapa, que es lo que
    hace que el degradé se lea; si la nieve termina de golpe, por fino que sea el borde, se ve
    como un bloque blanco apoyado encima. El degradé es parejo de la cumbrera al alero: cuando se
    concentraba arriba, el techo se partía en dos zonas en vez de leerse como una sola capa.

    Se construye duplicando las caras de chapa que miran al cielo, subdividiéndolas y corriendo
    cada vértice por su normal según ese espesor. El espesor queda guardado por vértice para que
    la acumulación del video la pueda animar sin rehacer la geometría."""
    mi = casco.data.materials.find(M["chapa"].name)
    src = bmesh.new()
    src.from_mesh(casco.data)
    caras = [f for f in src.faces
             if f.material_index == mi and f.normal.z > 0.35 and f.calc_center_median().z > 1.8]
    if not caras:
        src.free()
        return None
    bm = bmesh.new()
    mapa = {}
    for f in caras:
        vs = []
        for v in f.verts:
            if v.index not in mapa:
                mapa[v.index] = bm.verts.new(v.co)
            vs.append(mapa[v.index])
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    bm.verts.ensure_lookup_table()
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=10, use_grid_fill=True)
    bm.normal_update()
    zs = [v.co.z for v in bm.verts]
    z_cum, z_alero = max(zs), min(zs)
    espesor, velo = {}, {}
    for v in bm.verts:
        t = (v.co.z - z_alero) / max(z_cum - z_alero, 1e-6)
        t = 1.0 - t                                   # 0 en la cumbrera, 1 en el alero
        # La capa va entera y en degradé: el espesor baja hasta cero hacia la cumbrera, sin
        # cortes ni parches. Las fajas desprendidas se probaron y dejaban el techo parchado;
        # terminar la nieve de golpe la convertía en un bloque blanco pegado encima.
        e = 0.30 * TECHO * (0.10 + 0.90 * t)
        e *= 0.93 + 0.14 * noise.noise(Vector((v.co.x / 3.4, v.co.y / 3.4, 83.0)))
        espesor[v] = e
        # El velo decide cuánta chapa se ve, y crece mucho más lento que el espesor. Con un velo
        # lineal el degradé se agotaba en el primer tercio del faldón: la nieve es tan clara que
        # con medio velo ya se lee blanca. Elevado a 1,9 el cambio se reparte por todo el largo.
        velo[v] = TECHO * t ** 1.9
    # la cornisa: en el borde del alero la nieve sobresale y se dobla
    for v in bm.verts:
        if any(len(e.link_faces) == 1 for e in v.link_edges) and espesor[v] > 0.04:
            t = 1.0 - (v.co.z - z_alero) / max(z_cum - z_alero, 1e-6)
            if t > 0.84:
                baja = Vector((v.normal.x, v.normal.y, 0.0))
                if baja.length > 1e-6:
                    v.co += baja.normalized() * 0.18
                v.co.z -= 0.11
    for v in bm.verts:
        v.co += v.normal * espesor[v]
    me = bpy.data.meshes.new("Peumo_NieveTecho")
    bm.to_mesh(me)
    o = link(bpy.data.objects.new("Peumo_NieveTecho", me), casco.users_collection[0])
    me.materials.append(M["nieve_techo"])
    nt = M["nieve_techo"].node_tree
    if "EspesorAlfa" not in nt.nodes:
        bsdf = next(nd for nd in nt.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled")
        at_e = nt.nodes.new("ShaderNodeAttribute")
        at_e.name = "EspesorAlfa"
        at_e.attribute_name = "velo"
        # El degradé va de punta a punta del faldón: en la cumbrera la nieve es tan fina que se
        # ve la chapa negra, y gana hasta tapar del todo contra el alero, cambiando parejo en
        # todo el tramo. Concentrarlo arriba partía el techo
        # en dos zonas; dejarlo corto lo devolvía a un blanco entero sin degradé.
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.interpolation_type = "LINEAR"
        ramp.inputs[1].default_value, ramp.inputs[2].default_value = 0.0, 1.0
        ramp.inputs[3].default_value, ramp.inputs[4].default_value = 0.03, 0.95
        nt.links.new(at_e.outputs["Fac"], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], bsdf.inputs["Alpha"])
    at = me.attributes.new("espesor", "FLOAT", "POINT")
    at.data.foreach_set("value", [espesor[v] for v in bm.verts])
    at = me.attributes.new("velo", "FLOAT", "POINT")
    at.data.foreach_set("value", [velo[v] for v in bm.verts])
    bm.free()
    src.free()
    for q in me.polygons:
        q.use_smooth = True
    sol = o.modifiers.new("Espesor", "SOLIDIFY")
    sol.thickness = 0.02
    sol.offset = -1.0
    # la acumulación del video: con la carga baja, la capa se aplasta contra el techo
    ng = bpy.data.node_groups.new("NieveTechoCarga", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    sp = N.new("GeometryNodeSetPosition")
    nor = N.new("GeometryNodeInputNormal")
    esp = N.new("GeometryNodeInputNamedAttribute")
    esp.data_type = "FLOAT"
    esp.inputs["Name"].default_value = "espesor"
    carga = N.new("ShaderNodeValue")
    carga.name = "Carga"
    carga.outputs[0].default_value = 1.0
    menos = N.new("ShaderNodeMath")
    menos.operation = "SUBTRACT"
    menos.inputs[0].default_value = 1.0
    Lk.new(carga.outputs[0], menos.inputs[1])
    cuanto = N.new("ShaderNodeMath")
    cuanto.operation = "MULTIPLY"
    Lk.new(esp.outputs[0], cuanto.inputs[0])
    Lk.new(menos.outputs[0], cuanto.inputs[1])
    off = N.new("ShaderNodeVectorMath")
    off.operation = "SCALE"
    Lk.new(nor.outputs[0], off.inputs[0])
    neg = N.new("ShaderNodeMath")
    neg.operation = "MULTIPLY"
    neg.inputs[1].default_value = -1.0
    Lk.new(cuanto.outputs[0], neg.inputs[0])
    Lk.new(neg.outputs[0], off.inputs["Scale"])
    Lk.new(gi.outputs[0], sp.inputs["Geometry"])
    Lk.new(off.outputs[0], sp.inputs["Offset"])
    Lk.new(sp.outputs[0], go.inputs[0])
    md = o.modifiers.new("Carga", "NODES")
    md.node_group = ng
    o.modifiers.move(md.name and 0, 0)
    return o


def build_library(M):
    """Árboles reales de Poly Haven (CC0), nevados. Son abetos y pinos de verdad, con ramas y
    acículas: es lo único que hace que un bosque nevado no se vea de cartón.

    Van en tres bandas, y la del medio existe justamente para que no se note el cambio: con sólo
    dos, a los treinta y pico de metros se pasaba de golpe de un árbol nevado en detalle a una
    silueta aclarada, y ese salto delataba el truco más que la propia silueta del fondo.
      cerca  LOD2 con nieve de geometría densa
      medio  LOD2 con nieve de geometría rala (hasta ~110 m)
      lejos  LOD2 sin nieve, sólo el follaje aclarado, que la bruma termina de fundir."""
    lib = bpy.data.collections.new("Biblioteca")
    cerca = bpy.data.collections.new("ArbolesCerca")
    medio = bpy.data.collections.new("ArbolesMedio")
    lejos = bpy.data.collections.new("ArbolesLejos")
    renuevos = bpy.data.collections.new("Renuevos")
    for c in (lib, cerca, medio, lejos, renuevos):
        bpy.context.scene.collection.children.link(c)
    def arboles(dest, lod, dens, tam):
        nombres = [f"{t}_tree_01_{v}_{lod}" for t in ("fir", "pine") for v in "abc"]
        for ident in ("fir_tree_01", "pine_tree_01"):
            for o in load_ph(dest, ident, nombres):
                o = realizar(o)
                nevar(o, M, dens=dens, tam=tam) if dens else empolvar(o, M)
    arboles(cerca, "LOD2", 48.0, 0.085)
    arboles(medio, "LOD2", 20.0, 0.125)
    arboles(lejos, "LOD2", None, None)
    # renuevos: lo que crece en el claro, al borde del bosque
    for ident, nombres in (("fir_sapling_medium", ["fir_sapling_medium_a_LOD2", "fir_sapling_medium_b_LOD2"]),
                           ("fir_sapling", ["fir_sapling_a_LOD2", "fir_sapling_b_LOD2"]),
                           ("pine_sapling_small", ["pine_sapling_small_a", "pine_sapling_small_b",
                                                   "pine_sapling_small_c"])):
        for o in load_ph(renuevos, ident, nombres):
            nevar(realizar(o), M, dens=150.0, tam=0.055)
    for c in (lib, cerca, medio, lejos, renuevos):
        c.hide_render = c.hide_viewport = True
    return lib, cerca, medio, lejos, renuevos


def pistas_del_fondo(x, y):
    """Las pistas del otro lado del valle: corredores abiertos en el bosque del fondo. Es lo que
    termina de decir que la montaña entera es un centro de ski y no sólo la ladera de la casa.
    Son cuñas radiales, que a esa distancia se leen como las fajas despejadas que bajan entre el
    bosque; de cerca no actúan (de los 120 m para afuera)."""
    r = math.hypot(x - HC.x, y - HC.y)
    if r < 120.0:
        return 1.0
    a = math.atan2(x - HC.x, y - HC.y)
    f = math.sin(a * 5.0 + 1.3) + 0.55 * math.sin(a * 11.0 + 0.4)
    corte = min(1.0, max(0.0, (1.22 - f) / 0.40))
    return corte + (1.0 - corte) * min(1.0, max(0.0, (170.0 - r) / 50.0))


def build_forest(terreno, arboles, dmin=4.2, dens=0.18, seed=7, escala=(0.55, 1.60),
                 attr="veg", corte=None):
    """Bosque con nodos de geometría sobre una malla de terreno, según un atributo 'veg' calculado
    en Python: 0 en el claro de la casa y sobre la huella, 1 en el bosque, modulado por dos octavas
    de ruido para que haya matas y claros en vez de una grilla pareja (RECETA.md §3). Se corre
    sobre las dos mallas —la fina del claro y la gruesa del fondo—, si no el bosque se termina de
    golpe donde termina la malla fina y la casa queda en un descampado blanco."""
    me = terreno.data
    veg = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        cd = claro_d(x, y)
        w = min(1.0, max(0.0, (cd - CLARO) / 10.0))
        if cd < ORBITA[1]:
            w = 0.0                                             # nada grande donde orbita el dron
        # **La pista manda sobre todo lo demás.** Un árbol en medio de una pista no existe: la
        # franja pisada va limpia de punta a punta, y el bosque se corta contra su borde con un
        # canto bastante duro (3 m), que es como se ve el borde de una pista de verdad. Si se deja
        # una transición larga, el bosque se mete y la pista deja de leerse como pista.
        w *= min(1.0, max(0.0, (pista_d(x, y) - 1.5) / 3.0))
        w *= min(1.0, max(0.0, (house_dist(x, y) - 1.6) / 2.0))
        w *= min(1.0, max(0.0, (min(camino_d(x, y), explanada_d(x, y)) - 2.2) / 2.0))
        w *= min(1.0, max(0.0, (cam_dist(x, y) - 5.5) / 3.5))   # nada de árboles pegados al lente
        # Bosque ralo, no cerrado: es una ladera de centro de ski. El ruido se usa con el umbral
        # más alto que en Peumo, así que en vez de una masa continua con claros quedan islas de
        # árboles con nieve abierta entre medio, que es lo que deja entrar cielo en el cuadro.
        w *= min(1.0, max(0.0, 0.42 + 1.25 * noise.noise(Vector((x / 16.0, y / 16.0, 1.9)))
                          + 0.40 * noise.noise(Vector((x / 5.0, y / 5.0, 5.3)))))
        # Línea de árboles: por **altura real**, cordillera incluida. Si se mide sólo sobre la
        # ladera local, los cerros del fondo salen forestados hasta la cumbre y se ven como lomas
        # verdes; midiendo la altura total, arriba de los 60 m queda roca y nieve, que es lo que
        # da la escala alpina. De paso abre el fondo del cuadro.
        # La línea va a 150 m y se apaga en 50. Estuvo en 60 y dejaba una **franja blanca pelada**
        # entre donde terminaban los árboles y donde empieza el bosque pintado de la cordillera:
        # ni árboles ni bosque, una sábana blanca en medio del cuadro. Las dos líneas —la de los
        # árboles instanciados y la de bosque_lejano— tienen que solaparse, no tocarse.
        w *= min(1.0, max(0.0, (150.0 - (ladera_h(x, y) + cordillera_h(x, y))) / 50.0))
        w *= pistas_del_fondo(x, y)
        if corte:
            w *= corte(math.hypot(x - HC.x, y - HC.y))
        veg.append(max(0.0, min(1.0, w)))
    at = me.attributes.get(attr) or me.attributes.new(attr, "FLOAT", "POINT")
    at.data.foreach_set("value", veg)
    ng = bpy.data.node_groups.new("Bosque_%s_%s" % (terreno.name, attr), "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])
    at_n = N.new("GeometryNodeInputNamedAttribute")
    at_n.data_type = "FLOAT"
    at_n.inputs["Name"].default_value = attr
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = dmin
    dist.inputs["Density Max"].default_value = dens
    dist.inputs["Seed"].default_value = seed
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    Lk.new(at_n.outputs[0], dist.inputs["Density Factor"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = arboles
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rnd = N.new("FunctionNodeRandomValue")
    rnd.data_type = "INT"
    rnd.inputs[5].default_value = len(arboles.objects) - 1
    esc = N.new("FunctionNodeRandomValue")
    esc.data_type = "FLOAT_VECTOR"
    esc.inputs[0].default_value = (escala[0], escala[0], escala[0] * 0.95)
    esc.inputs[1].default_value = (escala[1], escala[1], escala[1] * 1.1)
    esc.inputs["Seed"].default_value = 3
    rot = N.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT_VECTOR"
    rot.inputs[0].default_value = (-0.10, -0.10, 0.0)   # en una ladera ninguno crece a plomo
    rot.inputs[1].default_value = (0.10, 0.10, math.tau)
    rot.inputs["Seed"].default_value = 5
    Lk.new(dist.outputs["Points"], inst.inputs["Points"])
    Lk.new(info.outputs["Instances"], inst.inputs["Instance"])
    inst.inputs["Pick Instance"].default_value = True
    Lk.new(rnd.outputs["Value"], inst.inputs["Instance Index"])
    Lk.new(esc.outputs["Value"], inst.inputs["Scale"])
    Lk.new(rot.outputs["Value"], inst.inputs["Rotation"])
    Lk.new(inst.outputs["Instances"], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = terreno.modifiers.new("Bosque_" + attr, "NODES")
    md.node_group = ng


def build_scrub(M, terreno, lib):
    """Lo que asoma de la nieve en el claro: arbustos tapados, tocones, troncos caídos, raíces y
    piedras, todos de Poly Haven y todos nevados, más algún lomo de nieve. Es lo que rompe el
    blanco del primer plano; un claro liso delata que es CG."""
    matas = bpy.data.collections.new("Matas")
    bpy.context.scene.collection.children.link(matas)
    piezas = {
        "shrub_02": ["shrub_02_a_LOD2", "shrub_02_b_LOD2", "shrub_02_c_LOD2"],
        "tree_stump_01": ["tree_stump_01"],
        "tree_stump_02": ["tree_stump_02"],
        "dead_tree_trunk": ["dead_tree_trunk"],
        "root_cluster_01": ["root_cluster_01"],
        "dry_branches_medium_01": ["dry_branches_medium_01_a", "dry_branches_medium_01_b"],
        "rock_07": ["rock_07_LOD2"],
        "rock_09": ["rock_09_LOD2"],
        "boulder_01": ["boulder_01_LOD2"],
    }
    for ident, nombres in piezas.items():
        for o in load_ph(matas, ident, nombres):
            nevar(realizar(o), M, dens=240.0, tam=0.065, umbral=0.38)
            o.location.z = -0.15          # medio enterrados en la nieve
    # un par de lomos de nieve pelados, para los claros entre mata y mata
    for i in range(2):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(0.6, 1.1),
                                              location=(0, 0, -0.55))
        m = bpy.context.object
        m.name = f"Lomo{i}"
        m.scale = (random.uniform(1.2, 2.1), random.uniform(1.2, 2.1), random.uniform(0.5, 0.8))
        for v in m.data.vertices:
            v.co.x *= random.uniform(0.75, 1.3)
            v.co.y *= random.uniform(0.75, 1.3)
            v.co.z *= random.uniform(0.7, 1.2)
        m.data.materials.append(M["nieve_rama"])
        for q in m.data.polygons:
            q.use_smooth = True
        bpy.context.scene.collection.objects.unlink(m)
        matas.objects.link(m)
    matas.hide_render = matas.hide_viewport = True
    me = terreno.data
    val = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        w = min(1.0, max(0.0, (house_dist(x, y) - 1.1) / 2.2))
        w *= min(1.0, max(0.0, (CLARO + 14.0 - claro_d(x, y)) / 10.0))
        w *= min(1.0, max(0.0, (pista_d(x, y) - 1.0) / 2.5))   # en la pista no asoma nada
        w *= min(1.0, max(0.0, (path_dist(x, y) - 1.8) / 1.5))
        w *= min(1.0, max(0.0, 0.70 + 1.2 * noise.noise(Vector((x / 5.0, y / 5.0, 21.5)))))
        val.append(max(0.0, min(1.0, w)))
    at = me.attributes.new("mata", "FLOAT", "POINT")
    at.data.foreach_set("value", val)
    ng = bpy.data.node_groups.new("Matas", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])
    at_n = N.new("GeometryNodeInputNamedAttribute")
    at_n.data_type = "FLOAT"
    at_n.inputs["Name"].default_value = "mata"
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    # Más ralo que en Peumo: en el claro de un bosque los tocones y las matas tapadas de nieve
    # están por todas partes, pero una ladera de centro de ski se despeja para poder esquiarla, y
    # con la densidad del bosque la nieve abierta se llenaba de montículos y parecía pedregal.
    dist.inputs["Distance Min"].default_value = 3.4
    dist.inputs["Density Max"].default_value = 0.11
    dist.inputs["Seed"].default_value = 31
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    Lk.new(at_n.outputs[0], dist.inputs["Density Factor"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = matas
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rnd = N.new("FunctionNodeRandomValue")
    rnd.data_type = "INT"
    rnd.inputs[5].default_value = len(matas.objects) - 1
    rnd.inputs["Seed"].default_value = 11
    esc = N.new("FunctionNodeRandomValue")
    esc.data_type = "FLOAT_VECTOR"
    esc.inputs[0].default_value = (0.6, 0.6, 0.6)
    esc.inputs[1].default_value = (1.3, 1.3, 1.2)
    esc.inputs["Seed"].default_value = 13
    rot = N.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT_VECTOR"
    rot.inputs[0].default_value = (0.0, 0.0, 0.0)
    rot.inputs[1].default_value = (0.0, 0.0, math.tau)
    rot.inputs["Seed"].default_value = 17
    Lk.new(dist.outputs["Points"], inst.inputs["Points"])
    Lk.new(info.outputs["Instances"], inst.inputs["Instance"])
    inst.inputs["Pick Instance"].default_value = True
    Lk.new(rnd.outputs["Value"], inst.inputs["Instance Index"])
    Lk.new(esc.outputs["Value"], inst.inputs["Scale"])
    Lk.new(rot.outputs["Value"], inst.inputs["Rotation"])
    Lk.new(inst.outputs["Instances"], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = terreno.modifiers.new("Matas", "NODES")
    md.node_group = ng


# ---------------------------------------------------------------- el centro de ski
def andarivel_x(y):
    """Eje del andarivel: sube por el otro lado de la pista, 14 m más allá de su borde.

    La distancia es el resultado de dos correcciones opuestas, así que conviene no volver a
    moverla a ciegas. Primero estuvo lejos y quedaba **fuera de cuadro** en todas las tomas (con
    lente de 30 en vertical el cuadro abarca ±18° y el andarivel caía a 30° del eje), así que se
    corrió hasta el canto de la pista. Ahí pasó lo contrario: en las tomas del acceso quedaba una
    sola torre justo detrás de la casa, y la revisión la leyó como **un poste de luz**, que es
    exactamente lo que parece una torre aislada sin más torres ni sillas alrededor. A 14 m del
    borde entran varias torres en fila con sus sillas, que es lo que lo hace leer como andarivel
    y no como poste, y ninguna cae pegada a la casa."""
    return pista_cx(y) - pista_w(y) - 14.0


def build_andarivel(M, y0=-205.0, y1=95.0, paso=52.0):
    """Andarivel de sillas cruzando la ladera: torres, los dos cables y las sillas colgando.

    Es lo que convierte "un cerro nevado" en "un centro de ski", y por eso es lo único de la
    escena que se modela entero aunque quede a media distancia: una torre contra la nieve se lee
    a doscientos metros, y el cable tendido entre dos torres da la línea diagonal que cruza el
    cuadro y le pone escala a la ladera.

    El cable no va recto de torre a torre: cuelga. Esa catenaria es la diferencia entre un cable
    de verdad y una línea tirada con regla, y a contraluz es lo primero que se nota."""
    coll = bpy.data.collections.new("Andarivel")
    bpy.context.scene.collection.children.link(coll)
    ys = [y0 + i * paso for i in range(int((y1 - y0) / paso) + 1)]
    SEP = 2.6            # separación entre el cable de subida y el de bajada
    cuelga = 2.9         # cuánto cuelga la silla bajo el cable
    tops = []
    for k, y in enumerate(ys):
        x = andarivel_x(y)
        z0 = terrain_h(x, y)
        alt = 9.5 + 2.2 * math.sin(k * 1.7)          # las torres no son todas iguales
        # la columna: tubo de acero, apenas cónico
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.30, depth=alt,
                                            location=(x, y, z0 + alt / 2))
        t = bpy.context.object
        t.name = f"TorreAndarivel{k}"
        for v in t.data.vertices:
            if v.co.z > 0:
                v.co.x *= 0.62
                v.co.y *= 0.62
        t.data.materials.append(M["torre"])
        bpy.ops.object.shade_smooth()
        bpy.context.scene.collection.objects.unlink(t)
        coll.objects.link(t)
        # el travesaño con los trenes de poleas en las puntas
        tv = box(f"TravesanoAnd{k}", x - SEP / 2 - 0.5, x + SEP / 2 + 0.5, y - 0.16, y + 0.16,
                 z0 + alt - 0.34, z0 + alt, M["torre"])
        bpy.context.scene.collection.objects.unlink(tv)
        coll.objects.link(tv)
        for lado in (-1, 1):
            pl = box(f"PoleaAnd{k}{lado}", x + lado * SEP / 2 - 0.42, x + lado * SEP / 2 + 0.42,
                     y - 0.11, y + 0.11, z0 + alt - 0.72, z0 + alt - 0.36, M["torre"])
            bpy.context.scene.collection.objects.unlink(pl)
            coll.objects.link(pl)
        tops.append((x, y, z0 + alt - 0.58))
    # los dos cables, con su catenaria entre torre y torre
    for lado in (-1, 1):
        pts = []
        for i in range(len(tops) - 1):
            (xa, ya, za), (xb, yb, zb) = tops[i], tops[i + 1]
            for j in range(13):
                u = j / 12.0
                # la flecha máxima va al medio del vano; 1,1 m en un vano de 52 es lo normal
                s_ = -1.1 * 4 * u * (1 - u)
                pts.append((xa + (xb - xa) * u + lado * SEP / 2,
                            ya + (yb - ya) * u, za + (zb - za) * u + s_))
        cu = bpy.data.curves.new(f"CableAnd{lado}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.035
        cu.bevel_resolution = 1
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, q in enumerate(pts):
            sp.points[i].co = (*q, 1.0)
        cb = bpy.data.objects.new(f"CableAndarivel{lado}", cu)
        cu.materials.append(M["torre"])
        coll.objects.link(cb)
        # las sillas, repartidas a lo largo del cable
        n = len(pts)
        for i in range(5, n - 5, 8):
            cx, cy, cz = pts[i]
            br = box(f"BrazoSilla{lado}_{i}", cx - 0.045, cx + 0.045, cy - 0.045, cy + 0.045,
                     cz - cuelga, cz, M["torre"])
            # La silla va de cuatro plazas y con el respaldo alto: a la distancia a la que ahora
            # queda la línea, una silla chica es un punto y vuelve a leerse como cable pelado.
            asiento = box(f"AsientoSilla{lado}_{i}", cx - 1.25, cx + 1.25, cy - 0.34, cy + 0.34,
                          cz - cuelga, cz - cuelga + 0.12, M["silla"])
            respaldo = box(f"RespaldoSilla{lado}_{i}", cx - 1.25, cx + 1.25,
                           cy + 0.24 * lado, cy + 0.36 * lado,
                           cz - cuelga + 0.12, cz - cuelga + 0.92, M["silla"])
            for o in (br, asiento, respaldo):
                bpy.context.scene.collection.objects.unlink(o)
                coll.objects.link(o)
    print("andarivel: %d torres, %d m de línea" % (len(ys), ys[-1] - ys[0]))
    return coll


def build_balizas(M, y0=-150.0, y1=70.0, paso=15.0):
    """Balizas al borde de la pista: las varillas que marcan por dónde se baja. Son el único color
    saturado de toda la escena —todo lo demás es nieve, madera y chapa negra—, así que no hace
    falta ponerle muchas: puestas cada quince metros, la hilera dibuja sola la curva de la pista
    y le da al ojo con qué medir la distancia."""
    coll = bpy.data.collections.new("Balizas")
    bpy.context.scene.collection.children.link(coll)
    n = 0
    y = y0
    while y < y1:
        for lado in (-1, 1):
            x = pista_cx(y) + lado * (pista_w(y) + 0.6)
            z = terrain_h(x, y)
            alt = random.uniform(1.6, 2.0)
            bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.035, depth=alt,
                                                location=(x, y, z + alt / 2 - 0.25))
            b = bpy.context.object
            b.name = f"Baliza{n}"
            b.rotation_euler = (random.uniform(-0.09, 0.09), random.uniform(-0.09, 0.09), 0)
            b.data.materials.append(M["baliza"])
            bpy.context.scene.collection.objects.unlink(b)
            coll.objects.link(b)
            n += 1
        y += paso * random.uniform(0.85, 1.15)
    print("balizas:", n)
    return coll


def build_huellas_esqui(M, terreno, n_bajadas=7):
    """Las curvas que dejaron los que ya bajaron: huellas de esquí marcadas en la pista.

    Van como **geometría**, no como material ni como atributo del terreno, y no por capricho: un
    surco de esquí tiene veinte centímetros de ancho y la malla fina del terreno tiene un vértice
    cada 1,10 m, así que ni el relieve ni un atributo por vértice pueden dibujarlo — saldría un
    manchón de dos metros. Cada huella es una cinta con sección en **V** (los cantos arriba y el
    fondo tres centímetros más abajo), que es lo que hace que con el sol rasante cada curva tenga
    su lado iluminado y su lado en sombra. Sin eso la pista acordonada se lee como una alfombra
    nueva que nadie pisó.

    La altura **se saca con un rayo contra la malla ya terminada**, no llamando a terrain_h. Dos
    razones, y las dos se vieron en el render: la malla es una grilla de 1,10 m que interpola
    recto entre vértices mientras terrain_h es una función suave, así que la cinta se hundía y
    flotaba alternadamente; y hundir_huella le baja el terreno a la pista **después** de armarla,
    con lo que la cinta quedaba colgada 30 cm en el aire. Con el rayo, la huella se apoya en lo
    que efectivamente se ve. Por eso sólo llega hasta donde llega la malla fina: más allá el
    terreno es de 7 m de paso y una huella de esquí ahí no tiene ningún sentido."""
    coll = bpy.data.collections.new("HuellasEsqui")
    bpy.context.scene.collection.children.link(coll)
    bm = bmesh.new()
    bm.from_mesh(terreno.data)
    bvh = BVHTree.FromBMesh(bm)

    def suelo(x, y):
        hit = bvh.ray_cast(Vector((x, y, 80.0)), Vector((0, 0, -1)), 260.0)[0]
        return hit.z if hit else None

    y0, y1 = -50.0, HC.y + 16.0
    hechas = 0
    for k in range(n_bajadas):
        amp = 4.5 + 3.2 * math.sin(k * 1.9 + 0.4)
        per = 23.0 + 9.0 * math.cos(k * 2.3)
        lado = (k - (n_bajadas - 1) / 2.0) * 2.6 + 1.4 * math.sin(k * 3.1)
        for esqui in (-1, 1):
            verts, faces, prev = [], [], False
            paso = 0.8
            m = int((y1 - y0) / paso)
            for i in range(m + 1):
                y = y0 + i * paso
                cx = pista_cx(y) + lado + amp * math.sin(y / per + k * 2.1)
                sep = 0.30 + 0.12 * math.cos(y / per + k * 2.1)
                x = cx + esqui * sep
                z = suelo(x, y)
                # fuera de la pista la huella no existe: el esquiador baja por lo pisado
                if z is None or pista_d(x, y) > 1.5:
                    prev = False
                    continue
                base = len(verts)
                for dx, dz in ((-0.11, 0.022), (0.0, -0.030), (0.11, 0.022)):
                    verts.append((x + dx, y, z + dz))
                if prev:
                    for a in (0, 1):
                        faces.append((base - 3 + a, base - 2 + a, base + 1 + a, base + a))
                prev = True
            if not faces:
                continue
            o = mesh_obj("HuellaEsqui%d_%d" % (k, esqui), verts, faces, M["nieve_huella"], coll)
            for q in o.data.polygons:
                q.use_smooth = True
            hechas += 1
    bm.free()
    print("huellas de esquí:", hechas)
    return coll


def build_carambanos(M, n=170):
    """Carámbanos colgando del alero. Es un detalle chico que pesa mucho: una casa nevada con el
    canto del techo perfectamente limpio se ve recién salida del modelador. Van en los dos aleros
    largos, agrupados —se forman donde el agua corre, no parejos— y con largos muy distintos."""
    coll = bpy.data.collections.new("Carambanos")
    bpy.context.scene.collection.children.link(coll)
    # los dos aleros largos del techo: el bajo en x = 0 y el alto en x = L (ver el extractor)
    bordes = ((0.0, 3.11, -0.06), (L, 5.35, 0.06))
    hechos = 0
    for x0, z0, fuera in bordes:
        for i in range(n):
            y = 2.3 + (D - 4.2) * (i / (n - 1.0))
            # se forman en racimos: un ruido decide dónde hay y dónde no
            if noise.noise(Vector((y / 2.7, x0 / 3.0, 97.0))) < 0.06:
                continue
            largo = random.uniform(0.09, 0.52) * (0.55 + 0.9 * abs(noise.noise(Vector((y / 1.6, 5.0, 71.0)))))
            r = 0.012 + largo * 0.055
            bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=r, radius2=0.0, depth=largo,
                                            location=(x0 + fuera + random.uniform(-0.02, 0.02),
                                                      y + random.uniform(-0.05, 0.05),
                                                      z0 - largo / 2 + 0.02))
            c = bpy.context.object
            c.rotation_euler = (random.uniform(-0.05, 0.05), random.uniform(-0.04, 0.04), 0)
            c.data.materials.append(M["hielo"])
            bpy.ops.object.shade_smooth()
            bpy.context.scene.collection.objects.unlink(c)
            coll.objects.link(c)
            hechos += 1
    print("carámbanos:", hechos)
    return coll


def build_acceso(M):
    """Puerta, ventana y terraza de la fachada de acceso.

    **El STL no trae ni puerta ni ventana**: los dos vanos vienen modelados con sus jambas pero
    vacíos, y en el render se leían como dos agujeros negros con el fondo del interior oscuro
    asomando. La revisión lo marcó en las dos tomas del acceso ("que puerta y ventana se vean y
    no solo el hueco"). Acá se cierran los dos.

    El ancho de la puerta **no se toca**: son 73 cm, que es lo que da el modelo oficial, y la
    revisión resolvió dejarlo así y ganar presencia con la hoja, no agrandando el vano. Lo que la
    hace leer como puerta de acceso y no como una ranura es el conjunto: marco oscuro que
    enmarca el vano, hoja de madera en su plano, una pieza de luz vertical a un costado,
    manilla y umbral.

    La terraza de entrada se alarga tres metros hacia afuera, con su faldón y una escalera nueva
    al borde: la que había era una lengüeta de poco más de un metro y la casa parecía entrar
    directo desde la nieve."""
    coll = bpy.data.collections.new("Acceso")
    bpy.context.scene.collection.children.link(coll)
    piezas = []

    def pz(nombre, x0, x1, y0, y1, z0, z1, mat):
        piezas.append(box(nombre, x0, x1, y0, y1, z0, z1, mat))

    # ---------------------------------------------------------------- la puerta
    px0, px1, pz0, pz1 = VANO_PUERTA
    MARCO = 0.075                    # ancho del marco visto de frente
    yf0, yf1 = ACC_Y - 0.30, ACC_Y + 0.025     # el marco cubre todo el espesor del vano
    pz("MarcoPuertaIzq", px0 - MARCO, px0 + 0.02, yf0, yf1, pz0, pz1 + MARCO, M["marco"])
    pz("MarcoPuertaDer", px1 - 0.02, px1 + MARCO, yf0, yf1, pz0, pz1 + MARCO, M["marco"])
    pz("MarcoPuertaSup", px0 - MARCO, px1 + MARCO, yf0, yf1, pz1 - 0.02, pz1 + MARCO, M["marco"])
    # la hoja, retranqueada diez centímetros: así tiene sombra propia y no se ve pegada al muro
    hy = ACC_Y - 0.13
    pz("HojaPuerta", px0 + 0.025, px1 - 0.025, hy - 0.025, hy + 0.025, pz0 + 0.01, pz1 - 0.02,
       M["puerta_acc"])
    # luz vertical: una faja de vidrio al costado de la manilla, que es lo que le da prestancia
    lz0, lz1 = pz0 + 0.55, pz1 - 0.22
    pz("LuzPuerta", px1 - 0.21, px1 - 0.09, hy - 0.032, hy + 0.032, lz0, lz1, M["vidrio"])
    pz("LuzPuertaMarco", px1 - 0.235, px1 - 0.065, hy - 0.036, hy + 0.036, lz0 - 0.025, lz1 + 0.025,
       M["marco"])
    # manilla y umbral
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.016, depth=0.26,
                                        location=(px0 + 0.20, hy - 0.075, pz0 + 1.05))
    man = bpy.context.object
    man.name = "ManillaPuerta"
    man.rotation_euler = (0, math.radians(90), 0)
    man.data.materials.append(M["acero"])
    bpy.ops.object.shade_smooth()
    bpy.context.scene.collection.objects.unlink(man)
    coll.objects.link(man)
    pz("UmbralPuerta", px0 - MARCO, px1 + MARCO, ACC_Y - 0.32, ACC_Y + 0.09, pz0 - 0.035, pz0 + 0.012,
       M["marco"])

    # ---------------------------------------------------------------- la ventana del 2do piso
    vx0, vx1, vz0, vz1 = VANO_VENT
    MV = 0.065
    pz("MarcoVentIzq", vx0 - MV, vx0 + 0.02, yf0, yf1, vz0 - MV, vz1 + MV, M["marco"])
    pz("MarcoVentDer", vx1 - 0.02, vx1 + MV, yf0, yf1, vz0 - MV, vz1 + MV, M["marco"])
    pz("MarcoVentSup", vx0 - MV, vx1 + MV, yf0, yf1, vz1 - 0.02, vz1 + MV, M["marco"])
    pz("MarcoVentInf", vx0 - MV, vx1 + MV, yf0, yf1, vz0 - MV, vz0 + 0.02, M["marco"])
    vy = ACC_Y - 0.10
    pz("VidrioVent", vx0 + 0.015, vx1 - 0.015, vy - 0.008, vy + 0.008, vz0 + 0.015, vz1 - 0.015,
       M["vidrio"])
    pz("ParteluzVent", (vx0 + vx1) / 2 - 0.035, (vx0 + vx1) / 2 + 0.035, vy - 0.03, vy + 0.03,
       vz0, vz1, M["marco"])
    # alféizar: la nieve se posa ahí, y es lo que delata que la ventana está hundida en el muro
    pz("AlfeizarVent", vx0 - MV - 0.03, vx1 + MV + 0.03, ACC_Y - 0.33, ACC_Y + 0.07,
       vz0 - MV - 0.045, vz0 - MV + 0.005, M["marco"])

    # ---------------------------------------------------------------- la terraza de entrada
    tx0, tx1, ty1 = TERRAZA_ACC
    ty0 = D - 0.25                       # arranca bajo el borde de la que ya existe
    TZ = 0.542                           # 2 mm sobre la cubierta existente: sin pelea de planos
    pz("TerrazaAcceso", tx0, tx1, ty0, ty1, TZ - 0.085, TZ, M["deck"])
    pz("FaldonTerrazaFin", tx0 - 0.03, tx1 + 0.03, ty1 - 0.04, ty1 + 0.03, TZ - 0.40, TZ + 0.01,
       M["decknegro"])
    for lado, xx in (("Izq", tx0), ("Der", tx1)):
        pz("FaldonTerraza" + lado, xx - 0.03, xx + 0.03, ty0, ty1 + 0.03, TZ - 0.40, TZ + 0.01,
           M["decknegro"])
    # escalera nueva al borde, centrada en la puerta
    ex = (VANO_PUERTA[0] + VANO_PUERTA[1]) / 2
    for i in range(3):
        z = TZ - 0.17 * (i + 1)
        pz("PeldanoAcceso%d" % i, ex - 1.15, ex + 1.15, ty1 + 0.04 + i * 0.30,
           ty1 + 0.34 + i * 0.30, z - 0.05, z, M["deck"])
    for o in piezas:
        bpy.context.scene.collection.objects.unlink(o)
        coll.objects.link(o)
    print("acceso: puerta, ventana y terraza (%d piezas)" % (len(piezas) + 1))
    return coll


def carga_en(g):
    """Carga de nieve en el cuadro g del video completo: crece parejo de punta a punta."""
    u = min(1.0, max(0.0, g / (VIDEO_N - 1.0)))
    return CARGA[0] + (CARGA[1] - CARGA[0]) * u


def animar_carga(n, g0):
    """Mueve la carga de todos los grupos de nieve a lo largo de la sección. Va cuadro a cuadro:
    son unos pocos valores por cuadro y así la curva no se pasa de los extremos entre secciones,
    que es lo que haría saltar la nieve en el empalme."""
    nodos = [ng.nodes["Carga"] for ng in bpy.data.node_groups if "Carga" in ng.nodes]
    for f in range(n):
        v = carga_en(g0 + f)
        for nd in nodos:
            nd.outputs[0].default_value = v
            nd.outputs[0].keyframe_insert("default_value", frame=f + 1)
    return nodos


def build_snowfall(M, loc=None, tgt=None, n=36000, fuerza=1.0, caja=None):
    """Nieve cayendo, en diagonal por el viento (VIENTO_TAN). Los de más cerca quedan
    desenfocados y se leen como motas blandas —que es como se ve nevar en una foto—, así que la
    cámara va con desenfoque: a 30 mm y f/4 la hiperfocal son ocho metros, o sea que el bosque
    y la casa quedan nítidos y sólo se ablanda lo que pasa a menos de tres metros del lente."""
    coll = bpy.data.collections.new("Nevada")
    bpy.context.scene.collection.children.link(coll)
    verts = []
    if caja:
        # recorrido de dron: la cámara se mueve, así que la nevada llena una caja sobre la casa.
        # La densidad está calibrada contra la toma fija (un copo por metro cúbico se ve bien en
        # pantalla); acá baja algo porque en video el motion blur estira cada copo en un hilo y
        # con la misma cantidad taparía la casa.
        rx, ry, zt = caja
        for _ in range(int(rx * ry * zt * 0.60 * fuerza)):
            verts.append(Vector((HC.x + random.uniform(-rx / 2, rx / 2),
                                 HC.y + random.uniform(-ry / 2, ry / 2),
                                 GROUND + random.uniform(0.2, zt))))
    else:
        # toma fija: basta llenar el cono que mira la cámara
        loc, tgt = Vector(loc), Vector(tgt)
        fwd = (tgt - loc).normalized()
        der = fwd.cross(Vector((0, 0, 1))).normalized()
        arr = der.cross(fwd)
        largo = (tgt - loc).length + 14.0
        for _ in range(int(n * fuerza)):
            # arrancan a tres metros y medio y se reparten parejo en profundidad: así la densidad
            # en pantalla es pareja. Más cerca el desenfoque los infla y parece lente sucio.
            d = 3.5 + (largo - 3.5) * random.random()
            ancho = 2.5 + d * 0.8
            p = loc + fwd * d + der * random.uniform(-ancho, ancho) + arr * random.uniform(-ancho, ancho)
            if p.z < GROUND + 0.1:
                continue
            verts.append(p)
    me = bpy.data.meshes.new("Copos")
    me.from_pydata(verts, [], [])
    me.update()
    o = link(bpy.data.objects.new("Copos", me), coll)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=0, radius=1.0, location=(0, 0, -900))
    copo = bpy.context.object
    copo.name = "Copo"
    copo.data.materials.append(M["copo"])
    bpy.context.scene.collection.objects.unlink(copo)
    coll.objects.link(copo)
    ng = bpy.data.node_groups.new("Nevada", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    inst = N.new("GeometryNodeInstanceOnPoints")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = copo
    esc = N.new("FunctionNodeRandomValue")
    esc.data_type = "FLOAT_VECTOR"
    esc.inputs[0].default_value = (0.011,) * 3
    esc.inputs[1].default_value = (0.028,) * 3
    Lk.new(gi.outputs[0], inst.inputs["Points"])
    Lk.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    Lk.new(esc.outputs["Value"], inst.inputs["Scale"])
    Lk.new(inst.outputs[0], go.inputs[0])
    md = o.modifiers.new("Nevada", "NODES")
    md.node_group = ng
    # cae: en video el motion blur lo convierte en hilos; en una foto fija no se nota. Las claves
    # van repartidas parejo, así la curva suave que arma Blender pasa recta por ellas y el copo
    # cae a velocidad constante, sin acelerar ni frenar.
    for k in range(9):
        dz = -9.0 * k / 8.0
        o.location = VIENTO * (-dz * VIENTO_TAN) + Vector((0, 0, dz))
        o.keyframe_insert("location", frame=1 + k * FPS)
    return coll


def build_lenera(M):
    """Leña apilada contra el muro, bajo el alero. Es de las cosas que más integran una casa:
    dice que alguien vive ahí y que el invierno se preparó con tiempo."""
    coll = bpy.data.collections.new("Lenera")
    bpy.context.scene.collection.children.link(coll)
    x0, y0 = L + 0.18, 11.4          # contra el muro alto, al llegar al porch
    for fila in range(7):
        for i in range(9):
            y = y0 + i * 0.30 + random.uniform(-0.02, 0.02)
            z = PISO + 0.06 + fila * 0.255 + random.uniform(-0.015, 0.015)
            r = random.uniform(0.105, 0.145)
            bpy.ops.mesh.primitive_cylinder_add(vertices=9, radius=r, depth=random.uniform(0.42, 0.5),
                                                location=(x0 + 0.26 + random.uniform(-0.03, 0.03), y, z))
            t = bpy.context.object
            t.rotation_euler = (0, math.radians(90), random.uniform(-0.05, 0.05))
            t.data.materials.append(M["corteza_clara"] if i % 3 else M["corteza"])
            bpy.context.scene.collection.objects.unlink(t)
            coll.objects.link(t)
    return coll


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
    sky.aerosol_density = 2.2       # aire limpio de montaña
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
    # Dónde deja de verse el cielo físico y empieza el HDRI, en seno de la elevación. Estaba en
    # 0,3-0,6 (de 17° a 37°) y en un cuadro vertical con lente de 30 eso deja el HDRI **fuera de
    # cuadro**: el cielo salía como un degradé azul perfectamente limpio, que es de lo que más
    # canta que es un render. Bajado a 0,20-0,45 entran las nubes del HDRI sin que asome el
    # paisaje propio que trae cerca del horizonte.
    hi.inputs[1].default_value, hi.inputs[2].default_value = 0.20, 0.45
    l.new(sep.outputs["Z"], hi.inputs[0])
    cam_sky = n.new("ShaderNodeMix")
    cam_sky.data_type = "RGBA"
    l.new(hi.outputs[0], cam_sky.inputs[0])
    l.new(gain.outputs[2], cam_sky.inputs[6])
    l.new(env.outputs["Color"], cam_sky.inputs[7])
    # Perilla para bajar sólo la rama que ilumina —la que toman los rayos que no son de cámara ni
    # de reflejo—, sin tocar el fondo que se ve. Con horn-koppe va en 1 y no hace nada; queda a
    # mano por si otra casa de la familia nieve necesita apagar el ambiente.
    amb = n.new("ShaderNodeMix")
    amb.data_type = "RGBA"
    amb.blend_type = "MULTIPLY"
    amb.inputs[0].default_value = 1.0
    amb.inputs[7].default_value = (AMBIENTE, AMBIENTE, AMBIENTE, 1)
    l.new(env.outputs["Color"], amb.inputs[6])
    lp = n.new("ShaderNodeLightPath")
    pick = n.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    seen = n.new("ShaderNodeMath")          # cámara o reflejos (mar, vidrios) ven el cielo limpio
    seen.operation = "MAXIMUM"
    l.new(lp.outputs["Is Camera Ray"], seen.inputs[0])
    l.new(lp.outputs["Is Glossy Ray"], seen.inputs[1])
    l.new(seen.outputs[0], pick.inputs[0])
    l.new(amb.outputs[2], pick.inputs[6])
    l.new(cam_sky.outputs[2], pick.inputs[7])
    l.new(pick.outputs[2], bg.inputs[0])
    # Nada de lámpara de sol aparte: horn-koppe_snow trae un sol propio muy fuerte (pico 62884
    # contra los 34 del nublado) y sumarle una lámpara quemaba la escena. Y bajar el ambiente
    # tampoco servía para sacar sombras: multiplicar el HDRI entero baja el sol y el cielo por
    # igual, así que la razón entre los dos —que es la que hace la sombra— no cambia. Lo que
    # decide es qué HDRI se elige.
    # Peumo cerraba a 420 m porque el bosque no dejaba ver más allá. Acá la bruma tiene que
    # dejar ver la cordillera entera: en una ladera abierta y con aire seco de montaña se ve
    # lejísimos, y cortar a 400 m dejaba los cerros del fondo planos y lavados.
    w.mist_settings.start = 40
    w.mist_settings.depth = 1800
    w.mist_settings.falloff = "LINEAR"


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = int(opts["samples"])
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.06
    cy.max_bounces = 6
    cy.diffuse_bounces = 2        # con tanta nieve a la vista, el tercer rebote casi no se nota
    cy.glossy_bounces = 2
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 10
    cy.use_fast_gi = True            # en bosque denso, los rebotes profundos salen por oclusión
    cy.ao_bounces_render = 2
    cy.sample_clamp_indirect = 3.0   # sin esto, el cielo visto entre acículas deja luciérnagas
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
    sc.view_settings.exposure = -0.35    # una escena casi toda blanca se quema fácil con AgX
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

    # bruma = 0,36 · (1 − e^(−(z − 45) / 520)), sobre todo lo que no es cielo (z < 10 km de cámara
    # para el cielo no hay superficie: su profundidad es enorme). Entra mucho más tarde que en el
    # bosque de Peumo y se estira más: en una ladera abierta la bruma no separa troncos, separa
    # **lomos de cerro**, y si entra a los veinte metros borra la pista en vez de dar profundidad.
    sc.view_layers[0].use_pass_z = True
    zrel = mnode("SUBTRACT", 45.0)
    pos = mnode("MAXIMUM", 0.0)
    sc_ = mnode("DIVIDE", -520.0)
    ex = mnode("EXPONENT", 0.0)
    one = mnode("SUBTRACT", 1.0)
    sky = mnode("LESS_THAN", 1.0e7)
    mul = mnode("MULTIPLY", 1.0)
    amt = mnode("MULTIPLY", 0.36)
    one.inputs[0].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0.80, 0.85, 0.91, 1)   # bruma de nieve, no de mar
    nt.links.new(rl.outputs["Depth"], zrel.inputs[0])
    nt.links.new(zrel.outputs[0], pos.inputs[0])
    nt.links.new(pos.outputs[0], sc_.inputs[0])
    nt.links.new(sc_.outputs[0], ex.inputs[0])
    nt.links.new(ex.outputs[0], one.inputs[1])
    nt.links.new(rl.outputs["Depth"], sky.inputs[0])
    nt.links.new(one.outputs[0], mul.inputs[0])
    nt.links.new(sky.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], amt.inputs[0])
    # + una bruma de lejanía que funde la cordillera con el cielo: 0,26 · (1 − e^(−z / 2400)).
    # Estuvo en 0,42 y **se comía la roca**: los cerros quedaban blancos parejos y toda la forma
    # que les da el material —farellones, vetas, bosque en los faldones— se perdía bajo el velo.
    # En un día alpino despejado la montaña lejana conserva contraste; la bruma separa planos,
    # no los borra.
    # La escala es casi el triple que en Peumo porque los cerros del fondo están a 600 m y no a
    # 200: con la escala corta se fundían del todo y la montaña desaparecía.
    far_s = mnode("DIVIDE", -2400.0)
    far_e = mnode("EXPONENT", 0.0)
    far_1 = mnode("SUBTRACT", 1.0)
    far_1.inputs[0].default_value = 1.0
    far_a = mnode("MULTIPLY", 0.26)
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
    # la cantidad de bruma se difumina antes de aplicarla: en el borde entre una acícula y el
    # cielo la profundidad salta de cien metros a infinito de un píxel al siguiente, y la bruma
    # saltaba con ella. Se veía como un moteado sucio en las copas del fondo.
    suave = nt.nodes.new("CompositorNodeBlur")
    suave.inputs["Size"].default_value = (3.0, 3.0)
    nt.links.new(tot.outputs[0], suave.inputs[0])
    nt.links.new(suave.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[6])
    nt.links.new(mix.outputs[2], go.inputs[0])


# tomas fijas de dron. El enganche de Peumo es el testero vidriado de doble altura, así que las
# dos primeras se plantan frente a él (-Y) y las opuestas miran desde el acceso, con el bosque
# nevado detrás. Encuadres a propósito abiertos, para poder reencuadrar en la edición.
# Tomas fijas de dron. **La tercera coordenada es altura sobre el terreno, no cota absoluta**:
# la ladera cae treinta centímetros por metro, así que una cota fija deja la cámara a tres metros
# del suelo abajo de la pista y enterrada arriba del talud. build_camera() le suma terrain_h.
# El enganche de Roble es el testero vidriado mirando a la pista (ENGANCHES.md), así que las dos
# primeras se plantan abajo, en la pista, mirando hacia arriba: desde ahí la casa se recorta
# contra el cielo y se ve lo que la casa ve. Las opuestas vienen del acceso, por el talud de
# arriba, y en ésas entra la cordillera del fondo.
VISTAS = {
    # Las dos de abajo van **más alto de lo que pide la intuición**: a seis metros sobre el
    # terreno la cámara queda por debajo de la plataforma, y el lomo de nieve del borde del banco
    # —que está a mitad de camino— le tapa la terraza y los pilotes. Medido en el cuadro de
    # prueba: con 6 m la casa aparecía recortada desde el piso para arriba. Con 12 la línea de
    # visión pasa limpia sobre el lomo y entra la terraza entera.
    "izq": ((-14.0, -19.0, 12.0), (4.0, 6.0, 2.6), 30),
    "der": ((20.0, -16.0, 11.0), (5.0, 6.2, 2.6), 30),
    # opuestas: desde la fachada de acceso, el camino y la explanada
    "izq_atras": ((26.0, 26.0, 7.0), (4.6, 11.0, 2.4), 30),
    "der_atras": ((-16.0, 28.0, 7.5), (4.2, 11.0, 2.4), 30),
    # y una de contexto, desde abajo en la pista: la casa chica en el cuadro, con el andarivel,
    # el acordonado y la cordillera. El emplazamiento es lo que hay que aprobar en esta casa
    # —la nieve ya venía resuelta de Peumo—, y de cerca no se ve dónde está parada.
    # Va con lente de 24, no de 30: con 30 no entraban a la vez la casa y la línea del
    # andarivel, y en una toma que existe para mostrar el lugar eso es justamente lo que falta.
    "contexto": ((-30.0, -95.0, 20.0), (4.0, 8.0, 3.0), 24),
}
def build_camera():
    sc = bpy.context.scene
    cam = link(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
    sc.camera = cam
    loc, tgt, lens = VISTAS[opts["vista"]]
    loc = (loc[0], loc[1], terrain_h(loc[0], loc[1]) + loc[2])
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.clip_end = 5000
    return cam



# ---------------------------------------------------------------- recorrido de dron (por secciones)
# El reel se divide en secciones que se renderizan por separado (--vista dron --tramo sN) y se unen
# en la edición como una sola toma de dron (la última pose de una es la primera de la siguiente),
# con la misma lógica del reel de Casa Lingue y del recorrido de Huingán:
#   s1  aproximación: parte lejos y alto sobre el bosque y se acerca en espiral, desacelerando,
#       hasta la diagonal frontal izquierda                                                10 s
#   s2  vuelo lento rodeando el frente hacia el costado, a distancia casi constante
#   s3  sube a la vista aérea y el techo se corta: recintos hasta la cenital
#   s4  paso a la planta y la lámina (post 2D, como tools/video_corte.py en Lingue)
#   s5  baja en espiral hacia la fachada de acceso y el camino
# Un dron no hace zoom: la distancia cambia de forma continua y suave (nunca "respira" con el giro);
# el encuadre adaptable sólo fija la distancia final para que la casa quepa en pantalla.
SECCIONES = {"s1": 240, "s2": 192, "s3": 240, "s5": 192}
INICIO = {"s2": 0, "s3": 192, "s5": 432}      # cuadro de inicio de cada sección en la ruta continua s2..s5
CASA_BOX = (0.0, L, -0.7, D + 0.7, GROUND, 6.7)      # caja de la casa (con escaleras) para encuadrar
CASA_C = Vector((L / 2, D / 2, 2.4))                 # punto al que mira el dron
FIT = 0.86                                           # ancho de pantalla que ocupa la casa


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
S1_EL = (44.0, 15.0)         # elevación (°): empieza alto, por sobre las copas
# En la playa el dron podía entrar rasante porque no había nada en el medio. Acá, a ras de copas,
# el bosque tapa la casa entera: la aproximación tiene que venir de arriba y bajar al claro.
S1_D0 = 118.0                # distancia inicial (m)


def pose_s1(f, n):
    """Aproximación en espiral: el giro avanza parejo y la distancia cae en escala logarítmica con
    salida suave (el dron frena al llegar). El punto de mira pasa del claro a la casa, y llega
    pronto: si tarda, a mitad de la aproximación la casa queda pegada al borde del cuadro."""
    u = f / (n - 1)
    ua = u * u * (3 - 2 * u)
    az = math.radians(S1_AZ[0] + (S1_AZ[1] - S1_AZ[0]) * ua)
    el = math.radians(S1_EL[0] + (S1_EL[1] - S1_EL[0]) * ua)
    direc = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    ud = 1 - (1 - u) ** 2.2                          # rápido al comienzo, frena al final
    tgt = Vector((L / 2, -7.0, 1.6)).lerp(CASA_C, smootherstep(min(1.0, u * 2.1)))
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
# Roble tiene dos pisos, así que el corte baja en dos tiempos en vez de uno: primero se lleva el
# techo y deja ver el segundo piso (dormitorio-1 y escritorio), después baja al primero. Con un
# solo escalón esos dos recintos no se alcanzarían a ver nunca.
# OJO para el video: por ser de dos pisos, el barrido de s3 tiene que **pausar en cada piso** tres
# segundos con la cámara andando (RECETA.md §1, resuelto en Casa Boldo como la sección "s3p").
# Eso se arma recién después de que el usuario apruebe las fotos.
# cumbrera en 6,55, losa del segundo piso en 3,26 y piso terminado en 0,55: el corte se lleva
# primero el techo (deja ver el 2do piso), después baja al primero
CUT_TOP, CUT_MID, CUT_LOW = 7.2, 4.45, 2.30
# claves: (cuadro global, azimut°, elevación°, distancia, altura de corte, parar)
#   distancia: número (m) o ("fit", factor): la del encuadre adaptable en esa dirección
#   parar=True: la cámara llega quieta a esa clave (fin de s3, antes del paso a la planta)
RUTA = [
    (0, S1_AZ[1], S1_EL[1], ("fit", 1.0), CUT_TOP, True),     # = último cuadro de s1
    (90, 0.0, 13.0, ("frente", 1.0), CUT_TOP, False),         # de frente al testero vidriado
    (192, 62.0, 16.0, ("frente", 1.0), CUT_TOP, False),       # fin s2: costado, sobre los pilotes
    (262, 78.0, 40.0, ("fit", 1.05), CUT_TOP, False),
    (352, 86.0, 76.0, ("fit", 1.0), CUT_MID, False),
    (432, 90.0, 89.5, ("fit", 1.0), CUT_LOW, True),           # fin s3: cenital, casa a lo largo de la pantalla
    (500, 122.0, 52.0, ("fit", 1.15), CUT_TOP, False),
    (624, 168.0, 14.0, ("fit", 1.0), CUT_TOP, True),          # fin s5: fachada de acceso y el camino
]
CUT_KEYS = [(0, CUT_TOP), (250, CUT_TOP), (330, CUT_MID), (400, CUT_LOW), (432, CUT_LOW),
            (470, CUT_LOW), (545, CUT_TOP), (624, CUT_TOP)]


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
    frente = max(fit_distance(_dir(a, 15.0), CASA_C, lens, w / h) for a in range(-45, 75, 5))
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
    capped = {"ChapaNegra", "MaderaFachada", "MaderaCielo", "MuroInterior", "Pm_MarcoNegro", "Pm_PuertaMadera"}
    mats = {sl.material for o in house for sl in o.material_slots if sl.material}
    techo = bpy.data.materials.get("NieveTecho")      # la nieve del techo se corta con el techo
    if techo:
        mats.add(techo)
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
        if o.type == "MESH" and o.name != "Peumo_Casco":
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
    bpy.context.scene.cycles.transparent_max_bounces = 12




POSES = {"s1": pose_s1}
SETUP = {"s1": s1_setup}
for _t in ("s2", "s3", "s5"):
    POSES[_t] = (lambda t: lambda f, n: ruta_pose(INICIO[t] + f))(_t)
    SETUP[_t] = ruta_setup


def build_drone(cam):
    """Anima la cámara cuadro a cuadro según la sección pedida."""
    sc = bpy.context.scene
    tramo = opts["tramo"]
    n = SECCIONES[tramo]
    sc.frame_start, sc.frame_end = 1, n
    # --desde/--hasta recortan sólo lo que se renderiza, no el recorrido: las poses y la
    # acumulación de nieve se calculan igual para los n cuadros de la sección, así que repartir
    # una sección entre dos contenedores da exactamente los mismos cuadros que hacerla de corrido.
    if opts.get("desde"):
        sc.frame_start = max(1, int(opts["desde"]))
    if opts.get("hasta"):
        sc.frame_end = min(n, int(opts["hasta"]))
    sc.frame_step = int(opts.get("step", "1"))   # >1 para previsualizaciones rápidas
    w, h = (int(v) for v in opts["res"].split("x"))
    lens = 30.0
    cam.data.lens = lens
    SETUP[tramo](w, h, lens)
    for f in range(n):
        pose = POSES[tramo](f, n)
        direc, tgt = pose[0], pose[1]
        dist = pose[2] if len(pose) > 2 else fit_distance(direc, tgt, lens, w / h)
        cam.location = tgt + direc * dist
        cam.rotation_euler = (-direc).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=f + 1)
        cam.keyframe_insert("rotation_euler", frame=f + 1)
    if tramo in ("s3", "s5"):
        apply_section(n, INICIO[tramo])
    if tramo == "s3":   # dónde cae la casa en la cenital: para calzar la planta (tools/plano_peumo.py)
        import json
        from bpy_extras.object_utils import world_to_camera_view
        direc, tgt, dist = ruta_pose(INICIO["s3"] + n - 1)
        cam.location = tgt + direc * dist
        cam.rotation_euler = (-direc).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        pts = {}
        for k, (x, y) in {"o": (0.0, 0.0), "x": (L, 0.0), "y": (0.0, D)}.items():
            v = world_to_camera_view(sc, cam, Vector((x, y, PISO)))
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
    cerca, lejos = build_landscape(M)
    lib, arb_cerca, arb_medio, arb_lejos, renuevos = build_library(M)
    # El bosque va más ralo que en Peumo (dmin más grande, densidad más baja): es una ladera de
    # centro de ski, y lo que tiene que llenar el cuadro es la nieve abierta y el cielo, no las
    # copas. Las bandas de fondo llegan mucho más lejos porque acá se ve hasta la cordillera.
    # El rango de escala va ancho a propósito (0,55 a 1,60): un bosque donde todos los árboles
    # miden lo mismo se lee como una estampilla repetida. Con viejos grandes y renuevos entre
    # medio aparece la textura de bosque de verdad.
    build_forest(cerca, arb_cerca, dmin=5.6, dens=0.13)
    build_forest(lejos, arb_medio, dmin=8.5, dens=0.10, seed=19, escala=(0.62, 1.70),
                 attr="veg_medio", corte=lambda r: min(1.0, max(0.0, (190.0 - r) / 40.0)))
    build_forest(lejos, arb_lejos, dmin=13.0, dens=0.075, seed=23, escala=(0.70, 1.85),
                 attr="veg_lejos", corte=lambda r: min(1.0, max(0.0, (r - 165.0) / 40.0)))
    # renuevos pegados a la casa: lo que crece solo al borde de la plataforma y la enraíza
    build_forest(cerca, renuevos, dmin=3.6, dens=0.22, seed=41, escala=(0.6, 1.25),
                 attr="renuevo", corte=lambda r: min(1.0, max(0.0, (CLARO + 8.0 - r) / 6.0)))
    build_scrub(M, cerca, lib)
    build_lenera(M)
    build_andarivel(M)
    build_balizas(M)
    build_acceso(M)
    build_huellas_esqui(M, cerca)
    build_carambanos(M)
    build_world()
    setup_render()
    sc = bpy.context.scene
    if opts["vista"] == "dron":
        cam = link(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
        cam.data.clip_end = 5000
        sc.camera = cam
        build_drone(cam)
        animar_carga(SECCIONES[opts["tramo"]], VIDEO_G0[opts["tramo"]])
        # la nevada va sólo en la quinta parte: en las otras tapa la casa y el bosque
        if opts["tramo"] == "s5":
            build_snowfall(M, caja=(72.0, 72.0, 30.0), fuerza=float(opts["nevada"]))
    else:
        cam = build_camera()
        for ng in bpy.data.node_groups:
            if "Carga" in ng.nodes:
                ng.nodes["Carga"].outputs[0].default_value = float(opts["carga"])
        loc, tgt, _ = VISTAS[opts["vista"]]
        loc = (loc[0], loc[1], terrain_h(loc[0], loc[1]) + loc[2])
        build_snowfall(M, loc, tgt, fuerza=float(opts["nevada"]))
        if opts.get("dof", "1") != "0":
            cam.data.dof.use_dof = True
            cam.data.dof.focus_distance = (Vector(tgt) - Vector(loc)).length
            cam.data.dof.aperture_fstop = 4.0
    if opts["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=opts["save"])
    sc.render.filepath = opts["out"]
    if opts["vista"] == "dron" and not opts.get("cuadro"):
        bpy.ops.render.render(animation=True)
    else:
        sc.frame_set(int(opts.get("cuadro") or opts["still"]))
        bpy.ops.render.render(write_still=True)


main()
