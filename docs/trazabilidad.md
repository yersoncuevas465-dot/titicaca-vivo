# Trazabilidad: requisito → base → código → pantalla → prueba

Estado: entrega final, revisada el 29/10/2026. Con las filas de la F9 (cuenta del personal y marca de agua), el 30/10/2026.

Cada regla del enunciado se puede seguir de punta a punta:

1. **Requisito**: la regla de negocio (RN-xx) o el requisito no funcional.
2. **En la base**: la tabla, restricción, vista o trigger de MariaDB que la cuida.
3. **En el código**: el archivo y la función de Python que la aplica (`archivo::función`).
4. **Dónde se ve**: la página de la app donde se puede mostrar en vivo.
5. **Pruebas**: las pruebas automáticas que demuestran que se cumple.

**Esta matriz se verifica sola.** `tests/test_trazabilidad.py` revisa que cada regla RN-01 a RN-15
tenga su fila, que exista cada prueba citada, cada archivo, cada función o trigger (`archivo::nombre`)
y cada página de la app (por ejemplo `/panel/pagos`). Si alguien borra o renombra algo de lo que aquí
se cita, `pytest` falla.

---

## 1. Reglas de negocio

| Requisito | En la base | En el código | Dónde se ve | Pruebas |
|---|---|---|---|---|
| **RN-01** Cupos libres = cupo − ocupados, nunca negativo | Vista `database/02_vistas_triggers.sql::v_disponibilidad_salida` (`GREATEST(…, 0)`) | `app/modelos/salida.py::listar_publicas` y `app/modelos/panel.py::salidas_de_hoy` leen la vista | `/salidas` (barra de cupos), `/panel` | `test_vista_disponibilidad_cuenta_solo_lo_que_ocupa_lugar`, `test_una_reserva_vencida_ya_no_ocupa_lugar` |
| **RN-02** Sin sobreventa | Trigger `database/02_vistas_triggers.sql::trg_reserva_pasajero_bi` (red de seguridad) | `app/modelos/reserva.py::crear`: `SELECT … FOR UPDATE` sobre la salida y conteo en READ COMMITTED, todo en una transacción | `/salidas/10/reservar` | `test_sin_cupo_no_se_crea_nada`, `test_ocho_hilos_por_el_ultimo_lugar_crean_una_sola_reserva`, `test_trigger_frena_la_sobreventa`, `test_el_mutante_sin_for_update_vende_de_mas` |
| **RN-03** Un envío, una reserva (doble clic, «Atrás», 3 envíos a la vez) | `database/01_esquema.sql::uk_reserva_token` (UNIQUE) | `app/modelos/reserva.py::crear` busca el `token_envio` y, si choca, captura el error 1062 | `/salidas/10/reservar` → «Confirmar reserva» dos veces | `test_el_mismo_token_no_duplica_la_reserva`, `test_doble_clic_no_duplica_la_reserva`, `test_tres_envios_del_mismo_formulario_crean_una_sola_reserva` |
| **RN-04** Precio = tarifa vigente × (1 + recargo de temporada), guardado como foto | `reserva_pasajero.precio_aplicado` (CHECK > 0) | `app/modelos/tarifa.py::calcular_precio`, `app/modelos/tarifa.py::precios_para_salida`; la foto la guarda `app/modelos/reserva.py::crear` | `/salidas/10` (precios por persona) | `test_calcular_precio`, `test_precio_de_una_salida_en_temporada`, `test_el_precio_aplicado_es_una_foto`, `test_reprogramar_mantiene_codigo_pagos_y_precio` |
| **RN-05** Yape o Plin: pendiente de pago, el lugar se guarda 2 horas | Condición `vence_en > NOW()` en la vista y en el trigger | `app/modelos/reserva.py::crear` (120 min), `app/modelos/reserva.py::vencer_pendientes` y el comando `flask reservas vencer` | `/reservas/TV-TX69` | `test_reserva_con_yape_queda_pendiente_y_vence_en_2_horas`, `test_vencer_pendientes`, `test_comando_reservas_vencer` |
| **RN-06** El turista reporta el pago y el operador lo verifica o rechaza | `database/01_esquema.sql::uk_pago_operacion` (un número de operación una sola vez) | `app/modelos/reserva.py::reportar_pago`, `app/modelos/pago.py::verificar`, `app/modelos/pago.py::rechazar`, `app/modelos/pago.py::registrar_cobro` | `/reservas/TV-RQCP/pago`, `/panel/pagos` | `test_reportar_pago_guarda_el_cupo_hasta_60_minutos_antes`, `test_verificar_el_total_deja_la_reserva_pagada_y_asigna_la_familia`, `test_rechazar_devuelve_2_horas_al_turista`, `test_cobro_en_el_muelle_en_dos_partes` |
| **RN-07** Salida válida: cupo ≤ capacidad, lancha operativa, capitán con licencia, sin cruces; no se edita si zarpó | `database/02_vistas_triggers.sql::pr_validar_salida`, `database/02_vistas_triggers.sql::trg_salida_bi`, `database/02_vistas_triggers.sql::trg_salida_bu` | `app/modelos/salida.py::_validar_rn07` (lancha con `FOR UPDATE`), `app/modelos/salida.py::crear`, `app/modelos/salida.py::editar` | `/panel/salidas/nueva` | `test_rn07_rechaza`, `test_la_misma_lancha_no_tiene_salidas_que_se_cruzan`, `test_no_se_edita_una_salida_que_ya_zarpo`, `test_el_capitan_debe_tener_licencia` |
| **RN-08** Estado público: disponible, pocos cupos, llena, suspendida… | `CASE` en la vista `database/02_vistas_triggers.sql::v_disponibilidad_salida` | Filtro `estado_publico` en `app/servicios/formato.py::registrar`; macro `barra_cupos` | `/salidas`, `/salidas/9` (suspendida) | `test_salidas_por_defecto_muestra_las_de_hoy`, `test_detalle_de_salida_suspendida_muestra_motivo_y_alerta` |
| **RN-09** Documento y teléfono con formato válido; un documento viaja una sola vez por salida | CHECK en `turista` y `reserva_pasajero`; `database/01_esquema.sql::uk_pasajero_documento`; el trigger `database/02_vistas_triggers.sql::trg_reserva_pasajero_bi` | `app/modelos/reserva.py::validar` (formatos) y `app/modelos/reserva.py::crear` (documento repetido en la salida, con la salida bloqueada) | `/salidas/10/reservar` (DNI de 3 dígitos → error junto al campo) | `test_check_rechaza_dato_invalido`, `test_datos_invalidos`, `test_un_documento_no_viaja_dos_veces_en_la_misma_salida`, `test_trigger_frena_documento_repetido_en_la_misma_salida` |
| **RN-10** Rotación justa de familias anfitrionas (y reasignar con motivo) | Tabla `hospedaje`; índice `database/01_esquema.sql::ix_hospedaje_familia_noche` | `app/modelos/hospedaje.py::elegir_familia`, `app/modelos/hospedaje.py::asignar`, `app/modelos/hospedaje.py::reasignar` | `/panel/hospedajes`, `/panel/hospedajes/transparencia` | `test_rotacion_justa_de_familias`, `test_la_familia_debe_tener_capacidad_para_el_grupo`, `test_reasignar_una_noche_con_motivo`, `test_transparencia_incluye_a_las_familias_sin_noches` |
| **RN-11** Alerta naranja o roja: marca las salidas afectadas, se suspenden en un paso y el turista reprograma o pide la devolución | `alerta_lago` + `ruta_parada` | `app/modelos/alerta.py::salidas_afectadas`, `app/modelos/alerta.py::suspender_afectadas` (una transacción), `app/modelos/reprogramacion.py::reprogramar`, `app/modelos/reprogramacion.py::pedir_devolucion` | `/panel/alertas`, `/alertas`, `/reservas/TV-GPJN/reprogramar` | `test_salida_afectada_por_alerta_queda_marcada`, `test_alerta_naranja_suspende_en_un_paso_las_salidas_afectadas`, `test_reprogramar_respeta_el_cupo_y_la_ruta`, `test_devolucion_cancela_y_queda_por_atender` |
| **RN-12** Abordaje con QR: de 60 min antes a 15 min después del zarpe, una vez por pasajero | `database/01_esquema.sql::uk_abordaje` | `app/modelos/abordaje.py::buscar`, `app/modelos/abordaje.py::registrar`; el QR lo arma `app/servicios/qr.py::url_de_abordaje` | `/panel/abordaje` (y la URL del QR: `/panel/abordaje/TV-33VR`) | `test_abordaje_en_la_ventana_y_una_sola_vez_por_pasajero`, `test_abordaje_fuera_de_horario`, `test_sin_pago_verificado_no_se_aborda`, `test_url_del_qr` |
| **RN-13** Reseña: solo si abordó, después del viaje, una por reserva y moderada | `database/01_esquema.sql::uk_resena_reserva` | `app/modelos/resena.py::crear`, `app/modelos/resena.py::moderar`, `app/modelos/resena.py::publicadas_de_ruta` | `/panel/resenas`, `/salidas/10` (opiniones) | `test_resena_solo_de_un_viaje_hecho_y_una_vez`, `test_resena_por_formulario` |
| **RN-14** Bitácora: inicios de sesión y cambios de estado (quién, cuándo, desde qué IP) | Tabla `bitacora` (`JSON_VALID`); trigger `database/02_vistas_triggers.sql::trg_salida_au` | `app/modelos/usuario.py::registrar_inicio_sesion`, `app/modelos/bitacora.py::anotar` (reservas, pagos, hospedajes, abordajes, catálogos y usuarios) | `/panel/bitacora` | `test_entrar_bien_redirige_al_panel_y_queda_en_la_bitacora`, `test_cambio_de_estado_de_salida_queda_en_la_bitacora`, `test_suspender_guarda_el_motivo_y_la_bitacora_sabe_quien_fue` |
| **RN-15** Todo en hora de Lima (−05:00) | `SET time_zone = '-05:00'` en cada script | `app/bd.py::COMANDO_INICIAL` (cada conexión), `app/registro.py::FormatoLima` (logs) | `/salud` | `test_cada_conexion_usa_hora_de_lima_y_modo_estricto`, `test_salud_responde_ok_con_la_hora_de_lima`, `test_registro_escribe_en_hora_de_lima`, `test_hoy_en_lima_no_depende_de_la_pc` |
| **S-11** Al zarpar, la reserva sin nadie a bordo pasa a «no se presentó» | — | `app/modelos/salida.py::marcar_zarpe` (`NOT EXISTS`) | `/panel/salidas/8/pasajeros` → «Marcar zarpe» | `test_zarpe_marca_no_show_solo_a_quien_no_subio_nadie`, `test_el_zarpe_se_marca_desde_60_minutos_antes` |

