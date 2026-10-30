# Fase 8 · Entrega (Platino)

La F8 cierra el proyecto:

- **Platino**: la misma aplicación corre contra otro servidor de base de datos, cambiando solo el `.env`;
- **HTTPS**: cómo ponerla en producción detrás de un proxy, con la cookie `Secure`;
- **revisión de dependencias a mano** (sin `pip-audit`);
- **documentación completa**, con `consultas-explicadas.md`;
- **un ZIP** sin `.env` ni entorno virtual.

## 1. Qué hicimos

### Platino: otro servidor, cambiando solo el `.env` (sección 4)

El enunciado pide «todo lo anterior contra un servidor de base de datos real (el MariaDB de XAMPP y,
como extra, un MySQL/MariaDB en otra PC o en la nube), cambiando solo el .env».

- **El MariaDB de XAMPP** es un servidor real desde la F1. Todas las pruebas (485 en la entrega), la semilla y cada pantalla usan
  MariaDB 10.4.32. No hay SQLite ni ORM.
- **El extra: un segundo servidor.** En esta PC no había otro MySQL/MariaDB ni acceso a la nube.
  Por eso armamos un **segundo servidor MariaDB**, separado del de XAMPP:
  - otro puerto (3307);
  - su propia carpeta de datos;
  - su propio `root` y su propio `titicaca_app`, con contraseñas nuevas generadas al azar, que no
    están en el proyecto.

  Después cambiamos **2 líneas del `.env`** (`BD_PUERTO` y `BD_CONTRASENA`) y corrimos todo:

| Paso | Resultado (20/10/2026) |
|---|---|
| Cambiar el `.env` | Cambiaron solo `BD_PUERTO` y `BD_CONTRASENA`; el resto quedó igual |
| `flask bd reiniciar --si` | 20 tablas, 269 filas en `127.0.0.1:3307`, en 0.8 s |
| ¿A qué servidor se conecta? | puerto **3307**, MariaDB 10.4.32, carpeta de datos del segundo servidor, `/salud` → `ok: true` |
| `pytest -q` | **479 passed**: todas las de la F1 a la F7 (la base de pruebas también está en el 3307) |
| Volver al `.env` original | Huella SHA-256 igual a la original; la app vuelve al 3306 |

No se cambió ni una línea de código. La evidencia completa está en [evidencias/f8-platino-otro-servidor.txt](evidencias/f8-platino-otro-servidor.txt).

**Un arreglo para MySQL 8 (D-99).** Revisamos qué partes del SQL podían fallar en MySQL 8. Había una:
5 CHECK usaban `CAST(x AS BINARY) REGEXP` para distinguir mayúsculas (por ejemplo, `slug` solo con
minúsculas). MySQL 8 rechaza esa forma, con el error 3995. Ahora usan `x COLLATE utf8mb4_bin REGEXP`,
que hace lo mismo en MariaDB y en MySQL 8. Las 102 pruebas de la base siguen pasando.

#### Guía para repetir Platino en otra PC de la red (lo hace el equipo)

**En la PC B (el servidor):**

1. Abrir XAMPP y pulsar **Start** en MySQL.
2. En `C:\xampp\mysql\bin\my.ini`, si hay una línea `bind-address = 127.0.0.1`, comentarla con `#`.
   Así MariaDB escucha en la red. Después, reiniciar MySQL.
3. Abrir el puerto 3306 en el Firewall de Windows **solo para la red privada**. En PowerShell como
   administrador:

   ```powershell
   New-NetFirewallRule -DisplayName "MariaDB Titicaca" -Direction Inbound -Protocol TCP -LocalPort 3306 -Profile Private -RemoteAddress LocalSubnet -Action Allow
   ```

