# Fase 9 · Cuenta del personal, seguridad y marca de agua

Fecha: 30/10/2026. Pedido del equipo: dejar Titicaca Vivo tan detallado como **NeoClinic** (el otro
proyecto del equipo): recuperar la contraseña, que cada rol vea su función, y fotos de fondo como
marca de agua; y después, los respaldos de la base desde el panel. Las decisiones están en
[decisiones.md](decisiones.md), de D-109 a D-118.

**No cambia la base de datos**: siguen las 20 tablas, las 2 vistas, los 4 triggers y el procedimiento.
No hace falta volver a cargarla por esta fase.

---

## 1. Qué se agregó

### Recuperar la contraseña (D-111)

En `/entrar` está el enlace **«¿Olvidaste tu contraseña?»**. Son 2 pasos:

1. `/recuperar`: se escribe el **usuario o el correo**. Si la cuenta está activa y tiene correo, le llega
   un **código de 6 dígitos**. La página dice lo mismo exista o no la cuenta (nadie averigua qué cuentas hay).
2. `/recuperar/codigo`: el código y la contraseña nueva (dos veces).

| Regla | Cómo se cumple |
|---|---|
| El código vence a los 15 minutos | La sesión del navegador guarda la hora de vencimiento. |
| Sirve una sola vez | Su firma depende del hash actual; al cambiar la contraseña ya no coincide. La fila se bloquea con `FOR UPDATE`: dos pedidos a la vez no lo usan dos veces. |
| Solo en el navegador que lo pidió | La firma va en la sesión de ese navegador. |
| No se guarda en ninguna parte | En la sesión queda solo un HMAC (`SECRET_KEY` + hash), nunca el código. Tampoco va a `logs/app.log`. |
| Límite de intentos | 5 códigos malos por pedido (después hay que pedir otro), 10 por IP cada 15 minutos, 5 pedidos por IP. |
| Contraseña floja | Si el código está bien pero la contraseña no cumple la regla, el código **no** se gasta. |

**Sin internet (modo demostración).** Con `CORREO_SIMULAR=1` (lo que viene en el `.env`), el correo no
sale: se muestra en la ventana del servidor (INICIAR.bat o la terminal de VS Code) en un bloque
`[CORREO SIMULADO]`, con el código. Para enviarlo de verdad con Gmail se completa `SMTP_*` en el `.env`
y se pone `CORREO_SIMULAR=0`; `flask correo probar tu@correo` revisa la configuración.

**Si no hay correo.** El admin pone una contraseña nueva en *Usuarios → Editar*. Si el que la olvidó es el
admin, el encargado del servidor usa `flask usuarios clave admin` (queda en la bitácora con la IP «consola»).

### Entrar y la sesión (D-110, D-112, D-113)

- Se entra con el **usuario o con el correo**.
- Desde el 3.er intento fallido, la página avisa **cuántos intentos quedan** antes del bloqueo de 15 minutos.
- La sesión **se cierra sola tras 30 minutos sin actividad** (`SESION_INACTIVA_MIN`). Dos minutos antes
  aparece un aviso con el botón «Seguir trabajando». Al volver a entrar, regresa a la página donde estaba.
- Si la contraseña cambia, **las demás sesiones de esa cuenta se cierran solas** (la cookie guarda un
  sello que sale del hash).
- Con la sesión abierta **ninguna página queda en la caché** del navegador: tras «Salir», «Atrás» no
  muestra datos.

### Mi cuenta (D-113)

`/panel/mi-cuenta`, para los 4 roles, en el menú del panel:

- sus datos (usuario, rol, comunidad o licencia, correo, celular, último acceso);
- **lo que hace y lo que no hace su rol**;
- **cambiar mi contraseña** (pide la actual);
- **correo y celular** (pide la contraseña: el correo es el que recibe el código);
- **sus últimos movimientos**: entradas, salidas, intentos fallidos y cambios, con la IP.

La regla de una contraseña nueva es una sola en todo el sistema (alta del admin, Mi cuenta, recuperación
y consola): 10 caracteres o más, letras y números, sin espacios y sin el nombre de usuario.

### Usuarios y bitácora (D-114, D-115)

- **Usuarios**: botón **Activar / Desactivar** en cada fila (nadie se desactiva a sí mismo; un guía o
  capitán con salidas por venir no se desactiva). Se marca a quien **no tiene correo**. Abajo, cada rol con
  lo que hace y lo que no hace.
- **Bitácora**: cada acción en palabras, filtro por **periodo** (hoy, semana, mes, año) y **descarga en
  CSV** para Excel: toda o solo las entradas y salidas. Anota también el cierre de sesión, los intentos
  fallidos (con la cuenta, nunca lo que se escribió), los pedidos de código y los cambios de contraseña.

