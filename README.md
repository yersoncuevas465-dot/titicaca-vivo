# Titicaca Vivo

Plataforma de turismo lacustre y vivencial de Puno para Giant Trip Travel Agency: salidas, reservas sin sobreventa, pagos Yape/Plin, abordaje con QR, alertas del lago y rotación justa de familias anfitrionas.

Curso Ingeniería de Software II (EST323), FINESI, Universidad Nacional del Altiplano, 2026-II.
Equipo: Cuevas Mamani Yerson · Ilaquita Pariapaza Kemelly Shannel · Luque Cornejo Zulema Yasmile.

> **Estado: Fase 8 (entrega) + mejora F9.** La aplicación está completa (F1–F6) y revisada (F7). **Platino:** la misma app corre contra otro servidor MariaDB cambiando solo el `.env`. La documentación está completa, con [20 consultas explicadas](docs/consultas-explicadas.md), y el ZIP de entrega no lleva `.env` ni entorno virtual. **F9 (30/10/2026):** recuperar la contraseña con un código por correo, Mi cuenta para cada rol, cierre de sesión por inactividad y una foto del lago como marca de agua en cada sección ([fase-9](docs/fase-9-cuenta-y-marca.md)).

> **Para empezar rápido:** `COMO_FUNCIONA.txt` (el programa explicado en una página) y `USUARIOS_DEMO.txt` (usuarios y claves de prueba), en esta misma carpeta.

Stack: Python 3.12/3.13 · Flask 3.1 · MariaDB 10.4 (XAMPP) · PyMySQL (SQL escrito a mano, sin ORM).

---

## Puesta en marcha en Windows con XAMPP

### 1. Arrancar MySQL (MariaDB)

Abre **XAMPP Control Panel** y pulsa **Start** en **MySQL**.

phpMyAdmin es una página PHP, así que para usarlo también hay que pulsar **Start** en **Apache**. La aplicación Flask no necesita Apache.

### 2. Crear la base y el usuario

