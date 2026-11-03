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
# VOZ_LUFS=-16  a cuánto se lleva la voz antes de mezclar.
# CAMA_LUFS=-30 a cuánto se lleva la cama. La diferencia entre las dos es lo que decide si
#               se entiende: una locución quiere la voz unos 12-14 dB sobre la cama. Fijar
#               las dos por separado es más seguro que una ganancia a ojo, porque la cama
#               puede llegar cruda o ya masterizada y el mismo -8 dB sirve para una y
#               ahoga a la otra.
set -euo pipefail

VIDEO="${1:?uso: tools/montar_voz.sh <video> <voz> <salida.mp4> [cama]}"
VOZ="${2:?falta la voz}"
SALIDA="${3:?falta la salida}"
CAMA="${4:-}"
RETARDO="${RETARDO:-0.8}"
VOZ_LUFS="${VOZ_LUFS:--16}"
CAMA_LUFS="${CAMA_LUFS:--30}"

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
echo "video ${DUR}s · voz ${DV}s · retardo ${RETARDO}s"
echo "  voz a ${VOZ_LUFS} LUFS · cama a ${CAMA_LUFS} LUFS ($FUENTE)"
python3 -c "
d,v,r=float('$DUR'),float('$DV'),float('$RETARDO')
s=d-(v+r)
print('  aviso: la voz se pasa %.2f s del video; se va a cortar' % -s) if s<-0.05 else \
print('  quedan %.2f s de cola sin voz al final' % s)
"

VOZ_F="adelay=${MS}|${MS},apad,atrim=0:${DUR},asetpts=N/SR/TB"
FADE=$(python3 -c "print(max(0,float('$DUR')-2))")
FADE_CAMA=""

lufs_de() {   # $1 = archivo, $2 = índice de pista ('a:0' o vacío)
  ffmpeg -nostats -i "$1" ${2:+-map "$2"} -af ebur128 -f null - 2>&1 \
    | grep -A3 "Integrated loudness" | grep -oE "I: *-?[0-9.]+" | tail -1 \
    | grep -oE "\-?[0-9.]+"
}

ganancia_a() {   # $1 = lufs medido, $2 = lufs objetivo
  python3 -c "print('%.2f' % (float('$2') - float('$1')))"
}

# loudnorm de una pasada se queda corto (midió -15,5 con objetivo -14) porque estima el
# material sobre la marcha. Dos pasadas: la primera mide, la segunda corrige con lo medido.
medir_loudnorm() {   # $1 = cadena de filtros hasta antes de loudnorm
  ffmpeg -nostats -v info "${ENTRADAS[@]}" -filter_complex \
    "$1,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[out]" \
    -map "[out]" -f null - 2>&1 | python3 -c "
import sys, json, re
t = sys.stdin.read()
m = re.findall(r'\{[^{}]*input_i[^{}]*\}', t, re.S)
if not m: sys.exit(1)
d = json.loads(m[-1])
print('measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s'
      % (d['input_i'], d['input_tp'], d['input_lra'], d['input_thresh']))
"
}

mezclar() {   # $1 = etiqueta de la entrada de cama
  local previo="
      [1:a]aformat=sample_rates=48000:channel_layouts=stereo,
           volume=${G_VOZ}dB,${VOZ_F}[voz];
      [voz]asplit=2[voz_mix][voz_sc];
      [$1]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:${DUR},
          volume=${G_CAMA}dB${FADE_CAMA}[cama];
      [cama][voz_sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[cama_d];
      [voz_mix][cama_d]amix=inputs=2:duration=first:normalize=0"
  local medido
  if medido=$(medir_loudnorm "$previo"); then
    echo "  medido: $medido"
    LN="loudnorm=I=-14:TP=-1.5:LRA=11:${medido}:linear=true"
  else
    echo "  (no se pudo medir; normalizo en una pasada)"
    LN="loudnorm=I=-14:TP=-1.5:LRA=11"
  fi
  ffmpeg -y -v error -stats "${ENTRADAS[@]}" -filter_complex "${previo},${LN}[out]" \
    -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 192k -shortest "$SALIDA"
}

L_VOZ=$(lufs_de "$VOZ")
G_VOZ=$(ganancia_a "$L_VOZ" "$VOZ_LUFS")
if [ -n "$CAMA" ]; then L_CAMA=$(lufs_de "$CAMA"); else L_CAMA=$(lufs_de "$VIDEO" "a:0"); fi
G_CAMA=$(ganancia_a "$L_CAMA" "$CAMA_LUFS")
echo "  voz medida ${L_VOZ} -> ${G_VOZ} dB · cama medida ${L_CAMA} -> ${G_CAMA} dB"
echo "  la voz queda $(python3 -c "print('%.0f' % (float('$VOZ_LUFS')-float('$CAMA_LUFS')))") dB sobre la cama"

if [ -n "$CAMA" ]; then
  FADE_CAMA=",afade=t=out:st=${FADE}:d=2"
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
