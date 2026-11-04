# Qué falta para cada casa

Lo que hay que conseguir **antes** de poder empezar. Complemento de `RECETA.md`, que dice cómo
hacerlo; esto dice qué falta para poder hacerlo.

## Orden de trabajo

El acordado con el usuario. No es por costo: Peumo y Boldo son de las familias más caras y van
primero.

1. ~~Lingue~~ ✅ campo
2. ~~Huingán~~ ✅ playa
3. ~~Peumo~~ ✅ nieve en el bosque
4. **Boldo** — lago ← **en curso** (escena lista, fotos a la espera del visto bueno)
5. **Mañío** — playa urbanizada
6. **Roble** — nieve tipo centro de ski
7. **Maitén** — mar roca
8. **Coihue** — campo, que se note el trigo
9. **Ciprés** — playa del norte (más seco)

Conviene que Peumo deje resuelto el material de nieve y Boldo el agua calma: Roble y Maitén
después heredan de ellos, igual que Mañío y Ciprés heredan de Huingán.

---

## Hecha: Peumo (nieve en el bosque)

Las cinco secciones y la secuencia de 1008 cuadros / 42 s están en `output/`. El render se repartió
entre tres contenedores; lo que se aprendió de eso (cómo medir un empalme, por qué el md5 de un PNG
de Blender nunca coincide, que la vara tiene que ser local) está en `CLAUDE.md`.

### Lo que se decidió

- ✅ **Ventanal Grande**, elegido por el usuario. Es con el que funciona el enganche: el vidrio
  sube hasta el frontón sin interrupciones. `assets/peumo/casa.blend` sale de ese archivo.
- ✅ **La planta sin cotas en PDF**, en `assets/peumo/planta_sin_cotas.pdf` (las dos plantas en
  una lámina, bajada del Drive de Neorigen). La sección 4 se puede hacer.
- ✅ **Cotas que el STL no dice**, medidas al convertirlo: piso terminado en z = 0,60 sobre
  pilotes (terreno en z = 0), segundo piso en z = 3,00, cumbrera en x = 7,61 a z = 6,53,
  frente vidriado en y = 2,05 y acceso en y = 12,35. Los faldones dan 28° y 33°, que confirma
  los 28° de `ENGANCHES.md`.

### Lo que ya está listo

- ✅ **El STL**, medido y verificado (ver tabla arriba).
- ✅ **HDRI bajados y medidos.** `tools/get_assets_hdri.sh nieve` trae seis; para un bosque
  nevado los candidatos son:

  | HDRI | `HDRI_SUN_U` | `SUN_ELEV` | Carácter |
  |---|---|---|---|
  | `snowy_forest_path_01` | 0.6010 | 20.6 | **Nublado**, luz difusa pareja — el más fiel a un bosque nevado |
  | `snowy_forest` | 0.6836 | 38.4 | Sol suave alto, algo de dirección |
  | `snowy_hillside` | 0.6004 | 19.9 | Sol marcado y bajo, bosque abierto |
  | `snowy_field` | 0.5999 | 22.0 | Sol fuerte, campo abierto con huellas |

  Mi recomendación es **`snowy_forest_path_01`**: en un bosque cerrado la luz llega rebotada y
  difusa, y eso además perdona mucho más el ruido a 32 samples que un sol duro entre troncos.
  Si se quiere que entren rayos de sol entre los árboles, `snowy_hillside`.
- ✅ **`tools/medir_sol_hdri.py`** — mide `HDRI_SUN_U` y `SUN_ELEV` de cualquier HDRI, que antes
  era un paso manual. Avisa cuándo el cielo es nublado (sin sol direccional).
- ✅ **`tools/medir_stl.py`** — dimensiones reales, origen y restos sueltos de cada STL.

### Lo que hay que construir, en orden

1. ✅ **Material de nieve con subsurface scattering**, en `snow_mat()` de `casa_peumo_3d.py`:
   scattering corto y apenas azulado (radio 0,09 / 0,11 / 0,17), relieve de tres escalas de ruido
   y grano fino sobre la rugosidad, que es de donde sale el destello.
2. ✅ **Nieve sobre las ramas**, como geometría: un cono apoyado sobre cada faldón de la conífera
   y un medio cilindro sobre cada rama de los árboles desnudos. No cae pareja —se sostiene en
   parches—, si no se ve como una torta de bodas.
3. ✅ **Bosque sureño.** No salió de Sapling: son coníferas de faldones por capas y árboles
   desnudos, instanciados con nodos de geometría sobre las dos mallas de terreno. Mucho más
   baratas de renderizar, y a esa distancia con bruma rinden igual. La bruma entre los troncos
   es la del compositor, con la escala acortada (22 m, 190).
