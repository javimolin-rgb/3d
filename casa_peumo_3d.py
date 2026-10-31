"""Escena 3D de Casa Peumo en un bosque nevado (Blender 5.x, Cycles).

Uso:
  python casa_peumo_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  python casa_peumo_3d.py -- --vista dron --tramo s1 --out frames_peumo/s1/f_ --res 720x1280
  (vistas: izq / der = tomas fijas de dron desde el frente vidriado; izq_atras / der_atras = las
  opuestas, desde la fachada de acceso. --nevada gradúa la nieve cayendo: 0 la apaga, 1 es nevada
  normal, 2,5 es nevando fuerte. --dof 0 apaga el desenfoque. El recorrido de dron por secciones se arma después de que
  el usuario apruebe estas fotos: RECETA.md §0.)

La casa sale del modelo STL de Neorigen (assets/peumo/casa.blend, generado con
tools/extraer_peumo_stl.py, variante "Ventanal Grande"): 9,49 m de ancho por 13,04 de fondo,
terraza hacia -Y bajo el testero vidriado de doble altura, porch de acceso hacia +Y, techo a dos
aguas asimétrico (cumbrera en x = 7,61, faldones de 28° y 33°), piso terminado en z = 0,60 sobre
pilotes y terreno en z = 0.

Paisaje: bosque nevado del sur, día nublado. Claro entre los árboles con la casa al medio, nieve
con subsurface scattering, nieve cargada sobre las ramas, huella de pisadas hasta el acceso y
bruma entre los troncos. El enganche (ENGANCHES.md) es el testero: desde el estar el bosque
nevado ocupa la pared entera, así que las tomas se plantan frente al ventanal.

Las tres cosas que deciden si la nieve se ve real (RECETA.md §5):
  1. subsurface en el material de nieve, si no se lee como yeso;
  2. sombras azules, que salen solas si el cielo físico calza con el HDRI;
  3. un rebote difuso más (3), porque la nieve devuelve muchísima luz, y exposición más baja.
"""
import math
import os
import random
import sys

import bpy  # noqa: E402  (bpy debe importarse antes que bmesh)
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"vista": "izq", "out": "//cuadro.png", "res": "720x1280", "samples": "32", "still": "1",
        "wb": "6900", "save": None, "dof": "1",
        "nevada": "1.0", "tramo": "s1"}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(11)
ROOT = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.join(ROOT, "assets", "peumo", "casa.blend")
PH = os.path.join(ROOT, "assets", "nieve", "ph")   # modelos CC0 (tools/get_assets_nieve.sh)
HDRI = os.path.join(ROOT, "assets", "hdri", "nieve", "snowy_forest_path_01_2k.exr")  # CC0
HDRI_SUN_U = 0.6010          # columna del sol en el HDRI (0-1), medida con tools/medir_sol_hdri.py
SUN_ELEV = 20.6              # elevación del sol en el HDRI
SKY_GAIN = 0.11              # brillo del cielo físico (horizonte) para empatar con el HDRI
SUN_AZ = 200.0               # luz desde adelante-izquierda (azimut desde +Y hacia +X)
WB_TEMP = float(opts["wb"])  # más cálido que la playa: compensa el azul del día nublado
L, D = 9.49, 13.04           # ancho y fondo del casco (terraza + caja + porch)
HC = Vector((L / 2, D / 2))  # centro de la casa en planta
GROUND = 0.0                 # terreno bajo la casa (base de los pilotes)
PISO = 0.60                  # piso terminado
# El claro tiene que dar para la órbita del dron. Con la casa de 9,5 x 13 m y lente de 30 mm, el
# encuadre adaptable deja la cámara a unos 31 m: si el claro es más chico que eso, el dron orbita
# por dentro del bosque y los árboles le tapan el lente. Así que el claro es grande, pero no es un
# potrero: adentro quedan renuevos, matas, tocones y algunos árboles grandes sueltos, y la franja
# por donde pasa la órbita es la única que va del todo despejada.
CLARO = 30.0                 # radio del claro del bosque alrededor de la casa
ORBITA = (23.0, 40.0)        # franja radial por donde pasa el dron: sin árboles grandes
# La nieve cae con viento: 25° de inclinación. Cayendo a plomo se ve falsa, y además en video el
# motion blur convierte cada copo en un hilo, y son esos hilos inclinados los que leen como nevada.
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



