# Fase 6 · Innovación para Puno

La F6 suma lo que la sección 8 llama "lo innovador":

- alertas del lago que suspenden salidas en un solo paso, con reprogramación o devolución para el turista;
- rotación de familias con reasignación y un reporte de transparencia comunitaria;
- reseñas moderadas;
- un panel de indicadores;
- las páginas del turista en inglés.

## 1. Qué hicimos

**Alertas y suspensión (RN-11)**

- En `/panel/alertas`, el operador registra a mano los avisos de SENAMHI, de la Capitanía, de la agencia o de la comunidad (sin scraping). El admin solo mira.
- Cada alerta naranja o roja muestra las **salidas afectadas**: las que todavía no zarpan, se cruzan con su horario y pasan por su comunidad (o cualquiera, si es de todo el lago).
- El botón «Suspender las N salidas en un solo paso» las suspende en **una transacción** (D-82): o todas, o ninguna.
- El trigger anota cada cambio con el operador y su IP, y el modelo anota la suspensión en bloque.

**Reprogramar o pedir la devolución (turista)**

- Con la salida suspendida, la reserva muestra **«Reprogramar o pedir la devolución»**. Antes, el turista se identifica en "Mi reserva".
- **Reprogramar** (`/reservas/<código>/reprogramar`):
  - ofrece las salidas de la **misma ruta** que tienen lugar para todo el grupo, y avisa si alguna tiene alerta;
  - actualiza **la misma reserva** (D-04): el código, los pagos, los precios y el boleto siguen valiendo;
  - bloquea las dos salidas en orden de id y vuelve a contar el cupo (RN-02) y los documentos (RN-09);
  - si cambia la noche, la vieja pasa a `cancelado` y se asigna una familia por rotación (D-83).
- **Devolución** (`/reservas/<código>/devolucion`):
  - la reserva pasa a `cancelada` y su noche a `cancelado`;
  - queda `devolucion_solicitada` en la bitácora, con el monto verificado (D-11, D-84);
  - el operador la ve en **Pagos → Devoluciones por atender** y la marca como devuelta, con una nota.

**Hospedajes y transparencia (RN-10, sección 8.1)**

- `/panel/hospedajes` muestra las noches desde una fecha, las **reservas con noche y sin familia** (ver D-69) y las acciones:
  - **Reasignar**: la familia nueva se elige entre las libres, en el orden de la rotación (la que toca viene marcada). El motivo es obligatorio y queda en la bitácora (D-85).
  - **Asignar familia por rotación**, para la reserva que quedó sin familia.
  - **Confirmar que se cumplió**: una noche que ya pasó, de una reserva que abordó, pasa a `cumplido` (D-86).
- `/panel/hospedajes/transparencia?mes=AAAA-MM` es el reporte por comunidad y por familia: noches cumplidas, personas-noche, monto, y lo que está por cumplir. Aparecen **también las familias sin noches** y los totales de cada comunidad. Se puede imprimir para la asamblea (D-87).

**Reseñas (RN-13)**

- El turista opina en `/reservas/<código>/resena`: solo si la reserva fue `abordada`, después de la hora de retorno, y una sola vez (D-88).
- El operador las modera en `/panel/resenas`.
- Las publicadas se ven en el detalle de cada salida: el promedio de la ruta, las estrellas y el comentario, sin nombres (solo el país y el mes del viaje).

**Indicadores (sección 8.8)**

`/panel/indicadores`, para el admin y el operador, con un periodo de 30, 90 o 365 días (D-89):

- ocupación por ruta, con su puesto (`RANK() OVER`);
- rutas con menos de 50 % de ocupación (`HAVING`);
- ingresos por método de pago, con su parte del total (`SUM(SUM(...)) OVER ()`);
- nacionalidades;
- noches por familia, con el promedio de su comunidad (`AVG() OVER (PARTITION BY ...)`, `LEFT JOIN` a una subconsulta agrupada).

Las barras son SVG propios (la CSP no deja estilos en línea) y cada gráfico tiene su tabla con los números.

**Inglés (sección 8.9)**

