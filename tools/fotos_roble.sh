#!/usr/bin/env bash
# Las fotos de aprobación de Casa Roble (RECETA.md §0). PY=<python con bpy>.
# Las cuatro tomas del juego van **sin nieve cayendo**, al revés que en Peumo. Dos razones: el
# emplazamiento es un día de sol de centro de ski, y además los copos cerca del lente caen fuera
# del plano de foco y el desenfoque los convierte en bolas blancas, que se leen como suciedad en
# el lente y no como nevada. La quinta es la misma toma nevando, para que se pueda elegir, y la
# sexta es la de contexto, que es la que muestra dónde está parada la casa.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-$PWD/venv-bpy/bin/python}
RES=${RES:-720x1280}
SAMPLES=${SAMPLES:-32}
DEST=output/roble_propuesta
mkdir -p "$DEST"
shot() {  # nombre vista nevada
  [ -s "$DEST/$1.png" ] && { echo "$1 ya estaba"; return; }
  echo "== $1  $(date +%H:%M:%S)"
  "$PY" -I casa_roble_3d.py -- --vista "$2" --still 1 --res "$RES" --samples "$SAMPLES" \
      --nevada "$3" --out "$DEST/$1.png" 2>&1 | grep -E "Saved|Error"
}
shot izq         izq       0.0
shot der         der       0.0
shot izq_atras   izq_atras 0.0
shot der_atras   der_atras 0.0
shot contexto    contexto  0.0
shot izq_nevando izq       1.0
echo "FOTOS LISTAS $(date +%H:%M:%S)"
