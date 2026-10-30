# Receta de modelos Neorigen

Guía para que cualquier sesión de Claude Code con acceso a este repositorio pueda atender
"hazme el modelo de Casa X" sin más instrucciones. La referencia de calidad es **Casa Huingán**
(`casa_huingan_3d.py`): si algo no está dicho acá, mirá cómo lo resuelve ese script.

---

## 0. Regla de oro: fotos antes de renderizar

**Nunca empezar a renderizar video apenas piden un modelo.** Primero se mandan **fotos fijas
desde varios ángulos** para afinar lo visual, y recién cuando el usuario las aprueba se lanza el
render largo.

Un modelo completo son ~17 h de CPU. Un juego de 4 fotos son ~10 minutos. Cualquier ajuste de
luz, materiales, vegetación, terreno o emplazamiento cuesta mil veces menos descubrirlo en las
fotos. Si se renderiza primero y el color del techo estaba mal, se pierde un día.

```bash
for v in izq der izq_atras der_atras; do
  /opt/bpyvenv/bin/python casa_<nombre>_3d.py -- --vista $v --still 1 \
    --out output/<nombre>_propuesta/$v.png --res 720x1280 --samples 32
done
```

Entregarlas con `SendUserFile` y **esperar respuesta**. Iterar sobre las fotos las veces que haga
falta: es barato. Solo con el visto bueno explícito se pasa al §2.

Antes de ese juego de 4, conviene un cuadro suelto a `--res 360x640 --samples 8` (~1 min) para
confirmar que la escena arma sin errores.

---

## 1. Qué se entrega

Salvo que pidan otra cosa, un modelo terminado son **cinco secciones de video vertical** que
forman una sola toma de dron continua, más la secuencia unida:

| Sección | Qué hace | Cuadros | Duración |
|---|---|---|---|
| s1 | Aproximación en espiral desde lejos | 240 | 10 s |
| s2 | Arco frontal alrededor de la casa | 192 | 8 s |
| s3 | Sube a cenital mientras el techo se corta | 240 | 10 s |
| s4 | De la cenital a la planta de arquitectura (post 2D, **no se renderiza**) | 144 | 6 s |
| s5 | Baja a la fachada de acceso y el camino | 192 | 8 s |
| **secuencia** | Las cinco unidas sin recodificar | **1008** | **42 s** |

720x1280, 24 fps, 32 samples. **Sin textos ni rótulos**: el usuario edita después.

Archivos: `output/casa_<nombre>_s1..s5.mp4` y `output/casa_<nombre>_secuencia.mp4`.
Se commitean al repo. Los PNG (`frames_<nombre>/`) van en `.gitignore` y se pierden con el
contenedor; los MP4 son el entregable duradero.

---

## 2. Flujo

1. **Modelo** → el usuario entrega un STL (exportado de SketchUp, en mm).
   `tools/extraer_<nombre>_stl.py` lo convierte en `assets/<nombre>/casa.blend` con materiales:
   el casco es una sola pieza y sus caras se pintan según normal y posición; el resto se separa
   en piezas y se clasifica por forma y zona de la planta. Las piezas densas se simplifican con
   Decimate (`MAX_FACES = 2500`). El STL original **no** va al repo; el `.blend` sí.
2. **Escena** → `casa_<nombre>_3d.py`, copiado del script del emplazamiento que corresponda
   (ver §5) y ajustado al terreno real.
3. **Fotos de aprobación** → el paso del §0. Cuatro ángulos, entregados y aprobados por el
   usuario. **No se sigue al 4 sin ese visto bueno.** Las fotos finales quedan en
   `output/<nombre>_propuesta/`.
4. **Secciones** → `PY=/opt/bpyvenv/bin/python setsid nohup tools/render_<nombre>.sh s1 &`
   (copiar `tools/render_huingan.sh`). Orden: s1 → s2 → s3 → s4 → s5.
