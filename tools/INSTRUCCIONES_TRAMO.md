# Instrucciones para un contenedor que renderiza un tramo de Casa Roble

Sos uno de once contenedores de un render repartido. Tu único trabajo es renderizar **el tramo
que te asignaron** y subir su MP4. La tabla de tramos y el por qué están en `REPARTO_ROBLE.md`.

## 1. Rearmar el entorno

El contenedor viene pelado y nada de esto está en el repo (~1,7 GB):

```
apt-get update && apt-get install -y libegl1 libgl1 libglx-mesa0 libgl1-mesa-dri libxi6 \
  libxrender1 libxxf86vm1 libxfixes3 libsm6 libice6 libxkbcommon0 libwayland-client0
python3.11 -m venv venv-bpy && ./venv-bpy/bin/pip install bpy==5.0.1
tools/get_assets_nieve.sh && tools/get_assets_hdri.sh nieve
```

Verificá que diga **5.0.1**: `./venv-bpy/bin/python -c "import bpy; print(bpy.app.version_string)"`.
No tomes otra versión: con 5.2.3 el script aborta en `nevar()`, y además todos los tramos tienen
que rendirse con la misma versión o la diferencia se ve justo en el empalme. Si `pip install` se
cuelga resolviendo dependencias, bajá la rueda directo de `pypi.org/pypi/bpy/json` con
`curl -sSL -C -` y dale el nombre canónico.

`assets/roble/casa.blend` **ya está en el repo**: no corras `tools/extraer_roble_stl.py`, tarda
más de una hora.

## 2. Lanzar el render, desprendido de la sesión

```
cd /home/user/3d && export PY=$PWD/venv-bpy/bin/python
SECCION=<sec> DESDE=<a> HASTA=<b> setsid nohup tools/render_roble_tramo.sh > /dev/null 2>&1 < /dev/null &
```

Comprobá a los 30 s con `pgrep -f "[c]asa_roble_3d"`. El avance queda en `PROGRESO_RENDER.txt`.
Son unos 9,3 min por cuadro en cuatro núcleos.

## 3. Mantenerte vivo

**El contenedor se reinicia cada hora y media y se lleva el render.** Creá una tarea programada
**horaria sobre tu propia sesión** (`create_trigger`, sin `persistent_session_id` ni
`create_new_session_on_fire`) cuyo texto diga: revisar `uptime`, `pgrep -f "[c]asa_roble_3d"` y
la línea "Actualizado" de `PROGRESO_RENDER.txt` (si tiene más de unos minutos, el render está
caído aunque el archivo diga "renderizando"); si no hay render vivo,
`cd /home/user/3d && find frames_roble -name "f_*.png" -size -10k -delete` y relanzar el comando
del punto 2; si `venv-bpy` tampoco está, rearmar el entorno antes. El disco normalmente sobrevive
al reinicio. Gastar los mínimos tokens posibles: sólo comprobar y, si hace falta, relanzar.

El render es reanudable (`use_overwrite = False`), así que un corte cuesta como mucho un cuadro.
Para saber si Blender sigue vivo **no** uses `pgrep -f` con el mismo texto del comando de espera:
se encuentra a sí mismo.

## 4. Armar el MP4 del tramo y empujarlo

Cuando estén todos los cuadros del tramo:

```
LOOK=dia tools/armar_video.sh frames_roble/<sec> output/tramos/<archivo>.mp4 24
```

Revisá que el MP4 tenga tantos cuadros como el tramo
(`ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 <archivo>`).
Después commiteá **sólo ese archivo** y empujá a la rama `javieramolin/dreamy-gates-iqll9z`.
Si el push se rechaza porque la rama tiene commits que no tenés:
`git fetch origin javieramolin/dreamy-gates-iqll9z && git merge --no-edit FETCH_HEAD` y empujá de
nuevo. **Nunca** force-push ni rebase: los otros commits son de los otros diez contenedores.

## 5. Avisar y apagarse

Mandá un `send_message` a la sesión que te creó diciendo que tu tramo está empujado (y el ritmo
que midió el log, que sirve para repartir el próximo render), y borrá tu tarea programada con
`delete_trigger`.

## Lo que no hay que hacer, pase lo que pase

- **No cambiar** `--res 720x1280`, `--samples 16`, `--nevada 0` ni la versión de bpy: son los
  cuatro parámetros que tienen que coincidir entre tramos. Aunque el render parezca lento, no
  bajes las muestras: el usuario lo pidió explícitamente ("repartelo, no bajes la calidad").
- **No tocar** `casa_roble_3d.py`, nada de `tools/`, `CLAUDE.md`, `RECETA.md` ni ningún otro
  archivo compartido: los once contenedores empujan a la misma rama y cualquier cambio ahí es un
  conflicto. Si te parece que hay un error en el script, avisá por `send_message` en vez de
  arreglarlo.
- No renderizar cuadros fuera de tu tramo, no armar el video completo, no escribir `plano_roble.py`
  ni la sección s4, no crear pull requests, no empujar a otra rama que la de arriba.
- No le escribas al usuario ni esperes respuesta de nadie: trabajás solo y reportás al final.
