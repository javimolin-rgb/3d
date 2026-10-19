#!/usr/bin/env bash
# Escribe cada minuto el avance del render de los conectores del reel en PROGRESO_RENDER.txt
# y copia el último cuadro a PROGRESO_ultimo_cuadro.jpg (ambos en la raíz del repo, ignorados por git).
# Se puede abrir desde la app de Claude sin gastar tokens.
# Uso: setsid nohup tools/progreso_render.sh > /dev/null 2>&1 &
cd "$(dirname "$0")/.."
TOTAL=(c1:101 c3:107 c4:191)
while true; do
  {
    echo "Render de conectores del reel Casa Lingue"
    echo "Actualizado: $(TZ=America/Santiago date '+%d-%m %H:%M') (hora de Chile)"
    echo
    hechos=0; todos=0
    for par in "${TOTAL[@]}"; do
      t=${par%%:*}; n=${par##*:}
      k=$(find frames_reel/$t -name 'f_*.png' -size +10k 2>/dev/null | wc -l)
      hechos=$((hechos + k)); todos=$((todos + n))
      printf "  %s: %3d / %3d cuadros (%3d %%)\n" "$t" "$k" "$n" $((100 * k / n))
    done
    echo
    printf "Total: %d / %d cuadros (%d %%)\n" "$hechos" "$todos" $((100 * hechos / todos))
    # ritmo: cuadros guardados en la última hora
    ritmo=$(find frames_reel/c? -name 'f_*.png' -size +10k -mmin -60 2>/dev/null | wc -l)
    if [ "$ritmo" -gt 0 ]; then
      falta=$(( (todos - hechos) * 60 / ritmo ))
      printf "Ritmo: %d cuadros/hora; faltan unas %d h %02d min\n" "$ritmo" $((falta / 60)) $((falta % 60))
    fi
    if ps aux | grep "vista reel" | grep -v grep > /dev/null; then
      echo "Blender: renderizando"
    else
      echo "Blender: DETENIDO (si no terminó, el contenedor se reinició y hay que relanzar)"
    fi
  } > PROGRESO_RENDER.txt.tmp && mv PROGRESO_RENDER.txt.tmp PROGRESO_RENDER.txt
  ult=$(ls -t frames_reel/c?/f_*.png 2>/dev/null | head -1)
  if [ -n "$ult" ] && [ "$(stat -c %s "$ult")" -gt 10240 ]; then
    ffmpeg -loglevel error -y -i "$ult" -vf scale=360:-1 PROGRESO_ultimo_cuadro.jpg
  fi
  sleep 60
done