# ---------------------------------------------------------------- materiales de nieve y bosque
def snow_mat(name="Nieve", sss=0.38, rough=0.38, bump=0.5):
    """Nieve: lo decisivo es el subsurface. Sin translucidez la nieve se lee como yeso; con un
    scattering corto y apenas azulado aparece el brillo interno que la delata como nieve. El
    relieve son tres escalas de ruido (lomos de viento, grumos y grano) y el grano fino además
    pica la rugosidad, que es de dónde sale el destello."""
    m, n, l = new_mat(name)
    N = Nodos(n, l)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    v = tc.outputs["Object"]
    b.inputs["Base Color"].default_value = (0.90, 0.93, 0.97, 1)
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Radius"].default_value = (0.09, 0.11, 0.17)   # el azul viaja más adentro
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
    M["nieve"] = snow_mat()
    M["nieve_rama"] = snow_mat("NieveRama", sss=0.45, rough=0.33, bump=0.8)
    M["copo"] = principled("Copo", (0.95, 0.96, 0.98), 0.6)
    M["corteza"] = bark_mat()
    M["corteza_clara"] = bark_mat("CortezaClara", (0.16, 0.135, 0.105), (0.06, 0.05, 0.042))
    M["follaje"] = foliage_mat("Follaje", (0.022, 0.048, 0.024), (0.010, 0.025, 0.014))
    M["follaje2"] = foliage_mat("Follaje2", (0.030, 0.052, 0.028), (0.014, 0.030, 0.017))
    M["follaje_nevado"] = principled("FollajeNevado", (0.105, 0.125, 0.115), 0.80)
    M["lejos"] = principled("BosqueLejos", (0.055, 0.070, 0.062), 0.9)
    return M


def load_house(M):
    """Casa del STL con los materiales de la escena (por nombre de material del .blend)."""
    with bpy.data.libraries.load(CASA) as (a, b):
        b.objects = a.objects
    swap = {"Pm_ChapaNegra": M["chapa"], "Pm_MaderaFachada": M["fachada"], "Pm_MaderaCielo": M["cielo"],
            "Pm_Deck": M["deck"], "Pm_PisoInterior": M["piso"], "Pm_MuroInterior": M["muroint"],
            "Pm_Vidrio": M["vidrio"], "Pm_Pilote": M["hormigon"]}
    coll = bpy.data.collections.new("Casa")
    bpy.context.scene.collection.children.link(coll)
    for o in b.objects:
        coll.objects.link(o)
        for sl in o.material_slots:
            if sl.material and sl.material.name in swap:
                sl.material = swap[sl.material.name]
    # nieve en el techo: una capa rala, limitada al material de la chapa. Los 28° descargan la
    # nieve solos (es el enganche de la casa), pero un techo impecable en medio de una nevada
    # delata que la casa se posó ahí hace un segundo.
    casco = next((o for o in coll.objects if "Casco" in o.name), None)
    if casco:
        nevar(casco, M, dens=110.0, tam=0.075, umbral=0.55, solo=M["chapa"])
    # luces interiores tibias: con el día nublado afuera, son las que hacen que el ventanal
    # se lea como una casa habitada y no como un vidrio apagado
    for x, y, z, p in ((4.6, 5.0, 2.3, 150), (8.2, 4.6, 2.1, 70), (3.0, 10.4, 2.2, 90),
                       (8.3, 5.0, 4.6, 70), (4.8, 3.2, 2.5, 60)):
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        lt = bpy.context.object
        lt.data.energy, lt.data.size = p, 1.0
        lt.data.color = (1.0, 0.70, 0.42)
    return coll


# ---------------------------------------------------------------- terreno
def claro_d(x, y):
    """Distancia al claro, medida en una elipse algo estirada hacia -Y: el claro se abre un poco
    más delante del ventanal, que es lo que el testero tiene para mirar."""
    dx = (x - HC.x) / 1.15
    dy = (y - HC.y) / (1.35 if y < HC.y else 1.1)
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


