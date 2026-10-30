# Créditos de imágenes

## Imágenes propias del proyecto

| Archivo | Qué es | Autoría |
|---|---|---|
| `img/logo.svg`, `logo-negativo.svg`, `logo-isotipo.svg`, `favicon.svg` | Logo y sello | Equipo Titicaca Vivo (D-13) |
| `img/apple-touch-icon.png`, `favicon-32.png` | Íconos generados con `scripts/generar_iconos.py` | Equipo Titicaca Vivo |
| `img/comunidad-ilustracion.svg` | Ilustración que se ve mientras una comunidad no tiene foto | Equipo Titicaca Vivo |
| Mapa del lago (lo dibuja `servicios/mapa.py`) | Mapa esquemático | Equipo Titicaca Vivo. Coordenadas de Wikipedia (ver fase-3) |

## Fotos de las comunidades (Wikimedia Commons)

Descargadas el 20/10/2026 con la autorización del equipo: la miniatura de 960 px de cada archivo, no el original. Se convirtieron con `scripts/preparar_foto.py` (recorte central 8:5, 640×400, WebP de 40 KB o menos) y quedaron en `app/estaticos/img/comunidades/<slug>.webp`.

El crédito visible sale de la base (`comunidad.foto_credito`) y aparece debajo de cada foto.

**Revisión de personas:** antes de usarlas se miraron una por una. No hay rostros reconocibles: en Uros, Taquile y Llachón las personas están lejos y se ven pequeñas; en Luquina Chico son siluetas a contraluz; Amantaní y Ticonata son paisajes.

| Comunidad | Archivo en Commons | Licencia | Autor | WebP |
|---|---|---|---|---|
| Uros | [Floating Islands Puno.jpg](https://commons.wikimedia.org/wiki/File:Floating_Islands_Puno.jpg) | Dominio público | Entropy1963 | 38.3 KB |
| Taquile | [Lago Titicaca, Isla Taquile - panoramio.jpg](https://commons.wikimedia.org/wiki/File:Lago_Titicaca,_Isla_Taquile_-_panoramio.jpg) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) | Alonso Cárdenas | 32.7 KB |
| Amantaní | [Isla Amantani Lago Titicaca 1.JPG](https://commons.wikimedia.org/wiki/File:Isla_Amantani_Lago_Titicaca_1.JPG) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Pastor3571 | 35.6 KB |
| Llachón | [LLachón, región Puno.jpg](https://commons.wikimedia.org/wiki/File:LLach%C3%B3n,_regi%C3%B3n_Puno.jpg) | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | Hilda Maria FC | 34.2 KB |
| Luquina Chico | [On Lake Titicaca…our home stay village of Luquina (8443401653).jpg](https://commons.wikimedia.org/wiki/File:On_Lake_Titicaca%E2%80%A6our_home_stay_village_of_Luquina_(8443401653).jpg) | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) | Murray Foubister | 18.4 KB |
| Ticonata | [P8090171 Tikonata.JPG](https://commons.wikimedia.org/wiki/File:P8090171_Tikonata.JPG) | Dominio público | Titico (quien la subió a Commons) | 39.8 KB |

**Sobre las licencias:**

- **CC BY** y **CC BY-SA** exigen nombrar al autor y la licencia. Por eso el crédito se ve debajo de la foto, y aquí se enlaza la licencia.
- **CC BY-SA** ("compartir igual") también alcanza a nuestras versiones recortadas, que quedan bajo la misma licencia.
- **Dominio público** y **CC0** no lo exigen, pero igual damos el crédito.

## Fotos de fondo (marca de agua, D-109)

Son las **mismas 6 fotos** de arriba, agrandadas a 960×600 y suavizadas con `scripts/preparar_fondos.py`
(WebP de 20 KB o menos), en `app/estaticos/img/fondos/<slug>.webp`. Se muestran muy tenues detrás de cada
sección, solo en pantallas anchas.

- Cada página que las usa muestra al pie **«Foto de fondo: comunidad · autor · licencia»**: así se cumple
  el crédito que piden CC BY y CC BY-SA (los créditos están en `app/servicios/imagenes.py`).
- Las versiones suavizadas de las fotos **CC BY-SA** (Taquile y Luquina Chico) quedan bajo la misma licencia.

| Fondo | Viene de | Peso |
|---|---|---|
| `fondos/uros.webp` | Uros (dominio público) | 18.5 KB |
| `fondos/taquile.webp` | Taquile (CC BY-SA 3.0) | 15.0 KB |
| `fondos/amantani.webp` | Amantaní (CC BY 4.0) | 16.6 KB |
| `fondos/llachon.webp` | Llachón (CC0) | 14.8 KB |
| `fondos/luquina-chico.webp` | Luquina Chico (CC BY-SA 2.0) | 13.3 KB |
| `fondos/ticonata.webp` | Ticonata (dominio público) | 15.6 KB |