5. **s4** → `tools/plano_<nombre>.py`, post 2D sobre el último cuadro de s3.
6. **MP4 por sección** → `LOOK=dia tools/armar_video.sh frames_<nombre>/<sec> output/casa_<nombre>_<sec>.mp4 24`
7. **Secuencia** → concatenar sin recodificar (todas salen h264 720x1280 yuv420p 24fps):
   ```bash
   for f in s1 s2 s3 s4 s5; do echo "file '$PWD/output/casa_<nombre>_$f.mp4'"; done > /tmp/c.txt
   ffmpeg -v error -y -f concat -safe 0 -i /tmp/c.txt -c copy output/casa_<nombre>_secuencia.mp4
   ```
   Verificar 1008 cuadros y 42 s con `ffprobe`. **Nunca recodificar**: perdería calidad sin motivo.

---

## 3. Receta de realismo

Lo que hace que Huingán no se vea CG. Respetar esto es más importante que subir samples.

### Luz: HDRI real + cielo físico mezclados

Un HDRI solo no alcanza, porque cerca del horizonte trae su propio paisaje (árboles, pérgolas)
que delata el truco. La solución de `build_world()`:

- El HDRI se rota para que **su** sol caiga en el azimut que queremos (`HDRI_SUN_U` es la columna
  del sol en la imagen, 0-1; de ahí sale la rotación hacia `SUN_AZ`).
- Un `ShaderNodeTexSky` (`MULTIPLE_SCATTERING`, `sun_disc = False`) con **el sol en el mismo
  lugar** (`SUN_ELEV`, `SUN_AZ`) cubre la franja baja; el HDRI queda solo arriba, para las nubes.
  La mezcla es un `MapRange` suave sobre el seno de la elevación (0.3 → 0.6).
- El cielo físico se evalúa **en espejo** (`z → |z|`): bajo el horizonte sería suelo oscuro, y los
  reflejos rasantes del agua lo dibujarían como una línea negra en el horizonte.
- Un `LightPath` hace que **cámara y reflejos** (`Is Camera Ray`, `Is Glossy Ray`) vean el HDRI
  limpio, mientras la iluminación difusa usa la mezcla. `SKY_GAIN` empata los brillos.

### Perspectiva aérea

Sin bruma por distancia todo se ve de cartón. `use_pass_mist = True`, `mist_settings` con
`start 60`, `depth 1400`, `falloff LINEAR`, y en el compositor una bruma azulada aplicada
**solo sobre el terreno lejano**. Es lo que separa los planos y da escala.

### Vegetación que respeta el lugar

El error típico es esparcir plantas uniformes. Acá `build_vegetation()` calcula en Python un
atributo `veg` por vértice del terreno, y los nodos de geometría lo usan como densidad:

- 0 en la playa, la pasarela, bajo la casa, sobre el sendero y sobre el camino de tierra
  (transiciones suaves, no bordes duros);
- modulado por dos octavas de ruido (escalas 7.0 y 2.5) para que haya claros y matas;
- cada instancia toma una **variante al azar** de una colección (`Pick Instance`), con rotación,
  inclinación y escala aleatorias.

Resultado: los senderos se leen porque la vegetación los deja libres, no porque estén dibujados.

### Contexto lejano

Casas vecinas, camino de tierra, arboledas y cerros con bosque. Sin eso la casa flota. Todo
pasado por la misma bruma.

### Materiales procedurales

Nada de texturas planas: `boards_mat` (tablas con veta y bump), `ribbed_metal` (techo nervado por
geometría), `glass_mat`, `sand_mat`, `water_mat` (modificador Ocean, oleaje en tres escalas,
espuma según profundidad). Vegetación y rocas de **Poly Haven (CC0)** y Botaniq.

### Render

```python
cy.samples = 32;  cy.use_adaptive_sampling = True;  cy.adaptive_threshold = 0.03
cy.max_bounces = 6;  cy.diffuse_bounces = 2;  cy.glossy_bounces = 2
cy.transmission_bounces = 4;  cy.transparent_max_bounces = 12
cy.caustics_reflective = cy.caustics_refractive = False;  cy.blur_glossy = 1.0
cy.use_denoising = True
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.use_motion_blur = True;  sc.render.motion_blur_shutter = 0.35
sc.render.use_overwrite = False;  sc.render.use_placeholder = True   # reanudable
sc.render.use_persistent_data = True
```

