# Enganches por casa

El gancho narrativo de cada modelo: lo que la hace distinta y hay que contar en el video. Son
**borradores basados en la geometría real** del STL (medida con `tools/medir_stl.py`), no en
intuición — los números de abajo se pueden verificar. El usuario los aprueba o los corrige.

Sirven para decidir qué mira el dron: si el enganche es el ventanal, el recorrido tiene que
detenerse en el ventanal.

| Casa | Planta (m) | Alto | Techo | Lo que la distingue |
|---|---|---|---|---|
| Lingue | 4,40 × 8,50 | 6,15 | dos aguas | la más angosta |
| Huingán | 12,18 × 9,24 | — | dos aguas asimétrico | mariposa |
| Peumo | 9,49 × 13,04 | 6,54 | dos aguas 28° | testero vidriado doble altura |
| Boldo | 7,49 × 14,33 | 6,55 | dos aguas **38°** | la más empinada |
| Mañío | 16,02 × 11,15 | 5,07 | una agua **12°** | fachada vidriada corrida |
| Roble | 8,79 × 16,81 | 6,55 | dos aguas 32° | angosta y larga |
| Maitén | 16,27 × 11,84 | **8,10** | 20° | la más alta, dos volúmenes |
| Coihue | **19,81** × 13,76 | 5,15 | 16° | la más ancha |
| Ciprés | 12,18 × 7,24 | 5,27 | **una agua** 2,58→5,27 | sobre pilotes |

---

## Lingue — campo ✅

**Crece hacia arriba, no hacia los lados.** Con 4,40 m de ancho es la más angosta de las nueve,
pero llega a 6,15 m de alto: el dormitorio va en altillo sobre un living de doble altura con el
frente vidriado. Ocupa la mínima huella posible en el terreno — se posa en el campo sin
comérselo.

## Huingán — playa ✅

**Mariposa, pensada para dos parejas.** Las dos alas llevan los dormitorios a extremos opuestos
con las zonas comunes al medio: dos parejas comparten la casa sin perder privacidad. El techo a
dos aguas es asimétrico, con la cumbrera corrida hacia un lado (x = 8,9 de 12,18), así que cada
ala tiene su propia escala.

> Enganche aportado por el usuario.

## Peumo — nieve en el bosque

**El bosque nevado como cuadro.** El testero completo es ventanal de doble altura: desde el
living el bosque no es una vista por la ventana, ocupa la pared entera. Los 28° de pendiente
descargan la nieve solos, y el alero protege el vidrio de lo que cae del techo.

> Hay dos archivos de ventanal. El enganche funciona mejor con el **Ventanal Grande**, donde el
> vidrio sube hasta el frontón sin interrupciones.

## Boldo — lago

**Todo apunta al agua.** 7,49 m de ancho por 14,33 de fondo: la más angosta y alargada de todas.
El vidrio está concentrado en un solo testero, así que la casa funciona como un visor orientado
al lago — no se dispersa mirando en varias direcciones. Además tiene **la pendiente más empinada
de las nueve, 38°**, que es lo que descarga nieve y lluvia sin acumular.

## Mañío — playa urbanizada

**Se abre entera al frente.** No es una ventana al mar: es toda la fachada, vidriada y corrida a
lo largo, con la terraza siguiéndola de punta a punta. Y es la más baja del conjunto (5,07 m,
techo de una agua a 12°): se tiende en el terreno en vez de asomarse sobre los vecinos. En una
playa ya urbanizada, ese perfil bajo es privacidad.

## Roble — nieve tipo centro de ski

**La forma triangular impide que la nieve se acumule.** Los 32° de pendiente la descargan sola,
que es justo lo que se necesita a esa altura. Angosta (8,79 m) y larga (16,81), con el testero
vidriado mirando a la pista.

> Enganche aportado por el usuario. Dato para afinarlo: Boldo es aún más empinada (38°), así que
> si se quiere que lo triangular sea *la* marca de Roble, conviene apoyarlo también en el uso
> —casa de nieve de verdad— y no solo en el ángulo.

## Maitén — mar roca

**Se para frente al mar.** Es la más alta de las nueve (8,10 m), y esa altura es la que permite
mirar por encima de la roca en vez de quedar encajonada contra ella. Son **dos volúmenes**: el
principal con el frente de doble altura, y uno menor adosado con techo propio, que da un programa
aparte sin ensuciar la casa grande.

## Coihue — campo, que se note el trigo

**Horizontal como el campo.** Con 19,81 m de frente es la más ancha de todas, casi cuatro veces
el ancho de Lingue, y apenas 5,15 de alto con el techo a 16°. Acompaña la línea del trigal en vez
de interrumpirla: la casa se lee como una franja más del paisaje. La fachada vidriada corrida
convierte el trigo en el fondo permanente de la casa.

## Ciprés — playa del norte

**Una sola agua que se levanta hacia la vista.** El techo arranca en 2,58 m atrás y sube hasta
5,27 adelante: todo el volumen crece en la dirección en que se mira. Y está sobre pilotes a 0,5 m,
así que se posa sobre la arena sin aplanar el terreno.

---

## Cómo se usan

El enganche decide el recorrido, no al revés:

- Si es **el ventanal** (Peumo, Boldo, Roble), s2 tiene que frenar frente al testero y s5 cerrar
  mostrando la doble altura desde adentro hacia afuera.
- Si es **la horizontal** (Coihue, Mañío), el arco frontal conviene más abierto y más bajo, para
  que la casa cruce la pantalla a lo ancho en vez de quedar centrada y chica.
- Si es **la forma en planta** (Huingán), la cenital de s3 es el momento clave: ahí se lee la
  mariposa, y la transición a la planta de s4 la explica sola.
- Si es **la altura** (Maitén, Lingue), la aproximación de s1 debería terminar más abajo de lo
  habitual, mirando hacia arriba.
