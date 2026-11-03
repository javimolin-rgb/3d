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

## 2. Con qué se genera

Dos vías. **La primera es la que usamos**, y salió de un comentario de que probáramos
[Voicebox](https://github.com/jamiepine/voicebox).

### Voicebox — local, sin clave, sin plan (la que usamos)

Estudio de voz de código abierto (MIT) que corre en la máquina. Ocho motores de TTS; el que
sirve acá es **Qwen VoiceDesign 1.7B**, porque arma la voz desde una **descripción escrita**
—no hay que clonar a nadie ni elegir de un catálogo— y acepta una **instrucción de
interpretación** por generación, que es justo la perilla que falta en el problema del §1.

Ventajas sobre un servicio con API, para este caso concreto:

- **El silencio lo ponemos nosotros.** En vez de pedirle al modelo un `<break>` y esperar que
  lo respete, `tools/generar_voz_local.py` genera **frase por frase**, le recorta el aire que
  el modelo deja en las puntas, y pega los trozos con la pausa exacta del guion. La tabla de
  tiempos calza al cuadro en vez de aproximadamente.
- **Nadie clona a nadie.** La voz nace de un texto, así que no hay sample de una persona de
  por medio. (El repo igual trae `RESPONSIBLE_USE.md`: clonar a alguien pide permiso escrito,
  y el audio sintético se declara donde corresponda.)
- Gratis y sin cuota, así que iterar sale lo que cuesta el tiempo de CPU.

Lo que cuesta: **es lento sin GPU**. En este contenedor (4 núcleos, sin GPU) el modelo pesa
3,5 GB de descarga y ~8,5 GB de RAM cargado en float32.

> **Ojo con el motor que se elige.** `OmniVoice` también está en Voicebox y cubre más idiomas,
> pero sus pesos son **CC-BY-NC**: no se puede usar en un reel de marca. Qwen VoiceDesign y
> Kokoro (82M, Apache-2.0, dos voces masculinas en español) sí sirven comercialmente.

Montar el entorno en un contenedor nuevo (Voicebox exige **Python 3.12**, ni 3.11 ni 3.13):

```bash
git clone --depth 1 https://github.com/jamiepine/voicebox /home/user/jamiepine/voicebox
cd /home/user/jamiepine/voicebox && python3.12 -m venv .venv
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio
.venv/bin/pip install "numpy>=1.24,<2.0" soundfile librosa fastapi \
  "transformers>=4.36,<=4.57.6" accelerate "huggingface_hub>=0.20" "qwen-tts>=0.1.1"
apt-get install -y sox
```

No hace falta el `requirements.txt` completo ni levantar el servidor FastAPI: el script importa
la clase del motor directo. Tampoco hace falta la app de escritorio.

### ElevenLabs — la alternativa de pago

Si en algún momento se quiere comparar: la red llega desde el contenedor (comprobado), falta
`ELEVENLABS_API_KEY` en el entorno (se agrega en la configuración del entorno de la sesión →
Edit; nunca pegarla en el chat) y plan Starter como mínimo, porque el gratis no da derechos
comerciales. El guion son 888 caracteres, ~2.700 créditos por tres tomas. `tools/generar_voz.sh`
está escrito y probado hasta el punto de autenticación. Las 21 voces que trae la cuenta por
defecto son **todas de acento inglés** (verificado contra la API), así que habría que entrar a
la Voice Library.

## 3. La voz y la interpretación

Con VoiceDesign la voz no se elige de un catálogo: se escribe. Son dos textos distintos y
conviene no mezclarlos, porque el modelo los usa distinto:

- **`DESIGN`** — *quién habla*. Timbre, edad, acento, actitud. Es estable en todo el reel.
- **`INSTRUCT`** — *cómo lo dice en esta frase*. Velocidad, énfasis, cuánto baja al cerrar.
  Se le pega encima del `DESIGN`, no lo reemplaza.

Los dos van **en inglés** aunque la locución sea en español: el modelo obedece bastante mejor
la instrucción en inglés, y el idioma de salida lo fija el parámetro `--idioma es` aparte. Los
dos textos están arriba de `tools/generar_voz_local.py`, en `DESIGN` e `INSTRUCT_TAGS`.

El `DESIGN` que quedó es el mismo retrato que ya teníamos escrito para la voz de Neorigen:
hombre chileno de unos treinta, registro medio, cercano, contando algo que le entusiasma, sin
tono publicitario. Si una toma sale con acento raro o demasiado formal, lo que se toca es ese
texto, no las pausas — las pausas ya están resueltas por el guion.

**La frase que importa en el `INSTRUCT`.** Qwen VoiceDesign **no tiene parámetro de
velocidad** (sólo sampling: temperature, top_k, top_p), así que el ritmo se pide por escrito
— y no todas las formas de pedirlo funcionan igual. Medido sobre la misma frase de 9 palabras,
misma semilla:

| Instrucción / texto                                     | resultado  |
| ------------------------------------------------------- | ---------- |
| "normal conversational speed"                           | 273 ppm    |
| "Speak slowly and unhurried, taking your time"          | 239 ppm    |
| + **"with clear separation between words"**             | **155 ppm** |
| lo mismo, con comas agregadas al texto                  | 177 ppm    |
| lo mismo, con puntos suspensivos                        | 152 ppm    |

O sea: pedir "lento" casi no mueve la aguja, y **"clear separation between words" sí**. Por eso
esa frase está en las tres variantes de `INSTRUCT_TAGS` y conviene no sacarla al editarlas.
Agregar comas al texto no ayuda —incluso lo apuró— así que **el guion va con puntuación
normal**; las pausas son cosa del script, no del texto.

Como la generación es muestreada, la velocidad varía algo entre frases. `--ajustar-tempo`
estira la frase que se salga hasta su duración de diseño con el `atempo` de ffmpeg (WSOLA,
mejor que un vocoder de fase para voz), con tope en `--tempo-minimo 0.72` para que no se oiga
artificial. El script imprime las ppm de cada frase y marca FUERA las que se pasan.

**Qué hacer según lo que falle:**

| Lo que se escucha            | Qué tocar                                               |
| ---------------------------- | ------------------------------------------------------- |
| suena leído, parejo          | las pausas del guion — pero ya vienen calibradas         |
| una frase sale apurada       | revisar que su `INSTRUCT` traiga "clear separation…"; si no, `--ajustar-tempo` |
| acento que no es chileno     | `DESIGN`, siendo más específico con el acento            |
| una frase sale rara o cortada| borrar su `fNN.wav` y regenerar con otra `--semilla`     |
| cierra demasiado arriba      | la etiqueta `[más suave]` ya baja las dos últimas frases |

**Pronunciación a revisar en cada toma:** *Peumo* (PÉU-mo, diptongo) y el cierre, que va
escrito "neorigen punto ce ele" porque ".cl" se lee impredecible.

**Si hace falta algo mucho más rápido**, Voicebox trae también Kokoro 82M (350 MB, Apache-2.0,
rápido en CPU) con dos voces masculinas en español, `em_alex` y `em_santa`. Es un modelo mucho
más chico y se nota, pero sirve para probar el calce de tiempos sin esperar media hora.

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

Los `<break>` del archivo cumplen doble función: ElevenLabs los lee como etiqueta, y
`generar_voz_local.py` los usa como separador de frase y duración del silencio que inserta él
mismo. Por eso con Voicebox la tabla de tiempos se cumple exacta y con ElevenLabs hay que
generar, medir y ajustar — la duración de un `<break>` ahí no está garantizada.

## 5. El bucle de trabajo

```bash
VOICEBOX=/home/user/jamiepine/voicebox tools/generar_voz_local.py \
  guiones/peumo_voz.txt tomas/peumo_local.wav --semilla 7
```

Genera las 14 frases del guion una por una y las pega con las pausas del guion. Es
**reanudable**: cada frase queda en `tomas/peumo_local_frases/fNN.wav` y en una segunda pasada
no se regenera lo que ya está. Para rehacer sólo una frase que salió mal, borrar su `fNN.wav`
y volver a correr; con `--desde N --hasta M` se acota el tramo. `--semilla` fija la toma, así
que cambiarla es la forma de pedir una variante.

La descripción de la voz y las instrucciones de interpretación están arriba del script, en
`DESIGN` e `INSTRUCT_TAGS`, **en inglés a propósito**: el modelo entiende bastante mejor la
instrucción en inglés aunque después hable en español. Las etiquetas `[cálido]` y
`[más suave]` del guion eligen la instrucción de ahí en adelante.

Después, medir y montar:

```bash
tools/medir_voz.sh tomas/peumo_local.wav 107
```

```bash
tools/montar_voz.sh Reel_Casa_Peumo.mp4 tomas/peumo_local.wav output/casa_peumo_reel_v2.mp4 cama.mp3
```

`medir_voz.sh` es la vara: si marca FUERA en silencio o en velocidad, la toma todavía suena a
locutor por linda que sea la voz. Si marca ok en las tres y sigue sin gustar, ahí sí el
problema es el timbre y hay que tocar `DESIGN`.

`montar_voz.sh` nivela voz y cama **por separado** (`VOZ_LUFS=-16`, `CAMA_LUFS=-30`), agacha la
cama bajo la voz con sidechain y deja el total a -14 LUFS / -1,5 dBTP en dos pasadas.
`RETARDO=0.8` es el aire antes de la primera palabra.

Lo que decide si se entiende es **la diferencia entre esos dos números**, no la ganancia que uno
le ponga a ojo a la cama: la voz quiere quedar unos 12-14 dB sobre la cama. La primera vez puse
una ganancia fija de -8 dB y, como la voz salía a -20,2 LUFS y la cama del reel ya venía
masterizada a -14,1, la pausa sonaba igual de fuerte que el habla. Midiendo las dos y fijando el
objetivo de cada una, las pausas quedan 12-18 dB bajo la voz, que es lo que las hace existir.

La cama no lleva fade propio cuando sale del video: el reel ya termina bajando solo (-32 dB en
el último segundo) y agregarle otro fade apagaba la cola. El fade queda sólo para una cama que
venga de archivo, que se repite en bucle y hay que cerrar.

## 6. Resultado de la primera toma

`output/casa_peumo_reel_voz_v2.mp4`, generada con la semilla 7:

| Vara                       | Voz original | Voz nueva   |
| -------------------------- | ------------ | ----------- |
| silencio interno           | 8,1 % FUERA  | 19,9 % ok   |
| pausas / respiraciones reales | 12 / 5    | 21 / 14     |
| primera pausa              | t=13,4 s FUERA | t=3,2 s ok |
| velocidad en la frase      | 138 ppm FUERA | 169 ppm (apenas sobre 165) |

Lo que sigue sin estar fino: la velocidad queda justo arriba del rango, y cuatro frases salieron
a 193-246 ppm y hubo que estirarlas, dos de ellas al tope de 0,72. Esas son las candidatas a
regenerar con `--reintentos 3`, que tira otra semilla en vez de estirar. El LRA de la voz sola
es 3,8: expresiva del todo no es, y si eso molesta el camino es tocar `DESIGN`, no las pausas.

## 7. Antes de publicar

- **Subtítulos quemados.** La mayoría lo ve en mudo; la voz acompaña, no carga el reel sola.
  Los tiempos de la tabla de `guiones/peumo_voz.txt` sirven de base para los subtítulos.
- Escucharlo **en celular y con el altavoz del teléfono**, no con audífonos: ahí se nota si la
  cama se come la voz.
- Revisar que "Peumo" y "neorigen punto ce ele" se entiendan a la primera.
