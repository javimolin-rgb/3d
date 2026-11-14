# Renders 3D Neorigen

Escenas de Blender (Cycles) generadas por script: `casa_cipres_3d.py`, `casa_lingue_3d.py` y
`casa_huingan_3d.py`.

## Si piden "hacer el modelo de Casa X"

**Leer `RECETA.md` antes de empezar.** Tiene el flujo completo (STL → escena → 5 secciones de
dron → secuencia de 42 s), la receta de realismo que se afinó en Casa Huingán, cómo funciona el
recorrido de dron y el emplazamiento de cada casa con lo que hay que cambiar en cada una.

Emplazamiento de cada casa, en orden de trabajo (detalle en `RECETA.md` §5):

1. Lingue — campo ✅
2. Huingán — playa ✅
3. Peumo — nieve en el bosque ✅
4. Boldo — lago ✅
5. Mañío — playa urbanizada 🔨 en curso (escena lista, esperando el visto bueno de las fotos)
6. Roble — nieve tipo centro de ski
7. Maitén — mar roca
8. Coihue — campo, que se note el trigo
9. Ciprés — playa del norte (más seco) ⚠️

⚠️ El primer Ciprés (campo al atardecer) **no** corresponde a su emplazamiento y está archivado
en `archivo/cipres_v1/`: no partir de ahí, Ciprés se rehace desde Huingán.

**`PENDIENTES.md`** dice qué falta para cada casa antes de poder empezar, con las medidas reales
de cada STL. Los STL están en `stl/` (falta solo el de Ciprés) y los HDRI de todas las familias
ya se bajan con `tools/get_assets_hdri.sh`.

**Las plantas sin cotas de la sección 4 ya no hay que pedirlas**: el sitio las publica y
`tools/get_planos_web.py` las baja a `assets/<casa>/planta_sin_cotas.png` (ocho de las nueve;
Ciprés no tiene planta publicada). Huingán y Peumo conservan su PDF del Drive, que es el que está
calibrado en sus `tools/plano_*.py`. Ojo: las nuevas son **PNG**, así que el `plano_<casa>.py` de
cada casa abre la imagen directo en vez de pasarla por `pdftoppm`.

Los STL de SketchUp traen **restos sueltos y el origen desplazado**, que rompen el encuadre
adaptable: correr `python3 tools/medir_stl.py stl/*.stl` antes de escribir cualquier extractor.

**`ENGANCHES.md`** tiene el gancho narrativo de cada casa (qué la hace distinta: la mariposa de
Huingán, el testero vidriado de Peumo, la pendiente de Roble). El enganche decide qué mira el
dron, así que conviene leerlo antes de ajustar el recorrido.

**Nunca renderizar video de entrada.** Primero mandar fotos fijas desde varios ángulos (~10 min)
y esperar el visto bueno del usuario; recién ahí lanzar el render largo (~17 h). Los ajustes de
luz, materiales o vegetación se hacen sobre las fotos, no sobre el video.

Si la casa pedida no está en esa tabla y no dicen dónde va, **preguntar el emplazamiento antes de
renderizar**: es lo único que no se deduce del STL y equivocarse cuesta horas.

## Renders de video (largos)

- Siempre que se renderice un video, dejar un proceso activo en segundo plano mientras dure
  el render (p. ej. un bucle `while` que espera los cuadros, con `run_in_background` y el
  timeout máximo, re-armándolo cuando expire). Si la sesión queda inactiva, el contenedor
  se suspende o reinicia y el render se corta.
- Lanzar Blender separado de la sesión (`setsid nohup ... &`) y programar además una
  revisión con `send_later` como respaldo.
- El render es reanudable (`use_overwrite = False`): si se corta, borrar los cuadros
  marcadores vacíos (< 10 KB) y relanzar el mismo comando; sigue desde el último cuadro.
- Para saber si Blender sigue vivo no usar `pgrep -f` con el mismo texto del comando de espera
  (se encuentra a sí mismo); usar `ps aux | grep "<patrón>" | grep -v grep` y mirar `uptime`
  (0 min = el contenedor se reinició y hay que relanzar).