4. ✅ **Ajustes de render**: `diffuse_bounces` de 2 a 3 por el albedo alto de la nieve, y vigilar
   la exposición para que no se queme con AgX. Única excepción a los ajustes de `RECETA.md` §3.
5. ❌ **Sombras azules**: descartado. El usuario dijo que las sombras le daban lo mismo, así que
   no se usó como criterio.
6. ✅ **Sección 4 (la planta de arquitectura)** con `tools/plano_peumo.py`. Las constantes que
   calzan el dibujo sobre la casa salen de `tools/calibrar_planta.py` (nuevo), **no se heredan de
   otra casa**: la lámina de Peumo trae las dos plantas y los valores de Huingán caían entre medio.
   Y sin desvanecimiento diferencial, que sobre nieve deja un contorno encendido alrededor de la casa.

El HDRI elegido **no** es el nublado que se recomendaba acá. `snowy_forest_path_01` daba luz difusa
pareja y el usuario lo vio *"muy tétrico"*: la idea es que den ganas de ir a desconectarse a la
montaña. Quedó `horn-koppe_snow` (`HDRI_SUN_U = 0.6000`, `SUN_ELEV = 28.2`), con sol alto y fuerte.
Multiplicar el HDRI entero no sirve para ganar sombras, porque escala sol y cielo por igual y la
razón entre ambos —que es de donde salen— no cambia: hay que elegir un HDRI que ya traiga sol.

---

## Lo que hace falta para cualquier casa

Estas tres cosas las necesita **toda** casa nueva, sin excepción. Sin la primera no se empieza.

### 1. El STL del modelo — lo entrega el usuario ✅ (casi todos recibidos)

Exportados de SketchUp, en mm, en la carpeta `stl/` del repo. Medidos con
`python3 tools/medir_stl.py stl/*.stl`:

| Casa | Casa real (m) | Triángulos | Restos sueltos |
|---|---|---|---|
| Peumo | 9,49 × 13,04 × 6,54 | 1.291.109 | 12 |
| Peumo (Ventanal Grande) | 9,49 × 13,04 × 6,54 | 1.270.894 | 1.224 |
| Boldo | 7,49 × 14,33 × 6,55 | 1.529.068 | — |
| Mañío | 16,02 × 11,15 × 5,07 | 864.905 | — |
| Roble | 8,79 × 16,81 × 6,55 | 1.608.021 | 1.224, origen en x −31,5 y +21,4 |
| Maitén | 16,27 × 11,84 × 8,10 | 1.426.653 | 298 |
| Coihue | 19,81 × 13,76 × 5,15 | 1.767.804 | — |
| **Ciprés** | — | — | 🔴 **falta** |

Los dos archivos de **Peumo son la misma casa**: masa principal idéntica, difieren en 1.224
triángulos (el ventanal) y en dónde está posicionada en el espacio. No son dos plantas distintas.

Al convertir: `tools/extraer_<nombre>_stl.py` produce `assets/<nombre>/casa.blend` (eso sí se
commitea). **Limpiar los restos y recentrar el origen** antes de calcular las medidas; ver el
aviso en `RECETA.md` §2.

### 2. Las cotas de la casa — se sacan del STL, pero conviene confirmarlas

Ancho y fondo ya están medidos arriba. Falta lo que el STL no dice: altura de **piso terminado**,
dónde está la **cumbrera**, dónde el **frente vidriado** y dónde el **acceso**. En Huingán están
en el encabezado del script (12,18 m de ancho, cumbrera en x = 8,9, piso en z = 0,23, terreno en
z = −0,31). Alimentan `CASA_BOX` y el encuadre adaptable: si están mal, el dron encuadra mal toda
la película.

### 3. La planta sin cotas, en PDF — para la sección 4

`assets/<nombre>/planta_sin_cotas.pdf`. Se rasteriza a 300 dpi y se calza sobre la cenital.
Si no la hay, s4 no se puede hacer y el recorrido queda en cuatro secciones.

### Y por cada casa hay que escribir

- `casa_<nombre>_3d.py` — copiado de la familia que corresponda.
- `tools/extraer_<nombre>_stl.py` — copiado del de Huingán y ajustado a las zonas de esa planta.
- `tools/render_<nombre>.sh` — copia literal de `render_huingan.sh` cambiando el nombre.
- `tools/plano_<nombre>.py` — copiado del de Huingán, para s4.

---

## Lo que falta por familia

### Campo — para **Coihue**

