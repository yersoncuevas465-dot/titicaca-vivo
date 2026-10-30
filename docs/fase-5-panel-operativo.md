# Fase 5 · Panel operativo

La F5 completa el trabajo diario de la agencia en el muelle y en la oficina:

- programar salidas con la regla RN-07, editarlas, suspenderlas, cancelarlas y marcar el zarpe;
- ver la lista de pasajeros: en pantalla, para imprimir, como manifiesto PDF y para WhatsApp;
- registrar el abordaje leyendo el QR del boleto (o escribiendo el código);
- verificar o rechazar los pagos Yape/Plin y cobrar en el muelle;
- mantener los 7 catálogos y los usuarios del personal.

## 1. Qué hicimos

**Salidas** (`/panel/salidas`, solo el operador; el admin solo mira)

- **Lista por día**, con flechas para el día anterior y el siguiente, más un selector de fecha. Incluye las salidas canceladas.
- **Crear** (`/panel/salidas/nueva`). El modelo revisa la regla **RN-07** antes del INSERT:
  - la lancha está operativa y el cupo no pasa su capacidad;
  - el capitán tiene rol capitán, está activo y tiene licencia;
  - el guía, si se elige, tiene rol guía;
  - la misma lancha no tiene otra salida que se cruce (sin contar las canceladas ni las suspendidas);
  - el zarpe es en el futuro.

  El retorno se calcula con la duración de la ruta (D-63). La **lancha se bloquea con `FOR UPDATE`**: así dos salidas creadas al mismo tiempo no se pueden cruzar (D-65). El trigger de la F1 sigue siendo la red de seguridad.
- **Editar**: no se edita una salida que ya zarpó o se canceló. El cupo nuevo no puede ser menor que los ocupados, que se cuentan con lectura actual. Con reservas, se puede cambiar la hora pero **no el día** (D-64). La ruta no cambia.
- **Suspender** (con motivo): las reservas quedan como están y el turista ve el motivo. Reprogramar o pedir la devolución llega en la F6.
- **Cancelar** (con motivo): solo una salida **sin reservas activas**. Si tiene reservas, el sistema pide suspenderla (D-66).
- **Marcar zarpe**: lo hace el operador o el capitán **de esa salida**, desde 60 minutos antes. La salida pasa a `zarpo`. Las reservas confirmadas o pagadas **sin nadie a bordo** pasan a `no_show` (S-11, D-67).
- Cada cambio de estado lo escribe en la bitácora el trigger `trg_salida_au`, con el usuario y la IP de la app (S-24). La creación y la edición las anota el modelo.

**Pasajeros de una salida** (`/panel/salidas/<id>/pasajeros`)

- Los ven el operador y el admin. El guía y el capitán solo ven **sus** salidas (◐); si no, reciben 403.
- La lista está agrupada por reserva y muestra:
  - el titular y su teléfono, y el estado de la reserva;
  - si falta pagar;
  - quién ya abordó, a qué hora y si fue por QR o a mano.
- `?formato=pdf` → **manifiesto de zarpe** en A4 (D-72): lancha, matrícula, capitán con su licencia, guía y cada pasajero con su documento, nacionalidad, tipo, reserva y hora de abordaje. Lleva firmas, número de hoja y hora de Lima.
- `?formato=whatsapp` → el texto listo y un enlace **wa.me** (D-73). No se usa la API: la persona elige el contacto y envía. Si el guía tiene teléfono, hay un botón para enviárselo. **El texto no lleva documentos ni teléfonos** de los turistas.
- `?formato=imprimir` → **lista liviana para imprimir** o guardar como PDF desde el navegador. Es el modo baja señal (sección 8.6, D-74).

**Abordaje** (`/panel/abordaje/<código>`: la URL que va dentro del QR del boleto)