4. Crear las bases y un usuario que pueda entrar desde la red. `00_crear_bd_usuario.sql` lo crea solo
   para `localhost`. En phpMyAdmin de la PC B (pestaña SQL), con una contraseña **nueva**:

   ```sql
   CREATE DATABASE IF NOT EXISTS titicaca_vivo CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
   CREATE DATABASE IF NOT EXISTS titicaca_vivo_pruebas CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
   -- '192.168.1.%' = cualquier PC de esa red; cámbialo por la red de ustedes (ipconfig)
   CREATE USER 'titicaca_app'@'192.168.1.%' IDENTIFIED BY 'CLAVE_NUEVA';
   GRANT ALL PRIVILEGES ON titicaca_vivo.* TO 'titicaca_app'@'192.168.1.%';
   GRANT ALL PRIVILEGES ON titicaca_vivo_pruebas.* TO 'titicaca_app'@'192.168.1.%';
   ```

**En la PC A (la aplicación):**

5. En el `.env`, cambiar **solo** `BD_HOST=<IP de la PC B>` y `BD_CONTRASENA=CLAVE_NUEVA`.
6. Ejecutar `flask bd reiniciar --si` y luego `flask bd contar`, que debe dar 20 tablas y 269 filas.
7. Ejecutar `python servidor.py` y abrir `/salud`. Después correr `pytest`.
8. **Oro en el otro servidor:** hacer una reserva desde la PC A. En el phpMyAdmin de la PC B, ejecutar
   `SELECT codigo, estado, total FROM reserva ORDER BY id DESC LIMIT 3;`. La reserva aparece **una vez**.

#### Si el otro servidor es un MySQL 8 o una base en la nube

Esto **no lo probamos**: en esta PC no hay MySQL 8. Es lo que sabemos que cambia:

| Tema | Qué pasa | Qué hacer |
|---|---|---|
| `CAST AS BINARY` en los CHECK | MySQL 8 lo rechaza | **Ya arreglado** (D-99) |
| Error **1419** al crear triggers | MySQL 8 trae el binlog encendido | `SET GLOBAL log_bin_trust_function_creators = 1;` (lo hace el administrador), o importar los scripts como root |
| Contraseña con `caching_sha2_password` (lo normal en MySQL 8) | Sin TLS, PyMySQL necesita el paquete `cryptography`, que es una **dependencia nueva** | Crear el usuario con `IDENTIFIED WITH mysql_native_password` (en MySQL 8.0). Si no se puede, preguntar antes de agregar `cryptography` |
| Bases en la nube que **exigen TLS** | `bd.py` no manda opciones de TLS: no basta con cambiar el `.env` | Propuesta **PR-15** (no está en el código) |
| `VALUES()` dentro de `ON DUPLICATE KEY UPDATE` | MySQL 8.0.20 o más nuevo lo marca como «obsoleto», pero funciona | Nada por ahora |

**Recomendación:** para el extra, usar un MariaDB en otra PC de la red (la guía de arriba). Funciona sin
tocar el código y sin dependencias nuevas.

### HTTPS detrás de un proxy (sección 11: cookie `Secure` en producción)

waitress no atiende HTTPS. Con `ENTORNO=produccion`, la cookie de sesión lleva `Secure`, y el navegador
solo la manda por **https://**. Por eso en producción va un **proxy** delante, que pone el certificado
(el candado): Caddy, nginx o IIS. El proxy le pasa cada petición a waitress por
`http://127.0.0.1:8080`, con 2 cabeceras:

- `X-Forwarded-For`: la IP del turista;
- `X-Forwarded-Proto`: `https`.

**No hay que cambiar código** (D-101): waitress trae sus propias opciones para confiar en el proxy, y
solo en él.

1. En el `.env` de producción: `ENTORNO=produccion` y `URL_PUBLICA=https://tu-dominio.example`
   (la dirección que va dentro del QR del boleto).
2. Arrancar waitress **solo en 127.0.0.1**, para que nadie entre sin pasar por el proxy, y confiando
   en el proxy:

   ```powershell
   waitress-serve --listen=127.0.0.1:8080 --threads=8 --ident=titicaca-vivo --trusted-proxy=127.0.0.1 --trusted-proxy-count=1 --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --clear-untrusted-proxy-headers --call app:crear_app
   ```

