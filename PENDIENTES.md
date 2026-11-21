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
5. **Mañío** — playa urbanizada
6. **Roble** — nieve tipo centro de ski 🔧 *escena armada, esperando aprobación de fotos*
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

### Lago — para **Boldo** — hecho

Fotos aprobadas y **las cinco secciones**: s1 (240), s2 (192), s3 (240), s4 (264) y s5 (192), en
`output/casa_boldo_s*.mp4`, unidas en `output/casa_boldo_secuencia.mp4` (1128 cuadros, 47 s). Son
cinco segundos más que los 42 de la receta porque s4 muestra los dos pisos con sus recintos
rotulados, y la pausa sobre el 2do piso es más larga: es el único momento del recorrido donde ese
piso aparece.

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

La familia que era **más cara** cuando no había nada hecho. Peumo dejó resuelto todo lo de nieve
y Roble lo heredó entero sin tocarlo: material con subsurface, nieve de geometría sobre las
ramas, la capa modelada del techo, `diffuse_bounces` en 3 y la exposición baja.

**HDRI:** los dos usan **`horn-koppe_snow`** (`HDRI_SUN_U = 0.6000`, `SUN_ELEV = 28.2`), alpino y
con sol marcado. `snow_field_2` es nublado con huellas, por si alguna vez se quiere un día plano.

#### Roble (centro de ski) — escena armada, **a la espera de las fotos de aprobación**

Lo que se construyó, que es todo lo que **no** se heredaba de Peumo. El emplazamiento es lo
opuesto al bosque cerrado: ladera abierta, mucho más cielo y la nieve pisada llenando el cuadro.

- ✅ **La casa**, de `stl/Casa Roble + Ventana.stl` con `tools/extraer_roble_stl.py` →
  `assets/roble/casa.blend`. El STL traía 1.224 restos sueltos y el origen en x = −31,5, y = +21,4.
  El casco quedó en 1.553 caras y el resto son 26.665 piezas sueltas clasificadas por recinto.
  Ojo con el tiempo: el extractor tardó **una hora larga**, porque hay un `bpy.ops` por pieza
  densa y Blender revalúa la escena entera en cada uno.
- ✅ **Cotas que el STL no dice**, medidas al convertir: piso terminado en z = 0,55, segundo piso
  en 3,26, cumbrera en x = 6,89 a z = 6,55, testero vidriado de doble altura en y = 3,20 y acceso
  al fondo (el casco llega a y = 15,36; la terraza y el porch son piezas sueltas). Los faldones
  dan **32° y 27°**, que confirma los 32° de `ENGANCHES.md`.
- ✅ **Es de dos pisos**, como Boldo: living a doble altura, y arriba dormitorio-1, w.cl., baño y
  escritorio. Para el video eso obliga a la **pausa del corte por piso** de `RECETA.md` §1.
- ✅ **Los recintos van en dos bandas a lo largo**, no en franjas transversales: día a −X (living,
  comedor, cocina, lavadero) y noche a +X (dormitorio-2, los dos baños, dormitorio-3). Es la
  corrección que la lámina de Boldo dejó a la vista tarde, aplicada de entrada.
- ✅ **Ladera asimétrica.** Cae 17° por delante (la pista) y sube sólo 6° por detrás. No es
  gusto: con la misma pendiente a los dos lados, el talud de arriba subía 14 m a 20 m de la casa
  y el dron, que en s2 y s5 pasa a 15° de elevación, **se metía dentro del cerro**. Se midió
  antes de renderizar nada, con un chequeo numérico del terreno.
- ✅ **Pista pisada con el acordonado del pisanieve**, que es *la* firma del lugar: la franja
  rayada al lado de la nieve virgen. Va como atributo `pisado` sobre el terreno, con una onda de
  bandas cada 20 cm, y donde hay acordonado se **baja** el relieve natural en vez de sumarle uno
  (el pisanieve justamente borra los grumos).
- ✅ **Andarivel** de seis torres con los dos cables en catenaria y las sillas colgando, al canto
  de la pista. Estuvo primero 7,5 m más afuera y **quedaba fuera de cuadro en todas las tomas**:
  con el lente de 30 mm en vertical el cuadro abarca ±18° y caía a 30° del eje.
- ✅ **Balizas** al borde de la pista y huellas de esquí bajando de la terraza.
- ✅ **Cordillera en malla propia** (26 m de paso, hasta 1,7 km), con roca asomando donde la
  pendiente pasa de 40°. Sin la roca los cerros salían como **conos blancos lisos**, un merengue;
  con ella aparecen las aristas. Y con una sola octava de ruido tampoco alcanzaba.