**Ya está:** `casa_lingue_3d.py` resuelto, `assets/cielo/DaySkyHDRI065A_2K_HDR.exr`,
`assets/campo/pastos_botaniq.blend`, `vegetacion.py` (árboles con Sapling Tree Gen).

**Falta:**
- 🟡 **Modelo de trigo.** Es el pedido explícito ("que se note el trigo") y no lo tenemos. Hay
  que conseguir espigas maduras CC0 o generarlas por procedimiento. Los pastos Botaniq que hay
  son pasto, no trigal: no sirven como protagonista.
- 🟡 **Viento.** No hay animación de vegetación en ningún script. Un trigal quieto se ve muerto,
  así que hay que resolver el movimiento (desplazamiento con ruido 4D animado sobre las
  instancias, que es lo más barato de renderizar).
- Todo lo del bloque común (STL, cotas, planta).

### Playa — para **Mañío** y **Ciprés**

**Ya está:** `casa_huingan_3d.py` completo (duna, matorral, pasarela, mar con oleaje y espuma),
5 HDRI de costa en `assets/playa/ph/hdri/` y 16 modelos + 2 texturas de Poly Haven que baja
`tools/get_assets_playa.sh`.

Es la familia **más barata de arrancar**: casi todo se hereda.

**Falta para Mañío (urbanizada):**
- 🟡 Contexto urbano: casas vecinas más densas y cercanas, costanera o calle pavimentada, postes,
  muros de contención. Hoy `build_context()` hace casas sueltas y camino de tierra.
- 🟡 Vegetación ornamental (césped, palmeras o especies de jardín). La que hay es matorral
  silvestre.

**Falta para Ciprés (norte, seco):**
- 🟢 Nada que descargar: `flamingo_pan_2k.exr` ya está y es el más árido de los cinco. Hay que
  medirle el `HDRI_SUN_U` y la elevación del sol.
- 🟡 Ajustes de clima seco: menos bruma, sol más alto, sombras más duras, arena más clara, casi
  nada de verde. Es parametrizar lo que ya existe, no construir cosas nuevas.
- Ojo: **no partir de `archivo/cipres_v1/`**, que es campo al atardecer y está archivado.

### Costa rocosa — para **Maitén**

**Ya está:** todo el océano de Huingán. `cape_hill_2k.exr` y `white_cliff_top_2k.exr` calzan con
el carácter.

**Falta:**
- 🟡 **Geometría de costa rocosa.** Hoy la orilla es una parábola suave de arena (`shore_y`,
  `SHORE_K`). Hay que reemplazarla por roca: formaciones, cantos, poza de marea.
- 🟡 **Espuma contra la roca.** La espuma actual se calcula por profundidad del agua, que sirve
  para una playa en pendiente. Contra un farellón hay que concentrarla donde el agua golpea la
  piedra, y agregar salpicadura.
- 🟢 Rocas CC0: `namaqualand_boulder_02` y `coast_rocks_01` ya los baja el script de assets.

### Lago — para **Boldo** — resuelto en `casa_boldo_3d.py`

**Hecho** (falta sólo el visto bueno del usuario a las fotos, y la planta en PDF para s4):

- ✅ **La casa**, de `stl/Modelo Casa Boldo.stl` con `tools/extraer_boldo_stl.py` →
  `assets/boldo/casa.blend`. El STL vino limpio (0 restos) pero desplazado (esquina en
  x = −0,75, y = −0,05, z = −0,55).
- ✅ **Cotas que el STL no dice**, medidas al convertirlo: piso terminado en z = 0,55, segundo
  piso en 3,25, cumbrera en x = 5,60 a z = 6,55, testero vidriado en y = 3,10 y acceso en
  y = 12,40. Los dos faldones dan **32°** (no 38°, ver la corrección en `ENGANCHES.md`), con
  alero bajo en 3,00 y alto en 5,38: el techo es mucho más asimétrico que el de Huingán.
- ✅ **Agua calma**: el modificador Ocean casi apagado (escala 0,045, viento 3,2, *choppiness* 0,
  sin espuma) y el shader con tres bumps mínimos. De la espuma de Huingán queda sólo la línea
  mojada donde el agua lame la piedra.
- ✅ **El lago como lago y no como mar**: es una elipse de 1400 × 860 m (`lake_d`), con la orilla
  cercana a 14 m del testero y la opuesta a 860. Así el agua se cierra contra los cerros por los
  cuatro lados y **no hay línea de horizonte de agua**, que es lo que delataba el truco.
- ✅ **Ribera opuesta**: cerros que arrancan en el agua y suben a 150-200 m, con la cordillera
  detrás (hasta ~740 m, con nieve sobre los 540). Es la mitad de la imagen, porque se refleja.
