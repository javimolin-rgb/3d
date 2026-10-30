# Casa Ciprés — primer intento (archivado)

Esto es la **primera prueba del proyecto**, hecha antes de que existiera la receta de
`RECETA.md`. Se guarda como referencia, **no se usa ni se continúa.**

## Por qué está archivado

La escena es un **campo chileno al atardecer**. Pero el emplazamiento real de Casa Ciprés es
**playa del norte (más seco)**, así que el contexto, la luz y la vegetación no corresponden.
Casa Ciprés se rehace desde cero partiendo de `casa_huingan_3d.py` (ver `RECETA.md` §5).

Además es anterior al formato actual: videos horizontales / de otra duración, sin el recorrido
por secciones ni la secuencia continua de 42 s.

## Qué puede servir

- **El render de la casa en sí** (volumen, proporciones, materiales del casco) sirve de
  referencia visual al rehacerla. El terreno, el cielo y la vegetación, no.
- El tratamiento de **grado cálido de atardecer** sigue siendo válido como referencia de color
  si alguna vez se pide una toma de atardecer en cualquier casa. Es lo que usa `LOOK=atardecer`
  en `tools/armar_video.sh`.

## Contenido

| Archivo | Qué es |
|---|---|
| `casa_cipres_v1_3d.py` | La escena de campo al atardecer (era `casa_cipres_3d.py`) |
| `drone_video_cipres_v1.py` | Armaba un video estilo dron desde renders y planos, antes del sistema actual |
| `casa_cipres_dron*.mp4` | Los tres videos de esa etapa |
| `preview_*.mp4` | Previews de la exploración: vegetación, texturas, toma abierta, luz chilena, atardecer |

## Dependencia que quedó fuera

`vegetacion.py` nació para esta escena, pero **sigue en la raíz del repo a propósito**: lo importa
`casa_lingue_3d.py` (`import vegetacion as vg`) para generar árboles y arbustos con Sapling Tree
Gen. Moverlo rompería Lingue. No es parte del archivo.
