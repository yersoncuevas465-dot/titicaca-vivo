# Fase 4 · Reservar (nivel Oro)

> Estado: entregada el 20/10/2026. Espera el "ok" del equipo para pasar a la F5.
> Antes de empezar la F4 se cerró un pendiente de la F3: las 6 fotos de las comunidades.

## 0. Fotos de las comunidades (pendiente de la F3)

- Con la autorización del equipo se bajaron las **miniaturas de 960 px** de los 6 archivos de Commons. Commons limita la velocidad (respondió 429), así que se bajaron de a una.
- Antes de usarlas se revisaron una por una: no muestran rostros reconocibles.
- Se convirtieron con `scripts/preparar_foto.py` (ejecutado con `python -I`, porque son archivos descargados) a WebP de 640×400. Pesan entre 18 y 40 KB.
- Los créditos están en `comunidad.foto_credito` (semilla) y en [creditos-imagenes.md](creditos-imagenes.md).

## 1. Qué hicimos

- **`/salidas/<id>/reservar`** (GET y POST):
  - datos del titular, con "Yo también viajo" marcado por defecto (D-08);
  - acompañantes: **con JavaScript** se agregan y quitan filas (`estaticos/js/reservar.js`, sin código en línea); **sin JavaScript** se elige la cantidad y la página se recarga;
  - forma de pago: Yape, Plin o en el muelle;
  - el país se elige con un `<datalist>` ISO 3166 (los 249 países), compartido por todas las filas.
- **Modelo `reserva.crear`, en UNA transacción (RN-02):**
  1. `SELECT … FROM salida WHERE id = %s FOR UPDATE`, que bloquea la salida;
  2. ¿el mismo `token_envio` ya creó una reserva? Si es así, devuelve esa (RN-03);
  3. cuenta los ocupados con **lectura actual** (`LOCK IN SHARE MODE`, y la transacción en READ COMMITTED);
  4. revisa que ningún documento esté ya en la salida (RN-09);
  5. guarda o reutiliza al titular: mismo documento y mismo nombre, sin importar tildes ni mayúsculas (S-08);
  6. calcula el **precio de cada pasajero** (RN-04, la foto del precio) y el total;
  7. inserta la reserva (Yape/Plin → `pendiente_pago`, vence en 120 min; muelle → `confirmada`) y los pasajeros;
  8. si la ruta tiene noche y la reserva queda confirmada, **asigna la familia anfitriona por rotación justa** (RN-10). Con Yape/Plin solo revisa que haya una libre; la asignación llega al verificar el pago (F5);
  9. bitácora y **COMMIT**.
- **Idempotencia (RN-03)**: si el token ya está, se devuelve la reserva existente. Además, el UNIQUE de `token_envio` atrapa el error 1062 como última red.
- **`/reservas/<código>`**: estado, salida, titular, pasajeros, total, pagos y familia anfitriona. **Los datos personales se ven ocultos** (`R*** M**** Q*****`, `•••••081`) hasta que la persona se identifica.
- **`/mi-reserva`**: con el código y el documento del titular se habilita, en la sesión, ver los datos completos, el boleto y el formulario de pago. Si falla, responde 401 con el mismo mensaje sea el código o el documento lo que está mal.
- **Boleto** `/reservas/<código>/boleto`:
  - en HTML tiene aspecto de pase de abordar, con un **QR en SVG** que guarda `/panel/abordaje/<código>` (la ruta que se programa en la F5);
  - en **PDF** (`?formato=pdf`) es un A6 hecho con reportlab, con el **isotipo redibujado** (cumple D-13).
- **Reporte de pago** `/reservas/<código>/pago` (RN-06):
  - el pago queda `reportado`;
  - el cupo se guarda hasta 60 minutos antes del zarpe (D-09);
  - un número de operación repetido se rechaza;
  - con el total ya reportado, la página dice "en revisión".
- **`flask reservas vencer`** (RN-05): marca las vencidas y las anota en la bitácora. Aun sin ejecutarlo, las vencidas ya no cuentan en los cupos.

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `app/modelos/reserva.py` | Crear (la transacción), consultar, acceso, reportar pago y vencer. |
| `app/modelos/hospedaje.py` | Rotación justa (RN-10) dentro de la transacción. |
| `app/modelos/__init__.py` | `ErrorNegocio`, la excepción común de las reglas. |
| `app/formularios/reserva.py` | Reserva (con `FieldList` de acompañantes), Mi reserva y Pago. |
| `app/rutas/reservas.py` | 5 rutas, con POST → 303 → GET. |
| `app/servicios/qr.py`, `pdf.py`, `privacidad.py`, `paises.py` | QR (SVG y PNG), boleto PDF, enmascarado y países ISO. |
| `app/plantillas/reservas/*`, `estaticos/js/reservar.js`, `estilos.css` | Páginas, script de acompañantes y estilos del boleto. |
| `app/comandos.py`, `config.py`, `.env.example` | `flask reservas vencer`, máximo de pasajeros, datos de cobro (ficticios) y `URL_PUBLICA`. |
| `app/estaticos/img/comunidades/*.webp`, `database/03_datos.sql` | Fotos y créditos. |
| `tests/test_reglas_reserva.py`, `test_rutas_reservas.py`, `test_concurrencia.py` | 64 pruebas nuevas. |

