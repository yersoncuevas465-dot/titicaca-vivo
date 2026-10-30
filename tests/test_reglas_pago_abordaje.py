"""Pagos (RN-06, D-09, RN-10 al pagar) y abordaje (RN-12) en el modelo (F5)."""

import pytest

from app.modelos import ErrorValidacion, EstadoNoPermite, PermisoDenegado, abordaje, pago
from app.modelos import reserva as modelo_reserva
from app.modelos import salida as modelo_salida
from tests.conftest import actor, consultar_valor, ejecutar_y_confirmar, reservar_en

ADMIN, OPERADOR, ELENA, MARCO, TEODORO = 1, 2, 3, 4, 5


def valor_reserva(app, codigo, columna):
    # Solo nombres de columna escritos en esta prueba (no vienen de un usuario).
    return consultar_valor(app, f"SELECT {columna} FROM reserva WHERE codigo = %s", (codigo,))  # noqa: S608


def reportar(app, codigo, monto=None, numero="OPE-PRUEBA"):
    """El turista reporta un pago (F4). Devuelve el id del pago."""
    total = valor_reserva(app, codigo, "total")
    with app.app_context():
        modelo_reserva.reportar_pago(codigo, "yape", monto or total, f"{numero}-{codigo[3:]}")
    return consultar_valor(app, "SELECT MAX(p.id) FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                "WHERE r.codigo = %s", (codigo,))


# --- Verificar y rechazar (RN-06) --------------------------------------------------------------------

def test_verificar_el_total_deja_la_reserva_pagada_y_asigna_la_familia(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=3, dias=25)                 # Uros, Amantaní (noche) y Taquile
    codigo = reservar_en(app, salida_id, acompanantes=1, metodo="yape")
    assert consultar_valor(app, "SELECT COUNT(*) FROM hospedaje h JOIN reserva r ON r.id = h.reserva_id "
                                "WHERE r.codigo = %s", (codigo,)) == 0     # D-52: todavía no
    pago_id = reportar(app, codigo)
    with app.app_context():
        resultado = pago.verificar(actor(OPERADOR), pago_id, ip="203.0.113.5")
    assert resultado["pagada"] and resultado["familia"]
    assert valor_reserva(app, codigo, "estado") == "pagada"
    assert consultar_valor(app, "SELECT CONCAT(estado, ' ', verificado_por) FROM pago WHERE id = %s",
                           (pago_id,)) == "verificado 2"
    assert consultar_valor(app, "SELECT COUNT(*) FROM hospedaje h JOIN reserva r ON r.id = h.reserva_id "
                                "WHERE r.codigo = %s AND h.estado = 'asignado'", (codigo,)) == 1


def test_un_pago_parcial_no_alcanza(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), acompanantes=1, metodo="yape")
    total = valor_reserva(app, codigo, "total")
    pago_id = reportar(app, codigo, monto=total / 2)
    with app.app_context():
        resultado = pago.verificar(actor(OPERADOR), pago_id)
    assert not resultado["pagada"] and resultado["pagado"] == total / 2
    assert valor_reserva(app, codigo, "estado") == "pendiente_pago"


def test_rechazar_devuelve_2_horas_al_turista(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(dias=10), metodo="yape")
    pago_id = reportar(app, codigo)
    assert valor_reserva(app, codigo, "TIMESTAMPDIFF(DAY, NOW(), vence_en)") >= 9   # D-09
    with app.app_context():
        with pytest.raises(ErrorValidacion) as excinfo:
            pago.rechazar(actor(OPERADOR), pago_id, "  ")
        assert "observacion" in excinfo.value.errores
        pago.rechazar(actor(OPERADOR), pago_id, "No aparece en Yape")
    assert consultar_valor(app, "SELECT CONCAT(estado, ' / ', observacion) FROM pago WHERE id = %s",
                           (pago_id,)) == "rechazado / No aparece en Yape"
    assert 118 <= valor_reserva(app, codigo, "TIMESTAMPDIFF(MINUTE, NOW(), vence_en)") <= 120


def test_un_pago_se_revisa_una_sola_vez(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), metodo="yape")
    pago_id = reportar(app, codigo)
    with app.app_context():
        pago.verificar(actor(OPERADOR), pago_id)
        with pytest.raises(EstadoNoPermite, match="ya fue revisado"):
            pago.verificar(actor(OPERADOR), pago_id)
        with pytest.raises(EstadoNoPermite):
            pago.rechazar(actor(OPERADOR), pago_id, "Me equivoqué")


