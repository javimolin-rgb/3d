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
- Armar el MP4 con `tools/armar_video.sh` (`LOOK=dia` para Casa Lingue).

## Historia de "modelo destacado" (9:16)

- `casa_lingue_3d.py -- --vista historia --out tomas/ --res 1080x1920 --samples 48`
  renderiza en una sola pasada las seis tomas de la historia (las de `TOMAS` más
  la vista interior) y, junto a cada render, su pase de profundidad normalizado
  (`<toma>_zprofundidad.png`: 0 = cámara, blanco = 90 m). Es reanudable: salta las
  tomas que ya estén en la carpeta.
- `historia_lingue.py <carpeta_tomas> <salida.mp4>` arma el video vertical con los
  datos del modelo (diccionario `MODELO`, al comienzo del archivo).
- El pase de profundidad es lo que permite las transiciones en tres dimensiones:
  cada gráfico declara su distancia en metros (`z`) y se dibuja sólo donde la
  escena está más lejos, así los textos entran por detrás de la casa y salen por
  delante del pasto. Para elegir esas distancias conviene mirar antes el perfil de
  profundidad de cada toma (mediana por franjas) sobre una previsualización chica.
- Con el módulo `bpy` de PyPI hacen falta `libegl1` (apt) y los recursos de
  `tools/get_assets.sh` (complemento Sapling en `assets/vendor`).
