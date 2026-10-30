"""Restricciones de la base (CHECK, ENUM estricto, FK y UNIQUE) probadas con INSERT/UPDATE/DELETE directos.

Cada caso es una sentencia que la base DEBE rechazar. Si MariaDB la aceptara,
la prueba falla. Al final de cada prueba se hace ROLLBACK (ver conftest.py).
"""

import pytest

from tests.conftest import (
    ERROR_CHECK,
    ERROR_DATO_INVALIDO,
    ERROR_DUPLICADO,
    ERROR_FK_HIJO,
    ERROR_FK_PADRE,
    falla_con,
)

TOKEN_NUEVO = "0123456789abcdef0123456789abcdef"
FUTURO = "CURDATE() + INTERVAL 20 DAY"

CASOS_CHECK = [
    ("familia con capacidad 11",
     "INSERT INTO familia_anfitriona (comunidad_id, nombre_familia, responsable, capacidad_personas) "
     "VALUES (3, 'Familia Prueba', 'Responsable Prueba', 11)"),
    ("lancha con capacidad 41",
     "INSERT INTO embarcacion (nombre, matricula, capacidad_maxima, tipo) "
     "VALUES ('Prueba', 'PRB-0001', 41, 'lancha')"),
    ("salida que vuelve antes de zarpar",
     f"INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, fecha_hora_zarpe, fecha_hora_retorno, "
     f"cupo, creada_por) VALUES (1, 4, 5, {FUTURO} + INTERVAL 10 HOUR, {FUTURO} + INTERVAL 9 HOUR, 10, 2)"),
    ("salida con cupo 0",
     f"INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, fecha_hora_zarpe, fecha_hora_retorno, "
     f"cupo, creada_por) VALUES (1, 4, 5, {FUTURO} + INTERVAL 8 HOUR, {FUTURO} + INTERVAL 11 HOUR, 0, 2)"),
    ("turista sin teléfono ni correo",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad) "
     "VALUES ('Ana', 'Prueba', 'DNI', '12345678', 'PE')"),
    ("DNI de 7 dígitos",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad, telefono) "
     "VALUES ('Ana', 'Prueba', 'DNI', '1234567', 'PE', '900000999')"),
    ("CE de 8 dígitos",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad, telefono) "
     "VALUES ('Ana', 'Prueba', 'CE', '12345678', 'AR', '900000999')"),
    ("pasaporte en minúsculas",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad, correo) "
     "VALUES ('Ana', 'Prueba', 'PASAPORTE', 'ab123456', 'FR', 'ana@correo.example')"),
    ("nacionalidad en minúsculas",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad, telefono) "
     "VALUES ('Ana', 'Prueba', 'DNI', '12345678', 'pe', '900000999')"),
    ("teléfono que no es celular peruano ni +código",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad, telefono) "
     "VALUES ('Ana', 'Prueba', 'DNI', '12345678', 'PE', '812345678')"),
    ("código de reserva con la letra O",
     f"INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     f"VALUES ('TV-AB2O', 13, 1, 'confirmada', 'muelle', '{TOKEN_NUEVO}')"),
    ("código de reserva en minúsculas",
     f"INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     f"VALUES ('TV-abcd', 13, 1, 'confirmada', 'muelle', '{TOKEN_NUEVO}')"),
    ("pendiente_pago sin vence_en",
     f"INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     f"VALUES ('TV-ZZZZ', 13, 1, 'pendiente_pago', 'yape', '{TOKEN_NUEVO}')"),
    ("token que no es hexadecimal",
     "INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     "VALUES ('TV-ZZZZ', 13, 1, 'confirmada', 'muelle', 'XYZ456789abcdef0123456789abcdef0')"),
    ("pasajero con precio 0",
     "INSERT INTO reserva_pasajero (reserva_id, tipo_pasajero_id, nombres, apellidos, tipo_documento, "
     "numero_documento, nacionalidad, precio_aplicado) VALUES (8, 1, 'A', 'B', 'DNI', '11112222', 'PE', 0)"),
    ("pago de 0 soles",
     "INSERT INTO pago (reserva_id, metodo, monto, numero_operacion) VALUES (19, 'yape', 0, '99990001')"),
    ("Yape sin número de operación",
     "INSERT INTO pago (reserva_id, metodo, monto) VALUES (19, 'yape', 10)"),
    ("temporada que termina antes de empezar",
     "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, recargo_porcentaje) "
     "VALUES ('Prueba', '2030-02-10', '2030-02-01', 5)"),
    ("recargo de 101 %",
     "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, recargo_porcentaje) "
     "VALUES ('Prueba', '2030-02-01', '2030-02-10', 101)"),
    ("tarifa de 0 soles",
     "INSERT INTO tarifa (ruta_id, tipo_pasajero_id, precio_base, vigente_desde) VALUES (1, 1, 0, '2030-01-01')"),
    ("tarifa vigente hasta antes de su inicio",
     "INSERT INTO tarifa (ruta_id, tipo_pasajero_id, precio_base, vigente_desde, vigente_hasta) "
     "VALUES (1, 1, 10, '2030-01-10', '2030-01-01')"),
    ("reseña con 6 estrellas",
     "INSERT INTO resena (reserva_id, puntuacion, idioma) VALUES (6, 6, 'es')"),
    ("bitácora con JSON inválido",
     "INSERT INTO bitacora (accion, detalle) VALUES ('prueba', '{esto no es json')"),
    ("rol que no existe en el enunciado",
     "INSERT INTO rol (codigo, nombre) VALUES ('turista', 'Turista')"),
    ("slug con mayúsculas",
     "INSERT INTO comunidad (nombre, slug, distrito, provincia, idioma_originario, senal) "
     "VALUES ('Prueba', 'Prueba-X', 'Puno', 'Puno', 'aimara', 'buena')"),
    ("hospedaje para 0 personas",
     "INSERT INTO hospedaje (reserva_id, familia_id, fecha_noche, personas, monto_familia) "
     "VALUES (14, 2, CURDATE() + INTERVAL 9 DAY, 0, 0)"),
    ("alerta que termina antes de empezar",
     "INSERT INTO alerta_lago (tipo, nivel, titulo, fuente, vigente_desde, vigente_hasta, registrada_por) "
     "VALUES ('oleaje', 'rojo', 'Prueba', 'SENAMHI', NOW(), NOW() - INTERVAL 1 HOUR, 2)"),
    ("edad máxima menor que la mínima",
     "UPDATE tipo_pasajero SET edad_maxima = 2 WHERE codigo = 'nino'"),
    ("ruta de 0 horas",
     "UPDATE ruta SET duracion_horas = 0 WHERE id = 1"),
    ("parada en el orden 0",
     "INSERT INTO ruta_parada (ruta_id, comunidad_id, orden, minutos_estadia) VALUES (1, 2, 0, 30)"),
]


@pytest.mark.parametrize("descripcion, sql", CASOS_CHECK, ids=[c[0] for c in CASOS_CHECK])
def test_check_rechaza_dato_invalido(cur, descripcion, sql):
    codigo, mensaje = falla_con(cur, sql)
    assert codigo == ERROR_CHECK, mensaje


def test_modo_estricto_rechaza_un_enum_invalido(cur):
    # Sin STRICT_TRANS_TABLES, MariaDB guardaría '' y solo daría un aviso.
    codigo, _ = falla_con(cur, "UPDATE reserva SET estado = 'perdida' WHERE id = 1")
    assert codigo == ERROR_DATO_INVALIDO


CASOS_FK = [
    ("salida de una ruta que no existe",
     f"INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, fecha_hora_zarpe, fecha_hora_retorno, "
     f"cupo, creada_por) VALUES (999, 4, 5, {FUTURO} + INTERVAL 8 HOUR, {FUTURO} + INTERVAL 11 HOUR, 10, 2)",
     ERROR_FK_HIJO),
    ("reserva de un turista que no existe",
     f"INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     f"VALUES ('TV-ZZZZ', 13, 999, 'confirmada', 'muelle', '{TOKEN_NUEVO}')", ERROR_FK_HIJO),
    ("pago de una reserva que no existe",
     "INSERT INTO pago (reserva_id, metodo, monto, numero_operacion) VALUES (999, 'yape', 10, '99990002')",
     ERROR_FK_HIJO),
    ("borrar una ruta que tiene salidas", "DELETE FROM ruta WHERE id = 1", ERROR_FK_PADRE),
    ("borrar una reserva que tiene pagos", "DELETE FROM reserva WHERE id = 1", ERROR_FK_PADRE),
    ("borrar una comunidad que tiene familias", "DELETE FROM comunidad WHERE id = 3", ERROR_FK_PADRE),
    ("borrar un capitán que tiene salidas", "DELETE FROM usuario WHERE id = 5", ERROR_FK_PADRE),
    ("borrar una lancha que tiene salidas", "DELETE FROM embarcacion WHERE id = 1", ERROR_FK_PADRE),
    ("borrar una familia con hospedajes", "DELETE FROM familia_anfitriona WHERE id = 1", ERROR_FK_PADRE),
]


@pytest.mark.parametrize("descripcion, sql, esperado", CASOS_FK, ids=[c[0] for c in CASOS_FK])
def test_clave_foranea(cur, descripcion, sql, esperado):
    codigo, mensaje = falla_con(cur, sql)
    assert codigo == esperado, mensaje


CASOS_UNIQUE = [
    ("token_envio repetido (RN-03)",
     "INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     "VALUES ('TV-ZZZZ', 13, 1, 'confirmada', 'muelle', '2e9f8a1986e9b5fc7fe3759157bea41a')"),
    ("código de reserva repetido",
     f"INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
     f"VALUES ('TV-RA57', 13, 1, 'confirmada', 'muelle', '{TOKEN_NUEVO}')"),
    ("mismo número de operación Yape",
     "INSERT INTO pago (reserva_id, metodo, monto, numero_operacion) VALUES (19, 'yape', 10, '10450001')"),
    ("segunda reseña de la misma reserva",
     "INSERT INTO resena (reserva_id, puntuacion, idioma) VALUES (1, 5, 'es')"),
    ("misma reserva y misma noche de hospedaje",
     "INSERT INTO hospedaje (reserva_id, familia_id, fecha_noche, personas, monto_familia) "
     "VALUES (4, 3, CURDATE() - INTERVAL 6 DAY, 3, 120)"),
    ("mismo pasajero abordando dos veces la misma salida",
     "INSERT INTO abordaje (reserva_pasajero_id, salida_id, registrado_por, metodo) "
     "SELECT reserva_pasajero_id, salida_id, 3, 'qr' FROM (SELECT * FROM abordaje LIMIT 1) a"),
    ("turista con un documento ya registrado",
     "INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento, nacionalidad, telefono) "
     "VALUES ('Otra', 'Persona', 'DNI', '41020304', 'PE', '900000999')"),
    ("mismo documento dos veces en la misma reserva",
     "INSERT INTO reserva_pasajero (reserva_id, tipo_pasajero_id, nombres, apellidos, tipo_documento, "
     "numero_documento, nacionalidad, precio_aplicado) VALUES (8, 1, 'A', 'B', 'DNI', '46301122', 'PE', 80)"),
    ("dos paradas con el mismo orden",
     "INSERT INTO ruta_parada (ruta_id, comunidad_id, orden, minutos_estadia) VALUES (1, 2, 1, 30)"),
    ("la misma comunidad dos veces en una ruta",
     "INSERT INTO ruta_parada (ruta_id, comunidad_id, orden, minutos_estadia) VALUES (2, 1, 5, 30)"),
    ("nombre de usuario repetido",
     "INSERT INTO usuario (rol_id, nombre_usuario, nombre_completo, hash_contrasena) "
     "VALUES (2, 'admin', 'Otro admin', 'x')"),
    ("matrícula repetida",
     "INSERT INTO embarcacion (nombre, matricula, capacidad_maxima, tipo) "
     "VALUES ('Otra', 'PUN-LT-0101', 10, 'lancha')"),
    ("tarifa repetida para la misma ruta, tipo y fecha",
     "INSERT INTO tarifa (ruta_id, tipo_pasajero_id, precio_base, vigente_desde) VALUES (1, 1, 99, '2026-01-01')"),
]


@pytest.mark.parametrize("descripcion, sql", CASOS_UNIQUE, ids=[c[0] for c in CASOS_UNIQUE])
def test_unique_rechaza_duplicado(cur, descripcion, sql):
    codigo, mensaje = falla_con(cur, sql)
    assert codigo == ERROR_DUPLICADO, mensaje


def test_varios_pagos_en_efectivo_sin_numero_no_chocan(cur):
    # En un UNIQUE, NULL no es igual a NULL: dos pagos en efectivo sin número son válidos.
    for _ in range(2):
        cur.execute(
            "INSERT INTO pago (reserva_id, metodo, monto, estado) VALUES (13, 'efectivo_muelle', 10, 'reportado')"
        )
    cur.execute("SELECT COUNT(*) AS n FROM pago WHERE reserva_id = 13 AND numero_operacion IS NULL")
    assert cur.fetchone()["n"] == 2


def test_borrar_ruta_borra_sus_paradas_en_cascada(cur):
    cur.execute(
        "INSERT INTO ruta (codigo, nombre, duracion_horas, muelle_salida) "
        "VALUES ('PRB-01', 'Ruta de prueba', 2.0, 'Muelle de Puno')"
    )
    ruta_id = cur.lastrowid
    cur.execute(
        "INSERT INTO ruta_parada (ruta_id, comunidad_id, orden, minutos_estadia) "
        "VALUES (%s, 1, 1, 30), (%s, 2, 2, 60)", (ruta_id, ruta_id)
    )
    cur.execute("DELETE FROM ruta WHERE id = %s", (ruta_id,))
    cur.execute("SELECT COUNT(*) AS n FROM ruta_parada WHERE ruta_id = %s", (ruta_id,))
    assert cur.fetchone()["n"] == 0


def _reserva_de_prueba(cur, estado):
    cur.execute(
        "INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, token_envio) "
        "VALUES ('TV-ZZZZ', 13, 1, %s, 'muelle', %s)", (estado, TOKEN_NUEVO)
    )
    reserva_id = cur.lastrowid
    cur.execute(
        "INSERT INTO reserva_pasajero (reserva_id, tipo_pasajero_id, nombres, apellidos, tipo_documento, "
        "numero_documento, nacionalidad, precio_aplicado) VALUES "
        "(%s, 1, 'Ana', 'Prueba', 'DNI', '11112222', 'PE', 90), "
        "(%s, 1, 'Luis', 'Prueba', 'DNI', '11112223', 'PE', 90)", (reserva_id, reserva_id)
    )
    return reserva_id


def test_borrar_reserva_borra_sus_pasajeros_en_cascada(cur):
    reserva_id = _reserva_de_prueba(cur, "cancelada")
    cur.execute("DELETE FROM reserva WHERE id = %s", (reserva_id,))
    cur.execute("SELECT COUNT(*) AS n FROM reserva_pasajero WHERE reserva_id = %s", (reserva_id,))
    assert cur.fetchone()["n"] == 0


def test_abordaje_impide_borrar_la_reserva(cur):
    # La cascada a reserva_pasajero se frena si un pasajero ya abordó (RESTRICT en abordaje).
    reserva_id = _reserva_de_prueba(cur, "confirmada")
    cur.execute(
        "INSERT INTO abordaje (reserva_pasajero_id, salida_id, registrado_por, metodo) "
        "SELECT id, 13, 5, 'manual' FROM reserva_pasajero WHERE reserva_id = %s LIMIT 1", (reserva_id,)
    )
    codigo, _ = falla_con(cur, "DELETE FROM reserva WHERE id = %s", (reserva_id,))
    assert codigo == ERROR_FK_PADRE