## 3. Comandos para probarlo

```powershell
flask bd reiniciar --si
flask run                       # http://127.0.0.1:5000/salidas  →  elegir una salida  →  Reservar
flask reservas vencer           # RN-05
pytest -v --cov=app/modelos     # 283 pruebas, cobertura de modelos
ruff check .
```

Recorrido sugerido:

1. Reservar con Yape: queda "Pendiente de pago", con el plazo.
2. Abrir "Reportar mi pago" e ingresar un número de operación: el pago queda en revisión.
3. Hacer otra reserva pagando en el muelle: queda confirmada.
4. Abrir "Ver mi boleto con QR" y "Descargar PDF".
5. Abrir la misma reserva en una ventana de incógnito: los datos se ven ocultos.
6. En esa ventana, usar "Mi reserva" con el código y el documento del titular: se ven completos.

## 4. Evidencia (20/10/2026)

- `pytest -v --cov=app/modelos`: **283 passed in 37 s**, con **93 %** de cobertura en `app/modelos` (el mínimo es 80 %) → [evidencias/f4-pytest.txt](evidencias/f4-pytest.txt).
  - 38 reglas: RN-02 a RN-06, RN-09, RN-10 y vencimiento;
  - 24 rutas: 200, 303, 302, 400, 401, 404, 409 y 422;
  - 2 de concurrencia.
- **Concurrencia (nivel Oro):**
  - **8 hilos** con sus propias conexiones piden el último lugar al mismo tiempo: hay **1** reserva y **7** reciben "sin cupo";
  - **3 envíos simultáneos** del mismo formulario: hay **1** reserva y los 3 reciben el mismo código.
- `ruff check .`: *All checks passed!*
- En el navegador, todo en la app local:
  - formulario con 2 acompañantes agregados con el botón, quitar uno y la renumeración → [f4-formulario-celular.jpg](evidencias/f4-formulario-celular.jpg);
  - reserva con Yape → [f4-reserva-pendiente-celular.jpg](evidencias/f4-reserva-pendiente-celular.jpg);
  - reporte de pago: el plazo se extendió hasta las 07:00 del día del viaje;
  - boleto → [celular](evidencias/f4-boleto-celular.jpg) y [escritorio](evidencias/f4-boleto-escritorio.jpg);
  - PDF dibujado con pdf.js → [f4-boleto-pdf.jpg](evidencias/f4-boleto-pdf.jpg).
- Errores encontrados en esa revisión y corregidos:
  - con el total ya reportado, la página pedía "pagar S/ 0.00";
  - en 375 px el menú cortaba "Mi reserva" (ahora pasa a una segunda línea).

## 5. Pendientes

- **F5**: el operador verifica pagos (`pagada`, y asignación de familia para las reservas Yape/Plin con noche), y se programa la ruta `/panel/abordaje/<código>` que abre el QR.
- **F6**: reprogramar o pedir la devolución desde la reserva cuando la salida se suspende, reseñas e inglés.
- **F7**: la **prueba mutante**: quitar el `FOR UPDATE` y ver que la prueba de los 8 hilos falla.
- **PR-07** (propuesta): límite de intentos también en `/mi-reserva`. Probar todas las combinaciones es inviable (31⁴ códigos × 10⁸ documentos), pero protegería mejor los datos personales.

---

## Para explicar al docente

### 1. Bloquear la salida: `SELECT … FOR UPDATE` (RN-02, paso 1)

```sql
-- Devuelve la salida y la bloquea hasta el COMMIT.
SELECT id, ruta_id, cupo, estado, fecha_hora_zarpe, fecha_hora_zarpe > NOW() AS aun_no_zarpa
FROM salida
WHERE id = %s
FOR UPDATE;
```

- **FOR UPDATE** pone un candado en **esa fila**. Si otra persona está reservando la misma salida, su transacción **espera aquí** hasta que la primera haga COMMIT o ROLLBACK. Así, dos reservas de la misma salida nunca cuentan cupos al mismo tiempo.
- Las reservas de **otras** salidas no esperan: el candado es de una sola fila.
- `fecha_hora_zarpe > NOW() AS aun_no_zarpa` devuelve 1 o 0: no se reserva una salida que ya partió.

### 2. Contar los ocupados con "lectura actual" (RN-01 / RN-02, paso 2)

```sql
-- Cuenta los pasajeros que ocupan lugar en la salida (confirmada, pagada, abordada,
-- o pendiente de pago que todavía no vence).
SELECT COUNT(*) AS ocupados
FROM reserva_pasajero rp
JOIN reserva r ON r.id = rp.reserva_id
WHERE r.salida_id = %s
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
LOCK IN SHARE MODE;
```