- ✅ **Bosque ralo** y línea de árboles por **altura real** (ladera + cordillera): midiendo sólo
  la ladera local, los cerros del fondo salían forestados hasta la cumbre.
- ✅ **Bruma mucho más larga** que en Peumo: 1800 m contra 420. Es una ladera abierta, no un
  bosque; cortando a 400 m la cordillera quedaba plana y lavada.
- ✅ **Las alturas de las tomas fijas van sobre el terreno**, no en cota absoluta. En una ladera
  de 0,30 una cota fija deja la cámara enterrada arriba del talud y a tres metros del suelo abajo
  de la pista. Y hay una quinta toma de **contexto** con lente de 24, porque el emplazamiento es
  lo que hay que aprobar en esta casa y de cerca no se ve dónde está parada.

#### Primera revisión de las fotos (21 de noviembre) — los cuatro puntos, resueltos

La revisión marcó cuatro cosas sobre las dos tomas de la fachada de acceso (`izq_atras` y
`der_atras`) y dio el resto por bueno. Lo importante de esta vuelta no son los arreglos sino **lo
que se descubrió del STL**, porque las casas que faltan van a traer lo mismo:

- ⚠️ **El STL trae la puerta de acceso abierta 90° hacia adentro.** No es que falte: la hoja está,
  con sus 0,77 x 2,03, sus dos bisagras en y = 14,65, sus dos manillas y el picaporte, sólo que
  de canto a cualquier cámara de afuera. Lo que se ve es el vano de 73 cm con el interior oscuro
  detrás, y la revisión lo leyó exactamente así: "se ve muy angosta para ser puerta de acceso
  principal… no sé si es el ángulo o que se vea extraño porque no está la puerta". **Antes de dar
  por vacío un vano, hay que mirar si la hoja no está parada al lado**, en el plano de la jamba.
  La cierra `cerrar_puerta_acceso()` girando la hoja del modelo sobre su bisagra: las piezas están
  repartidas en tres objetos (`Roble_puerta`, `Roble_acero`, `Roble_maderaOsc`), así que se eligen
  por caja, y son 3.596 vértices.
- ⚠️ **La ventana del segundo piso tampoco estaba vacía**: trae su paño de 1,44 x 1,44 en y = 14,66
  con `Ro_Vidrio`. Se leía como un hueco porque detrás no hay luz y el paño va pelado. Lo que le
  faltaba era **marco, parteluz y alféizar**, y eso es lo único que agrega `build_acceso()`. Un
  primer intento le puso además un vidrio nuevo en el mismo plano: eso deja el paño del modelo
  metido dentro del nuevo y Cycles atraviesa cuatro caras de vidrio en vez de una. **No reponer
  vidrio sin medir antes si ya hay.**
- **La decisión sobre el ancho de la puerta fue no tocarlo.** Se preguntó en el cronograma, porque
  el modelo es el oficial, y la respuesta fue: "si es a base de los renders oficiales hay q
  dejarla así pero ponle puerta pa darle más prestancia". Así que el vano queda en sus 73 cm y lo
  que cambia es que la puerta se vea.
- **La terraza de entrada no puede ser de ancho completo.** El suelo de la casa termina en
  y = 14,97 a 16,06 según la franja de x, y sólo la lengüeta del acceso (x = 3,5 a 6,0) llega a
  16,81. Una terraza de lado a lado que arranque más afuera que eso deja aire a los dos costados
  y **se lee como una balsa suelta** — así salió el primer intento. Va en la franja de la lengüeta
  (x = 3,30 a 6,25) y arrancando encima de ella (y = 16,00), hasta y = 18,90.
