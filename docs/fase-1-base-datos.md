# Fase 1 · Base de datos (nivel Bronce)

> Estado: entregada el 19/10/2026. Espera el "ok" del equipo para pasar a la F2.

## 1. Qué hicimos

- **20 tablas** con PK, FK (con índice), CHECK, UNIQUE y ENUM, en InnoDB con `utf8mb4_spanish_ci` (`01_esquema.sql`).
- **2 vistas, 4 triggers y 1 procedimiento** (`02_vistas_triggers.sql`):
  - `v_disponibilidad_salida` (RN-01 y RN-08) y `v_ingresos_familia` (transparencia);
  - un trigger de sobreventa con documento repetido, dos de reglas de salida y uno que escribe en la bitácora;
  - el procedimiento `pr_validar_salida` reúne la regla RN-07 para no escribirla dos veces.
- **Semilla coherente** (`03_datos.sql`), con 269 filas:
  - todas las tablas tienen 5 filas o más, salvo `rol`, que tiene 4 (ver D-15);
  - las fechas salen de `CURDATE()`: siempre hay salidas hoy, mañana y pasado mañana;
  - los precios de los pasajeros se calculan con la misma regla RN-04, no se escriben a mano;
  - hay reservas en los 7 estados, pagos parciales, uno rechazado y uno reportado, una alerta naranja vigente que suspendió una salida, una reprogramación, una devolución solicitada (P4), reseñas en los 3 estados y bitácora.
- **Hash bcrypt** generados por `scripts/generar_hashes.py` y escritos en el `.sql`, para importar en phpMyAdmin sin ejecutar Python.
- **`flask bd reiniciar`** (y `flask bd contar`), con una app mínima: `crear_app`, `config.py` y `bd.py` (una conexión por petición en `flask.g`, autocommit apagado y transacciones explícitas).
- **`99_consultas_prueba.sql`**: el conteo por tabla, un SELECT * de cada tabla, las 2 vistas y 5 consultas con JOIN.
- **112 pruebas automáticas** de la base: CHECK, ENUM estricto, FK, CASCADE, UNIQUE, triggers, vistas, semilla y comandos.

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `database/00_crear_bd_usuario.sql` | Crea las 2 bases y el usuario `titicaca_app`, como root y una sola vez. |
| `database/01_esquema.sql` | Las 20 tablas. |
| `database/02_vistas_triggers.sql` | Las vistas, los triggers y el procedimiento. |
| `database/03_datos.sql` | La semilla. |
| `database/99_consultas_prueba.sql` | La evidencia de Bronce. |
| `scripts/generar_hashes.py` | Los hash bcrypt de los usuarios demo. |
| `app/__init__.py`, `app/config.py`, `app/bd.py`, `app/comandos.py` | La app mínima y `flask bd …`. |
| `tests/` (5 archivos) | Las pruebas de la base. |
| `.env.example`, `.flaskenv`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `README.md` | Configuración y guía de instalación. |
| `docs/desafio-niveles.md`, `docs/evidencias/f1-*.txt` | Evidencia del nivel Bronce. |
| `docs/modelo-datos.md`, `docs/decisiones.md` | Actualizados con las respuestas P1–P5 y las decisiones de la F1. |

## 3. Comandos para probarlo

Desde `titicaca_vivo`, con el venv activo y el `.env` configurado (ver el README):

```powershell
flask bd reiniciar --si        # crea y siembra titicaca_vivo
flask bd contar                # filas por tabla
pytest -v                      # 112 pruebas, contra titicaca_vivo_pruebas
ruff check .
```

En phpMyAdmin, importa `01`, `02` y `03` en orden sobre la base `titicaca_vivo` y luego ejecuta `99_consultas_prueba.sql`.

## 4. Evidencia

Todo se ejecutó el 19/10/2026 en esta PC, con MariaDB **10.4.32** (XAMPP):

- importación con el cliente `mysql` (el mismo intérprete de `DELIMITER` que usa phpMyAdmin): **0 errores** en 01, 02 y 03;
- `flask bd reiniciar`: 74 sentencias en 0.7 s, con 20 tablas y 269 filas → [evidencias/f1-flask-bd-reiniciar.txt](evidencias/f1-flask-bd-reiniciar.txt);
- `99_consultas_prueba.sql`: las 26 consultas corren → [evidencias/f1-consultas-prueba.txt](evidencias/f1-consultas-prueba.txt);
- `pytest -v`: **112 passed in 3.4 s** → [evidencias/f1-pytest.txt](evidencias/f1-pytest.txt);
- `ruff check .`: *All checks passed!*

