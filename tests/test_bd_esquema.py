"""Nivel Bronce: el esquema existe, tiene datos y la semilla es coherente."""

import bcrypt
import pytest

from app import bd


def test_hay_20_tablas_innodb_con_cotejamiento_espanol(cur):
    # Devuelve motor y cotejamiento de cada tabla base de la base de pruebas.
    cur.execute(
        "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'"
    )
    tablas = cur.fetchall()
    assert {t["TABLE_NAME"] for t in tablas} == set(bd.TABLAS)
    assert {t["ENGINE"] for t in tablas} == {"InnoDB"}
    assert {t["TABLE_COLLATION"] for t in tablas} == {"utf8mb4_spanish_ci"}


@pytest.mark.parametrize("tabla", bd.TABLAS)
def test_cada_tabla_tiene_5_filas_o_mas(con, tabla):
    conteo = dict(bd.contar_filas(con))
    # rol es la excepción: el enunciado fija exactamente 4 códigos de rol.
    minimo = 4 if tabla == "rol" else 5
    assert conteo[tabla] >= minimo


def test_vistas_procedimiento_y_triggers_existen(cur):
    cur.execute("SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE()")
    assert {f["TABLE_NAME"] for f in cur.fetchall()} == {
        "v_disponibilidad_salida", "v_ingresos_familia"}
    cur.execute(
        "SELECT TRIGGER_NAME, SQL_MODE FROM information_schema.TRIGGERS "
        "WHERE TRIGGER_SCHEMA = DATABASE()"
    )
    triggers = cur.fetchall()
    assert {t["TRIGGER_NAME"] for t in triggers} == {
        "trg_reserva_pasajero_bi", "trg_salida_bi", "trg_salida_bu", "trg_salida_au"}
    # Los triggers recuerdan el sql_mode de su creación: deben ser estrictos.
    assert all("STRICT_TRANS_TABLES" in t["SQL_MODE"] for t in triggers)
    cur.execute("SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                "WHERE ROUTINE_SCHEMA = DATABASE()")
    assert [f["ROUTINE_NAME"] for f in cur.fetchall()] == ["pr_validar_salida"]


def test_cada_conexion_usa_hora_de_lima_y_modo_estricto(cur):
    cur.execute("SELECT @@session.time_zone AS zona, @@session.sql_mode AS modo")
    fila = cur.fetchone()
    assert fila["zona"] == "-05:00"
    assert "STRICT_TRANS_TABLES" in fila["modo"]


def test_hay_salidas_hoy_manana_y_pasado_manana(cur):
    # Devuelve los días distintos (contados desde hoy) que tienen salidas.
    cur.execute(
        "SELECT DISTINCT DATEDIFF(DATE(fecha_hora_zarpe), CURDATE()) AS dia FROM salida "
        "WHERE fecha_hora_zarpe >= CURDATE() AND fecha_hora_zarpe < CURDATE() + INTERVAL 3 DAY"
    )
    assert {f["dia"] for f in cur.fetchall()} == {0, 1, 2}


def test_hay_reservas_en_los_7_estados(cur):
    cur.execute("SELECT DISTINCT estado FROM reserva")
    assert {f["estado"] for f in cur.fetchall()} == {
        "pendiente_pago", "confirmada", "pagada", "abordada", "cancelada", "vencida", "no_show"}


def test_total_de_cada_reserva_es_la_suma_de_sus_pasajeros(cur):
    # Devuelve las reservas cuyo total NO coincide con la suma de precio_aplicado (deben ser 0).
    cur.execute(
        "SELECT r.id FROM reserva r JOIN reserva_pasajero rp ON rp.reserva_id = r.id "
        "GROUP BY r.id, r.total HAVING r.total <> SUM(rp.precio_aplicado)"
    )
    assert cur.fetchall() == ()


def test_reservas_pagadas_tienen_pagos_verificados_que_cubren_el_total(cur):
    # Devuelve las reservas pagadas/abordadas con pagos verificados menores al total (deben ser 0).
    cur.execute(
        "SELECT r.id FROM reserva r "
        "LEFT JOIN pago p ON p.reserva_id = r.id AND p.estado = 'verificado' "
        "WHERE r.estado IN ('pagada','abordada') "
        "GROUP BY r.id, r.total HAVING COALESCE(SUM(p.monto), 0) < r.total"
    )
    assert cur.fetchall() == ()


def test_precio_aplicado_sigue_la_tarifa_vigente(cur):
    # Reserva 2: Uros+Taquile para 2 adultos nacionales, tarifa 2026 de S/ 80.00 (sin temporada).
    cur.execute("SELECT precio_aplicado FROM reserva_pasajero WHERE reserva_id = 2")
    precios = {f["precio_aplicado"] for f in cur.fetchall()}
    cur.execute(
        "SELECT COUNT(*) AS n FROM temporada t JOIN salida s ON s.id = 2 "
        "WHERE DATE(s.fecha_hora_zarpe) BETWEEN t.fecha_inicio AND t.fecha_fin"
    )
    if cur.fetchone()["n"] == 0:
        assert {str(p) for p in precios} == {"80.00"}


def test_los_hash_de_los_usuarios_demo_son_bcrypt_validos(cur):
    cur.execute("SELECT nombre_usuario, hash_contrasena FROM usuario ORDER BY id")
    usuarios = {f["nombre_usuario"]: f["hash_contrasena"] for f in cur.fetchall()}
    assert all(h.startswith("$2b$12$") for h in usuarios.values())
    assert bcrypt.checkpw(b"Admin-Titicaca26", usuarios["admin"].encode())
    assert bcrypt.checkpw(b"Capitan-Titicaca26", usuarios["capitan.fermin"].encode())
    assert not bcrypt.checkpw(b"otra-clave", usuarios["admin"].encode())


def test_vista_disponibilidad_cuenta_solo_lo_que_ocupa_lugar(cur):
    cur.execute(
        "SELECT salida_id, cupo, ocupados, libres, estado_publico FROM v_disponibilidad_salida"
    )
    vista = {f["salida_id"]: f for f in cur.fetchall()}
    # Salida 10: 2 (pendiente vigente) + 2 (pago reportado); la pendiente vencida (3) NO cuenta.
    assert vista[10]["ocupados"] == 4
    assert vista[10]["libres"] == 21
    assert vista[10]["estado_publico"] == "disponible"
    assert vista[8]["libres"] == 3            # 15 de 18
    assert vista[9]["estado_publico"] == "suspendida"
    assert vista[5]["estado_publico"] == "cancelada"
    assert vista[2]["estado_publico"] == "zarpo"
    assert all(f["libres"] >= 0 for f in vista.values())


def test_vista_ingresos_familia_solo_suma_lo_cumplido(cur):
    cur.execute(
        "SELECT noches, monto FROM v_ingresos_familia "
        "WHERE familia_id = 1 AND mes = DATE_FORMAT(CURDATE() - INTERVAL 6 DAY, '%Y-%m')"
    )
    fila = cur.fetchone()
    assert fila["noches"] == 1
    assert str(fila["monto"]) == "120.00"