- **El andarivel: la separación de las sillas la manda el encuadre.** Una torre sola, con su
  travesaño pero sin sillas alrededor, se lee como poste de luz, y eso fue lo que marcó la
  revisión ("sacar el andarivel que está justo atrás, porque se confunde con poste de luz; si
  quieres poner andarivel que sea un poco más lejos y se vean las sillas, sino sacarlo"). Se
  corrió a 14 m del borde de la pista —ojo: es el tercer movimiento, y el rango bueno es
  estrecho, está explicado en `andarivel_x()`— y las sillas pasaron de una cada 35 m a una cada
  17 m, que además es lo real en un cuadrimotor. Con 35 m **no entraba ninguna** en las tomas del
  acceso. Efecto lateral a mirar: a 14 m la línea ya no entra en la toma de `contexto`, salvo una
  silla cortada por el borde izquierdo del cuadro.

#### Segunda vuelta: el canto de los vanos (21 de noviembre)

Pedido del usuario: *"pinta el canto del interior de todas las ventanas negro, haz que las
ventanas se vean lo más real posible"*. El STL revestía cada hueco con el material interior que
tocara —muro, cielo, piso, todos madera clara—, así que sobre el revestimiento negro de los muros
largos cada ventana llevaba **un marco pálido** alrededor, y en el testero el vidrio quedaba metido
entre maderas del mismo tono que el interior.

Lo resuelve `forrar_vanos_ventanas()`: **27 ventanas exteriores**, 108 tiras negras. Dos cosas que
conviene no volver a descubrir:

- **No se repinta la malla, se construye el forro.** Repintar por criterio geométrico se probó y
  no sirve: `Roble_Casco` tiene 1.553 caras para toda la cáscara, así que la cara de la jamba y la
  del muro interior que llega hasta ella suelen ser la misma cara enorme. Medido, el "canto" que
  salía tenía hasta 1,3 m de profundidad media contra los 0,10 m que mide el muro: pintarlo deja
  manchones negros adentro, visibles por el vidrio.
- **Cuál de los 69 paños de vidrio es una ventana.** Dos filtros encadenados: que haya aire libre
  de un lado (rayo de 25 m que no choca con nada) **y** que haya muro alrededor del hueco (rayos
  desde afuera justo por fuera del borde). El primero solo no alcanza — deja pasar la mesa de
  vidrio de la terraza, que también tiene cielo encima. El espesor del muro sale de esos mismos
  rayos: 0,100 m parejo en los muros; en el testero da mezclado, porque es un muro cortina
  escalonado con paños en y = 3,15 y en 3,25, así que ahí se acota a 0,12.

**Dos cosas que salieron de revisar el primer intento** ("¿ahora aparecen unos tubos raros del
techo o no?"), y las dos se veían en el techo:

- 🐛 **Los paños del vértice del frontón son triángulos**, no rectángulos: siguen la pendiente del
  techo. El forro se armaba sobre el **rectángulo envolvente**, así que las tiras de arriba caían
  fuera del vidrio, donde no hay hueco sino losa de techo, y la atravesaban: en el render quedaba
  **un rectángulo negro dibujado sobre el faldón**. Ahora se mide la envolvente convexa del paño
  proyectado y se descartan los que no llenan su rectángulo (un rectángulo da 1,0 y un triángulo
  0,5; el corte está en 0,85). Quedan 24 ventanas forradas en vez de 27: los tres triángulos del
  frontón se quedan sin forro, que no se nota porque ahí el vano da contra el alero negro.
- 🪧 **Una baliza justo detrás de la cumbrera.** El borde de adentro de la pista pasa a entre 1,5
  y 4 m del muro (y = 0, 15 y 30), así que desde las tomas del lado contrario una baliza caía
  detrás del techo y asomaba por encima de la cumbrera: se leía como un tubo saliendo del tejado.
  `build_balizas()` ya no pone ninguna en la franja pegada a la casa, que además es lo correcto
  (al borde de una pista de verdad los jalones se retiran de los edificios). Pasan de 30 a 26 y la
  hilera no se nota cortada, porque la de enfrente sigue entera.

Queda **sin hacer, por si lo piden**: alféizar que sobresalga en las ventanas de los muros (hoy
sólo lo tiene la del acceso). En un emplazamiento de nieve juntaría nieve encima y sumaría
realismo, pero es agregarle una pieza al diseño oficial, así que no se hizo sin preguntar.

**Falta:**
- 🟡 **El visto bueno del usuario sobre las fotos de esta segunda vuelta.** Nada de video hasta
  entonces (`RECETA.md` §0).
- 🟡 Las cinco secciones del recorrido, con la **pausa del corte en cada piso** (dos pisos).
- 🟡 `tools/plano_roble.py` para s4, con la lámina `assets/roble/planta_sin_cotas.png` (ya está
  bajada, es PNG y trae las dos plantas, igual que la de Boldo) calibrada con
  `tools/calibrar_planta.py` sobre la cenital de s3.
- Verificar en las fotos que **las sombras salgan azules**, no grises.


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
| 6 | **Roble** | 🔧 escena armada (pista, andarivel, cordillera); falta el visto bueno de las fotos |
| 7 | **Maitén** | Reescribir la orilla rocosa y la espuma contra la piedra |
| 8 | **Coihue** | Conseguir trigo y resolver viento |
| 9 | **Ciprés** | 🔴 **Falta el STL**; lo demás es solo parametrizar Huingán |
