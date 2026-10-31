#!/usr/bin/env bash
# Descarga los recursos CC0 de Poly Haven para la escena de bosque nevado de Casa Peumo
# (casa_peumo_3d.py) en assets/nieve/ph/<id>/. No van al repo: se bajan con este script.
#   modelos: .blend 1k con sus texturas
# Las coníferas (fir_tree_01, pine_tree_01) son el corazón de la escena: son modelos reales con
# ramas y acículas, y es lo único que hace que un bosque nevado no se vea de cartón. Encima de
# ellas la escena acumula su propia nieve (ver nevar() en casa_peumo_3d.py).
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=assets/nieve/ph
UA="neorigen-render/1.0"
MODELOS="fir_tree_01 pine_tree_01 fir_sapling_medium fir_sapling pine_sapling_medium
  pine_sapling_small tree_stump_01 tree_stump_02 dead_tree_trunk dead_tree_trunk_02
  dry_branches_medium_01 root_cluster_01 pine_roots rock_07 rock_09 boulder_01 shrub_02"

get() {  # url destino
  [ -s "$2" ] && return
  mkdir -p "$(dirname "$2")"
  curl -sSfL -A "$UA" --retry 4 -o "$2.part" "$1" && mv "$2.part" "$2"
}

for id in $MODELOS; do
  curl -sSf -A "$UA" "https://api.polyhaven.com/files/$id" | python3 -c '
import json, sys
b = json.load(sys.stdin)["blend"]["1k"]["blend"]
print(b["url"], "'"$id"'.blend")
for p, v in b.get("include", {}).items():
    print(v["url"], p)' | while read -r url path; do get "$url" "$DEST/$id/$path"; done
  echo "modelo $id"
done
du -sh "$DEST"
