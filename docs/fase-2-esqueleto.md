# Fase 2 · Esqueleto, inicio de sesión y roles

> Estado: entregada el 19/10/2026. Espera el "ok" del equipo para pasar a la F3.

## 1. Qué hicimos

- **App factory completa** (`crear_app`), con 3 blueprints:
  - `publico`: `/` provisional y `/salud`;
  - `autenticacion`: `/entrar` y `/salir`;
  - `panel`: `/panel` y `/panel/bitacora`.
- **Capas respetadas**: las rutas no tienen SQL; todo el SQL está en `app/modelos/` (usuario, panel, bitácora y sistema), con un comentario que dice qué devuelve cada consulta.
- **Inicio de sesión** con Flask-Login, Flask-WTF y bcrypt:
  - mensaje genérico para cualquier falla, y un hash ficticio para que la respuesta tarde lo mismo si el usuario no existe;
  - **5 intentos fallidos cada 15 minutos** (Flask-Limiter), sin contar los ingresos correctos;
  - las contraseñas de más de 72 bytes se rechazan sin romper nada (bcrypt 5 daba error).
- **Bitácora de inicios de sesión** (RN-14): `UPDATE ultimo_acceso` + `INSERT bitacora`, en una sola transacción.
- **Roles**:
  - `@requiere_rol` en la ruta y `exigir_rol` en el modelo;
  - `/panel` muestra un resumen distinto para operador o admin (pendientes y salidas de hoy) y para guía o capitán (solo sus salidas);
  - la bitácora es solo para el admin, con filtro por acción en lista blanca y paginación.
- **Seguridad (sección 11)**:
  - CSRF en todo POST;
  - CSP `'self'`, `X-Frame-Options: DENY` y `nosniff`;
  - cookie HttpOnly y SameSite=Lax (Secure en producción);
  - `no-store` en el panel;
  - `?next=` solo a rutas internas.
- **Páginas de error** 400 (formulario vencido), 403, 404, 405, 429 y 500, sin trazas. El 500 no consulta la base.
- **`/salud`**: `{"ok": true, "hora": "…-05:00"}`, o **503** si la base no responde.
- **Registro** en `logs/app.log`, con hora de Lima: arranques, inicios de sesión y errores.
- **Layout mobile-first** con la paleta y el logo:
  - en el celular, el isotipo y el nombre; en pantallas anchas, el logo completo;
  - enlace "Saltar al contenido", foco visible, botones de 44 px y contraste AA medido (D-06 y D-27).
- **Íconos PNG** (`apple-touch-icon` y `favicon-32`), generados con Pillow desde la geometría del logo.
- **`servidor.py`** con waitress, para la demostración o la red local.

## 2. Archivos creados o cambiados

| Archivo | Qué es |
|---|---|
| `app/__init__.py`, `config.py` | Factory, cookies, límites y caché por entorno. |
| `app/seguridad.py`, `errores.py`, `registro.py` | Sesión, CSRF, límite, roles, cabeceras, errores y log. |
| `app/bd.py` | Agrega `consultar()` y `consultar_uno()`, y un tiempo de espera de 5 s. |
| `app/modelos/__init__.py`, `usuario.py`, `panel.py`, `bitacora.py`, `sistema.py` | El SQL de la F2. |
| `app/rutas/publico.py`, `autenticacion.py`, `panel.py` | Las rutas. |
| `app/formularios/autenticacion.py` | El formulario de ingreso. |
| `app/servicios/formato.py` | Fechas en español y soles, sin depender del locale de Windows. |
| `app/plantillas/…` | `base.html`, `macros.html`, entrar, panel, bitácora, portada y error. |
| `app/estaticos/css/estilos.css`, `img/*.png` | Estilos e íconos. |
| `scripts/generar_iconos.py`, `servidor.py` | Íconos y servidor waitress. |
| `tests/test_rutas_autenticacion.py`, `test_rutas_panel.py`, `test_seguridad_y_errores.py` | 53 pruebas nuevas. |
| `docs/matriz-permisos.md`, `arquitectura.md`, `trazabilidad.md` | Documentación nueva. |
| `README.md`, `decisiones.md` | Actualizados. |

## 3. Comandos para probarlo

Desde `titicaca_vivo`, con el venv activo:

```powershell
flask run                         # desarrollo: http://127.0.0.1:5000
python servidor.py                # waitress: http://127.0.0.1:8080
pytest -v                         # 165 pruebas
ruff check .
```

Recorrido manual:

1. Abrir `/entrar`.
2. Enviar el formulario vacío: debe dar 422, con los errores arriba y junto a cada campo.
3. Entrar como `operador`: aparecen las alertas, los pendientes y las salidas de hoy.
4. Abrir `/panel/bitacora`: debe dar **403**.
5. Salir y entrar como `admin`: la bitácora muestra el inicio de sesión recién hecho.
6. Abrir `/salud`.

## 4. Evidencia (19/10/2026)

- `pytest -v`: **165 passed in 14 s**. Son las 112 de la F1 más 25 de autenticación, 17 de panel y permisos y 11 de seguridad y errores → [evidencias/f2-pytest.txt](evidencias/f2-pytest.txt).
- `ruff check .`: *All checks passed!*
- Revisión en el navegador, con waitress en el puerto 5050:
  - celular de 375 px: [f2-entrar-celular.jpg](evidencias/f2-entrar-celular.jpg), [f2-entrar-errores-celular.jpg](evidencias/f2-entrar-errores-celular.jpg), [f2-panel-operador-celular.jpg](evidencias/f2-panel-operador-celular.jpg);
  - escritorio de 1280 px: [f2-bitacora-escritorio.png](evidencias/f2-bitacora-escritorio.png);
  - teclado: [f2-foco-teclado.png](evidencias/f2-foco-teclado.png), con "Saltar al contenido" y el anillo de foco;
  - la consola del navegador no mostró ninguna violación de la CSP.
- Peso de `/entrar` con su CSS y sus imágenes: < 100 KB, comprobado en una prueba. El HTML pesa unos 2.8 KB y el CSS unos 11 KB.
- `logs/app.log`: `2026-10-19 23:08:52-0500 INFO app: Inicio de sesión: admin desde 127.0.0.1`.

## 5. Pendientes

- **Python 3.13**: sigue pendiente de la F1 (las pruebas corren con 3.11).
- **HTTPS en producción**: con `ENTORNO=produccion` la cookie lleva `Secure`, así que hace falta un proxy con TLS delante de waitress (F8).
- El límite de intentos vive en la memoria del proceso, y con un solo proceso de waitress alcanza. Si algún día se usan varios procesos, habría que guardarlo en Redis (está en decisiones.md).
- La portada `/` es provisional: la real llega en la **F3**, con las salidas, las alertas, el mapa y las comunidades.
- PR-03 (registrar también los ingresos fallidos) sigue esperando el "ok".

---

## Para explicar al docente

### 1. ¿Cómo sabe la app quién entra? (SELECT con JOIN y parámetro `%s`)

```sql
-- Devuelve el usuario con ese nombre, su rol y su hash (para comparar la contraseña).
SELECT u.id, u.nombre_usuario, u.nombre_completo, u.comunidad_id, u.activo,
       u.hash_contrasena, r.codigo AS rol, r.nombre AS rol_nombre
FROM usuario u
JOIN rol r ON r.id = u.rol_id
WHERE u.nombre_usuario = %s
```

- **JOIN rol**: el usuario guarda solo `rol_id`, un número. Para saber si es "capitan" hay que juntarlo con la tabla `rol`.
- **`%s`** es un **parámetro**: PyMySQL pone ahí lo que escribió la persona, pero como dato, no como parte del SQL. Si alguien escribe `' OR '1'='1`, se busca un usuario con ese nombre raro y no aparece nadie. Eso es lo que evita la *inyección SQL*.
- La base devuelve el **hash**, no la contraseña, y la comparación la hace Python con `bcrypt.checkpw`. Si el usuario no existe, se compara contra un hash ficticio, para que la respuesta tarde lo mismo y no delate qué usuarios existen.

### 2. Registrar el ingreso: dos sentencias en UNA transacción

```sql
UPDATE usuario SET ultimo_acceso = NOW() WHERE id = %s;
INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
VALUES (%s, 'inicio_sesion', 'usuario', %s, %s, %s);
```