1. Abre `database/00_crear_bd_usuario.sql` y cambia `CAMBIA_ESTA_CLAVE` por una contraseña tuya (las dos veces).
2. Ejecútalo como root de una de estas dos formas:
   - **phpMyAdmin** (http://localhost/phpmyadmin) → pestaña **SQL** → pega el contenido → **Continuar**;
   - **Consola** (PowerShell, desde la carpeta `titicaca_vivo`):

     ```powershell
     C:\xampp\mysql\bin\mysql.exe -u root -e "source database/00_crear_bd_usuario.sql"
     ```

El script crea `titicaca_vivo` (trabajo), `titicaca_vivo_pruebas` (pruebas automáticas) y el usuario `titicaca_app`, con permisos solo sobre esas dos bases.

### 3. Crear las tablas y cargar los datos

Elige **una** de estas dos opciones:

- **Opción A, phpMyAdmin:** selecciona la base `titicaca_vivo` → **Importar** → importa `01_esquema.sql`, luego `02_vistas_triggers.sql` y luego `03_datos.sql`, en ese orden y uno por uno.
- **Opción B, comando:** cuando termines los pasos 4 y 5, ejecuta `flask bd reiniciar`. Borra la base, la crea de nuevo y siembra todo.

Para comprobar el resultado, ejecuta `database/99_consultas_prueba.sql` en la pestaña SQL. Muestra cuántas filas tiene cada tabla, un SELECT * de cada una y 5 consultas con JOIN.

### 4. Crear el entorno virtual e instalar las dependencias

Crea el entorno **fuera de OneDrive**: tiene miles de archivos y OneDrive los sincronizaría todos.

```powershell
py -3.13 -m venv $env:USERPROFILE\.venvs\titicaca_vivo
& $env:USERPROFILE\.venvs\titicaca_vivo\Scripts\Activate.ps1
pip install -r requirements.txt
```

En VS Code, elige ese intérprete con *Python: Select Interpreter*.

### 5. Configurar el `.env` y ejecutar

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # pega el resultado en SECRET_KEY
notepad .env                                                # escribe BD_CONTRASENA (la del paso 2)
                                                            # YAPE_NUMERO, PLIN_NUMERO, TITULAR_COBRO: datos de cobro (ficticios en el ejemplo)
                                                            # URL_PUBLICA: dirección que abre el QR del boleto (vacía = la del servidor)
flask bd reiniciar                                          # pide confirmación; con --si no pregunta
flask bd contar                                             # filas por tabla
flask reservas vencer                                       # RN-05: marca las reservas vencidas
```

### 6. Abrir la aplicación

```powershell
flask run                       # desarrollo:  http://127.0.0.1:5000
python servidor.py              # waitress:    http://127.0.0.1:8080
python servidor.py --host 0.0.0.0   # para probar desde un celular en la misma red Wi-Fi
```

- Entra en `/entrar` con un usuario demo (abajo).
- `/salud` responde `{"ok": true, "hora": "…-05:00"}` si la base está bien.
- Los arranques, los inicios de sesión y los errores quedan en `logs/app.log`, con la hora de Lima.

---

## Usuarios demo

Son personas ficticias. Los hash bcrypt ya están escritos en `03_datos.sql`, los genera `scripts/generar_hashes.py`.

| Usuario | Contraseña | Rol | Detalle |
|---|---|---|---|
| `admin` | `Admin-Titicaca26` | admin | |
| `operador` | `Operador-Titicaca26` | operador | |
| `guia.elena` | `Guia-Titicaca26` | guía | Comunidad Amantaní |
| `guia.marco` | `Guia-Titicaca26` | guía | Comunidad Llachón |
| `capitan.teodoro` | `Capitan-Titicaca26` | capitán | Licencia LIC-PUN-00123 |
| `capitan.fermin` | `Capitan-Titicaca26` | capitán | Licencia LIC-PUN-00456 |

Si cambias una contraseña en `scripts/generar_hashes.py`, vuelve a ejecutar `python scripts/generar_hashes.py`: reescribe el bloque de usuarios del `.sql`.

---

## Cuenta del personal (F9)

El detalle está en [docs/fase-9-cuenta-y-marca.md](docs/fase-9-cuenta-y-marca.md).

- **¿Olvidaste tu contraseña?** (en `/entrar`): usuario o correo → un código de 6 dígitos al correo de la cuenta → contraseña nueva. Vence a los 15 minutos y sirve una sola vez.
- **Sin correo de verdad** (`CORREO_SIMULAR=1`, el valor del `.env`): el código aparece en la ventana del servidor, en el bloque `[CORREO SIMULADO]`. Para enviarlo con Gmail se completa `SMTP_*` en el `.env` (ver `.env.example`) y se prueba con `flask correo probar tu@correo.com`.
- **Mi cuenta** (en el menú del panel): tus datos, lo que hace y no hace tu rol, cambiar tu contraseña, tu correo y tu celular, y tus últimos movimientos.
- Se entra con el **usuario o con el correo**. La sesión se cierra sola tras **30 minutos sin actividad** (`SESION_INACTIVA_MIN`), con aviso 2 minutos antes. Si cambias tu contraseña, tus otras sesiones se cierran solas.
- Una contraseña nueva necesita 10 caracteres o más, letras y números, sin espacios y sin el nombre de usuario.
- El admin activa o desactiva cuentas con un clic (Usuarios) y descarga la bitácora en CSV (Bitácora).
- Si el admin olvidó su contraseña y no tiene correo:

  ```powershell
  flask usuarios listar           # el personal y quién tiene correo
  flask usuarios clave admin      # pide la contraseña nueva sin mostrarla
  ```

## Respaldos de la base (F9)

En el panel del admin, **Respaldos**: «Crear respaldo ahora» guarda toda la base en `respaldos/respaldo_<fecha>.sql` (las 20 tablas con sus datos, las vistas, el procedimiento y los triggers), se descarga, y con el servidor encendido se crea uno **automático cada 24 horas**. Se guardan los 15 más nuevos. «Reporte general» baja reservas, pagos, salidas y hospedajes en CSV para Excel, sin documentos ni teléfonos.

```powershell
flask bd respaldar                                  # un respaldo ahora
flask bd restaurar respaldo_20261030_120000.sql     # BORRA la base y deja la del respaldo
```

`flask bd restaurar` pide confirmación y antes guarda un respaldo «antes de restaurar»; `flask bd reiniciar` también guarda uno antes de borrar. La carpeta `respaldos/` no va en el ZIP de entrega ni en git: lleva datos personales.

---

## Pruebas y calidad

```powershell
pytest            # 628 pruebas; usa SOLO la base titicaca_vivo_pruebas (la borra y la crea al empezar)
ruff check .      # estilo y seguridad
pytest -v -s tests/test_mutante.py              # prueba mutante: sin FOR UPDATE hay sobreventa
python scripts/explicar_consultas.py             # EXPLAIN de las 3 consultas más importantes
python scripts/empaquetar.py                     # ZIP de la entrega en ..\entrega\ (sin .env ni venv)
```

---

## Platino: otro servidor de base de datos

La conexión sale entera del `.env`. Para usar otro MariaDB o MySQL (en otra PC, en otro puerto o en la nube) se cambian **solo** estas líneas:

```ini
BD_HOST=192.168.1.30      # IP de la PC que tiene la base
BD_PUERTO=3306
BD_CONTRASENA=<la del usuario titicaca_app de ese servidor>
```

Después se ejecuta `flask bd reiniciar --si`, y la app y las pruebas ya trabajan contra ese servidor. En ese servidor hay que crear el usuario para la IP de esta PC, no solo para `localhost`.

El paso a paso para otra PC de la red, lo que cambia en MySQL 8 y la evidencia (479 pruebas en un segundo servidor) están en [docs/fase-8-entrega.md](docs/fase-8-entrega.md).

---

## Producción con HTTPS

waitress no atiende HTTPS, y con `ENTORNO=produccion` la cookie de sesión solo viaja por https. Por eso delante va un **proxy** con certificado (Caddy, nginx o IIS), y waitress confía **solo** en él:

```powershell
waitress-serve --listen=127.0.0.1:8080 --threads=8 --ident=titicaca-vivo --trusted-proxy=127.0.0.1 --trusted-proxy-count=1 --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --clear-untrusted-proxy-headers --call app:crear_app
```

En el `.env` de producción van `ENTORNO=produccion` y `URL_PUBLICA=https://<tu dominio>`. La configuración del proxy y la prueba de por qué hacen falta esas opciones están en [docs/fase-8-entrega.md](docs/fase-8-entrega.md#https-detrás-de-un-proxy-sección-11-cookie-secure-en-producción).

---

## Entrega

```powershell
python scripts/empaquetar.py
```

Esto arma `..\entrega\titicaca_vivo-2.2.0.zip`, fuera de la carpeta del proyecto. El ZIP:

- no lleva `.env`, entornos virtuales, cachés, `logs/` ni `.coverage`;
- **no se arma** si algún archivo contiene la `SECRET_KEY` o la `BD_CONTRASENA` del `.env`.

Quien lo reciba sigue esta guía desde el paso 1.

---

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| XAMPP dice **"Port 3306 in use"** | Hay otro MySQL corriendo (por ejemplo, el servicio `MySQL80` del instalador oficial, o un `mysqld` que quedó abierto). Búscalo con `netstat -ano \| findstr :3306` y detenlo: `services.msc`, o `C:\xampp\mysql_stop.bat` si es el de XAMPP. También puedes cambiar `port=` en `C:\xampp\mysql\bin\my.ini` y poner el mismo número en `BD_PUERTO`. |
| **Error 1045** *Access denied for user 'titicaca_app'* | La contraseña de `BD_CONTRASENA` no es la del paso 2, o no se ejecutó `00_crear_bd_usuario.sql`. Ese script crea el usuario para `localhost` y para `127.0.0.1`. |
| **Error 2003/2002** *Can't connect* | MySQL no está arrancado (paso 1). |
| `ZoneInfoNotFoundError: America/Lima` | Windows no trae la base de zonas horarias. Ejecuta `pip install tzdata` (ya está en `requirements.txt`). |
| **#1064** al importar `02_vistas_triggers.sql` en phpMyAdmin | Hay que usar **Importar** con el archivo, no pegarlo por partes: el archivo usa `DELIMITER $$` para los triggers. |
| **Error 1419** (*SUPER privilege… binary logging*) en otro servidor | Ese servidor tiene binlog. Pide al administrador `SET GLOBAL log_bin_trust_function_creators = 1;` (aplica en el nivel Platino). |
| Un ENUM inválido se guarda vacío (`''`) sin error | XAMPP trae un `sql_mode` no estricto. Los scripts y la app activan `STRICT_TRANS_TABLES` en cada sesión. Si escribes a mano en phpMyAdmin, ejecuta antes `SET SESSION sql_mode = 'STRICT_TRANS_TABLES';`. |
| OneDrive se pone lento o bloquea archivos | El entorno virtual está dentro de OneDrive: créalo fuera (paso 4). |
| `RuntimeError: Falta SECRET_KEY` | El `.env` no tiene `SECRET_KEY` (paso 5). |
| "Demasiados intentos" (429) en `/entrar` | Hubo 5 intentos fallidos en 15 minutos desde esa IP. Espera, o reinicia la app (el contador vive en memoria). |
| Con `ENTORNO=produccion` no se puede iniciar sesión | En producción la cookie lleva `Secure` y solo viaja por **HTTPS**. Para una demostración por HTTP usa `ENTORNO=desarrollo`. |
| El QR del boleto abre `127.0.0.1` en el celular | Pon en `URL_PUBLICA` la dirección de la PC en la red (por ejemplo `http://192.168.1.20:8080`) y arranca con `--host 0.0.0.0`. |
| "Ya no recibe reservas" (409) | La salida ya zarpó, está embarcando, se suspendió o se canceló. Solo se reservan salidas `programada` que todavía no zarpan (D-54). |
| El QR del boleto abre «No tienes permiso» (403) | Ese guía o capitán no está asignado a la salida de esa reserva (◐). El operador puede registrar cualquier abordaje. |
| «El abordaje abre 60 minutos antes del zarpe» | RN-12: solo se registra de 60 min antes a 15 min después del zarpe, en hora de Lima. |
| «No se puede cancelar»: la salida tiene reservas | Suspéndela: así cada turista podrá reprogramar o pedir la devolución (D-66). |
| La página sale en inglés y quieres español | Usa «Español» arriba a la derecha (queda en la sesión). El panel siempre está en español. |
| Un texto sale en español aunque elegiste inglés | Viene de la base (nombre de ruta, descripción, país): no tiene versión en inglés (PR-13). Si es un texto de la página, falta en `app/servicios/textos_en.py` (la prueba `test_cada_texto_del_turista_tiene_su_traduccion` lo avisa). |
| No ves los cambios de CSS | En desarrollo no hay caché. En producción se renuevan al cambiar `VERSION` en `config.py`. |
| Detrás de un proxy, «Demasiados intentos» le sale a **todos** | waitress no sabe que hay un proxy y todos parecen `127.0.0.1`. Arráncalo con `--trusted-proxy` (ver «Producción con HTTPS»). |
| *'cryptography' package is required for sha256_password or caching_sha2_password* (MySQL 8) | El usuario de MySQL 8 usa `caching_sha2_password`. Créalo con `IDENTIFIED WITH mysql_native_password BY '…'`. Agregar `cryptography` sería una dependencia nueva ([fase-8-entrega.md](docs/fase-8-entrega.md#si-el-otro-servidor-es-un-mysql-8-o-una-base-en-la-nube)). |
| `Can't connect` a la base de **otra PC** | En esa PC: MySQL arrancado, `bind-address` comentado en `my.ini`, puerto 3306 abierto en el firewall para la red privada y el usuario creado para tu IP (guía de Platino). |

---

## Estructura

```
titicaca_vivo/
  app/            __init__.py (crear_app), config.py, bd.py, seguridad.py, errores.py,
                  registro.py, comandos.py
  app/rutas/      publico.py, autenticacion.py, reservas.py, panel.py, panel_seguimiento.py,
                  catalogos.py                                           (sin SQL)
  app/modelos/    salida, ruta, tarifa, comunidad, alerta, reserva, hospedaje, pago, abordaje,
                  embarcacion, temporada, tipo_pasajero, familia, usuario, panel, bitacora,
                  sistema, catalogo, validacion, reprogramacion, resena, indicadores (todo el SQL)
  app/formularios/ autenticacion.py, reserva.py, panel.py, catalogos.py
  app/servicios/  formato.py, mapa.py, imagenes.py, paises.py, privacidad.py, qr.py, pdf.py,
                  whatsapp.py, textos.py, textos_en.py (español / inglés)
  app/plantillas/ base.html, macros.html, publico/, reservas/, autenticacion/, panel/, errores/
  app/estaticos/  css/estilos.css, js/reservar.js, img/ (logo, isotipo, favicon, íconos, comunidades/*.webp)
  servidor.py     waitress
  database/       00_crear_bd_usuario.sql, 01_esquema.sql, 02_vistas_triggers.sql,
                  03_datos.sql, 99_consultas_prueba.sql
  scripts/        generar_hashes.py, generar_iconos.py, preparar_foto.py, explicar_consultas.py,
                  empaquetar.py
  tests/          conftest.py; base: test_bd_*.py; reglas: test_reglas_*.py; rutas: test_rutas_*.py;
                  test_concurrencia.py, test_mutante.py, test_plata.py, test_rendimiento.py,
                  test_seguridad_y_errores.py, test_seguridad_f7.py, test_accesibilidad.py,
                  test_catalogos.py, test_mapa_precios_fotos.py, test_scripts_y_comandos.py,
                  test_documentacion.py
  docs/           fase-0 … fase-8, modelo-datos.md, consultas-explicadas.md, desafio-niveles.md,
                  arquitectura.md, matriz-permisos.md, trazabilidad.md, decisiones.md,
                  creditos-imagenes.md, evidencias/
```