Los rebotes bajos y las cáusticas apagadas son deliberados: a 32 samples dan una imagen **más
limpia** que subirlos. El motion blur es lo que hace leer el movimiento como cámara real.

---

## 4. Recorrido de dron

Debe verse como **una sola toma**, con acercamientos y alejamientos que nunca corten la casa ni
la dejen chica. Cómo está resuelto:

- **`fit_distance(direc, target, lens, aspect, fit)`** — búsqueda binaria sobre las 8 esquinas de
  la caja de la casa; devuelve la distancia a la que ocupa `FIT = 0.74` del ancho de pantalla.
  De frente la casa muestra todo su largo y la cámara retrocede; en diagonal se acorta y se acerca.
- **Modo `"frente"`** — en el arco frontal no se usa `fit` cuadro a cuadro (el dron "respiraría"
  mientras rodea): se toma el **máximo** encuadre de todo el arco y se mantiene fijo.
- **`RUTA`** — claves `(cuadro global, azimut, elevación, distancia, altura de corte, parar)`
  interpoladas con **Hermite y tangentes Catmull-Rom**. `parar=True` pone tangente 0: el dron
  **llega detenido** a la cenital y al final, en vez de frenar de golpe.
- **Distancia en escala logarítmica** — un acercamiento lineal en metros se ve acelerado; en log
  se ve parejo.
- **Continuidad** — el cuadro 0 de la ruta es idéntico al último de s1, y s2/s3/s5 son tramos de
  la misma ruta (`INICIO` marca dónde corta cada archivo). Se renderiza por tramos solo para poder
  reanudar. El tiempo del oleaje también avanza entre secciones, así el mar no salta.
- Lente 30 mm, encuadres **a propósito abiertos** para poder reencuadrar y desenfocar en edición.

### Velocidad y edición

Acelerar en edición es exacto (se tiran cuadros); **ralentizar** por debajo de lo rendereado
obliga a interpolar y se ve mal. Si el usuario quiere margen para ir más lento, hay que
**renderizar más cuadros sobre la misma ruta, en todas las secciones** — si se alarga una sola,
el empalme cambia de velocidad de golpe. El motion blur queda horneado para la velocidad
rendereada: acelerar más de 2x deja la imagen algo nítida de más.

---

## 5. Emplazamientos

Cada casa tiene un emplazamiento fijo, que define HDRI, balance de blancos, exposición,
vegetación, terreno y contexto. **Partir copiando el script de la familia que corresponda** y
cambiar solo lo que el lugar pide; la receta del §3 no se toca.

| Casa | Emplazamiento | Familia | Script base | Estado |
|---|---|---|---|---|
| **Lingue** | Campo | Campo | `casa_lingue_3d.py` | ✅ hecho |
| **Huingán** | Playa | Playa | `casa_huingan_3d.py` | ✅ hecho |
| **Coihue** | Campo, *que se note el trigo* | Campo | `casa_lingue_3d.py` | pendiente |
| **Mañío** | Playa urbanizada | Playa | `casa_huingan_3d.py` | pendiente |
| **Ciprés** | Playa del norte (más seco) | Playa | `casa_huingan_3d.py` ⚠️ | pendiente |
| **Maitén** | Mar roca | Costa rocosa | `casa_huingan_3d.py` | pendiente |
| **Boldo** | Lago | Lago | `casa_huingan_3d.py` | pendiente |
| **Peumo** | Nieve en el bosque | Nieve | `casa_lingue_3d.py` | pendiente |
| **Roble** | Nieve tipo centro de ski | Nieve | `casa_lingue_3d.py` | pendiente |

> ⚠️ **Ciprés**: el script `casa_cipres_3d.py` que ya existe es una escena de **campo al
> atardecer** y no corresponde a su emplazamiento. Hay que rehacerla partiendo de Huingán, no de
> su propio script viejo. El antiguo queda como referencia de grado cálido nada más.