- Sin sesión, la página lleva a `/entrar` y, después de iniciar sesión, vuelve a la reserva.
- Lo registran el operador y el guía o el capitán **de esa salida** (S-23). El admin no.
- **RN-12**:
  - solo de 60 minutos antes a 15 minutos después del zarpe;
  - solo reservas confirmadas o pagadas (una Yape/Plin sin verificar no sube);
  - la salida tiene que estar programada (no suspendida ni zarpada);
  - cada pasajero aborda **una vez** (lo revisa el modelo y, de respaldo, el UNIQUE).
- Todos los pasajeros vienen marcados; se desmarca a quien no llegó. Cuando sube todo el grupo, la reserva pasa a `abordada`.
- Si la reserva paga en el muelle y falta dinero, aparece "Falta pagar S/ X". El operador lo **cobra ahí mismo**, en efectivo, POS o transferencia (D-71).
- `/panel/abordaje?codigo=TV-XXXX` es para el turista que no tiene el boleto: queda registrado como `manual`.

**Pagos** (`/panel/pagos`, RN-06)

- Muestra los pagos reportados, del más antiguo al más nuevo, con la reserva, el titular, la salida, lo ya verificado y hasta cuándo se guarda el lugar.
- **Verificar**: si lo verificado llega al total, la reserva pasa a `pagada`. Si la ruta tiene noche, en la **misma transacción** se asigna la familia por rotación (RN-10, D-52). Si no queda familia libre, el pago se verifica igual y se avisa (D-69).
- **Rechazar**: el motivo es obligatorio. Si no quedan otros pagos por revisar, el turista vuelve a tener 2 horas (D-09, D-70).
- Una reserva vencida no se verifica: su lugar ya no está guardado y podría haberse vendido (D-69).

**Catálogos** (`/panel/catalogos`, admin y operador)

- Son 7: rutas (con sus paradas), lanchas, tarifas, temporadas, tipos de pasajero, comunidades y familias.
- Tienen una lista y un formulario. Nada se borra; se desactiva. Lo único que se borra son las paradas (D-75).
- Reglas que protegen la operación (D-76):
  - una lancha con salidas por venir no sale de operación ni baja su capacidad;
  - las temporadas no se solapan (S-14);
  - una sola parada de pernocte por ruta (S-16);
  - una familia con noches asignadas no se desactiva ni baja su capacidad;
  - una comunidad que es parada de una ruta activa no se desactiva.

**Usuarios** (`/panel/usuarios`, solo admin)

- Se pueden dar de alta, editar, desactivar y cambiar la contraseña. Se guarda con bcrypt y nunca queda en la bitácora.
- El guía necesita una comunidad y el capitán una licencia.
- El admin no se puede desactivar a sí mismo. Un capitán con salidas por venir no se desactiva (D-78).

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `app/modelos/salida.py` | Parte del panel: lista, RN-07, crear, editar, suspender, cancelar, zarpe y pasajeros. |
| `app/modelos/pago.py` (nuevo) | Verificar, rechazar, cobrar en el muelle y pasar a `pagada` (con la familia). |
| `app/modelos/abordaje.py` (nuevo) | Buscar por código y registrar (RN-12). |
| `app/modelos/embarcacion.py`, `temporada.py`, `tipo_pasajero.py`, `familia.py` (nuevos) | Catálogos, con su SQL a la vista. |
| `app/modelos/ruta.py`, `tarifa.py`, `comunidad.py`, `usuario.py` | Su parte del panel (con las paradas y los usuarios). |
| `app/modelos/catalogo.py`, `validacion.py` (nuevos) | Guardar (INSERT o UPDATE + 1062 + bitácora) y validar campos. |
| `app/modelos/__init__.py`, `bitacora.py`, `bd.py` | `ErrorValidacion`, `EstadoNoPermite`, `bitacora.anotar()` y `transaccion(lectura_actual=True)`. |
| `app/formularios/__init__.py`, `panel.py`, `catalogos.py` | Formularios con mensajes en español (D-80). |
| `app/rutas/panel.py`, `app/rutas/catalogos.py` (nuevo) | 14 vistas nuevas en el panel y 5 en catálogos (sin SQL). |
| `app/servicios/pdf.py`, `whatsapp.py` (nuevo) | Manifiesto A4 y enlace wa.me. |
| `app/plantillas/panel/*` (15 plantillas nuevas; cambian `base_panel` e `inicio`), `estilos.css` | Páginas del panel, menú por rol y estilos. |
| `tests/test_reglas_salida.py`, `test_reglas_pago_abordaje.py`, `test_catalogos.py`, `test_rutas_panel_operacion.py` | 109 pruebas nuevas. |
| `tests/conftest.py` | `salida_cerca` (salidas que zarpan en X minutos), `reservar_en` y `actor`. |

