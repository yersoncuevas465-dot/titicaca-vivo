# Matriz de permisos

Los permisos se revisan **dos veces**:

1. **En la ruta**, con el decorador `@requiere_rol(...)` de `app/seguridad.py`.
   - Sin sesión → redirige a `/entrar?next=...`.
   - Con sesión pero sin el rol → **403**.
2. **En el modelo**, con `exigir_rol(actor, ...)` de `app/modelos/__init__.py`.
   - Si una ruta olvidara el decorador, el modelo igual lanza `PermisoDenegado` y la app responde 403.

Leyenda:

| Signo | Significado |
|---|---|
| ✔ | Puede hacerlo. |
| 👁 | Solo puede mirar. |
| ◐ | Solo lo suyo: el guía y el capitán, únicamente las salidas que tienen asignadas; el residente (v2.9), sus productos. |
| — | No puede (403, o redirección a /entrar). |

| Página o acción | Turista (sin cuenta) | admin | operador | guía | capitán | residente | Fase |
|---|---|---|---|---|---|---|---|
| Portada, salidas, comunidades, alertas, `/salud` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | F3 (`/salud` en F2) |
| Reservar (formulario público) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **F4 ✔** |
| Contacto: enviar un mensaje a la agencia (CSRF, trampa para robots y límite por IP) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **v2.6 ✔** |
| Libro de reclamaciones: registrar una hoja y ver su constancia (solo quien la registró) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **v2.8 ✔** |
| Experiencias en las comunidades y pedido de cotización para grupos | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **v2.8 ✔** |
| Productos y artesanías: la página pública, por lugar y por tipo, y los 3 más nuevos en la portada | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **v2.9 ✔** |
| Completar los nombres con el DNI (RENIEC, `/api/dni`: con token CSRF y límite por IP) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | **v2.2 ✔** |
| Mi reserva (código + documento), boleto, reportar pago | ◐ (solo la suya) | — | — | — | — | — | **F4 ✔** |
| Boleto con QR de cualquier reserva (para imprimirlo o mandarlo) | — | 👁 | ✔ | — | — | — | **F10 ✔** |
| Reprogramar o pedir la devolución, reseña | ◐ (solo la suya) | — | — | — | — | — | **F6 ✔** |
| `/entrar`, `/salir` | — | ✔ | ✔ | ✔ | ✔ | ✔ | **F2 ✔** |
| Recuperar la contraseña con un código (`/recuperar`, sin sesión) | — | ✔ | ✔ | ✔ | ✔ | ✔ | **F9 ✔** |
| Mi cuenta: sus datos, su rol, su contraseña, su correo y celular, sus movimientos | — | ◐ (la suya) | ◐ (la suya) | ◐ (la suya) | ◐ (la suya) | ◐ (la suya) | **F9 ✔** |
| `/panel` (resumen del día) | — | 👁 (toda la operación) | ✔ | ◐ | ◐ | ◐ (sus productos) | **F2 ✔** |
| Salidas: crear, editar, suspender, cancelar | — | 👁 | ✔ | — | — | — | **F5 ✔** |
| Salidas: marcar el zarpe | — | — | ✔ | — | ◐ | — | **F5 ✔** |
| Reservas: buscar (código, documento, celular o nombre) y ver la ficha con su historial | — | 👁 | ✔ | — | — | — | **F10 ✔** |
| Vender en el muelle o por WhatsApp (queda con su canal y a su nombre en la bitácora) | — | — | ✔ | — | — | — | **F10 ✔** |
| Lista de pasajeros, manifiesto PDF, WhatsApp | — | 👁 | ✔ | ◐ | ◐ | — | **F5 ✔** |
| Abordaje por QR o manual | — | — | ✔ | ◐ | ◐ | — | **F5 ✔** |
| Cobrar en el muelle | — | — | ✔ | — | — | — | **F5 ✔** |
| Verificar o rechazar pagos | — | 👁 | ✔ | — | — | — | **F5 ✔** |
| Hospedajes: ver y reasignar (y el reporte de transparencia) | — | 👁 | ✔ | — | — | — | **F6 ✔** |
| Alertas: registrar y suspender salidas | — | 👁 | ✔ | — | — | — | **F6 ✔** |
| Catálogos (rutas, paradas, lanchas, tarifas, temporadas, tipos, comunidades, familias) | — | ✔ | ✔ | — | — | — | **F5 ✔** |
| Moderar reseñas | — | 👁 | ✔ | — | — | — | **F6 ✔** |
| Libro de reclamaciones en el panel: ver las hojas y responderlas (una vez, en 15 días hábiles) | — | 👁 | ✔ | — | — | — | **v2.8 ✔** |
| Productos en el panel: publicar, editar, retirar y volver a publicar | — | 👁 | ✔ (los de la agencia) | — | — | ◐ (los suyos, en su comunidad) | **v2.9 ✔** |
| Ocultar el producto de un residente y volver a mostrarlo | — | — | ✔ | — | — | — | **v2.9 ✔** |
| Devoluciones: marcar como atendida | — | 👁 | ✔ | — | — | — | **F6 ✔** |
| Indicadores | — | ✔ | ✔ | — | — | — | **F6 ✔** |
| Usuarios y roles | — | ✔ | — | — | — | — | **F5 ✔** |
| Activar o desactivar una cuenta con un clic (no la propia) | — | ✔ | — | — | — | — | **F9 ✔** |
| Bitácora | — | ✔ | — | — | — | — | **F2 ✔** |
| Bitácora por periodo y descarga en CSV | — | ✔ | — | — | — | — | **F9 ✔** |
| Respaldos de la base: crear, descargar y reporte general (restaurar, solo desde la consola) | — | ✔ | — | — | — | — | **F9 ✔** |

