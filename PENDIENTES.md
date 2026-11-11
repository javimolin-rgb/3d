# Qué falta para cada casa

Lo que hay que conseguir **antes** de poder empezar. Complemento de `RECETA.md`, que dice cómo
hacerlo; esto dice qué falta para poder hacerlo.

## Orden de trabajo

El acordado con el usuario. No es por costo: Peumo y Boldo son de las familias más caras y van
primero.

1. ~~Lingue~~ ✅ campo
2. ~~Huingán~~ ✅ playa
3. ~~Peumo~~ ✅ nieve en el bosque
4. ~~Boldo~~ ✅ lago (las cinco secciones, 42 s)
5. **Mañío** — playa urbanizada 🔨 *en curso: escena armada, fotos de aprobación entregadas*
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
| Mañío (cotas medidas al convertir) | piso 0,53 · aleros 2,90 y 2,84 · cumbrera 4,91 en x = 9,55 · ventanal y = 2,95 · acceso y = 9,35 | | |
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

### 3. La planta sin cotas — ya no bloquea a nadie

`assets/<nombre>/planta_sin_cotas.{pdf,png}`. Se calza sobre la cenital de s3.

**Deja de ser algo que pedirle al usuario**: el propio sitio publica la lámina "Planta y
Distribución" de cada modelo, y `python3 tools/get_planos_web.py` la baja a
`assets/<casa>/planta_sin_cotas.png` (1400 px de ancho, de sobra para mostrarla a 720x1280).
Están **ocho de las nueve**; Ciprés no tiene planta publicada, su página ni siquiera trae el
rótulo. Huingán y Peumo conservan el PDF del Drive, que es el dibujo calibrado en sus
`tools/plano_*.py`: la versión web es la misma planta con otra diagramación (vertical y con la
franja de marca, en vez de apaisada con los dos pisos rotulados), así que cambiarla obligaría a
recalibrar sin ganar nada.

Las nuevas son PNG, así que el `plano_<casa>.py` abre la imagen directo en vez de pasarla por
`pdftoppm`, que es la única línea que cambia respecto de `tools/plano_huingan.py`.

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

**Mañío (urbanizada) — en curso.** `casa_manio_3d.py` armado y las fotos de aprobación en
`output/manio_propuesta/` (izq, der, frente, cerca, izq_atras, calle). **Falta el visto bueno del
usuario antes de renderizar video.**

Lo que se construyó sobre la base de Huingán:

- ✅ **La casa**, de `stl/mañio.stl` con `tools/extraer_manio_stl.py` → `assets/manio/casa.blend`.
  El STL vino limpio (0 restos) y desplazado (esquina en x = 0,00, y = 0,25, z = −0,32). Es **la
  más grande de las nueve**: 16,02 × 11,15 (178 m² de huella contra los 113 de Huingán), un piso
  con tres dormitorios, escritorio y tres baños — nació como la *Huingán familiar*.
- ✅ **Corrección del techo**: no es de una agua a 12° como decía `ENGANCHES.md`, son **dos
  faldones de 12° y 18° con la cumbrera en x = 9,55**, justo sobre el muro que separa el living
  del dormitorio 2. Lo de "una agua" sale de que desde el mar sólo se ve el faldón de 12°.
- ✅ **Contexto urbano**: costanera pavimentada paralela a la orilla (calzada de asfalto con
  huellas de rueda, solera, veredas a ambos lados), alumbrado público cada 30 m, postes de
  hormigón con tendido aéreo cada 36 m, entrada de autos al porch con portón y pandereta, y dos
  filas de vecinos sobre la costanera más el balneario trepando el cerro (65 casas en total).
  Los vecinos de la primera fila son **más chicos que Mañío a propósito**, si no deja de leerse
  como la grande.
- ✅ **Muro de contención** de hormigón sobre la playa, con escalera pública a la arena y el
  sendero que la une con la terraza. Es lo que explica que el predio esté plano: `terrain_h`
  aterraza todo el loteo en vez de ondularlo.
- ✅ **Vegetación domesticada**: césped de bermuda (tarjetas de 6-10 caras, por eso aguanta
  55 matas/m²) con el terreno teñido de verde debajo, setos recortados en los deslindes, macizos
  de arbustos de jardín, jacarandás alineados en la vereda y árboles ornamentales de antejardín.
  El matorral costero silvestre queda sólo en los **sitios baldíos** y al pie del muro.