def path_dist(x, y):
    """Distancia a las huellas en la nieve: la que sale del porch (+Y) hacia el camino del bosque
    y la que baja de la escalera de la terraza (-Y) y se pierde entre los árboles. Las pisadas son
    lo que dice que la casa está habitada y no recién puesta ahí."""
    t = max(0.0, min(1.0, (y - D) / 26.0))
    px = L * 0.72 + 5.5 * t * t - 1.5 * math.sin(t * 3.4)
    d1 = math.hypot(x - px, 0.0) if y > D else math.hypot(x - px, D - y)
    u = max(0.0, min(1.0, -y / 14.0))
    qx = L * 0.28 - 4.0 * u * u + 1.2 * math.sin(u * 3.0)
    d2 = math.hypot(x - qx, 0.0) if y < 0 else math.hypot(x - qx, y)
    return min(d1, d2)


def terrain_h(x, y):
    """Terreno nevado: un claro casi plano donde se posa la casa y lomas suaves hacia el bosque,
    que suben a los cerros del fondo. La nieve redondea todo, así que nada de aristas."""
    r = math.hypot(x - HC.x, y - HC.y)
    base = (1.25 * noise.noise(Vector((x / 26.0, y / 26.0, 0.7)))
            + 0.55 * noise.noise(Vector((x / 9.0, y / 9.0, 3.1)))
            + 0.18 * noise.noise(Vector((x / 3.0, y / 3.0, 6.4))))
    lejos = max(0.0, (r - 55.0) / 95.0)
    cerros = 26.0 * lejos ** 1.7 * (1.0 + 0.55 * noise.noise(Vector((x / 70.0, y / 70.0, 9.2))))
    plano = max(0.0, min(1.0, (r - 7.0) / 9.0))          # el claro de la casa, casi a nivel
    # aun en el claro la nieve ondula: ventisqueros bajos que cruzan el terreno. Sin esto el
    # primer plano es una mesa de billar blanca y delata que es CG.
    sopla = (0.46 * noise.noise(Vector((x / 6.5, y / 6.5, 11.3)))
             + 0.20 * noise.noise(Vector((x / 2.4, y / 2.4, 14.7)))
             + 0.07 * noise.noise(Vector((x / 1.1, y / 1.1, 18.2))))
    h = base * plano + cerros + sopla * (0.45 + 0.55 * plano)
    # la nieve se amontona contra la casa: el viento la arrima a los muros y deja un ventisquero
    # que sube por los pilotes. Sin él la casa se ve apoyada sobre la nieve en vez de metida en ella.
    d = house_dist(x, y)
    if d < 6.5:
        amontona = (1.0 - d / 6.5) ** 2
        h += (0.62 + 0.22 * noise.noise(Vector((x / 3.0, y / 3.0, 31.0)))) * amontona
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
    """Suelo nevado: malla fina en el claro (donde se ven las huellas y el relieve) y una gruesa
    hasta los cerros del fondo, que la bruma termina de fundir con el cielo."""
    coll = bpy.data.collections.new("Terreno")
    bpy.context.scene.collection.children.link(coll)
    cerca = grid("NieveCerca", -46.0, L + 46.0, -46.0, D + 46.0, 1.1, M["nieve"], coll)
    dentro = (lambda x, y: -46.0 <= x <= L + 46.0 and -46.0 <= y <= D + 46.0)
    lejos = grid("NieveLejos", -230.0, L + 230.0, -230.0, D + 230.0, 5.0, M["nieve"], coll,
                 skip=dentro, sink=dentro)
    hundir_huella(cerca)
    return cerca, lejos


