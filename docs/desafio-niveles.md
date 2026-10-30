# Desafío del docente: evidencia por nivel

| Nivel | Criterio | Fase | Estado |
|---|---|---|---|
| Bronce | CREATE TABLE con PK y FK, ≥ 3 filas por tabla (pedimos 5) y SELECT * de cada tabla | F1 | **Listo** (19/10/2026) |
| Plata | Cada pantalla lee de la base, sin datos fijos en el HTML | F3 | **Listo** (20/10/2026) |
| Oro | Reservar hace INSERT; el dato sigue ahí al recargar; sin duplicados por doble clic ni envíos simultáneos | F4 (+ mutante en F7) | **Listo** (20/10/2026); mutante **listo** (F7) |
| Platino | Lo mismo contra otro servidor MariaDB/MySQL cambiando solo el `.env` | F8 | **Listo** (20/10/2026): segundo servidor MariaDB; la prueba en otra PC queda como guía para el equipo |

---

## Bronce

### 1. CREATE TABLE con PK y FK

`database/01_esquema.sql` crea **20 tablas**, cada una con `PRIMARY KEY (id)`, y **29 claves foráneas**, todas con índice. Se puede comprobar en phpMyAdmin (pestaña SQL):

```sql
-- Devuelve cuántas tablas, FK y CHECK tiene la base.
SELECT (SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE')        AS tablas,
       (SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE())                                AS claves_foraneas,
       (SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE())                                AS checks;
```

Resultado al cerrar la F1 (19/10/2026, MariaDB 10.4.32): **tablas = 20, claves_foraneas = 29, checks = 36.** En la entrega (F8, 20/10/2026) da **checks = 39**: las fases siguientes agregaron 3 reglas. Las tablas y las FK siguen iguales.

### 2. Filas por tabla (pedimos 5 o más)

Es la primera consulta de `99_consultas_prueba.sql`, y `flask bd contar` muestra lo mismo:

| Tabla | Filas | Tabla | Filas |
|---|---|---|---|
| rol | **4** \* | salida | 14 |
| usuario | 6 | turista | 20 |
| comunidad | 6 | reserva | 23 |
| familia_anfitriona | 10 | reserva_pasajero | 58 |
| embarcacion | 5 | pago | 14 |
| ruta | 5 | hospedaje | 9 |
| ruta_parada | 10 | abordaje | 14 |
| temporada | 6 | alerta_lago | 6 |
| tipo_pasajero | 5 | resena | 6 |
| tarifa | 35 | bitacora | 13 |

\* `rol` tiene 4 filas porque el enunciado fija **exactamente 4 códigos** (admin, operador, guía, capitán) y un CHECK impide inventar otros. Cumple el mínimo del docente (≥ 3). Ver la decisión D-15.

### 3. SELECT * de cada tabla

En `database/99_consultas_prueba.sql`, sección B: 20 consultas `SELECT * FROM <tabla>;`, cada una con un comentario que dice qué devuelve. La salida completa está en [evidencias/f1-consultas-prueba.txt](evidencias/f1-consultas-prueba.txt).

### 4. Extra: la base se defiende sola

`pytest` ejecuta **112 pruebas** que intentan meter datos inválidos y comprueban que MariaDB los rechace:

- 30 casos de CHECK;
- ENUM en modo estricto;
- 9 casos de FK;
- 13 casos de UNIQUE;
- CASCADE y RESTRICT;
- 14 casos de triggers: sobreventa, documento repetido, capacidad, capitán, cruces y bitácora.

La salida está en [evidencias/f1-pytest.txt](evidencias/f1-pytest.txt).

### Cómo lo mostramos en clase (5 minutos)

