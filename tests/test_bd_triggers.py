"""Triggers de respaldo: sobreventa, documento repetido, reglas de salida y bitácora."""

import json
import secrets

from tests.conftest import ERROR_SIGNAL, falla_con

ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MANANA = "CURDATE() + INTERVAL 1 DAY"
EN_20_DIAS = "CURDATE() + INTERVAL 20 DAY"


def crear_reserva(cur, salida_id, estado="confirmada", vence_en_sql="NULL"):
    """Inserta una reserva de prueba (titular: turista 1) y devuelve su id."""
    codigo = "TV-" + "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(4))
    cur.execute(
        "INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido, "
        f"token_envio, vence_en) VALUES (%s, %s, 1, %s, 'yape', %s, {vence_en_sql})",
        (codigo, salida_id, estado, secrets.token_hex(16)),
    )
    return cur.lastrowid


# Un pasajero adulto nacional con DNI; los datos van como parámetros %s.
SQL_PASAJERO = (
    "INSERT INTO reserva_pasajero (reserva_id, tipo_pasajero_id, nombres, apellidos, "
    "tipo_documento, numero_documento, nacionalidad, precio_aplicado) "
    "VALUES (%s, 1, 'Pasajero', 'De Prueba', 'DNI', %s, 'PE', 30)"
)


def libres(cur, salida_id):
    cur.execute("SELECT libres FROM v_disponibilidad_salida WHERE salida_id = %s", (salida_id,))
    return cur.fetchone()["libres"]


# --- trg_reserva_pasajero_bi -------------------------------------------------

def test_trigger_frena_la_sobreventa(cur):
    assert libres(cur, 8) == 3                        # salida 8: 15 de 18 ocupados
    reserva_id = crear_reserva(cur, 8)
    for dni in ("90000001", "90000002", "90000003"):
        cur.execute(SQL_PASAJERO, (reserva_id, dni))    # los 3 últimos cupos: entran
    assert libres(cur, 8) == 0
    codigo, mensaje = falla_con(cur, SQL_PASAJERO, (reserva_id, "90000004"))
    assert codigo == ERROR_SIGNAL
    assert "Sobreventa" in mensaje


def test_reserva_vencida_no_ocupa_lugar_ni_la_frena_el_trigger(cur):
    # RN-05: una pendiente_pago con vence_en en el pasado no cuenta como ocupado.
    llena = crear_reserva(cur, 8)
    for dni in ("90000001", "90000002", "90000003"):
        cur.execute(SQL_PASAJERO, (llena, dni))
    vencida = crear_reserva(cur, 8, "pendiente_pago", "NOW() - INTERVAL 1 MINUTE")
    cur.execute(SQL_PASAJERO, (vencida, "90000009"))    # no da error
    assert libres(cur, 8) == 0                        # y no cambia los libres


def test_trigger_frena_documento_repetido_en_la_misma_salida(cur):
    # 48761230 ya viaja en la salida 10 (reserva 17, pendiente vigente).
    reserva_id = crear_reserva(cur, 10)
    codigo, mensaje = falla_con(cur, SQL_PASAJERO, (reserva_id, "48761230"))
    assert codigo == ERROR_SIGNAL
    assert "Documento repetido" in mensaje


def test_documento_de_una_reserva_vencida_si_puede_volver_a_reservar(cur):
    # 45678123 estaba en la reserva 18, que ya venció: puede reservar otra vez.
    reserva_id = crear_reserva(cur, 10)
    cur.execute(SQL_PASAJERO, (reserva_id, "45678123"))
    assert cur.rowcount == 1


# --- trg_salida_bi / trg_salida_bu (procedimiento pr_validar_salida) ---------

def sql_salida(embarcacion_id, capitan_id, zarpe, retorno, cupo, estado="programada"):
    return (
        "INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, fecha_hora_zarpe, "
        f"fecha_hora_retorno, cupo, estado, creada_por) VALUES (1, {embarcacion_id}, {capitan_id}, "
        f"{zarpe}, {retorno}, {cupo}, '{estado}', 2)"
    )


def test_cupo_no_puede_pasar_la_capacidad_de_la_lancha(cur):
    sql = sql_salida(3, 5, f"{EN_20_DIAS} + INTERVAL 8 HOUR", f"{EN_20_DIAS} + INTERVAL 11 HOUR", 25)
    codigo, mensaje = falla_con(cur, sql)              # Wiñay Inti: capacidad 20
    assert codigo == ERROR_SIGNAL
    assert "capacidad" in mensaje


def test_el_capitan_debe_tener_rol_capitan(cur):
    sql = sql_salida(3, 3, f"{EN_20_DIAS} + INTERVAL 8 HOUR", f"{EN_20_DIAS} + INTERVAL 11 HOUR", 10)
    codigo, mensaje = falla_con(cur, sql)              # el usuario 3 es guía
    assert codigo == ERROR_SIGNAL
    assert "capit" in mensaje


