#!/usr/bin/env bash
# Las fotos de aprobación de Casa Peumo (RECETA.md §0). PY=<python con bpy>.
# Las cuatro tomas del juego, más una con la nevada fuerte.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-/opt/bpyvenv/bin/python}
RES=${RES:-720x1280}
SAMPLES=${SAMPLES:-32}
DEST=output/peumo_propuesta
mkdir -p "$DEST"
shot() {  # nombre vista nevada
  [ -s "$DEST/$1.png" ] && { echo "$1 ya estaba"; return; }
  echo "== $1  $(date +%H:%M:%S)"
  "$PY" -I casa_peumo_3d.py -- --vista "$2" --still 1 --res "$RES" --samples "$SAMPLES" \
      --nevada "$3" --out "$DEST/$1.png" 2>&1 | grep -E "Saved|Error"
}
shot izq        izq        1.0
shot der        der        1.0
shot izq_atras  izq_atras  1.0
shot der_atras  der_atras  1.0
shot izq_nevando izq       2.5
echo "FOTOS LISTAS $(date +%H:%M:%S)"