| Tabla | Filas | Tabla | Filas |
|---|---|---|---|
| rol | 4 | salida | 14 |
| usuario | 6 | turista | 20 |
| comunidad | 6 | reserva | 23 |
| familia_anfitriona | 10 | reserva_pasajero | 58 |
| embarcacion | 5 | pago | 14 |
| ruta | 5 | hospedaje | 9 |
| ruta_parada | 10 | abordaje | 14 |
| temporada | 6 | alerta_lago | 6 |
| tipo_pasajero | 5 | resena | 6 |
| tarifa | 35 | bitacora | 13 |

## 5. Pendientes

- **Python 3.13**: las pruebas se corrieron con Python 3.11, el único instalado en esta PC. El código no usa nada propio de una versión, pero el enunciado pide 3.12 o 3.13: hay que instalarlo y repetir `pytest`.
- **Importar una vez a mano en phpMyAdmin** (2 minutos), para confirmar el paso 3A del README. Lo verificamos con el cliente `mysql`, pero no con la interfaz de phpMyAdmin.
- Los datos "por confirmar" de la F0 siguen abiertos: señal, matrículas, precios y fechas de temporada.
- `foto_credito` está en NULL hasta tener las fotos (F3).

---

## Para explicar al docente

### Consulta 1 · Salidas de los próximos 3 días (JOIN y LEFT JOIN)

```sql
-- Salidas de hoy, mañana y pasado mañana con ruta, lancha, capitán y guía.
SELECT s.id, s.fecha_hora_zarpe, r.nombre AS ruta, e.nombre AS lancha, e.matricula,
       cap.nombre_completo AS capitan, gui.nombre_completo AS guia, s.cupo, s.estado
FROM salida s
JOIN ruta r           ON r.id = s.ruta_id
JOIN embarcacion e    ON e.id = s.embarcacion_id
JOIN usuario cap      ON cap.id = s.capitan_id
LEFT JOIN usuario gui ON gui.id = s.guia_id
WHERE s.fecha_hora_zarpe >= CURDATE()
  AND s.fecha_hora_zarpe <  CURDATE() + INTERVAL 3 DAY
ORDER BY s.fecha_hora_zarpe;
```

- **FROM salida s**: partimos de las salidas. La `s` es un apodo (alias) para escribir menos.
- **JOIN ruta / embarcacion**: toda salida tiene una ruta y una lancha (sus FK son NOT NULL). JOIN junta cada salida con su ruta y su lancha usando la FK.
- **JOIN usuario cap**: el capitán también es un usuario, por eso la tabla `usuario` aparece con el apodo `cap`.
- **LEFT JOIN usuario gui**: `guia_id` puede ser NULL. Con JOIN, las salidas sin guía **desaparecerían**; con LEFT JOIN se quedan y la columna `guia` sale NULL.
- **WHERE**: desde hoy a las 00:00 hasta antes de dentro de 3 días. Comparar la columna directamente, sin `DATE(...)` alrededor, permite usar el índice `ix_salida_zarpe`.
- **ORDER BY**: de la más temprana a la más tardía.

Ejemplo con la semilla del 19/10/2026 (8 filas):

| id | zarpe | ruta | lancha | capitán | guía | estado |
|---|---|---|---|---|---|---|
| 6 | 2026-10-19 07:00 | Uros y Taquile | Qhapaq Qocha | Fermín Ccama Turpo | Elena Yucra Cruz | programada |
| 7 | 2026-10-19 08:00 | Islas flotantes de los Uros | Wiñay Inti | Teodoro Choque Pari | NULL | programada |
| 9 | 2026-10-20 07:00 | Uros, Amantaní y Taquile | Mama Qota | Fermín Ccama Turpo | Elena Yucra Cruz | suspendida |

### Consulta 2 · Manifiesto: quién ocupa lugar en una salida (la regla RN-01)

```sql
-- Pasajeros que ocupan lugar en la salida 8, con su documento.
SELECT re.codigo, rp.apellidos, rp.nombres, rp.tipo_documento, rp.numero_documento,
       rp.nacionalidad, tp.nombre AS tipo, rp.precio_aplicado
FROM reserva_pasajero rp
JOIN reserva re       ON re.id = rp.reserva_id
JOIN tipo_pasajero tp ON tp.id = rp.tipo_pasajero_id
WHERE re.salida_id = 8
  AND (re.estado IN ('confirmada','pagada','abordada')
       OR (re.estado = 'pendiente_pago' AND re.vence_en > NOW()))
ORDER BY re.codigo, rp.apellidos;
```

