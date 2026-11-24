# Reparto del render de Casa Roble entre contenedores

Medido en este repo: **9,3 min/cuadro** a 720x1280 y 16 muestras, en cuatro núcleos, parejo
(doce cuadros seguidos de s5: 542 a 595 s, media 559). Quedaban 564 cuadros = **87 h** en un
solo contenedor, y el contenedor se reinicia cada hora y media, así que se reparte.

Cada contenedor renderiza su tramo con `tools/render_roble_tramo.sh` (que usa `--desde/--hasta`;
las poses y la nieve se calculan igual para toda la sección, así que los cuadros salen idénticos
a hacer la sección de corrido), arma **el MP4 de su tramo** con `LOOK=dia tools/armar_video.sh`
y lo sube a `output/tramos/`. Al final se pegan sin recodificar con el demuxer `concat` de
ffmpeg: el look de `armar_video.sh` no depende del tiempo (la viñeta va con `lt(t,1000)`), así
que los pedazos quedan con la misma corrección de color.

**Todos con lo mismo**: `bpy==5.0.1`, `--res 720x1280`, `--samples 16`, `--nevada 0`. Si un
contenedor cambia cualquiera de esos cuatro, la diferencia se ve justo en el empalme.

| tramo | sección | cuadros | archivo | |
|---|---|---|---|---|
|  1 | s5  |   1-48  | `output/tramos/s5_0001-0048.mp4` |
| 1b | s5  |  49-72  | `output/tramos/s5_0049-0072.mp4` | robo de trabajo |
|  2 | s5  |  73-132 | `output/tramos/s5_0073-0132.mp4` |
|  3 | s5  | 133-192 | `output/tramos/s5_0133-0192.mp4` |
|  4 | s3p |   1-48  | `output/tramos/s3p_0001-0048.mp4` | **listo** |
|  5 | s3p |  49-96  | `output/tramos/s3p_0049-0096.mp4` |
|  6 | s3p |  97-144 | `output/tramos/s3p_0097-0144.mp4` |
|  7 | s3p | 145-192 | `output/tramos/s3p_0145-0192.mp4` |
|  8 | s3p | 193-240 | `output/tramos/s3p_0193-0240.mp4` |
|  9 | s3p | 241-288 | `output/tramos/s3p_0241-0288.mp4` |
| 10 | s3p | 289-336 | `output/tramos/s3p_0289-0336.mp4` |
| 11 | s3p | 337-384 | `output/tramos/s3p_0337-0384.mp4` |

s1 y s2 ya estaban rendidas enteras (`output/roble_s1.mp4`, `output/roble_s2.mp4`).

## Lo que salió mal en este reparto: se midió una sola parte del recorrido

Los 9,3 min/cuadro se midieron **en los primeros cuadros de s5**, y se repartió suponiendo que
valían para todo. No valen: dentro de una misma sección el costo cambia por un factor 4.

Medido después, cada contenedor sobre su propio `render.log`:

| sección | cuadros | min/cuadro |
|---|---|---|
| s5  |  13-48  | 9,3 |
| s5  |  73-132 | **2,6-3,1** |
| s3p |   1-48  | **2,2** |
| s3p | 337-384 | **9,0** |

O sea que **no es que una sección sea cara y la otra barata**: dentro de cada una el costo varía
por un factor 4, y las dos tienen una punta cara y una barata. El 9,3 original salió de los
primeros cuadros de s5 y se generalizó a las 564: ése fue el error de base.

Y no son escalones entre tramos sino **una rampa continua**. Medido cuadro a cuadro dentro de un
solo tramo (s5 13-25, un mismo contenedor):

```
f_0013 9,2   f_0017 8,2   f_0021 8,6   f_0025 6,8
f_0014 8,7   f_0018 8,4   f_0022 7,7
f_0015 8,5   f_0019 8,1   f_0023 7,4
f_0016 8,5   f_0020 8,3   f_0024 7,2
```

Baja parejo, pero **la recta no sirve para extrapolar y conviene no intentarlo**. Ajustada sobre
esos 13 cuadros da -0,2 min por cuadro, predice 1,8 min/cuadro en el f_0050 y lo medido ahí es
4,98: erra por 2,7 veces. Y la misma recta se hace **negativa** en el f_0072, que era señal
suficiente para descartarla sin necesidad de medir nada.

La curva es convexa: baja cada vez más despacio hacia una asíntota de ~2,85 min/cuadro. Medido en
cuatro contenedores distintos, el exceso sobre esa asíntota se parte al medio cada ~26 cuadros:

```
f_0019  +5,55     f_0025  +3,95     f_0051  +2,01     f_0100  +0,05     f_0160  +0,04
```

Lo que sí queda establecido, y es lo que importaba para repartir, es que hay **una sola curva
continua a lo largo de s5** que cruza cuatro contenedores sin escalón: 9,2 → 6,8 (uno), 4,86
(otro), 2,9 y 2,89 (otros dos). No hay diferencia de máquina.

Eso además descarta la explicación que parecía más probable con los datos de arriba: que el raro
fuera *el contenedor* y no el tramo. Tres contenedores distintos midieron tres cosas distintas y
ninguno había medido dos tramos en la misma máquina, así que "s5 es cara al principio" y "esa
máquina es lenta" explicaban los mismos números. La rampa dentro de un único contenedor los
distingue: es la posición en el recorrido, no la máquina.

