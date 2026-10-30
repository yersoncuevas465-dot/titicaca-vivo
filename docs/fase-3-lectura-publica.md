# Fase 3 · Lectura pública (nivel Plata)

> Estado: entregada el 20/10/2026. Espera el "ok" del equipo para pasar a la F4.
> Queda una decisión del equipo: autorizar la descarga de las fotos (sección 5).

## 1. Qué hicimos

- **6 páginas públicas** que leen todo de la base:

  | Página | Muestra |
  |---|---|
  | `/` | Alertas vigentes, salidas de hoy, mapa, rutas con "desde S/" y comunidades. |
  | `/salidas?fecha=&ruta=` | Filtro por fecha y por ruta, con los próximos 7 días y cuántas salidas tiene cada uno. |
  | `/salidas/<id>` | Estado, alertas que la afectan, cupos, lancha, recorrido en orden y **precios por tipo de pasajero con la regla RN-04** (tarifa vigente × temporada). |
  | `/comunidades` | Listado con el mapa. |
  | `/comunidades/<slug>` | Idioma, señal, artesanía, próximas salidas, rutas y **familias anfitrionas sin datos personales**. |
  | `/alertas` | Vigentes, próximas y de los últimos 30 días. |

- **Mapa del lago en SVG propio**, sin mapas externos ni JavaScript:
  - las comunidades se dibujan con su latitud y longitud, y las rutas con sus paradas en orden, todo leído de la base;
  - la orilla es un dibujo esquemático;
  - las rutas que salen al lago abierto pasan por la boca de la bahía, para no cruzar las penínsulas.
- **RN-11 (marcar)**: una salida queda marcada si una alerta naranja o roja se cruza con su horario y es de todo el lago o de una comunidad de su ruta. Suspender llega en la F6.
- **RN-08**: estado público con su insignia, y barra de cupos en amarillo con 3 libres o menos y en rojo si está llena.
- **Columnas nuevas** `comunidad.latitud` y `comunidad.longitud` (D-38), con CHECK: las dos o ninguna, y dentro de rango.
- **Fotos**:
  - mecanismo listo: `<slug>.webp` con carga diferida y el crédito leído de `comunidad.foto_credito`;
  - mientras no haya fotos se ve una **ilustración propia**;
  - el script `scripts/preparar_foto.py` deja cada foto en 640×400 y 40 KB o menos.
- **Sin N+1**: cada página hace un número fijo de consultas, y una prueba lo comprueba.

| Página | Consultas |
|---|---|
| Portada | 5 |
| Listado de salidas | 3 |
| Detalle de salida | 4 |
| Comunidades | 2 |
| Ficha de comunidad | 4 |
| Alertas | 1 |

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `database/01_esquema.sql`, `03_datos.sql` | `latitud` y `longitud` en `comunidad`, con las coordenadas reales (ver la sección 4). |
| `app/modelos/salida.py`, `ruta.py`, `tarifa.py`, `comunidad.py`, `alerta.py` | El SQL público (el panel ahora reutiliza `alerta.vigentes()`). |
| `app/servicios/mapa.py`, `imagenes.py`, `formato.py` | Proyección del mapa, fotos y textos (idioma, señal, servicios, duración, fechas largas). |
| `app/rutas/publico.py` | Las 6 páginas. |
| `app/plantillas/publico/*`, `macros_publico.html`, `macros.html`, `base.html` | Plantillas, menú público y macros reutilizables. |
| `app/estaticos/css/estilos.css`, `img/comunidad-ilustracion.svg` | Estilos e ilustración propia. |
| `scripts/preparar_foto.py` | Convierte una foto a WebP de 40 KB o menos. |
| `tests/test_rutas_publicas.py`, `test_plata.py`, `test_mapa_precios_fotos.py` | 54 pruebas nuevas. |
| `docs/…` | Este archivo, `desafio-niveles.md` (Plata), `creditos-imagenes.md`, `modelo-datos.md`, `decisiones.md`, `trazabilidad.md`. |