## Cómo se prueba

En `tests/test_rutas_panel.py`:

| Prueba | Qué comprueba |
|---|---|
| `test_bitacora_solo_para_admin` | admin → 200; operador, guía y capitán → 403. |
| `test_sin_sesion_el_panel_redirige_a_entrar` | Sin sesión → 302 a `/entrar`. |
| `test_el_capitan_ve_solo_sus_salidas` y `test_la_guia_ve_solo_las_salidas_que_tiene_asignadas` | ◐: cada uno ve solo sus salidas. |
| `test_el_modelo_tambien_niega_la_bitacora_al_operador` | La segunda verificación, sin pasar por la ruta. |
| `test_un_usuario_desactivado_pierde_la_sesion` | Si el admin desactiva a alguien, su sesión deja de valer en la siguiente petición. |
| `test_matriz_de_permisos` (F5, `tests/test_rutas_panel_operacion.py`) | 14 páginas del panel × 4 roles: el código esperado (200 o 403) para cada combinación de esta tabla. |
| `test_solo_el_operador_crea_salidas`, `test_solo_el_operador_revisa_pagos`, `test_la_guia_no_toca_los_catalogos`, `test_solo_el_admin_maneja_usuarios` | La segunda verificación (en el modelo) de cada acción de la F5. |
| `test_matriz_de_permisos_f6` (`tests/test_rutas_f6.py`) | Las 7 páginas nuevas de la F6 × 4 roles. |
| `test_toda_pagina_del_panel_pide_sesion` (F7, `tests/test_seguridad_f7.py`) | Recorre **todas** las páginas GET del panel: sin sesión, cada una redirige a `/entrar`. Una página nueva queda cubierta sola. |
| `test_otro_capitan_no_marca_el_zarpe`, `test_el_guia_registra_solo_en_su_salida`, `test_la_lista_de_pasajeros_es_solo_para_su_guia_o_capitan` | ◐: el guía y el capitán, solo en sus salidas. |
| `test_mi_cuenta_muestra_los_datos_y_lo_que_hace_cada_rol` (F9, `tests/test_cuenta.py`) | Mi cuenta para los 4 roles, cada uno con lo que hace y lo que no hace. |
| `test_solo_el_admin_activa_o_desactiva`, `test_no_se_desactiva_a_si_mismo_ni_a_un_guia_con_salidas` | Activar o desactivar: solo el admin, nunca a sí mismo ni a quien tiene salidas por venir. |
| `test_matriz_de_permisos` (F9) | Suma `/panel/mi-cuenta` (200 para los 4), `/panel/bitacora/exportar` y `/panel/respaldos` (solo el admin). |
| `test_el_residente_no_ve_nada_del_personal` y las demás de `tests/test_productos.py` (v2.9) | El residente: 403 en todo lo del personal; publica solo en su comunidad y solo edita lo suyo. El operador publica los de la agencia y oculta; el admin solo mira. |
| `test_solo_el_admin_maneja_los_respaldos`, `test_solo_se_descargan_respaldos_que_existen` (`tests/test_respaldos.py`) | Operador, guía y capitán: 403 en la página, el reporte y crear; y nadie baja un archivo que no sea un respaldo. |

## Notas

- El **admin** ve la operación pero no la ejecuta (supuesto S-26): así quedan separadas la administración del sistema y la operación diaria.
- El **turista** no tiene cuenta. Su acceso a "Mi reserva" se valida con el código y el número de documento del titular, y queda guardado en la sesión (F4).