Con eso, la hipótesis de que el costo sigue **cuánto paisaje entra en cuadro** es la que queda en
pie —en Boldo ya estaba medido que la cenital era tres veces más barata que el vuelo bajo sobre el
agua—, aunque sigue sin probarse y no se escribe acá como causa. Lo que sí está medido es que ni
la sección ni el estado del corte alcanzan para predecirlo: en Peumo lo caro era el techo a medio
abrir y lo barato el techo cerrado, y acá la cola de s3p —techo cerrado y casi a plomo— es la cara.

**Cómo medir esto bien la próxima vez**, que son tres errores distintos, todos cometidos acá:

1. Mirar el `render.log` **cuadro a cuadro** dentro de un mismo tramo, no el promedio del tramo.
   El promedio esconde la rampa y encima invita a atribuirle a la máquina lo que es posición en
   el recorrido.
2. **No ajustar una recta.** La curva es convexa y se aplana; una recta ajustada sobre un puñado
   de cuadros y proyectada decenas de cuadros más allá erra por un factor 3. Si el modelo predice
   un valor imposible dentro del rango que interesa —acá, tiempo negativo—, está descartado sin
   necesidad de medir.
3. **Tres puntos separados por sección, no dos.** Con dos puntos lejanos entra cualquier curva, y
   la elección de la forma es justamente lo que decide el reparto.

Y el robo de trabajo tiene su propio límite, que conviene tener presente: rearmar el entorno de
un contenedor cuesta ~25 min (apt, la rueda de bpy y 1,3 GB de recursos). Robarle la cola a un
tramo al que le quedan menos de ~40 min de render es trabajo de más, no de menos. Sólo sale a
cuenta con un contenedor que **ya tiene el entorno armado**, o con colas largas.

Para la próxima: **medir varios puntos de cada sección antes de repartir** (basta rendir unos
pocos cuadros sueltos con `--desde/--hasta` en el arranque, el medio y el final) y repartir por
horas estimadas, no por cantidad de cuadros. Partir en tramos chicos ayuda igual, porque acota lo
que puede tardar el peor tramo aunque la curva no se conozca.

Mientras tanto, lo que queda se reparte por **robo de trabajo**, que no necesita predecir nada: el
contenedor que termina su tramo avisa, y se le da la cola de un tramo todavía en curso. Al dueño
de ese tramo se le acorta el final a un cuadro X cómodamente por delante de donde va (arma su MP4
hasta X) y el tramo [X+1, fin] pasa a ser un tramo más de la tabla.

Los tramos de s3p son de 48 cuadros y no de 55 porque en la sección del corte el costo por
cuadro **no crece parejo, hace una loma** (en Peumo, el doble de caro con el techo a medio abrir,
porque el interior se ilumina sólo de rebote por una abertura parcial). Partir en tramos más
chicos acota lo que puede tardar el peor tramo; no se midió dónde cae la loma en Roble porque
medirla costaba más que achicar los tramos.

## Qué hace falta en un contenedor nuevo

Nada de esto va al repo (~1,7 GB), y `assets/roble/casa.blend` **sí** está en el repo, así que
no hay que volver a correr el extractor del STL (tarda más de una hora):

```
apt-get update && apt-get install -y libegl1 libgl1 libglx-mesa0 libgl1-mesa-dri libxi6 \
  libxrender1 libxxf86vm1 libxfixes3 libsm6 libice6 libxkbcommon0 libwayland-client0
python3.11 -m venv venv-bpy && ./venv-bpy/bin/pip install bpy==5.0.1
tools/get_assets_nieve.sh && tools/get_assets_hdri.sh nieve
```

## Pegar los tramos al final

```
printf "file '%s'\n" output/tramos/s5_*.mp4 > /tmp/lista.txt
ffmpeg -f concat -safe 0 -i /tmp/lista.txt -c copy output/roble_s5.mp4
```

Para verificar un empalme, medir sobre los **PNG crudos**, no sobre los MP4 (CLAUDE.md explica
por qué), y comparar contra los vecinos inmediatos del empalme, no contra una base de otra parte
del clip.

## Una trampa al medir el ritmo en `render.log`

Blender imprime el tiempo acumulado como `MM:SS.ss` antes de la primera hora y como
`HH:MM:SS.ss` después, en el mismo archivo. Un regex de `HH:MM:SS` se come **en silencio** todos
los cuadros de la primera hora: en el tramo s3p 1-48 dejaba 21 de 48 y el ritmo salía mal sin que
nada fallara.

## Un aviso del log que no es un problema

Al armar la escena salen `WARNING Topology differs, disabling motion blur for object
Roble_ceramica / Roble_sabanas / Roble_marco`. Son objetos de interior a los que el corte les
cambia la topología entre cuadros, así que Cycles les apaga el desenfoque de movimiento. No aborta
nada y los cuadros salen. Si en el video final algo de la casa no arrastra desenfoque cuando el
dron pasa rápido, el origen es ése y **no** el empalme entre tramos.
