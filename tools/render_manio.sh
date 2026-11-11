#!/usr/bin/env bash
# Renderiza las secciones del recorrido de dron de Casa Mañío (casa_manio_3d.py --vista dron),
# en orden. Reanudable: borra los marcadores vacíos y salta los cuadros ya guardados.
# Avance legible en PROGRESO_RENDER.txt y PROGRESO_ultimo_cuadro.jpg (raíz del repo, ignorados por git).
# Uso: setsid nohup tools/render_manio.sh s1 [s2 ...] > /dev/null 2>&1 &
#      (cuadros en frames_manio/<sección>/f_*.png, registro en frames_manio/<sección>/render.log)
PY=${PY:-python3}
cd "$(dirname "$0")/.."
progreso() {
  while true; do
    {
      echo "Render del recorrido de dron Casa Mañío"
      echo "Actualizado: $(TZ=America/Santiago date '+%d-%m %H:%M') (hora de Chile)"
      echo
      for t in "$@"; do
        n=$(python3 -c "import re;print(re.search(r'\"$t\": (\d+)', open('casa_manio_3d.py').read()).group(1))")
        k=$(find frames_manio/$t -name 'f_*.png' -size +10k 2>/dev/null | wc -l)
        printf "  %s: %3d / %3d cuadros (%3d %%)\n" "$t" "$k" "$n" $((100 * k / n))
      done
      ritmo=$(find frames_manio -name 'f_*.png' -size +10k -mmin -60 2>/dev/null | wc -l)
      [ "$ritmo" -gt 0 ] && printf "Ritmo: %d cuadros/hora\n" "$ritmo"
      if ps aux | grep "vista dron" | grep -v grep > /dev/null; then
        echo "Blender: renderizando"
      else
        echo "Blender: DETENIDO"
      fi
    } > PROGRESO_RENDER.txt.tmp && mv PROGRESO_RENDER.txt.tmp PROGRESO_RENDER.txt
    ult=$(ls -t frames_manio/*/f_*.png 2>/dev/null | head -1)
    if [ -n "$ult" ] && [ "$(stat -c %s "$ult")" -gt 10240 ]; then
      ffmpeg -loglevel error -y -i "$ult" -vf scale=360:-1 PROGRESO_ultimo_cuadro.jpg
    fi
    sleep 60
  done
}
progreso "$@" &
PROG=$!
for t in "$@"; do
  mkdir -p frames_manio/$t
  find frames_manio/$t -name "f_*.png" -size -10k -delete
  "$PY" casa_manio_3d.py -- --vista dron --tramo $t --out "$PWD/frames_manio/$t/f_" \
    --res 720x1280 --samples 32 >> frames_manio/$t/render.log 2>&1 < /dev/null
done
sleep 65
kill $PROG