- **¿Por qué no basta un SELECT normal?** En **REPEATABLE READ**, el nivel por defecto de MariaDB, un SELECT normal lee una **foto** de la base tomada en la primera lectura de la transacción. Si otra persona confirmó una reserva después de esa foto, no la veríamos, contaríamos un lugar libre que ya no existe y **venderíamos de más**.
- Se usan dos defensas:
  - la transacción va en **READ COMMITTED**, y cada SELECT ve lo último confirmado;
  - el conteo usa **LOCK IN SHARE MODE**, una lectura con bloqueo que siempre lee la versión más reciente.
- `libres = cupo − ocupados`. Si los pasajeros pedidos son más que los libres, se cancela todo con **ROLLBACK** y se muestra "Solo quedan N lugares".
- **Cómo se prueba:** 8 hilos piden el último lugar al mismo tiempo, y solo 1 lo consigue (`test_concurrencia.py`).

### 3. ¿Algún documento ya viaja en esa salida? (RN-09, con `IN` de pares)

```sql
-- Devuelve los documentos de esta reserva que ya ocupan lugar en la salida.
SELECT rp.tipo_documento, rp.numero_documento
FROM reserva_pasajero rp
JOIN reserva r ON r.id = rp.reserva_id
WHERE r.salida_id = %s
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
  AND (rp.tipo_documento, rp.numero_documento) IN ((%s, %s), (%s, %s))
LOCK IN SHARE MODE;
```

- `(tipo, número) IN ((…), (…))` compara **pares**: DNI 70000081 y CE 70000081 son documentos distintos.
- Python arma tantos `(%s, %s)` como pasajeros haya, pero **los valores siempre van como parámetros**. Ningún dato del turista se pega dentro del texto SQL.
- No puede ser un UNIQUE de la tabla: `reserva_pasajero` no tiene `salida_id`, y una reserva vencida o cancelada no debe impedir volver a reservar.

### 4. Rotación justa de familias (RN-10): un ORDER BY con 3 criterios

```sql
SELECT f.id, f.nombre_familia,
       (SELECT COUNT(*) FROM hospedaje h
        WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido')
          AND h.fecha_noche BETWEEN %s - INTERVAL 30 DAY AND %s - INTERVAL 1 DAY) AS noches_30_dias,
       (SELECT MAX(h.fecha_noche) FROM hospedaje h
        WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido')
          AND h.fecha_noche < %s) AS ultima_noche
FROM familia_anfitriona f
WHERE f.comunidad_id = %s AND f.activa = 1 AND f.capacidad_personas >= %s
  AND NOT EXISTS (SELECT 1 FROM hospedaje h
                  WHERE h.familia_id = f.id AND h.fecha_noche = %s
                    AND h.estado IN ('asignado','cumplido'))
ORDER BY noches_30_dias, ultima_noche IS NOT NULL, ultima_noche, f.id
LIMIT 1
FOR UPDATE;
```

- **WHERE**: familias activas, de la comunidad donde se duerme, con capacidad para el grupo y **libres esa noche** (`NOT EXISTS`: no tienen otra reserva esa fecha).
- **ORDER BY**, en el orden de RN-10:
  1. `noches_30_dias`: menos noches en los 30 días anteriores;
  2. `ultima_noche IS NOT NULL, ultima_noche`: la que espera desde hace más tiempo; si **nunca** recibió (NULL), va primera, porque `IS NOT NULL` vale 0 para ella;
  3. `f.id`: desempate final.
- **LIMIT 1** toma la primera. **FOR UPDATE** bloquea las candidatas: dos reservas de la misma noche no se quedan con la misma familia.
- Ejemplo con la semilla de Llachón para una noche dentro de 20 días: primero la **familia 8** (nunca recibió), luego la **6** (su última noche fue hace 12 días, fuera de la ventana) y por último la **7** (tiene 1 noche en la ventana). Así lo comprueba `test_rotacion_justa_de_familias`.

### 5. Reportar un pago: UPDATE con JOIN y GREATEST (D-09)

```sql
UPDATE reserva r
JOIN salida s ON s.id = r.salida_id
SET r.vence_en = GREATEST(r.vence_en, s.fecha_hora_zarpe - INTERVAL 60 MINUTE)
WHERE r.id = %s;
```

- Se ejecuta **después** del `INSERT INTO pago (... 'reportado')`, en la misma transacción.
- **UPDATE … JOIN**: para calcular el nuevo plazo hace falta la hora de zarpe, que está en `salida`.
- **GREATEST(a, b)** devuelve el mayor de los dos. El plazo pasa a "60 minutos antes del zarpe", pero **nunca se acorta**: si ya era más largo, se queda.
- Así la verificación del operador, que puede tardar horas, no le quita el lugar a quien ya pagó.