---

## 2. Requisitos no funcionales y del desafío

| Requisito | En el código | Pruebas o evidencia |
|---|---|---|
| **Bronce**: PK, FK, ≥ 5 filas por tabla, `SELECT *` de cada una | `database/01_esquema.sql`, `database/03_datos.sql`, `database/99_consultas_prueba.sql` | `test_hay_20_tablas_innodb_con_cotejamiento_espanol`, `test_cada_tabla_tiene_5_filas_o_mas` |
| **Plata**: cada pantalla lee de la base, sin datos fijos | `app/modelos/` + `app/rutas/publico.py` | `test_ninguna_plantilla_tiene_datos_del_negocio_escritos`, `test_cambiar_un_dato_en_la_base_cambia_la_pagina`, `test_sin_base_ninguna_pagina_publica_puede_mostrarse` |
| **Oro**: reservar hace INSERT, persiste y no se duplica | `app/modelos/reserva.py::crear` + POST → 303 → GET | `test_reservar_redirige_y_el_dato_sigue_al_recargar`, `test_tres_envios_del_mismo_formulario_crean_una_sola_reserva` |
| **Platino**: otro servidor cambiando solo el `.env` | `app/config.py` (todo `BD_*` sale del `.env`) | [evidencias/f8-platino-otro-servidor.txt](evidencias/f8-platino-otro-servidor.txt): 479 pruebas en el 2.º servidor |
| Prueba mutante: sin `FOR UPDATE` hay sobreventa | `tests/test_mutante.py` | `test_el_mutante_sin_for_update_vende_de_mas`, `test_con_for_update_y_sin_trigger_no_hay_sobreventa`, `test_el_trigger_frena_al_mutante` |
| Boleto con QR (HTML y PDF) y manifiesto de zarpe en PDF | `app/servicios/qr.py::png`, `app/servicios/pdf.py::boleto`, `app/servicios/pdf.py::manifiesto` | `test_boleto_html_y_pdf_con_qr`, `test_manifiesto_pdf` |
| Lista para WhatsApp con wa.me, sin API ni documentos | `app/servicios/whatsapp.py::texto_lista`, `app/servicios/whatsapp.py::enlace` | `test_lista_para_whatsapp_sin_documentos` |
| Datos personales ocultos sin acceso validado | `app/servicios/privacidad.py::documento`, `app/modelos/reserva.py::validar_acceso` | `test_otra_persona_ve_los_datos_ocultos`, `test_mi_reserva` |
| Transparencia comunitaria por familia | `app/modelos/hospedaje.py::transparencia` (vista `database/02_vistas_triggers.sql::v_ingresos_familia`) | `test_transparencia_incluye_a_las_familias_sin_noches`, `test_transparencia_imprimible` |
| Indicadores con GROUP BY, HAVING y funciones de ventana | `app/modelos/indicadores.py::ocupacion_por_ruta`, `app/modelos/indicadores.py::rutas_con_poca_ocupacion` | `test_indicadores_con_agregaciones_y_ventanas`, `test_indicadores_y_periodo_en_lista_blanca` |
| Turista en español e inglés | `app/servicios/textos.py::t`, `app/servicios/textos_en.py` | `test_cada_texto_del_turista_tiene_su_traduccion` |
| Mapa SVG propio con las comunidades y rutas de la base | `app/servicios/mapa.py::construir` | `test_proyeccion_de_las_esquinas`, `test_construir_mapa` |
| Ningún SQL en las rutas; SQL siempre con `%s` | `app/rutas/`, `app/modelos/` | `test_ninguna_ruta_tiene_sql`, `test_ningun_sql_lleva_texto_del_usuario` |
| Contraseñas con bcrypt; 5 intentos cada 15 minutos | `app/modelos/usuario.py::verificar_credenciales`, `app/seguridad.py::init_app` | `test_los_hash_de_los_usuarios_demo_son_bcrypt_validos`, `test_limite_de_5_intentos_fallidos` |
| CSRF en todo POST; sesión en todo el panel; permisos en la ruta **y** en el modelo | `app/seguridad.py::requiere_rol`, `app/modelos/__init__.py::exigir_rol` | `test_todo_post_sin_token_csrf_da_400`, `test_toda_pagina_del_panel_pide_sesion`, `test_matriz_de_permisos`, `test_el_modelo_tambien_niega_la_bitacora_al_operador` |
| Cookies HttpOnly y SameSite; `Secure` en producción | `app/config.py` | `test_la_cookie_de_sesion_es_httponly_y_samesite_lax`, `test_en_produccion_la_cookie_lleva_secure` |
| Cabeceras CSP, DENY y nosniff; sin estilos ni scripts en línea | `app/seguridad.py::agregar_cabeceras` | `test_cabeceras_de_seguridad_en_todas_las_paginas`, `test_las_plantillas_no_usan_estilos_ni_scripts_en_linea` |
| XSS: lo que escribe una persona sale escapado | Autoescape de Jinja | `test_comentario_con_script_se_muestra_escapado`, `test_titulo_de_alerta_con_html_se_muestra_escapado` |
| Páginas de error propias, sin trazas | `app/errores.py::registrar` | `test_pagina_404_propia_en_espanol`, `test_pagina_500_sin_trazas_y_queda_en_el_registro` |
| Si MySQL se apaga: la página y la consola dicen qué hacer | `app/diagnostico.py::explicar`, `app/errores.py::_sin_base`, `servidor.py::revisar` | `test_pagina_sin_base_dice_que_no_hay_conexion`, `test_servidor_no_arranca_sin_mysql_y_dice_que_hacer`, `test_los_comandos_sin_mysql_explican_que_hacer` |
| `/salud` en JSON, y 503 si la base no responde | `app/rutas/publico.py` | `test_salud_responde_ok_con_la_hora_de_lima`, `test_salud_da_503_si_la_base_no_responde` |
| Accesibilidad: etiquetas, errores junto al campo y arriba, idioma, teclado | `app/plantillas/macros.html` | `test_paginas_del_turista`, `test_paginas_del_panel`, `test_formulario_con_errores_los_muestra_junto_al_campo_y_arriba` |
| Ayuda paso a paso en cada pantalla del panel | `app/plantillas/panel/_macros.html` (`como_funciona`) | `test_cada_pagina_del_panel_explica_como_funciona`, `test_cada_rol_ve_su_trabajo_de_hoy` |
| Cada página pesa ≤ 100 KB (sin fotos) y sin N+1 | CSS propio, sin CDN; una consulta por lista | `test_paginas_del_turista_pesan_100_kb_o_menos`, `test_paginas_del_panel_pesan_100_kb_o_menos`, `test_consultas_por_pagina_no_crecen_con_los_datos` |
| EXPLAIN de las 3 consultas principales | `scripts/explicar_consultas.py` | `test_explain_de_las_3_consultas_principales` |
| 15 o más SELECT explicados, idénticos al código | `docs/consultas-explicadas.md` (20) | `test_hay_al_menos_15_consultas_con_sus_5_partes`, `test_cada_consulta_del_documento_es_identica_a_la_del_codigo` |
| ZIP de entrega sin `.env`, sin venv y sin contraseñas | `scripts/empaquetar.py`, `scripts/crear_bd.py` | `test_el_zip_no_lleva_env_ni_venv_ni_caches_ni_registros`, `test_el_proyecto_real_se_puede_empaquetar_sin_secretos`, `test_el_script_de_usuario_no_lleva_contrasena` |
| **F9** Recuperar la contraseña con un código por correo (D-111), en `/recuperar` | `app/modelos/cuenta.py::pedir_codigo`, `app/modelos/cuenta.py::restablecer_con_codigo`, `app/rutas/autenticacion.py::recuperar_codigo`, `app/servicios/correo.py::enviar` | `test_recuperar_la_contrasena_de_punta_a_punta`, `test_cinco_codigos_equivocados_y_hay_que_pedir_otro`, `test_misma_respuesta_si_no_hay_cuenta_o_no_tiene_correo`, `test_el_codigo_vence` |
| **F9** La sesión se cierra sola por inactividad y al cambiar la contraseña (D-110, D-112) | `app/seguridad.py::revisar_inactividad`, `app/seguridad.py::cargar_usuario`, `app/estaticos/js/sesion.js` | `test_la_sesion_se_cierra_sola_por_inactividad`, `test_al_cambiar_la_contrasena_se_cierran_las_otras_sesiones`, `test_con_sesion_abierta_ninguna_pagina_queda_en_la_cache` |
| **F9** Mi cuenta: cada rol con lo que hace y no hace, y una sola regla de contraseña (D-113), en `/panel/mi-cuenta` | `app/modelos/cuenta.py::error_contrasena`, `app/modelos/cuenta.py::cambiar_contrasena`, `app/plantillas/panel/_roles.html` | `test_mi_cuenta_muestra_los_datos_y_lo_que_hace_cada_rol`, `test_cambiar_mi_contrasena`, `test_contrasenas_que_no_sirven` |
| **F9** Activar o desactivar con un clic y la bitácora en CSV (D-114, D-115), en `/panel/bitacora/exportar` | `app/modelos/usuario.py::cambiar_activo`, `app/modelos/bitacora.py::exportar` | `test_desactivar_y_activar_con_un_clic`, `test_descargar_la_bitacora_en_csv`, `test_el_csv_no_deja_formulas_de_excel` |
| **F9** Una foto del lago como marca de agua en cada sección (D-109) | `app/servicios/imagenes.py::fondo_de_pagina`, `scripts/preparar_fondos.py` | `test_cada_seccion_tiene_su_foto_de_fondo_con_su_credito`, `test_las_fotos_de_fondo_son_livianas_y_solo_para_pantallas_anchas` |
| **F9** Respaldos de la base: crear, restaurar (la base queda idéntica), automático y reporte general (D-116 a D-118), en `/panel/respaldos` | `app/modelos/respaldo.py::crear`, `app/modelos/respaldo.py::restaurar`, `app/modelos/respaldo.py::crear_si_hace_falta`, `app/comandos.py::restaurar` | `test_un_respaldo_restaurado_deja_la_base_identica`, `test_no_se_restaura_un_archivo_que_no_es_un_respaldo_completo`, `test_el_respaldo_automatico_solo_cuando_hace_falta`, `test_reporte_general_en_excel_sin_documentos`, `test_los_respaldos_no_van_en_el_zip_de_entrega_ni_en_git` |