- El turista elige **English / Español** en la cabecera. Queda guardado en su sesión (`/idioma/<es|en>`).
- Se traducen las páginas públicas y de reservas, los formularios, los mensajes de error del modelo, las páginas de error, las fechas y el boleto PDF.
- El idioma elegido queda en `turista.idioma` y `resena.idioma`.
- El panel queda en español.
- Los textos que vienen de la base (nombres y descripciones de rutas y comunidades, tipos de pasajero, países) quedan en español: no tienen columna en inglés (D-90, PR-13).

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `app/modelos/alerta.py` | Lista, registrar, salidas afectadas y `suspender_afectadas` (una transacción). |
| `app/modelos/reprogramacion.py` (nuevo) | Opciones, reprogramar, pedir la devolución y devoluciones por atender. |
| `app/modelos/hospedaje.py` | Lista, candidatas por rotación, reasignar, asignar la que falta, cumplida y transparencia. |
| `app/modelos/resena.py`, `indicadores.py` (nuevos) | Reseñas (crear, moderar, publicadas) y los 5 indicadores. |
| `app/rutas/panel_seguimiento.py` (nuevo) | 12 rutas del panel: alertas, hospedajes, transparencia, reseñas, indicadores y devoluciones (D-91). |
| `app/rutas/reservas.py`, `publico.py` | Reprogramar, devolución, reseña, `/idioma` y las opiniones en el detalle. Todo con `t()`. |
| `app/servicios/textos.py`, `textos_en.py` (nuevos) | `t()`, `mensaje()`, `traducir_formulario()` y el diccionario español → inglés (355 textos y 7 patrones). |
| `app/servicios/formato.py`, `pdf.py`, `app/errores.py`, `app/__init__.py` | Fechas y etiquetas por idioma, boleto PDF en inglés, errores traducidos e idioma de cada petición. |
| `app/formularios/panel.py`, `reserva.py` | Alerta, reasignar, nota de devolución, reprogramar y reseña. |
| `app/plantillas/panel/*` (7 nuevas), `reservas/*` (2 nuevas), `publico/*`, `base.html`, `macros*.html` | Páginas nuevas y textos con `t()`. |
| `tests/test_reglas_f6.py`, `tests/test_rutas_f6.py` (nuevos) | 41 pruebas nuevas. |

## 3. Comandos para probarlo

```powershell
flask bd reiniciar --si
flask run
pytest -v --cov=app/modelos           # 433 pruebas
ruff check .
```

Recorrido sugerido:

1. **operador** → *Alertas* → *Registrar alerta*: roja, «Todo el lago», desde mañana 06:00 hasta mañana 18:00. En la alerta aparecen las salidas afectadas: *Suspender en un solo paso*.
2. En una ventana de incógnito, abrir una reserva de esas salidas con "Mi reserva". Se ve «Tu salida está suspendida» → *Reprogramar* → elegir otra salida. El código y el boleto siguen iguales.
3. Con otra reserva suspendida, *Pedir la devolución*. En el panel, *Pagos → Devoluciones por atender* → *Marcar como devuelta*.
4. *Hospedajes* → *Reasignar* una noche (con su motivo) → *Reporte de transparencia*.
5. Arriba a la derecha, **English**: la portada, una salida (con las opiniones) y el formulario de reserva quedan en inglés. Un DNI de 3 dígitos muestra «A DNI has 8 digits.».
6. **admin** → *Indicadores* → 365 días.

## 4. Evidencia (20/10/2026)

- `pytest -v --cov=app/modelos`: **433 passed in 85 s**, con **91 %** de cobertura en `app/modelos` → [evidencias/f6-pytest.txt](evidencias/f6-pytest.txt).
  - 20 pruebas de reglas:
    - la alerta suspende solo las salidas afectadas, en un paso;
    - la amarilla solo informa;
    - reprogramar respeta el cupo, la ruta y la noche;
    - devolución y su atención;
    - reasignar con motivo, asignar la que falta y cumplida;
    - la transparencia incluye a las familias sin noches;
    - reseñas: una vez y moderadas;
    - indicadores con `RANK`, `HAVING` y ventanas.
  - 21 pruebas de rutas:
    - la matriz de permisos de las 7 páginas nuevas;
    - los flujos por formulario;
    - el inglés: cambio y vuelta, solo páginas internas, el panel sigue en español, mensajes del modelo y página 404;
    - **cada `t('…')` de las plantillas del turista tiene su traducción**.
- `ruff check .`: *All checks passed!*
- En el navegador (app local):
  - salida y opiniones en inglés (375 px) → [salida](evidencias/f6-salida-en-ingles-celular.jpg), [opiniones](evidencias/f6-opiniones-en-ingles-celular.jpg);
  - TV-GPJN reprogramada de la salida suspendida a la del día siguiente, en inglés → [f6-reprogramar-en-ingles-celular.jpg](evidencias/f6-reprogramar-en-ingles-celular.jpg). Se le asignó la familia de la nueva noche;
  - [indicadores](evidencias/f6-indicadores.jpg), [alertas](evidencias/f6-alertas.jpg) y [transparencia](evidencias/f6-transparencia.jpg).

  Después se reinició la base a la semilla (269 filas).
