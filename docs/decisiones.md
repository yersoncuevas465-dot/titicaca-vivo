# Decisiones, propuestas y pendientes

Así se lee este archivo:

- **D-xx**: decisión tomada (en el código o en el modelo);
- **PR-xx**: propuesta, que no entra al código sin el "ok" del equipo;
- las preguntas P1–P5 de la F0 ya se respondieron (19/10/2026) y ahora son D-08 a D-12.

---

## Decisiones de la F0 (19/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-01 | La raíz del proyecto es `TURISMO PROGRAMA/titicaca_vivo/`. | Es la estructura de la sección 13 y deja aparte el ZIP de entrega. |
| D-02 | "Un documento por salida" (RN-09) se valida en el modelo, con FOR UPDATE, y otra vez en el trigger, no con un UNIQUE. | `reserva_pasajero` no tiene `salida_id`, y las reservas canceladas o vencidas no deben bloquear. |
| D-03 | El cambio de estado de una salida lo escribe en la bitácora el trigger `trg_salida_au`, con `@app_usuario_id` y `@app_ip`. El modelo no lo repite. | El enunciado pide el trigger, y así no hay registros duplicados. |
| D-04 | Reprogramar actualiza la misma reserva (`salida_id` y `reprogramada_desde_salida_id`). | El código TV-XXXX, los pagos y el boleto siguen valiendo. |
| D-05 | `temporada` se cruza con `salida` por fecha, sin FK. | Está explicado en [modelo-datos.md](modelo-datos.md#relaciones-y-cardinalidad). |
| D-06 | Reglas de contraste de la paleta (ver la tabla siguiente). | WCAG AA (sección 10). |
| D-07 | El logo es geométrico y no requiere dependencias nuevas (ver D-13). | Sección 3: no se agregan dependencias sin preguntar. |

### Respuestas del equipo a P1–P5 (19/10/2026: "aceptamos las recomendaciones")

| ID | Pregunta | Decisión |
|---|---|---|
| D-08 | P1 · ¿El titular viaja? | La casilla "Yo también viajo" viene marcada y copia al titular como pasajero 1. Si se desmarca, el titular no ocupa lugar. |
| D-09 | P2 · Pago reportado cerca del vencimiento | Al **reportar** un pago, `vence_en` pasa a ser "zarpe − 60 min". Si el pago se **rechaza**, `vence_en` vuelve a ser "ahora + 2 h" como mínimo. (En la semilla, la reserva TV-RQCP lo muestra.) |
| D-10 | P3 · `monto_familia` | `personas × PAGO_FAMILIA_PERSONA_NOCHE` (`.env`, S/ 40.00 por confirmar), guardado como foto. |
| D-11 | P4 · Devolución | Sin columnas nuevas: la reserva pasa a `cancelada` y se registra `bitacora.accion = 'devolucion_solicitada'` (y luego `'devolucion_atendida'`). (En la semilla: reserva TV-YSYM.) |
| D-12 | P5 · Crédito de las fotos | Nueva columna `comunidad.foto_credito VARCHAR(200) NULL`. La foto es `img/comunidades/<slug>.webp`. |
| D-13 | PR-01 · Logo | Aprobado. Se usa desde la F2 (ver la ficha más abajo). |
| D-14 | PR-02 · Nombre | Aprobado: **Titicaca Vivo**. |

### Decisiones de la F1 (19/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-15 | `rol` tiene **4 filas**, no 5. | El enunciado fija exactamente 4 códigos y el CHECK no deja inventar más. Cumple el mínimo del docente (≥ 3). |
| D-16 | Cada script y cada conexión de la app activan `sql_mode = STRICT_TRANS_TABLES,…`. Los triggers se crean en modo estricto. | XAMPP trae un `sql_mode` **no estricto**: un ENUM inválido se guardaría como `''` con solo un aviso. |
| D-17 | La regla RN-07 de la base vive en el procedimiento `pr_validar_salida`, que llaman `trg_salida_bi` y `trg_salida_bu`. | MariaDB no permite un trigger para INSERT y UPDATE a la vez. Así la regla se escribe una sola vez. |
| D-18 | `trg_salida_bu` solo revisa la salida si cambia la lancha, el capitán, el cupo o el horario, o si se reactiva una salida suspendida o cancelada. | Marcar como "finalizada" una salida antigua no debe fallar porque, por ejemplo, la lancha se dio de baja después. |
| D-19 | El trigger de sobreventa bloquea la salida con `FOR UPDATE` y cuenta con `LOCK IN SHARE MODE` (lectura actual). | En REPEATABLE READ, un `SELECT` normal lee la "foto" del inicio de la transacción y podría no ver una reserva recién confirmada. |
| D-20 | Consecuencia de D-19: no se puede hacer `INSERT INTO reserva_pasajero … SELECT … JOIN salida` en una sola sentencia (error 1442). La semilla usa una tabla temporal y la app inserta con `VALUES`. | MariaDB no deja que un trigger bloquee una tabla que la misma sentencia está leyendo. |
| D-21 | Hay 5 embarcaciones (las 3 operativas que pide la sección 12, más una en mantenimiento y una de baja) y 5 rutas (las 4 del enunciado más "Uros y Luquina Chico"). | Para llegar a ≥ 5 filas por tabla y mostrar todos los estados. |
| D-22 | `reserva.codigo` y `reserva.token_envio` usan `ascii_bin`. | Así el CHECK distingue mayúsculas de minúsculas. El modelo guarda el código siempre en mayúsculas. |
| D-23 | `estado_publico` también puede valer `'cancelada'`. | Es un complemento de RN-08: la portada no muestra esas salidas. |
| D-24 | Se agregó `database/00_crear_bd_usuario.sql`. | Es el paso 2 del README: crea las 2 bases y un usuario con permisos solo sobre ellas. |
| D-25 | El venv se crea **fuera de OneDrive** (`%USERPROFILE%\.venvs\titicaca_vivo`). | OneDrive sincronizaría miles de archivos y puede bloquearlos. |
| D-26 | La semilla calcula `precio_aplicado` con la regla RN-04, no lo escribe a mano. Las fechas salen de `CURDATE()`. | Los datos son coherentes el día que se importen, y si falta una tarifa la importación falla al instante. |

### Decisiones de la F2 (19/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-27 | Se suman **colores de estado** fuera de la paleta: error `#9B1C1C`, éxito `#1F5E3B`, amarillo `#8A6100` y texto suave `#5E4654`. Todos tienen ≥ 4.6:1 sobre crema y arena. | Un error no puede mostrarse en terracota (3.2:1). Hacen falta colores claros para "llena", "suspendida" y los niveles de alerta. |
| D-28 | Credenciales malas → **401** con un solo mensaje ("Usuario o contraseña incorrectos.") para usuario inexistente, clave mala o usuario inactivo. Campos vacíos → **422**. | No se delata qué usuarios existen. Un hash ficticio iguala los tiempos. |
| D-29 | El límite de `/entrar` cuenta **solo los intentos fallidos**, por IP, en memoria. | Un guía que entra bien varias veces no se bloquea. Con un proceso de waitress, la memoria alcanza; con varios procesos haría falta Redis. |
| D-30 | `session_protection = "basic"`, no `"strong"`. | En el lago el celular cambia de IP (3G/4G) y "strong" cerraría la sesión a cada rato. |
| D-31 | Las contraseñas de más de 72 bytes se rechazan como incorrectas. | bcrypt 5 lanza `ValueError` con más de 72 bytes. Así no hay un error 500. |
| D-32 | Al entrar se limpia la sesión (`session.clear()`). La sesión dura hasta cerrar el navegador (sin "recordarme"). `/salir` solo acepta POST con CSRF. | Evita arrastrar datos de otra sesión, y que un enlace o una imagen cierren la sesión de alguien. |
| D-33 | `no-store` en `/panel/*`, `/entrar` y `/salud`. Los estáticos llevan `?v=VERSION`: en producción se guardan 1 día y en desarrollo no se guardan. | Datos personales fuera de la caché y páginas livianas en una red lenta. |
| D-34 | `/salud` saca la hora **de la base** (`SELECT NOW()`) y no muestra el detalle del error. | Así demuestra que la base responde, sin dar pistas a un atacante. |
| D-35 | La portada `/` es provisional en la F2. | La portada real (salidas, alertas, mapa) es la F3. |
| D-36 | `servidor.py` escucha por defecto en `127.0.0.1:8080`. `--host 0.0.0.0` lo abre a la red local. | Seguro por defecto. Para probar con celulares hay que abrirlo a propósito. |
| D-37 | Los íconos PNG se generan con `scripts/generar_iconos.py` (Pillow), con la misma geometría del SVG. | Sin dependencias nuevas (D-13). |

### Decisiones de la F3 (20/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-38 | **Nuevas columnas `comunidad.latitud` y `comunidad.longitud`** (DECIMAL(9,6), NULL), con CHECK "las dos o ninguna" y rango válido. **El equipo debe confirmarlo.** | La sección 8.7 pide un mapa "con las comunidades leídas de la base", y el modelo de 20 tablas no tenía dónde guardar la ubicación. Pasó lo mismo con `foto_credito` (P5). |
| D-39 | En el mapa, lo **fijo es dibujo**: la orilla, las islas, Puno y la boca de la bahía, en `servicios/mapa.py`. Lo **variable sale de la base**: las comunidades y las rutas. | Igual que una ilustración. Si se agrega una comunidad o una ruta, aparece sola en el mapa. |
| D-40 | Los tramos que van de la bahía al lago abierto pasan por la **boca de la bahía** (entre Capachica y Chucuito). | Una línea recta cruzaría la península de Capachica, y las lanchas no van por tierra. |
| D-41 | "Artesanía" en la ficha de la comunidad = cuántas familias ofrecen `taller_textil`, sin una columna nueva. | El enunciado pide mostrar la artesanía y el modelo ya tenía ese dato en `servicios`. |
| D-42 | La ficha pública muestra de cada familia **solo** su nombre de casa, su capacidad y sus servicios. El responsable y el teléfono quedan para el panel. | Sección 9: "familias anfitrionas sin datos personales". |
| D-43 | El listado público oculta las salidas **canceladas**. Una salida **suspendida** se muestra con su motivo. | El turista con reserva debe ver por qué no sale (RN-11, F6). |
| D-44 | Un filtro inválido en `/salidas` (fecha o ruta) responde **422**, con el error junto al campo y, debajo, las salidas de hoy. | La convención del proyecto: 422 para datos inválidos (F2). Y la página sigue siendo útil. |
| D-45 | El precio lo multiplica **Python** (`tarifa.calcular_precio`, Decimal con redondeo al céntimo hacia arriba en la mitad). El SQL trae la tarifa y el recargo. | La regla RN-04 vive en el modelo y la F4 la reutiliza al reservar. El redondeo es igual al `ROUND` de la semilla. |
| D-46 | Mientras una comunidad no tenga foto, se muestra una **ilustración propia**. Las fotos de Commons esperan autorización para descargarlas. | Descargar archivos requiere el permiso del equipo. |
| D-47 | Las páginas públicas están en español en la F3. El diccionario es/en (`servicios/textos.py`) llega en la F6 (**hecho**: D-90). | Así lo ordena el plan de fases (la F6 incluye el inglés). |
| D-48 | `estatico()` y `foto_comunidad()` son **globales de Jinja**, no `context_processor`. | Los macros importados con `{% from %}` no ven el contexto de la plantilla. |

### Decisiones de la F4 (20/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-49 | Las 6 fotos de Commons se bajaron como **miniaturas** (960 px), se revisaron y se convirtieron a WebP ≤ 40 KB. El crédito va en `comunidad.foto_credito`. | Autorizado por el equipo. Ver [creditos-imagenes.md](creditos-imagenes.md). |
| D-50 | La transacción de reserva va en **READ COMMITTED**. Empieza con un ROLLBACK (descarta lecturas previas de la petición), bloquea la salida con `FOR UPDATE` y cuenta con `LOCK IN SHARE MODE`. | En REPEATABLE READ un SELECT normal puede ver una foto vieja y vender de más. Las dos defensas juntas lo evitan. |
| D-51 | Idempotencia doble: después de bloquear la salida se busca el `token_envio` y, como última red, se captura el error **1062** del UNIQUE. | Un doble clic o 3 envíos simultáneos dan la misma reserva, aunque haya varios procesos (RN-03). |
| D-52 | **RN-10 en la misma transacción**: si la reserva queda `confirmada` (muelle), se asigna la familia. Con Yape/Plin solo se revisa que haya una libre; se asigna al verificar el pago (F5). Las familias candidatas se bloquean con `FOR UPDATE`. | La familia no queda asignada a una reserva que puede vencer, y dos reservas de la misma noche no se quedan con la misma familia. |
| D-53 | Máximo **10 pasajeros** por reserva (`MAX_PASAJEROS_POR_RESERVA`). | Una familia anfitriona recibe hasta 10 personas (CHECK de la F1). |
| D-54 | Solo se reserva una salida `programada` que todavía no zarpa (no `embarcando`). | En el muelle, la reserva de último minuto la hace el operador (F5, canal mostrador). |
| D-55 | Al reportar un pago, `vence_en = GREATEST(vence_en, zarpe − 60 min)`. El monto va de 0 a lo que falta pagar, y el número de operación tiene de 4 a 30 caracteres. | Es la forma de aplicar D-09 sin acortar nunca el plazo. |
| D-56 | Sin identificarse, `/reservas/<código>` muestra los datos personales **ocultos**. Con código + documento del titular (`/mi-reserva`) la sesión recuerda hasta 10 reservas y muestra todo. El boleto y el pago exigen identificarse. | Sección 9: "datos enmascarados salvo acceso validado". |
| D-57 | Códigos HTTP: **303** después de un POST correcto; **422** con datos o reglas inválidas; **409** al abrir el formulario de una salida que no recibe reservas; **401** si "Mi reserva" falla. | Es la misma convención de la F2 y la F3. |
| D-58 | Los números de Yape/Plin y el titular del cobro van en el `.env` (ficticios en el ejemplo), no en la base. | Las 20 tablas no tienen una tabla de "agencia". No son datos fijos en la plantilla. |
| D-59 | El QR guarda `URL_PUBLICA + /panel/abordaje/<código>`. Si `URL_PUBLICA` está vacía, usa la dirección del servidor. | El celular del guía tiene que poder abrir esa URL en la red de la agencia. |
| D-60 | La nacionalidad usa un `<datalist>` con los 249 códigos ISO 3166 (`servicios/paises.py`). | Es un catálogo técnico de la norma, no un dato del negocio. Un solo `<datalist>` mantiene la página por debajo de 100 KB. |
| D-61 | El boleto en PDF es A6, con el isotipo redibujado en reportlab y el QR en PNG. | Cumple D-13 sin dependencias nuevas. Se revisó con pdf.js. |
| D-62 | En el celular, el menú público pasa a una segunda línea. | Con "Mi reserva" ya no entraban las 5 opciones en 375 px. |

### Decisiones de la F5 (20/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-63 | El retorno de una salida = zarpe + duración de la ruta; el formulario no lo pide. | La duración ya está en `ruta`, y así el cruce de horarios (RN-07) siempre usa el mismo dato. |
| D-64 | Al editar, la ruta no cambia. Con reservas activas se puede cambiar la hora, pero no el día. | Los precios (foto RN-04) y la noche con la familia dependen de la ruta y del día. |
| D-65 | RN-07 se revisa en el modelo con la **lancha bloqueada** (`FOR UPDATE` sobre `embarcacion`), en READ COMMITTED. Además: capitán y guía activos, y el guía con rol guía. El trigger sigue como red; si frena algo, se muestra su mensaje. | Sin el bloqueo, dos salidas creadas a la vez para la misma lancha podrían no verse entre sí. |
| D-66 | Solo se **cancela** una salida sin reservas activas. Si tiene, se suspende. | Una cancelación dejaría reservas pagadas sin camino. Suspendida, el turista puede reprogramar o pedir la devolución (RN-11, F6). |
| D-67 | **Marcar zarpe**: el operador o el capitán de la salida, desde 60 min antes. Las reservas confirmadas o pagadas sin nadie a bordo pasan a `no_show` (S-11); si subió parte del grupo, la reserva queda como estaba. Los estados `embarcando` y `finalizada` todavía no se usan. | Es lo que pide la F5. Ningún requisito dice cuándo pasar a `embarcando`, y `finalizada` va como PR-10. |
| D-68 | Abordaje: por QR = `qr`; desde la lista o escribiendo el código = `manual`. Bloqueo: la salida con `LOCK IN SHARE MODE` y luego la reserva con `FOR UPDATE`, el mismo orden que usa el zarpe. | Así se registra el método sin preguntarlo, y no hay interbloqueos entre el zarpe y el abordaje. |
| D-69 | Verificar un pago exige que la reserva siga `pendiente_pago` y vigente; si venció, se rechaza. Al llegar al total pasa a `pagada` y se asigna la familia (D-52). Si no hay familia libre, el pago se verifica igual, con aviso y `bitacora.accion = 'sin_familia'`. | El dinero es real y no debe perderse. Una reserva vencida ya no tiene su lugar guardado, y revivirla podría vender de más. |
| D-70 | Al rechazar, el motivo es obligatorio. Si no quedan otros pagos por revisar y la reserva sigue vigente, `vence_en = ahora + 2 h` (D-09). | El turista ve el motivo y tiene tiempo de corregir. Si ya venció, no se revive. |
| D-71 | El **cobro en el muelle** (efectivo, POS o transferencia) lo registra el operador desde la página de abordaje y queda verificado. El monto no pasa del saldo, y la transferencia lleva número de operación. Una reserva abordada puede pagar su saldo sin cambiar de estado. | Es el flujo de la v1 ("paga en el muelle"); el ENUM `pago.metodo` ya lo tenía. |
| D-72 | El manifiesto es un PDF A4 hecho con `reportlab.platypus` (viene con reportlab). Lleva el documento completo, la columna "Abordó" y las firmas. | La sección 8.4 pide documento y nacionalidad; la tabla sigue en otra hoja si no entra. |
| D-73 | WhatsApp: enlace `wa.me/?text=…` sin API (sección 17). El texto no lleva documentos ni teléfonos de los turistas. Hay un botón extra para enviarlo al teléfono del guía (se agrega el +51). | Un mensaje de WhatsApp se reenvía con facilidad: van solo los datos necesarios. |
| D-74 | La "lista del guía imprimible" (8.6) es una página liviana que se imprime o se guarda como PDF desde el navegador. El service worker queda como PR-09. | La sección 8.6 dice que el service worker es opcional. |
| D-75 | Los catálogos van en un blueprint aparte (`rutas/catalogos.py`) con 2 plantillas comunes. Cada catálogo tiene su propio SQL en su modelo. No se borra nada: se desactiva (`activa = 0`). La excepción son las paradas, que no tienen hijos. | Hay menos código repetido y cada SELECT sigue a la vista para explicarlo. Las FK RESTRICT protegen la historia. |
| D-76 | Reglas al editar catálogos: una lancha con salidas por venir no deja de estar operativa ni baja su capacidad por debajo de un cupo; una ruta con salidas no se desactiva; una comunidad que es parada de una ruta activa no se desactiva; una familia con noches asignadas no se desactiva ni baja su capacidad; las temporadas no se solapan (S-14); hay una sola parada de pernocte (S-16), en una ruta con noche y una comunidad con hospedaje. | Un cambio de catálogo no puede romper una salida o una reserva ya vendida. |
| D-77 | Los tipos de pasajero solo se editan (nombre y edades). | El CHECK de la tabla fija los 5 códigos. |
| D-78 | Usuarios: el nombre de usuario es `[a-z0-9._-]{3,30}`. La contraseña tiene de 10 caracteres a 72 bytes; al editar, si queda vacía, no cambia. La bitácora anota `contrasena_cambiada`, nunca la contraseña. El admin no se desactiva ni se quita el rol a sí mismo. Un capitán o guía con salidas por venir no se desactiva ni cambia de rol. Los roles se ven, pero no se editan. | Así no se pierde el acceso de administración ni se rompe RN-07 en salidas ya programadas. |
| D-79 | `bitacora.anotar()` es un ayudante común. También se anotan los catálogos y los usuarios (`creacion`, `edicion`, `borrado`). | RN-14 pide los estados y los inicios de sesión. Lo demás ayuda a la auditoría y sale casi gratis. |
| D-80 | Los mensajes de WTForms se traducen con un diccionario (`FormularioBase`), sin Babel. | Sin dependencias nuevas, y todo queda en español. |
| D-81 | Si una regla frena una acción de un solo botón (zarpe, verificar), la página se muestra otra vez con el motivo y el código **422**. | Es la misma convención de D-57. |

### Decisiones de la F6 (20/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-82 | Una alerta naranja o roja suspende sus salidas **en una transacción**: las bloquea con `FOR UPDATE` en orden de id y hace un solo `UPDATE … IN (…)`. Solo afecta a las salidas programadas que todavía no zarpan. El trigger anota cada salida y el modelo anota `suspension_por_alerta`. | Lo pide RN-11 ("en un solo paso"). El orden de id evita los interbloqueos. |
| D-83 | Reprogramar (D-04) bloquea las dos salidas en orden de id y luego la reserva. Vuelve a contar el cupo con lectura actual y revisa los documentos (RN-09). Si cambia la noche, la vieja pasa a `cancelado` y se asigna una familia por rotación; si la reserva ya tuvo esa fecha, se reutiliza su fila (`ON DUPLICATE KEY UPDATE`). Las opciones: misma ruta, programada, sin zarpar y con lugar para todo el grupo. | Reprogramar es una reserva nueva en otra salida: aplica la misma regla RN-02. |
| D-84 | La devolución es un POST aparte (`/reservas/<código>/devolucion`), desde la página de reprogramar. La reserva pasa a `cancelada`, su noche a `cancelado`, y queda `devolucion_solicitada` con el monto verificado. El operador la marca `devolucion_atendida`, con una nota, en Pagos. | D-11, sin columnas nuevas. El reembolso es a mano (sección 17). |
| D-85 | Reasignar cambia la familia en la misma fila (S-20). La nueva tiene que ser de la misma comunidad, estar activa, tener capacidad y estar libre esa noche. Las candidatas aparecen en el orden de RN-10 (la primera viene marcada) y el motivo es obligatorio. | RN-10: "el operador puede reasignar indicando el motivo". |
| D-86 | «Confirmar que se cumplió»: el operador pasa a `cumplido` una noche que ya pasó, de una reserva `abordada`. | El reporte de transparencia cuenta como ingreso lo cumplido. No es PR-10 (automático), que no se aprobó. |
| D-87 | El reporte de transparencia está en el panel (admin y operador), por mes y listo para imprimir. Incluye a las familias sin noches. | Lo que cobra cada familia es un dato sensible: publicarlo necesita el acuerdo de la comunidad (PR-12). |
| D-88 | Reseña: "después de la fecha del viaje" = cuando pasó la hora de retorno. Una por reserva. Se publica sin nombre: solo el país y el mes del viaje. El comentario se muestra en su idioma (`lang`). | Privacidad. Un viaje de 3 horas se puede comentar esa misma tarde. |
| D-89 | Los indicadores tienen periodos en lista blanca (30, 90 y 365 días, contando también las salidas que vienen). Las barras son `<rect>` SVG y cada gráfico tiene su tabla. | La CSP no deja `style` en línea. La tabla sirve también al lector de pantalla. |
| D-90 | Inglés: un diccionario cuya clave es el texto en español (`t('…')`); si falta una traducción, se ve el español. La elección queda en la sesión (`/idioma/<es\|en>?volver=`, solo rutas internas). El panel y `/entrar` quedan en español. Los mensajes del modelo se traducen en la ruta (`mensaje()`, con patrones para los números). Lo que viene de la base queda en español (PR-13). | 8.9: "un diccionario de textos; el panel queda solo en español". Las plantillas se siguen leyendo en español. Una prueba revisa que no falte ninguna traducción. |
| D-91 | Las rutas del panel de la F6 están en `rutas/panel_seguimiento.py`, registradas en el mismo blueprint `panel`. | `panel.py` ya tenía 450 líneas. Las URL siguen siendo `/panel/...`. |
| D-92 | Las fechas usan el filtro `inicial_mayuscula`, no `capitalize`. | `capitalize` de Jinja baja a minúscula el resto: «Tuesday, october 20». |

### Decisiones de la F7 (20/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-93 | La prueba mutante copia `reserva.py` sin `FOR UPDATE` ni `LOCK IN SHARE MODE`, quita el trigger de sobreventa **solo durante la prueba** (después lo vuelve a crear y lo comprueba) y usa la misma pausa de 0.3 s en las 3 corridas. | Con el trigger puesto, el mutante no vende de más: es la segunda defensa (D-19). Hay que sacarlo para ver qué hace cada defensa. Con el trigger solo hay interbloqueos (1213): por eso el modelo bloquea primero. |
| D-94 | La accesibilidad se revisa con un auditor propio sobre `html.parser` (sin dependencias nuevas), en 56 páginas. Contraste, foco visible y uso con teclado se revisaron a mano. | Sección 3: no se agregan dependencias sin preguntar. Lo que no se ve en el HTML no se puede automatizar sin un navegador. |
| D-95 | `[hidden] { display: none !important; }` en el CSS. | Una clase con `display: flex` le ganaba al atributo `hidden`: el selector de acompañantes no se escondía con JavaScript (error desde la F4). |
| D-96 | El peso de página es el HTML más los estáticos propios que pide (CSS, JS, SVG, PNG), sin las fotos de las comunidades (que cargan diferidas). Se mide también en inglés y en el panel. | Así lo dice la sección 11: "100 KB o menos sin contar las fotos". |
| D-97 | El EXPLAIN se toma después de `ANALYZE TABLE`, sobre la semilla. Con tablas de 5 a 20 filas, MariaDB a veces prefiere leer la tabla entera (`ALL`): se explica en cada caso. | El plan depende de la cantidad de datos. El índice correcto ya está y el optimizador lo usará cuando crezca la tabla. |
| D-98 | Las pruebas de seguridad recorren `app.url_map`: CSRF en **cada** ruta POST y sesión en **cada** página GET del panel. | Una ruta nueva queda cubierta sola. Si alguien olvida `@requiere_rol`, la prueba falla. |

### Decisiones de la F8 (20/10/2026)

| ID | Decisión | Por qué |
|---|---|---|
| D-99 | Los 5 CHECK con `REGEXP` que distinguen mayúsculas usan `x COLLATE utf8mb4_bin REGEXP …` en vez de `CAST(x AS BINARY) REGEXP …`. | MySQL 8 rechaza `CAST AS BINARY` con REGEXP (error 3995). `COLLATE utf8mb4_bin` hace lo mismo en MariaDB y en MySQL 8. Las 102 pruebas de la base siguen pasando. |
| D-100 | Platino se probó con un **segundo servidor MariaDB** en la misma PC: puerto 3307, con sus propios datos, su propio `root` y su propio `titicaca_app`, y contraseñas nuevas que no están en el proyecto. Solo cambiaron `BD_PUERTO` y `BD_CONTRASENA`. | No había otra PC ni nube disponibles. Un servidor aparte, con sus propios datos y usuarios, demuestra lo mismo: la app no depende del MariaDB de XAMPP. La prueba en otra PC queda como guía para el equipo. |
| D-101 | HTTPS: un proxy (Caddy, nginx o IIS) va delante de waitress, y waitress se arranca con `waitress-serve --trusted-proxy=127.0.0.1 --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --clear-untrusted-proxy-headers`. **No se cambia código.** | waitress no atiende HTTPS. Si no confía en el proxy, todos los turistas parecen `127.0.0.1` y el límite de `/entrar` se vuelve uno solo para todos (lo probamos). Si confiara en cualquiera, cualquiera inventaría su IP. Las opciones ya vienen en waitress: no hay dependencias nuevas. |
| D-102 | La revisión de dependencias se hizo a mano, sin `pip-audit`: los 36 paquetes del venv contra PyPI y OSV. setuptools 65.5.0 (8 fallas) no se cambia desde aquí. | Lo decidió el equipo en la F8. setuptools no lo usa la app (solo sirve para instalar paquetes), y actualizarlo es cambiar la PC del equipo: queda en Pendientes. |
| D-103 | `consultas-explicadas.md` copia el SQL del código con un script, no a mano. `tests/test_documentacion.py` revisa que siga idéntico y que el enlace apunte a su línea. Los ejemplos y los EXPLAIN salen de la base de pruebas recién sembrada. | Un documento copiado a mano se desactualiza sin que nadie lo note. El docente firma lo que explicamos, y eso tiene que ser lo que de verdad corre. |
| D-104 | `scripts/empaquetar.py` arma el ZIP fuera del proyecto (`../entrega/`), sin `.env`, entornos virtuales, cachés, `logs/` ni `.coverage`. Si algún archivo lleva un valor secreto del `.env`, no lo arma. | Sección 16: «un ZIP sin .env ni venv». Revisar los valores, y no solo el nombre del archivo, evita que un secreto copiado en un documento salga en la entrega. |
| D-105 | El fixture `limite_de_intentos_limpio` pide la `app`. | Sin la app, el limitador no tiene memoria. Un archivo de pruebas que no usa la app fallaba al correrlo solo; se vio con `test_documentacion.py`. |
| D-106 | Fondos tipo **marca de agua** (el lago abajo a la derecha y una trama de tejido muy suave), portada con un amanecer sobre el lago y 2 capas de **olas animadas**, y movimiento suave de las tarjetas y botones al pasar el mouse. Solo CSS y 4 SVG propios (menos de 2 KB cada uno), sin JavaScript ni CDN. Con «reducir movimiento» del sistema, nada se mueve. | Pedido del equipo (21/10/2026): la página se veía «seca». Así no cambia ninguna regla ni consulta, la CSP sigue igual y el texto queda sobre crema o sobre tarjetas (contraste de D-06). |
| D-107 | Sección **«Cómo reservar»** (3 pasos) en la portada, y en «Mi reserva» una ayuda para quien todavía no tiene código. Con su versión en inglés. | El equipo preguntó dónde se pide el código: no se pide, se genera al terminar la reserva. Ahora la página lo dice. |
| D-108 | El peso de cada página cuenta también las imágenes de fondo que pide el CSS (`url(...)`). | Si no, los fondos nuevos no contarían para el límite de 100 KB (D-96). Con ellos, las páginas pesan de 41 a 62 KB. |

### Decisiones de la mejora de cuenta, seguridad y marca (30/10/2026)

Pedido del equipo: dejar el sistema tan detallado como NeoClinic (su otro proyecto): recuperar la contraseña, cada rol con su función a la vista y fotos de fondo como marca de agua. El detalle está en [fase-9-cuenta-y-marca.md](fase-9-cuenta-y-marca.md).

| ID | Decisión | Por qué |
|---|---|---|
| D-109 | Cada sección tiene una **foto del lago como marca de agua** (opacidad 0,14, como el velo de 86 % de NeoClinic, fija detrás de todo) y su crédito al pie. Son las 6 fotos de las comunidades agrandadas y suavizadas por `scripts/preparar_fondos.py` (960×600, 20 KB o menos). Van en un `<img loading="lazy">` que en el celular está oculto: **en el celular no se descargan**. El acceso y el resumen del panel comparten foto; el formulario de reserva no lleva (es la página más pesada). | Pedido del equipo, como en NeoClinic. En un `<img>` y no en el CSS, la foto cuenta para el peso de su página (D-96, D-108) y cada página baja solo la suya (en el CSS se contarían las 6). El turista del lago, con poca señal, no paga nada. |
| D-110 | La sesión del personal se cierra sola tras **30 minutos sin actividad** (`SESION_INACTIVA_MIN`). El servidor guarda la hora del último clic en la sesión; `js/sesion.js` avisa 2 minutos antes y, mientras la persona escribe, le dice al servidor que sigue trabajando (`/panel/sesion`, como mucho una vez por minuto). El cierre queda en la bitácora con el motivo. | Un celular del muelle o una PC de la agencia que queda sola no debe dejar a la vista los datos de los pasajeros. Sin JavaScript igual se cierra (lo revisa el servidor). El script es un archivo propio: la CSP sigue igual. |
| D-111 | **«¿Olvidaste tu contraseña?»** en 2 pasos: usuario o correo → un código de 6 dígitos al correo de la cuenta → código y contraseña nueva. El código no se guarda en ninguna parte: en la sesión del navegador queda solo su firma (HMAC con la `SECRET_KEY` y el hash actual), así vence a los 15 minutos, sirve una sola vez (la fila se bloquea con `FOR UPDATE`) y solo en el navegador que lo pidió. 5 códigos malos por pedido y 10 por IP cada 15 minutos; 5 pedidos por IP. El mensaje es el mismo exista o no la cuenta. Sin correo real (`CORREO_SIMULAR=1`) el código sale en la ventana del servidor; si el admin lo olvidó, `flask usuarios clave admin`. | Como en NeoClinic, sin tablas nuevas: la base sigue con 20 tablas. Un código guardado en la base sería un secreto más que proteger. Sin internet la demostración funciona igual. |
| D-112 | La cookie de sesión guarda `id.sello`, con un sello que sale del hash de la contraseña (HMAC). **Si la contraseña cambia** (la persona, el admin, la recuperación o la consola), **las demás sesiones de esa cuenta se cierran solas**. Y con la sesión abierta, ninguna página se guarda en la caché del navegador (`no-store`). | Si alguien vio o robó una sesión, cambiar la contraseña la corta. Tras «Salir», el botón «Atrás» no muestra datos. Es el patrón «alternative tokens» de Flask-Login: no agrega consultas. |
| D-113 | **Mi cuenta** para los 4 roles: sus datos, **lo que hace y no hace su rol**, cambiar su contraseña (pide la actual), su correo y celular (pide la contraseña), y sus últimos movimientos. La regla de una contraseña nueva es la misma en todo el sistema: 10 caracteres o más, letras y números, sin espacios, sin el nombre de usuario. Se puede entrar con el usuario o con el correo. | Cada persona ve lo suyo y nada más. El correo es el que recibe el código (D-111): por eso lo cuida la contraseña. Las contraseñas demo siguen sirviendo para entrar: la regla vale para las nuevas. |
| D-114 | El admin **activa o desactiva una cuenta con un clic** desde Usuarios (POST con CSRF), con las mismas reglas que al editar: nadie se desactiva a sí mismo y un guía o capitán con salidas por venir no se desactiva. La lista marca a quien no tiene correo. | Dar de baja a alguien no debería tomar 5 pasos. Desactivada, la persona pierde la sesión en su siguiente clic. |
| D-115 | La **bitácora** muestra cada acción en palabras, se filtra también por periodo (hoy, semana, mes, año) y se **descarga en CSV** para Excel: toda o solo las entradas y salidas. Anota también el cierre de sesión, los intentos fallidos (con la cuenta, nunca lo que se escribió), los pedidos de código y los cambios de contraseña. La descarga queda anotada y una celda que empieza con `=`, `+`, `-` o `@` lleva un apóstrofo. | Como en NeoClinic. Lo escrito en un intento fallido podría ser una contraseña puesta en el campo equivocado. El apóstrofo evita que un motivo escrito por alguien se ejecute como fórmula al abrirlo en Excel. |
| D-116 | **Respaldos de la base** desde el panel del admin (Respaldos): un `.sql` con las 20 tablas (estructura con `SHOW CREATE TABLE` y datos con `INSERT`, leídos en **una sola foto** de la base con `START TRANSACTION WITH CONSISTENT SNAPSHOT`) y, al final, las vistas, el procedimiento y los triggers **copiados de `02_vistas_triggers.sql`**. Se descarga, se guardan los 15 más nuevos en `respaldos/` y cada creación o descarga queda en la bitácora. La carpeta no va en el ZIP de entrega ni en git. | Como en NeoClinic, sin depender de `mysqldump`. La foto consistente evita un respaldo a medias si alguien reserva mientras tanto. Los triggers van después de los datos para no frenar la carga, y desde el script para no arrastrar el `DEFINER` de quien creó la base: así el respaldo se restaura con `titicaca_app`, con root o con phpMyAdmin. La carpeta lleva datos personales. |
| D-117 | **Restaurar** solo desde la consola: `flask bd restaurar <archivo>`, con confirmación, y **antes guarda un respaldo «antes de restaurar»**. Solo acepta un respaldo completo (su cabecera y su «Fin del respaldo»). `flask bd reiniciar` también guarda antes un respaldo «antes de reiniciar» (se salta con `--sin-respaldo`). | Restaurar o reiniciar borra la base: un clic en el panel sería demasiado fácil de dar por error. Con el respaldo previo, cualquier reinicio o restauración equivocada se deshace. Un archivo cortado a la mitad dejaría la base sin tablas. |
| D-118 | **Respaldo automático** cada 24 horas (`RESPALDO_CADA_HORAS`) mientras corre `servidor.py`, en un hilo que revisa cada hora (y al arrancar). Y un **reporte general** para Excel (un ZIP con reservas, pagos, salidas y hospedajes en CSV) **sin documentos, teléfonos ni correos** de los turistas. | Si nadie se acuerda de respaldar, igual hay una copia del día. El hilo solo vive en el servidor: ni `flask run` ni las pruebas lo encienden. El reporte es para revisar la operación en Excel; para recuperar la base está el `.sql`. |

### D-06. Contraste medido de la paleta "Esencia Andina"

| Texto sobre fondo | Contraste | Uso permitido |
|---|---|---|
| tinta `#2A1220` sobre crema `#FEF9F3` | 16.6 : 1 | Texto normal (AAA). |
| ciruela `#572B44` sobre crema | 10.9 : 1 | Títulos, enlaces y texto normal (AAA). |
| crema sobre ciruela | 10.9 : 1 | **Botones principales** (fondo ciruela). |
| ciruela sobre arena `#F5E9DC` | 9.6 : 1 | Tarjetas (AAA). |
| terracota `#C27A52` sobre tinta | 5.1 : 1 | Texto normal (AA). |
| terracota sobre ciruela | 3.4 : 1 | Solo texto grande (≥ 24 px, o ≥ 18.7 px en negrita) y gráficos. |
| terracota sobre crema | 3.2 : 1 | Solo texto grande, íconos, bordes y la barra de cupos. **No sirve para botones con texto pequeño.** |
| terracota sobre arena | 2.8 : 1 | **No usar para texto.** |

---

## D-13 · Ficha del logo

Archivos en `app/estaticos/img/`:

| Archivo | Qué es | Peso | Dónde se usa |
|---|---|---|---|
| `logo.svg` | Isotipo + nombre + lema, para fondos claros. | 1.7 KB | Cabecera en pantallas anchas, `/entrar`, portada. |
| `logo-negativo.svg` | Lo mismo, para fondos ciruela o tinta. | 1.7 KB | Cabecera del boleto ("pase de abordar") y pie de página. |
| `logo-isotipo.svg` | Solo el sello circular. | 1.1 KB | Cabecera en celular, páginas 403/404/500, ícono de la app. |
| `favicon.svg` | El sello simplificado (sin cordillera, rayos ni anillo) para que se lea a 16 px. | 0.4 KB | Pestaña del navegador. |

**Concepto.** Es un sello circular, como el de un pase de abordar:

- el **Inti** (sol andino) saliendo sobre el lago, en terracota;
- la **Cordillera Real** al fondo, en tinta;
- una **balsa de totora** de los Uros, en arena;
- dos **olas** del Titicaca, en crema;
- el nombre: "Titicaca" en ciruela (serif en negrita) y "*Vivo*" en terracota cursiva;
- un **escalonado andino**, que recuerda los textiles de Taquile y la chakana;
- el lema "Turismo lacustre y vivencial · Puno".

Es neutral entre comunidades quechuas y aimaras.

**Reglas de uso:**

- El logo completo se usa desde 300 px de ancho. En el celular va el isotipo (40 px) más el nombre escrito en HTML.
- El isotipo mide 32 px como mínimo. Para tamaños menores se usa `favicon.svg`.
- Alrededor se deja libre un margen de al menos ¼ de la altura del logo.
- No se cambian los colores, no se estira y no se pone sobre fotos sin un fondo liso.
- **No se pone el logo dentro del QR**: empeora la lectura con cámaras de gama baja.

**Detalles técnicos:**

- Usa fuentes del sistema y nada desde CDN. `textLength` fija el ancho, así que nada se descuadra si falta Georgia.
- PDF (F5): el isotipo se redibuja con las primitivas de reportlab (no hace falta `svglib`).
- PNG (F2): `apple-touch-icon` se genera con Pillow, que ya viene con `qrcode[pil]`.

---

## Propuestas (no están en el enunciado; esperan el "ok")

| ID | Propuesta | Fase |
|---|---|---|
| PR-03 | Registrar en la bitácora también los **inicios de sesión fallidos** (usuario intentado e IP, nunca la contraseña). Hoy solo quedan en el límite de intentos. | F2+ |
| PR-04 | Validar que `adulto_nacional` tenga nacionalidad `PE` o documento CE. | F4 |
| PR-05 | Trigger de respaldo en `usuario`: el guía con comunidad y el capitán con licencia. El trigger de salida ya exige la licencia; el modelo de usuarios (F5) ya lo valida. | F7 |
| PR-06 | UNIQUE(`comunidad_id`, `nombre_familia`) en `familia_anfitriona`. | — |
| PR-07 | Límite de intentos también en `/mi-reserva`: por ejemplo, 10 cada 15 minutos por IP. Probar todas las combinaciones ya es inviable (31⁴ códigos × 10⁸ documentos), pero protegería mejor los datos personales. | F7 |
| PR-08 | El mismo **capitán** no puede tener dos salidas que se crucen, igual que la lancha. RN-07 solo lo pide para la lancha. | F6 |
| PR-09 | Un **service worker** que guarde la última lista de pasajeros para verla sin señal (opcional en la sección 8.6). | F7 |
| PR-10 | Marcar la salida como **finalizada** al volver y pasar sus hospedajes a `cumplido`. El reporte de transparencia cuenta los cumplidos. | F6 |
| PR-11 | **Reactivar** una salida suspendida cuando pasa la alerta. El trigger ya revisa los cruces al reactivar. | F6 |
| PR-12 | Una versión **pública** del reporte de transparencia por comunidad (por ejemplo, en su ficha), con el acuerdo de la asamblea. | F8 |
| PR-13 | Columnas en inglés para lo que viene de la base (`nombre_en`, `descripcion_en` en ruta, comunidad y tipo de pasajero) y nombres de países en inglés. | — |
| PR-14 | Al suspender por una alerta, una lista de los turistas afectados con un enlace wa.me para avisarles (como la lista de la F5, sin API). | F7 |
| PR-15 | Variable `BD_SSL_CA` en el `.env`, para conectarse por TLS a una base en la nube que lo exija. PyMySQL ya lo soporta: son 3 líneas en `config.py` y `bd.py`. | F8 |
| PR-16 | Fijar también las dependencias indirectas (`pip freeze > requirements-bloqueo.txt`), para que otra PC instale exactamente las mismas versiones. Hoy `requirements.txt` fija las 14 directas. | F8 |
| PR-17 | **Cuentas para el turista** (pedido del equipo, 21/10/2026). Primero, crear cuenta con correo y contraseña: sin dependencias nuevas, con bcrypt, y el admin las ve y las puede desactivar. Después, entrar con Google, Microsoft o Apple, o con un código por SMS. Hace falta: cambiar el modelo (hoy el turista reserva sin cuenta y la base tiene 20 tablas), registrar la app en cada proveedor (sus claves van al `.env`; Apple cobra USD 99 al año), una librería nueva para OAuth (hay que preguntar antes, sección 3), internet durante el uso y un servicio pagado para los SMS. | Después de la presentación |

---

## Pendientes

| Pendiente | Quién | Estado |
|---|---|---|
| Instalar **Python 3.13** y repetir `pytest`. Las pruebas de la F1 a la F8 se corrieron con 3.11. | Equipo | **Cerrado** (21/10/2026): con Python 3.13.16, 486 passed ([evidencias/f8-pytest-python313.txt](evidencias/f8-pytest-python313.txt)) |
| HTTPS delante de waitress en producción (la cookie `Secure` lo necesita). | F8 | **Cerrado** (F8): guía y prueba en `fase-8-entrega.md` (D-101) |
| Revisión de dependencias con fallas conocidas, a mano y sin `pip-audit`. | F8 | **Cerrado** (D-102): 0 fallas en las 14 directas |
| Actualizar `setuptools` del entorno virtual o crearlo con Python 3.12/3.13, que ya no lo instalan (D-102). | Equipo | **Cerrado** (21/10/2026): el entorno de 3.13 no trae setuptools; 35 paquetes, 0 fallas conocidas |
| Antes de presentar, repetir la revisión de dependencias en osv.dev (guía en `fase-8-entrega.md`). | Equipo | Abierto |
| Platino en **otra PC de la red** o en la nube (el extra de la sección 4), con la guía de `fase-8-entrega.md`. | Equipo | Abierto |
| Probar con un lector de pantalla (NVDA) y con Lighthouse de Chrome. | Equipo | Abierto |
| **Riesgo aceptado**: `/mi-reserva` sin límite de intentos (PR-07 no se aprobó). | Equipo | Aceptado (F4) |
| Importar `01`–`03` una vez con la interfaz de phpMyAdmin. Se verificó con el cliente `mysql`, que interpreta `DELIMITER` igual. | Equipo | Abierto |
| Confirmar los datos "por confirmar": señal, ruta de Llachón, matrículas, precios, fechas de temporada y pago a las familias. | Equipo con Giant Trip | Abierto |
| Confirmar las columnas de ubicación (D-38) y, en OpenStreetMap, las coordenadas de Llachón y Luquina Chico. | Equipo | Abierto |
| Fotos de Commons: autorizadas, revisadas e instaladas (D-49). | Equipo | **Cerrado** (20/10/2026) |
| ¿La familia cobra si el turista no se presenta (`no_show`)? Hoy su noche queda `asignado`. | Equipo con Giant Trip | Abierto |
| Si al zarpar subió solo parte de un grupo, ¿la reserva pasa a `abordada`? Hoy queda como estaba (D-67). | Equipo con Giant Trip | Abierto |
| **Fuera de alcance** (sección 17): pagos reales, API de WhatsApp Business y scraping de SENAMHI. | — | Para una versión futura |
