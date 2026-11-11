#!/usr/bin/env bash
# Recursos CC0 de Poly Haven para el contexto urbanizado de Casa Mañío (casa_manio_3d.py),
# en assets/playa/ph/<id>/ junto a los de Huingán. No van al repo: se bajan con este script.
# Complementa a tools/get_assets_playa.sh (mar, arena, matorral y rocas), que hay que correr antes.
#   alumbrado y postes · árboles ornamentales de calle · arbustos de jardín · maceteros y
#   mobiliario urbano · texturas de asfalto y hormigón para la costanera.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=assets/playa/ph
UA="neorigen-render/1.0"
MODELOS="street_lamp_01 modular_electricity_poles jacaranda_tree island_tree_01 island_tree_02
  tree_small_02 shrub_01 potted_plant_01 potted_plant_02 modular_street_seating metal_trash_can"
TEXTURAS="asphalt_02 brushed_concrete_03"

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
for id in $TEXTURAS; do
  curl -sSf -A "$UA" "https://api.polyhaven.com/files/$id" | python3 -c '
import json, sys
f = json.load(sys.stdin)
for m in ("Diffuse", "nor_gl", "Rough", "AO"):
    if m in f and "2k" in f[m]:
        e = f[m]["2k"].get("jpg") or f[m]["2k"].get("png")
        print(e["url"], m)' | while read -r url m; do get "$url" "$DEST/tex/$id/${id}_${m}_2k.${url##*.}"; done
  echo "textura $id"
done
du -sh "$DEST"
