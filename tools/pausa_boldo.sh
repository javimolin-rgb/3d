#!/usr/bin/env bash
# Pausa de tres segundos sobre el segundo piso, dentro de s3 de Casa Boldo, y el MP4 de la sección
# con la pausa adentro. El barrido del corte pasa por el 2do piso en un suspiro y la revisión pidió
# quedarse ahí para rotularlo con flechas en edición.
#
# Es **un solo cuadro** renderizado con la cámara y el corte detenidos en el cuadro K de s3, que el
# video repite: en ese encuadre no entra el lago, así que no hay nada en movimiento y la pausa sale
# idéntica a renderizarla cuadro a cuadro —y sin el arrastre del motion blur, que congelando un
# cuadro de la sección se vería como una mancha fija durante los tres segundos—.
#
# Uso: PY=$PWD/venv-bpy/bin/python tools/pausa_boldo.sh [cuadro] [cuadros_de_pausa]
PY=${PY:-python3}
cd "$(dirname "$0")/.."
K=${1:-121}        # cuadro de s3 donde se para: corte en z = 4,1 m, el 2do piso entero a la vista
HOLD=${2:-72}      # 3 s a 24 fps
N=$(python3 -c "import re;print(re.search(r'\"s3\": (\d+)', open('casa_boldo_3d.py').read()).group(1))")
mkdir -p frames_boldo/pausa
if [ ! -s frames_boldo/pausa/f_0001.png ]; then
  "$PY" casa_boldo_3d.py -- --vista dron --tramo pausa --pausaf "$K" --cuadro 1 \
    --out "$PWD/frames_boldo/pausa/f_0001.png" --res 720x1280 --samples 32 \
    >> frames_boldo/pausa/render.log 2>&1 < /dev/null
fi
rm -rf frames_boldo/s3_pausa && mkdir -p frames_boldo/s3_pausa
python3 - "$K" "$HOLD" "$N" <<'PY'
import os, sys
K, HOLD, N = (int(v) for v in sys.argv[1:4])
S3, OUT, P = "frames_boldo/s3", "frames_boldo/s3_pausa", "frames_boldo/pausa/f_0001.png"
n = 0
for f in list(range(1, K + 1)) + [None] * HOLD + list(range(K + 1, N + 1)):
    n += 1
    os.link(P if f is None else f"{S3}/f_{f:04d}.png", f"{OUT}/f_{n:04d}.png")
print(f"s3 con la pausa: {n} cuadros ({K} + {HOLD} + {N - K})")
PY
LOOK=dia tools/armar_video.sh frames_boldo/s3_pausa output/casa_boldo_s3.mp4 24
