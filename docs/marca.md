# Marca e interfaz de Titicaca Vivo

Este documento junta en un solo lugar la marca (nombre, logo, colores, letras y tono) y las reglas de
la interfaz. Las decisiones de detalle están en [decisiones.md](decisiones.md) (D-06, D-13, D-27,
D-106 y D-107).

---

## 1. La marca en una frase

> **Titicaca Vivo** · *Turismo lacustre y vivencial · Puno*
> «Vive el lago con las comunidades que lo habitan».

| | |
|---|---|
| **Nombre** (PR-02, aprobado en la F0) | *Titicaca* es el lugar. Una forma de explicar *Vivo*: turismo **vivencial** (dormir en casa de una familia), comunidades **vivas** (que reciben su parte con transparencia) e información **en vivo** (cupos y alertas del lago). |
| **De dónde viene** | Es la versión 2 de «Titicaca Reservas» (v1: Node, 5 tablas). El nombre nuevo dejó de hablar solo de reservar. |
| **Para quién** | La agencia Giant Trip (Puno), sus turistas (peruanos y extranjeros) y las familias anfitrionas de Uros, Taquile, Amantaní, Llachón, Luquina Chico y Ticonata. |
| **Promesa** | Reservar sin sorpresas: el lugar que ves libre es tuyo, el precio no cambia y, si el lago se pone bravo, te avisamos y reprogramas. |

---

## 2. El logo (D-13)

Es un **sello circular**, como el de un pase de abordar. Está hecho a mano en SVG (sin dependencias):

| Elemento | Qué representa | Color |
|---|---|---|
| El **Inti** (sol andino) saliendo sobre el lago | El amanecer en el Titicaca | Terracota |
| La **Cordillera Real** al fondo | El paisaje de Puno | Tinta |
| Una **balsa de totora** | Las islas flotantes de los Uros | Arena |
| Dos **olas** | El lago | Crema |
| Un **escalonado andino** | Los textiles de Taquile y la chakana | Terracota |
| «Titicaca» en serif negrita y «*Vivo*» en cursiva | El nombre | Ciruela y terracota |

Es neutral entre comunidades quechuas y aimaras.

| Archivo (`app/estaticos/img/`) | Qué es | Dónde se usa |
|---|---|---|
| `logo.svg` | Sello + nombre + lema, para fondos claros (1.7 KB) | Cabecera en pantallas anchas, portada |
| `logo-negativo.svg` | Lo mismo, para fondos ciruela o tinta | Boleto («pase de abordar») y pie |
| `logo-isotipo.svg` | Solo el sello (1.1 KB) | Cabecera en el celular, `/entrar`, páginas de error |
| `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` | El sello simplificado para 16–180 px | Pestaña del navegador e ícono del celular |
| PDF | El sello redibujado con reportlab | Boleto y manifiesto de zarpe |

**Reglas de uso:** el logo completo desde 300 px de ancho (en el celular, el sello de 40 px más el
nombre en HTML); un margen libre de ¼ de su altura; no se estira ni se cambia de color; **nunca va
dentro del QR** (empeora la lectura con cámaras de gama baja).

---

## 3. Colores: paleta «Esencia Andina» (D-06, D-27)

| Color | Hex | Idea que transmite* | Uso |
|---|---|---|---|
| **Ciruela** | `#572B44` | Los tejidos y polleras de la Candelaria | Títulos, enlaces, botones principales, cabecera del panel |
| **Terracota** | `#C27A52` | La tierra y el sol de la tarde | Detalles, bordes, foco del teclado, el sol del logo |
| **Crema** | `#FEF9F3` | La lana sin teñir | Fondo de todas las páginas |
| **Arena** | `#F5E9DC` | La totora seca | Tarjetas y bloques |
| **Tinta** | `#2A1220` | La noche en el lago | Texto |

\* La paleta se llama «Esencia Andina» desde la F0. La columna «Idea que transmite» es una
propuesta para explicarla en el video (29/10/2026): ajústenla si el equipo la pensó distinto.

Colores de estado, solo para avisos: error `#9B1C1C`, éxito `#1F5E3B`, amarillo `#8A6100`, texto
suave `#5E4654`.

**Contraste medido (WCAG):**

| Texto sobre fondo | Contraste | Nivel |
|---|---|---|
| Tinta sobre crema | 16.6 : 1 | AAA |
| Ciruela sobre crema (y crema sobre ciruela: botones) | 10.9 : 1 | AAA |
| Ciruela sobre arena (tarjetas) | 9.6 : 1 | AAA |
| Terracota sobre crema | 3.2 : 1 | Solo texto grande, íconos y bordes: **nunca** en botones con texto chico |

Por eso los botones son ciruela y la terracota queda para los detalles.

---

## 4. Letras