## 3. Comandos para probarlo

```powershell
flask bd reiniciar --si
python servidor.py --host 0.0.0.0     # para abrir el QR desde un celular en la misma red
pytest -v --cov=app/modelos           # 392 pruebas
ruff check .
```

Recorrido sugerido (usuarios demo del README):

1. **operador** → *Salidas* → *Nueva salida*. Elegir una lancha **en mantenimiento** (aparece el error junto al campo). Elegir una operativa en el horario de otra salida (error de cruce). Corregir y guardar.
2. En esa salida: *Lista para WhatsApp* (abre WhatsApp con el texto) y *Manifiesto (PDF)*.
3. *Pagos* → verificar el pago de TV-RQCP: la reserva queda **PAGADA**.
4. Con el boleto de una reserva que sale en menos de 1 hora, leer el QR con el celular (o *Abordaje* → escribir el código), cobrar si falta y confirmar el abordaje: queda **abordada**.
5. **capitan.teodoro** → *Resumen* → una de sus salidas → *Marcar zarpe*. Quien no subió queda como «no se presentó».
6. **admin** → *Usuarios* → crear un guía sin comunidad (error), corregir y entrar con él.

## 4. Evidencia (20/10/2026)

- `pytest -v --cov=app/modelos`: **392 passed in 74 s**, con **91 %** de cobertura en `app/modelos` (el mínimo es 80 %) → [evidencias/f5-pytest.txt](evidencias/f5-pytest.txt).
  - 24 pruebas de salidas: RN-07, editar, suspender, cancelar y zarpe con `no_show`;
  - 18 de pagos y abordaje: RN-06, D-09, RN-10 al pagar, cobro en el muelle, ventana RN-12, una vez por pasajero y ◐ del guía;
  - 33 de catálogos y usuarios: UNIQUE, solapes, reglas que protegen la operación y permisos;
  - 34 de rutas: la **matriz de permisos completa** (14 URL × 4 roles), sin sesión → `/entrar?next=`, CSRF → 400, POST → 303, 422 con el error junto al campo, PDF, WhatsApp sin documentos y "ninguna ruta tiene SQL".
- `ruff check .`: *All checks passed!*
- En el navegador (app local, 375 px):
  - cobro en el muelle de TV-WWUQ → **pagada**;
  - abordaje de sus 5 pasajeros → **abordada** → [f5-abordaje-celular.jpg](evidencias/f5-abordaje-celular.jpg);
  - página de la salida → [f5-salida-pasajeros-celular.jpg](evidencias/f5-salida-pasajeros-celular.jpg);
  - pago de TV-RQCP → [por verificar](evidencias/f5-pagos-por-verificar-celular.jpg) y [verificado](evidencias/f5-pago-verificado-celular.jpg);
  - manifiesto dibujado con pdf.js → [f5-manifiesto-pdf.png](evidencias/f5-manifiesto-pdf.png).

  Después se reinició la base a la semilla (269 filas).
- Lo que se corrigió en esa revisión:
  - en el manifiesto, el código de reserva se partía en dos líneas;
  - el estado de la salida aparecía en minúsculas.

## 5. Pendientes