- ✅ **Recursos nuevos**: `tools/get_assets_urbano.sh` (alumbrado, jacarandá, island_tree,
  arbustos de jardín, maceteros, asfalto y hormigón de Poly Haven CC0).

Tres cosas que costaron y conviene no repetir en Ciprés:

1. **La playa tiene que ser ancha.** Con los 13 m de duna de Huingán, el encuadre adaptable planta
   la cámara justo sobre el muro de contención y el mar queda **detrás de ella** en todas las
   tomas. Quedó en 24 m de arena (`MURO_D`), y aun así las vistas que tienen que mostrar la
   relación con el agua se alejan a factor 2,6 (ver `VISTAS`).
2. **El ripple de arena hay que apagarlo donde hay césped.** La rampa de Huingán deja las ondas de
   viento encendidas para todo `shore_d > 10`, o sea tierra adentro también: el pasto de los
   antejardines salía con rayas paralelas y en la cenital el jardín se veía como pana.
3. **El liquen del muro se mide con un atributo, no con la z del mundo.** El muro corre a cota
   variable; con la z cruda la franja húmeda del pie cubría el muro entero y se veía una faja
   verde oscura cruzando la playa.

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

### Lago — para **Boldo** — hecho

Fotos aprobadas y **las cinco secciones**: s1 (240), s2 (192), s3 (240), s4 (144) y s5 (192), en
`output/casa_boldo_s*.mp4`, unidas en `output/casa_boldo_secuencia.mp4` (1008 cuadros, 42 s).

s4 se hizo con `tools/plano_boldo.py` y la lámina bajada del sitio
(`assets/boldo/planta_sin_cotas.png`). Dos cosas que hubo que ajustar y valen para las que vienen:
el engrosado de líneas baja a MinFilter(3), porque la lámina del sitio tiene 76,8 px/m contra los
374 px/m de un PDF a 300 dpi; y el recorte en metros deja fuera el rótulo "PRIMER PISO", que cae
en y 14,6..14,9 mientras el dibujo termina en el borde del porch, y = 14,2 (se midió contando
tinta por fila, no a ojo).

**Lo que se construyó:**

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

**Una diferencia que dejó a la vista la lámina**: la planta real reparte los recintos en dos
bandas **a lo largo** —estar, cocina y lavadero de un lado; dormitorio 1, baño y dormitorio 2 del
otro— mientras que `tools/extraer_boldo_stl.py` supuso tres franjas transversales. Eso sólo
cambia qué material recibe cada mueble del interior (que se ve a través del ventanal), no la
geometría ni nada del exterior, así que no se rehízo el render. Si alguna vez se vuelve a
extraer la casa, conviene corregir las zonas de `clasificar()` contra la lámina.

**Lo que se aprendió del render** (sirve para planificar las que vienen): el cuadro no cuesta lo
mismo a lo largo del recorrido. De lejos sobre el agua son ~29 cuadros/hora; a medida que el dron
se acerca baja a 21, porque entra más bosque y más reflejo; en la cenital sube a 38, porque desde
arriba casi no entra bosque. En total: s1 9,5 h, s2 8 h, s3 7 h y s5 6 h en cuatro núcleos. El
contenedor se reinició dos veces y las dos se retomó sin perder más de 40 minutos, borrando el
cuadro marcador a medio escribir y relanzando el mismo comando.

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
| — | todas | ✅ STL recibidos, salvo **Ciprés** 🔴; plantas de s4 bajadas del sitio, salvo Ciprés |
| 3 | **Peumo** | Material de nieve con SSS + nieve en las ramas |
| 4 | ~~Boldo~~ | ✅ hecho; sólo falta la lámina de planta para s4 |
| 5 | **Mañío** | Contexto urbano y vegetación ornamental |
| 6 | **Roble** | Hereda la nieve de Peumo; falta contexto de montaña |
| 7 | **Maitén** | Reescribir la orilla rocosa y la espuma contra la piedra |
| 8 | **Coihue** | Conseguir trigo y resolver viento |
| 9 | **Ciprés** | 🔴 **Falta el STL**; lo demás es solo parametrizar Huingán |
