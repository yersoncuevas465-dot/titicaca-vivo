"""Feriados del Perú (v2.2): Nager.Date, sin clave. En un feriado llegan más turistas al lago.

GET <FERIADOS_API_URL>/<año>/PE → [{"date": "2026-11-01", "localName": "Día de Todos los Santos",
"name": "All Saints' Day", ...}]. Se pide una vez al día por año. El turista ve «Feriado» en
la lista de salidas y en la salida; el operador, en las salidas del día del panel.
"""

from datetime import date

from flask import current_app

from app.servicios import externas, textos

SEGUNDOS_EN_CACHE = 24 * 3600


def del_anio(anio):
    """{fecha: {'es': nombre, 'en': nombre}} de los feriados nacionales del año ({} sin datos)."""
    def consultar():
        base = current_app.config["FERIADOS_API_URL"].rstrip("/")
        datos = externas.obtener_json(f"{base}/{anio}/PE")
        try:
            return {date.fromisoformat(f["date"]): {"es": f.get("localName") or f["name"],
                                                    "en": f.get("name") or f["localName"]}
                    for f in datos if f.get("global", True)}
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise externas.ApiNoDisponible(
                f"respuesta inesperada ({type(error).__name__})") from error

    return externas.guardado(("feriados", anio), SEGUNDOS_EN_CACHE, consultar) or {}


def de_la_fecha(fecha):
    """El nombre del feriado de esa fecha, en el idioma de la página, o None."""
    nombres = del_anio(fecha.year).get(fecha) if fecha else None
    return nombres[textos.idioma()] if nombres else None


def de_las_fechas(fechas):
    """{fecha: nombre} de las fechas que son feriado (para la tira de días)."""
    return {f: nombre for f in fechas if (nombre := de_la_fecha(f))}
