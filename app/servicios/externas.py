"""APIs externas (v2.2): RENIEC (DNI → nombres), SUNAT (tipo de cambio), Open-Meteo (clima del
lago) y Nager.Date (feriados del Perú). Todas públicas y sin clave.

- Solo las llama el servidor: la CSP no deja que el navegador hable con otros sitios, y así el
  DNI que escribe el turista no sale de su navegador hacia terceros.
- Tiempo de espera corto y caché en memoria: si una API se cae o tarda, la página se muestra
  igual, sin ese dato, y no se le vuelve a preguntar hasta que pase un rato.
- Con APIS_EXTERNAS = 0 (y siempre en las pruebas) no sale nada a internet.
- Nunca se escribe en el registro lo que responde una API (puede traer datos personales).
"""

import json
import threading
import time
import urllib.error
import urllib.request

from flask import current_app

MAXIMO_EN_CACHE = 1000
_cache = {}                          # clave → (vence_en, valor)
_candado = threading.Lock()          # waitress atiende con varios hilos


class ApiNoDisponible(Exception):
    """La API no respondió a tiempo, falló (5xx, 429) o respondió algo que no se entiende."""


class NoEncontrado(Exception):
    """La API respondió que ese dato no existe (4xx): por ejemplo, un DNI que no está."""


def activas():
    return bool(current_app.config["APIS_EXTERNAS"])


def obtener_json(url):
    """GET a la URL y su JSON. Lanza NoEncontrado (4xx) o ApiNoDisponible (todo lo demás)."""
    if not activas():
        raise ApiNoDisponible("las APIs externas están apagadas (APIS_EXTERNAS=0)")
    # La URL sale de la configuración (https), nunca de lo que escribe el usuario.
    pedido = urllib.request.Request(url, headers={  # noqa: S310
        "Accept": "application/json",
        "User-Agent": f"TiticacaVivo/{current_app.config['VERSION']}"})
    espera = current_app.config["APIS_TIMEOUT"]
    try:
        with urllib.request.urlopen(pedido, timeout=espera) as respuesta:  # noqa: S310
            return json.loads(respuesta.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as error:          # (antes que URLError: es una subclase)
        if 400 <= error.code < 500 and error.code != 429:
            raise NoEncontrado(f"HTTP {error.code}") from error
        raise ApiNoDisponible(f"HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise ApiNoDisponible(type(error).__name__) from error


def leer(clave):
    """(True, valor) si la clave está guardada y no venció; (False, None) si no."""
    with _candado:
        guardado = _cache.get(clave)
    if guardado and guardado[0] > time.monotonic():
        return True, guardado[1]
    return False, None


def guardar(clave, valor, segundos):
    with _candado:
        if len(_cache) >= MAXIMO_EN_CACHE:
            _cache.clear()          # es solo un atajo: se vacía y se vuelve a llenar
        _cache[clave] = (time.monotonic() + segundos, valor)


def guardado(clave, segundos, consultar, segundos_si_falla=300):
    """Lo que devuelve `consultar()`, guardado `segundos`. Si la API no responde, None durante
    `segundos_si_falla`: así una API caída no hace esperar a cada página."""
    if not activas():
        return None
    hay, valor = leer(clave)
    if hay:
        return valor
    try:
        valor = consultar()
    except NoEncontrado:
        valor = None
    except ApiNoDisponible as error:
        current_app.logger.warning("API externa sin respuesta (%s): %s", clave[0], error)
        guardar(clave, None, segundos_si_falla)
        return None
    guardar(clave, valor, segundos)
    return valor


def limpiar():
    """Vacía la caché (las pruebas empiezan cada una sin nada guardado)."""
    with _candado:
        _cache.clear()
