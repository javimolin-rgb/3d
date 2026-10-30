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
3. **Peumo — nieve en el bosque** ← la que viene
4. Boldo — lago
5. Mañío — playa urbanizada
6. Roble — nieve tipo centro de ski
7. Maitén — mar roca
8. Coihue — campo, que se note el trigo
9. Ciprés — playa del norte (más seco) ⚠️

⚠️ El primer Ciprés (campo al atardecer) **no** corresponde a su emplazamiento y está archivado
en `archivo/cipres_v1/`: no partir de ahí, Ciprés se rehace desde Huingán.

**`PENDIENTES.md`** dice qué falta conseguir para cada casa antes de poder empezar (el STL lo
entrega el usuario; HDRI de nieve y de lago todavía no existen).

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
- Casa Huingan (playa): `casa_huingan_3d.py` (casa desde el STL con `tools/extraer_huingan_stl.py`; recursos de
  Poly Haven con `tools/get_assets_playa.sh`). Recorrido de dron por secciones (`SECCIONES` en el script):
  `setsid nohup tools/render_huingan.sh s1 [s2 ...] &` (cuadros en `frames_huingan/<sección>/`, avance en
  PROGRESO_RENDER.txt). El dron se aleja o acerca solo para que la casa ocupe siempre el mismo ancho de pantalla.
  Orden: s1 (aproximación) → s2 → s3 (corte, cenital) → s4 = `tools/plano_huingan.py` (planta sobre la cenital,
  post 2D desde el último cuadro de s3) → s5; MP4 de cada sección con `LOOK=dia tools/armar_video.sh`.

## Entorno en un contenedor nuevo

Los contenedores son efímeros: al empezar una sesión en uno nuevo hay que rearmar esto antes de
renderizar (nada de ello va al repo, son ~650 MB).

- Blender: instalar el módulo `bpy` en un venv. `pip install bpy` se cuelga resolviendo
  dependencias; bajar la rueda directo y darle el nombre canónico (pip rechaza otro):
  `curl -sSL -C - -o bpy-5.2.3-cp313-cp313-manylinux_2_28_x86_64.whl <url de pypi.org/pypi/bpy/json>`
  y `python3 -m venv /opt/bpyvenv && /opt/bpyvenv/bin/pip install <la rueda>`. Luego usar
  `PY=/opt/bpyvenv/bin/python` en los scripts de render.
- Librerías gráficas: `bpy` aborta con SIGABRT sin ellas, aunque Cycles renderice en CPU.
  `apt-get install -y libegl1 libgl1 libglx-mesa0 libgl1-mesa-dri libxi6 libxrender1 libxxf86vm1
  libxfixes3 libsm6 libice6 libxkbcommon0 libwayland-client0`. Los avisos `EGL_BAD_MATCH` que
  quedan son inofensivos (no hay pantalla): el render igual se guarda.
- Recursos de Poly Haven de Huingan (251 MB, en .gitignore): `tools/get_assets_playa.sh`.
