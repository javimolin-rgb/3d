#!/usr/bin/env bash
# Las fotos de aprobación de Casa Boldo (RECETA.md §0). PY=<python con bpy>.
# Tres ángulos: los dos de sobre el agua, frente al testero vidriado, y el del acceso.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-$PWD/venv-bpy/bin/python}
RES=${RES:-720x1280}
SAMPLES=${SAMPLES:-32}
DEST=output/boldo_propuesta
mkdir -p "$DEST"
shot() {  # nombre vista
  [ -s "$DEST/$1.png" ] && { echo "$1 ya estaba"; return; }
  echo "== $1  $(date +%H:%M:%S)"
  "$PY" casa_boldo_3d.py -- --vista "$2" --still 1 --res "$RES" --samples "$SAMPLES" \
      --out "$DEST/$1.png" 2>&1 | grep -E "Saved|Error"
}
shot izq   izq
shot der   der
shot atras atras
echo "FOTOS LISTAS $(date +%H:%M:%S)"