## 3. Comandos para probarlo

```powershell
flask bd reiniciar --si          # la base cambió (columnas de ubicación): hay que volver a crearla
flask run                        # http://127.0.0.1:5000
pytest -v                        # 219 pruebas
ruff check .
```

Recorrido: abrir `/`, entrar a una salida de hoy, ir a `/salidas` y elegir "mañana": la salida 9 aparece suspendida y marcada por la alerta. Luego abrir `/comunidades/amantani` y `/alertas`.

## 4. Evidencia (20/10/2026)

- `pytest -v`: **219 passed in 28 s** → [evidencias/f3-pytest.txt](evidencias/f3-pytest.txt).
- `ruff check .`: *All checks passed!*
- **Nivel Plata** (detalle en [desafio-niveles.md](desafio-niveles.md#plata)):
  - si se cambia un dato en la base, la página lo muestra al recargar (5 casos);
  - ninguna plantilla tiene escrito un dato de la base;
  - sin base, ninguna página pública se puede mostrar.
- Peso del HTML: entre 5.1 KB (detalle) y 15.8 KB (portada con el mapa). Con su CSS y sus imágenes, todas pesan menos de 100 KB, y una prueba lo comprueba.
- Capturas:
  - [portada con el mapa](evidencias/f3-portada-mapa-y-comunidades.jpg);
  - [salida suspendida en el celular](evidencias/f3-salida-suspendida-celular.jpg);
  - [ficha de Amantaní](evidencias/f3-comunidad-amantani-celular.jpg);
  - [filtro con fecha inválida (422)](evidencias/f3-salidas-filtro-422-celular.jpg).
- La consola del navegador no mostró ninguna violación de la CSP.
- **Coordenadas**:
  - Amantaní (−15.6642, −69.7100) y Taquile (−15.7772, −69.6842): Wikipedia en español;
  - Ticonata (−15.6485, −69.7877): copia de Wikipedia en inglés;
  - Uros: cerca de Chullune (−15.819, −69.991);
  - **Llachón y Luquina Chico: aproximadas, por confirmar**. No encontramos coordenadas publicadas; las ubicamos dentro de las zonas confirmadas (el área de Capachica y la punta de la península de Chucuito).

## 5. Pendientes y decisión del equipo

- **Fotos**: necesitamos tu permiso para descargar 6 fotos de Wikimedia Commons (lista en [creditos-imagenes.md](creditos-imagenes.md)). Bajaríamos las miniaturas de 800 px, unos 100 a 200 KB cada una, y las convertiríamos con `preparar_foto.py`. Hasta entonces se ve la ilustración propia.
- **Confirmar en OpenStreetMap** las coordenadas de Llachón y Luquina Chico.
- **Inglés** en las páginas públicas: está planificado para la F6 (diccionario `servicios/textos.py`). En la F3 los textos están en español.
- **Botón "Reservar"**: aparece solo cuando exista la ruta de reserva (F4). Mientras tanto, la página dice que la reserva en línea estará disponible muy pronto.

---

## Para explicar al docente

### 1. Salidas de un día y si una alerta las afecta (EXISTS con subconsulta)

```sql
-- Devuelve las salidas (no canceladas) de un día, con cupos y estado público (vista),
-- y si alguna alerta naranja o roja se cruza con su horario y toca su ruta (RN-11).
SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.cupo, v.ocupados, v.libres,
       v.estado_publico,
       EXISTS (SELECT 1
               FROM alerta_lago a
               WHERE a.nivel IN ('naranja','rojo')
                 AND a.vigente_desde < v.fecha_hora_retorno
                 AND a.vigente_hasta > v.fecha_hora_zarpe
                 AND (a.comunidad_id IS NULL
                      OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp
                                            WHERE rp.ruta_id = v.ruta_id))
       ) AS afectada_por_alerta
FROM v_disponibilidad_salida v
WHERE v.fecha_hora_zarpe >= %s
  AND v.fecha_hora_zarpe <  %s + INTERVAL 1 DAY
  AND v.estado <> 'cancelada'
  AND (%s IS NULL OR v.ruta_codigo = %s)
ORDER BY v.fecha_hora_zarpe, v.ruta_nombre;
```

- **FROM la vista**: ya trae los ocupados, los libres y el estado público (F1), así que no hay que volver a calcularlos.
- **EXISTS (...)** responde sí (1) o no (0): "¿existe al menos una alerta que cumpla esto?". Se evalúa **para cada salida**, porque la subconsulta usa `v.fecha_hora_retorno` y `v.ruta_id` de la fila de afuera (subconsulta *correlacionada*).
- **Dos horarios se cruzan** si la alerta empieza antes de que vuelva la lancha **y** termina después de que zarpe.
- **`a.comunidad_id IN (SELECT ... FROM ruta_parada ...)`**: la alerta toca alguna comunidad por la que pasa esa ruta. `comunidad_id IS NULL` significa que es para todo el lago.
- **`(%s IS NULL OR v.ruta_codigo = %s)`**: el filtro de ruta es opcional (ver la F2).
- Ejemplo de mañana: las salidas 10 (Uros y Taquile, 0), 9 (Uros, Amantaní y Taquile, **1**, por la alerta naranja de Amantaní) y 11 (Uros, 0).

### 2. Precio por tipo de pasajero (RN-04): la tarifa vigente más reciente y la temporada

```sql
SELECT tp.codigo, tp.nombre, t.precio_base,
       COALESCE((SELECT MAX(te.recargo_porcentaje) FROM temporada te
                 WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin),
                0) AS recargo_porcentaje
FROM salida s
JOIN tarifa t         ON t.ruta_id = s.ruta_id
JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id
WHERE s.id = %s
  AND t.vigente_desde = (SELECT MAX(t2.vigente_desde) FROM tarifa t2
                         WHERE t2.ruta_id = t.ruta_id
                           AND t2.tipo_pasajero_id = t.tipo_pasajero_id
                           AND t2.vigente_desde <= DATE(s.fecha_hora_zarpe)
                           AND (t2.vigente_hasta IS NULL
                                OR t2.vigente_hasta >= DATE(s.fecha_hora_zarpe)));
```

- Una ruta puede tener **varias tarifas** para el mismo tipo de pasajero (la de 2025 y la de 2026). La subconsulta con **MAX(vigente_desde)** elige, entre las que valen en la fecha de la salida, la que empezó más recientemente.
- **El recargo** sale de otra subconsulta: la temporada cuyo rango (`BETWEEN`) contiene la fecha. Si no hay ninguna, `MAX` devuelve NULL y **COALESCE** lo convierte en 0. Por eso no hace falta una FK entre `temporada` y `salida` (F0).
- **La multiplicación la hace Python** (`tarifa.calcular_precio`, con `Decimal` y redondeo al céntimo). La regla queda en el modelo y la F4 la reutiliza al reservar.
- Ejemplo de la salida 10 (Uros y Taquile, sin temporada): adulto nacional S/ 80.00, extranjero S/ 120.00, estudiante S/ 60.00, niño S/ 40.00 y adulto mayor S/ 60.00. En una prueba se agrega una temporada del 20 % y el adulto nacional pasa a S/ 96.00.

### 3. Comunidades con sus conteos: LEFT JOIN a subconsultas ya agrupadas (sin N+1)

```sql
SELECT c.nombre, c.slug, c.idioma_originario, c.senal,
       COALESCE(f.familias, 0) AS familias,
       COALESCE(f.talleres, 0) AS talleres,
       COALESCE(r.rutas, 0)    AS rutas
FROM comunidad c
LEFT JOIN (SELECT comunidad_id, COUNT(*) AS familias,
                  SUM(FIND_IN_SET('taller_textil', servicios) > 0) AS talleres
           FROM familia_anfitriona WHERE activa = 1
           GROUP BY comunidad_id) f ON f.comunidad_id = c.id
LEFT JOIN (SELECT rp.comunidad_id, COUNT(DISTINCT rp.ruta_id) AS rutas
           FROM ruta_parada rp JOIN ruta ru ON ru.id = rp.ruta_id AND ru.activa = 1
           GROUP BY rp.comunidad_id) r ON r.comunidad_id = c.id
WHERE c.activa = 1
ORDER BY c.nombre;
```

- Cada subconsulta **agrupa primero** (una fila por comunidad) y después se junta con `comunidad`. Así se resuelve todo en **una sola consulta**, en vez de una consulta por comunidad (el problema "N+1").
- **¿Por qué no un JOIN directo a las dos tablas?** Porque se multiplicarían las filas: 4 familias × 1 ruta, o 1 familia × 2 rutas, y los COUNT saldrían inflados.
- **`FIND_IN_SET('taller_textil', servicios)`** busca un valor dentro de un campo SET (`'desayuno,cena,taller_textil'`) y devuelve su posición, o 0. `> 0` lo convierte en 1 o 0, y `SUM` cuenta cuántas familias lo ofrecen.
- **LEFT JOIN + COALESCE**: Ticonata no tiene familias registradas y aparece igual, con 0.
- Ejemplo: Amantaní tiene 4 familias, 1 taller y 1 ruta; Uros, 0 familias y 5 rutas; Taquile, 1 familia, 1 taller y 2 rutas.

### 4. Cuántas salidas tiene cada día (GROUP BY por fecha)

```sql
-- Devuelve cada día desde hoy, durante 7 días, que tiene salidas no canceladas, con cuántas.
SELECT DATE(fecha_hora_zarpe) AS dia, COUNT(*) AS salidas
FROM salida
WHERE estado <> 'cancelada'
  AND fecha_hora_zarpe >= CURDATE()
  AND fecha_hora_zarpe <  CURDATE() + INTERVAL %s DAY
GROUP BY DATE(fecha_hora_zarpe)
ORDER BY dia;
```

- **`DATE(...)`** quita la hora: las salidas de las 07:00 y de las 14:00 del mismo día caen en el mismo grupo.
- **GROUP BY** arma un grupo por día y **COUNT(\*)** cuenta las salidas de cada grupo.
- Los días sin salidas **no aparecen** (no hay filas que agrupar). Python completa los 7 días poniendo 0 en esos.
- Ejemplo (20/10/2026): hoy 3, mié 21 3, jue 22 2, vie 23 1, y del sáb 24 al lun 26, 0.

### 5. Alertas en tres grupos con CASE

```sql
SELECT a.titulo, a.nivel, COALESCE(c.nombre, 'Todo el lago') AS lugar,
       CASE WHEN a.vigente_desde <= NOW() AND a.vigente_hasta > NOW() THEN 'vigente'
            WHEN a.vigente_desde > NOW() THEN 'proxima'
            ELSE 'pasada' END AS grupo
FROM alerta_lago a
LEFT JOIN comunidad c ON c.id = a.comunidad_id
WHERE a.vigente_hasta >= NOW() - INTERVAL 30 DAY
ORDER BY FIELD(grupo, 'vigente', 'proxima', 'pasada'), a.nivel DESC, a.vigente_desde DESC;
```

- **CASE** pone una etiqueta a cada fila según su fecha. Es como un if/elif/else dentro del SELECT.
- **WHERE** deja fuera lo que terminó hace más de 30 días.
- **FIELD(grupo, ...)** ordena los grupos en el orden que queremos (vigentes, próximas y pasadas), y dentro de cada grupo lo más grave primero.