### HDRI disponibles

Ya descargados por `tools/get_assets_playa.sh` en `assets/playa/ph/hdri/` (Poly Haven, CC0):
`sundowner_overlook` (tarde de costa), `secluded_beach`, `cape_hill`, `white_cliff_top`,
`flamingo_pan` (seco, árido). En `assets/cielo/`: `DaySkyHDRI065A_2K_HDR.exr` (ambientCG, día).

**No hay HDRI de nieve ni de lago**: hay que agregarlos al script de descarga cuando se encare
esa familia. Al elegir uno, medir su `HDRI_SUN_U` (columna del sol, 0-1) y su elevación, porque
el cielo físico debe calzar con el sol del HDRI (§3).

### Qué cambia en cada familia

**Campo** — base ya resuelta en Lingue: potreros, álamos, cerros. WB 6500, exposición 0.0.
*Coihue* pide que **el trigo sea protagonista**: campo dorado maduro como masa principal, no como
fondo. Esparcirlo con la misma lógica de atributo del §3 (que respete camino y entorno de la
casa), con variación de altura y de tono, y **animarlo con viento** — un trigal quieto se ve
muerto. Las espigas en contraluz con el sol bajo son lo que da el efecto.

**Playa** — base resuelta en Huingán: duna, matorral costero, pasarela, mar con oleaje y espuma.
- *Mañío* (**urbanizada**): el mar y la arena se reutilizan tal cual; lo que cambia es el
  contexto y la vegetación. Más casas vecinas y más cerca, costanera o calle pavimentada en vez
  de camino de tierra, postes y muros de contención, vegetación **domesticada** (césped, palmeras
  o especies ornamentales) en vez de matorral silvestre. La duna deja de ser salvaje.
- *Ciprés* (**norte, seco**): mismo mar, clima opuesto. Casi nada de verde — arena y roca
  desnudas, alguna mata rala y aislada. Luz más dura y vertical: subir `SUN_ELEV`, bajar
  `aerosol_density` del cielo físico y **reducir la bruma** (`mist_settings.depth` más corto),
  porque el aire seco del norte deja ver lejos con nitidez. Sombras más marcadas y contrastadas.
  `flamingo_pan` es el HDRI más cercano a ese carácter árido. Arena más clara y amarilla.

**Costa rocosa** (*Maitén*, "mar roca") — lo más cercano a Huingán: se hereda el océano completo
(oleaje en tres escalas, espuma por profundidad). Lo que cambia es la orilla: en vez de la
parábola suave de arena, una costa de **roca**. La firma visual es el **oleaje reventando contra
la piedra**: concentrar la espuma donde el agua golpea la roca y agregar salpicadura. Paleta más
oscura y fría que Huingán, roca húmeda con brillo especular en la zona de rompiente.
`cape_hill` y `white_cliff_top` calzan con ese carácter.

**Lago** (*Boldo*) — se hereda el material de agua pero **no el oleaje de mar**: un lago está
casi quieto. Bajar muchísimo la escala y la fuerza del modificador Ocean, hasta dejar una
superficie casi espejo con ondulación mínima. Eso cambia el protagonista: en el mar manda la
espuma, en el lago mandan **los reflejos**. Hay que construir la **orilla opuesta** (cerros,
bosque) porque es lo que se ve reflejado, y el reflejo es la mitad de la imagen. Mantener la
bruma entre la ribera lejana y la cámara.

**Nieve** (*Peumo* y *Roble*) — familia nueva, sin base hecha. Tres cosas que deciden si la nieve
se ve real o de plástico:
1. **Subsurface scattering en el material de nieve.** Es lo más importante. Sin translucidez la
   nieve se lee como yeso blanco. Con SSS leve aparece el brillo interno que la delata como nieve.
2. **Sombras azules.** La nieve en sombra está iluminada solo por el cielo, así que vira a azul.
   Sale gratis si el cielo físico y el HDRI están bien calzados (§3), pero hay que verificarlo en
   las fotos de aprobación: si las sombras salen grises, algo está mal.
