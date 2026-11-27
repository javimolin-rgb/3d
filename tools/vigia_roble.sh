#!/usr/bin/env bash
# Vigia del contenedor de apoyo: cada 2 min revisa que la cadena siga viva y la relanza si no.
# Los reinicios de contenedor los cubre el hook de SessionStart, que tambien relanza este vigia.
#   tools/vigia_roble.sh b
# Ojo con pgrep -f aca: funciona porque la linea de comandos de este proceso es solo la ruta del
# guion. En el hook, que lleva el comando en linea, hay que mirar la marca de tiempo en su lugar.
# Un merge puede reescribir este archivo mientras corre y bash lo relee por posicion de byte,
# asi que la ejecucion en curso se corrompe. Corremos desde una copia para que no pase.
if [ "$ROBLE_COPIA" != 1 ]; then
  cp "$0" /tmp/$(basename "$0") && chmod +x /tmp/$(basename "$0")
  ROBLE_COPIA=1 exec /tmp/$(basename "$0") "$@"
fi
cd /home/user/3d || exit 1
while [ ! -f .cadena_lista ]; do
  touch .vigia_vivo
  if ! pgrep -f '[c]asa_roble_3d' >/dev/null && ! pgrep -f '[c]adena_roble' >/dev/null; then
    setsid tools/cadena_roble.sh "${1:-b}" >/dev/null 2>&1 &
  fi
  pgrep -f '[l]atido_roble' >/dev/null || setsid tools/latido_roble.sh "${1:-b}" >/dev/null 2>&1 &
  sleep 120
done
rm -f .vigia_vivo