- Lo que se corrigió en esa revisión:
  - las fechas en inglés salían como «Tuesday, october 20» (`capitalize` de Jinja), D-92;
  - la limpieza de las pruebas no podía borrar una salida de la que se reprogramó una reserva.

## 5. Pendientes

- **Confirmar con Giant Trip**:
  - si las reseñas pueden mostrar el nombre de pila del turista (hoy solo el país y el mes);
  - si la familia cobra cuando el turista no se presenta (abierto desde la F5).
- **Propuestas nuevas** (en [decisiones.md](decisiones.md)):
  - PR-12: una versión pública del reporte de transparencia por comunidad;
  - PR-13: columnas en inglés para los textos de la base;
  - PR-14: avisar a los turistas afectados por una suspensión con un enlace wa.me.
- **F7**: seguridad, accesibilidad, pesos de página y EXPLAIN, la prueba mutante y la cobertura.

---

## Para explicar al docente

### 1. Suspender en un solo paso todas las salidas que afecta una alerta (RN-11)

```sql
-- Devuelve (y BLOQUEA, en orden de id) las salidas programadas que todavía no zarpan,
-- se cruzan con la alerta y pasan por su comunidad (o cualquiera, si es de todo el lago).
SELECT s.id
FROM salida s
WHERE s.estado IN ('programada','embarcando')
  AND s.fecha_hora_zarpe > NOW()
  AND s.fecha_hora_zarpe < %s            -- empieza antes de que termine la alerta…
  AND s.fecha_hora_retorno > %s          -- …y termina después de que empieza
  AND (%s IS NULL
       OR EXISTS (SELECT 1 FROM ruta_parada rp
                  WHERE rp.ruta_id = s.ruta_id AND rp.comunidad_id = %s))
ORDER BY s.id
FOR UPDATE;

UPDATE salida SET estado = 'suspendida', motivo_estado = %s WHERE id IN (%s, %s, …);
```

- **Se cruzan** si cada horario empieza antes de que termine el otro: es la misma regla que el cruce de lanchas de la F5.
- `%s IS NULL OR EXISTS (…)` cubre los dos casos:
  - una alerta de todo el lago (`comunidad_id` NULL) afecta a todas las salidas;
  - una de una comunidad afecta solo a las rutas que paran allí. **EXISTS** es verdadero si encuentra al menos una parada.
- `FOR UPDATE` en **orden de id**: nadie reserva ni edita esas salidas mientras tanto, y dos procesos que bloquean las mismas filas lo hacen en el mismo orden, así no se esperan en círculo.
- El `UPDATE … IN (…)` lleva una marca `%s` por id. Todo va en una transacción: si algo falla, **ROLLBACK** y no se suspende ninguna. El trigger `trg_salida_au` anota cada salida en la bitácora.

### 2. Reporte de transparencia: LEFT JOIN y SUM() OVER (PARTITION BY …)

```sql
-- Devuelve cada familia (también las que no recibieron a nadie) con sus noches y montos del mes,
-- y los totales de SU comunidad sin agrupar otra vez (función de ventana).
SELECT c.nombre AS comunidad, f.nombre_familia,
       COALESCE(v.noches, 0) AS noches, COALESCE(v.monto, 0) AS monto,
       COALESCE(v.noches_por_cumplir, 0) AS noches_por_cumplir,
       SUM(COALESCE(v.monto, 0)) OVER (PARTITION BY c.id) AS monto_comunidad
FROM familia_anfitriona f
JOIN comunidad c ON c.id = f.comunidad_id
LEFT JOIN v_ingresos_familia v ON v.familia_id = f.id AND v.mes = %s
WHERE c.tiene_hospedaje = 1 AND (f.activa = 1 OR v.familia_id IS NOT NULL)
ORDER BY c.nombre, f.nombre_familia;
```

- **LEFT JOIN**: una familia sin noches en el mes **igual aparece**, con 0. Para la transparencia es clave: se ve quién no recibió turistas.
- La condición del mes (`v.mes = %s`) va en el **ON** y no en el WHERE. En el WHERE convertiría el LEFT JOIN en un JOIN común y desaparecerían las familias con 0.
- `SUM(...) OVER (PARTITION BY c.id)` suma el monto de **todas las familias de la misma comunidad** y lo pone en cada fila. A diferencia de GROUP BY, no junta las filas: se ve cada familia y también el total de su comunidad.
- `v_ingresos_familia` es la vista de la F1: agrupa los hospedajes por mes, comunidad y familia, y separa lo cumplido de lo asignado.

