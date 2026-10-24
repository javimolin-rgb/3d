#!/usr/bin/env bash
# Descarga los recursos CC0 de Poly Haven para la escena de playa de Casa Huingan
# (casa_huingan_3d.py) en assets/playa/ph/<id>/. No van al repo (pesan ~250 MB): se bajan con este script.
#   modelos: .blend 1k con sus texturas    HDRIs: .exr 2k    texturas: jpg 2k
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=assets/playa/ph
UA="neorigen-render/1.0"
MODELOS="searsia_lucida wild_rooibos_bush othonna_cerarioides didelta_spinosa shrub_02 shrub_04
  crystalline_iceplant cheiridopsis_succulent grass_medium_01 grass_medium_02 grass_bermuda_01
  flower_heliophila namaqualand_boulder_02 coast_rocks_01 dead_tree_trunk dry_branches_medium_01"
HDRIS="secluded_beach flamingo_pan cape_hill sundowner_overlook white_cliff_top"
TEXTURAS="coast_sand_01 aerial_beach_01"

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
for id in $HDRIS; do
  get "https://dl.polyhaven.org/file/ph-assets/HDRIs/exr/2k/${id}_2k.exr" "$DEST/hdri/${id}_2k.exr"
  echo "hdri $id"
done
for id in $TEXTURAS; do
  curl -sSf -A "$UA" "https://api.polyhaven.com/files/$id" | python3 -c '
import json, sys
f = json.load(sys.stdin)
for m in ("Diffuse", "nor_gl", "Rough", "Displacement", "AO"):
    if m in f and "2k" in f[m]:
        e = f[m]["2k"].get("jpg") or f[m]["2k"].get("png")
        print(e["url"], m)' | while read -r url m; do get "$url" "$DEST/tex/$id/${id}_${m}_2k.${url##*.}"; done
  echo "textura $id"
done
du -sh "$DEST"