---

## 3. Un requisito de punta a punta: RN-02 «sin sobreventa»

Así se recorre una fila de la matriz, por ejemplo en el video o ante el docente:

1. **Requisito.** El enunciado pide que nunca se vendan más lugares de los que tiene la salida, aunque
   muchas personas reserven a la vez.
2. **Base de datos.** En `database/02_vistas_triggers.sql`, el trigger `trg_reserva_pasajero_bi`
   cuenta los ocupados antes de cada INSERT de un pasajero y lanza `SIGNAL` si ya no hay lugar.
   Es la red de seguridad: funciona aunque alguien inserte desde phpMyAdmin.
3. **Código.** En `app/modelos/reserva.py`, la función `crear` abre una transacción, bloquea la fila
   de la salida con `SELECT … FOR UPDATE` y recién entonces cuenta y guarda. Otra reserva de la misma
   salida espera en esa línea hasta el COMMIT.
4. **Pantalla.** En `/salidas/10/reservar` se reserva; si ya no hay lugar, el formulario responde
   «Solo quedan N lugares en esta salida» junto al campo.
5. **Pruebas.** `pytest tests/test_concurrencia.py -v`: 8 hilos pelean por el último lugar y se crea
   **una** reserva. `pytest -v -s tests/test_mutante.py`: si se quita el `FOR UPDATE` (y el
   trigger), los mismos 8 hilos venden **8** lugares. La prueba demuestra que la línea importa.

