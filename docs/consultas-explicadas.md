# Consultas explicadas

Las **20 consultas SELECT más importantes** de Titicaca Vivo (la sección 15 pide al menos 15). Cada una tiene:

1. la pantalla donde se usa;
2. la consulta completa, copiada **tal cual** del código;
3. la explicación línea por línea;
4. un ejemplo del resultado con los datos de la semilla;
5. el índice que usa, según el `EXPLAIN`.

Está escrito para estudiarlo y explicarlo con nuestras propias palabras.

**Cómo se armó.** Un script copió el SQL del código, sin pasarlo a mano. Los ejemplos y los `EXPLAIN` se tomaron en la base de pruebas recién cargada con `flask bd reiniciar` (MariaDB 10.4.32), el 20/10/2026 a las 21:42.

La semilla calcula sus fechas a partir del día en que se carga. En los ejemplos, «hoy» es el 20/10/2026, «mañana» el 21/10 y «pasado mañana» el 22/10. Si la cargan otro día, cambian las fechas, pero no los resultados.

La prueba `tests/test_documentacion.py` revisa que cada consulta de este documento siga **idéntica** a la del código: si alguien cambia una, la prueba avisa.

## Índice

| # | Consulta | Pantalla | Lo que hay que saber explicar |
|---|---|---|---|
| [1](#consulta-1) | Salidas de un día y si una alerta las afecta | `/` y `/salidas` | Vista, `EXISTS` con subconsulta, filtro opcional |
| [2](#consulta-2) | La vista `v_disponibilidad_salida`: cupos libres y estado público | Todas las que muestran cupos | Vista, `LEFT JOIN` a una subconsulta con `GROUP BY`, `CASE` |
| [3](#consulta-3) | Precio por tipo de pasajero: tarifa vigente y temporada (RN-04) | `/salidas/<id>`, reservar | Subconsulta correlacionada con `MAX`, `COALESCE` |
| [4](#consulta-4) | Alertas que afectan a una salida (RN-11) | `/salidas/<id>` | JOIN por rango de horas, `LEFT JOIN`, orden de un ENUM |
| [5](#consulta-5) | Comunidades con sus conteos, sin N+1 | `/comunidades`, portada | `LEFT JOIN` a subconsultas agrupadas, `FIND_IN_SET` |
| [6](#consulta-6) | Reseñas publicadas de una ruta, con su promedio | `/salidas/<id>` | Funciones de ventana `AVG() OVER ()` y `COUNT(*) OVER ()` |
| [7](#consulta-7) | Mi reserva: ¿el documento es del titular? | `/mi-reserva` | JOIN, parámetros `%s` (sin inyección SQL) |
| [8](#consulta-8) | Reservar, paso 1: bloquear la salida (`FOR UPDATE`) | Reservar | Bloqueo de fila, transacción (RN-02) |
| [9](#consulta-9) | Reservar, paso 2: contar los ocupados con lectura actual | Reservar | `COUNT`, `JOIN`, `LOCK IN SHARE MODE` (RN-01) |
| [10](#consulta-10) | Reservar: ¿algún documento ya viaja en esa salida? (RN-09) | Reservar | `IN` de pares, marcas `%s` armadas en Python |
| [11](#consulta-11) | La familia anfitriona que toca: rotación justa (RN-10) | Reservar con noche | Subconsultas por fila, `NOT EXISTS`, `ORDER BY` con 4 criterios, `FOR UPDATE` |
| [12](#consulta-12) | Iniciar sesión: el usuario, su rol y su hash | `/entrar` | JOIN, búsqueda por UNIQUE, bcrypt fuera del SQL |
| [13](#consulta-13) | Pagos por verificar (RN-06) | `/panel/pagos` | 4 JOIN, subconsulta con `SUM`, cola por fecha |
| [14](#consulta-14) | Manifiesto: los pasajeros de una salida | `/panel/salidas/<id>/pasajeros` | `LEFT JOIN` (abordaje opcional), subconsulta agrupada, sin N+1 |
| [15](#consulta-15) | Abordaje con QR: la reserva y la ventana de RN-12 | `/panel/abordaje/<código>` | 5 JOIN, `BETWEEN` con `INTERVAL`, hora de Lima |
| [16](#consulta-16) | ¿La lancha ya tiene otra salida en ese horario? (RN-07) | Nueva salida / editar | Cruce de intervalos, `FOR UPDATE` de la lancha |
| [17](#consulta-17) | Las salidas que afecta una alerta, para suspenderlas (RN-11) | `/panel/alertas/<id>` | JOIN de una tabla con una vista por horario, `EXISTS` |
| [18](#consulta-18) | Transparencia comunitaria: ingresos por familia y por comunidad | `/panel/hospedajes/transparencia` | `LEFT JOIN` con condición en el `ON`, `SUM() OVER (PARTITION BY …)` |
| [19](#consulta-19) | Ocupación por ruta con su puesto | `/panel/indicadores` | `GROUP BY` con `SUM`, `RANK() OVER` |
| [20](#consulta-20) | Rutas con poca ocupación | `/panel/indicadores` | `HAVING` frente a `WHERE` |

## Cómo leer un EXPLAIN

`EXPLAIN` delante de un SELECT muestra **cómo** lo va a ejecutar MariaDB, sin ejecutarlo. Hay una fila por cada tabla que lee. Las columnas más importantes son estas:

| Columna | Qué dice |
|---|---|
| `type` | Cómo encuentra las filas, de mejor a peor: `const` (1 fila, por PK o UNIQUE) → `eq_ref` (1 fila por cada fila de la tabla anterior, por PK) → `ref` (varias filas, por un índice) → `range` (un rango del índice) → `index` (recorre todo el índice) → `ALL` (lee la tabla entera). |
| `key` | El índice que eligió (— = ninguno). |
| `rows` | Cuántas filas calcula que va a leer. |
| `Extra` | `Using index`: le basta el índice, sin leer la tabla. `Using where`: filtra después de leer. `Using index condition`: filtra dentro del índice. `Using filesort`: ordena aparte. `Using temporary`: usa una tabla temporal (por GROUP BY, ventanas o ORDER BY). |
| Tipo de subconsulta | `DEPENDENT SUBQUERY`: se repite por cada fila de afuera. `DERIVED`: subconsulta del FROM, se calcula una vez. `LATERAL DERIVED`: MariaDB la calcula solo para las filas que necesita. `MATERIALIZED`: la calcula una vez y la guarda. |

**Tablas chicas.** Con 5 a 23 filas por tabla, leer la tabla entera (`ALL`) a veces es más rápido que usar un índice, y el optimizador lo decide con las estadísticas (D-97). Donde sale `ALL`, decimos qué índice está listo para cuando la tabla crezca.

---

## Lo que ve el turista

<a id="consulta-1"></a>

### 1. Salidas de un día y si una alerta las afecta

- **Pantalla:** La portada (`/`, «Salidas de hoy») y `/salidas?fecha=…&ruta=…`.
- **Dónde está:** `salida.listar_publicas(fecha, ruta_codigo=None)`, en [app/modelos/salida.py:34](../app/modelos/salida.py#L34).
- **Qué hay que saber explicar:** Vista, `EXISTS` con subconsulta, filtro opcional.

```sql
SELECT v.salida_id, v.fecha_hora_zarpe, v.fecha_hora_retorno, v.ruta_codigo,
       v.ruta_nombre, v.incluye_pernocte, v.embarcacion_nombre, v.cupo, v.ocupados,
       v.libres, v.estado, v.estado_publico,
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
ORDER BY v.fecha_hora_zarpe, v.ruta_nombre
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT v.salida_id, … v.estado_publico` | Las columnas salen de la vista `v_disponibilidad_salida` (consulta 2), que ya trae la ruta, la lancha, los cupos y el estado que ve el público. Así esta consulta no repite esos JOIN. |
| `EXISTS (SELECT 1 FROM alerta_lago a WHERE …) AS afectada_por_alerta` | Subconsulta que da **1** si existe al menos una alerta que cumpla las condiciones, y **0** si no. Dice `SELECT 1` porque no importan las columnas: solo si hay alguna fila. Se calcula para cada salida. |
| `a.nivel IN ('naranja','rojo')` | Solo las alertas naranja o roja afectan a una salida (RN-11). La amarilla y la verde son avisos. |
| `a.vigente_desde < v.fecha_hora_retorno AND a.vigente_hasta > v.fecha_hora_zarpe` | Los dos horarios se cruzan: la alerta empieza antes de que vuelva la lancha **y** termina después de que zarpe. |
| `a.comunidad_id IS NULL OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp WHERE rp.ruta_id = v.ruta_id)` | La alerta es de todo el lago (no tiene comunidad) **o** es de una comunidad por la que pasa la ruta. La subconsulta lista las paradas de la ruta. |
| `FROM v_disponibilidad_salida v` | La vista se lee como si fuera una tabla. |
| `WHERE v.fecha_hora_zarpe >= %s AND v.fecha_hora_zarpe < %s + INTERVAL 1 DAY` | Las salidas del día pedido: desde las 00:00 de ese día hasta antes de las 00:00 del siguiente. No se escribe `DATE(v.fecha_hora_zarpe) = %s`: una función sobre la columna impide usar su índice. |
| `AND v.estado <> 'cancelada'` | Las canceladas no se muestran al público. |
| `AND (%s IS NULL OR v.ruta_codigo = %s)` | Filtro opcional. Si no se eligió ruta, el parámetro es NULL y la condición vale para todas. Si se eligió una, solo esa. Una sola consulta sirve para los 2 casos, sin armar el SQL pegando texto. |
| `ORDER BY v.fecha_hora_zarpe, v.ruta_nombre` | Por hora de zarpe. Si 2 zarpan a la misma hora, por nombre de ruta. |

**Ejemplo con la semilla:** `listar_publicas('2026-10-21')`: las salidas de mañana, sin elegir ruta.

| salida_id | fecha_hora_zarpe | ruta_codigo | cupo | ocupados | libres | estado | estado_publico | afectada_por_alerta |
|---|---|---|---|---|---|---|---|---|
| 10 | 2026-10-21 07:00 | URO-TAQ | 25 | 4 | 21 | programada | disponible | 0 |
| 9 | 2026-10-21 07:00 | URO-AMA-TAQ | 20 | 2 | 18 | suspendida | suspendida | 1 |
| 11 | 2026-10-21 09:00 | URO-MD | 18 | 0 | 18 | programada | disponible | 0 |

La salida 9 pasa por Amantaní, y la alerta 1 (oleaje **naranja** en Amantaní, hasta el 22/10 a las 06:00) se cruza con su horario: `afectada_por_alerta = 1`. Además ya está suspendida. La 10 (Uros y Taquile) no pasa por Amantaní: da 0. Hay una alerta de heladas de todo el lago que se cruza con ella, pero es **amarilla** y no cuenta.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `ALL` | — | 5 | Using temporary; Using filesort |
| `s` | `ref` | `ix_salida_ruta_zarpe` | 1 | Using index condition; Using where |
| `e` | `eq_ref` | `PRIMARY` | 1 | — |
| `<derived5>` | `ref` | `key0` | 2 | — |
| `re` (lateral derived) | `ref` | `ix_reserva_salida_estado` | 1 | Using index condition; Using where |
| `rp` (lateral derived) | `ref` | `uk_pasajero_documento` | 1 | Using index |
| `a` (dependent subquery) | `ALL` | — | 6 | Range checked for each record (index map: 0x6) |
| `rp` (dependent subquery) | `eq_ref` | `uk_parada_comunidad` | 1 | Using index |

`s` (salida) usa `ix_salida_ruta_zarpe` (ruta + hora de zarpe): por cada ruta va directo a las salidas de ese día. El conteo de ocupados de la vista aparece como `LATERAL DERIVED` con `ix_reserva_salida_estado`: MariaDB cuenta solo las reservas de las salidas que necesita, no las de todas. La subconsulta de paradas usa `uk_parada_comunidad` con `Using index`: le basta el índice. `ruta` (5 filas) y `alerta_lago` (6 filas) se leen enteras (`ALL`) porque son tablas chicas. En `alerta_lago`, «Range checked for each record» quiere decir que, por cada salida, MariaDB decide si le conviene usar `ix_alerta_vigencia`.

<a id="consulta-2"></a>

### 2. La vista `v_disponibilidad_salida`: cupos libres y estado público

- **Pantalla:** Toda pantalla que muestra cupos: la portada, `/salidas`, `/salidas/<id>`, la lista de salidas del panel y los indicadores. Las consultas 1, 17, 19 y 20 la leen.
- **Dónde está:** Vista de la base (se crea en `02_vistas_triggers.sql`), en [database/02_vistas_triggers.sql:21](../database/02_vistas_triggers.sql#L21).
- **Qué hay que saber explicar:** Vista, `LEFT JOIN` a una subconsulta con `GROUP BY`, `CASE`.

```sql
CREATE OR REPLACE VIEW v_disponibilidad_salida AS
SELECT
  s.id                 AS salida_id,
  s.fecha_hora_zarpe,
  s.fecha_hora_retorno,
  s.estado,
  s.motivo_estado,
  s.cupo,
  r.id                 AS ruta_id,
  r.codigo             AS ruta_codigo,
  r.nombre             AS ruta_nombre,
  r.incluye_pernocte,
  e.id                 AS embarcacion_id,
  e.nombre             AS embarcacion_nombre,
  e.matricula,
  e.capacidad_maxima,
  COALESCE(o.ocupados, 0) AS ocupados,
  -- Nunca negativo (RN-01). CAST: cupo es UNSIGNED y restar podría desbordar.
  GREATEST(CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0), 0) AS libres,
  CASE
    WHEN s.estado = 'cancelada' THEN 'cancelada'                       -- no se muestra al público
    WHEN s.estado IN ('zarpo','finalizada') OR s.fecha_hora_zarpe <= NOW() THEN 'zarpo'
    WHEN s.estado = 'suspendida' THEN 'suspendida'
    WHEN COALESCE(o.ocupados, 0) >= s.cupo THEN 'llena'
    WHEN CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0) <= 3 THEN 'pocos_cupos'
    ELSE 'disponible'
  END AS estado_publico
FROM salida s
JOIN ruta r        ON r.id = s.ruta_id
JOIN embarcacion e ON e.id = s.embarcacion_id
-- LEFT JOIN: una salida sin reservas igual debe aparecer (con 0 ocupados)
LEFT JOIN (
  SELECT re.salida_id, COUNT(*) AS ocupados
  FROM reserva re
  JOIN reserva_pasajero rp ON rp.reserva_id = re.id
  WHERE re.estado IN ('confirmada','pagada','abordada')
     OR (re.estado = 'pendiente_pago' AND re.vence_en > NOW())
  GROUP BY re.salida_id
) o ON o.salida_id = s.id;
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `CREATE OR REPLACE VIEW v_disponibilidad_salida AS SELECT` | Una vista es una consulta guardada con nombre. No guarda datos: cada vez que se lee, se ejecuta con los datos de ese momento. |
| `s.id AS salida_id, … e.capacidad_maxima` | Datos de la salida, de su ruta y de su lancha. `AS` les pone un nombre claro. |
| `COALESCE(o.ocupados, 0) AS ocupados` | Si la salida no tiene reservas, el LEFT JOIN deja `o.ocupados` en NULL. COALESCE lo cambia por 0. |
| `GREATEST(CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0), 0) AS libres` | Libres = cupo − ocupados, y nunca menos de 0. El `CAST AS SIGNED` hace falta porque `cupo` es UNSIGNED (sin signo): sin él, 18 − 20 daría error de desborde en vez de −2. |
| `CASE WHEN … END AS estado_publico` | Lo que ve el turista, en este orden: cancelada, zarpó (porque ya zarpó o ya pasó la hora), suspendida, llena (ocupados ≥ cupo), pocos cupos (3 o menos libres) y disponible. El CASE se queda con la **primera** condición verdadera, por eso el orden importa (RN-08). |
| `FROM salida s JOIN ruta r ON … JOIN embarcacion e ON …` | JOIN interno: toda salida tiene ruta y lancha (FK NOT NULL), así que no se pierde ninguna. |
| `LEFT JOIN (SELECT re.salida_id, COUNT(*) AS ocupados FROM reserva re JOIN reserva_pasajero rp ON … GROUP BY re.salida_id) o ON o.salida_id = s.id` | La subconsulta cuenta los pasajeros por salida: GROUP BY junta los de una misma salida y COUNT(*) los cuenta. Es LEFT JOIN para que también salgan las salidas que no tienen reservas. |
| `WHERE re.estado IN ('confirmada','pagada','abordada') OR (re.estado = 'pendiente_pago' AND re.vence_en > NOW())` | **RN-01**: ocupan lugar las reservas confirmadas, pagadas y abordadas, y las pendientes de pago que todavía no vencen. Una pendiente vencida ya no guarda el lugar. |

**Ejemplo con la semilla:** `SELECT salida_id, ruta_codigo, cupo, ocupados, libres, estado, estado_publico FROM v_disponibilidad_salida WHERE salida_id IN (8, 9, 10, 11)`

| salida_id | ruta_codigo | cupo | ocupados | libres | estado | estado_publico |
|---|---|---|---|---|---|---|
| 9 | URO-AMA-TAQ | 20 | 2 | 18 | suspendida | suspendida |
| 8 | URO-MD | 18 | 15 | 3 | programada | zarpo |
| 11 | URO-MD | 18 | 0 | 18 | programada | disponible |
| 10 | URO-TAQ | 25 | 4 | 21 | programada | disponible |

La salida 10 tiene 3 reservas pendientes de pago: TV-TX69 (2 pasajeros, todavía vigente), TV-RQCP (2, vence mañana a las 06:00) y TV-UKKR (3, que **venció** media hora después de cargar la semilla). Ocupan 2 + 2 = **4**, no 7. La salida 8 tiene 15 de 18 lugares ocupados, pero zarpó hoy a las 14:00: el público ve «zarpo», no «pocos cupos».

**Índice (EXPLAIN)** de `EXPLAIN SELECT * FROM v_disponibilidad_salida WHERE salida_id = 10`

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `s` | `const` | `PRIMARY` | 1 | — |
| `r` | `const` | `PRIMARY` | 1 | — |
| `e` | `const` | `PRIMARY` | 1 | — |
| `<derived3>` | `ALL` | — | 23 | Using where |
| `re` (derived) | `ALL` | — | 23 | Using where; Using temporary; Using filesort |
| `rp` (derived) | `ref` | `uk_pasajero_documento` | 1 | Using index |

`s`, `r` y `e` son `const`: las encuentra por su PRIMARY, una fila cada una. El conteo (`<derived3>`) lee las 23 reservas (`ALL`): con tan pocas filas, MariaDB prefiere contarlas todas y después quedarse con la salida 10. En la consulta 1, con las mismas tablas, elige `LATERAL DERIVED` con `ix_reserva_salida_estado` y cuenta solo las salidas que necesita. Cuando haya miles de reservas, irá por ese camino (D-97).

<a id="consulta-3"></a>

### 3. Precio por tipo de pasajero: tarifa vigente y temporada (RN-04)

- **Pantalla:** `/salidas/<id>` (tabla de precios) y `/salidas/<id>/reservar` (el total). También se usa dentro de la transacción de reserva: el precio queda guardado como una foto en `precio_aplicado`.
- **Dónde está:** `tarifa.precios_para_salida(salida_id)`, en [app/modelos/tarifa.py:24](../app/modelos/tarifa.py#L24).
- **Qué hay que saber explicar:** Subconsulta correlacionada con `MAX`, `COALESCE`.

```sql
SELECT tp.id AS tipo_pasajero_id, tp.codigo, tp.nombre, tp.edad_minima, tp.edad_maxima,
       t.precio_base,
       COALESCE((SELECT MAX(te.recargo_porcentaje) FROM temporada te
                 WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin),
                0) AS recargo_porcentaje,
       (SELECT te.nombre FROM temporada te
        WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin
        ORDER BY te.recargo_porcentaje DESC
        LIMIT 1) AS temporada
FROM salida s
JOIN tarifa t         ON t.ruta_id = s.ruta_id
JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id
WHERE s.id = %s
  AND t.vigente_desde = (SELECT MAX(t2.vigente_desde) FROM tarifa t2
                         WHERE t2.ruta_id = t.ruta_id
                           AND t2.tipo_pasajero_id = t.tipo_pasajero_id
                           AND t2.vigente_desde <= DATE(s.fecha_hora_zarpe)
                           AND (t2.vigente_hasta IS NULL
                                OR t2.vigente_hasta >= DATE(s.fecha_hora_zarpe)))
ORDER BY tp.id
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT tp.id AS tipo_pasajero_id, … t.precio_base` | Cada tipo de pasajero con su precio base. |
| `COALESCE((SELECT MAX(te.recargo_porcentaje) FROM temporada te WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin), 0) AS recargo_porcentaje` | El recargo de la temporada que contiene el día de la salida. Si 2 temporadas se cruzan, gana la de mayor recargo (MAX). Si no hay temporada, la subconsulta da NULL y COALESCE lo vuelve 0. |
| `(SELECT te.nombre … ORDER BY te.recargo_porcentaje DESC LIMIT 1) AS temporada` | El nombre de esa misma temporada (la de mayor recargo), para mostrarlo. |
| `FROM salida s JOIN tarifa t ON t.ruta_id = s.ruta_id JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id` | Las tarifas de la ruta de esa salida, con el nombre de cada tipo de pasajero. |
| `WHERE s.id = %s` | Solo la salida pedida. |
| `AND t.vigente_desde = (SELECT MAX(t2.vigente_desde) FROM tarifa t2 WHERE t2.ruta_id = t.ruta_id AND t2.tipo_pasajero_id = t.tipo_pasajero_id AND t2.vigente_desde <= DATE(s.fecha_hora_zarpe) AND (t2.vigente_hasta IS NULL OR t2.vigente_hasta >= DATE(s.fecha_hora_zarpe)))` | Subconsulta **correlacionada**: usa la `t` de afuera. De todas las tarifas de esa ruta y ese tipo que valen el día de la salida, toma la más reciente. Así, si el operador sube el precio desde el 1 de diciembre, las salidas de noviembre siguen con el precio anterior. `vigente_hasta IS NULL` quiere decir «sin fecha de fin». |
| `ORDER BY tp.id` | En el orden de los tipos: primero el adulto nacional. |
| *Después, en Python* | `precio = precio_base × (1 + recargo / 100)`, redondeado a 2 decimales (`tarifa.calcular_precio`). |

**Ejemplo con la semilla:** `precios_para_salida(10)`: Uros y Taquile, mañana.

| tipo_pasajero_id | codigo | nombre | precio_base | recargo_porcentaje | temporada |
|---|---|---|---|---|---|
| 1 | adulto_nacional | Adulto nacional | 80.00 | 0.00 | NULL |
| 2 | adulto_extranjero | Adulto extranjero | 120.00 | 0.00 | NULL |
| 3 | estudiante | Estudiante (con carné) | 60.00 | 0.00 | NULL |
| 4 | nino | Niño o niña | 40.00 | 0.00 | NULL |
| 5 | adulto_mayor | Adulto mayor | 60.00 | 0.00 | NULL |

El recargo es 0 porque el 21 de octubre no hay temporada. Si la salida fuera el 3 de noviembre, entraría en la «Semana Jubilar de Puno 2026» (del 1 al 7 de noviembre, 10 %): el adulto nacional pagaría 80.00 × 1.10 = **88.00**.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `s` | `const` | `PRIMARY` | 1 | — |
| `tp` | `index` | `PRIMARY` | 5 | — |
| `t` | `ref` | `uk_tarifa_vigencia` | 1 | Using where |
| `t2` (dependent subquery) | `ref` | `uk_tarifa_vigencia` | 1 | Using index condition; Using where |
| `te` (subquery) | `range` | `ix_temporada_fechas` | 1 | Using index condition; Using filesort |
| `te` (subquery) | `range` | `ix_temporada_fechas` | 1 | Using index condition |

`s` es `const` (PRIMARY). `t` es `ref` por `uk_tarifa_vigencia` (ruta, tipo, vigente_desde): por cada tipo va directo a sus tarifas. La subconsulta del MAX (`t2`) usa el mismo índice. Las 2 subconsultas de temporada usan `ix_temporada_fechas` por rango (`range`). `tp` aparece como `index`: recorre los 5 tipos por su PRIMARY, que ya están en el orden del `ORDER BY tp.id`.

<a id="consulta-4"></a>

### 4. Alertas que afectan a una salida (RN-11)

- **Pantalla:** `/salidas/<id>` (el aviso de arriba del detalle) y el formulario de reserva.
- **Dónde está:** `salida.alertas_que_la_afectan(salida_id)`, en [app/modelos/salida.py:96](../app/modelos/salida.py#L96).
- **Qué hay que saber explicar:** JOIN por rango de horas, `LEFT JOIN`, orden de un ENUM.

```sql
SELECT a.id, a.tipo, a.nivel, a.titulo, a.descripcion, a.fuente,
       a.vigente_desde, a.vigente_hasta,
       COALESCE(c.nombre, 'Todo el lago') AS lugar
FROM salida s
JOIN alerta_lago a ON a.vigente_desde < s.fecha_hora_retorno
                  AND a.vigente_hasta > s.fecha_hora_zarpe
LEFT JOIN comunidad c ON c.id = a.comunidad_id
WHERE s.id = %s
  AND a.nivel IN ('naranja','rojo')
  AND (a.comunidad_id IS NULL
       OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp
                             WHERE rp.ruta_id = s.ruta_id))
ORDER BY a.nivel DESC, a.vigente_desde
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT a.id, … COALESCE(c.nombre, 'Todo el lago') AS lugar` | Los datos de la alerta y el lugar: el nombre de la comunidad, o «Todo el lago» si la alerta no tiene comunidad (NULL). |
| `FROM salida s JOIN alerta_lago a ON a.vigente_desde < s.fecha_hora_retorno AND a.vigente_hasta > s.fecha_hora_zarpe` | Este JOIN no une por un id sino por el horario: junta cada alerta cuyo horario se cruza con el de la salida. |
| `LEFT JOIN comunidad c ON c.id = a.comunidad_id` | Es LEFT JOIN porque una alerta de todo el lago no tiene comunidad. Con un JOIN interno, esas alertas desaparecerían. |
| `WHERE s.id = %s` | La salida que se está mirando. |
| `AND a.nivel IN ('naranja','rojo')` | Solo las que afectan (RN-11). |
| `AND (a.comunidad_id IS NULL OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp WHERE rp.ruta_id = s.ruta_id))` | Alertas de todo el lago, o de una comunidad por la que pasa la ruta. |
| `ORDER BY a.nivel DESC, a.vigente_desde` | Primero las rojas. `nivel` es un ENUM ('verde','amarillo','naranja','rojo'), y un ENUM se ordena por su posición en la lista, no por orden alfabético. Después, por la hora de inicio. |

**Ejemplo con la semilla:** `alertas_que_la_afectan(9)`: Uros, Amantaní y Taquile, mañana a las 07:00.

| id | nivel | tipo | titulo | vigente_desde | vigente_hasta | lugar |
|---|---|---|---|---|---|---|
| 1 | naranja | oleaje | Oleaje fuerte en el sector de Amantaní | 2026-10-20 00:00 | 2026-10-22 06:00 | Amantaní |

La alerta 2 (heladas, todo el lago) también se cruza con esta salida, pero es amarilla: no sale. La 6 (fiesta en Llachón) es verde y de otra comunidad.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `s` | `const` | `PRIMARY` | 1 | — |
| `a` | `ALL` | — | 6 | Using where; Using filesort |
| `c` | `eq_ref` | `PRIMARY` | 1 | Using where |
| `rp` (dependent subquery) | `eq_ref` | `uk_parada_comunidad` | 1 | Using index |

`s` es `const`. `alerta_lago` es `ALL` (6 filas): lee todas las alertas y filtra por horario y nivel. Para cuando crezca, está `ix_alerta_vigencia` (vigente_desde, vigente_hasta). `c` es `eq_ref` por PRIMARY. La subconsulta de paradas es `eq_ref` por `uk_parada_comunidad`, con `Using index`.

<a id="consulta-5"></a>

### 5. Comunidades con sus conteos, sin N+1

- **Pantalla:** `/comunidades` y la portada (las tarjetas de comunidades).
- **Dónde está:** `comunidad.listar_publicas()`, en [app/modelos/comunidad.py:17](../app/modelos/comunidad.py#L17).
- **Qué hay que saber explicar:** `LEFT JOIN` a subconsultas agrupadas, `FIND_IN_SET`.

```sql
SELECT c.id, c.nombre, c.slug, c.distrito, c.provincia, c.idioma_originario, c.senal,
       c.tiene_hospedaje, c.descripcion, c.foto_credito, c.latitud, c.longitud,
       COALESCE(f.familias, 0) AS familias,
       COALESCE(f.talleres, 0) AS talleres,
       COALESCE(r.rutas, 0)    AS rutas
FROM comunidad c
LEFT JOIN (SELECT comunidad_id, COUNT(*) AS familias,
                  SUM(FIND_IN_SET('taller_textil', servicios) > 0) AS talleres
           FROM familia_anfitriona
           WHERE activa = 1
           GROUP BY comunidad_id) f ON f.comunidad_id = c.id
LEFT JOIN (SELECT rp.comunidad_id, COUNT(DISTINCT rp.ruta_id) AS rutas
           FROM ruta_parada rp
           JOIN ruta ru ON ru.id = rp.ruta_id AND ru.activa = 1
           GROUP BY rp.comunidad_id) r ON r.comunidad_id = c.id
WHERE c.activa = 1
ORDER BY c.nombre
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT c.id, c.nombre, …` | Los datos públicos de la comunidad, sin teléfonos ni responsables. |
| `COALESCE(f.familias, 0) AS familias, COALESCE(f.talleres, 0) AS talleres, COALESCE(r.rutas, 0) AS rutas` | Los conteos vienen de 2 subconsultas. COALESCE pone 0 a la comunidad que no aparece en ellas. |
| `LEFT JOIN (SELECT comunidad_id, COUNT(*) AS familias, SUM(FIND_IN_SET('taller_textil', servicios) > 0) AS talleres FROM familia_anfitriona WHERE activa = 1 GROUP BY comunidad_id) f ON f.comunidad_id = c.id` | Subconsulta agrupada: una fila por comunidad, con cuántas familias activas tiene y cuántas ofrecen taller textil. `servicios` es un SET; `FIND_IN_SET` da la posición del valor (0 si no está), `> 0` lo vuelve 1 o 0, y SUM cuenta los 1. |
| `LEFT JOIN (SELECT rp.comunidad_id, COUNT(DISTINCT rp.ruta_id) AS rutas FROM ruta_parada rp JOIN ruta ru ON ru.id = rp.ruta_id AND ru.activa = 1 GROUP BY rp.comunidad_id) r ON r.comunidad_id = c.id` | Por cuántas rutas activas se visita cada comunidad. `DISTINCT` cuenta cada ruta una vez. |
| `WHERE c.activa = 1` | Solo las comunidades activas. |
| `ORDER BY c.nombre` | Alfabético. El cotejamiento `utf8mb4_spanish_ci` ordena bien las tildes y la ñ. |
| *¿Por qué no hay N+1?* | Sin las subconsultas, la página haría 1 consulta para las comunidades y 2 más por cada comunidad: 13 consultas para 6 comunidades. Así hace **1**, sin importar cuántas comunidades haya. |

**Ejemplo con la semilla:** `listar_publicas()`, sin parámetros.

| id | nombre | slug | familias | talleres | rutas |
|---|---|---|---|---|---|
| 3 | Amantaní | amantani | 4 | 1 | 1 |
| 4 | Llachón | llachon | 3 | 1 | 1 |
| 5 | Luquina Chico | luquina-chico | 1 | 0 | 1 |
| 2 | Taquile | taquile | 1 | 1 | 2 |
| 6 | Ticonata | ticonata | 0 | 0 | 0 |
| 1 | Uros | uros | 0 | 0 | 5 |

Ticonata no tiene familias ni rutas, pero aparece, gracias al LEFT JOIN y al COALESCE. Uros no tiene familias anfitrionas en la semilla, pero las 5 rutas pasan por ahí. Amantaní tiene 4 familias activas: la Familia Cari Tito está inactiva y no cuenta.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `c` | `ALL` | — | 6 | Using where; Using filesort |
| `<derived2>` | `ref` | `key0` | 2 | — |
| `<derived3>` | `ref` | `key0` | 2 | — |
| `ru` (derived) | `ALL` | — | 5 | Using where; Using temporary; Using filesort |
| `rp` (derived) | `ref` | `uk_parada_comunidad` | 1 | Using index |
| `familia_anfitriona` (derived) | `ALL` | — | 10 | Using where; Using temporary; Using filesort |

`c` es `ALL` (6 comunidades), con `Using filesort` para el `ORDER BY c.nombre`. Las 2 subconsultas (`DERIVED`) se calculan una vez cada una y se unen por `key0`, un índice que MariaDB crea solo para esa tabla temporal. `familia_anfitriona` es `ALL` (10 filas) dentro de su subconsulta; tiene `ix_familia_comunidad` para cuando crezca.

<a id="consulta-6"></a>

### 6. Reseñas publicadas de una ruta, con su promedio

- **Pantalla:** `/salidas/<id>`, en la sección «Opiniones».
- **Dónde está:** `resena.publicadas_de_ruta(ruta_id, limite=5)`, en [app/modelos/resena.py:141](../app/modelos/resena.py#L141).
- **Qué hay que saber explicar:** Funciones de ventana `AVG() OVER ()` y `COUNT(*) OVER ()`.

```sql
SELECT re.puntuacion, re.comentario, re.idioma, t.nacionalidad, s.fecha_hora_zarpe,
       AVG(re.puntuacion) OVER () AS promedio, COUNT(*) OVER () AS total
FROM resena re
JOIN reserva r ON r.id = re.reserva_id
JOIN salida s  ON s.id = r.salida_id
JOIN turista t ON t.id = r.turista_id
WHERE s.ruta_id = %s AND re.estado = 'publicada'
ORDER BY re.creada_en DESC
LIMIT %s
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT re.puntuacion, re.comentario, re.idioma, t.nacionalidad, s.fecha_hora_zarpe` | La reseña, el país del titular y la fecha del viaje. No se muestran nombres, por privacidad. |
| `AVG(re.puntuacion) OVER () AS promedio, COUNT(*) OVER () AS total` | **Funciones de ventana**: calculan el promedio y el total sobre todas las filas del resultado, pero sin juntarlas: cada fila sigue apareciendo. `OVER ()` vacío quiere decir que la ventana es todo el resultado. Se calculan **antes** del LIMIT: el promedio es de todas las reseñas publicadas, aunque solo se muestren 5. |
| `FROM resena re JOIN reserva r ON … JOIN salida s ON … JOIN turista t ON …` | De la reseña a su reserva, de la reserva a su salida (para saber la ruta) y al turista (para el país). |
| `WHERE s.ruta_id = %s AND re.estado = 'publicada'` | Solo las de esa ruta que el operador aprobó. Las pendientes y las rechazadas no se ven. |
| `ORDER BY re.creada_en DESC LIMIT %s` | Las más nuevas primero, y solo 5. |
| *¿Por qué no GROUP BY?* | Con `GROUP BY` y `AVG` se juntarían las filas y quedaría solo el promedio. Para tener las reseñas y el promedio harían falta 2 consultas. |

**Ejemplo con la semilla:** `publicadas_de_ruta(2, 5)`: Uros y Taquile, hasta 5 reseñas.

| puntuacion | idioma | nacionalidad | fecha_hora_zarpe | promedio | total |
|---|---|---|---|---|---|
| 5 | es | PE | 2026-10-13 07:00 | 4.5000 | 2 |
| 4 | en | FR | 2026-10-13 07:00 | 4.5000 | 2 |

Las 2 filas llevan el mismo promedio (4.5) y el mismo total (2).

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `re` | `ALL` | — | 6 | Using where; Using temporary; Using filesort |
| `r` | `eq_ref` | `PRIMARY` | 1 | — |
| `t` | `eq_ref` | `PRIMARY` | 1 | — |
| `s` | `eq_ref` | `PRIMARY` | 1 | Using where |

`resena` es `ALL` (6 filas), con `Using temporary; Using filesort` por la ventana y el ORDER BY. Después, cada JOIN es `eq_ref` por PRIMARY: una fila exacta por reseña. Para cuando haya muchas reseñas está `ix_resena_estado`.

<a id="consulta-7"></a>

### 7. Mi reserva: ¿el documento es del titular?

- **Pantalla:** `/mi-reserva`: el turista escribe su código y su documento.
- **Dónde está:** `reserva.validar_acceso(codigo, numero_documento)`, en [app/modelos/reserva.py:522](../app/modelos/reserva.py#L522).
- **Qué hay que saber explicar:** JOIN, parámetros `%s` (sin inyección SQL).

```sql
SELECT 1 AS ok
FROM reserva r
JOIN turista t ON t.id = r.turista_id
WHERE r.codigo = %s AND t.numero_documento = %s
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT 1 AS ok` | No hace falta ningún dato: solo saber si hay una fila. |
| `FROM reserva r JOIN turista t ON t.id = r.turista_id` | La reserva y su titular. |
| `WHERE r.codigo = %s AND t.numero_documento = %s` | Las 2 cosas tienen que coincidir. Los `%s` son **parámetros**: PyMySQL manda el texto aparte del SQL, así que un «código» como `' OR 1=1 --` no cambia la consulta. Antes, Python normaliza los datos: el código va en mayúsculas y el documento sin espacios. |
| *¿Por qué no se dice qué falló?* | La página responde lo mismo si el código no existe o si el documento no coincide. Así nadie puede averiguar qué códigos existen. |

**Ejemplo con la semilla:** `validar_acceso('TV-TX69', '48761230')`: el código y el documento del titular.

| ok |
|---|
| 1 |

Con el mismo código y otro documento, `validar_acceso('TV-TX69', '11111111')`, da **0 filas**: no entra.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `const` | `uk_reserva_codigo` | 1 | — |
| `t` | `const` | `PRIMARY` | 1 | — |

`r` es `const` por `uk_reserva_codigo`: el código es UNIQUE, así que hay a lo más 1 fila. `t` es `const` por PRIMARY. Es la consulta más barata posible: lee 2 filas.

---

## Reservar sin sobreventa (Oro)

<a id="consulta-8"></a>

### 8. Reservar, paso 1: bloquear la salida (`FOR UPDATE`)

- **Pantalla:** `/salidas/<id>/reservar`, al enviar «Confirmar reserva».
- **Dónde está:** `reserva._crear_en_transaccion` (paso 1), en [app/modelos/reserva.py:250](../app/modelos/reserva.py#L250).
- **Qué hay que saber explicar:** Bloqueo de fila, transacción (RN-02).

```sql
SELECT id, ruta_id, cupo, estado, fecha_hora_zarpe, fecha_hora_zarpe > NOW() AS aun_no_zarpa
FROM salida
WHERE id = %s
FOR UPDATE
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT id, ruta_id, cupo, estado, fecha_hora_zarpe, fecha_hora_zarpe > NOW() AS aun_no_zarpa` | Lo que hace falta para decidir: el cupo, el estado y si todavía no zarpa. La comparación da 1 o 0. |
| `FROM salida WHERE id = %s` | La salida elegida. |
| `FOR UPDATE` | **Bloquea esa fila** hasta el COMMIT o el ROLLBACK. Otra transacción que pida `FOR UPDATE` sobre la misma salida espera aquí: 2 reservas para la misma salida van de a una (RN-02). Las reservas de **otras** salidas no esperan, porque el bloqueo es de una fila, no de la tabla. |
| *¿Qué pasa después?* | Con la salida bloqueada, se revisa el token (RN-03) y el estado, se cuentan los ocupados (consulta 9), se revisan los documentos (consulta 10) y la familia (consulta 11), y recién ahí se hace el INSERT. Si algo falla, hay ROLLBACK y no queda nada a medias. |

**Ejemplo con la semilla:** Con la salida `10`.

| id | ruta_id | cupo | estado | fecha_hora_zarpe | aun_no_zarpa |
|---|---|---|---|---|---|
| 10 | 2 | 25 | programada | 2026-10-21 07:00 | 1 |

La prueba mutante de la F7 quita este `FOR UPDATE`: con 8 hilos y 1 lugar, se venden **8 lugares**.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `salida` | `const` | `PRIMARY` | 1 | — |

Es `const` por PRIMARY: encuentra una sola fila y bloquea solo esa. Si buscara sin índice, InnoDB bloquearía todas las filas que lee. Por eso importa buscar por la PK.

<a id="consulta-9"></a>

### 9. Reservar, paso 2: contar los ocupados con lectura actual

- **Pantalla:** `/salidas/<id>/reservar` (dentro de la misma transacción del paso 1).
- **Dónde está:** `reserva._crear_en_transaccion` (paso 2; `salida.contar_ocupados` usa la misma), en [app/modelos/reserva.py:272](../app/modelos/reserva.py#L272).
- **Qué hay que saber explicar:** `COUNT`, `JOIN`, `LOCK IN SHARE MODE` (RN-01).

```sql
SELECT COUNT(*) AS ocupados
FROM reserva_pasajero rp
JOIN reserva r ON r.id = rp.reserva_id
WHERE r.salida_id = %s
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
LOCK IN SHARE MODE
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT COUNT(*) AS ocupados` | Cuenta **pasajeros** (filas de `reserva_pasajero`), no reservas: una reserva de 4 personas ocupa 4 lugares. |
| `FROM reserva_pasajero rp JOIN reserva r ON r.id = rp.reserva_id` | Cada pasajero con su reserva, para saber su salida y su estado. |
| `WHERE r.salida_id = %s` | Solo esa salida. |
| `AND (r.estado IN ('confirmada','pagada','abordada') OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))` | RN-01, la misma regla que la vista (consulta 2). Los paréntesis importan: sin ellos, el OR se mezclaría con el `salida_id` y contaría pasajeros de otras salidas. |
| `LOCK IN SHARE MODE` | **Lectura actual**: lee lo último que se confirmó, no una foto vieja de la transacción, y bloquea esas filas para que nadie las cambie hasta el COMMIT. Junto con el `FOR UPDATE` de la salida, el conteo sigue siendo cierto al hacer el INSERT. |
| *Después, en Python* | `libres = max(cupo − ocupados, 0)`. Si los pasajeros nuevos son más que los libres, responde «Solo quedan N lugares» (422). |

**Ejemplo con la semilla:** Con la salida `10`.

| ocupados |
|---|
| 4 |

Da 4, igual que la vista: la reserva TV-UKKR ya venció y no cuenta.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `ref` | `ix_reserva_salida_estado` | 6 | Using index condition; Using where |
| `rp` | `ref` | `uk_pasajero_documento` | 1 | Using index |

`r` es `ref` por `ix_reserva_salida_estado` (salida_id, estado): va directo a las reservas de la salida 10. `rp` es `ref` por `uk_pasajero_documento` (reserva_id, …), con `Using index`: cuenta los pasajeros sin leer la tabla, porque le basta el índice. Esta consulta corre en **cada** reserva: por eso es una de las 3 del EXPLAIN de la F7.

<a id="consulta-10"></a>

### 10. Reservar: ¿algún documento ya viaja en esa salida? (RN-09)

- **Pantalla:** `/salidas/<id>/reservar` (dentro de la transacción).
- **Dónde está:** `reserva._crear_en_transaccion` (RN-09), en [app/modelos/reserva.py:293](../app/modelos/reserva.py#L293).
- **Qué hay que saber explicar:** `IN` de pares, marcas `%s` armadas en Python.

```sql
SELECT rp.tipo_documento, rp.numero_documento
FROM reserva_pasajero rp
JOIN reserva r ON r.id = rp.reserva_id
WHERE r.salida_id = %s
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
  AND (rp.tipo_documento, rp.numero_documento) IN ({marcas})
LOCK IN SHARE MODE
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `f"""…""" y {marcas}` | Es la única consulta armada con f-string, y lo único que se pega son **marcas `%s`**: para 2 pasajeros, `marcas` vale `(%s, %s), (%s, %s)`. Los documentos van como parámetros. Nunca entra texto del usuario en el SQL (sección 17), y la prueba `test_ningun_sql_lleva_texto_del_usuario` lo revisa. |
| `SELECT rp.tipo_documento, rp.numero_documento` | El documento repetido, para el mensaje de error. |
| `FROM reserva_pasajero rp JOIN reserva r ON … WHERE r.salida_id = %s AND (… estados que ocupan lugar …)` | Los pasajeros que ocupan lugar en la salida, igual que en la consulta 9. |
| `AND (rp.tipo_documento, rp.numero_documento) IN ({marcas})` | Comparación de **pares**: el tipo y el número tienen que coincidir juntos. Un DNI 40000001 y un pasaporte 40000001 son personas distintas. |
| `LOCK IN SHARE MODE` | Lectura actual, como en la consulta 9. |

**Ejemplo con la semilla:** Salida `10` y 2 pasajeros: (DNI 48761230) y (DNI 40000001).

| tipo_documento | numero_documento |
|---|---|
| DNI | 48761230 |

El primer documento ya viaja en la reserva TV-TX69, pendiente de pago y vigente. La reserva se rechaza con «El documento DNI 48761230 ya tiene un lugar en esta salida». El segundo documento no viaja en esa salida.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `ref` | `ix_reserva_salida_estado` | 6 | Using index condition; Using where |
| `rp` | `ref` | `uk_pasajero_documento` | 1 | Using where; Using index |

`r` es `ref` por `ix_reserva_salida_estado`. `rp` es `ref` por `uk_pasajero_documento` (reserva_id, tipo_documento, numero_documento), con `Using index`: compara los pares sin leer la tabla. Además existe `ix_pasajero_documento` (tipo, número), para buscar un documento en todas las salidas.

<a id="consulta-11"></a>

### 11. La familia anfitriona que toca: rotación justa (RN-10)

- **Pantalla:** Reservar una ruta con noche (Amantaní o Llachón). El operador la usa al asignar una familia que falta (`/panel/hospedajes`).
- **Dónde está:** `hospedaje.elegir_familia(cur, comunidad_id, fecha_noche, personas)`, en [app/modelos/hospedaje.py:41](../app/modelos/hospedaje.py#L41).
- **Qué hay que saber explicar:** Subconsultas por fila, `NOT EXISTS`, `ORDER BY` con 4 criterios, `FOR UPDATE`.

```sql
SELECT f.id, f.nombre_familia, f.capacidad_personas,
       (SELECT COUNT(*) FROM hospedaje h
        WHERE h.familia_id = f.id
          AND h.estado IN ('asignado','cumplido')
          AND h.fecha_noche BETWEEN %s - INTERVAL 30 DAY AND %s - INTERVAL 1 DAY
       ) AS noches_30_dias,
       (SELECT MAX(h.fecha_noche) FROM hospedaje h
        WHERE h.familia_id = f.id
          AND h.estado IN ('asignado','cumplido')
          AND h.fecha_noche < %s
       ) AS ultima_noche
FROM familia_anfitriona f
WHERE f.comunidad_id = %s
  AND f.activa = 1
  AND f.capacidad_personas >= %s
  AND NOT EXISTS (SELECT 1 FROM hospedaje h
                  WHERE h.familia_id = f.id
                    AND h.fecha_noche = %s
                    AND h.estado IN ('asignado','cumplido'))
ORDER BY noches_30_dias, ultima_noche IS NOT NULL, ultima_noche, f.id
LIMIT 1
FOR UPDATE
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT f.id, f.nombre_familia, f.capacidad_personas` | La familia candidata. |
| `(SELECT COUNT(*) FROM hospedaje h WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido') AND h.fecha_noche BETWEEN %s - INTERVAL 30 DAY AND %s - INTERVAL 1 DAY) AS noches_30_dias` | Una subconsulta por familia: cuántas noches recibió, o tiene asignadas, en los 30 días anteriores a esa noche. Las canceladas no cuentan. |
| `(SELECT MAX(h.fecha_noche) … AND h.fecha_noche < %s) AS ultima_noche` | Su última noche antes de esa. Es NULL si nunca recibió a nadie. |
| `FROM familia_anfitriona f WHERE f.comunidad_id = %s AND f.activa = 1 AND f.capacidad_personas >= %s` | Las familias activas de la comunidad donde se duerme, con lugar para **todo** el grupo: el grupo no se separa. |
| `AND NOT EXISTS (SELECT 1 FROM hospedaje h WHERE h.familia_id = f.id AND h.fecha_noche = %s AND h.estado IN ('asignado','cumplido'))` | Que esa noche esté libre: **no existe** un hospedaje suyo en esa fecha. |
| `ORDER BY noches_30_dias, ultima_noche IS NOT NULL, ultima_noche, f.id` | El corazón de RN-10. (1) Primero la que tuvo menos noches en 30 días. (2) `ultima_noche IS NOT NULL` vale 0 para la que nunca recibió y 1 para las demás: la que nunca recibió va primero. (3) Después, la que espera hace más tiempo (la última noche más antigua). (4) Si empatan en todo, la de menor id. |
| `LIMIT 1` | Solo la primera: la que toca. |
| `FOR UPDATE` | Bloquea las candidatas. 2 reservas para la misma noche no pueden quedarse con la misma familia: la segunda espera, y después ya no la ve libre. |

**Ejemplo con la semilla:** `elegir_familia(cur, 3, '2026-10-22', 2)`: Amantaní, pasado mañana, 2 personas.

| id | nombre_familia | capacidad_personas | noches_30_dias | ultima_noche |
|---|---|---|---|---|
| 2 | Familia Mamani Yucra | 4 | 1 | 2026-10-14 |

La misma consulta sin `LIMIT 1`, para ver el orden completo:

| id | nombre_familia | capacidad_personas | noches_30_dias | ultima_noche |
|---|---|---|---|---|
| 2 | Familia Mamani Yucra | 4 | 1 | 2026-10-14 |
| 3 | Familia Huatta Calsin | 5 | 1 | 2026-10-21 |

Quispe Cruz y Pacompía Ccalla ya tienen huéspedes esa noche (el NOT EXISTS las saca), y Cari Tito está inactiva. Las 2 candidatas tuvieron 1 noche en los últimos 30 días, así que desempata la última noche: Mamani Yucra espera desde el 14/10, mientras que Huatta Calsin ya tiene huéspedes el 21/10.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `f` | `range` | `ix_familia_comunidad` | 5 | Using index condition; Using where; Using filesort |
| `h` (materialized) | `ALL` | — | 9 | Using where |
| `h` (dependent subquery) | `ref` | `ix_hospedaje_familia_noche` | 1 | Using index condition; Using where |
| `h` (dependent subquery) | `ref` | `ix_hospedaje_familia_noche` | 1 | Using index condition; Using where |

`f` es `range` por `ix_familia_comunidad`. Las 2 subconsultas (`DEPENDENT SUBQUERY`, una vez por familia) usan `ix_hospedaje_familia_noche` (familia_id, fecha_noche) y van directo a las noches de esa familia. El `NOT EXISTS` aparece como `MATERIALIZED` con `ALL`: MariaDB lee una vez los 9 hospedajes y los guarda, porque son pocos (D-97). Con más filas, usará el mismo índice.

---

## El panel del personal

<a id="consulta-12"></a>

### 12. Iniciar sesión: el usuario, su rol y su hash

- **Pantalla:** `/entrar` (personal de la agencia).
- **Dónde está:** `usuario.verificar_credenciales(nombre_usuario, contrasena)`, en [app/modelos/usuario.py:66](../app/modelos/usuario.py#L66).
- **Qué hay que saber explicar:** JOIN, búsqueda por UNIQUE, bcrypt fuera del SQL.

```sql
SELECT u.id, u.nombre_usuario, u.nombre_completo, u.comunidad_id, u.activo,
       u.hash_contrasena, r.codigo AS rol, r.nombre AS rol_nombre
FROM usuario u
JOIN rol r ON r.id = u.rol_id
WHERE u.nombre_usuario = %s
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT u.id, …, u.activo, u.hash_contrasena, r.codigo AS rol, r.nombre AS rol_nombre` | El usuario, si está activo, su hash bcrypt y su rol. |
| `FROM usuario u JOIN rol r ON r.id = u.rol_id` | JOIN interno: todo usuario tiene rol (FK NOT NULL). |
| `WHERE u.nombre_usuario = %s` | Parámetro: el nombre que se escribió va aparte del SQL, así que no hay inyección. |
| *¿Y la contraseña?* | La base **nunca** compara la contraseña, porque no la guarda: guarda el hash. Python hace `bcrypt.checkpw(contraseña, hash)`. Si el usuario no existe, compara contra un hash ficticio: tarda lo mismo y el mensaje es el mismo («Usuario o contraseña incorrectos»). Así no se puede adivinar qué usuarios existen. |

**Ejemplo con la semilla:** `verificar_credenciales('operador', …)`.

| id | nombre_usuario | nombre_completo | activo | hash_contrasena | rol | rol_nombre |
|---|---|---|---|---|---|---|
| 2 | operador | Jorge Apaza Huanca | 1 | $2b$12$PYmGm… | operador | Operador |

El hash se acorta aquí: es bcrypt con costo 12 (`$2b$12$…`).

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `u` | `const` | `uk_usuario_nombre` | 1 | — |
| `r` | `const` | `PRIMARY` | 1 | — |

`u` es `const` por `uk_usuario_nombre` (UNIQUE) y `r` es `const` por PRIMARY.

<a id="consulta-13"></a>

### 13. Pagos por verificar (RN-06)

- **Pantalla:** `/panel/pagos` (operador).
- **Dónde está:** `pago.listar_por_verificar(actor)`, en [app/modelos/pago.py:37](../app/modelos/pago.py#L37).
- **Qué hay que saber explicar:** 4 JOIN, subconsulta con `SUM`, cola por fecha.

```sql
SELECT p.id, p.metodo, p.monto, p.numero_operacion, p.reportado_en,
       r.codigo, r.estado AS estado_reserva, r.total, r.vence_en,
       (r.vence_en > NOW()) AS vigente,
       t.nombres, t.apellidos, t.telefono,
       s.fecha_hora_zarpe, ru.nombre AS ruta_nombre,
       COALESCE((SELECT SUM(p2.monto) FROM pago p2
                 WHERE p2.reserva_id = r.id AND p2.estado = 'verificado'), 0) AS pagado
FROM pago p
JOIN reserva r  ON r.id = p.reserva_id
JOIN turista t  ON t.id = r.turista_id
JOIN salida s   ON s.id = r.salida_id
JOIN ruta ru    ON ru.id = s.ruta_id
WHERE p.estado = 'reportado'
ORDER BY p.reportado_en, p.id
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT p.id, p.metodo, p.monto, p.numero_operacion, p.reportado_en` | Lo que reportó el turista: Yape o Plin, el monto y el número de operación, para buscarlo en la app del banco. |
| `r.codigo, r.estado AS estado_reserva, r.total, r.vence_en, (r.vence_en > NOW()) AS vigente` | La reserva y si todavía está a tiempo. |
| `t.nombres, t.apellidos, t.telefono, s.fecha_hora_zarpe, ru.nombre AS ruta_nombre` | Quién paga y para qué viaje. |
| `COALESCE((SELECT SUM(p2.monto) FROM pago p2 WHERE p2.reserva_id = r.id AND p2.estado = 'verificado'), 0) AS pagado` | Lo ya verificado de esa reserva (se puede pagar en partes), o 0 si no hay nada. |
| `FROM pago p JOIN reserva r ON … JOIN turista t ON … JOIN salida s ON … JOIN ruta ru ON …` | 4 JOIN internos: cada pago tiene reserva, cada reserva tiene titular y salida, y cada salida tiene ruta. |
| `WHERE p.estado = 'reportado'` | Solo los pagos que esperan revisión. |
| `ORDER BY p.reportado_en, p.id` | El que llegó primero se revisa primero, como una cola. |

**Ejemplo con la semilla:** `listar_por_verificar(operador)`.

| id | metodo | monto | codigo | estado_reserva | total | vigente | nombres | apellidos | ruta_nombre | pagado |
|---|---|---|---|---|---|---|---|---|---|---|
| 13 | yape | 140.00 | TV-RQCP | pendiente_pago | 140.00 | 1 | Milagros | Cahui Pari | Uros y Taquile | 0.00 |

Hay un solo pago reportado: S/ 140 por Yape para TV-RQCP, que todavía está vigente (`vigente = 1`) y no tiene nada verificado.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `p` | `ref` | `ix_pago_estado` | 1 | Using index condition; Using where; Using filesort |
| `r` | `eq_ref` | `PRIMARY` | 1 | — |
| `s` | `eq_ref` | `PRIMARY` | 1 | — |
| `t` | `eq_ref` | `PRIMARY` | 1 | — |
| `ru` | `eq_ref` | `PRIMARY` | 1 | — |
| `p2` (dependent subquery) | `ref` | `ix_pago_reserva` | 1 | Using where |

`p` es `ref` por `ix_pago_estado`: va directo a los pagos en estado «reportado». Cada JOIN es `eq_ref` por PRIMARY. La subconsulta de lo pagado usa `ix_pago_reserva`.

<a id="consulta-14"></a>

### 14. Manifiesto: los pasajeros de una salida

- **Pantalla:** `/panel/salidas/<id>/pasajeros`, el PDF del manifiesto y la lista para WhatsApp. El guía y el capitán solo ven sus salidas (◐).
- **Dónde está:** `salida.pasajeros_de_salida(actor, salida_id)`, en [app/modelos/salida.py:555](../app/modelos/salida.py#L555).
- **Qué hay que saber explicar:** `LEFT JOIN` (abordaje opcional), subconsulta agrupada, sin N+1.

```sql
SELECT r.codigo, r.estado AS estado_reserva, r.metodo_pago_elegido, r.total,
       COALESCE(pv.pagado, 0) AS pagado,
       rp.id AS pasajero_id, rp.nombres, rp.apellidos, rp.tipo_documento,
       rp.numero_documento, rp.nacionalidad, tp.nombre AS tipo,
       t.nombres AS titular_nombres, t.apellidos AS titular_apellidos,
       t.telefono AS titular_telefono,
       a.registrado_en AS abordo_en, a.metodo AS metodo_abordaje
FROM reserva r
JOIN reserva_pasajero rp ON rp.reserva_id = r.id
JOIN tipo_pasajero tp    ON tp.id = rp.tipo_pasajero_id
JOIN turista t           ON t.id = r.turista_id
LEFT JOIN abordaje a     ON a.reserva_pasajero_id = rp.id AND a.salida_id = r.salida_id
LEFT JOIN (SELECT p.reserva_id, SUM(p.monto) AS pagado
           FROM pago p
           JOIN reserva r2 ON r2.id = p.reserva_id
           WHERE r2.salida_id = %s AND p.estado = 'verificado'
           GROUP BY p.reserva_id) pv ON pv.reserva_id = r.id
WHERE r.salida_id = %s
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
ORDER BY r.codigo, rp.id
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT r.codigo, …, COALESCE(pv.pagado, 0) AS pagado, rp.…, tp.nombre AS tipo, t.… (titular), a.registrado_en AS abordo_en, a.metodo AS metodo_abordaje` | Una fila por pasajero: su reserva, lo pagado, su tipo, el titular y si ya abordó. |
| `FROM reserva r JOIN reserva_pasajero rp ON … JOIN tipo_pasajero tp ON … JOIN turista t ON …` | La reserva, sus pasajeros, el tipo de cada uno y el titular. |
| `LEFT JOIN abordaje a ON a.reserva_pasajero_id = rp.id AND a.salida_id = r.salida_id` | Es LEFT JOIN porque el que todavía no subió no tiene abordaje: sale con `abordo_en` en NULL. Con JOIN interno, la lista solo tendría a los que ya subieron. |
| `LEFT JOIN (SELECT p.reserva_id, SUM(p.monto) AS pagado FROM pago p JOIN reserva r2 ON … WHERE r2.salida_id = %s AND p.estado = 'verificado' GROUP BY p.reserva_id) pv ON pv.reserva_id = r.id` | Subconsulta agrupada: lo pagado por cada reserva de la salida, en **una** consulta y no una por reserva (sin N+1). La reserva sin pagos sale con 0 gracias al LEFT JOIN. |
| `WHERE r.salida_id = %s AND (… estados que ocupan lugar …)` | Solo los pasajeros que tienen lugar (RN-01). |
| `ORDER BY r.codigo, rp.id` | Agrupados por reserva, en el orden en que se escribieron. |

**Ejemplo con la semilla:** `pasajeros_de_salida(operador, 6)`: Uros y Taquile, hoy a las 07:00.

| codigo | estado_reserva | metodo_pago_elegido | total | pagado | nombres | apellidos | tipo | abordo_en |
|---|---|---|---|---|---|---|---|---|
| TV-6DQT | confirmada | muelle | 320.00 | 0.00 | Valentina | Rojas Muñoz | Adulto extranjero | NULL |
| TV-6DQT | confirmada | muelle | 320.00 | 0.00 | Tomás | Rojas Muñoz | Adulto extranjero | NULL |
| TV-6DQT | confirmada | muelle | 320.00 | 0.00 | Isidora | Rojas Vidal | Niño o niña | NULL |
| TV-6DQT | confirmada | muelle | 320.00 | 0.00 | Pedro | Rojas Vidal | Niño o niña | NULL |
| TV-DMT9 | pagada | yape | 120.00 | 120.00 | Carmen Rosa | Torres Villanueva | Adulto nacional | NULL |
| TV-DMT9 | pagada | yape | 120.00 | 120.00 | Mateo | Torres Quispe | Niño o niña | NULL |

TV-6DQT se paga en el muelle (lleva 0 pagado). TV-DMT9 se pagó con Yape en 2 partes de 60 (120 en total). Nadie tiene abordaje registrado en esta salida de la semilla.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `ref` | `ix_reserva_salida_estado` | 4 | Using index condition; Using where; Using temporary; Using filesort |
| `t` | `eq_ref` | `PRIMARY` | 1 | — |
| `rp` | `ref` | `uk_pasajero_documento` | 1 | — |
| `tp` | `eq_ref` | `PRIMARY` | 1 | — |
| `a` | `eq_ref` | `uk_abordaje` | 1 | — |
| `<derived2>` | `ref` | `key0` | 2 | — |
| `p` (lateral derived) | `ref` | `ix_pago_reserva` | 1 | Using index condition; Using where |
| `r2` (lateral derived) | `eq_ref` | `PRIMARY` | 1 | Using where |

`r` es `ref` por `ix_reserva_salida_estado` y `rp` es `ref` por `uk_pasajero_documento`. `tp` y `t` son `eq_ref`. `a` es `eq_ref` por `uk_abordaje` (reserva_pasajero_id, salida_id): el UNIQUE que impide abordar 2 veces también sirve para buscar. La subconsulta de lo pagado aparece como `LATERAL DERIVED` por `ix_pago_reserva`.

<a id="consulta-15"></a>

### 15. Abordaje con QR: la reserva y la ventana de RN-12

- **Pantalla:** `/panel/abordaje/<código>`: lo abre el celular del guía al leer el QR.
- **Dónde está:** `abordaje.buscar(actor, codigo)`, en [app/modelos/abordaje.py:34](../app/modelos/abordaje.py#L34).
- **Qué hay que saber explicar:** 5 JOIN, `BETWEEN` con `INTERVAL`, hora de Lima.

```sql
SELECT r.id, r.codigo, r.estado, r.total, r.metodo_pago_elegido,
       s.id AS salida_id, s.fecha_hora_zarpe, s.estado AS salida_estado,
       s.capitan_id, s.guia_id, ru.nombre AS ruta_nombre,
       e.nombre AS embarcacion_nombre,
       t.nombres, t.apellidos, t.telefono,
       COALESCE((SELECT SUM(p.monto) FROM pago p
                 WHERE p.reserva_id = r.id AND p.estado = 'verificado'), 0) AS pagado,
       (NOW() BETWEEN s.fecha_hora_zarpe - INTERVAL %s MINUTE
                  AND s.fecha_hora_zarpe + INTERVAL %s MINUTE) AS en_ventana,
       (NOW() < s.fecha_hora_zarpe - INTERVAL %s MINUTE) AS antes_de_ventana
FROM reserva r
JOIN salida s      ON s.id = r.salida_id
JOIN ruta ru       ON ru.id = s.ruta_id
JOIN embarcacion e ON e.id = s.embarcacion_id
JOIN turista t     ON t.id = r.turista_id
WHERE r.codigo = %s
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT r.id, r.codigo, r.estado, …, s.capitan_id, s.guia_id, ru.nombre, e.nombre, t.…` | La reserva y su salida (con el capitán y el guía, para revisar el ◐), la ruta, la lancha y el titular. |
| `COALESCE((SELECT SUM(p.monto) … 'verificado'), 0) AS pagado` | Lo pagado. Si falta algo, el guía lo ve antes de dejarlo subir. |
| `(NOW() BETWEEN s.fecha_hora_zarpe - INTERVAL %s MINUTE AND s.fecha_hora_zarpe + INTERVAL %s MINUTE) AS en_ventana` | RN-12: se puede abordar desde 60 minutos antes hasta 15 minutos después del zarpe. Da 1 o 0. `NOW()` es la hora de Lima, porque cada conexión fija `time_zone = '-05:00'`. |
| `(NOW() < s.fecha_hora_zarpe - INTERVAL %s MINUTE) AS antes_de_ventana` | Para elegir el mensaje: «todavía no abre» o «ya cerró». |
| `FROM reserva r JOIN salida s ON … JOIN ruta ru ON … JOIN embarcacion e ON … JOIN turista t ON … WHERE r.codigo = %s` | Todo se busca a partir del código que trae el QR. |

**Ejemplo con la semilla:** `buscar(guía, 'TV-33VR')`, con 60 y 15 minutos.

| codigo | estado | total | salida_id | fecha_hora_zarpe | salida_estado | ruta_nombre | pagado | en_ventana | antes_de_ventana |
|---|---|---|---|---|---|---|---|---|---|
| TV-33VR | pagada | 300.00 | 12 | 2026-10-22 07:00 | programada | Uros, Amantaní y Taquile | 300.00 | 0 | 1 |

La reserva está pagada, pero su salida es pasado mañana a las 07:00: `en_ventana = 0` y `antes_de_ventana = 1`. La pantalla dice «El abordaje abre 60 minutos antes del zarpe».

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `const` | `uk_reserva_codigo` | 1 | — |
| `s` | `const` | `PRIMARY` | 1 | — |
| `ru` | `const` | `PRIMARY` | 1 | — |
| `e` | `const` | `PRIMARY` | 1 | — |
| `t` | `const` | `PRIMARY` | 1 | — |
| `p` (subquery) | `ref` | `ix_pago_reserva` | 1 | Using where |

Todo es `const`: `r` por `uk_reserva_codigo` y las demás por PRIMARY. Son 5 tablas, con 1 fila cada una. La subconsulta usa `ix_pago_reserva`.

<a id="consulta-16"></a>

### 16. ¿La lancha ya tiene otra salida en ese horario? (RN-07)

- **Pantalla:** `/panel/salidas/nueva` y `/panel/salidas/<id>/editar` (operador).
- **Dónde está:** `salida._validar_rn07` (la consulta del cruce), en [app/modelos/salida.py:323](../app/modelos/salida.py#L323).
- **Qué hay que saber explicar:** Cruce de intervalos, `FOR UPDATE` de la lancha.

```sql
SELECT s.fecha_hora_zarpe, r.nombre AS ruta
FROM salida s
JOIN ruta r ON r.id = s.ruta_id
WHERE s.embarcacion_id = %s
  AND s.id <> %s
  AND s.estado NOT IN ('cancelada','suspendida')
  AND s.fecha_hora_zarpe < %s
  AND %s < s.fecha_hora_retorno
ORDER BY s.fecha_hora_zarpe
LIMIT 1
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT s.fecha_hora_zarpe, r.nombre AS ruta` | La salida que choca, para el mensaje de error. |
| `FROM salida s JOIN ruta r ON r.id = s.ruta_id` | Con su ruta. |
| `WHERE s.embarcacion_id = %s` | La misma lancha. |
| `AND s.id <> %s` | Que no sea ella misma (al editar). Al crear se manda 0, que no es ningún id. |
| `AND s.estado NOT IN ('cancelada','suspendida')` | Las salidas canceladas y suspendidas no ocupan la lancha. |
| `AND s.fecha_hora_zarpe < %s AND %s < s.fecha_hora_retorno` | **Cruce de horarios**: la otra zarpa antes de que vuelva la nueva, **y** la nueva zarpa antes de que vuelva la otra. Si una de las 2 condiciones es falsa, una termina antes de que empiece la otra. |
| `ORDER BY s.fecha_hora_zarpe LIMIT 1` | Con una sola basta para mostrar el error. |
| *Antes de esta consulta* | La lancha se bloquea con `SELECT … FROM embarcacion WHERE id = %s FOR UPDATE`. Así, 2 operadores que crean salidas para la misma lancha se revisan de a uno. Además, el trigger `trg_salida_bi` repite la regla en la base. |

**Ejemplo con la semilla:** Una salida nueva para la misma lancha de la salida 10 (lancha 1), mañana de 10:00 a 13:00. Al crear, el id que se manda es 0.

| fecha_hora_zarpe | ruta |
|---|---|
| 2026-10-21 07:00 | Uros y Taquile |

Choca con «Uros y Taquile», que zarpa a las 07:00 y vuelve a las 16:30. El formulario muestra el error junto al campo «Lancha».

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `s` | `range` | `ix_salida_embarcacion_zarpe` | 3 | Using index condition; Using where |
| `r` | `eq_ref` | `PRIMARY` | 1 | — |

`s` es `range` por `ix_salida_embarcacion_zarpe` (embarcacion_id, fecha_hora_zarpe): lee solo las salidas de esa lancha que zarpan antes del retorno. `r` es `eq_ref`.

<a id="consulta-17"></a>

### 17. Las salidas que afecta una alerta, para suspenderlas (RN-11)

- **Pantalla:** `/panel/alertas/<id>` (el botón «Suspender las salidas afectadas»).
- **Dónde está:** `alerta.salidas_afectadas(actor, alerta_id)`, en [app/modelos/alerta.py:107](../app/modelos/alerta.py#L107).
- **Qué hay que saber explicar:** JOIN de una tabla con una vista por horario, `EXISTS`.

```sql
SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.embarcacion_nombre, v.estado,
       v.ocupados, v.cupo
FROM alerta_lago a
JOIN v_disponibilidad_salida v ON v.fecha_hora_zarpe < a.vigente_hasta
                              AND v.fecha_hora_retorno > a.vigente_desde
WHERE a.id = %s
  AND a.nivel IN ('naranja','rojo')
  AND v.estado IN ('programada','embarcando','suspendida')
  AND v.fecha_hora_zarpe > NOW()
  AND (a.comunidad_id IS NULL
       OR EXISTS (SELECT 1 FROM ruta_parada rp
                  WHERE rp.ruta_id = v.ruta_id AND rp.comunidad_id = a.comunidad_id))
ORDER BY v.fecha_hora_zarpe
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT v.salida_id, … v.ocupados, v.cupo` | De la vista: también cuántos pasajeros hay que avisar. |
| `FROM alerta_lago a JOIN v_disponibilidad_salida v ON v.fecha_hora_zarpe < a.vigente_hasta AND v.fecha_hora_retorno > a.vigente_desde` | JOIN por cruce de horarios, como en la consulta 4, pero desde la alerta. |
| `WHERE a.id = %s AND a.nivel IN ('naranja','rojo')` | Esa alerta, y solo si es de las que afectan. |
| `AND v.estado IN ('programada','embarcando','suspendida')` | Las salidas que todavía pueden salir, y las ya suspendidas, para ver qué falta. |
| `AND v.fecha_hora_zarpe > NOW()` | Solo las que no zarparon. |
| `AND (a.comunidad_id IS NULL OR EXISTS (SELECT 1 FROM ruta_parada rp WHERE rp.ruta_id = v.ruta_id AND rp.comunidad_id = a.comunidad_id))` | La alerta es de todo el lago, o la ruta pasa por la comunidad de la alerta. Aquí se escribe con EXISTS; en la consulta 4, con IN. Las 2 formas dicen lo mismo. |
| `ORDER BY v.fecha_hora_zarpe` | La más próxima primero. |

**Ejemplo con la semilla:** `salidas_afectadas(operador, 1)`: oleaje naranja en Amantaní, hasta el 22/10 a las 06:00.

| salida_id | fecha_hora_zarpe | ruta_nombre | embarcacion_nombre | estado | ocupados | cupo |
|---|---|---|---|---|---|---|
| 9 | 2026-10-21 07:00 | Uros, Amantaní y Taquile | Mama Qota | suspendida | 2 | 20 |

Sale la salida 9, que ya está suspendida. La 12 (Uros, Amantaní y Taquile) zarpa el 22/10 a las 07:00, cuando la alerta ya terminó, así que no sale.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `a` | `const` | `PRIMARY` | 1 | Using temporary; Using filesort |
| `r` | `ALL` | — | 5 | Using where |
| `s` | `ref` | `ix_salida_ruta_zarpe` | 1 | Using index condition; Using where |
| `e` | `eq_ref` | `PRIMARY` | 1 | — |
| `<derived4>` | `ref` | `key0` | 2 | — |
| `re` (lateral derived) | `ref` | `ix_reserva_salida_estado` | 1 | Using index condition; Using where |
| `rp` (lateral derived) | `ref` | `uk_pasajero_documento` | 1 | Using index |
| `rp` (materialized) | `index` | `uk_parada_comunidad` | 10 | Using index |

`a` es `const` por PRIMARY. La vista se resuelve con `ix_salida_ruta_zarpe`, y el conteo con `LATERAL DERIVED` por `ix_reserva_salida_estado`. El EXISTS aparece como `MATERIALIZED`: lee una vez las 10 paradas, solo del índice `uk_parada_comunidad`.

<a id="consulta-18"></a>

### 18. Transparencia comunitaria: ingresos por familia y por comunidad

- **Pantalla:** `/panel/hospedajes/transparencia?mes=AAAA-MM` (admin y operador; sección 8.1).
- **Dónde está:** `hospedaje.transparencia(actor, mes)`, en [app/modelos/hospedaje.py:319](../app/modelos/hospedaje.py#L319).
- **Qué hay que saber explicar:** `LEFT JOIN` con condición en el `ON`, `SUM() OVER (PARTITION BY …)`.

```sql
SELECT c.id AS comunidad_id, c.nombre AS comunidad, f.id AS familia_id,
       f.nombre_familia, f.activa,
       COALESCE(v.noches, 0)             AS noches,
       COALESCE(v.personas_noche, 0)     AS personas_noche,
       COALESCE(v.monto, 0)              AS monto,
       COALESCE(v.noches_por_cumplir, 0) AS noches_por_cumplir,
       COALESCE(v.monto_por_cumplir, 0)  AS monto_por_cumplir,
       SUM(COALESCE(v.monto, 0)) OVER (PARTITION BY c.id) AS monto_comunidad,
       SUM(COALESCE(v.noches, 0) + COALESCE(v.noches_por_cumplir, 0))
           OVER (PARTITION BY c.id) AS noches_comunidad
FROM familia_anfitriona f
JOIN comunidad c ON c.id = f.comunidad_id
LEFT JOIN v_ingresos_familia v ON v.familia_id = f.id AND v.mes = %s
WHERE c.tiene_hospedaje = 1 AND (f.activa = 1 OR v.familia_id IS NOT NULL)
ORDER BY c.nombre, f.nombre_familia
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT c.id …, f.id, f.nombre_familia, f.activa` | Cada familia con su comunidad. |
| `COALESCE(v.noches, 0) AS noches, … COALESCE(v.monto_por_cumplir, 0)` | Los datos de la vista `v_ingresos_familia`, que agrupa los hospedajes por mes y familia: noches y monto ya cumplidos, y lo asignado que falta cumplir. La familia sin hospedajes ese mes sale con 0. |
| `SUM(COALESCE(v.monto, 0)) OVER (PARTITION BY c.id) AS monto_comunidad` | **Función de ventana**: suma los montos de todas las familias de la **misma** comunidad (`PARTITION BY` = por grupo) y pone ese total en cada fila, sin juntarlas. En la misma tabla se ve cuánto recibió cada familia y cuánto recibió su comunidad. |
| `SUM(COALESCE(v.noches, 0) + COALESCE(v.noches_por_cumplir, 0)) OVER (PARTITION BY c.id) AS noches_comunidad` | Lo mismo con las noches: cumplidas más por cumplir. |
| `FROM familia_anfitriona f JOIN comunidad c ON c.id = f.comunidad_id` | Se parte de las **familias**, no de los hospedajes. Así aparecen también las que no recibieron a nadie, que es lo que hace visible la rotación. |
| `LEFT JOIN v_ingresos_familia v ON v.familia_id = f.id AND v.mes = %s` | El mes va en el **ON**, no en el WHERE. En el WHERE, `v.mes = '2026-10'` sacaría a las familias que no tienen fila en la vista (su `v.mes` es NULL), y el LEFT JOIN ya no serviría. |
| `WHERE c.tiene_hospedaje = 1 AND (f.activa = 1 OR v.familia_id IS NOT NULL)` | Solo las comunidades con hospedaje. Las familias activas, y las inactivas solo si tuvieron noches ese mes. |
| `ORDER BY c.nombre, f.nombre_familia` | Por comunidad y por familia. |

**Ejemplo con la semilla:** `transparencia(operador, '2026-10')`.

| comunidad | nombre_familia | noches | personas_noche | monto | noches_por_cumplir | monto_por_cumplir | monto_comunidad | noches_comunidad |
|---|---|---|---|---|---|---|---|---|
| Amantaní | Familia Huatta Calsin | 0 | 0 | 0.00 | 1 | 80.00 | 200.00 | 5 |
| Amantaní | Familia Mamani Yucra | 1 | 2 | 80.00 | 0 | 0.00 | 200.00 | 5 |
| Amantaní | Familia Pacompía Ccalla | 0 | 0 | 0.00 | 1 | 80.00 | 200.00 | 5 |
| Amantaní | Familia Quispe Cruz | 1 | 3 | 120.00 | 1 | 40.00 | 200.00 | 5 |
| Llachón | Familia Cahuana Charca | 1 | 2 | 80.00 | 0 | 0.00 | 80.00 | 2 |
| Llachón | Familia Flores Mamani | 0 | 0 | 0.00 | 1 | 80.00 | 80.00 | 2 |
| Llachón | Familia Turpo Coila | 0 | 0 | 0.00 | 0 | 0.00 | 80.00 | 2 |
| Luquina Chico | Familia Choque Ari | 0 | 0 | 0.00 | 0 | 0.00 | 0.00 | 0 |
| Taquile | Familia Huatta Machaca | 0 | 0 | 0.00 | 0 | 0.00 | 0.00 | 0 |

Amantaní tiene 2 noches cumplidas: Quispe Cruz con 120.00 y Mamani Yucra con 80.00, así que la comunidad suma 200.00. Además tiene 3 noches por cumplir. Turpo Coila, Choque Ari y Huatta Machaca no recibieron a nadie y aparecen con 0: justo lo que el reporte tiene que mostrar. El monto es personas × S/ 40 por noche (P3).

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `f` | `ALL` | — | 10 | Using temporary; Using filesort |
| `c` | `eq_ref` | `PRIMARY` | 1 | Using where |
| `<derived2>` | `ref` | `key0` | 2 | Using where |
| `h` (derived) | `ALL` | — | 9 | Using where; Using temporary; Using filesort |
| `f` (derived) | `eq_ref` | `PRIMARY` | 1 | — |
| `c` (derived) | `eq_ref` | `PRIMARY` | 1 | — |

`f` es `ALL` (10 familias) y `c` es `eq_ref`. La vista se calcula una vez (`DERIVED`: agrupa los 9 hospedajes con `Using temporary`) y se une por `key0`. Para cuando crezca está `ix_hospedaje_familia_noche`.

<a id="consulta-19"></a>

### 19. Ocupación por ruta con su puesto

- **Pantalla:** `/panel/indicadores` (admin y operador).
- **Dónde está:** `indicadores.ocupacion_por_ruta(actor, dias)`, en [app/modelos/indicadores.py:17](../app/modelos/indicadores.py#L17).
- **Qué hay que saber explicar:** `GROUP BY` con `SUM`, `RANK() OVER`.

```sql
SELECT v.ruta_id, v.ruta_nombre, COUNT(*) AS salidas,
       SUM(v.ocupados) AS ocupados, SUM(v.cupo) AS cupo,
       ROUND(100 * SUM(v.ocupados) / SUM(v.cupo), 1) AS ocupacion,
       RANK() OVER (ORDER BY SUM(v.ocupados) / SUM(v.cupo) DESC) AS puesto
FROM v_disponibilidad_salida v
WHERE v.estado <> 'cancelada'
  AND v.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY
GROUP BY v.ruta_id, v.ruta_nombre
ORDER BY puesto, v.ruta_nombre
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT v.ruta_id, v.ruta_nombre, COUNT(*) AS salidas` | Por ruta: cuántas salidas tiene. |
| `SUM(v.ocupados) AS ocupados, SUM(v.cupo) AS cupo` | Pasajeros y lugares, sumando todas sus salidas. |
| `ROUND(100 * SUM(v.ocupados) / SUM(v.cupo), 1) AS ocupacion` | El % de ocupación, con 1 decimal. Se divide la suma de los ocupados entre la suma de los cupos. No se promedian porcentajes: una salida de 25 lugares pesa más que una de 18. |
| `RANK() OVER (ORDER BY SUM(v.ocupados) / SUM(v.cupo) DESC) AS puesto` | Función de ventana sobre el resultado **ya agrupado**: numera las rutas de mayor a menor ocupación. Si 2 empatan, comparten el puesto. |
| `FROM v_disponibilidad_salida v WHERE v.estado <> 'cancelada' AND v.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY` | Las salidas no canceladas desde hace N días, y las que vienen. |
| `GROUP BY v.ruta_id, v.ruta_nombre` | Junta las salidas de una misma ruta: queda una fila por ruta. |
| `ORDER BY puesto, v.ruta_nombre` | Del mejor puesto al peor. |

**Ejemplo con la semilla:** `ocupacion_por_ruta(operador, 30)`: los últimos 30 días (lo que muestra el panel si no se elige otro periodo).

| ruta_id | ruta_nombre | salidas | ocupados | cupo | ocupacion | puesto |
|---|---|---|---|---|---|---|
| 1 | Islas flotantes de los Uros | 4 | 18 | 72 | 25.0 | 1 |
| 2 | Uros y Taquile | 3 | 14 | 75 | 18.7 | 2 |
| 3 | Uros, Amantaní y Taquile | 3 | 10 | 60 | 16.7 | 3 |
| 4 | Llachón vivencial | 2 | 4 | 32 | 12.5 | 4 |
| 5 | Uros y Luquina Chico | 1 | 3 | 25 | 12.0 | 5 |

Islas flotantes de los Uros: 4 salidas, 18 pasajeros en 72 lugares, o sea 25.0 % y el puesto 1.

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `ALL` | — | 5 | Using temporary; Using filesort |
| `s` | `ref` | `ix_salida_ruta_zarpe` | 1 | Using index condition; Using where |
| `e` | `eq_ref` | `PRIMARY` | 1 | Using index |
| `<derived3>` | `ref` | `key0` | 2 | — |
| `re` (lateral derived) | `ref` | `ix_reserva_salida_estado` | 1 | Using index condition; Using where |
| `rp` (lateral derived) | `ref` | `uk_pasajero_documento` | 1 | Using index |

Se lee la vista: `ruta` es `ALL` (5 filas) y, por cada ruta, sus salidas con `ix_salida_ruta_zarpe`; los ocupados con `LATERAL DERIVED` y `ix_reserva_salida_estado`. `Using temporary; Using filesort` aparece porque el GROUP BY y el RANK necesitan una tabla temporal, lo normal en un reporte.

<a id="consulta-20"></a>

### 20. Rutas con poca ocupación

- **Pantalla:** `/panel/indicadores` (el recuadro «Rutas con menos de 50 %»).
- **Dónde está:** `indicadores.rutas_con_poca_ocupacion(actor, dias, umbral=50)`, en [app/modelos/indicadores.py:37](../app/modelos/indicadores.py#L37).
- **Qué hay que saber explicar:** `HAVING` frente a `WHERE`.

```sql
SELECT v.ruta_nombre, COUNT(*) AS salidas,
       ROUND(100 * SUM(v.ocupados) / SUM(v.cupo), 1) AS ocupacion
FROM v_disponibilidad_salida v
WHERE v.estado <> 'cancelada'
  AND v.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY
GROUP BY v.ruta_id, v.ruta_nombre
HAVING 100 * SUM(v.ocupados) / SUM(v.cupo) < %s
ORDER BY ocupacion
```

**Línea por línea**

| Parte de la consulta | Qué hace y por qué |
|---|---|
| `SELECT v.ruta_nombre, COUNT(*) AS salidas, ROUND(…) AS ocupacion` | Igual que la consulta 19. |
| `WHERE v.estado <> 'cancelada' AND v.fecha_hora_zarpe >= …` | WHERE filtra **filas** (salidas), antes de agrupar. |
| `GROUP BY v.ruta_id, v.ruta_nombre` | Una fila por ruta. |
| `HAVING 100 * SUM(v.ocupados) / SUM(v.cupo) < %s` | HAVING filtra **grupos** (rutas), después de agrupar: quedan solo las rutas con ocupación menor al umbral. En el WHERE no se puede usar SUM, porque cuando se aplica el WHERE todavía no hay grupos. |
| `ORDER BY ocupacion` | La peor primero. Se puede ordenar por el alias de la columna. |

**Ejemplo con la semilla:** `rutas_con_poca_ocupacion(operador, 30, 50)`.

| ruta_nombre | salidas | ocupacion |
|---|---|---|
| Uros y Luquina Chico | 1 | 12.0 |
| Llachón vivencial | 2 | 12.5 |
| Uros, Amantaní y Taquile | 3 | 16.7 |
| Uros y Taquile | 3 | 18.7 |
| Islas flotantes de los Uros | 4 | 25.0 |

Salen las 5 rutas, porque la semilla tiene poca ocupación. Con un umbral de 15 solo quedarían Uros y Luquina Chico (12.0) y Llachón vivencial (12.5).

**Índice (EXPLAIN)**

| Tabla | type | Índice que usa (key) | rows | Extra |
|---|---|---|---|---|
| `r` | `ALL` | — | 5 | Using temporary; Using filesort |
| `s` | `ref` | `ix_salida_ruta_zarpe` | 1 | Using index condition; Using where |
| `e` | `eq_ref` | `PRIMARY` | 1 | Using index |
| `<derived3>` | `ref` | `key0` | 2 | — |
| `re` (lateral derived) | `ref` | `ix_reserva_salida_estado` | 1 | Using index condition; Using where |
| `rp` (lateral derived) | `ref` | `uk_pasajero_documento` | 1 | Using index |

Es el mismo plan que el de la consulta 19. El HAVING no cambia cómo se leen las tablas: se aplica al final, sobre las 5 filas ya agrupadas.