- **Confirmar con Giant Trip**:
  - si la familia cobra cuando el turista no se presenta (`no_show`): hoy su noche queda `asignado`;
  - si una reserva con **parte** del grupo a bordo al zarpar debe pasar a `abordada`: hoy queda como estaba, y el manifiesto muestra quién subió.
- **F6**:
  - suspender por alerta varias salidas en un paso;
  - reprogramar o pedir la devolución desde la reserva;
  - reasignar familias a mano (también las reservas pagadas que quedaron sin familia, D-69);
  - reporte de transparencia, reseñas, indicadores e inglés.
- **Propuestas nuevas** (en [decisiones.md](decisiones.md)):
  - PR-08: el mismo capitán no puede tener dos salidas que se crucen;
  - PR-09: un service worker para ver la última lista sin señal;
  - PR-10: marcar `finalizada` al volver y pasar los hospedajes a `cumplido`;
  - PR-11: reactivar una salida suspendida.

---

## Para explicar al docente

### 1. ¿Se cruza la lancha con otra salida? (RN-07)

```sql
-- Bloquea la lancha hasta el COMMIT (dos salidas para la misma lancha se revisan una tras otra).
SELECT capacidad_maxima, estado FROM embarcacion WHERE id = %s FOR UPDATE;

-- Devuelve otra salida de la misma lancha cuyo horario se cruza con el nuevo.
SELECT s.fecha_hora_zarpe, r.nombre AS ruta
FROM salida s
JOIN ruta r ON r.id = s.ruta_id
WHERE s.embarcacion_id = %s                         -- la misma lancha
  AND s.id <> %s                                    -- sin contarse a sí misma (al editar)
  AND s.estado NOT IN ('cancelada','suspendida')    -- esas no ocupan la lancha
  AND s.fecha_hora_zarpe < %s                       -- la otra empieza antes de que esta vuelva…
  AND %s < s.fecha_hora_retorno                     -- …y esta empieza antes de que la otra vuelva
ORDER BY s.fecha_hora_zarpe
LIMIT 1;
```

- **Dos horarios se cruzan** si cada uno empieza antes de que termine el otro. Por ejemplo, 07:00–16:30 y 12:00–15:00 se cruzan; 07:00–16:30 y 17:00–20:00 no.
- El primer SELECT bloquea **la fila de la lancha**. Si dos operadores crean salidas para la misma lancha a la vez, el segundo espera. Cuando sigue, ya ve la salida del primero (lectura actual, READ COMMITTED).
- `LIMIT 1`: basta encontrar una salida que se cruce para mostrar el error.

### 2. El manifiesto: pasajeros, abordaje y lo pagado en una sola consulta

```sql
-- Devuelve cada pasajero de las reservas que ocupan lugar, si ya abordó y cuánto pagó su reserva.
SELECT r.codigo, r.estado AS estado_reserva, r.total, COALESCE(pv.pagado, 0) AS pagado,
       rp.nombres, rp.apellidos, rp.tipo_documento, rp.numero_documento, rp.nacionalidad,
       tp.nombre AS tipo, t.telefono AS titular_telefono,
       a.registrado_en AS abordo_en, a.metodo AS metodo_abordaje
FROM reserva r
JOIN reserva_pasajero rp ON rp.reserva_id = r.id
JOIN tipo_pasajero tp    ON tp.id = rp.tipo_pasajero_id
JOIN turista t           ON t.id = r.turista_id
LEFT JOIN abordaje a     ON a.reserva_pasajero_id = rp.id AND a.salida_id = r.salida_id
LEFT JOIN (SELECT p.reserva_id, SUM(p.monto) AS pagado
           FROM pago p JOIN reserva r2 ON r2.id = p.reserva_id
           WHERE r2.salida_id = %s AND p.estado = 'verificado'
           GROUP BY p.reserva_id) pv ON pv.reserva_id = r.id
WHERE r.salida_id = %s
  AND (r.estado IN ('confirmada','pagada','abordada')
       OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
ORDER BY r.codigo, rp.id;
```

