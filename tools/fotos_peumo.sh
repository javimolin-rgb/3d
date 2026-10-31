#!/usr/bin/env bash
# Las cuatro fotos de aprobación de Casa Peumo (RECETA.md §0). PY=<python con bpy>.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-/opt/bpyvenv/bin/python}
RES=${RES:-720x1280}
SAMPLES=${SAMPLES:-32}
for v in izq der izq_atras der_atras; do
  [ -s "output/peumo_propuesta/$v.png" ] && { echo "$v ya estaba"; continue; }
  echo "== $v  $(date +%H:%M:%S)"
  "$PY" -I casa_peumo_3d.py -- --vista "$v" --still 1 --res "$RES" --samples "$SAMPLES" \
      --out "output/peumo_propuesta/$v.png" 2>&1 | grep -E "Saved|Error" 
done
echo "FOTOS LISTAS $(date +%H:%M:%S)"
