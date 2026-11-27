#!/usr/bin/env bash
# Las fotos de aprobación de Casa Maitén (RECETA.md §0). PY=<python con bpy>.
# Seis ángulos: los dos desde el agua —bajos, mirando hacia arriba, porque el enganche de
# Maitén es la altura (ENGANCHES.md)—, los mismos dos más cerca y algo más altos (los pidió la
# revisión), y los dos de tierra, con el mar detrás de la casa.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-$PWD/venv-bpy/bin/python}
RES=${RES:-720x1280}
SAMPLES=${SAMPLES:-32}
DEST=output/maiten_propuesta
mkdir -p "$DEST"
shot() {  # nombre vista
  [ -s "$DEST/$1.png" ] && { echo "$1 ya estaba"; return; }
  echo "== $1  $(date +%H:%M:%S)"
  "$PY" casa_maiten_3d.py -- --vista "$2" --still 1 --res "$RES" --samples "$SAMPLES" \
      --out "$DEST/$1.png" 2>&1 | grep -E "Saved|Error"
}
shot izq        izq
shot der        der
shot izq_cerca  izq_cerca
shot der_cerca  der_cerca
shot izq_atras  izq_atras
shot der_atras  der_atras
echo "FOTOS LISTAS $(date +%H:%M:%S)"