- Las dos van dentro de `with bd.transaccion()`: si ambas salen bien, **COMMIT**; si la segunda falla, **ROLLBACK**, y tampoco queda el `ultimo_acceso`. Nunca queda la mitad.
- `NOW()` da la hora de Lima porque cada conexión hace `SET time_zone = '-05:00'`.
- `detalle` es un JSON (`{"resultado": "ok"}`). La tabla tiene `CHECK (JSON_VALID(detalle))`, así que la base no acepta un JSON roto.

### 3. Las salidas del capitán (JOIN con una vista y un rango de fechas)

```sql
-- Devuelve las salidas de este capitán de hoy y los 2 días siguientes, con sus ocupados.
SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.embarcacion_nombre,
       v.matricula, v.cupo, v.ocupados, v.libres, v.estado, v.estado_publico
FROM v_disponibilidad_salida v
JOIN salida s ON s.id = v.salida_id
WHERE s.capitan_id = %s
  AND v.fecha_hora_zarpe >= CURDATE()
  AND v.fecha_hora_zarpe <  CURDATE() + INTERVAL 3 DAY
ORDER BY v.fecha_hora_zarpe;
```

- La **vista** ya trae los ocupados y los libres calculados (F1), pero no trae `capitan_id`. Por eso se junta con `salida`.
- `>= CURDATE()` y `< CURDATE() + INTERVAL 3 DAY` cubren desde hoy a las 00:00 hasta antes de dentro de 3 días. Se usa `<` y no `<=` para no incluir el día 4 a las 00:00.
- Ejemplo con la semilla: para `capitan.teodoro` salen las salidas 7 y 8 (hoy, Uros), la 10 (mañana, Uros y Taquile) y la 13 (pasado mañana, Uros y Luquina Chico). Las de Fermín no salen.

### 4. Alertas vigentes (LEFT JOIN, COALESCE y ordenar un ENUM)

```sql
-- Devuelve las alertas vigentes ahora, de la más grave a la más leve.
SELECT a.id, a.tipo, a.nivel, a.titulo, a.fuente, a.vigente_hasta,
       COALESCE(c.nombre, 'Todo el lago') AS lugar
FROM alerta_lago a
LEFT JOIN comunidad c ON c.id = a.comunidad_id
WHERE a.vigente_desde <= NOW() AND a.vigente_hasta > NOW()
ORDER BY a.nivel DESC, a.vigente_hasta;
```

- **LEFT JOIN**: una alerta con `comunidad_id` NULL es de **todo el lago**. Con un JOIN normal desaparecería; con LEFT JOIN se queda, y `c.nombre` sale NULL.
- **COALESCE** cambia ese NULL por el texto "Todo el lago".
- **WHERE**: "vigente" significa que ya empezó y todavía no terminó.
- **ORDER BY a.nivel DESC**: un ENUM se ordena por su **posición** en la definición (verde = 1, amarillo = 2, naranja = 3, rojo = 4), no alfabéticamente. Con DESC, lo rojo sale primero.
- Ejemplo: la "Oleaje fuerte en el sector de Amantaní" (naranja) sale primero, y luego "Heladas en la madrugada" (amarilla, todo el lago).

### 5. Bitácora paginada (filtro opcional y LIMIT/OFFSET)

```sql
-- Devuelve una página de la bitácora, lo más reciente primero, con el usuario si lo hay.
SELECT b.id, b.creado_en, b.accion, b.tabla_afectada, b.registro_id,
       b.detalle, b.ip, u.nombre_usuario
FROM bitacora b
LEFT JOIN usuario u ON u.id = b.usuario_id
WHERE (%s IS NULL OR b.accion = %s)
ORDER BY b.creado_en DESC, b.id DESC
LIMIT %s OFFSET %s
```

- **LEFT JOIN usuario**: las acciones del turista o del sistema tienen `usuario_id` NULL y deben verse igual.
- **`(%s IS NULL OR b.accion = %s)`** es un filtro opcional. Si no se eligió una acción, se manda NULL, el `IS NULL` es verdadero y pasan todas las filas. Si se eligió `inicio_sesion`, solo pasan esas. Además, la ruta solo acepta acciones que existen en la tabla (lista blanca).
- **LIMIT 25 OFFSET 25** salta las primeras 25 filas y trae las siguientes 25: es la página 2. La ruta calcula `OFFSET = (página − 1) × 25`.
- **ORDER BY creado_en DESC, id DESC**: el segundo criterio desempata dos registros del mismo segundo.