### Fotos de fondo como marca de agua (D-109)

Cada sección tiene una foto del lago, fija y muy tenue detrás de todo, y su crédito al pie:

| Sección | Foto |
|---|---|
| Portada y salidas · Panel: salidas, pasajeros y abordaje | Uros |
| Comunidades, reseñas y catálogos | Taquile |
| Mi reserva (turista) · Panel: hospedajes y transparencia | Amantaní |
| Entrar, recuperar la contraseña y el resumen del panel | Llachón |
| Panel: pagos e indicadores | Luquina Chico |
| Alertas · Panel: alertas, usuarios, bitácora y Mi cuenta | Ticonata |
| Detalle de una comunidad | La foto de esa comunidad |

Son las 6 fotos de Wikimedia Commons que ya usaba el proyecto, agrandadas y suavizadas con
`scripts/preparar_fondos.py` (960×600, de 13 a 19 KB). **Solo se ven en pantallas anchas**: en el
celular el `<img>` está oculto y, como es `loading="lazy"`, ni se descarga. El formulario de reserva no
lleva foto (es la página más pesada). La página de acceso tiene además un panel de marca con la foto, el
logo y para qué sirve el panel.

### Respaldos de la base (D-116 a D-118)

Panel del admin → **Respaldos**, como en NeoClinic:

- **Crear respaldo ahora**: un archivo `.sql` con las 20 tablas (su estructura real y todos los datos,
  leídos en una sola «foto» de la base: nada queda a medias aunque alguien esté reservando) y, al final,
  las vistas, el procedimiento y los triggers de `02_vistas_triggers.sql`. Con los datos de la demo
  pesa unos 60 KB.
- **Descargar** cada respaldo, para guardar una copia fuera de la PC.
- **Respaldo automático** cada 24 horas mientras corre `servidor.py` (y al arrancar, si el último tiene
  más de 24 horas). Se guardan los 15 más nuevos.
- **Reporte general (Excel)**: un ZIP con reservas, pagos, salidas y hospedajes en CSV, sin documentos,
  teléfonos ni correos de los turistas.
- **Restaurar**, solo desde la consola y con confirmación: `flask bd restaurar <archivo>`. Antes guarda
  un respaldo «antes de restaurar», así que una restauración equivocada también se deshace.
  `flask bd reiniciar` ahora también guarda antes un respaldo «antes de reiniciar».
- La carpeta `respaldos/` no va en el ZIP de entrega ni en git: lleva datos personales.
- Crear, descargar, restaurar y el reporte quedan en la bitácora. En «Tu trabajo de hoy» el admin ve
  cuándo fue el último respaldo.

### Comandos nuevos

```powershell
flask usuarios listar                 # el personal, su rol, si está activo y si tiene correo
flask usuarios clave admin            # contraseña nueva desde la terminal (la pide sin mostrarla)
flask correo probar tu@correo.com     # revisa la configuración del correo
flask bd respaldar                    # un respaldo completo ahora, en respaldos/
flask bd restaurar respaldo_20261030_120000.sql   # deja la base como en ese respaldo
```

---

## 2. Archivos

| Archivo | Qué es |
|---|---|
| `app/modelos/cuenta.py` | **Nuevo.** Regla de contraseña, sello de sesión, recuperación con código, Mi cuenta y eventos de sesión en la bitácora. |
| `app/servicios/correo.py` | **Nuevo.** Envío por SMTP o simulado en la ventana del servidor. |
| `app/estaticos/js/sesion.js` | **Nuevo.** Aviso de cierre por inactividad y «sigo trabajando». |
| `app/estaticos/img/fondos/*.webp`, `scripts/preparar_fondos.py` | **Nuevos.** Fotos de fondo y el script que las arma. |
| `app/plantillas/autenticacion/recuperar.html`, `recuperar_codigo.html`, `_acceso.html` | **Nuevas.** Los 2 pasos de la recuperación y el panel de marca del acceso. |
| `app/plantillas/panel/mi_cuenta.html`, `_roles.html` | **Nuevas.** Mi cuenta y qué hace cada rol. |
| `app/rutas/autenticacion.py` | Entrar con correo, aviso de intentos, bitácora al salir y la recuperación. |
| `app/seguridad.py` | Cierre por inactividad, sello de sesión y `no-store` con sesión abierta. |
| `app/rutas/panel.py` | Mi cuenta, `/panel/sesion`, bitácora por periodo y CSV, activar o desactivar. |
| `app/modelos/usuario.py`, `bitacora.py` | Sello en la sesión, regla única de contraseña, activar o desactivar, consola y exportar. |
| `app/comandos.py` | `flask usuarios …`, `flask correo probar`, `flask bd respaldar`, `flask bd restaurar` y el respaldo previo de `flask bd reiniciar`. |
| `app/modelos/respaldo.py`, `app/plantillas/panel/respaldos.html` | **Nuevos.** Crear, listar, descargar y restaurar respaldos, el automático y el reporte general. |
| `app/servicios/hoja_de_calculo.py` | **Nuevo.** CSV para Excel (sin fórmulas) y el ZIP del reporte. |
| `scripts/empaquetar.py`, `.gitignore` | La carpeta `respaldos/` queda fuera del ZIP de entrega y de git. |
| `tests/test_cuenta.py`, `tests/test_respaldos.py` | **Nuevos.** Las pruebas de esta fase. |