### 3. Ocupación por ruta: GROUP BY, RANK() OVER y HAVING

```sql
-- Devuelve, por ruta, salidas, pasajeros, cupo y % de ocupación, con su puesto.
SELECT v.ruta_nombre, COUNT(*) AS salidas, SUM(v.ocupados) AS ocupados, SUM(v.cupo) AS cupo,
       ROUND(100 * SUM(v.ocupados) / SUM(v.cupo), 1) AS ocupacion,
       RANK() OVER (ORDER BY SUM(v.ocupados) / SUM(v.cupo) DESC) AS puesto
FROM v_disponibilidad_salida v
WHERE v.estado <> 'cancelada' AND v.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY
GROUP BY v.ruta_id, v.ruta_nombre;

-- Solo las rutas con poca ocupación: HAVING filtra DESPUÉS de agrupar.
… GROUP BY v.ruta_id, v.ruta_nombre
HAVING 100 * SUM(v.ocupados) / SUM(v.cupo) < %s;
```

- **GROUP BY** junta las salidas de cada ruta. `SUM` y `COUNT` trabajan sobre cada grupo.
- **RANK() OVER (ORDER BY …)** numera las rutas ya agrupadas por su ocupación. Si dos empatan, comparten el puesto.
- **WHERE vs HAVING**: WHERE filtra **filas** antes de agrupar (no puede usar `SUM`); HAVING filtra **grupos** después (sí puede).
- `ocupados` sale de la vista `v_disponibilidad_salida` (RN-01): solo cuentan las reservas que ocupan lugar.

### 4. Reseñas publicadas con su promedio: AVG() OVER () antes del LIMIT

```sql
-- Devuelve las últimas reseñas publicadas de la ruta, con el país y la fecha (sin nombres),
-- y el promedio y el total de TODAS las publicadas.
SELECT re.puntuacion, re.comentario, re.idioma, t.nacionalidad, s.fecha_hora_zarpe,
       AVG(re.puntuacion) OVER () AS promedio, COUNT(*) OVER () AS total
FROM resena re
JOIN reserva r ON r.id = re.reserva_id
JOIN salida s  ON s.id = r.salida_id
JOIN turista t ON t.id = r.turista_id
WHERE s.ruta_id = %s AND re.estado = 'publicada'
ORDER BY re.creada_en DESC
LIMIT 5;
```

- La reseña es de una **reserva**. Para llegar a su **ruta** se encadenan reserva → salida → ruta (`s.ruta_id`).
- `OVER ()` sin nada adentro es una ventana sobre **todas** las filas del resultado. Se calcula **antes** del LIMIT: aunque se muestren 5 reseñas, el promedio y el total son los de todas las publicadas. Con una sola consulta se tienen la lista y el resumen.
- Solo se muestran `nacionalidad` y la fecha: el nombre del turista no sale (privacidad).

### 5. Devoluciones por atender: NOT EXISTS sobre la bitácora

```sql
-- Devuelve las devoluciones pedidas que todavía no se atendieron, con el titular y lo pagado.
SELECT b.registro_id AS reserva_id, r.codigo, t.nombres, t.apellidos, t.telefono,
       COALESCE((SELECT SUM(p.monto) FROM pago p
                 WHERE p.reserva_id = r.id AND p.estado = 'verificado'), 0) AS pagado
FROM bitacora b
JOIN reserva r ON r.id = b.registro_id
JOIN turista t ON t.id = r.turista_id
WHERE b.accion = 'devolucion_solicitada' AND b.tabla_afectada = 'reserva'
  AND NOT EXISTS (SELECT 1 FROM bitacora b2
                  WHERE b2.accion = 'devolucion_atendida'
                    AND b2.tabla_afectada = 'reserva'
                    AND b2.registro_id = b.registro_id)
ORDER BY b.creado_en;
```

- D-11 decidió no agregar columnas: la devolución vive en la **bitácora**. Una pedida (`devolucion_solicitada`) está pendiente mientras no exista su `devolucion_atendida`.
- **NOT EXISTS** con una subconsulta **correlacionada** (`b2.registro_id = b.registro_id`): para cada pedido busca si ya se atendió esa misma reserva.
- La subconsulta del SELECT suma lo **verificado** (lo que hay que devolver). Va en el SELECT porque devuelve un solo número por fila.
- El índice `ix_bitacora_registro (tabla_afectada, registro_id)` de la F1 hace rápida esta búsqueda.
