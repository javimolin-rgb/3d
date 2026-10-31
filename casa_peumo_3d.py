"""Escena 3D de Casa Peumo en un bosque nevado (Blender 5.x, Cycles).

Uso:
  python casa_peumo_3d.py -- --vista izq --still 1 --out cuadro.png [--res 720x1280] [--samples 32]
  (vistas: izq / der = tomas fijas de dron desde el frente vidriado; izq_atras / der_atras = las
  opuestas, desde la fachada de acceso. El recorrido de dron por secciones se arma después de que
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
        "wb": "6900", "save": None}
for i in range(0, len(argv), 2):
    opts[argv[i].lstrip("-")] = argv[i + 1]

random.seed(11)
ROOT = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.join(ROOT, "assets", "peumo", "casa.blend")
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
CLARO = 11.0                 # radio del claro del bosque alrededor de la casa
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
    M["corteza"] = bark_mat()
    M["corteza_clara"] = bark_mat("CortezaClara", (0.16, 0.135, 0.105), (0.06, 0.05, 0.042))
    M["follaje"] = foliage_mat("Follaje", (0.022, 0.048, 0.024), (0.010, 0.025, 0.014))
    M["follaje2"] = foliage_mat("Follaje2", (0.030, 0.052, 0.028), (0.014, 0.030, 0.017))
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
    """Distancia al claro, medida en una elipse estirada hacia -Y: el bosque encierra la casa por
    los costados y por atrás, pero se abre delante del ventanal. Es lo que hace que el testero
    tenga algo que mirar —y lo que deja plantar la cámara sin un árbol encima."""
    dx = (x - HC.x) / 1.15
    dy = (y - HC.y) / (2.2 if y < HC.y else 1.25)
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
    """Distancia a la huella de pisadas que sale del porch (+Y) hacia el camino del bosque."""
    t = max(0.0, min(1.0, (y - D) / 26.0))
    px = L * 0.72 + 5.5 * t * t - 1.5 * math.sin(t * 3.4)
    return math.hypot(x - px, 0.0) if y > D else math.hypot(x - px, D - y)


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
    sopla = (0.30 * noise.noise(Vector((x / 6.5, y / 6.5, 11.3)))
             + 0.12 * noise.noise(Vector((x / 2.2, y / 2.2, 14.7))))
    h = base * plano + cerros + sopla * (0.45 + 0.55 * plano)
    # la nieve se acumula contra la casa: un lomo bajo que la asienta en el terreno
    d = house_dist(x, y)
    if d < 4.0:
        h += 0.30 * (1.0 - d / 4.0) ** 2
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
    cerca = grid("NieveCerca", -34.0, L + 34.0, -34.0, D + 34.0, 0.9, M["nieve"], coll)
    dentro = (lambda x, y: -34.0 <= x <= L + 34.0 and -34.0 <= y <= D + 34.0)
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
def conifera(M, name, h=11.0, faldas=14, r0=1.6, nieve=True):
    """Conífera de cono por capas: tronco y faldones que se achican hacia arriba, con la carga de
    nieve encima. La nieve sobre las ramas no es material, es geometría: un cono más chico apoyado
    sobre el faldón, y no en todos —la nieve se sostiene en parches, no en discos parejos—. Sin
    esta carga el árbol se ve verde y limpio y la escena de nieve se cae (RECETA.md §5)."""
    partes = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=h * 0.014, depth=h, location=(0, 0, h / 2))
    t = bpy.context.object
    t.data.materials.append(M["corteza"])
    partes.append(t)
    for i in range(faldas):
        u = i / (faldas - 1)
        z = h * (0.20 + 0.78 * u)
        r = r0 * (1.0 - u) ** 0.7 + 0.08
        hh = h * 0.13 * (1.0 - 0.4 * u)
        jit = random.uniform(-0.09, 0.09)
        bpy.ops.mesh.primitive_cone_add(vertices=9, radius1=r, radius2=r * 0.12, depth=hh,
                                        location=(jit, jit, z + hh / 2))
        c = bpy.context.object
        c.data.materials.append(M["follaje" if i % 2 else "follaje2"])
        for v in c.data.vertices:                       # un cono perfecto no existe en el bosque
            v.co.x *= random.uniform(0.80, 1.20)
            v.co.y *= random.uniform(0.80, 1.20)
            v.co.z *= random.uniform(0.9, 1.1)
        partes.append(c)
        if nieve and random.random() < 0.72:
            rs = r * random.uniform(0.55, 0.85)
            bpy.ops.mesh.primitive_cone_add(vertices=9, radius1=rs, radius2=rs * 0.25,
                                            depth=hh * 0.26,
                                            location=(jit + random.uniform(-0.1, 0.1),
                                                      jit + random.uniform(-0.1, 0.1),
                                                      z + hh * 0.78))
            sn = bpy.context.object
            sn.data.materials.append(M["nieve_rama"])
            for v in sn.data.vertices:
                v.co.x *= random.uniform(0.7, 1.3)
                v.co.y *= random.uniform(0.7, 1.3)
                v.co.z *= random.uniform(0.7, 1.3)
            partes.append(sn)
    # la punta, siempre nevada
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=r0 * 0.16, radius2=0.0, depth=h * 0.1,
                                    location=(0, 0, h * 0.99))
    pt = bpy.context.object
    pt.data.materials.append(M["nieve_rama"])
    partes.append(pt)
    bpy.ops.object.select_all(action="DESELECT")
    for p in partes:
        p.select_set(True)
    bpy.context.view_layer.objects.active = partes[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def arbol_desnudo(M, name, h=9.0):
    """Árbol sin hojas: tronco y unas ramas con nieve encima. Mezclados entre las coníferas dan
    la variedad del bosque de verdad y leen muy bien en contraluz contra la bruma."""
    partes = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=7, radius=h * 0.022, depth=h, location=(0, 0, h / 2))
    t = bpy.context.object
    t.data.materials.append(M["corteza_clara"])
    partes.append(t)
    for i in range(11):
        z = h * random.uniform(0.32, 0.96)
        a = random.uniform(0, math.tau)
        lr = h * random.uniform(0.16, 0.30)
        incl = math.radians(random.uniform(52, 74))
        cx, cy = math.cos(a) * lr * 0.5 * math.sin(incl), math.sin(a) * lr * 0.5 * math.sin(incl)
        cz = z + lr * 0.5 * math.cos(incl)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=h * 0.014, depth=lr,
                                            location=(cx, cy, cz))
        r = bpy.context.object
        r.rotation_euler = (0, incl, a)
        r.data.materials.append(M["corteza_clara"])
        partes.append(r)
        # la nieve se apoya sobre la rama: mismo eje, apenas más gruesa y corrida hacia arriba
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=h * 0.016, depth=lr * 0.8,
                                            location=(cx, cy, cz + h * 0.011))
        sn = bpy.context.object
        sn.rotation_euler = (0, incl, a)
        sn.scale = (1.0, 0.55, 1.0)
        sn.data.materials.append(M["nieve_rama"])
        partes.append(sn)
    bpy.ops.object.select_all(action="DESELECT")
    for p in partes:
        p.select_set(True)
    bpy.context.view_layer.objects.active = partes[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    return o


def build_library(M):
    """Variantes de árbol en una colección aparte, que el esparcido instancia."""
    lib = bpy.data.collections.new("Biblioteca")
    for i, h in enumerate((15.0, 12.0, 9.5, 18.0, 7.5, 13.0)):
        o = conifera(M, f"Conifera{i}", h=h, faldas=15 if h > 10 else 12,
                     r0=h * 0.135 * random.uniform(0.85, 1.15))
        bpy.context.scene.collection.objects.unlink(o)
        lib.objects.link(o)
    for i, h in enumerate((11.0, 8.0)):
        o = arbol_desnudo(M, f"Desnudo{i}", h=h)
        bpy.context.scene.collection.objects.unlink(o)
        lib.objects.link(o)
    return lib


def build_forest(terreno, lib, dmin=3.4, dens=0.22, seed=7, escala=(0.72, 1.25)):
    """Bosque con nodos de geometría sobre una malla de terreno, según un atributo 'veg' calculado
    en Python: 0 en el claro de la casa y sobre la huella, 1 en el bosque, modulado por dos octavas
    de ruido para que haya matas y claros en vez de una grilla pareja (RECETA.md §3). Se corre
    sobre las dos mallas —la fina del claro y la gruesa del fondo—, si no el bosque se termina de
    golpe donde termina la malla fina y la casa queda en un descampado blanco."""
    me = terreno.data
    veg = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        w = min(1.0, max(0.0, (claro_d(x, y) - CLARO) / 5.0))   # el claro alrededor de la casa
        w *= min(1.0, max(0.0, (path_dist(x, y) - 2.2) / 2.0))  # el camino queda libre
        w *= min(1.0, max(0.0, (cam_dist(x, y) - 5.5) / 3.5))   # nada de árboles pegados al lente
        w *= min(1.0, max(0.0, 0.80 + 1.1 * noise.noise(Vector((x / 13.0, y / 13.0, 1.9)))
                          + 0.35 * noise.noise(Vector((x / 4.0, y / 4.0, 5.3)))))
        veg.append(max(0.0, min(1.0, w)))
    at = me.attributes.get("veg") or me.attributes.new("veg", "FLOAT", "POINT")
    at.data.foreach_set("value", veg)
    ng = bpy.data.node_groups.new("Bosque_" + terreno.name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    Lk.new(gi.outputs[0], join.inputs[0])
    at_n = N.new("GeometryNodeInputNamedAttribute")
    at_n.data_type = "FLOAT"
    at_n.inputs["Name"].default_value = "veg"
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = dmin
    dist.inputs["Density Max"].default_value = dens
    dist.inputs["Seed"].default_value = seed
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    Lk.new(at_n.outputs[0], dist.inputs["Density Factor"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = lib
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rnd = N.new("FunctionNodeRandomValue")
    rnd.data_type = "INT"
    rnd.inputs[5].default_value = len(lib.objects) - 1
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
    md = terreno.modifiers.new("Bosque", "NODES")
    md.node_group = ng


def build_scrub(M, terreno):
    """Matas nevadas y montículos en el claro. Es lo que rompe el blanco del primer plano: en un
    claro de verdad asoman arbustos tapados, tocones y lomos de nieve, no una sábana lisa."""
    lib = bpy.data.collections.new("Matas")
    for i in range(5):
        partes = []
        a = random.uniform(0.5, 1.2)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=a,
                                              location=(0, 0, a * 0.42))
        m = bpy.context.object
        m.scale = (random.uniform(1.1, 2.0), random.uniform(1.1, 2.0), random.uniform(0.16, 0.30))
        for v in m.data.vertices:
            v.co.x *= random.uniform(0.75, 1.3)
            v.co.y *= random.uniform(0.75, 1.3)
            v.co.z *= random.uniform(0.7, 1.2)
        m.data.materials.append(M["nieve_rama"])
        partes.append(m)
        if i % 2:                                   # alguna rama oscura que asoma de la mata
            for _ in range(3):
                an = random.uniform(0, math.tau)
                bpy.ops.mesh.primitive_cylinder_add(vertices=5, radius=0.028, depth=a * 1.5,
                                                    location=(math.cos(an) * a * 0.3,
                                                              math.sin(an) * a * 0.3, a * 0.75))
                r = bpy.context.object
                r.rotation_euler = (0, random.uniform(0.3, 0.8), an)
                r.data.materials.append(M["corteza_clara"])
                partes.append(r)
        bpy.ops.object.select_all(action="DESELECT")
        for q in partes:
            q.select_set(True)
        bpy.context.view_layer.objects.active = partes[0]
        bpy.ops.object.join()
        o = bpy.context.object
        o.name = f"Mata{i}"
        for q in o.data.polygons:
            q.use_smooth = True
        bpy.context.scene.collection.objects.unlink(o)
        lib.objects.link(o)
    me = terreno.data
    val = []
    for v in me.vertices:
        x, y = v.co.x, v.co.y
        w = min(1.0, max(0.0, (house_dist(x, y) - 2.5) / 3.0))
        w *= min(1.0, max(0.0, (path_dist(x, y) - 1.8) / 1.5))
        w *= min(1.0, max(0.0, 0.45 + 1.3 * noise.noise(Vector((x / 5.0, y / 5.0, 21.5)))))
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
    dist.inputs["Distance Min"].default_value = 2.6
    dist.inputs["Density Max"].default_value = 0.22
    dist.inputs["Seed"].default_value = 31
    Lk.new(gi.outputs[0], dist.inputs["Mesh"])
    Lk.new(at_n.outputs[0], dist.inputs["Density Factor"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    info = N.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = lib
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    rnd = N.new("FunctionNodeRandomValue")
    rnd.data_type = "INT"
    rnd.inputs[5].default_value = len(lib.objects) - 1
    rnd.inputs["Seed"].default_value = 11
    esc = N.new("FunctionNodeRandomValue")
    esc.data_type = "FLOAT_VECTOR"
    esc.inputs[0].default_value = (0.5, 0.5, 0.4)
    esc.inputs[1].default_value = (1.3, 1.3, 1.1)
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


def build_far_forest(M):
    """Bosque de fondo: no son árboles, es una masa oscura y dentada sobre los cerros. A esa
    distancia la bruma se come el detalle, y poner árboles de verdad costaría horas de render."""
    coll = bpy.data.collections.new("BosqueLejos")
    bpy.context.scene.collection.children.link(coll)
    random.seed(23)
    for i in range(1400):
        a = random.uniform(0, math.tau)
        r = random.uniform(150.0, 260.0)
        x, y = HC.x + math.cos(a) * r, HC.y + math.sin(a) * r
        h = random.uniform(8.0, 15.0) * (0.8 + r / 420.0)
        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=h * 0.115, radius2=0.0, depth=h,
                                        location=(x, y, terrain_h(x, y) + h / 2 - 0.6))
        o = bpy.context.object
        o.data.materials.append(M["lejos"])
        o.scale = (random.uniform(0.8, 1.2), random.uniform(0.8, 1.2), 1.0)
        bpy.context.scene.collection.objects.unlink(o)
        coll.objects.link(o)
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

    # bruma = 0,74 · (1 − e^(−(z − 22) / 190)), sobre todo lo que no es cielo (z < 10 km de cámara
    # para el cielo no hay superficie: su profundidad es enorme). En un bosque la bruma tiene que
    # entrar mucho antes que en la playa: es lo que separa las filas de troncos y da profundidad.
    sc.view_layers[0].use_pass_z = True
    zrel = mnode("SUBTRACT", 22.0)
    pos = mnode("MAXIMUM", 0.0)
    sc_ = mnode("DIVIDE", -190.0)
    ex = mnode("EXPONENT", 0.0)
    one = mnode("SUBTRACT", 1.0)
    sky = mnode("LESS_THAN", 1.0e7)
    mul = mnode("MULTIPLY", 1.0)
    amt = mnode("MULTIPLY", 0.74)
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



def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = materials()
    load_house(M)
    cerca, lejos = build_landscape(M)
    lib = build_library(M)
    build_forest(cerca, lib)
    build_forest(lejos, lib, dmin=6.0, dens=0.1, seed=19, escala=(0.85, 1.4))
    build_scrub(M, cerca)
    build_far_forest(M)
    build_world()
    setup_render()
    sc = bpy.context.scene
    build_camera()
    if opts["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=opts["save"])
    sc.render.filepath = opts["out"]
    sc.frame_set(int(opts["still"]))
    bpy.ops.render.render(write_still=True)


main()