---

## 4. Trazabilidad en la operación: la bitácora

Además de la matriz (trazabilidad del **requisito**), la app guarda la trazabilidad de **cada acción**
en la tabla `bitacora` (RN-14). El admin la ve en `/panel/bitacora`.

| Qué queda registrado | Quién lo escribe | Ejemplo de acción |
|---|---|---|
| Inicio de sesión del personal | `app/modelos/usuario.py::registrar_inicio_sesion` | `inicio_sesion` |
| Cambio de estado de una salida (suspender, cancelar, zarpe) | El trigger `database/02_vistas_triggers.sql::trg_salida_au`, con el usuario y la IP que deja la app | `cambio_estado` |
| Reserva creada, reprogramada o cancelada; devolución pedida y atendida | `app/modelos/bitacora.py::anotar` | `creacion`, `reprogramacion`, `devolucion_solicitada` |
| Pago verificado o rechazado, cobro en el muelle | `app/modelos/bitacora.py::anotar` | `cambio_estado`, `cobro_muelle` |
| Abordaje, hospedaje reasignado, catálogos y usuarios | `app/modelos/bitacora.py::anotar` | `abordaje`, `reasignacion`, `edicion` |

Cada fila guarda **quién** (o vacío si fue un turista), **qué**, **sobre qué registro**, el **detalle**
en JSON y la **IP**, en hora de Lima. La app no tiene ninguna opción para editarla ni borrarla.

Y cada reserva tiene su propio rastro: el código `TV-XXXX` es el mismo desde que se crea hasta que se
aborda (aunque se reprograme), y el boleto lleva un QR con ese código.

---

## 5. Cómo se verifica esta matriz

```powershell
pytest -v tests/test_trazabilidad.py
```

| Prueba | Qué revisa |
|---|---|
| `test_cada_regla_de_negocio_tiene_su_fila` | RN-01 a RN-15 tienen su fila en la tabla 1. |
| `test_cada_prueba_citada_existe` | Cada `test_…` citado existe en `tests/`. |
| `test_cada_archivo_y_funcion_citados_existen` | Cada `archivo::nombre` existe: la función o clase en el `.py`, o el trigger, vista o índice en el `.sql`. |
| `test_cada_pantalla_citada_existe` | Cada página citada (como `/panel/bitacora`) existe en la app. |
