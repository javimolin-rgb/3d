#!/usr/bin/env bash
# Monta una locución sobre el reel y deja el máster a -14 LUFS (lo que espera Instagram).
#
#   tools/montar_voz.sh <video> <voz> <salida.mp4> [cama]
#
# La cama se elige así, en este orden:
#   1. el archivo que se pase como 4º argumento;
#   2. si no, el audio que ya traiga el video (el reel "sin voz" viene con la cama puesta);
#   3. si no hay ninguno, sale sólo la voz.
# En los dos primeros casos la cama se agacha bajo la voz con sidechain en vez de pelear
# con ella. La voz NUNCA sale del video: si el video ya trae voz, hay que pedir uno limpio.
#
# RETARDO=0.8   aire antes de la primera palabra (el reel abre con el rótulo)
# CAMA_DB=-8    cuánto se baja la cama. -8 asume una cama ya masterizada (~-14 LUFS);
#               para una pista cruda y fuerte conviene algo como -19.
set -euo pipefail

VIDEO="${1:?uso: tools/montar_voz.sh <video> <voz> <salida.mp4> [cama]}"
VOZ="${2:?falta la voz}"
SALIDA="${3:?falta la salida}"
CAMA="${4:-}"
RETARDO="${RETARDO:-0.8}"
CAMA_DB="${CAMA_DB:--8}"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
DV=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VOZ")
TIENE_AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$VIDEO" | head -1)
MS=$(python3 -c "print(int(float('$RETARDO')*1000))")

if [ -n "$CAMA" ]; then
  FUENTE="archivo: $CAMA"
elif [ -n "$TIENE_AUDIO" ]; then
  FUENTE="el propio audio del video"
else
  FUENTE="ninguna (sólo voz)"
fi
echo "video ${DUR}s · voz ${DV}s · retardo ${RETARDO}s · cama: $FUENTE (${CAMA_DB} dB)"
python3 -c "
d,v,r=float('$DUR'),float('$DV'),float('$RETARDO')
s=d-(v+r)
print('  aviso: la voz se pasa %.2f s del video; se va a cortar' % -s) if s<-0.05 else \
print('  quedan %.2f s de cola sin voz al final' % s)
"

VOZ_F="adelay=${MS}|${MS},apad,atrim=0:${DUR},asetpts=N/SR/TB"
FADE=$(python3 -c "print(max(0,float('$DUR')-2))")

mezclar() {   # $1 = etiqueta de la entrada de cama
  ffmpeg -y -v error -stats "${ENTRADAS[@]}" -filter_complex "
      [1:a]aformat=sample_rates=48000:channel_layouts=stereo,${VOZ_F}[voz];
      [voz]asplit=2[voz_mix][voz_sc];
      [$1]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:${DUR},
          volume=${CAMA_DB}dB,afade=t=out:st=${FADE}:d=2[cama];
      [cama][voz_sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[cama_d];
      [voz_mix][cama_d]amix=inputs=2:duration=first:normalize=0,
          loudnorm=I=-14:TP=-1.5:LRA=11[out]" \
    -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 192k -shortest "$SALIDA"
}

if [ -n "$CAMA" ]; then
  ENTRADAS=(-i "$VIDEO" -i "$VOZ" -stream_loop -1 -i "$CAMA"); mezclar "2:a"
elif [ -n "$TIENE_AUDIO" ]; then
  ENTRADAS=(-i "$VIDEO" -i "$VOZ"); mezclar "0:a"
else
  ffmpeg -y -v error -stats -i "$VIDEO" -i "$VOZ" \
    -filter_complex "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,${VOZ_F},
                     loudnorm=I=-14:TP=-1.5:LRA=11[out]" \
    -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 192k -shortest "$SALIDA"
fi

echo
echo "== $SALIDA"
ffmpeg -nostats -i "$SALIDA" -af ebur128=framelog=verbose -f null - 2>&1 | grep -E "^\s+(I|LRA):"