- Para acortar un render largo se puede **repartir una sección entre varios contenedores**:
  `--desde N --hasta M` recorta sólo lo que se renderiza (las poses y la nieve acumulada se
  calculan igual para toda la sección, así que los cuadros salen idénticos). Cada contenedor arma
  su tramo con `tools/armar_video.sh` y después se pegan sin recodificar con el demuxer `concat`
  de ffmpeg: el look de `armar_video.sh` no depende del tiempo (la viñeta va con
  `lt(t,1000)`), así que los pedazos quedan con la misma corrección de color.
  Para repartir bien hay que medir el costo cuadro a cuadro en `render.log`, no suponerlo: en la
  sección del corte no crece parejo, hace una loma (en Peumo, 3,3 min/cuadro con el techo cerrado,
  6,5 min con el techo a medio abrir —el interior se ilumina sólo de rebote por una abertura
  parcial— y 3,3 otra vez cuando queda abierto del todo). Partir por la mitad en cantidad de
  cuadros le deja toda la meseta cara a un contenedor.
  Para verificar un empalme, medir sobre los **PNG crudos**, no sobre los MP4: H.264 predice entre
  cuadros vecinos y achica la diferencia entre los pares que están dentro de un mismo archivo
  (x0,82 de media, más cuanto menor la diferencia real), mientras que el par del empalme cruza dos
  codificaciones y no recibe ese descuento. Medido así, el empalme de Peumo leía un +30 % contra
  sus vecinos y en crudo era un +10 %, dentro de la variación de la serie.
  Y para comparar un mismo cuadro rendido en dos contenedores **no sirve el md5 del PNG**: Blender
  escribe `tEXt Date` y `tEXt RenderTime` adentro, así que el hash difiere siempre aunque los
  píxeles sean idénticos. Comparar el volcado crudo:
  `ffmpeg -i f.png -f rawvideo -pix_fmt rgb24 f.raw && md5sum f.raw`. Ojo que entre contenedores
  distintos ni el crudo coincide exacto (el núcleo de Cycles que elige la CPU del host cambia el
  último bit); lo que importa es la magnitud, y en Peumo quedó por debajo del ruido de
  codificación de un cuadro contra su propia versión en el MP4 (1,72 contra 1,95 de media).
  Y la vara tiene que ser **local**: la diferencia entre cuadros vecinos no es constante a lo largo
  de una toma (cambia con la velocidad de la cámara), así que el empalme se compara contra sus
  vecinos inmediatos y no contra una base medida en otra parte del clip. En s5 de Peumo la base era
  5,9 al principio y 7,8 junto al empalme: con la base vieja, un empalme limpio (+1,2 %) habría
  leído +31 %.
- Armar el MP4 con `tools/armar_video.sh` (`LOOK=dia` para Casa Lingue).
- Video de recintos de Lingue: `casa_lingue_3d.py -- --vista corte --res 720x1280 --samples 20
  --frames 1-264`, luego `tools/video_corte.py frames_recintos frames_recintos_post` y
  `VIGNETA_HASTA=11 LOOK=dia tools/armar_video.sh frames_recintos_post output/casa_lingue_recintos.mp4 24`.
  Versión sin rótulos ni textos (para editar el reel): `tools/video_corte.py frames_recintos
  frames_recintos_limpio --sin-textos` y armar `output/casa_lingue_recintos_limpio.mp4` igual.
- Reel continuo de Lingue (una sola toma de dron, sin textos): conectores con
  `PY=<python con bpy> setsid nohup tools/render_reel.sh c1 c3 c4 &` (casa_lingue_3d.py --vista reel;
  avance legible en PROGRESO_RENDER.txt con `setsid nohup tools/progreso_render.sh &`), plano azul con
  `tools/video_corte.py frames_recintos frames_reel/plano --sin-textos --papel azul --hold 48
  --vuelta frames_reel/c3/f_0001.png`, luego `tools/reel_continuo.py frames_reel/continuo` y
  `VIGNETA_EXPR='<la que imprime>' LOOK=dia tools/armar_video.sh frames_reel/continuo
  output/casa_lingue_reel_continuo.mp4 24`.
