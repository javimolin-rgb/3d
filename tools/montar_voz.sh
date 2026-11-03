#!/usr/bin/env bash
# Pega una locución nueva sobre el video del reel y deja el máster a -14 LUFS (lo que
# espera Instagram). Descarta el audio que traiga el video: la voz vieja no se puede
# separar de la cama, así que se reemplaza la pista entera.
#
#   tools/montar_voz.sh <video> <voz.mp3> <salida.mp4> [cama.mp3]
#
# Con cama, la música se agacha bajo la voz (sidechain) en vez de pelear con ella.
# RETARDO=0.8  segundos de aire antes de la primera palabra (el reel abre con el rótulo).
# CAMA_DB=-19  nivel de la cama cuando no hay voz encima.
set -euo pipefail

VIDEO="${1:?uso: tools/montar_voz.sh <video> <voz.mp3> <salida.mp4> [cama.mp3]}"
VOZ="${2:?falta la voz}"
SALIDA="${3:?falta la salida}"
CAMA="${4:-}"
RETARDO="${RETARDO:-0.8}"
CAMA_DB="${CAMA_DB:--19}"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
DV=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VOZ")
MS=$(python3 -c "print(int(float('$RETARDO')*1000))")
echo "video ${DUR}s · voz ${DV}s · retardo ${RETARDO}s"
python3 -c "
d,v,r=float('$DUR'),float('$DV'),float('$RETARDO')
sobra=d-(v+r)
print('  aviso: la voz se pasa %.2f s del video; se va a cortar' % -sobra) if sobra<-0.05 else \
print('  quedan %.2f s de cola sin voz al final' % sobra)
"

VOZ_F="adelay=${MS}|${MS},apad,atrim=0:${DUR},asetpts=N/SR/TB"

if [ -n "$CAMA" ]; then
  ffmpeg -y -v error -stats -i "$VIDEO" -i "$VOZ" -stream_loop -1 -i "$CAMA" \
    -filter_complex "
      [1:a]aformat=sample_rates=48000:channel_layouts=stereo,${VOZ_F}[voz];
      [voz]asplit=2[voz_mix][voz_sc];
      [2:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:${DUR},
           volume=${CAMA_DB}dB,afade=t=out:st=$(python3 -c "print(max(0,float('$DUR')-2))"):d=2[cama];
      [cama][voz_sc]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[cama_d];
      [voz_mix][cama_d]amix=inputs=2:duration=first:normalize=0,
           loudnorm=I=-14:TP=-1.5:LRA=11[out]" \
    -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 192k -shortest "$SALIDA"
else
  ffmpeg -y -v error -stats -i "$VIDEO" -i "$VOZ" \
    -filter_complex "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,${VOZ_F},
                     loudnorm=I=-14:TP=-1.5:LRA=11[out]" \
    -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 192k -shortest "$SALIDA"
fi

echo
echo "== $SALIDA"
ffmpeg -nostats -i "$SALIDA" -af ebur128=framelog=verbose -f null - 2>&1 | grep -E "^\s+(I|LRA):"
