"""Tipo de cambio del día de SUNAT (v2.2): apis.net.pe, sin clave. Para mostrar los precios
también en dólares al turista extranjero; es referencial: en la agencia se paga en soles.

GET <TIPO_CAMBIO_API_URL> → {"origen": "SUNAT", "compra": 3.455, "venta": 3.461,
"moneda": "USD", "fecha": "2026-10-30"}. Se guarda 6 horas.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import current_app

from app.servicios import externas

SEGUNDOS_EN_CACHE = 6 * 3600
# Un tipo de cambio fuera de este rango es un error de la API: mejor no mostrar nada.
RANGO_CREIBLE = (Decimal("2.00"), Decimal("6.00"))


def _consultar():
    datos = externas.obtener_json(current_app.config["TIPO_CAMBIO_API_URL"])
    try:
        venta = Decimal(str(datos["venta"]))
        compra = Decimal(str(datos["compra"]))
        fecha = date.fromisoformat(datos["fecha"])
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise externas.ApiNoDisponible(f"respuesta inesperada ({type(error).__name__})") from error
    if not RANGO_CREIBLE[0] <= venta <= RANGO_CREIBLE[1]:
        raise externas.ApiNoDisponible("tipo de cambio fuera de rango")
    return {"venta": venta, "compra": compra, "fecha": fecha}


def del_dia():
    """{'venta', 'compra', 'fecha'} de SUNAT, o None si no hay dato."""
    return externas.guardado(("tipo_cambio",), SEGUNDOS_EN_CACHE, _consultar)
