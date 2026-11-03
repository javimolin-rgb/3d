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

## 2. Qué hace falta para generarla

Desde este contenedor la red **sí llega** a ElevenLabs (comprobado: `api.elevenlabs.io`
responde 200). Lo único que falta es la clave:

- **`ELEVENLABS_API_KEY`** en el entorno. Se agrega en la configuración del entorno de la
  sesión (menú del entorno en la barra de título → Edit), en *Network secrets* / variables de
  entorno. La toma una sesión nueva. No pegarla en el chat.
- **Plan Starter (US$6) como mínimo.** El plan gratis obliga a atribuir a ElevenLabs y no da
  derechos comerciales, así que no sirve para un reel de marca. Starter da 30.000 créditos al
  mes; el guion de Peumo son **888 caracteres**, o sea ~2.700 créditos por tres tomas. Sobra.
- **Un `voice_id`.** Lo entrega la Voice Library del sitio al elegir la voz. Las 21 voces que
  trae la cuenta por defecto son **todas de acento inglés** (lo verifiqué contra la API), así
  que hay que entrar a la Library sí o sí.

## 3. Voz y modelo (ElevenLabs)

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

## 4. El guion marcado

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

## 5. El bucle de trabajo

```bash
ELEVENLABS_API_KEY=... tools/generar_voz.sh guiones/peumo_voz.txt <voice_id> tomas/peumo 3
```

Manda sólo el cuerpo del guion (lo que está entre las dos líneas de guiones largos; el
encabezado y la tabla de tiempos no van al modelo), genera tres tomas y mide cada una.
Si el modelo `eleven_v3` no está habilitado en la cuenta vía API, reintentar con
`MODELO=eleven_multilingual_v2` — sale más estable y más plano, hay que compensar bajando
`STABILITY` a 0,30.

Para medir una toma suelta, o la que llegue hecha desde afuera:

```bash
tools/medir_voz.sh voz.mp3 107
```

Y para montar la elegida sobre el reel:

```bash
tools/montar_voz.sh Reel_Casa_Peumo.mp4 voz.mp3 output/casa_peumo_reel_v2.mp4 cama.mp3
```

`medir_voz.sh` es la vara: si vuelve a marcar FUERA en silencio o en velocidad, la toma todavía
suena a locutor por mucho que la voz sea linda. Si marca ok en las tres y sigue sin gustar,
ahí sí el problema es la voz y hay que cambiarla.

`montar_voz.sh` agacha la cama bajo la voz con sidechain (`CAMA_DB=-19` por defecto) y deja el
total a -14 LUFS / -1,5 dBTP. `RETARDO=0.8` es el aire antes de la primera palabra.

## 6. Antes de publicar

- **Subtítulos quemados.** La mayoría lo ve en mudo; la voz acompaña, no carga el reel sola.
  Los tiempos de la tabla de `guiones/peumo_voz.txt` sirven de base para los subtítulos.
- Escucharlo **en celular y con el altavoz del teléfono**, no con audífonos: ahí se nota si la
  cama se come la voz.
- Revisar que "Peumo" y "neorigen punto ce ele" se entiendan a la primera.
