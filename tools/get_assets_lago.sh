#!/usr/bin/env bash
# Descarga los modelos CC0 de Poly Haven para la escena de lago de Casa Boldo
# (casa_boldo_3d.py) en assets/lago/ph/<id>/. No van al repo: se bajan con este script.
#
# Los árboles son el corazón de la escena, igual que en Peumo: en un lago la ribera de enfrente y
# el bosque alrededor del claro se ven dos veces —la real y la del reflejo—, así que árboles de
# bolas desplazadas se notan el doble. Coníferas (fir, pine) para la masa del bosque, island_tree
# y tree_small para la copa ancha del nativo, helechos y matas para el sotobosque de la ribera.
#   modelos: .blend 1k con sus texturas
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=assets/lago/ph
UA="neorigen-render/1.0"
MODELOS="fir_tree_01 pine_tree_01 island_tree_01 island_tree_02 island_tree_03 tree_small_02
  fir_sapling_medium pine_sapling_small fern_02 shrub_01 shrub_03 shrub_sorrel_01
  tree_stump_01 dead_tree_trunk_02 rock_07 rock_09 boulder_01"

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
