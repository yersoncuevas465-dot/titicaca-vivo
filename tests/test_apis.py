"""APIs externas (v2.2): RENIEC (DNI → nombres), tipo de cambio de SUNAT, clima del zarpe
(Open-Meteo) y feriados (Nager.Date).

Ninguna prueba sale a internet: se reemplaza externas.obtener_json (o urlopen) por respuestas
de ejemplo con datos ficticios. Lo que se prueba: que cada dato llegue a su página, que una API
caída o rara no rompa nada, que la consulta de DNI pida el token y tenga límite, y que con
APIS_EXTERNAS apagado no salga ningún pedido.
"""

import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app import tareas
from app.servicios import clima, externas, feriados, formato, reniec, tipo_cambio
from tests.conftest import consultar_valor, iniciar_sesion, token_csrf
from tests.test_accesibilidad import problemas

DNI = "12345678"
PERSONA_FICTICIA = {"documentID": DNI, "names": "ROSA ELENA", "paternalLastName": "QUISPE",
                    "maternalLastName": "DE LA CRUZ", "fullName": "QUISPE DE LA CRUZ ROSA ELENA",
                    "resourceOf": "api"}
CAMBIO = {"origen": "SUNAT", "compra": 3.48, "venta": 3.5, "moneda": "USD", "fecha": "2026-10-30"}


class ApisDeEjemplo:
    """Respuestas por fragmento de URL (un dato o una excepción) y la lista de URLs pedidas."""

    def __init__(self):
        self.respuestas, self.pedidas = {}, []

    def __call__(self, url):
        self.pedidas.append(url)
        for fragmento, respuesta in self.respuestas.items():
            if fragmento in url:
                if isinstance(respuesta, Exception):
                    raise respuesta
                return respuesta
        raise externas.ApiNoDisponible("sin respuesta de ejemplo")


@pytest.fixture(autouse=True)
def cache_vacia():
    externas.limpiar()
    yield
    externas.limpiar()


@pytest.fixture
def apis(app, monkeypatch):
    falsas = ApisDeEjemplo()
    monkeypatch.setitem(app.config, "APIS_EXTERNAS", True)
    monkeypatch.setattr(externas, "obtener_json", falsas)
    return falsas


def zarpe_de(app, salida_id):
    return consultar_valor(app, "SELECT fecha_hora_zarpe FROM salida WHERE id = %s", (salida_id,))


def pronostico_de_ejemplo(dia, rafagas=25):
    """Un día de Open-Meteo con el mismo dato a cada hora."""
    horas = [datetime.combine(dia, time(h)).isoformat(timespec="minutes") for h in range(24)]
    return {"hourly": {"time": horas, "temperature_2m": [8.4] * 24,
                       "precipitation_probability": [20] * 24, "weather_code": [2] * 24,
                       "wind_speed_10m": [14.6] * 24, "wind_gusts_10m": [rafagas] * 24},
            "daily": {"time": [dia.isoformat()], "sunrise": [f"{dia}T05:21"],
                      "sunset": [f"{dia}T17:58"]}}


def pedir_dni(cliente, numero, salida_id=10):
    csrf = token_csrf(cliente.get(f"/salidas/{salida_id}/reservar"))
    return cliente.post("/api/dni", data={"dni": numero, "csrf_token": csrf})


# --- Sin APIs (las pruebas, o sin internet) no sale nada --------------------------------------

def test_con_las_apis_apagadas_no_sale_ningun_pedido(app, cliente, monkeypatch):
    def prohibido(*_args, **_kwargs):
        raise AssertionError("Una prueba intentó salir a internet")

    monkeypatch.setattr(urllib.request, "urlopen", prohibido)
    with app.test_request_context():
        with pytest.raises(externas.ApiNoDisponible):
            externas.obtener_json("https://ejemplo.invalid/x")
        assert clima.pronostico() is None and tipo_cambio.del_dia() is None
        assert feriados.de_la_fecha(date.today()) is None and not reniec.disponible()
    salida = cliente.get("/salidas/10").get_data(True)
    assert "El clima para el zarpe" not in salida and "En dólares" not in salida
    formulario = cliente.get("/salidas/10/reservar").get_data(True)
    assert "data-dni-url" not in formulario and "js/dni.js" not in formulario
    respuesta = pedir_dni(cliente, DNI)
    assert respuesta.status_code == 503 and "no está activa" in respuesta.get_json()["error"]