def hundir_huella(o):
    """Pisadas: la huella no se dibuja, se hunde. Un surco de pocos centímetros con el borde
    levantado basta para que se lea el camino hasta el acceso."""
    for v in o.data.vertices:
        d = path_dist(v.co.x, v.co.y)
        if d < 1.6:
            v.co.z -= 0.13 * (1.0 - d / 1.6) ** 1.5
            v.co.z += 0.05 * max(0.0, 1.0 - abs(d - 1.0) / 0.6)     # borde pisoteado
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
    miles de árboles nevados no entra en memoria."""
    for sl in o.material_slots:
        if sl.material:
            sl.material = M["follaje_nevado"]
    return o


def nevar(o, M, dens=110.0, tam=0.075, umbral=0.45, solo=None):
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
    src.data.materials.append(M["nieve_rama"])
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
    dele = N.new("GeometryNodeDeleteGeometry")
    dele.domain = "POINT"
    Lk.new(d.outputs["Points"], dele.inputs["Geometry"])
    Lk.new(cmp.outputs[0], dele.inputs["Selection"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = src
    esc = N.new("FunctionNodeRandomValue")
    esc.data_type = "FLOAT_VECTOR"
    esc.inputs[0].default_value = (tam * 0.5, tam * 0.5, tam * 0.3)
    esc.inputs[1].default_value = (tam * 1.8, tam * 1.8, tam * 1.0)
    rot = N.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT_VECTOR"
    rot.inputs[0].default_value = (0.0, 0.0, 0.0)
    rot.inputs[1].default_value = (0.35, 0.35, math.tau)
    Lk.new(dele.outputs[0], inst.inputs["Points"])
    Lk.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    Lk.new(esc.outputs["Value"], inst.inputs["Scale"])
    Lk.new(rot.outputs["Value"], inst.inputs["Rotation"])
    Lk.new(inst.outputs[0], join.inputs[0])
    Lk.new(join.outputs[0], go.inputs[0])
    md = o.modifiers.new("Nieve", "NODES")
    md.node_group = ng
    return o


def build_library(M):
    """Árboles reales de Poly Haven (CC0), nevados. Son abetos y pinos de verdad, con ramas y
    acículas: es lo único que hace que un bosque nevado no se vea de cartón.

    Van en tres bandas, y la del medio existe justamente para que no se note el cambio: con sólo
    dos, a los treinta y pico de metros se pasaba de golpe de un árbol nevado en detalle a una
    silueta aclarada, y ese salto delataba el truco más que la propia silueta del fondo.
      cerca  LOD1 con nieve de geometría densa
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
    arboles(cerca, "LOD1", 85.0, 0.075)
    arboles(medio, "LOD2", 32.0, 0.11)
    arboles(lejos, "LOD2", None, None)
    # renuevos: lo que crece en el claro, al borde del bosque
    for ident, nombres in (("fir_sapling_medium", ["fir_sapling_medium_a_LOD1", "fir_sapling_medium_b_LOD1"]),
                           ("fir_sapling", ["fir_sapling_a_LOD1", "fir_sapling_b_LOD1"]),
                           ("pine_sapling_small", ["pine_sapling_small_a", "pine_sapling_small_b",
                                                   "pine_sapling_small_c"])):
        for o in load_ph(renuevos, ident, nombres):
            nevar(realizar(o), M, dens=240.0, tam=0.05)
    for c in (lib, cerca, medio, lejos, renuevos):
        c.hide_render = c.hide_viewport = True
    return lib, cerca, medio, lejos, renuevos


