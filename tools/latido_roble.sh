#!/usr/bin/env bash
# Latido: cada 15 min publica cuantos cuadros lleva cada tramo en este contenedor, para que el
# otro —y el documento de progreso— puedan sumar el avance EN CURSO y no solo los tramos
# terminados. Sin esto un tramo caro deja el total quieto ocho horas.
# Un solo intento de push: si pierde la carrera contra el push de un tramo, la gana el proximo
# latido. Asi nunca le pelea el turno al trabajo de verdad.
# Un merge puede reescribir este archivo mientras corre y bash lo relee por posicion de byte,
# asi que la ejecucion en curso se corrompe. Corremos desde una copia para que no pase.
if [ "$ROBLE_COPIA" != 1 ]; then
  cp "$0" /tmp/$(basename "$0") && chmod +x /tmp/$(basename "$0")
  ROBLE_COPIA=1 exec /tmp/$(basename "$0") "$@"
fi
cd /home/user/3d || exit 1
RAMA=javieramolin/dreamy-gates-iqll9z
ORDEN=${1:-a}
while [ ! -f .cadena_lista ]; do
  : > output/tramos/estado_$ORDEN.txt
  for d in frames_roble/r_*/; do
    [ -d "$d" ] || continue
    IFS=_ read -r sec des has <<< "$(basename "$d" | sed 's|^r_||')"
    [ -n "$has" ] || continue
    k=$(ls "$d"/f_*.png 2>/dev/null | wc -l)
    printf "%s_%04d-%04d %d\n" "$sec" "$des" "$has" "$k" >> output/tramos/estado_$ORDEN.txt
  done
  git add -A output/tramos/estado_$ORDEN.txt 2>/dev/null \
    && git -c user.email=noreply@anthropic.com -c user.name=Claude commit -q -m "Roble: latido $ORDEN" 2>/dev/null \
    && { git fetch -q origin $RAMA && git merge --no-edit -q FETCH_HEAD \
         && git push -q origin $RAMA; } >/dev/null 2>&1
  sleep 900
done