class _Respuesta:
    def __init__(self, cuerpo):
        self.cuerpo = cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _maximo=None):
        return self.cuerpo


@pytest.mark.parametrize("sucede, error", [
    (_Respuesta(b'{"ok": 1}'), None),
    (urllib.error.HTTPError("u", 404, "Not Found", {}, None), externas.NoEncontrado),
    (urllib.error.HTTPError("u", 400, "Bad Request", {}, None), externas.NoEncontrado),
    (urllib.error.HTTPError("u", 429, "Too Many", {}, None), externas.ApiNoDisponible),
    (urllib.error.HTTPError("u", 503, "Down", {}, None), externas.ApiNoDisponible),
    (TimeoutError("tardó"), externas.ApiNoDisponible),
    (urllib.error.URLError("sin red"), externas.ApiNoDisponible),
    (_Respuesta(b"<html>no es JSON</html>"), externas.ApiNoDisponible),
])
def test_obtener_json_separa_no_encontrado_de_no_disponible(app, monkeypatch, sucede, error):
    def urlopen_falso(pedido, timeout):
        assert timeout == app.config["APIS_TIMEOUT"] and pedido.get_header("User-agent")
        if isinstance(sucede, Exception):
            raise sucede
        return sucede

    monkeypatch.setitem(app.config, "APIS_EXTERNAS", True)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)
    with app.app_context():
        if error is None:
            assert externas.obtener_json("https://ejemplo.invalid/x") == {"ok": 1}
        else:
            with pytest.raises(error):
                externas.obtener_json("https://ejemplo.invalid/x")


def test_una_api_caida_no_se_vuelve_a_pedir_en_cada_pagina(app, apis):
    apis.respuestas["tipo-cambio"] = externas.ApiNoDisponible("HTTP 503")
    cliente = app.test_client()
    for _ in range(3):
        assert cliente.get("/salidas/10").status_code == 200
    assert sum("tipo-cambio" in u for u in apis.pedidas) == 1      # la falla también se guarda


# --- RENIEC: el DNI completa nombres y apellidos ---------------------------------------------

def test_nombre_propio_como_en_el_documento():
    assert reniec.nombre_propio("MARÍA DEL CARMEN") == "María del Carmen"
    assert reniec.nombre_propio("  DE LA CRUZ  QUISPE ") == "De la Cruz Quispe"
    assert reniec.limpiar_dni(" 12.345-678 ") == DNI


def test_el_formulario_pide_primero_el_documento_y_trae_la_consulta(app, apis):
    html = app.test_client().get("/salidas/10/reservar").get_data(True)
    assert 'data-dni-url="/api/dni"' in html and re.search(r'src="/estaticos/js/dni\.js\?v=[^"]+" defer', html)
    assert "Con DNI peruano, escribe primero el número" in html
    assert html.index('id="titular_numero_documento"') < html.index('id="titular_nombres"')
    plantilla = html[html.index('id="plantilla-acompanante"'):]
    assert plantilla.index("numero_documento") < plantilla.index("-nombres")
    assert problemas(html) == []


def test_el_dni_devuelve_nombres_y_apellidos(app, cliente, apis):
    apis.respuestas[f"/api/query/{DNI}"] = PERSONA_FICTICIA
    respuesta = pedir_dni(cliente, " 12.345.678 ")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"ok": True, "nombres": "Rosa Elena", "apellidos": "Quispe de la Cruz"}
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert pedir_dni(cliente, DNI).status_code == 200
    assert sum("/api/query/" in u for u in apis.pedidas) == 1        # la segunda vez, de la caché


@pytest.mark.parametrize("respuesta_api, codigo, texto", [
    (externas.NoEncontrado("HTTP 400"), 200, "No encontramos ese DNI"),
    ({**PERSONA_FICTICIA, "documentID": "87654321"}, 200, "No encontramos ese DNI"),   # otro DNI
    ({"names": "", "paternalLastName": ""}, 200, "No encontramos ese DNI"),
    (externas.ApiNoDisponible("timeout"), 503, "RENIEC no responde"),
    (["no", "es", "un", "objeto"], 503, "RENIEC no responde"),
])
def test_dni_que_no_esta_o_reniec_caido(cliente, apis, respuesta_api, codigo, texto):
    apis.respuestas[f"/api/query/{DNI}"] = respuesta_api
    respuesta = pedir_dni(cliente, DNI)
    assert respuesta.status_code == codigo
    assert respuesta.get_json()["ok"] is False and texto in respuesta.get_json()["error"]


