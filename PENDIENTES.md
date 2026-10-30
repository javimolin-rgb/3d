# Qué falta para cada casa

Lo que hay que conseguir **antes** de poder empezar. Complemento de `RECETA.md`, que dice cómo
hacerlo; esto dice qué falta para poder hacerlo.

---

## Lo que hace falta para cualquier casa

Estas tres cosas las necesita **toda** casa nueva, sin excepción. Sin la primera no se empieza.

### 1. El STL del modelo — lo tiene que entregar el usuario 🔴

Exportado de SketchUp (ImageToStl sirve), en mm. Es el único insumo que **no se puede conseguir
solo**: todo lo demás se baja o se programa. Hoy solo existe el de Huingán, y ni siquiera: el STL
está en `.gitignore`, lo que sobrevivió es `assets/huingan/casa.blend` ya procesado.

Al recibirlo, va en `assets/<nombre>/modelo_<nombre>.stl` (no se commitea) y se convierte con
`tools/extraer_<nombre>_stl.py` en `assets/<nombre>/casa.blend` (eso sí se commitea).

### 2. Las cotas de la casa — se sacan del STL, pero conviene confirmarlas

Ancho, fondo, altura de piso terminado, dónde está la cumbrera, dónde el frente vidriado y dónde
el acceso. En Huingán están en el encabezado del script (12,18 m de ancho, cumbrera en x = 8,9,
piso en z = 0,23, terreno en z = −0,31). Son las que alimentan `CASA_BOX` y el encuadre
adaptable: si están mal, el dron encuadra mal toda la película.

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

### Lago — para **Boldo**

**Ya está:** el material de agua de Huingán como punto de partida.

**Falta:**
- 🔴 **HDRI de lago o montaña.** No hay ninguno. Hay que elegirlo en Poly Haven y agregarlo a
  `tools/get_assets_playa.sh`.
- 🟡 **Agua calma.** Bajar muchísimo escala y fuerza del modificador Ocean hasta dejarla casi
  espejo. Es sacar, no agregar.
- 🟡 **Orilla opuesta.** Es lo más importante y no existe en ninguna escena: cerros y bosque al
  otro lado, porque **el reflejo es la mitad de la imagen**. En el mar el horizonte queda vacío;
  en un lago, no.

### Nieve — para **Peumo** y **Roble**

La familia **más cara**: no hay nada hecho.

**Falta:**
- 🔴 **HDRI de nieve.** Ninguno. Para Peumo conviene uno nublado y difuso; para Roble, uno
  despejado de montaña. Agregarlos a `tools/get_assets_playa.sh`.
- 🔴 **Material de nieve con subsurface scattering.** Es lo que decide si se ve nieve o yeso
  blanco. No existe nada parecido en el repo.
- 🟡 **Nieve sobre la vegetación** (Peumo): no alcanza con el suelo blanco, tiene que haber carga
  de nieve en las ramas. Es trabajo de geometría, no solo de material.
- 🟡 **Árboles de bosque sureño nevado** (Peumo) y **contexto de montaña** (Roble: pistas,
  andariveles, huellas en la nieve).
- 🟡 **Ajuste de render**: subir `diffuse_bounces` de 2 a 3 por el albedo alto, y vigilar la
  exposición para que la nieve no se queme con AgX. Única excepción a los ajustes de `RECETA.md`.
- Verificar en las fotos de aprobación que **las sombras salgan azules**, no grises.

---

## Resumen de prioridad

| | Casa | Lo que bloquea |
|---|---|---|
| 🔴 | todas | **El STL** — sin eso no se empieza ninguna |
| 🟢 | **Ciprés** | Nada que descargar; es parametrizar Huingán |
| 🟢 | **Mañío** | Nada que descargar; cambiar contexto y vegetación |
| 🟡 | **Maitén** | Reescribir la orilla y la espuma |
| 🟡 | **Coihue** | Conseguir trigo y resolver viento |
| 🔴 | **Boldo** | Falta HDRI + construir orilla opuesta |
| 🔴 | **Peumo / Roble** | Falta HDRI + material de nieve desde cero |

Si da lo mismo el orden, conviene **Ciprés o Mañío primero**: heredan casi todo de Huingán, se
llega rápido a fotos de aprobación y sirven para validar que la receta se traspasa bien a otra
casa antes de meterse en las familias caras.
