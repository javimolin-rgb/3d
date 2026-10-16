#!/usr/bin/env bash
# Arma el MP4 a partir de los cuadros renderizados y aplica la corrección de color
# cálida de atardecer.
# Uso: tools/armar_video.sh <carpeta_cuadros> <salida.mp4> [fps_de_entrada]
#   fps_de_entrada = 24 para el video final; 3 para previews (1 de cada 8 cuadros).
set -euo pipefail
IN="$1"; OUT="$2"; FPS="${3:-24}"
GRADE="eq=brightness=0.035:gamma=1.12:saturation=1.12,colorbalance=rs=0.03:bs=-0.06:rm=0.11:gm=0.02:bm=-0.09:rh=0.09:gh=0.03:bh=-0.07,vignette=PI/7"
if [ "$FPS" = 24 ]; then VF="$GRADE,format=yuv420p"; else VF="$GRADE,minterpolate=fps=24:mi_mode=blend,format=yuv420p"; fi
ffmpeg -loglevel error -y -framerate "$FPS" -pattern_type glob -i "$IN/*.png" -vf "$VF" \
  -c:v libx264 -preset slow -crf 17 -movflags +faststart "$OUT"
echo "listo: $OUT"