def test_dni_mal_escrito_no_llega_a_reniec_y_el_mensaje_sigue_el_idioma(cliente, apis):
    for numero in ("1234", "1234567X", "123456789", ""):
        respuesta = pedir_dni(cliente, numero)
        assert respuesta.status_code == 422 and "8 dígitos" in respuesta.get_json()["error"]
    cliente.get("/idioma/en")
    assert "8 digits" in pedir_dni(cliente, "1234").get_json()["error"]
    assert not [u for u in apis.pedidas if "/api/query/" in u]       # a RENIEC no llegó nada


def test_la_consulta_de_dni_pide_el_token_csrf(cliente, apis):
    apis.respuestas["/api/query/"] = PERSONA_FICTICIA
    assert cliente.post("/api/dni", data={"dni": DNI}).status_code == 400
    assert not [u for u in apis.pedidas if "/api/query/" in u]


def test_la_consulta_de_dni_tiene_limite_por_ip(app, cliente, apis):
    apis.respuestas["/api/query/"] = PERSONA_FICTICIA
    csrf = token_csrf(cliente.get("/salidas/10/reservar"))
    maximo = int(app.config["LIMITE_CONSULTAS_DNI"].split()[0])
    codigos = [cliente.post("/api/dni", data={"dni": DNI, "csrf_token": csrf}).status_code
               for _ in range(maximo + 1)]
    assert codigos[:maximo] == [200] * maximo and codigos[-1] == 429


def test_el_operador_tambien_completa_por_dni_al_vender(app, apis):
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/salidas/10/reservar").get_data(True)
    assert "Venta del operador" in html and 'data-dni-url="/api/dni"' in html


# --- Tipo de cambio (SUNAT): precios también en dólares ---------------------------------------

def test_dolares_redondeados():
    assert formato.dolares(Decimal("80.00"), {"venta": Decimal("3.5")}) == "US$ 23"
    assert formato.dolares(Decimal("1000"), {"venta": Decimal("3.461")}) == "US$ 289"
    assert formato.dolares(Decimal("80.00"), None) == ""


def test_la_salida_muestra_los_precios_en_dolares(app, apis):
    apis.respuestas["tipo-cambio-sunat"] = CAMBIO
    cliente = app.test_client()
    html = cliente.get("/salidas/10").get_data(True)
    assert '<th scope="col">En dólares</th>' in html and "≈ US$ " in html
    assert "S/ 3,5 por dólar" in html and problemas(html) == []
    assert "(≈ US$ " in cliente.get("/salidas/10/reservar").get_data(True)
    cliente.get("/idioma/en")
    assert "In US dollars" in cliente.get("/salidas/10").get_data(True)


@pytest.mark.parametrize("raro", [{**CAMBIO, "venta": 35}, {"venta": "abc"}, {"fecha": "2026-10-30"}])
def test_un_tipo_de_cambio_raro_no_se_muestra(app, apis, raro):
    apis.respuestas["tipo-cambio-sunat"] = raro
    html = app.test_client().get("/salidas/10").get_data(True)
    assert "En dólares" not in html


# --- Clima del zarpe (Open-Meteo) ---------------------------------------------------------------

def test_la_salida_muestra_el_clima_a_la_hora_del_zarpe(app, apis):
    zarpe = zarpe_de(app, 10)
    apis.respuestas["open-meteo"] = pronostico_de_ejemplo(zarpe.date())
    cliente = app.test_client()
    html = cliente.get("/salidas/10").get_data(True)
    assert "El clima para el zarpe" in html and "8 °C" in html and "Parcialmente nublado" in html
    assert "15 km/h, ráfagas de 25 km/h" in html and "sale a las 05:21 y se pone a las 17:58" in html
    assert f"a las {zarpe:%H:00}" in html and "Se espera viento fuerte" not in html
    assert problemas(html) == []
    cliente.get("/idioma/en")
    assert "Weather at departure time" in cliente.get("/salidas/10").get_data(True)
    assert sum("open-meteo" in u for u in apis.pedidas) == 1          # 30 minutos en la caché


