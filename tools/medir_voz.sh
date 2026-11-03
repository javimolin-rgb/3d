#!/usr/bin/env bash
# Mide una locución y la compara con el objetivo del reel: sonar a persona contando,
# no a locutor leyendo. Uso:  tools/medir_voz.sh <audio|video> [palabras_del_guion]
#
# Lo que importa y por qué:
#   - % de silencio: un locutor lee de corrido (<8 %). Una persona contando respira (15-22 %).
#   - pausas < 0,3 s no son respiraciones, son separaciones de palabra; no cuentan como ritmo.
#   - LRA: rango dinámico. Plano (<5 LU) = leído parejo. Expresivo = 6-10 LU.
#   - LUFS: Instagram normaliza a -14; más bajo y el reel suena apagado contra el resto del feed.
set -euo pipefail

ENTRADA="${1:?uso: tools/medir_voz.sh <audio|video> [palabras_del_guion]}"
PALABRAS="${2:-0}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

ffmpeg -y -v error -i "$ENTRADA" -vn -ac 1 -ar 16000 "$TMP/a.wav"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$TMP/a.wav")

echo "== $ENTRADA  (${DUR}s)"
echo
ffmpeg -nostats -i "$TMP/a.wav" -af ebur128=framelog=verbose -f null - 2>&1 \
  | grep -E "^\s+(I|LRA):" | sed 's/^/  /'
echo

# Envolvente RMS en ventanas de 200 ms. El umbral es relativo a la mediana porque casi
# toda locución entregada viene con cama o ruido de sala: un umbral fijo en dB no ve las pausas.
ffmpeg -nostats -v info -i "$TMP/a.wav" \
  -af "asetnsamples=n=3200,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=$TMP/rms.txt" \
  -f null - >/dev/null 2>&1
grep -oE '=-?[0-9.]+|=-inf' "$TMP/rms.txt" | tr -d '=' > "$TMP/v.txt"

python3 -c "
import statistics, sys
vals=[]
for linea in open('$TMP/v.txt'):
    linea=linea.strip()
    vals.append(-90.0 if linea in ('-inf','') else float(linea))
dur=float('$DUR'); palabras=int('$PALABRAS'); paso=0.2
if not vals: sys.exit('sin datos')
med=statistics.median(vals)
quieto=[x < med-12 for x in vals]

# agrupar ventanas quietas contiguas en pausas
pausas=[]; i=0
while i < len(quieto):
    if quieto[i]:
        j=i
        while j < len(quieto) and quieto[j]: j+=1
        pausas.append((i*paso,(j-i)*paso)); i=j
    else: i+=1
# descartar cabeza y cola: no son ritmo interno
internas=[p for p in pausas if p[0] > 0.3 and p[0]+p[1] < dur-0.4]
sil=sum(p[1] for p in internas)
respiros=[p for p in internas if p[1] >= 0.3]

def veredicto(ok): return 'ok' if ok else 'FUERA'
print('  silencio interno: %.1f s de %.1f s = %.1f %%   (objetivo 15-22 %%)  %s'
      % (sil, dur, 100*sil/dur, veredicto(15 <= 100*sil/dur <= 22)))
print('  pausas internas:  %d, de las cuales %d son respiraciones reales (>=0,30 s)'
      % (len(internas), len(respiros)))
if internas:
    print('  pausa mediana:    %.2f s   mayor: %.2f s' %
          (statistics.median([p[1] for p in internas]), max(p[1] for p in internas)))
    arranque=min(p[0] for p in internas)
    print('  primera pausa en t=%.1f s  %s' % (arranque, veredicto(arranque < 6)),
          '' if arranque < 6 else ' <- abre leyendo de corrido')
if palabras:
    fonacion=dur-sil
    print('  velocidad dentro de la frase: %.0f palabras/min   (objetivo 150-165)  %s'
          % (60*palabras/fonacion, veredicto(150 <= 60*palabras/fonacion <= 165)))
print()
print('  mapa de pausas (t -> duración):')
print('   ', '  '.join('%.1f:%.2f' % p for p in internas) or '(ninguna)')
"