def test_no_se_verifica_el_pago_de_una_reserva_vencida(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), metodo="yape")
    pago_id = reportar(app, codigo)
    ejecutar_y_confirmar(app, "UPDATE reserva SET vence_en = NOW() - INTERVAL 1 MINUTE "
                              "WHERE codigo = %s", (codigo,))
    with app.app_context(), pytest.raises(EstadoNoPermite, match="Rechaza el pago"):
        pago.verificar(actor(OPERADOR), pago_id)


@pytest.mark.parametrize("quien", [ADMIN, ELENA, TEODORO])
def test_solo_el_operador_revisa_pagos(app, quien):
    pago_id = consultar_valor(app, "SELECT id FROM pago WHERE estado = 'reportado' LIMIT 1")
    with app.app_context():
        with pytest.raises(PermisoDenegado):
            pago.verificar(actor(quien), pago_id)
        with pytest.raises(PermisoDenegado):
            pago.rechazar(actor(quien), pago_id, "Sin permiso")


def test_sin_familia_libre_el_pago_se_verifica_igual_con_aviso(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=3, dias=26)
    codigo = reservar_en(app, salida_id, metodo="yape")
    pago_id = reportar(app, codigo)
    activas = consultar_valor(app, "SELECT GROUP_CONCAT(id) FROM familia_anfitriona "
                                   "WHERE comunidad_id = 3 AND activa = 1")
    ejecutar_y_confirmar(app, "UPDATE familia_anfitriona SET activa = 0 WHERE comunidad_id = 3")
    try:
        with app.app_context():
            resultado = pago.verificar(actor(OPERADOR), pago_id)
    finally:
        ejecutar_y_confirmar(app, "UPDATE familia_anfitriona SET activa = 1 "
                                  "WHERE FIND_IN_SET(id, %s)", (activas,))
    assert resultado["pagada"] and resultado["familia"] is None
    assert "SIN familia" in resultado["aviso"]
    assert consultar_valor(app, "SELECT COUNT(*) FROM bitacora b JOIN reserva r ON r.id = b.registro_id "
                                "WHERE b.accion = 'sin_familia' AND r.codigo = %s", (codigo,)) == 1


# --- Cobro en el muelle ---------------------------------------------------------------------------

