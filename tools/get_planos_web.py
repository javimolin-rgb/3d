"""Baja de neorigen.cl la lámina "Planta y Distribución" de cada modelo.

Es la planta sin cotas que necesita la sección 4 del recorrido de dron (RECETA.md §1), la misma
que hasta ahora se pedía al usuario por Drive. El sitio la publica para ocho de los nueve modelos,
así que conviene sacarla de ahí en vez de esperarla: queda en
`assets/<casa>/planta_sin_cotas.png`, 1400 px de ancho, que de sobra para una lámina que termina
mostrándose a 720x1280.

Cómo se encuentra: cada página de modelo tiene el rótulo "PLANTA Y DISTRIBUCIÓN" y la lámina es la
primera imagen que viene después. Buscarla por nombre de archivo no sirve —sólo dos de las nueve
se llaman `plano_<casa>.png`, el resto tiene nombres sueltos como `lingue-03.png` o un hash—, y
por eso el filtro es por posición en la página y no por nombre.

De la URL se le quita la transformación de Wix (`/v1/fill/w_...`) para pedir el archivo original.

No se tocan las casas que ya tienen su `planta_sin_cotas.pdf` (Huingán y Peumo, bajadas del Drive
de Neorigen): esas son las que están calibradas en `tools/plano_*.py` y son el dibujo bueno. La
versión web es la misma planta con otra diagramación —vertical y con la franja de marca, en vez de
apaisada con los dos pisos rotulados—, así que reemplazarlas obligaría a recalibrar sin ganar nada.

Casa Ciprés no tiene planta publicada: su página no trae el rótulo.

Uso:  python3 tools/get_planos_web.py [--forzar]
"""
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.neorigen.cl/modelo-"
UA = "neorigen-render/1.0"
# nombre de la casa en el repo -> slug en el sitio
CASAS = {"lingue": "lingue", "huingan": "huingan", "peumo": "peumo", "boldo": "boldo",
         "manio": "manio", "roble": "roble", "maiten": "maiten", "coihue": "coihue",
         "cipres": "cipres"}
ROTULO = "PLANTA Y DISTRIBUCI"
MEDIA = re.compile(r"https://static\.wixstatic\.com/media/"
                   r"([a-z0-9]+_[a-z0-9]+~mv2\.(?:png|jpg))/v1/[^\s\"')]*")
FORZAR = "--forzar" in sys.argv


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


for casa, slug in CASAS.items():
    dest_dir = os.path.join(ROOT, "assets", casa)
    pdf = os.path.join(dest_dir, "planta_sin_cotas.pdf")
    png = os.path.join(dest_dir, "planta_sin_cotas.png")
    if os.path.exists(pdf) and not FORZAR:
        print(f"{casa:9s} ya tiene la lámina del Drive (PDF), se deja como está")
        continue
    if os.path.exists(png) and not FORZAR:
        print(f"{casa:9s} ya estaba")
        continue
    try:
        html = bajar(BASE + slug).decode("utf-8", "replace")
    except Exception as e:                                   # noqa: BLE001
        print(f"{casa:9s} no se pudo leer la página: {e}")
        continue
    i = html.upper().find(ROTULO)
    if i < 0:
        print(f"{casa:9s} la página no trae planta publicada")
        continue
    m = MEDIA.search(html, i, i + 8000)
    if not m:
        print(f"{casa:9s} rótulo sin imagen detrás")
        continue
    datos = bajar("https://static.wixstatic.com/media/" + m.group(1))
    os.makedirs(dest_dir, exist_ok=True)
    with open(png, "wb") as f:
        f.write(datos)
    print(f"{casa:9s} {len(datos) // 1024:5d} KB  <- {m.group(1)}")
