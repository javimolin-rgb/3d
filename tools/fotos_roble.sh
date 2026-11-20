#!/usr/bin/env bash
# Las fotos de aprobación de Casa Roble (RECETA.md §0). PY=<python con bpy>.
# Las cuatro tomas del juego. La quinta no es 'nevando fuerte' como en Peumo —en un centro
# de ski con sol la nevada tapa justamente lo que hay que mostrar— sino la misma toma de la
# pista sin nieve cayendo, para ver limpio el acordonado del pisanieve y el andarivel.
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
shot izq        izq        0.35
shot der        der        0.35
shot izq_atras  izq_atras  0.35
shot der_atras  der_atras  0.35
shot izq_limpia izq        0.0
shot contexto   contexto   0.0
echo "FOTOS LISTAS $(date +%H:%M:%S)"