1. `flask bd reiniciar --si`: la base se crea desde cero en menos de 1 segundo.
2. En phpMyAdmin, ejecutar la sección A de `99_consultas_prueba.sql` (las filas por tabla).
3. Ejecutar 2 o 3 `SELECT *` y la consulta D1 (JOIN). Explicarla con [fase-1-base-datos.md](fase-1-base-datos.md#para-explicar-al-docente).
4. Intentar un INSERT inválido en vivo y ver el error de MariaDB. Por ejemplo:

   ```sql
   INSERT INTO familia_anfitriona (comunidad_id, nombre_familia, responsable, capacidad_personas)
   VALUES (3, 'Familia Prueba', 'Responsable', 11);
   ```

   La respuesta de MariaDB es ``#4025 - CONSTRAINT `ck_familia_capacidad` failed for `titicaca_vivo`.`familia_anfitriona` ``.

---

## Plata

**Criterio:** cada pantalla lee de la base, con cero datos fijos en el HTML.

### Pantallas y de dónde sale cada dato

| Pantalla | Lo que muestra | Consultas (modelo) |
|---|---|---|
| `/` portada | Alertas vigentes, salidas de hoy, rutas con "desde S/", mapa y comunidades | `alerta.vigentes`, `salida.listar_publicas`, `ruta.listar_activas`, `comunidad.listar_publicas`, `ruta.paradas_para_mapa` |
| `/salidas` | Salidas de un día y de una ruta, más los próximos 7 días | `salida.dias_con_salidas`, `salida.listar_publicas`, `ruta.listar_activas` |
| `/salidas/<id>` | Detalle, cupos, recorrido, precios (RN-04) y alertas (RN-11) | `salida.buscar_publica`, `ruta.paradas`, `tarifa.precios_para_salida`, `salida.alertas_que_la_afectan` |
| `/comunidades` | Comunidades y mapa | `comunidad.listar_publicas`, `ruta.paradas_para_mapa` |
| `/comunidades/<slug>` | Ficha, familias (sin datos personales), rutas y próximas salidas | `comunidad.buscar_por_slug`, `familias_publicas`, `rutas_que_la_visitan`, `proximas_salidas` |
| `/alertas` | Vigentes, próximas y pasadas | `alerta.para_pagina_publica` |
| `/panel` (F2) | Resumen del día según el rol | `panel.*`, `alerta.vigentes` |

Las plantillas solo tienen **textos de la interfaz** ("Salidas de hoy", "Lugares", "Precios por persona"…). Los datos del negocio (nombres, horarios, precios, cupos, alertas) llegan de la base.

### Evidencia automática (`tests/test_plata.py`, 14 pruebas)

1. **Ninguna plantilla tiene datos del negocio escritos.** La prueba lee de la base todos los nombres de comunidades, rutas, códigos, muelles, lanchas, matrículas, familias, alertas, tipos de pasajero, temporadas y códigos de reserva (más de 50 textos) y verifica que ninguno aparezca en `app/plantillas/**.html`. Otra prueba revisa que no haya precios escritos a mano (`S/ 30`…).
2. **Si se cambia un dato en la base, la página cambia al recargar** (5 casos):

   | Cambio en la base | Página | Se ve |
   |---|---|---|
   | Nombre de una comunidad | `/comunidades` | El nombre nuevo |
   | Cupo de una salida | `/salidas/10` | "4 de 24 lugares ocupados" |
   | Precio de una tarifa | `/salidas/10` | "S/ 85.50" |
   | Título de una alerta | `/` | El título nuevo |
   | Capacidad de una familia | `/comunidades/amantani` | "Hasta 9 personas" |

3. **Sin base, ninguna página pública se puede mostrar** (6 páginas): si la base no responde, cada una da error 500. Ninguna tiene datos "de respaldo" escritos en el HTML.
4. Además, cada página hace un **número fijo de consultas** (sin N+1). Por ejemplo, la portada hace 5, sin importar cuántas comunidades o salidas haya.

### Cómo lo mostramos en clase (3 minutos)

1. Abrir `/salidas/10` y ver "Adulto nacional S/ 80.00".
2. En phpMyAdmin:

   ```sql
   UPDATE tarifa SET precio_base = 85.50
   WHERE ruta_id = 2 AND tipo_pasajero_id = 1 AND vigente_desde = '2026-01-01';
   ```

3. Recargar la página: ahora dice **S/ 85.50**. Volver a dejar 80.00.
4. Explicar la consulta de precios con [fase-3-lectura-publica.md](fase-3-lectura-publica.md#para-explicar-al-docente).

---

## Oro

**Criterio:** la acción principal (reservar) hace INSERT o UPDATE; al recargar, el dato sigue ahí; dos clics o tres envíos simultáneos no duplican la reserva.

| Lo que pide el docente | Cómo lo cumplimos | Evidencia |
|---|---|---|
| Reservar hace **INSERT** | `reserva.crear()`: INSERT en `turista` (o UPDATE si ya existe), `reserva`, `reserva_pasajero`, `hospedaje` (si hay noche) y `bitacora`, todo en **una transacción** (COMMIT o ROLLBACK). | `test_reserva_en_el_muelle_queda_confirmada_con_su_total` |
| **Al recargar, el dato sigue ahí** | POST → redirección **303** → GET `/reservas/<código>`, que lee la reserva de la base. Recargar no vuelve a enviar el formulario. | `test_reservar_redirige_y_el_dato_sigue_al_recargar` (recarga 2 veces) |
| **Dos clics no duplican** | Cada formulario lleva un `token_envio` único (UNIQUE en la base). El segundo envío encuentra el token y recibe la **misma** reserva. | `test_doble_clic_no_duplica_la_reserva`, `test_el_mismo_token_no_duplica_la_reserva` |
| **Tres envíos simultáneos no duplican** | Los 3 esperan el bloqueo de la salida (`FOR UPDATE`): el primero crea la reserva y los otros dos encuentran el token. Si algo se escapara, el UNIQUE devuelve el error 1062 y se muestra la existente. | `test_tres_envios_del_mismo_formulario_crean_una_sola_reserva` (3 hilos, 3 conexiones) |
| Extra: **sin sobreventa** | `FOR UPDATE` sobre la salida, conteo con lectura actual y el trigger como red. | `test_ocho_hilos_por_el_ultimo_lugar_crean_una_sola_reserva` (8 hilos, 1 cupo: 1 reserva y 7 "sin cupo") |

### Cómo lo mostramos en clase (5 minutos)

1. Abrir `/salidas`, elegir una salida, **Reservar** y completar el formulario.
2. Hacer **doble clic** en "Confirmar reserva": aparece una sola reserva. Si el segundo clic llega a enviarse, se ve el aviso "ya estaba registrada: no se creó otra".
3. **Recargar** la página de la reserva: el dato sigue ahí.
4. En phpMyAdmin:

   ```sql
   SELECT codigo, estado, total, token_envio FROM reserva ORDER BY id DESC LIMIT 3;
   ```

   El código aparece una sola vez.
5. Ejecutar `pytest tests/test_concurrencia.py -v` y mostrar los 2 resultados (8 hilos → 1 reserva; 3 envíos → 1 reserva).
6. Explicar el `FOR UPDATE` y el conteo con [fase-4-reservas.md](fase-4-reservas.md#para-explicar-al-docente).

**Prueba mutante (F7)** — `pytest -v -s tests/test_mutante.py`: si se quita el `FOR UPDATE` (y el trigger de respaldo), los mismos 8 hilos crean **8 reservas para 1 lugar**: la prueba de concurrencia fallaría. Con el `FOR UPDATE`, 1 reserva. Con el trigger puesto, también 1. Ver [fase-7-calidad.md](fase-7-calidad.md#prueba-mutante-sección-14).

---

## Platino

**Criterio:** todo lo anterior contra un servidor de base de datos real (el MariaDB de XAMPP y, como extra, un MySQL/MariaDB en otra PC o en la nube), cambiando solo el `.env`.

| Lo que pide el docente | Cómo lo cumplimos | Evidencia |
|---|---|---|
| Un servidor **real** | El MariaDB 10.4.32 de XAMPP, desde la F1. No hay SQLite ni ORM: el SQL va escrito a mano con PyMySQL. | Todas las pruebas de la F1 a la F7 |
| **Otro** servidor | Un segundo MariaDB, separado del de XAMPP: puerto 3307, con sus propios datos, su propio `root` y su propio `titicaca_app`, y contraseñas nuevas (D-100). | [evidencias/f8-platino-otro-servidor.txt](evidencias/f8-platino-otro-servidor.txt) |
| Cambiando **solo el `.env`** | Cambiaron 2 líneas: `BD_PUERTO` y `BD_CONTRASENA`. El código no se tocó. Para volver, se dejó el `.env` original, con la misma huella SHA-256. | La misma evidencia |
| **Todo lo anterior** | Ahí corrimos `flask bd reiniciar` (20 tablas, 269 filas), `/salud`, y las **479 pruebas** de la F1 a la F7: Bronce, Plata, Oro, concurrencia y mutante. | `479 passed` en el puerto 3307 |
| Que también sirva en MySQL 8 | El único SQL que MySQL 8 rechazaba (`CAST AS BINARY` en 5 CHECK) se cambió por `COLLATE utf8mb4_bin` (D-99). Lo demás que cambia en MySQL 8 está en [fase-8-entrega.md](fase-8-entrega.md#si-el-otro-servidor-es-un-mysql-8-o-una-base-en-la-nube). | Las 102 pruebas de la base |

### Cómo lo mostramos en clase (5 minutos)

La forma más clara es con **2 PC** en la misma red: la PC B tiene la base y la PC A, la aplicación. El paso a paso está en [fase-8-entrega.md](fase-8-entrega.md#guía-para-repetir-platino-en-otra-pc-de-la-red-lo-hace-el-equipo).

1. Mostrar el `.env` de la PC A: `BD_HOST` tiene la IP de la PC B. Es lo **único** que cambió.
2. Ejecutar `flask bd reiniciar --si` y luego `flask bd contar` desde la PC A: 20 tablas y 269 filas, **en la PC B**.
3. En la PC A, abrir `/salud` y reservar una salida.
4. En el phpMyAdmin de la **PC B**, ejecutar:

   ```sql
   SELECT codigo, estado, total FROM reserva ORDER BY id DESC LIMIT 3;
   ```

   La reserva hecha desde la PC A está ahí, una sola vez: Oro, en el otro servidor.

Si solo hay una PC, se arma un segundo servidor MariaDB en otro puerto, como hicimos nosotros:

```powershell
C:\xampp\mysql\bin\mysql_install_db.exe --datadir=C:\platino\datos --port=3307 --password=<clave de root nueva>
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\platino\datos\my.ini --standalone
```

En otra ventana, ejecutar `00_crear_bd_usuario.sql` en ese servidor (`mysql.exe -u root -p -P 3307 -h 127.0.0.1`, con una clave nueva). Después, en el `.env`, cambiar `BD_PUERTO=3307` y `BD_CONTRASENA`, y seguir desde el paso 2.