- Marca Neorigen en gráficas: Azul Origen #011E2F, Niebla #F1F4F3, Verde Pino #3C4A3E, Madera #A9764A
  (sin negro ni blanco puros); Fraunces / Work Sans / IBM Plex Mono desde `assets/fuentes/`
  (instancias con `tools/instanciar_fuentes.py`), logo en `assets/marca/`. Texto mínimo 22 px a 720x1280.
- Casa Peumo (nieve en el bosque): `casa_peumo_3d.py` (casa desde el STL con `tools/extraer_peumo_stl.py`;
  recursos de Poly Haven con `tools/get_assets_nieve.sh`, 1,3 GB). Mismas cinco secciones que Huingán:
  `setsid nohup tools/render_peumo.sh s1 [s2 ...] &`, o Blender directo con `--desde/--hasta` para
  repartir una sección entre contenedores. s4 = `tools/plano_peumo.py`, con las constantes de la
  lámina calibradas por `tools/calibrar_planta.py`. La nieve cayendo va **sólo en s5** y en diagonal;
  `--techo` gradúa cuánta nieve queda en el techo (0,28 es la elegida).
- Casa Boldo (lago): `casa_boldo_3d.py` (casa desde el STL con `tools/extraer_boldo_stl.py`;
  árboles y sotobosque de Poly Haven con `tools/get_assets_lago.sh`, 1,3 GB, y el matorral y las
  rocas con `tools/get_assets_playa.sh`). Fotos de aprobación con `tools/fotos_boldo.sh`
  (`output/boldo_propuesta/`), secciones con `setsid nohup tools/render_boldo.sh s1 [s2 ...] &`.
  El agua va casi espejo y la ribera de enfrente es tema, no fondo: se refleja.
  **Completa**: las cinco secciones, `output/casa_boldo_secuencia.mp4`, 1008 cuadros, 42 s.
  s4 = `tools/plano_boldo.py`, con la lámina en PNG (`assets/boldo/planta_sin_cotas.png`, bajada
  del sitio): abre la imagen directo en vez de rasterizar un PDF, y por eso engrosa las líneas con
  MinFilter(3) y no (9) —la lámina del sitio son 76,8 px/m contra los 374 px/m de un PDF a 300 dpi,
  así que con 9 las paredes salían de doce centímetros—. Las constantes salen de
  `tools/calibrar_planta.py`, que ahora recibe el ancho y el fondo de la casa por argumento y
  acepta `FRANJA=0.13` para no dejar que la banda azul de marca de la lámina le compita al dibujo
  en la correlación.
  Costo medido, útil para repartir: el cuadro no vale lo mismo a lo largo del recorrido. De lejos
  sobre el agua son ~29 cuadros/hora; acercándose baja a 21 (entra más bosque y más reflejo); en
  la cenital sube a 38, porque desde arriba casi no entra bosque. s1 tardó 9,5 h, s2 8 h, s3 7 h
  y s5 6 h, en cuatro núcleos.
- Casa Mañío (playa urbanizada): `casa_manio_3d.py` (casa desde el STL con `tools/extraer_manio_stl.py`;
  recursos de Poly Haven con `tools/get_assets_playa.sh` **y** `tools/get_assets_urbano.sh`).
  Es la más grande de las nueve (16,02 × 11,15; era la "Huingán familiar"), así que el `FIT` del
  encuadre sube a 0,88 y el arco frontal va más bajo: el enganche es que se abre entera al frente.
  Hereda el mar y la arena de Huingán; lo que cambia es tierra adentro: **condominio de costa
  estilo Maitencillo**, con camino angosto de asfalto y bermas de maicillo (sin solera, sin
  vereda, sin alumbrado ni postes), muro de contención sobre la playa, vecinos cerca pero todos
  distintos, cierro de listones de madera y césped con setos en vez de matorral. Fotos de
  aprobación con `PY=$PWD/venv-bpy/bin/python tools/fotos_manio.sh` (`output/manio_propuesta/`),
  secciones con `setsid nohup tools/render_manio.sh s1 [s2 ...] &`.
  La primera versión era una costanera urbana y la revisión la rechazó: lo que la delataba eran
  los postes con tendido aéreo, la calzada ancha con solera y vereda de hormigón, y los vecinos
  repetidos en filas. Al heredar esto en Ciprés, partir de la **segunda** versión.
  Ojo además con tres cosas: la playa tiene que ser **ancha** (con la duna angosta de Huingán la
  cámara se planta sobre el muro y el mar queda fuera de cuadro), el ripple de arena hay que
  apagarlo donde hay césped, y la franja húmeda del muro se mide con un atributo de altura y no
  con la z del mundo.