| Para | Fuente | Por qué |
|---|---|---|
| Títulos | Georgia (serif) | Cálida y clásica, como un cartel de muelle; viene con Windows, Mac y celulares |
| Texto | La del sistema (`system-ui`, Segoe UI, Roboto…) | Se lee bien en cualquier pantalla y no se descarga nada |

No se usan fuentes de internet: la página carga rápido con poca señal y funciona sin CDN.

---

## 5. Tono de voz

- **Tú** y frases cortas: «Elige tu salida», «Guarda tu código».
- Cada error dice **qué hacer**: «Un DNI tiene 8 dígitos.», «Solo quedan 3 lugares en esta salida.»
- Al turista en **español o inglés** (botón «English» arriba); el panel, en español.
- Nunca se culpa al turista: «La suspensión no es tu culpa: al reprogramar se mantienen tu código,
  tus pagos y tus precios.»
- Al personal se le habla de su trabajo: «Tu trabajo de hoy», «¿Cómo funciona esta página?».

---

## 6. La interfaz

| Principio | Cómo se cumple | Prueba |
|---|---|---|
| **Primero el celular** | El CSS parte de la pantalla chica y agrega columnas en las anchas. El guía y el capitán trabajan en el muelle con el celular. | Capturas de celular en `docs/evidencias/` |
| **Botones para dedos (y guantes)** | Todo botón mide 44 px de alto como mínimo. | Revisión a mano (F7) |
| **Poca señal** | Cada página pesa 100 KB o menos sin fotos; CSS propio, sin frameworks ni CDN; fotos WebP de 40 KB con carga diferida. | `test_paginas_del_turista_pesan_100_kb_o_menos` |
| **Accesible** | Etiqueta en cada campo, errores junto al campo y en un resumen arriba, foco visible con el teclado, un solo `h1`, «Saltar al contenido». | `tests/test_accesibilidad.py` (56 páginas) |
| **Sin mareos** | Las olas y los movimientos al pasar el mouse se apagan si el sistema pide «reducir movimiento». | CSS `prefers-reduced-motion` |
| **Datos de verdad** | Ninguna pantalla tiene datos escritos a mano: todo sale de la base. | `tests/test_plata.py` |
| **Se explica sola** | Portada con «Cómo reservar» en 3 pasos; en el panel, «Tu trabajo de hoy» según el rol y «¿Cómo funciona esta página?» en cada pantalla. | `test_cada_rol_ve_su_trabajo_de_hoy`, `test_cada_pagina_del_panel_explica_como_funciona` |
| **Dos idiomas** | Español e inglés para el turista: páginas, formularios, errores, fechas y boleto PDF. | `test_cada_texto_del_turista_tiene_su_traduccion` |
| **Una foto del lago en cada sección** (D-109) | Marca de agua muy tenue (opacidad 0,14) detrás de cada sección, con el crédito al pie: Uros en salidas, Taquile en comunidades, Amantaní en reservas y hospedajes, Llachón en el acceso, Luquina Chico en pagos, Ticonata en alertas y administración. Solo en pantallas anchas: en el celular ni se descarga. | `test_cada_seccion_tiene_su_foto_de_fondo_con_su_credito` |
| **Cada rol, lo suyo** (D-113) | En Mi cuenta y en Usuarios, cada rol dice lo que **hace** (verde) y lo que **no hace** (rojo). | `test_mi_cuenta_muestra_los_datos_y_lo_que_hace_cada_rol` |

**Pantallas que muestran la marca:**

| Pantalla | Qué se ve |
|---|---|
| `/` (portada) | Amanecer sobre el lago con 2 capas de olas animadas, «Cómo reservar», mapa SVG propio y fotos de las comunidades |
| `/salidas` | Selector de días, barras de cupos (verde, amarillo, rojo) y estados con color |
| `/reservas/<código>/boleto` | El **pase de abordar**: logo en negativo, código grande, QR y pasajeros con el documento oculto |
| Boleto y manifiesto en PDF | El sello redibujado, los mismos colores |
| `/panel` | La barra ciruela del panel y «Tu trabajo de hoy» con pasos numerados |
| `/entrar` y `/recuperar` | Pantalla dividida: a la izquierda la foto de Llachón con un velo ciruela, el logo en negativo y para qué sirve el panel; a la derecha el formulario |
| `/no-existe` | Error 404 propio, con el sello y en el idioma del turista |

---

## 7. Cómo mostrarlo en 3 minutos (video)

1. Portada en pantalla ancha: el logo, el lema y las olas. Explicar el sello (sección 2).
2. Abrir las herramientas del navegador (F12 → modo celular): la misma portada en un celular.
3. Pulsar «English»: la página cambia de idioma; volver a «Español».
4. Abrir un boleto: el pase de abordar con el logo en negativo y el QR.
5. Entrar como operador: «Tu trabajo de hoy» y una guía «¿Cómo funciona esta página?» abierta.
6. Con la tecla Tab, recorrer un formulario: el foco terracota marca dónde está el cursor.