3. Configurar el proxy. **Caddy** es un solo `.exe` y saca el certificado solo, si el dominio apunta al
   servidor. Ya manda las 2 cabeceras:

   ```
   tu-dominio.example {
       reverse_proxy 127.0.0.1:8080
       header Strict-Transport-Security "max-age=31536000"
   }
   ```

   Con **nginx**, las 2 cabeceras se escriben a mano:

   ```
   location / {
       proxy_pass http://127.0.0.1:8080;
       proxy_set_header Host $host;
       proxy_set_header X-Forwarded-For $remote_addr;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```

4. En el firewall, abrir solo el **443** (y el 80, que el certificado necesita). El 8080 y el 3306 no
   se abren hacia afuera.

**¿Por qué hace falta el paso 2?** Probamos 3 casos. Un script hizo de proxy y mandó las cabeceras.
Las IP son de documentación (RFC 5737). La evidencia está en
[evidencias/f8-proxy-https.txt](evidencias/f8-proxy-https.txt).

| Caso | 5 errores del turista A, luego… | Resultado |
|---|---|---|
| **A.** Proxy delante, pero waitress **sin** configurar (como `python servidor.py`) | el turista B intenta **una vez** | **429**: B queda bloqueado por culpa de A. Todos parecen `127.0.0.1` y el límite de `/entrar` se vuelve uno solo para el mundo entero |
| **B.** waitress confía **solo** en el proxy, con `ENTORNO=produccion` | B intenta | **401**: cada turista tiene su propio límite (A sí recibe 429). La cookie va con `Secure; HttpOnly; SameSite=Lax`. Un POST por https sin `Referer` recibe **400** (Flask-WTF exige que el formulario venga del mismo sitio; el navegador manda el `Referer` solo) |
| **C.** Alguien se conecta **directo** e inventa `X-Forwarded-For` | B «inventado» intenta | **429**: waitress borra las cabeceras que no vienen del proxy. Inventarse otra IP no sirve para saltarse el límite |

Lo que **no** probamos: un Caddy o un nginx de verdad, con certificado. Habría que descargarlos y
tener un dominio, así que el script simuló al proxy.

### Revisión de dependencias a mano (sin `pip-audit`)

El equipo decidió revisar las dependencias **sin agregar `pip-audit`**. Revisamos los **36 paquetes**
del entorno virtual: los 14 de `requirements.txt` y los 22 que estos traen. Usamos las 2 fuentes
públicas que usaría `pip-audit`:

- **PyPI**, que da las fallas conocidas de cada versión;
- **OSV** (osv.dev), la base abierta de fallas conocidas.

Para no abrir 72 páginas una por una, un script de un solo uso hizo esas consultas. Usó solo la
biblioteca estándar, así que no se instaló nada, y solo mandó el nombre y la versión de cada paquete.
La evidencia está en [evidencias/f8-dependencias.txt](evidencias/f8-dependencias.txt).

| Paquete | Versión | Para qué lo usamos | Última | Fallas conocidas |
|---|---|---|---|---|
| Flask | 3.1.3 | App factory, blueprints y plantillas | 3.1.3 | 0 |
| PyMySQL | 1.2.3 | Conexión a MariaDB, SQL a mano con `%s` | 1.2.3 | 0 |
| Flask-WTF | 1.3.0 | Formularios y CSRF | 1.3.0 | 0 |
| Flask-Login | 0.6.3 | Sesión del personal | 0.6.3 | 0 |
| Flask-Limiter | 4.1.1 | 5 intentos cada 15 minutos en `/entrar` | 4.1.1 | 0 |
| bcrypt | 5.0.0 | Hash de las contraseñas | 5.0.0 | 0 |
| python-dotenv | 1.2.4 | Leer el `.env` | 1.2.4 | 0 |
| tzdata | 2026.5 | Zona `America/Lima` en Windows | 2026.5 | 0 |
| qrcode[pil] | 8.2 | QR del boleto | 8.2 | 0 |
| reportlab | 5.0.1 | PDF del boleto y del manifiesto | 5.0.1 | 0 |
| waitress | 3.0.2 | Servidor en Windows | 3.0.2 | 0 |
| pytest / pytest-cov | 9.1.1 / 7.1.0 | Pruebas y cobertura | iguales | 0 |
| ruff | 0.17.1 | Estilo y reglas de seguridad | 0.17.1 | 0 |

