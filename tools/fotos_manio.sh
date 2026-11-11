#!/usr/bin/env bash
# Fotos fijas de aprobación de Casa Mañío (RECETA.md §0): varios ángulos antes de renderizar
# nada de video. ~5 min por foto en 4 núcleos.
#   PY=$PWD/venv-bpy/bin/python tools/fotos_manio.sh [vista ...]
set -u
cd "$(dirname "$0")/.."
PY=${PY:-$PWD/venv-bpy/bin/python}
RES=${RES:-720x1280}
SAMPLES=${SAMPLES:-32}
OUT=${OUT:-output/manio_propuesta}
mkdir -p "$OUT"
VISTAS=("$@")
[ ${#VISTAS[@]} -eq 0 ] && VISTAS=(izq der frente cerca izq_atras calle)
for v in "${VISTAS[@]}"; do
  echo "== $v  $(date +%H:%M:%S)"
  "$PY" casa_manio_3d.py -- --vista "$v" --still 1 --out "$OUT/$v.png" \
      --res "$RES" --samples "$SAMPLES" 2>&1 | grep -E "Saved|Error|error" | tail -2
done