- Casa Huingan (playa): `casa_huingan_3d.py` (casa desde el STL con `tools/extraer_huingan_stl.py`; recursos de
  Poly Haven con `tools/get_assets_playa.sh`). Recorrido de dron por secciones (`SECCIONES` en el script):
  `setsid nohup tools/render_huingan.sh s1 [s2 ...] &` (cuadros en `frames_huingan/<sección>/`, avance en
  PROGRESO_RENDER.txt). El dron se aleja o acerca solo para que la casa ocupe siempre el mismo ancho de pantalla.
  Orden: s1 (aproximación) → s2 → s3 (corte, cenital) → s4 = `tools/plano_huingan.py` (planta sobre la cenital,
  post 2D desde el último cuadro de s3) → s5; MP4 de cada sección con `LOOK=dia tools/armar_video.sh`.

## Entorno en un contenedor nuevo

Los contenedores son efímeros: al empezar una sesión en uno nuevo hay que rearmar esto antes de
renderizar (nada de ello va al repo, son ~650 MB).

- Blender: instalar el módulo `bpy` en un venv, **fijando `bpy==5.0.1`, que sólo tiene rueda para
  Python 3.11**: `python3.11 -m venv venv-bpy && ./venv-bpy/bin/pip install bpy==5.0.1`. Luego usar
  `PY=$PWD/venv-bpy/bin/python` en los scripts de render. Verificar con
  `./venv-bpy/bin/python -c "import bpy; print(bpy.app.version_string)"`.
  **No tomar la última versión de bpy.** Con 5.2.3 (cp313) `casa_peumo_3d.py` no corre: aborta en
  `nevar()` con `NodeSocketInt.default_value expected an int type, not float` (lo vieron dos
  contenedores al rearmar el entorno desde esta receta, que antes decía 5.2.3). Si hace falta
  subir de versión, los enteros que van a sockets de Geometry Nodes hay que castearlos a `int`.
  Todas las secciones de una casa tienen que renderizarse **con la misma versión de bpy**: si se
  reparte una sección entre contenedores y uno usa otra versión, la diferencia se ve justo en el
  empalme.
  Si `pip install` se cuelga resolviendo dependencias, bajar la rueda directo de
  `pypi.org/pypi/bpy/json` con `curl -sSL -C -` y darle el nombre canónico (pip rechaza otro).
- Librerías gráficas: `bpy` aborta con SIGABRT sin ellas, aunque Cycles renderice en CPU.
  `apt-get install -y libegl1 libgl1 libglx-mesa0 libgl1-mesa-dri libxi6 libxrender1 libxxf86vm1
  libxfixes3 libsm6 libice6 libxkbcommon0 libwayland-client0`. Los avisos `EGL_BAD_MATCH` que
  quedan son inofensivos (no hay pantalla): el render igual se guarda.
- Recursos de Poly Haven de Huingan (251 MB, en .gitignore): `tools/get_assets_playa.sh`.
- Recursos de Mañío: `tools/get_assets_playa.sh` **y** `tools/get_assets_urbano.sh` (alumbrado,
  jacarandá, arbustos de jardín, maceteros y texturas de pavimento; ~60 MB más).
- Recursos de Boldo: `tools/get_assets_playa.sh` (matorral y rocas) **y**
  `tools/get_assets_lago.sh` (árboles y sotobosque, 1,3 GB), más
  `tools/get_assets_hdri.sh lago`.
