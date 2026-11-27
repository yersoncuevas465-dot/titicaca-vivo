"""Promociones (observación del docente, 27/11): una temporada también puede bajar el precio.

Antes una temporada solo subía el precio (recargo de 0 a 100 %, como la Candelaria con +20 %).
Ahora acepta de −50 a 100 %: con −10, la tarifa baja un 10 % en esas fechas (temporada baja).
"""

import datetime as dt
from decimal import Decimal

import pymysql
import pytest

from app.modelos import temporada
from app.modelos.tarifa import calcular_precio
from tests.conftest import ejecutar_y_confirmar
from tests.test_catalogos import errores, guardar, hoy
from tests.test_reglas_reserva import crear, fila_reserva, solicitud


def test_pp01_un_descuento_baja_el_precio():
    assert calcular_precio(Decimal("80.00"), Decimal("-10")) == Decimal("72.00")
    assert calcular_precio(Decimal("30.00"), Decimal("-15")) == Decimal("25.50")


def test_pp02_el_panel_guarda_una_promocion_pero_no_un_descuento_exagerado(app):
    lejos = hoy(app) + dt.timedelta(days=3100)
    datos = {"nombre": "Promoción de prueba", "fecha_inicio": lejos,
             "fecha_fin": lejos + dt.timedelta(days=10), "recargo_porcentaje": Decimal("-10")}
    temporada_id = guardar(app, temporada.guardar, None, datos)
    try:
        exagerado = {**datos, "recargo_porcentaje": Decimal("-60")}
        assert "recargo_porcentaje" in errores(app, temporada.guardar, temporada_id, exagerado)
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM temporada WHERE id = %s", (temporada_id,))


def test_pp03_la_base_tampoco_acepta_mas_de_50_por_ciento_de_descuento(app):
    with pytest.raises(pymysql.err.MySQLError):
        ejecutar_y_confirmar(app, "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, "
                                  "recargo_porcentaje) VALUES ('Prueba PP-03', '2031-02-01', "
                                  "'2031-02-10', -51)")


def test_pp04_la_salida_en_promocion_lo_dice_y_la_reserva_cobra_menos(app, cliente, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=26)
    ejecutar_y_confirmar(app, "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, "
                              "recargo_porcentaje) VALUES ('Temporada baja de prueba', "
                              "CURDATE() + INTERVAL 26 DAY, CURDATE() + INTERVAL 26 DAY, -10)")
    try:
        html = cliente.get(f"/salidas/{salida_id}").get_data(True)
        assert "Temporada baja de prueba" in html and "descuento de 10 %" in html
        codigo, _ = crear(app, solicitud(salida_id))
        assert fila_reserva(app, codigo)["total"] == Decimal("27.00")      # 30 × 0,90
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM temporada WHERE nombre = 'Temporada baja de prueba'")
