#!/usr/bin/env bash
# Genera la locución con ElevenLabs a partir de un guion marcado de guiones/.
#
#   ELEVENLABS_API_KEY=...  tools/generar_voz.sh <guion.txt> <voz_id> <salida_base> [n_tomas]
#
# Toma sólo el cuerpo del guion: lo que está entre las dos líneas de guiones largos.
# El encabezado y la tabla de tiempos no se mandan al modelo.
#
# Variables: MODELO (eleven_v3) · STABILITY (0.35) · SIMILARITY (0.80) · SPEED (1.05)
set -euo pipefail

GUION="${1:?uso: tools/generar_voz.sh <guion.txt> <voz_id> <salida_base> [n_tomas]}"
VOZ_ID="${2:?falta el voice_id (sacarlo de la Voice Library)}"
BASE="${3:?falta el nombre base de salida}"
TOMAS="${4:-3}"
MODELO="${MODELO:-eleven_v3}"
STABILITY="${STABILITY:-0.35}"
SIMILARITY="${SIMILARITY:-0.80}"
SPEED="${SPEED:-1.05}"

: "${ELEVENLABS_API_KEY:?falta ELEVENLABS_API_KEY en el entorno (ver LOCUCION.md §2)}"

TEXTO=$(awk '/^-----/{n++; next} n==1' "$GUION" | sed '/^[[:space:]]*$/d' | sed 's/^[[:space:]]*//')
if [ -z "$TEXTO" ]; then echo "no encontré el cuerpo del guion en $GUION" >&2; exit 1; fi

CHARS=$(printf '%s' "$TEXTO" | wc -m)
echo "guion: $CHARS caracteres · modelo $MODELO · $TOMAS tomas  (~$((CHARS*TOMAS)) créditos)"
echo "---"; printf '%s\n' "$TEXTO" | head -4; echo "..."; echo "---"

PALABRAS=$(printf '%s' "$TEXTO" | sed 's/<[^>]*>//g; s/\[[^]]*\]//g' | wc -w)

for i in $(seq 1 "$TOMAS"); do
  SALIDA="${BASE}_t${i}.mp3"
  echo
  echo "== toma $i -> $SALIDA"
  CODIGO=$(python3 -c "
import json,sys
print(json.dumps({'text':sys.stdin.read(),'model_id':'$MODELO',
  'voice_settings':{'stability':$STABILITY,'similarity_boost':$SIMILARITY,'speed':$SPEED}}))
" <<< "$TEXTO" | curl -sS --max-time 180 -o "$SALIDA" -w '%{http_code}' \
      -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOZ_ID}?output_format=mp3_44100_192" \
      -H "xi-api-key: ${ELEVENLABS_API_KEY}" -H "Content-Type: application/json" -d @-)

  if [ "$CODIGO" != "200" ]; then
    echo "  error HTTP $CODIGO:"; head -c 400 "$SALIDA"; echo; rm -f "$SALIDA"
    if [ "$CODIGO" = "422" ] || [ "$CODIGO" = "400" ]; then
      echo "  (si es por el modelo, reintentar con MODELO=eleven_multilingual_v2)"
    fi
    exit 1
  fi
  "$(dirname "$0")/medir_voz.sh" "$SALIDA" "$PALABRAS" | sed 's/^/  /'
done

echo
echo "Elegir la toma que marque ok en silencio y velocidad, y montarla:"
echo "  tools/montar_voz.sh <reel.mp4> ${BASE}_tN.mp3 output/casa_peumo_reel_v2.mp4 [cama.mp3]"