def build_forest(terreno, arboles, dmin=3.4, dens=0.22, seed=7, escala=(0.72, 1.25),
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
        w = min(1.0, max(0.0, (cd - CLARO) / 8.0))              # el bosque cerrado, fuera del claro
        # adentro del claro quedan algunos árboles grandes sueltos, para que no sea un potrero:
        # cerca de la casa dan escala y parallaje, pero la franja de la órbita va limpia
        if cd < ORBITA[0]:
            w = max(w, 0.09)
        elif cd < ORBITA[1]:
            w = 0.0
        w *= min(1.0, max(0.0, (house_dist(x, y) - 1.6) / 2.0))
        w *= min(1.0, max(0.0, (path_dist(x, y) - 2.2) / 2.0))  # el camino queda libre
        w *= min(1.0, max(0.0, (cam_dist(x, y) - 5.5) / 3.5))   # nada de árboles pegados al lente
        w *= min(1.0, max(0.0, 0.80 + 1.1 * noise.noise(Vector((x / 13.0, y / 13.0, 1.9)))
                          + 0.35 * noise.noise(Vector((x / 4.0, y / 4.0, 5.3)))))
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
    rot.inputs[0].default_value = (-0.05, -0.05, 0.0)
    rot.inputs[1].default_value = (0.05, 0.05, math.tau)
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
        "shrub_02": ["shrub_02_a_LOD1", "shrub_02_b_LOD1", "shrub_02_c_LOD1"],
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
            nevar(realizar(o), M, dens=380.0, tam=0.06, umbral=0.38)
            o.location.z = -0.15          # medio enterrados en la nieve
    # un par de lomos de nieve pelados, para los claros entre mata y mata
    for i in range(3):
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
        w *= min(1.0, max(0.0, (CLARO + 10.0 - claro_d(x, y)) / 8.0))
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
    dist.inputs["Distance Min"].default_value = 1.9
    dist.inputs["Density Max"].default_value = 0.40
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


def build_snowfall(M, loc=None, tgt=None, n=36000, fuerza=1.0, caja=None):
    """Nieve cayendo, en diagonal por el viento (VIENTO_TAN). Los de más cerca quedan
    desenfocados y se leen como motas blandas —que es como se ve nevar en una foto—, así que la
    cámara va con desenfoque: a 30 mm y f/4 la hiperfocal son ocho metros, o sea que el bosque
    y la casa quedan nítidos y sólo se ablanda lo que pasa a menos de tres metros del lente."""
    coll = bpy.data.collections.new("Nevada")
    bpy.context.scene.collection.children.link(coll)
    n = int(n * fuerza)
    loc, tgt = Vector(loc), Vector(tgt)
    fwd = (tgt - loc).normalized()
    der = fwd.cross(Vector((0, 0, 1))).normalized()
    arr = der.cross(fwd)
    largo = (tgt - loc).length + 14.0
    verts = []
    for _ in range(n):
        # más cerca de la cámara que lejos: es donde el desenfoque los vuelve visibles
        # arrancan a tres metros y medio y se reparten parejo en profundidad: así la densidad en pantalla
        # es pareja. Más cerca que eso el desenfoque los infla y parece lente sucio.
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
    x0, y0 = L + 0.18, 3.1
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
    sky.aerosol_density = 3.2       # aire cargado de un día nublado de nieve
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
    w.mist_settings.start = 25
    w.mist_settings.depth = 320
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
    cy.diffuse_bounces = 3        # la nieve tiene albedo altísimo y rebota mucha luz
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
    sc.view_settings.exposure = -0.75    # una escena casi toda blanca se quema fácil con AgX
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

    # bruma = 0,80 · (1 − e^(−(z − 22) / 165)), sobre todo lo que no es cielo (z < 10 km de cámara
    # para el cielo no hay superficie: su profundidad es enorme). En un bosque la bruma tiene que
    # entrar mucho antes que en la playa: es lo que separa las filas de troncos y da profundidad.
    sc.view_layers[0].use_pass_z = True
    zrel = mnode("SUBTRACT", 22.0)
    pos = mnode("MAXIMUM", 0.0)
    sc_ = mnode("DIVIDE", -165.0)
    ex = mnode("EXPONENT", 0.0)
    one = mnode("SUBTRACT", 1.0)
    sky = mnode("LESS_THAN", 1.0e7)
    mul = mnode("MULTIPLY", 1.0)
    amt = mnode("MULTIPLY", 0.80)
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
    # + una bruma de lejanía que funde el bosque de fondo con el cielo: 0,5 · (1 − e^(−z / 900))
    far_s = mnode("DIVIDE", -900.0)
    far_e = mnode("EXPONENT", 0.0)
    far_1 = mnode("SUBTRACT", 1.0)
    far_1.inputs[0].default_value = 1.0
    far_a = mnode("MULTIPLY", 0.50)
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


# tomas fijas de dron. El enganche de Peumo es el testero vidriado de doble altura, así que las
# dos primeras se plantan frente a él (-Y) y las opuestas miran desde el acceso, con el bosque
# nevado detrás. Encuadres a propósito abiertos, para poder reencuadrar en la edición.
VISTAS = {
    "izq": ((-8.0, -15.0, 4.6), (4.2, 3.2, 2.4), 30),
    "der": ((14.5, -13.5, 4.3), (5.4, 3.4, 2.4), 30),
    # opuestas: desde la fachada de acceso y la huella en la nieve
    "izq_atras": ((16.0, 20.0, 6.6), (5.0, 8.5, 2.0), 30),
    "der_atras": ((-9.0, 19.5, 6.2), (4.6, 8.5, 2.0), 30),
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
CASA_BOX = (0.0, L, -1.3, D + 1.3, GROUND, 6.6)      # caja de la casa (con escaleras) para encuadrar
CASA_C = Vector((L / 2, D / 2, 2.0))                 # punto al que mira el dron
FIT = 0.80                                           # ancho de pantalla que ocupa la casa


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
S1_EL = (44.0, 20.0)         # elevación (°): empieza alto, por sobre las copas
# En la playa el dron podía entrar rasante porque no había nada en el medio. Acá, a ras de copas,
# el bosque tapa la casa entera: la aproximación tiene que venir de arriba y bajar al claro.
S1_D0 = 118.0                # distancia inicial (m)


def pose_s1(f, n):
    """Aproximación en espiral: el giro avanza parejo y la distancia cae en escala logarítmica con
    salida suave (el dron frena al llegar). El punto de mira pasa del claro a la casa."""
    u = f / (n - 1)
    ua = u * u * (3 - 2 * u)
    az = math.radians(S1_AZ[0] + (S1_AZ[1] - S1_AZ[0]) * ua)
    el = math.radians(S1_EL[0] + (S1_EL[1] - S1_EL[0]) * ua)
    direc = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    ud = 1 - (1 - u) ** 2.2                          # rápido al comienzo, frena al final
    tgt = Vector((L / 2, -16.0, 1.0)).lerp(CASA_C, smootherstep(min(1.0, u * 1.25)))
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
# Peumo tiene dos pisos, así que el corte baja en dos tiempos en vez de uno: primero se lleva el
# techo y deja ver el segundo piso, después baja al primero. Con un solo escalón, el mezanine y el
# dormitorio principal no se alcanzaban a ver nunca.
CUT_TOP, CUT_MID, CUT_LOW = 7.2, 4.30, 2.35
# claves: (cuadro global, azimut°, elevación°, distancia, altura de corte, parar)
#   distancia: número (m) o ("fit", factor): la del encuadre adaptable en esa dirección
#   parar=True: la cámara llega quieta a esa clave (fin de s3, antes del paso a la planta)
RUTA = [
    (0, S1_AZ[1], S1_EL[1], ("fit", 1.0), CUT_TOP, True),     # = último cuadro de s1
    (90, 0.0, 19.0, ("frente", 1.0), CUT_TOP, False),         # de frente al testero vidriado
    (192, 62.0, 21.0, ("frente", 1.0), CUT_TOP, False),       # fin s2: costado, sobre los pilotes
    (262, 78.0, 40.0, ("fit", 1.05), CUT_TOP, False),
    (352, 86.0, 76.0, ("fit", 1.0), CUT_MID, False),
    (432, 90.0, 89.5, ("fit", 1.0), CUT_LOW, True),           # fin s3: cenital, casa a lo largo de la pantalla
    (500, 122.0, 52.0, ("fit", 1.15), CUT_TOP, False),
    (624, 168.0, 18.0, ("fit", 1.0), CUT_TOP, True),          # fin s5: fachada de acceso y el camino
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
    frente = max(fit_distance(_dir(a, 20.0), CASA_C, lens, w / h) for a in range(-45, 75, 5))
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
    bpy.context.scene.cycles.transparent_max_bounces = 24




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
    build_forest(cerca, arb_cerca)
    # el bosque del fondo, en dos bandas sobre la misma malla, para que el detalle baje de a poco
    build_forest(lejos, arb_medio, dmin=6.5, dens=0.12, seed=19, escala=(0.8, 1.35),
                 attr="veg_medio", corte=lambda r: min(1.0, max(0.0, (105.0 - r) / 26.0)))
    build_forest(lejos, arb_lejos, dmin=8.5, dens=0.10, seed=23, escala=(0.85, 1.5),
                 attr="veg_lejos", corte=lambda r: min(1.0, max(0.0, (r - 88.0) / 26.0)))
    # renuevos pegados a la casa: lo que crece solo al borde del claro y la enraíza en el lugar
    build_forest(cerca, renuevos, dmin=3.2, dens=0.26, seed=41, escala=(0.6, 1.25),
                 attr="renuevo", corte=lambda r: min(1.0, max(0.0, (CLARO + 8.0 - r) / 6.0)))
    build_scrub(M, cerca, lib)
    build_lenera(M)
    build_world()
    setup_render()
    sc = bpy.context.scene
    if opts["vista"] == "dron":
        cam = link(bpy.data.objects.new("Camara", bpy.data.cameras.new("Camara")))
        cam.data.clip_end = 5000
        sc.camera = cam
        build_drone(cam)
        # la nevada va sólo en la quinta parte: en las otras tapa la casa y el bosque
        if opts["tramo"] == "s5":
            build_snowfall(M, caja=(90.0, 90.0, 34.0), fuerza=float(opts["nevada"]))
    else:
        cam = build_camera()
        loc, tgt, _ = VISTAS[opts["vista"]]
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
