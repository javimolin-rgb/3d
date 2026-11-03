#!/usr/bin/env bash
# Cierra el ciclo de una locución: la mide y la monta sobre el reel.
#   tools/cerrar_voz.sh <voz.wav> <reel.mp4> <salida.mp4> [palabras] [cama.mp3]
set -euo pipefail
VOZ="${1:?}"; REEL="${2:?}"; SALIDA="${3:?}"; PALABRAS="${4:-107}"; CAMA="${5:-}"
D=$(dirname "$0")
echo "######## MEDIDA DE LA TOMA ########"
"$D/medir_voz.sh" "$VOZ" "$PALABRAS"
echo
echo "######## MONTAJE SOBRE EL REEL ########"
"$D/montar_voz.sh" "$REEL" "$VOZ" "$SALIDA" ${CAMA:+"$CAMA"}