De las 22 indirectas, como Werkzeug, Jinja2, pillow o MarkupSafe, **21 no tienen fallas conocidas**.
La única con fallas es **setuptools 65.5.0**, con 8:

- **No la usa la aplicación.** `pip show setuptools` dice que nadie la necesita, y no se importa en
  `app/`, `scripts/` ni `tests/`. La instala `python -m venv` en Python 3.11.
- Sus 8 fallas aparecen al **descargar o construir** paquetes, no al correr la app.
- **Arreglo, sin dependencias nuevas:** crear el entorno virtual con Python 3.12 o 3.13 (el enunciado
  ya los pide, y ellos no instalan setuptools). En el entorno actual, basta con
  `python -m pip install --upgrade setuptools`.
- **Hecho el 21/10/2026:** el equipo instaló Python 3.13.16 y se creó un entorno nuevo. No trae
  setuptools, y la revisión repetida da **35 paquetes y 0 fallas conocidas** (al final de la misma
  evidencia).

**Cómo repetirlo a mano**, antes de presentar o al cambiar una versión: por cada línea de
`requirements.txt`, abrir `https://osv.dev/list?ecosystem=PyPI&q=<paquete>` y comprobar que ninguna
falla incluya nuestra versión.

### Consultas explicadas (sección 15)

[consultas-explicadas.md](consultas-explicadas.md) tiene **20 SELECT** (se pedían 15 o más), ordenados como los usa la app:

- lo que ve el turista (7);
- reservar sin sobreventa (4);
- el panel del personal (9).

Cada uno tiene las 5 partes que pide la sección 15:

1. la pantalla;
2. la consulta completa;
3. la explicación línea por línea;
4. un ejemplo con la semilla;
5. el índice que usa, según el EXPLAIN.

Al principio hay una guía para leer un EXPLAIN.

- El SQL no se pasó a mano: un script lo copió del código. Los ejemplos y los EXPLAIN salen de la base de pruebas recién sembrada (D-103).
- `tests/test_documentacion.py` (3 pruebas) revisa 3 cosas:
  - que haya 15 consultas o más, cada una con sus 5 partes;
  - que cada consulta siga **idéntica** a la del código;
  - que el enlace «Dónde está» apunte a su línea.

  Si alguien cambia una consulta y no el documento, `pytest` falla.

### Documentación completa (sección 15)

| Documento | Qué tiene | Estado |
|---|---|---|
| [README](../README.md) | Paso a paso en Windows con XAMPP, usuarios demo y problemas comunes. Ahora también Platino, HTTPS y el ZIP. | Final |
| [modelo-datos.md](modelo-datos.md) | Diagrama ER (Mermaid), diccionario de las 20 tablas, relaciones con su cardinalidad y el porqué de cada ON DELETE. | Final (el CHECK de `slug` ya dice `COLLATE utf8mb4_bin`) |
| [consultas-explicadas.md](consultas-explicadas.md) | Las 20 consultas. | **Nuevo** |
| [desafio-niveles.md](desafio-niveles.md) | Bronce, Plata, Oro y **Platino**, con su evidencia y cómo mostrarlos en clase. | Final |
| [arquitectura.md](arquitectura.md) | Las capas, el recorrido de una petición y, ahora, la producción con HTTPS y otro servidor. | Final |
| [matriz-permisos.md](matriz-permisos.md) | Rol × página, con sus pruebas. | Final |
| [trazabilidad.md](trazabilidad.md) | Requisito → tabla o regla → código → prueba, con las filas de la F8. | Final |
| [decisiones.md](decisiones.md) | D-01 a D-108, propuestas PR-03 a PR-17 y pendientes. | Final |
| `fase-0` … `fase-8` | Qué se hizo en cada fase y «Para explicar al docente». | Final |

