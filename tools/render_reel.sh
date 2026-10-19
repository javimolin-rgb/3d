#!/usr/bin/env bash
# Renderiza los conectores del reel continuo de Casa Lingue (casa_lingue_3d.py --vista reel), en orden.
# Reanudable: borra los marcadores vacíos y salta los cuadros ya guardados.
# Uso: PY=<python con bpy> setsid nohup tools/render_reel.sh c1 c3 c4 > /dev/null 2>&1 &
#      (cuadros en frames_reel/<tramo>/f_*.png, registro en frames_reel/<tramo>/render.log)
PY=${PY:-python3}
cd "$(dirname "$0")/.."
for t in "$@"; do
  case $t in c1) n=101;; c3) n=107;; c4) n=191;; esac
  mkdir -p frames_reel/$t
  find frames_reel/$t -name "f_*.png" -size -10k -delete
  "$PY" casa_lingue_3d.py -- --vista reel --tramo $t --out "$PWD/frames_reel/$t/f_" \
    --res 720x1280 --samples 32 --frames 1-$n >> frames_reel/$t/render.log 2>&1 < /dev/null
done
