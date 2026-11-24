#!/usr/bin/env bash
# Renderiza UN TRAMO de una sección del recorrido de dron de Casa Roble, para repartir una
# sección entre varios contenedores (CLAUDE.md, "Renders de video"). --desde/--hasta recortan
# sólo lo que se renderiza: las poses y la nieve acumulada se calculan igual para toda la
# sección, así que los cuadros salen idénticos a hacerla de corrido.
# Reanudable: borra los marcadores vacíos y salta los cuadros ya guardados.
# Uso: SECCION=s3p DESDE=1 HASTA=48 PY=$PWD/venv-bpy/bin/python \
#        setsid nohup tools/render_roble_tramo.sh > /dev/null 2>&1 &
# Avance legible en PROGRESO_RENDER.txt; registro en frames_roble/<sección>/render.log.
PY=${PY:-python3}
cd "$(dirname "$0")/.."
T=${SECCION:?falta SECCION}; A=${DESDE:?falta DESDE}; B=${HASTA:?falta HASTA}
mkdir -p frames_roble/"$T"
progreso() {
  while true; do
    {
      echo "Render Casa Roble - sección $T, tramo $A-$B"
      echo "Actualizado: $(TZ=America/Santiago date '+%d-%m %H:%M') (hora de Chile)"
      echo
      n=$((B - A + 1)); k=0
      # cuenta sólo los cuadros del tramo: la carpeta puede traer cuadros de otro tramo
      for i in $(seq "$A" "$B"); do
        f=$(printf 'frames_roble/%s/f_%04d.png' "$T" "$i")
        [ -f "$f" ] && [ "$(stat -c %s "$f")" -gt 10240 ] && k=$((k + 1))
      done
      printf "  %s %d-%d: %3d / %3d cuadros (%3d %%)\n" "$T" "$A" "$B" "$k" "$n" $((100 * k / n))
      ritmo=$(find frames_roble/"$T" -name 'f_*.png' -size +10k -mmin -60 2>/dev/null | wc -l)
      [ "$ritmo" -gt 0 ] && printf "Ritmo: %d cuadros/hora (faltan ~%d h)\n" "$ritmo" $(((n - k + ritmo - 1) / ritmo))
      if ps aux | grep "vista dron" | grep -v grep > /dev/null; then
        echo "Blender: renderizando"
      else
        echo "Blender: DETENIDO"
      fi
    } > PROGRESO_RENDER.txt.tmp && mv PROGRESO_RENDER.txt.tmp PROGRESO_RENDER.txt
    sleep 60
  done
}
progreso &
PROG=$!
find frames_roble/"$T" -name "f_*.png" -size -10k -delete
"$PY" casa_roble_3d.py -- --vista dron --tramo "$T" --out "$PWD/frames_roble/$T/f_" \
  --desde "$A" --hasta "$B" --res 720x1280 --samples 16 --nevada "${NEVADA:-0}" \
  >> frames_roble/"$T"/render.log 2>&1 < /dev/null
sleep 65
kill $PROG
