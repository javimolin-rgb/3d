# Locución de los reels

Cómo se hace la voz en off de un reel de casa, y por qué la primera de Casa Peumo suena a
locutor. Sirve para las nueve casas: cambia el guion, no el método.

## 1. El problema no es la voz, es el ritmo

El reel actual (`Reel_Casa_Peumo_voz_hombre_1.mp4`, 49,57 s) medido con
`tools/medir_voz.sh <archivo> 105`:

```
  I: -17.3 LUFS      LRA: 4.0 LU
  silencio interno: 4.0 s de 49.6 s = 8.1 %        (objetivo 15-22 %)   FUERA
  pausas internas:  12, de las cuales 5 son respiraciones reales (>=0,30 s)
  pausa mediana:    0.20 s      mayor: 1.00 s
  primera pausa en t=13.4 s                        <- abre leyendo de corrido
  velocidad dentro de la frase: 138 palabras/min   (objetivo 150-165)   FUERA
```

Las cuatro cosas que dice ese cuadro, y que son exactamente lo que se escucha:

- **Abre sin respirar.** Los primeros 13,4 s —todo el gancho— van en un solo chorro. Nadie
  cuenta algo así; un locutor leyendo, sí.
- **Siete de las doce pausas duran 0,20 s.** Eso no es una respiración, es la separación entre
  dos palabras. Pausas de verdad hay cinco en 50 segundos.
- **Habla lento y parejo (138 ppm) en vez de rápido y con aire.** Es la raíz del asunto: la
  sensación de "pausado" no se consigue arrastrando las palabras, se consigue **diciéndolas a
  velocidad normal y callándose entre medio**. Arrastrarlas es justo lo que suena a locutor.
- **LRA 4,0 LU.** Rango plano, todas las frases al mismo peso. Una persona entusiasmada sube y
  baja: 6-10 LU.

Y aparte, **-17,3 LUFS**: Instagram normaliza a -14, así que el reel además entra apagado
contra lo que venía antes en el feed.

> La regla, entonces: **el total no cambia (≈49,5 s), cambia el reparto.** Las mismas 105
> palabras dichas a 155-165 ppm ocupan ~41 s y dejan ~8 s de silencio para repartir en 13
> respiraciones. Mismo largo, otra persona hablando.

## 2. Voz y modelo (ElevenLabs)

- **Modelo: `eleven_v3`.** Es el expresivo y el que entiende Audio Tags. `multilingual_v2` es
  más estable pero más plano — justo lo que no queremos. Para probar tomas rápido y barato,
  `flash_v2_5`; el máster siempre en v3.
- **Ajustes:** Stability **0,35** · Similarity **0,80** · Speed **1,05**.
  Stability alta (0,7+) es lo que aplana la lectura: para un reel conviene baja y generar
  dos o tres tomas. Similarity por encima de 0,85 empieza a meter artefactos.
- **Voz:** filtrar la Voice Library por **español (latinoamericano)**, masculina, y descartar
  todo lo que esté etiquetado *narration*, *documentary* o *broadcast* — ese es el banco de
  locutores. Buscar las etiquetadas *conversational* o *casual*. Si ninguna calza, Voice Design
  con este prompt:

  > Hombre chileno de unos 30 años, voz cálida y cercana, registro medio, habla relajada y
  > natural como contándole algo a un amigo, con entusiasmo contenido. Sin tono publicitario,
  > sin grandilocuencia, sin acento neutro de doblaje.

  Los IDs de voz de la librería cambian; anotar aquí cuál quedó cuando se elija.
- **Ética:** sólo voces de librería, diseñadas, o clonadas con consentimiento escrito. Nada de
  clonar a alguien conocido. Si en algún momento se hace pauta pagada con esto, la voz de IA
  se declara.

## 3. El guion marcado

`guiones/peumo_voz.txt` tiene el texto listo para pegar, con los `<break>` ya calculados y la
tabla de en qué segundo cae cada línea sobre la imagen. Dos criterios al repartir el aire:

- **Las respiraciones largas van donde la imagen tiene algo que decir sola.** En Peumo son dos:
  0,8 s antes de que entre la lámina azul de la planta, y 1,1 s después de "Casa Peumo", para
  que el cierre de marca respire. No son relleno.
- **La línea del enganche cae sobre su plano.** En Peumo el enganche es el testero vidriado
  (ver `ENGANCHES.md`), así que "Su ventanal sube de piso a techo" arranca en t=9,6, justo con
  el rótulo *Doble altura*. Si la línea llega tarde, se corrige moviendo la pausa anterior, no
  acelerando la frase.

ElevenLabs **no garantiza la duración exacta** de un `<break>`: hay que generar, medir y
ajustar. De ahí el bucle del punto 4.

## 4. El bucle de trabajo

```bash
# 1. generar la toma en ElevenLabs y bajarla como voz.mp3
# 2. medirla contra el objetivo (105 = palabras del guion de Peumo)
tools/medir_voz.sh voz.mp3 105
```

```bash
# 3. montarla sobre el video (descarta el audio viejo, deja el máster a -14 LUFS)
tools/montar_voz.sh Reel_Casa_Peumo.mp4 voz.mp3 output/casa_peumo_reel_v2.mp4 cama.mp3
```

`medir_voz.sh` es la vara: si vuelve a marcar FUERA en silencio o en velocidad, la toma todavía
suena a locutor por mucho que la voz sea linda. Si marca ok en las tres y sigue sin gustar,
ahí sí el problema es la voz y hay que cambiarla.

`montar_voz.sh` agacha la cama bajo la voz con sidechain (`CAMA_DB=-19` por defecto) y deja el
total a -14 LUFS / -1,5 dBTP. `RETARDO=0.8` es el aire antes de la primera palabra.

## 5. Antes de publicar

- **Subtítulos quemados.** La mayoría lo ve en mudo; la voz acompaña, no carga el reel sola.
  Los tiempos de la tabla de `guiones/peumo_voz.txt` sirven de base para los subtítulos.
- Escucharlo **en celular y con el altavoz del teléfono**, no con audífonos: ahí se nota si la
  cama se come la voz.
- Revisar que "Peumo" y "neorigen punto ce ele" se entiendan a la primera.