### El ZIP de la entrega (sección 16)

`python scripts/empaquetar.py` arma `..\entrega\titicaca_vivo-2.0.0.zip`, **fuera** de la carpeta del proyecto (D-104).

- **No lleva:** el `.env`, entornos virtuales (`.venv`, `venv`), `__pycache__`, `.pytest_cache`, `.ruff_cache`, `logs/` ni `.coverage`.
- **Sí lleva:** el `.env.example` (sin secretos), para que quien lo reciba arme su propio `.env`.
- **Revisión de secretos:** antes de escribir, el script busca en cada archivo la `SECRET_KEY` y la `BD_CONTRASENA` del `.env`. Si alguna aparece, no arma el ZIP y dice en qué archivo está.
- **Pruebas** (en `tests/test_scripts_y_comandos.py`):
  - con un proyecto de juguete, comprueban qué entra y qué no;
  - comprueban que no se arma si un documento lleva un secreto;
  - comprueban que el proyecto real se empaqueta sin secretos.

### Después de la entrega: la página más viva (21/10/2026, D-106 a D-108)

El equipo pidió que la página no se viera «seca» y que quedara claro cómo se hace el pedido:

- **Marca de agua** en el fondo de todas las páginas: el lago, el sol y una balsa de totora abajo a la derecha, y una trama de tejido muy suave.
- **Portada** con un amanecer sobre el lago y **olas que se mueven**. Las tarjetas y los botones se levantan un poco al pasar el mouse, y las fotos de las comunidades se acercan.
- **«Cómo reservar»** en 3 pasos en la portada, y en «Mi reserva» la ayuda «¿Todavía no tienes código?».
- Todo con CSS y 4 SVG propios: **sin JavaScript nuevo, sin CDN y sin tocar la base**. Las páginas pesan de 41 a 62 KB (el límite es 100), y ahora la prueba de peso también cuenta las imágenes de fondo del CSS (D-108).
- Para el equipo: `COMO_FUNCIONA.txt` (el programa en una página) y `USUARIOS_DEMO.txt`, en la carpeta principal.

### Errores encontrados y corregidos en esta fase

- **`CAST(x AS BINARY) REGEXP`** en 5 CHECK: MySQL 8 lo rechaza. Ahora se usa `COLLATE utf8mb4_bin` (D-99).
- **Un fixture de las pruebas** (`limite_de_intentos_limpio`) daba error si se corría solo un archivo de pruebas que no usa la app. Ahora pide la `app` (D-105).
- **Un dato viejo en `desafio-niveles.md`:** decía `checks = 36` (el número de la F1). La base final tiene **39**, así que se corrigió.

## 2. Archivos creados o cambiados

| Archivo | Cambio |
|---|---|
| `database/01_esquema.sql` | 5 CHECK con `COLLATE utf8mb4_bin REGEXP` (D-99) |
| `app/config.py` | `VERSION = "2.0.0"` (la entrega) |
| `app/seguridad.py` | Comentario de `ip_cliente`: detrás de un proxy, `--trusted-proxy` |
| `scripts/empaquetar.py` | **Nuevo**: el ZIP de la entrega |
| `tests/test_documentacion.py` | **Nuevo**: 3 pruebas de `consultas-explicadas.md` |
| `tests/test_scripts_y_comandos.py` | +3 pruebas del ZIP |
| `tests/conftest.py` | `limite_de_intentos_limpio(app)` (D-105) |
| `docs/consultas-explicadas.md`, `docs/fase-8-entrega.md` | **Nuevos** |
| `docs/evidencias/f8-*.txt` | **Nuevos**: Platino, proxy HTTPS, dependencias y pruebas finales |
| `README.md`, `docs/decisiones.md`, `desafio-niveles.md`, `trazabilidad.md`, `arquitectura.md`, `matriz-permisos.md`, `modelo-datos.md` | Cerrados para la entrega |

No hay dependencias nuevas, y `requirements.txt` no cambió.

## 3. Comandos para probarlo

