# Renders 3D Neorigen

Escenas de Blender (Cycles) generadas por script: `casa_cipres_3d.py` y `casa_lingue_3d.py`.

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
- Marca Neorigen en gráficas: Azul Origen #011E2F, Niebla #F1F4F3, Verde Pino #3C4A3E, Madera #A9764A
  (sin negro ni blanco puros); Fraunces / Work Sans / IBM Plex Mono desde `assets/fuentes/`
  (instancias con `tools/instanciar_fuentes.py`), logo en `assets/marca/`. Texto mínimo 22 px a 720x1280.