def test_el_capitan_debe_tener_licencia(cur):
    cur.execute("UPDATE usuario SET licencia_navegacion = NULL WHERE id = 5")
    sql = sql_salida(3, 5, f"{EN_20_DIAS} + INTERVAL 8 HOUR", f"{EN_20_DIAS} + INTERVAL 11 HOUR", 10)
    codigo, mensaje = falla_con(cur, sql)
    assert codigo == ERROR_SIGNAL
    assert "licencia" in mensaje


def test_la_misma_lancha_no_puede_tener_salidas_que_se_cruzan(cur):
    # La lancha 1 ya sale mañana de 07:00 a 16:30 (salida 10).
    sql = sql_salida(1, 6, f"{MANANA} + INTERVAL 10 HOUR", f"{MANANA} + INTERVAL 12 HOUR", 10)
    codigo, mensaje = falla_con(cur, sql)
    assert codigo == ERROR_SIGNAL
    assert "Cruce" in mensaje


def test_una_salida_que_empieza_justo_cuando_otra_termina_no_se_cruza(cur):
    # La salida 10 vuelve mañana a las 16:30; otra puede zarpar a las 16:30 en punto.
    cur.execute(sql_salida(1, 6, f"{MANANA} + INTERVAL 990 MINUTE", f"{MANANA} + INTERVAL 18 HOUR", 10))
    assert cur.rowcount == 1


def test_las_salidas_canceladas_no_cuentan_para_el_cruce(cur):
    # Ayer la lancha 2 tenía la salida 5, pero está cancelada.
    sql = sql_salida(2, 6, "CURDATE() - INTERVAL 1 DAY + INTERVAL 8 HOUR",
                     "CURDATE() - INTERVAL 1 DAY + INTERVAL 10 HOUR", 10)
    cur.execute(sql)
    assert cur.rowcount == 1


def test_una_salida_cancelada_nueva_no_se_revisa_por_cruce(cur):
    sql = sql_salida(1, 6, f"{MANANA} + INTERVAL 10 HOUR", f"{MANANA} + INTERVAL 12 HOUR", 10,
                     estado="cancelada")
    cur.execute(sql)
    assert cur.rowcount == 1


def test_reactivar_una_salida_suspendida_que_se_cruza_falla(cur):
    # La salida 9 (suspendida) usa la lancha 2 hasta pasado mañana a las 16:00,
    # y la salida 12 ya ocupa esa lancha desde pasado mañana a las 07:00.
    codigo, mensaje = falla_con(cur, "UPDATE salida SET estado = 'programada' WHERE id = 9")
    assert codigo == ERROR_SIGNAL
    assert "Cruce" in mensaje


def test_update_que_no_toca_la_regla_no_se_revisa(cur):
    # Si la lancha 1 pasa a capacidad 10, la salida 6 (cupo 25) queda "inválida",
    # pero igual se le puede escribir una nota; cambiar su cupo sí se revisa.
    cur.execute("UPDATE embarcacion SET capacidad_maxima = 10 WHERE id = 1")
    cur.execute("UPDATE salida SET motivo_estado = 'Nota del operador' WHERE id = 6")
    assert cur.rowcount == 1
    codigo, mensaje = falla_con(cur, "UPDATE salida SET cupo = 24 WHERE id = 6")
    assert codigo == ERROR_SIGNAL
    assert "capacidad" in mensaje


# --- trg_salida_au (bitácora) ------------------------------------------------

def test_cambio_de_estado_de_salida_queda_en_la_bitacora(cur):
    cur.execute("SET @app_usuario_id = 2, @app_ip = '127.0.0.1'")
    cur.execute("SELECT COALESCE(MAX(id), 0) AS ultimo FROM bitacora")
    ultimo = cur.fetchone()["ultimo"]

    cur.execute("UPDATE salida SET estado = 'embarcando' WHERE id = 11")
    cur.execute("UPDATE salida SET motivo_estado = 'Sin cambio de estado' WHERE id = 11")

    cur.execute("SELECT * FROM bitacora WHERE id > %s", (ultimo,))
    nuevas = cur.fetchall()
    assert len(nuevas) == 1                           # el 2.º UPDATE no cambió el estado
    fila = nuevas[0]
    assert (fila["usuario_id"], fila["accion"], fila["tabla_afectada"], fila["registro_id"]) == (
        2, "cambio_estado", "salida", 11)
    assert fila["ip"] == "127.0.0.1"
    detalle = json.loads(fila["detalle"])
    assert (detalle["de"], detalle["a"]) == ("programada", "embarcando")
