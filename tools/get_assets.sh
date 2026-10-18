#!/usr/bin/env bash
# Descarga recursos libres usados por la escena:
#  - Sapling Tree Gen (complemento oficial de Blender, GPL) -> assets/vendor/add_curve_sapling
#  - HDRIs CC0 de Poly Haven (copias del repo de three.js)   -> assets/hdri
#  - texturas de vegetación generadas                      -> assets/tex
set -euo pipefail
cd "$(dirname "$0")/.."
SAP=assets/vendor/add_curve_sapling
mkdir -p "$SAP/presets" assets/hdri assets/tex
RAW=https://raw.githubusercontent.com/blender/blender-addons/main/add_curve_sapling
for f in __init__.py utils.py; do curl -sfL -o "$SAP/$f" "$RAW/$f"; done
for p in douglas_fir small_pine quaking_aspen small_maple willow weeping_willow; do
  curl -sfL -o "$SAP/presets/$p.py" "$RAW/presets/$p.py"
done
T=https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures
for h in spruit_sunrise_1k.hdr venice_sunset_1k.hdr; do
  curl -sfL -o "assets/hdri/$h" "$T/equirectangular/$h"
done
python3 tools/make_textures.py assets/tex
echo "recursos listos"