- ✅ **Muelle de madera** que entra 9 m al agua, más la pasarela que baja el talud: es lo único
  vertical cerca de la cámara que el espejo duplica, y da la escala del agua.
- ✅ **Bosque con árboles de verdad** (`tools/get_assets_lago.sh`, 1,3 GB de Poly Haven CC0):
  fir, pine, island_tree y tree_small, en dos bandas de detalle, más sotobosque (helechos,
  nalquilla, matas, renuevos). **Esto no era opcional**: en un lago el bosque se ve dos veces
  —el real y el reflejado— y las copas de esferas desplazadas que bastaban de fondo en Huingán
  se notaban el doble. Con árboles reales la escena cambió por completo.
- ✅ **Bruma recalibrada**: la de Huingán estaba hecha para fundir el mar con el cielo y acá
  borraba la ribera de enfrente. Quedó en 0,40 con escala 1900 m (era 0,62 y 900).

**Falta:**
- 🔴 **`assets/boldo/planta_sin_cotas.pdf`** — sin ella no se puede hacer s4 y el recorrido queda
  en cuatro secciones. Es lo único que bloquea el video.
- 🟡 El visto bueno del usuario a las fotos de `output/boldo_propuesta/` (RECETA.md §0).

HDRI bajados y medidos con `tools/get_assets_hdri.sh lago` (se eligió **`lakeside`**):

| HDRI | `HDRI_SUN_U` | `SUN_ELEV` | Carácter |
|---|---|---|---|
| `lakeside` | 0.6001 | 31.8 | Sol claro de día, orilla con roca y árboles |
| `lakeside_sunrise` | 0.6003 | 5.3 | Sol muy bajo, contraluz sobre el agua |
| `montorfano` | 0.6035 | 17.5 | Nublado, lago alpino entre montañas |
| `shudu_lake` | 0.6101 | 9.7 | Nublado, montaña |

**Falta:**
- 🟡 **Agua calma.** Bajar muchísimo escala y fuerza del modificador Ocean hasta dejarla casi
  espejo. Es sacar, no agregar.
- 🟡 **Orilla opuesta.** Es lo más importante y no existe en ninguna escena: cerros y bosque al
  otro lado, porque **el reflejo es la mitad de la imagen**. En el mar el horizonte queda vacío;
  en un lago, no.

### Nieve — para **Peumo** y **Roble**

La familia **más cara**: no hay nada hecho.

**Ya está:** los HDRI, bajados y medidos con `tools/get_assets_hdri.sh nieve`. Para Peumo ver el
bloque de arriba; para **Roble** (ladera abierta, sol) el indicado es **`horn-koppe_snow`**
(`HDRI_SUN_U = 0.6000`, `SUN_ELEV = 28.2`), alpino y con sol marcado. `snow_field_2` es nublado
con huellas en la nieve, útil si se quiere un día plano.

**Falta:**
- 🔴 **Material de nieve con subsurface scattering.** Es lo que decide si se ve nieve o yeso
  blanco. No existe nada parecido en el repo. **Lo resuelve Peumo y Roble lo hereda.**
- 🟡 **Nieve sobre la vegetación** (Peumo): no alcanza con el suelo blanco, tiene que haber carga
  de nieve en las ramas. Es trabajo de geometría, no solo de material.
- 🟡 **Árboles de bosque sureño nevado** (Peumo) y **contexto de montaña** (Roble: pistas,
  andariveles, huellas en la nieve).
- 🟡 **Ajuste de render**: subir `diffuse_bounces` de 2 a 3 por el albedo alto, y vigilar la
  exposición para que la nieve no se queme con AgX. Única excepción a los ajustes de `RECETA.md`.
- Verificar en las fotos de aprobación que **las sombras salgan azules**, no grises.

---

## Resumen

Los HDRI y los STL ya **no bloquean a nadie**, salvo el de Ciprés. Lo que queda, en el orden de
trabajo acordado:

| # | Casa | Lo que bloquea |
|---|---|---|
| — | todas | ✅ STL recibidos, salvo **Ciprés** 🔴 |
| 3 | **Peumo** | Material de nieve con SSS + nieve en las ramas |
| 4 | **Boldo** | Agua calma + construir la orilla opuesta |
| 5 | **Mañío** | Contexto urbano y vegetación ornamental |
| 6 | **Roble** | Hereda la nieve de Peumo; falta contexto de montaña |
| 7 | **Maitén** | Reescribir la orilla rocosa y la espuma contra la piedra |
| 8 | **Coihue** | Conseguir trigo y resolver viento |
| 9 | **Ciprés** | 🔴 **Falta el STL**; lo demás es solo parametrizar Huingán |
