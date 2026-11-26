#!/usr/bin/env bash
# Vigia del contenedor de apoyo: cada 2 min revisa que la cadena siga viva y la relanza si no.
# Los reinicios de contenedor los cubre el hook de SessionStart, que tambien relanza este vigia.
#   tools/vigia_roble.sh b
# Ojo con pgrep -f aca: funciona porque la linea de comandos de este proceso es solo la ruta del
# guion. En el hook, que lleva el comando en linea, hay que mirar la marca de tiempo en su lugar.
cd /home/user/3d || exit 1
while [ ! -f .cadena_lista ]; do
  touch .vigia_vivo
  if ! pgrep -f '[c]asa_roble_3d' >/dev/null && ! pgrep -f '[c]adena_roble' >/dev/null; then
    setsid tools/cadena_roble.sh "${1:-b}" >/dev/null 2>&1 &
  fi
  sleep 120
done
rm -f .vigia_vivo
