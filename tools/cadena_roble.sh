#!/usr/bin/env bash
# Rearmado de Casa Roble con el corte arreglado, repartido entre VARIOS contenedores.
#   tools/cadena_roble.sh a|b|c|d
#
# Todos recorren la MISMA lista de 15 tramos, cada uno arrancando en un punto distinto y dando
# la vuelta, y se coordinan por git:
#   - saltan el tramo que ya tiene marca en output/tramos/rehechos/ (terminado por cualquiera);
#   - saltan el tramo que otro contenedor tiene a medias, segun el latido que publica cada 15 min
#     en output/tramos/estado_<orden>.txt (0 < cuadros < total = lo esta rindiendo alguien).
# Con eso se reparten solos sin listas fijas: nadie repite trabajo y, si un contenedor muere, los
# demas recogen lo suyo en la vuelta siguiente en vez de dejarlo huerfano.
# Reanudable: una carpeta por tramo, nada se borra. No gasta tokens: corre solo.
#
# Un merge puede reescribir este archivo mientras corre y bash lo relee por posicion de byte,
# asi que la ejecucion en curso se corrompe. Corremos desde una copia para que no pase.
if [ "$ROBLE_COPIA" != 1 ]; then
  cp "$0" /tmp/$(basename "$0") && chmod +x /tmp/$(basename "$0")
  ROBLE_COPIA=1 exec /tmp/$(basename "$0") "$@"
fi
cd /home/user/3d || exit 1
PY=$PWD/venv-bpy/bin/python
RAMA=javieramolin/dreamy-gates-iqll9z
MARCAS=output/tramos/rehechos
ORDEN=${1:-a}

L=("s3p 97 144" "s3p 145 182" "s3p 337 366" "s5 1 48" "s3p 193 229" "s3p 241 275" \
   "s5 73 132" "s3p 289 326" "s3p 367 384" "s3p 49 96" "s3p 183 192" "s3p 230 240" \
   "s3p 276 288" "s3p 327 336" "s5 49 72")
case "$ORDEN" in a) OFF=0;; b) OFF=4;; c) OFF=6;; d) OFF=7;; *) OFF=0;; esac

nombre () { printf "%s_%04d-%04d" "$1" "$2" "$3"; }
trae    () { git fetch -q origin $RAMA && git merge --no-edit -q FETCH_HEAD; }
empuja  () {
  git add -A "$1" "$2" && git -c user.email=render@local -c user.name=render commit -q -m "$3" || return 0
  for i in 1 2 3 4 5 6 7 8; do
    trae && git push -q origin $RAMA && return 0
    sleep 10
  done
}
# 0 si OTRO contenedor tiene ese tramo a medias ahora mismo.
ocupado () {
  local f k
  for f in $(git ls-tree --name-only origin/$RAMA output/tramos/ 2>/dev/null | grep 'estado_.*\.txt$'); do
    [ "$f" = "output/tramos/estado_$ORDEN.txt" ] && continue
    k=$(git show origin/$RAMA:$f 2>/dev/null | awk -v m="$1" '$1==m{print $2}' | tail -1)
    [ -n "$k" ] && [ "$k" -gt 0 ] && [ "$k" -lt "$2" ] && return 0
  done
  return 1
}

mkdir -p $MARCAS
# Marca lo que este contenedor ya rehizo antes de que existieran las marcas (idempotente).
for t in "${L[@]}"; do
  set -- $t ; nom=$(nombre "$@") ; n=$(($3-$2+1))
  [ "$(ls frames_roble/r_$1_$2_$3/f_*.png 2>/dev/null | wc -l)" -eq $n ] \
    && [ -f "output/tramos/$nom.mp4" ] && touch "$MARCAS/$nom.ok"
done

# Vueltas hasta que los 15 tramos tengan marca: asi se recoge lo que deje a medias el que muera.
while :; do
  trae
  [ "$(ls $MARCAS/*.ok 2>/dev/null | wc -l)" -ge 15 ] && break
  hizo=0
  for i in $(seq 0 14); do
    set -- ${L[$(( (i + OFF) % 15 ))]}
    nom=$(nombre "$@") ; d=frames_roble/r_$1_$2_$3 ; n=$(($3-$2+1))
    trae
    [ -f "$MARCAS/$nom.ok" ] && continue
    mkdir -p $d ; find $d -name "f_*.png" -size -10k -delete
    hay=$(ls $d/f_*.png 2>/dev/null | wc -l)
    # Si no lo empece yo y otro lo tiene a medias, que lo termine el.
    [ "$hay" -eq 0 ] && ocupado "$nom" "$n" && continue
    [ "$hay" -ge "$n" ] || \
      $PY casa_roble_3d.py -- --vista dron --tramo $1 --out "$PWD/$d/f_" --desde $2 --hasta $3 \
          --res 720x1280 --samples 16 --nevada 0 >> $d/render.log 2>&1 < /dev/null
    if [ "$(ls $d/f_*.png 2>/dev/null | wc -l)" -eq "$n" ]; then
      LOOK=dia tools/armar_video.sh $d output/tramos/$nom.mp4 24
      [ "$1 $3" = "s3p 384" ] && cp $d/f_0384.png assets/roble/cenital_s3p.png
      touch "$MARCAS/$nom.ok" ; hizo=1
      empuja output/tramos assets/roble "Roble: tramo $1 $2-$3 rehecho con el corte arreglado"
    fi
  done
  # Vuelta entera sin hacer nada: lo que falta lo tiene otro. Esperar y volver a mirar.
  [ "$hizo" -eq 0 ] && sleep 300
done

# Secuencia completa (s4 queda el viejo: lo rehace el usuario). La arma el que llegue ultimo.
trae
ls output/tramos/s3p_*.mp4 | sort | sed "s|^|file '$PWD/|;s|$|'|" > /tmp/ls3p.txt
ls output/tramos/s5_*.mp4  | sort | sed "s|^|file '$PWD/|;s|$|'|" > /tmp/ls5.txt
[ "$(wc -l < /tmp/ls3p.txt)" -eq 13 ] && [ "$(wc -l < /tmp/ls5.txt)" -eq 4 ] && {
  ffmpeg -loglevel error -y -f concat -safe 0 -i /tmp/ls3p.txt -c copy output/roble_s3p.mp4
  ffmpeg -loglevel error -y -f concat -safe 0 -i /tmp/ls5.txt  -c copy output/roble_s5.mp4
  printf "file '%s'\n" $PWD/output/roble_s1.mp4 $PWD/output/roble_s2.mp4 $PWD/output/roble_s3p.mp4 \
         $PWD/output/roble_s4.mp4 $PWD/output/roble_s5.mp4 > /tmp/lseq.txt
  ffmpeg -loglevel error -y -f concat -safe 0 -i /tmp/lseq.txt -c copy output/casa_roble_secuencia.mp4
  empuja output output "Roble: secuencia rearmada con el corte arreglado"
  touch /home/user/3d/.cadena_lista
}