```powershell
pytest                                     # 486 pruebas (usa SOLO titicaca_vivo_pruebas)
pytest -v tests/test_documentacion.py      # las consultas del documento = las del código
ruff check .
python scripts/empaquetar.py               # ..\entrega\titicaca_vivo-2.0.0.zip
```

## 4. Evidencia (20/10/2026)

| Qué | Resultado | Archivo |
|---|---|---|
| Pruebas | **485 passed** en 96 s; cobertura de `app/modelos`: **92 %** | [evidencias/f8-pytest.txt](evidencias/f8-pytest.txt) |
| Estilo y seguridad | `ruff check .` → All checks passed! | La misma |
| Platino | 479 pruebas en un segundo servidor MariaDB (puerto 3307), cambiando 2 líneas del `.env` | [evidencias/f8-platino-otro-servidor.txt](evidencias/f8-platino-otro-servidor.txt) |
| HTTPS detrás de un proxy | 3 casos: sin configurar (429 para todos), configurado (límite por turista, cookie `Secure`) e IP inventada (no sirve) | [evidencias/f8-proxy-https.txt](evidencias/f8-proxy-https.txt) |
| Dependencias | 36 paquetes: 0 fallas en las 14 directas; setuptools 65.5.0 con 8 (no la usa la app). Con el entorno de Python 3.13: 35 paquetes, **0 fallas** | [evidencias/f8-dependencias.txt](evidencias/f8-dependencias.txt) |
| Python 3.13 (sección 3) | Python 3.13.16 en un entorno nuevo: **486 passed** (con las mejoras visuales y su prueba nueva), `ruff` sin errores, 92 % de cobertura (21/10/2026) | [evidencias/f8-pytest-python313.txt](evidencias/f8-pytest-python313.txt) |
| El ZIP | 217 archivos y 2 MB. Ninguno es `.env`, del venv, de caché ni de registro. **Descomprimido en una carpeta nueva, sin `.env`** (los valores se pasaron como variables de entorno), dio **485 passed**: lo que se entrega funciona tal cual. | `..\entrega\titicaca_vivo-2.0.0.zip` |

## 5. Pendientes y riesgos

