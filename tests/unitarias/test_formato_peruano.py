"""Montos y porcentajes al estilo peruano (observación del docente, Práctica 9: «En Perú se
escribe S/ 1 250,00 y 25 %»). No usan la base: corren sin MariaDB."""

from decimal import Decimal

from app.servicios.formato import porcentaje, soles


def test_soles_al_estilo_peruano():
    assert soles(1250) == "S/ 1 250,00"
    assert soles(Decimal("15")) == "S/ 15,00"
    assert soles(Decimal("1234567.5")) == "S/ 1 234 567,50"
    assert soles(None) == ""


def test_porcentajes_al_estilo_peruano():
    assert porcentaje(25) == "25 %"
    assert porcentaje(Decimal("25.0")) == "25 %"
    assert porcentaje(Decimal("33.3")) == "33,3 %"
    assert porcentaje(None) == ""
