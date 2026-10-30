# Fase 7 · Calidad

La F7 no agrega pantallas: **revisa toda la aplicación** contra la sección 11 (seguridad,
rendimiento y accesibilidad) y la sección 14 (concurrencia, prueba mutante y cobertura).
Lo que se puede automatizar quedó como prueba, así se vuelve a revisar con cada `pytest`.

## 1. Qué hicimos

### Prueba mutante (sección 14)

`tests/test_mutante.py` hace lo siguiente:

1. Copia `app/modelos/reserva.py`, le quita `FOR UPDATE` y `LOCK IN SHARE MODE` y corre esa copia (el **mutante**).
2. Lanza la misma carrera de la prueba de concurrencia: **8 hilos**, cada uno con su conexión, piden **1 lugar**.
3. Usa una pausa de 0.3 s entre contar y guardar, para que el resultado no dependa de la suerte.
4. Quita el trigger de respaldo solo durante la prueba, y al final lo vuelve a crear (y lo comprueba).

| Modelo | Trigger de sobreventa | Resultado | Qué demuestra |
|---|---|---|---|
| original (con `FOR UPDATE`) | quitado | **1 reserva**, 7 «sin cupo» (2.5 s: van de a una) | El `FOR UPDATE` solo ya impide la sobreventa. |
| **mutante (sin `FOR UPDATE`)** | quitado | **8 reservas para 1 lugar** (0.4 s) | **Sin el bloqueo, la prueba de los 8 hilos falla.** |
| mutante | puesto | 1 reserva; los otros 7 reciben «sin cupo» o «inténtalo de nuevo» | El trigger es la red de respaldo, aunque con interbloqueos (D-93). |

Se sumaron 3 carreras de la F5 y la F6 a `tests/test_concurrencia.py`:

- dos operadores verifican **el mismo pago**: uno lo verifica y el otro recibe «ya fue revisado»;
- dos turistas **reprograman al último lugar**: uno lo consigue y el otro recibe «sin cupo»;
- dos guías leen **el mismo QR**: un solo abordaje por pasajero.

### Rendimiento (sección 11)

- **Peso de página** (`tests/test_rendimiento.py`). Se mide el HTML, el CSS, el JS, los íconos y los logos, **sin las fotos** de las comunidades:
  - 8 páginas del turista, en español y en inglés;
  - 14 páginas del panel del operador y 3 del admin.

  Todas pesan **entre 35 y 55 KB**; el límite es 100 KB. El formulario de reserva es la más pesada, por su lista de 249 países. El manifiesto PDF pesa menos de 100 KB. Detalle: [f7-pesos.txt](evidencias/f7-pesos.txt).
- **EXPLAIN de las 3 consultas más importantes**: `python scripts/explicar_consultas.py` → [f7-explain.txt](evidencias/f7-explain.txt). Están explicadas abajo, en «Para explicar al docente». Una prueba verifica que sigan usando sus índices.
- **Sin N+1 en el panel**:
  - la lista de pasajeros hace **las mismas consultas** con 1 o con 9 pasajeros, en sus 4 formatos (HTML, imprimir, WhatsApp y PDF);
  - pagos, hospedajes, indicadores, alertas, reseñas y catálogos hacen un número fijo y chico de consultas.

### Seguridad (sección 11)

`tests/test_seguridad_f7.py` revisa **toda la aplicación**: lee las rutas de `app.url_map`, así que una ruta nueva queda cubierta sin escribir otra prueba (D-98).

| Requisito | Cómo está | Prueba |
|---|---|---|
| CSRF en todo POST | `CSRFProtect` global | **Cada una de las rutas POST** sin token → 400 |
| Permisos | `@requiere_rol` + `exigir_rol` en el modelo | **Cada página GET del panel** sin sesión → `/entrar`; matrices por rol (F5, F6) |
| Consultas parametrizadas | `%s` en todo `modelos/*` | Un análisis del código (AST) revisa que ningún `execute`/`consultar` arme el SQL con `+`, `%` o una f-string con datos (solo marcas `%s` o nombres de una lista blanca) |
| XSS | Autoescape de Jinja; `t()` escapa cada valor | Una reseña con `<script>` y una alerta con `<b>` se muestran escapadas en el panel y en la web |
| Cabeceras | CSP `'self'`, `X-Frame-Options: DENY`, `nosniff` | También en el 404, en `/salud`, en los estáticos y en el PDF |
| `no-store` con datos personales | `g.sin_cache` en el panel y en las reservas | También en el manifiesto PDF |
| Cookies | HttpOnly, SameSite=Lax, Secure en producción | La cookie real después de entrar |
| Secretos | Solo en `.env` | `.env.example` sin `SECRET_KEY` ni contraseña; `.env` en `.gitignore`; ninguna contraseña demo en el código |
| 5 intentos cada 15 min, páginas de error sin trazas, contraseñas bcrypt | F2 | Pruebas de la F2, que siguen pasando |

### Accesibilidad (sección 11)

`tests/test_accesibilidad.py` revisa el HTML de **56 páginas**: el turista en español y en inglés, el panel de 3 roles y formularios con errores. Usa `html.parser` de Python, sin dependencias nuevas (D-94). En cada página comprueba:

- `<html lang>` y un solo `<h1>`;
- títulos sin saltos (de h2 no se pasa a h4);
- **cada campo con su etiqueta** (`<label for>`, `aria-label` o dentro de un `<label>`);
- cada `aria-describedby` y `aria-labelledby` apunta a un id que existe, y no hay ids repetidos;
- `alt` en toda imagen, sin `tabindex` positivo, enlaces y botones con texto, tablas con `<th>`;
- en un formulario con errores: el **resumen arriba** (`role="alert"`, con enlaces a cada campo) y el **error junto al campo** (`aria-invalid` + `aria-describedby`).

Una prueba confirma que el auditor detecta una página mala. Lo que se revisó a mano:

- el **contraste** se midió en la F0 y la F2 (D-06, D-27);
- **foco visible** con Tab → [f7-teclado-foco-visible.jpg](evidencias/f7-teclado-foco-visible.jpg);
- el formulario se completa solo con el teclado.

### Errores encontrados y corregidos en esta revisión

1. **Abordaje**: los dos formularios de la página (abordaje y cobro) tenían `id="csrf_token"`. Un id no se puede repetir.
2. **Registrar alerta** no tenía `<h1>`.
3. **Venía desde la F4.** Con JavaScript, el selector «¿Cuántos acompañantes?» y el botón «+ Agregar acompañante» se veían **los dos**. El JS escondía el selector con `hidden`, pero la clase CSS con `display: flex` lo volvía a mostrar. Lo mismo pasaba sin JavaScript con los botones «Quitar acompañante». Se arregló con `[hidden] { display: none !important; }` (D-95) y una prueba.

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `tests/test_mutante.py` (nuevo) | Prueba mutante: 3 carreras + el trigger restaurado. |
| `tests/test_concurrencia.py` | 3 carreras nuevas: pago, reprogramar y QR. |
| `tests/test_rendimiento.py` (nuevo) | Pesos de 33 páginas, EXPLAIN y N+1 del panel. |
| `tests/test_seguridad_f7.py` (nuevo) | CSRF en todo POST, panel con sesión, cabeceras, XSS, SQL sin datos, cookies y secretos. |
| `tests/test_accesibilidad.py` (nuevo) | Auditor de HTML sobre 56 páginas. |
| `scripts/explicar_consultas.py` (nuevo) | EXPLAIN de las 3 consultas más importantes. |
| `app/plantillas/panel/abordaje.html`, `alerta.html`, `estilos.css` | Las 3 correcciones. |

## 3. Comandos para probarlo

```powershell
pytest -v --cov=app/modelos                              # 479 pruebas
pytest -v -s tests/test_mutante.py                       # la tabla de la prueba mutante
pytest -q -s tests/test_rendimiento.py -k pesan          # el peso de cada página
python scripts/explicar_consultas.py                     # EXPLAIN de las 3 consultas
ruff check .
```

## 4. Evidencia (20/10/2026)

- `pytest -v --cov=app/modelos`: **479 passed in 76 s**, con **92 %** de cobertura en `app/modelos` (el mínimo es 80 %) → [f7-pytest.txt](evidencias/f7-pytest.txt). Son 46 pruebas nuevas en la F7.
- Mutante y concurrencia → [f7-mutante-y-concurrencia.txt](evidencias/f7-mutante-y-concurrencia.txt).
- Pesos → [f7-pesos.txt](evidencias/f7-pesos.txt). EXPLAIN → [f7-explain.txt](evidencias/f7-explain.txt).
- Foco visible con el teclado → [f7-teclado-foco-visible.jpg](evidencias/f7-teclado-foco-visible.jpg).
- `ruff check .`: *All checks passed!*

## 5. Pendientes y riesgos

- **Sin aprobar, así que no se hicieron**:
  - **PR-07**: límite de intentos en `/mi-reserva`. **Riesgo aceptado**: probar todas las combinaciones es inviable (31⁴ códigos × 10⁸ documentos), pero no hay freno.
  - **PR-09**: service worker.
  - **PR-14**: aviso por WhatsApp.
- **Revisión de dependencias**, para saber si alguna tiene fallas conocidas: hace falta `pip-audit`, que es una **dependencia nueva**. ¿La agregamos? Si no, se revisa a mano en la F8 con las versiones de `requirements.txt`.
- **Lector de pantalla** (NVDA, gratis en Windows) y Lighthouse de Chrome: los tiene que correr el equipo; no se automatizan aquí.
- Siguen abiertos:
  - Python 3.13 (las pruebas se corrieron con 3.11);
  - HTTPS (F8);
  - los datos "por confirmar" con Giant Trip.

---

## Para explicar al docente

### 1. EXPLAIN de los ocupados de una salida (lo que se cuenta en CADA reserva)

```sql
EXPLAIN
SELECT COUNT(*) AS ocupados
FROM reserva_pasajero rp
JOIN reserva r ON r.id = rp.reserva_id
WHERE r.salida_id = 10
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()));
```