3. **Rebotes.** La nieve tiene albedo altísimo y rebota muchísima luz. Acá conviene subir
   `diffuse_bounces` de 2 a 3; es la única excepción a los ajustes del §3.
   Además, cuidado con la exposición: una escena casi toda blanca se quema fácil con AgX.
- *Peumo* (**bosque nevado**): nieve cargada sobre las ramas, no solo en el suelo. Bosque cerrado
  y oscuro que contrasta con el blanco, bruma entre los troncos, luz difusa de día nublado.
- *Roble* (**centro de ski**): lo opuesto — ladera abierta, amplia y luminosa, huellas y marcas
  en la nieve, y contexto de montaña a lo lejos (pistas, andariveles). Más cielo en cuadro.

### Marca

Azul Origen `#011E2F`, Niebla `#F1F4F3`, Verde Pino `#3C4A3E`, Madera `#A9764A` (sin negro ni
blanco puros). Fuentes Fraunces / Work Sans / IBM Plex Mono en `assets/fuentes/`, logo en
`assets/marca/`. Texto mínimo 22 px a 720x1280.

Marca Neorigen para cualquier gráfica: Azul Origen `#011E2F`, Niebla `#F1F4F3`, Verde Pino
`#3C4A3E`, Madera `#A9764A` (sin negro ni blanco puros). Fuentes Fraunces / Work Sans /
IBM Plex Mono en `assets/fuentes/`, logo en `assets/marca/`. Texto mínimo 22 px a 720x1280.

---

## 6. Operación de renders largos

Un modelo completo son **~17 h de CPU** en 4 núcleos (~100 s por cuadro). Leer también
"Renders de video (largos)" y "Entorno en un contenedor nuevo" en `CLAUDE.md`. Lo esencial:

- **Mantener un proceso vivo en segundo plano** mientras dure el render (`run_in_background`,
  `timeout` 7200000, un `while` que espera mientras viva Blender). Sin eso el contenedor se
  suspende y el render se corta. Tiene **tope duro de 2 h**: re-armarlo preventivamente pasados
  ~90 min, lanzando uno nuevo (el viejo muere solo).
- Lanzar Blender **separado de la sesión**: `setsid nohup ... &`.
- Programar además un `send_later` de respaldo. Cada despertar: revisar, relanzar si hace falta,
  re-armar el guardián y volver a programar.
- **Es reanudable.** Si se corta: borrar los marcadores vacíos
  (`find frames_<nombre>/<sec> -name "f_*.png" -size -10k -delete`) y relanzar el mismo comando.
  Sigue desde el último cuadro. Los cuadros en disco sobreviven al reinicio del contenedor.
- Para saber si Blender vive, **no** usar `pgrep -f` con el texto del comando de espera (se
  encuentra a sí mismo): `ps aux | grep "vista dron" | grep -v grep`, y mirar `uptime`
  (0 min = el contenedor se reinició, hay que relanzar).
- Avance legible en `PROGRESO_RENDER.txt` (ruta fija, se reescribe cada 60 s) y miniatura del
  último cuadro en `PROGRESO_ultimo_cuadro.jpg`. Son mejores para que el usuario mire el avance
  que la salida de un proceso en segundo plano, que muere cada 2 h.

---

## 7. Checklist antes de dar un modelo por terminado

- [ ] Fotos de varios ángulos entregadas y **aprobadas por el usuario antes** de renderizar video.
- [ ] Cuadro de prueba revisado antes de cada sección larga.
- [ ] Las 5 secciones completas, cada una con su MP4.
- [ ] Secuencia concatenada **sin recodificar**: 1008 cuadros, 42 s.
- [ ] Empalmes invisibles salvo el de s4, que es intencional.
- [ ] Sin textos ni rótulos.
- [ ] MP4 commiteados y empujados; los PNG y los `.zip` de entrega **no** van al repo.
- [ ] Si el usuario pidió un ZIP: `zip -j output/casa_<nombre>_videos.zip output/casa_<nombre>_*.mp4`
      y entregarlo con `SendUserFile` junto a la secuencia suelta.
