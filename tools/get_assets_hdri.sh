#!/usr/bin/env bash
# Descarga los HDRI CC0 de Poly Haven por familia de emplazamiento, en assets/hdri/<familia>/.
# No van al repo (pesan ~20 MB cada uno): se bajan con este script.
#   Uso: tools/get_assets_hdri.sh [nieve] [lago] ...   (sin argumentos: todas)
# Después de bajar uno, medirle el sol con tools/medir_sol_hdri.py: la escena necesita
# HDRI_SUN_U y SUN_ELEV para calzar el cielo físico con el sol del HDRI (ver RECETA.md §3).
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=assets/hdri
UA="neorigen-render/1.0"

# Peumo: bosque nevado, luz difusa. Roble: ladera abierta de montaña, sol.
nieve="snowy_forest snowy_forest_path_01 snowy_hillside horn-koppe_snow snow_field_2"
# Boldo: lago con orilla opuesta visible (es lo que se refleja).
lago="lakeside lakeside_sunrise montorfano shudu_lake"

get() {  # id familia
  local out="$DEST/$2/${1}_2k.exr"
  [ -s "$out" ] && { echo "  $1 (ya estaba)"; return; }
  mkdir -p "$(dirname "$out")"
  curl -sSfL -A "$UA" --retry 4 -o "$out.part" \
    "https://dl.polyhaven.org/file/ph-assets/HDRIs/exr/2k/${1}_2k.exr" && mv "$out.part" "$out"
  echo "  $1"
}

for fam in "${@:-nieve lago}"; do
  eval "ids=\${$fam:-}"
  [ -z "$ids" ] && { echo "familia desconocida: $fam" >&2; exit 1; }
  echo "$fam:"
  for id in $ids; do get "$id" "$fam"; done
done
du -sh "$DEST"