| table | type | key | ref | rows | Extra |
|---|---|---|---|---|---|
| r | ref | ix_reserva_salida_estado | const | 6 | Using index condition; Using where |
| rp | ref | uk_pasajero_documento | r.id | 1 | Using index |

- **Fila r**: MariaDB empieza por `reserva` y entra directo por el índice `(salida_id, estado)` (`type = ref`, `ref = const`). Solo lee las reservas de la salida 10, no toda la tabla. «Using index condition» quiere decir que hasta el filtro por estado se resuelve con el índice.
- **Fila rp**: por cada reserva busca sus pasajeros con el UNIQUE `(reserva_id, tipo_documento, numero_documento)`. Sirve porque `reserva_id` es su primera columna. «Using index»: ni siquiera lee la tabla, el índice alcanza para contar.
- Por eso el índice `ix_reserva_salida_estado` se creó en la F1 con el comentario «RN-01: contar ocupados por salida».

### 2. EXPLAIN de las salidas del día (la portada y /salidas)

| id | select_type | table | type | key | Extra |
|---|---|---|---|---|---|
| 1 | PRIMARY | r (ruta) | ALL | — | Using temporary; Using filesort |
| 1 | PRIMARY | s (salida) | ref | ix_salida_ruta_zarpe | Using index condition |
| 1 | PRIMARY | e (lancha) | eq_ref | PRIMARY | Using index |
| 1 | PRIMARY | `<derived3>` | ref | key0 | |
| 3 | LATERAL DERIVED | re (reserva) | ref | ix_reserva_salida_estado | Using index condition |
| 3 | LATERAL DERIVED | rp | ref | uk_pasajero_documento | Using index |

- La consulta lee la vista `v_disponibilidad_salida`. MariaDB la "abre" y arma el plan con sus tablas.
- Empieza por `ruta` entera (`ALL`, 5 filas: con tan pocas, leerla toda es lo más barato). Por cada ruta entra a `salida` con el índice `(ruta_id, fecha_hora_zarpe)`, que filtra el rango de fechas del día.
- `lancha`: `eq_ref` por la PRIMARY, una sola fila por salida.
- **LATERAL DERIVED** es lo importante. La subconsulta de la vista que cuenta los ocupados no se calcula para todas las salidas: se calcula **solo para las salidas de este día**, otra vez con `ix_reserva_salida_estado`.
- «Using temporary; Using filesort» viene del `ORDER BY` por hora: ordena unas pocas filas en memoria.

### 3. EXPLAIN de la familia que toca (RN-10)

| id | select_type | table | type | key | rows |
|---|---|---|---|---|---|
| 1 | PRIMARY | f | range | ix_familia_comunidad | 5 |
| 4 | MATERIALIZED | h | ALL | — | 9 |
| 3 | DEPENDENT SUBQUERY | h | ref | ix_hospedaje_familia_noche | 1 |
| 2 | DEPENDENT SUBQUERY | h | ref | ix_hospedaje_familia_noche | 1 |

- **f**: las familias se buscan por el índice de su comunidad.
- **id 2 y 3** son las subconsultas de "noches en 30 días" y "última noche". Son **dependientes**: se calculan por cada familia y entran por `(familia_id, fecha_noche)`, que es justo lo que piden.
- **id 4** es el `NOT EXISTS` ("¿esa noche ya tiene a alguien?"). MariaDB decidió **materializarlo**: leer los 9 hospedajes una vez y guardarlos. Con 9 filas es más barato que buscarlos familia por familia. Con miles de hospedajes cambiaría de plan, porque el mismo índice `(familia_id, fecha_noche)` le sirve.
- Lección: el EXPLAIN depende de **cuántos datos hay**. Por eso el script ejecuta antes `ANALYZE TABLE` (estadísticas al día).

### 4. ¿Por qué el mutante vende de más? FOR UPDATE frente a un SELECT común

```sql
-- Original (paso 1 de RN-02): la segunda transacción ESPERA aquí hasta el COMMIT de la primera.
SELECT id, cupo, estado FROM salida WHERE id = %s FOR UPDATE;
-- Mutante: sin FOR UPDATE nadie espera. Los 8 hilos leen "0 ocupados" a la vez y los 8 guardan.
SELECT id, cupo, estado FROM salida WHERE id = %s;
```

- Con `FOR UPDATE`, el hilo 2 queda detenido en esa línea hasta que el hilo 1 hace COMMIT. Cuando sigue, cuenta con lectura actual y ya ve la reserva del hilo 1: «solo quedan 0 lugares». Por eso tarda 2.5 s: los 8 pasan **de a uno**.
- Sin `FOR UPDATE`, los 8 cuentan al mismo tiempo, los 8 ven 1 lugar libre y los 8 guardan: **8 pasajeros en una lancha con 1 lugar**. Eso es lo que pasaba con el cuaderno y WhatsApp.
- El trigger de la F1 vuelve a contar dentro del INSERT de cada pasajero, con su propio bloqueo, y frena la sobreventa. Pero como bloquea **tarde** (después de insertar la reserva), las transacciones se cruzan y MariaDB tiene que cortar algunas (interbloqueo, error 1213). Por eso el modelo bloquea **primero**: la salida, una sola vez y al comienzo.
