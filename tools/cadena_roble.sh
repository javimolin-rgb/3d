#!/usr/bin/env bash
# Rearmado de Casa Roble con el corte arreglado, repartido entre DOS contenedores.
#   tools/cadena_roble.sh a   -> contenedor principal (empieza por los tramos baratos)
#   tools/cadena_roble.sh b   -> contenedor de apoyo (empieza por los tres tramos caros)
#
# Los dos recorren la MISMA lista, en orden distinto, y se coordinan por git: antes de cada
# tramo traen lo que empujo el otro y lo saltan si ya tiene su marca en output/tramos/rehechos/.
# Asi se reparten solos sin repetir trabajo y, si un contenedor muere, el otro termina lo que
# falta: ninguno se queda con una lista fija que nadie mas puede recoger.
# Reanudable: una carpeta por tramo, nada se borra. No gasta tokens: corre solo.
cd /home/user/3d || exit 1
PY=$PWD/venv-bpy/bin/python
RAMA=javieramolin/dreamy-gates-iqll9z
MARCAS=output/tramos/rehechos

# Orden a: los baratos primero. Orden b: los tres caros primero y despues la lista de a al reves,
# para que los dos se crucen por el medio en vez de perseguirse.
CAROS=("s3p 193 229" "s3p 241 275" "s3p 289 326")
RESTO=("s3p 367 384" "s3p 97 144" "s3p 145 182" "s3p 337 366" "s5 73 132" "s5 1 48")
HECHOS=("s3p 230 240" "s3p 183 192" "s3p 327 336" "s3p 276 288" "s3p 49 96" "s5 49 72")
if [ "$1" = b ]; then
  LISTA=("${CAROS[@]}" "s5 1 48" "s5 73 132" "s3p 337 366" "s3p 145 182" "s3p 97 144" \
         "s3p 367 384" "${HECHOS[@]}")
else
  LISTA=("${RESTO[@]}" "${CAROS[@]}" "${HECHOS[@]}")
fi

nombre () { printf "%s_%04d-%04d" "$1" "$2" "$3"; }
trae    () { git fetch -q origin $RAMA && git merge --no-edit -q FETCH_HEAD; }
empuja  () {
  git add -A "$1" "$2" && git -c user.email=render@local -c user.name=render commit -q -m "$3" || return 0
  for i in 1 2 3 4 5 6 7 8; do
    trae && git push -q origin $RAMA && return 0
    sleep 10
  done
}

mkdir -p $MARCAS
# Marca lo que este contenedor ya rehizo antes de que existieran las marcas (idempotente).
for t in "${CAROS[@]}" "${RESTO[@]}" "${HECHOS[@]}"; do
  set -- $t ; nom=$(nombre "$@") ; n=$(($3-$2+1))
  [ "$(ls frames_roble/r_$1_$2_$3/f_*.png 2>/dev/null | wc -l)" -eq $n ] \
    && [ -f "output/tramos/$nom.mp4" ] && touch "$MARCAS/$nom.ok"
done

for t in "${LISTA[@]}"; do
  set -- $t
  nom=$(nombre "$@") ; d=frames_roble/r_$1_$2_$3 ; n=$(($3-$2+1))
  trae
  [ -f "$MARCAS/$nom.ok" ] && continue
  mkdir -p $d ; find $d -name "f_*.png" -size -10k -delete
  [ "$(ls $d/f_*.png 2>/dev/null | wc -l)" -ge $n ] || \
    $PY casa_roble_3d.py -- --vista dron --tramo $1 --out "$PWD/$d/f_" --desde $2 --hasta $3 \
        --res 720x1280 --samples 16 --nevada 0 >> $d/render.log 2>&1 < /dev/null
  if [ "$(ls $d/f_*.png 2>/dev/null | wc -l)" -eq "$n" ]; then
    LOOK=dia tools/armar_video.sh $d output/tramos/$nom.mp4 24
    [ "$1 $3" = "s3p 384" ] && cp $d/f_0384.png assets/roble/cenital_s3p.png
    touch "$MARCAS/$nom.ok"
    empuja output/tramos assets/roble "Roble: tramo $1 $2-$3 rehecho con el corte arreglado"
  fi
done

# Secuencia completa, solo cuando los 15 tramos rehechos tienen marca (s4 queda el viejo:
# lo rehace el usuario). La arma el contenedor que llegue ultimo; el otro ya salio del bucle.
trae
ls output/tramos/s3p_*.mp4 | sort | sed "s|^|file '$PWD/|;s|$|'|" > /tmp/ls3p.txt
ls output/tramos/s5_*.mp4  | sort | sed "s|^|file '$PWD/|;s|$|'|" > /tmp/ls5.txt
[ "$(ls $MARCAS/*.ok 2>/dev/null | wc -l)" -ge 15 ] \
  && [ "$(wc -l < /tmp/ls3p.txt)" -eq 13 ] && [ "$(wc -l < /tmp/ls5.txt)" -eq 4 ] && {
  ffmpeg -loglevel error -y -f concat -safe 0 -i /tmp/ls3p.txt -c copy output/roble_s3p.mp4
  ffmpeg -loglevel error -y -f concat -safe 0 -i /tmp/ls5.txt  -c copy output/roble_s5.mp4
  printf "file '%s'\n" $PWD/output/roble_s1.mp4 $PWD/output/roble_s2.mp4 $PWD/output/roble_s3p.mp4 \
         $PWD/output/roble_s4.mp4 $PWD/output/roble_s5.mp4 > /tmp/lseq.txt
  ffmpeg -loglevel error -y -f concat -safe 0 -i /tmp/lseq.txt -c copy output/casa_roble_secuencia.mp4
  empuja output output "Roble: secuencia rearmada con el corte arreglado"
  touch /home/user/3d/.cadena_lista
}