- Los **JOIN** traen lo que siempre existe: la reserva, sus pasajeros, el tipo y el titular.
- **LEFT JOIN abordaje**: un pasajero que todavía no subió también aparece, con `abordo_en` en NULL (en pantalla se ve "—").
- **LEFT JOIN a una subconsulta con GROUP BY**: suma los pagos verificados **por reserva** antes de unirlos. Si se sumara después del JOIN con los pasajeros, una reserva de 4 personas sumaría su pago 4 veces.
- El WHERE usa la misma condición de RN-01: solo las reservas que ocupan lugar.
- Es **una sola consulta** para toda la salida, sin N+1. El PDF, la lista para imprimir y la de WhatsApp salen de ella.

### 3. Al zarpar, ¿quién no se presentó? (NOT EXISTS)

```sql
-- Devuelve (y bloquea) las reservas confirmadas o pagadas sin NINGÚN pasajero a bordo.
SELECT r.id, r.codigo, r.estado
FROM reserva r
WHERE r.salida_id = %s
  AND r.estado IN ('confirmada','pagada')
  AND NOT EXISTS (SELECT 1
                  FROM reserva_pasajero rp
                  JOIN abordaje a ON a.reserva_pasajero_id = rp.id AND a.salida_id = r.salida_id
                  WHERE rp.reserva_id = r.id)
FOR UPDATE;
```

- **NOT EXISTS** es verdadero cuando la subconsulta **no devuelve ninguna fila**: nadie de esa reserva abordó.
- La subconsulta es **correlacionada**: usa `r.id` de la consulta de afuera, así que se evalúa para cada reserva.
- A cada una se le hace `UPDATE reserva SET estado = 'no_show'` y se anota en la bitácora, todo dentro de la misma transacción que pasa la salida a `zarpo`.

### 4. Verificar un pago: ¿ya llegó al total? (RN-06)

```sql
-- Devuelve la suma de los pagos verificados de la reserva (un rechazado no suma).
SELECT COALESCE(SUM(monto), 0) AS pagado
FROM pago
WHERE reserva_id = %s AND estado = 'verificado';
```

- Se ejecuta **después** de marcar el pago como verificado, dentro de la misma transacción, con la reserva bloqueada (`FOR UPDATE`).
- **COALESCE** cambia NULL por 0: `SUM` de cero filas da NULL.
- Si `pagado >= total`, la reserva pasa a `pagada` y, si la ruta tiene noche, se elige la familia con la consulta de rotación de la F4 (RN-10). Los pagos parciales (S-12) se suman solos.

### 5. ¿Está abierta la ventana de abordaje? (RN-12)

```sql
-- Devuelve 1 si AHORA está entre 60 minutos antes y 15 minutos después del zarpe.
SELECT (NOW() BETWEEN s.fecha_hora_zarpe - INTERVAL 60 MINUTE
                  AND s.fecha_hora_zarpe + INTERVAL 15 MINUTE) AS en_ventana,
       (NOW() < s.fecha_hora_zarpe - INTERVAL 60 MINUTE)     AS antes_de_ventana
FROM salida s
WHERE s.id = %s
LOCK IN SHARE MODE;
```

- La cuenta la hace **la base** con su `NOW()`, que está en hora de Lima (RN-15). No depende del reloj del celular del guía.
- `BETWEEN a AND b` incluye los dos extremos.
- `antes_de_ventana` sirve para elegir el mensaje: "abre a las…" o "cerró…".
- **LOCK IN SHARE MODE**: mientras se registra el abordaje, nadie puede marcar el zarpe de esa salida. Dos guías sí pueden registrar a la vez, porque la lectura compartida no los bloquea entre sí. Después se bloquea la reserva con `FOR UPDATE`, siempre en ese orden (salida y luego reserva), igual que en el zarpe: así no se producen interbloqueos.