---

## 3. Cómo mostrarlo (5 minutos)

1. **Recuperar la contraseña** (con `guia.elena`, que tiene correo). `/entrar` → «¿Olvidaste tu
   contraseña?» → `guia.elena` → Enviarme el código. En la ventana del servidor aparece el bloque
   `[CORREO SIMULADO]` con el código. Escribirlo, poner `Totora-Nueva-2026` dos veces → «Listo: tu
   contraseña cambió». Entrar con la nueva. Para dejarla como estaba: Mi cuenta → Cambiar mi contraseña →
   `Guia-Titicaca26`. (Con `admin` u `operador` no se puede volver a la de la demo, porque la regla no
   deja una contraseña que contenga el usuario: ahí sirve `flask bd reiniciar --si`.)
2. **Intentos.** En `/entrar`, 3 contraseñas malas: «Te quedan 2 intentos antes de un bloqueo de 15 minutos».
3. **Mi cuenta.** Entrar como guía (`guia.elena`) → Mi cuenta: sus datos, **lo que hace y no hace** su rol
   y sus últimos movimientos.
4. **Usuarios.** Como admin: Desactivar a `operador` (en otra ventana con el operador dentro, al siguiente
   clic vuelve a /entrar) y Activar de nuevo.
5. **Bitácora.** Periodo «Hoy» → aparecen los inicios, cierres, intentos fallidos y el cambio de
   contraseña → «Solo entradas y salidas» descarga el CSV para Excel.
6. **Marca de agua.** Recorrer Salidas, Comunidades, Alertas y el panel: cada sección con su foto y su
   crédito al pie.
7. **Respaldos.** Como admin: Respaldos → «Crear respaldo ahora» → aparece en la lista (manual, con su
   tamaño) → Descargar. «Reporte general (Excel)» baja el ZIP con los CSV. Para restaurar, en la
   terminal: `flask bd restaurar <nombre del archivo>` (pide confirmación y guarda antes un respaldo).

---

## 4. Evidencia

`tests/test_cuenta.py` prueba todo lo de arriba: la recuperación de punta a punta, el código que vence,
que sirve una sola vez y solo en su navegador, los 5 intentos, la contraseña floja que no gasta el código,
el límite de pedidos, el mismo mensaje sin cuenta o sin correo, entrar con el correo, el aviso de intentos,
la bitácora (sin lo escrito en un intento fallido), el cierre por inactividad, las otras sesiones que se
cierran al cambiar la contraseña, Mi cuenta de los 4 roles, activar y desactivar, el CSV (sin fórmulas de
Excel), los comandos y la foto de cada sección. Además se sumaron Mi cuenta y la descarga a la matriz de
permisos, a la revisión de accesibilidad, al peso de página y a las guías «¿Cómo funciona?».

`tests/test_respaldos.py` prueba que **un respaldo restaurado deja la base idéntica**: el `CHECKSUM TABLE`
de cada tabla, la bitácora fila por fila y el `AUTO_INCREMENT` quedan iguales, y vuelven las 2 vistas, el
procedimiento y los 4 triggers en modo estricto. También: el respaldo no lleva `DEFINER`, los triggers van
después de los datos, se divide en sentencias igual que en phpMyAdmin, no se restaura un archivo cortado
ni uno ajeno, se guardan solo los más nuevos, el automático solo cuando toca (y el hilo del servidor), la
página y la descarga solo para el admin (ningún otro nombre de archivo sale), el reporte sin documentos,
los comandos `respaldar`, `restaurar` (con confirmación) y `reiniciar` con su respaldo previo, y que la
carpeta no va en el ZIP de entrega ni en git. El resultado completo está en
[evidencias/f9-pytest.txt](evidencias/f9-pytest.txt).