Todos están en [decisiones.md](decisiones.md#pendientes).

- **Platino en otra PC de la red o en la nube** lo hace el equipo, con la guía de arriba. Nosotros lo probamos con un segundo servidor en la misma PC.
- **MySQL 8 no se probó**, porque en esta PC no hay uno. Lo que sabemos que cambia está en la tabla de arriba. Si hace falta `cryptography` o TLS (PR-15), hay que preguntar antes.
- **Un proxy real** (Caddy o nginx, con certificado) no se probó: el script simuló sus cabeceras.
- **Python 3.13: cerrado (21/10/2026).** Con Python 3.13.16 pasan las 486 pruebas, y el entorno
  nuevo ya no trae el setuptools viejo (D-102).
- **Siguen abiertos:**
  - los datos «por confirmar» con Giant Trip;
  - las columnas de ubicación (D-38);
  - probar con NVDA y con Lighthouse;
  - importar una vez con la interfaz de phpMyAdmin;
  - el riesgo aceptado de `/mi-reserva` sin límite de intentos (PR-07).
- **Propuestas nuevas, sin el «ok»:**
  - PR-15: `BD_SSL_CA` para bases en la nube con TLS;
  - PR-16: fijar también las dependencias indirectas.
  - PR-17: cuentas para el turista (primero con correo; después Google, Microsoft, Apple o SMS), pedida el 21/10/2026.

---

## Para explicar al docente

### 1. ¿A qué servidor está conectada la app? (Platino)

```sql
-- Devuelve el nombre de la máquina, el puerto, la versión, la base y el usuario de ESTA conexión.
SELECT @@hostname AS servidor, @@port AS puerto, VERSION() AS version,
       DATABASE() AS base, CURRENT_USER() AS usuario;
```

| Parte | En palabras simples |
|---|---|
| `@@hostname`, `@@port` | Las variables con `@@` son **del servidor**: en qué máquina y en qué puerto atiende. |
| `VERSION()` | La versión del motor, por ejemplo `10.4.32-MariaDB`. Con MySQL 8 diría `8.0.x`. |
| `DATABASE()` | La base en uso: la que dice `BD_NOMBRE` en el `.env`. |
| `CURRENT_USER()` | Con qué usuario y con qué host **lo aceptó** el servidor, por ejemplo `titicaca_app@localhost`. Por eso, en otra PC hay que crear el usuario para la IP de quien se conecta. |

Con el `.env` normal da `puerto = 3306`. Con el `.env` de Platino da `puerto = 3307`, y la carpeta de datos (`@@datadir`) es la del segundo servidor. Así se ve que es **otro** servidor y no la misma base con otro nombre.

### 2. ¿La base del otro servidor quedó igual?

```sql
-- Devuelve cuántas tablas, FK, CHECK, triggers y vistas tiene la base en uso.
SELECT (SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE') AS tablas,
       (SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE())                        AS claves_foraneas,
       (SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE())                        AS checks,
       (SELECT COUNT(*) FROM information_schema.TRIGGERS
        WHERE TRIGGER_SCHEMA = DATABASE())                           AS triggers,
       (SELECT COUNT(*) FROM information_schema.VIEWS
        WHERE TABLE_SCHEMA = DATABASE())                             AS vistas;
```

- `information_schema` es el **catálogo** del servidor: tablas que describen las tablas.
- Cada `(SELECT COUNT(*) …)` es una subconsulta que devuelve un solo número. Se pueden poner varias en el SELECT, una por columna.
- `TABLE_TYPE = 'BASE TABLE'` deja afuera las vistas, que se cuentan aparte.

Resultado: **tablas = 20, claves_foraneas = 29, checks = 39, triggers = 4, vistas = 2**. Es la misma base en cualquier servidor, porque la crean los mismos scripts con `flask bd reiniciar`.

### 3. ¿Por qué `COLLATE utf8mb4_bin` en el CHECK? (D-99)

```sql
-- Devuelve 1 o 0: ¿el texto cumple «solo minúsculas, números y guiones»?
SELECT 'amantani' COLLATE utf8mb4_bin REGEXP '^[a-z0-9-]+$' AS minusculas,
       'Amantani' COLLATE utf8mb4_bin REGEXP '^[a-z0-9-]+$' AS con_mayuscula,
       'Amantani'                     REGEXP '^[a-z0-9-]+$' AS sin_collate;
```

Resultado: **1, 0, 1**.

- La base usa `utf8mb4_spanish_ci`, y **ci** quiere decir «no distingue mayúsculas». Para ella, `A` y `a` son iguales.
- Por eso, sin `COLLATE`, `'Amantani'` pasa la regla (`sin_collate = 1`), y el CHECK dejaría guardar un `slug` con mayúscula.
- `COLLATE utf8mb4_bin` compara byte por byte. Así, `A` no está entre `a` y `z`.
- Antes escribíamos `CAST(slug AS BINARY)`, que en MariaDB hace lo mismo, pero MySQL 8 lo rechaza (error 3995). `COLLATE` funciona en los 2.

### 4. Oro en el otro servidor: ¿hay reservas duplicadas?

```sql
-- Devuelve los token_envio que aparecen en más de una reserva (debería no devolver nada).
SELECT token_envio, COUNT(*) AS veces
FROM reserva
GROUP BY token_envio
HAVING COUNT(*) > 1;
```

- `GROUP BY token_envio` junta las reservas que vienen del mismo envío del formulario.
- `HAVING COUNT(*) > 1` deja solo los grupos con más de una reserva, o sea, los duplicados. HAVING va después de agrupar, porque WHERE no puede usar COUNT.
- Resultado: **0 filas**. Lo garantiza el `UNIQUE` de `token_envio` (RN-03), en cualquier servidor.

Para verlo en números: `SELECT COUNT(*), COUNT(DISTINCT token_envio), COUNT(DISTINCT codigo) FROM reserva;` da **23, 23, 23**: cada reserva tiene su propio token y su propio código.