def test_con_viento_fuerte_avisa_al_turista_y_a_la_tripulacion(app, apis):
    apis.respuestas["open-meteo"] = pronostico_de_ejemplo(zarpe_de(app, 10).date(), rafagas=48)
    assert "Se espera viento fuerte" in app.test_client().get("/salidas/10").get_data(True)
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel/salidas/10/pasajeros").get_data(True)
    assert "Ráfagas de 48 km/h: revisa los avisos de SENAMHI" in html and problemas(html) == []
    assert "El clima para el zarpe" not in cliente.get(
        "/panel/salidas/10/pasajeros?formato=imprimir").get_data(True)


@pytest.mark.parametrize("respuesta", [
    {"hourly": {"time": ["2020-01-01T00:00"]}},                       # le faltan variables
    {"otra": "cosa"},
    externas.ApiNoDisponible("HTTP 502"),
])
def test_sin_pronostico_o_con_uno_raro_la_salida_sale_igual(app, apis, respuesta):
    apis.respuestas["open-meteo"] = respuesta
    respuesta_http = app.test_client().get("/salidas/10")
    assert respuesta_http.status_code == 200 and "El clima para el zarpe" not in respuesta_http.get_data(True)


def test_una_salida_fuera_del_pronostico_no_muestra_clima(app, apis):
    apis.respuestas["open-meteo"] = pronostico_de_ejemplo(date.today() - timedelta(days=30))
    with app.test_request_context():
        assert clima.para_la_hora(zarpe_de(app, 10)) is None


# --- Feriados (Nager.Date) --------------------------------------------------------------------

def test_el_feriado_se_ve_en_las_salidas_y_en_el_panel(app, apis):
    manana = date.today() + timedelta(days=1)
    apis.respuestas[f"/PublicHolidays/{manana.year}/PE"] = [
        {"date": manana.isoformat(), "localName": "Día de Prueba", "name": "Test Day", "global": True},
        {"date": manana.isoformat(), "localName": "Solo regional", "name": "Regional", "global": False},
    ]
    cliente = app.test_client()
    html = cliente.get(f"/salidas?fecha={manana.isoformat()}").get_data(True)
    assert "Feriado: Día de Prueba." in html and 'class="dia__feriado">Feriado<' in html
    assert "Solo regional" not in html and problemas(html) == []
    cliente.get("/idioma/en")
    assert "Public holiday: Test Day." in cliente.get(f"/salidas?fecha={manana.isoformat()}").get_data(True)
    operador = app.test_client()
    iniciar_sesion(operador, "operador")
    panel = operador.get(f"/panel/salidas?fecha={manana.isoformat()}").get_data(True)
    assert "Feriado: Día de Prueba." in panel


def test_la_salida_de_un_feriado_lo_avisa(app, apis):
    dia = zarpe_de(app, 10).date()
    apis.respuestas[f"/PublicHolidays/{dia.year}/PE"] = [
        {"date": dia.isoformat(), "localName": "Día de Prueba", "name": "Test Day"}]
    assert "Ese día es feriado (Día de Prueba)" in app.test_client().get("/salidas/10").get_data(True)


# --- El servidor deja todo listo cada 5 minutos ----------------------------------------------

def test_la_tarea_del_servidor_prepara_las_apis_y_no_se_cae(app, apis):
    apis.respuestas["open-meteo"] = pronostico_de_ejemplo(date.today())
    apis.respuestas["tipo-cambio-sunat"] = CAMBIO
    apis.respuestas["/PublicHolidays/"] = []
    tareas.hacer(app, revisar_respaldo=False)
    pedidas = " ".join(apis.pedidas)
    assert "open-meteo" in pedidas and "tipo-cambio-sunat" in pedidas and "PublicHolidays" in pedidas
    with app.test_request_context():
        assert tipo_cambio.del_dia()["venta"] == Decimal("3.5")       # ya estaba en la caché
    externas.limpiar()
    apis.respuestas.clear()                                          # todas caídas: no pasa nada
    tareas.hacer(app, revisar_respaldo=False)


def test_la_respuesta_de_reniec_no_se_escribe_en_el_registro(app, cliente, apis, caplog):
    apis.respuestas[f"/api/query/{DNI}"] = externas.ApiNoDisponible("HTTP 502")
    pedir_dni(cliente, DNI)
    assert DNI not in caplog.text and "RENIEC sin respuesta" in caplog.text
    assert json.dumps(PERSONA_FICTICIA["names"]) not in caplog.text