- Partimos de **reserva_pasajero**, porque cada fila es **una persona**: los cupos se cuentan en esta tabla, no en `reserva`.
- **JOIN reserva**: para saber a qué salida va y en qué estado está la reserva.
- **WHERE … estado**: solo ocupan lugar las reservas confirmadas, pagadas o abordadas, y las pendientes de pago que **todavía no vencen**. Una pendiente cuyo `vence_en` ya pasó deja de contar sola, aunque nadie ejecute el comando `vencer` (RN-05).
- Los **paréntesis** importan. Sin ellos, el `OR` se "comería" la condición `salida_id = 8` y aparecerían pasajeros de otras salidas.

Ejemplo: la salida 8 devuelve 15 pasajeros, de las reservas TV-DK5D (6), TV-HAWC (4) y TV-WWUQ (5). El cupo es 18, así que quedan **3 libres** y el estado público es "pocos cupos".

### Consulta 3 · La vista `v_disponibilidad_salida` (subconsulta + GROUP BY + CASE)

```sql
-- Devuelve cada salida con sus ocupados, sus libres y el estado que ve el público.
SELECT s.id AS salida_id, s.cupo,
       COALESCE(o.ocupados, 0) AS ocupados,
       GREATEST(CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0), 0) AS libres,
       CASE WHEN s.estado = 'cancelada' THEN 'cancelada'
            WHEN s.estado IN ('zarpo','finalizada') OR s.fecha_hora_zarpe <= NOW() THEN 'zarpo'
            WHEN s.estado = 'suspendida' THEN 'suspendida'
            WHEN COALESCE(o.ocupados, 0) >= s.cupo THEN 'llena'
            WHEN CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0) <= 3 THEN 'pocos_cupos'
            ELSE 'disponible' END AS estado_publico
FROM salida s
LEFT JOIN (SELECT re.salida_id, COUNT(*) AS ocupados
           FROM reserva re JOIN reserva_pasajero rp ON rp.reserva_id = re.id
           WHERE re.estado IN ('confirmada','pagada','abordada')
              OR (re.estado = 'pendiente_pago' AND re.vence_en > NOW())
           GROUP BY re.salida_id) o ON o.salida_id = s.id;
```

(Es la vista resumida. La real también trae la ruta y la lancha.)

- **La subconsulta `o`** primero cuenta, para **cada salida**, cuántos pasajeros ocupan lugar. `GROUP BY re.salida_id` arma un grupo por salida y `COUNT(*)` cuenta las filas de cada grupo.
- **LEFT JOIN … o**: una salida sin reservas no aparece en `o`. El LEFT JOIN la conserva con `ocupados` NULL, y **COALESCE(…, 0)** cambia ese NULL por 0.
- **GREATEST(…, 0)**: los libres nunca son negativos (RN-01). El **CAST AS SIGNED** existe porque `cupo` es UNSIGNED, y en MariaDB restar a un número sin signo un valor mayor da error.
- **CASE**: aplica RN-08 en orden. La primera condición que se cumple gana, por eso "zarpó" se revisa antes que "llena".

Ejemplo: la salida 10 tiene 4 ocupados y 21 libres ("disponible"). La reserva TV-UKKR, pendiente y ya vencida, tiene 3 pasajeros que **no** cuentan.

### Consulta 4 · Transparencia comunitaria (GROUP BY con SUM)

```sql
-- Noches y monto por familia (sin lo cancelado).
SELECT c.nombre AS comunidad, f.nombre_familia,
       COUNT(*) AS noches, SUM(h.personas) AS personas_noche, SUM(h.monto_familia) AS monto
FROM hospedaje h
JOIN familia_anfitriona f ON f.id = h.familia_id
JOIN comunidad c          ON c.id = f.comunidad_id
WHERE h.estado IN ('asignado','cumplido')
GROUP BY c.nombre, f.id, f.nombre_familia
ORDER BY c.nombre, monto DESC;
```

- **WHERE** se aplica **antes** de agrupar: deja fuera las noches canceladas, que no son ingreso.
- **GROUP BY** junta todas las noches de una misma familia en un grupo. **COUNT(*)** da cuántas noches tiene; **SUM** suma las personas y el monto.
- Se agrupa también por `f.id`, porque dos familias podrían llamarse igual.

Ejemplo: Familia Quispe Cruz (Amantaní) tiene 2 noches, 4 personas-noche y S/ 160.00; Familia Mamani Yucra tiene 1 noche y S/ 80.00. Las familias 4 (Pacompía Ccalla) y 1 aparecen con noches asignadas por la rotación RN-10.

### ¿Por qué la semilla calcula los precios y no los escribe?

Así el dato es **coherente por construcción**: `precio_aplicado` sale de la tarifa vigente en la fecha de la salida y del recargo de la temporada (RN-04), igual que lo hará la app en la F4.

Si algún día falta una tarifa, el precio queda NULL y MariaDB rechaza la fila (la columna es NOT NULL). El error aparece al importar, no meses después.