def test_cobro_en_el_muelle_en_dos_partes(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), acompanantes=1)        # muelle: confirmada
    total = valor_reserva(app, codigo, "total")
    with app.app_context():
        operador = actor(OPERADOR)
        with pytest.raises(ErrorValidacion) as excinfo:
            pago.registrar_cobro(operador, codigo, "efectivo_muelle", total + 1, None)
        assert "Falta pagar" in excinfo.value.errores["monto"]
        with pytest.raises(ErrorValidacion) as excinfo:
            pago.registrar_cobro(operador, codigo, "transferencia", 10, "")
        assert "numero_operacion" in excinfo.value.errores
        primera = pago.registrar_cobro(operador, codigo, "efectivo_muelle", total - 10, None)
        segunda = pago.registrar_cobro(operador, codigo, "pos", "10", "POS-1234")
        with pytest.raises(EstadoNoPermite, match="ya está pagada"):
            pago.registrar_cobro(operador, codigo, "efectivo_muelle", 1, None)
    assert not primera["pagada"] and segunda["pagada"]
    assert valor_reserva(app, codigo, "estado") == "pagada"
    assert consultar_valor(app, "SELECT SUM(monto) FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                "WHERE r.codigo = %s AND p.estado = 'verificado'", (codigo,)) == total


# --- Abordaje (RN-12) ------------------------------------------------------------------------------

def test_abordaje_en_la_ventana_y_una_sola_vez_por_pasajero(app, salida_cerca):
    codigo = reservar_en(app, salida_cerca(minutos=30), acompanantes=1)
    with app.app_context():
        operador = actor(OPERADOR)
        datos = abordaje.buscar(operador, codigo)
        ids = [p["id"] for p in datos["pasajeros"]]
        assert datos["motivo_no"] is None and datos["faltan"] == 2
        primero = abordaje.registrar(operador, codigo, ids[:1], "qr")
        with pytest.raises(EstadoNoPermite, match="ya abordaron"):
            abordaje.registrar(operador, codigo, ids[:1], "qr")
        segundo = abordaje.registrar(operador, codigo, ids, "manual")   # solo registra al que falta
    assert primero == {"registrados": 1, "faltan": 1, "abordada": False}
    assert segundo == {"registrados": 1, "faltan": 0, "abordada": True}
    assert valor_reserva(app, codigo, "estado") == "abordada"
    assert consultar_valor(app, "SELECT GROUP_CONCAT(a.metodo ORDER BY a.id) FROM abordaje a "
                                "JOIN reserva_pasajero rp ON rp.id = a.reserva_pasajero_id "
                                "JOIN reserva r ON r.id = rp.reserva_id WHERE r.codigo = %s",
                           (codigo,)) == "qr,manual"


@pytest.mark.parametrize("minutos_hasta_zarpe, mensaje", [(120, "abre 60 minutos antes"),
                                                          (-30, "cerró 15 minutos después")])
def test_abordaje_fuera_de_horario(app, salida_cerca, minutos_hasta_zarpe, mensaje):
    salida_id = salida_cerca(minutos=max(minutos_hasta_zarpe, 30))
    codigo = reservar_en(app, salida_id)
    if minutos_hasta_zarpe < 0:                       # la salida "ya zarpó" hace 30 minutos
        ejecutar_y_confirmar(app, "UPDATE salida SET fecha_hora_zarpe = NOW() - INTERVAL 30 MINUTE "
                                  "WHERE id = %s", (salida_id,))
    with app.app_context():
        datos = abordaje.buscar(actor(OPERADOR), codigo)
        assert mensaje in datos["motivo_no"]
        with pytest.raises(EstadoNoPermite, match=mensaje):
            abordaje.registrar(actor(OPERADOR), codigo, [datos["pasajeros"][0]["id"]], "qr")


def test_sin_pago_verificado_no_se_aborda(app, salida_cerca):
    codigo = reservar_en(app, salida_cerca(minutos=30), metodo="yape")
    with app.app_context():
        assert "Falta verificar el pago" in abordaje.buscar(actor(OPERADOR), codigo)["motivo_no"]


def test_salida_suspendida_no_aborda(app, salida_cerca):
    salida_id = salida_cerca(minutos=30)
    codigo = reservar_en(app, salida_id)
    with app.app_context():
        modelo_salida.suspender(actor(OPERADOR), salida_id, "Tormenta eléctrica")
        assert "suspendida" in abordaje.buscar(actor(OPERADOR), codigo)["motivo_no"]


def test_el_guia_registra_solo_en_su_salida(app, salida_cerca):
    codigo = reservar_en(app, salida_cerca(minutos=30, guia_id=MARCO))
    with app.app_context():
        with pytest.raises(PermisoDenegado):
            abordaje.buscar(actor(ELENA), codigo)
        with pytest.raises(PermisoDenegado):
            abordaje.registrar(actor(ELENA), codigo, [1], "qr")
        datos = abordaje.buscar(actor(MARCO), codigo)
        resultado = abordaje.registrar(actor(MARCO), codigo, [datos["pasajeros"][0]["id"]], "qr")
        assert resultado["abordada"]
        with pytest.raises(PermisoDenegado):
            abordaje.buscar(actor(ADMIN), codigo)            # el admin no registra abordajes


def test_un_pasajero_de_otra_reserva_no_entra(app, salida_cerca):
    salida_id = salida_cerca(minutos=30)
    una, otra = reservar_en(app, salida_id), reservar_en(app, salida_id)
    with app.app_context():
        ajeno = abordaje.buscar(actor(OPERADOR), otra)["pasajeros"][0]["id"]
        with pytest.raises(ErrorValidacion):
            abordaje.registrar(actor(OPERADOR), una, [ajeno], "qr")
        with pytest.raises(ErrorValidacion):
            abordaje.registrar(actor(OPERADOR), una, [], "qr")


def test_la_seleccion_del_metodo_es_lista_blanca(app, salida_cerca):
    codigo = reservar_en(app, salida_cerca(minutos=30))
    with app.app_context():
        datos = abordaje.buscar(actor(OPERADOR), codigo)
        abordaje.registrar(actor(OPERADOR), codigo, [datos["pasajeros"][0]["id"]], "'; DROP TABLE x")
    assert consultar_valor(app, "SELECT a.metodo FROM abordaje a JOIN reserva_pasajero rp "
                                "ON rp.id = a.reserva_pasajero_id JOIN reserva r ON r.id = rp.reserva_id "
                                "WHERE r.codigo = %s", (codigo,)) == "manual"
