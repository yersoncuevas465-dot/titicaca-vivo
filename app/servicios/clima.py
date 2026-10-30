"""Clima del lago a la hora del zarpe (v2.2): Open-Meteo, sin clave (datos con licencia CC BY 4.0).

Un solo pronóstico por hora para la bahía de Puno, de 14 días, guardado 30 minutos. Es una
referencia para el turista y para la tripulación: lo que suspende una salida es la alerta de
SENAMHI o de la Capitanía que registra el operador (RN-11).
"""

from datetime import date, datetime
from urllib.parse import urlencode

from flask import current_app

from app.servicios import externas

DIAS = 14
SEGUNDOS_EN_CACHE = 1800
RAFAGA_FUERTE = 40          # km/h: desde aquí la página avisa «se espera viento fuerte»

# Códigos WMO del cielo → texto (y un ícono que no se lee: aria-hidden)
CIELO = {
    0: ("Despejado", "☀️"), 1: ("Mayormente despejado", "🌤️"), 2: ("Parcialmente nublado", "⛅"),
    3: ("Nublado", "☁️"), 45: ("Niebla", "🌫️"), 48: ("Niebla", "🌫️"),
    51: ("Llovizna", "🌦️"), 53: ("Llovizna", "🌦️"), 55: ("Llovizna", "🌦️"),
    56: ("Llovizna helada", "🌨️"), 57: ("Llovizna helada", "🌨️"),
    61: ("Lluvia débil", "🌧️"), 63: ("Lluvia", "🌧️"), 65: ("Lluvia fuerte", "🌧️"),
    66: ("Lluvia helada", "🌨️"), 67: ("Lluvia helada", "🌨️"),
    71: ("Nieve", "🌨️"), 73: ("Nieve", "🌨️"), 75: ("Nieve fuerte", "🌨️"), 77: ("Granizo menudo", "🌨️"),
    80: ("Chubascos", "🌦️"), 81: ("Chubascos", "🌦️"), 82: ("Chubascos fuertes", "⛈️"),
    85: ("Chubascos de nieve", "🌨️"), 86: ("Chubascos de nieve", "🌨️"),
    95: ("Tormenta eléctrica", "⛈️"), 96: ("Tormenta con granizo", "⛈️"),
    99: ("Tormenta con granizo", "⛈️"),
}
VARIABLES = ("temperature_2m", "precipitation_probability", "weather_code", "wind_speed_10m",
             "wind_gusts_10m")


def _consultar():
    latitud, longitud = current_app.config["CLIMA_LUGAR"]
    parametros = urlencode({
        "latitude": latitud, "longitude": longitud, "timezone": current_app.config["ZONA_HORARIA"],
        "hourly": ",".join(VARIABLES), "daily": "sunrise,sunset", "forecast_days": DIAS,
        "wind_speed_unit": "kmh"})
    datos = externas.obtener_json(f"{current_app.config['CLIMA_API_URL']}?{parametros}")
    try:
        horas, dias = datos["hourly"], datos["daily"]
        por_hora = {datetime.fromisoformat(momento): {v: horas[v][i] for v in VARIABLES}
                    for i, momento in enumerate(horas["time"])}
        sol = {date.fromisoformat(dia): (datetime.fromisoformat(dias["sunrise"][i]),
                                         datetime.fromisoformat(dias["sunset"][i]))
               for i, dia in enumerate(dias["time"])}
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise externas.ApiNoDisponible(f"respuesta inesperada ({type(error).__name__})") from error
    return {"horas": por_hora, "sol": sol}


def pronostico():
    return externas.guardado(("clima",), SEGUNDOS_EN_CACHE, _consultar)


def para_la_hora(momento):
    """El pronóstico de la hora en punto de `momento` (la del zarpe), o None si no hay: APIs
    apagadas, sin respuesta, o la salida es en más de 14 días o ya pasó."""
    datos = pronostico()
    if not datos or momento is None:
        return None
    hora = momento.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    fila = datos["horas"].get(hora)
    if not fila or any(fila[v] is None for v in VARIABLES):
        return None
    cielo, icono = CIELO.get(fila["weather_code"], ("Sin dato del cielo", "🌡️"))
    amanecer, atardecer = datos["sol"].get(hora.date(), (None, None))
    rafagas = round(fila["wind_gusts_10m"])
    return {
        "hora": hora, "temperatura": round(fila["temperature_2m"]), "cielo": cielo, "icono": icono,
        "lluvia": round(fila["precipitation_probability"]), "viento": round(fila["wind_speed_10m"]),
        "rafagas": rafagas, "fuerte": rafagas >= RAFAGA_FUERTE,
        "amanecer": amanecer, "atardecer": atardecer,
    }
