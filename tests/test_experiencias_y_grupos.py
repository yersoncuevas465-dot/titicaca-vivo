"""Experiencias en las comunidades y viajes en grupo (v2.8): las experiencias salen de la base
(paradas, noche, servicios de las familias) y el pedido de cotización llega por correo con el
precio referencial, sin guardar datos personales en la base."""

import json
from datetime import date, timedelta

import pytest

from app.servicios import formato
from tests.conftest import consultar_valor, token_csrf
from tests.test_accesibilidad import problemas


@pytest.fixture
def buzon(monkeypatch):
    enviados = []

    def enviar_falso(destino, asunto, texto):
        enviados.append((destino, asunto, texto))
        return "simulado"

    monkeypatch.setattr("app.servicios.correo.enviar", enviar_falso)
    return enviados


def tarjetas(html):
    return html.count('<li class="experiencia">')


# --- Experiencias -------------------------------------------------------------------------------

def test_las_experiencias_salen_de_la_base(app, cliente):
    html = cliente.get("/experiencias").get_data(True)
    assert tarjetas(html) == consultar_valor(app, "SELECT COUNT(*) AS n FROM comunidad WHERE activa = 1")
    assert "Noche con una familia anfitriona" in html and "Visita de" in html
    assert 'aria-current="page">Experiencias</a>' in html and problemas(html) == []


@pytest.mark.parametrize("actividad, sql", [
    ("noche", "SELECT COUNT(DISTINCT rp.comunidad_id) AS n FROM ruta_parada rp "
              "JOIN ruta r ON r.id = rp.ruta_id AND r.activa = 1 WHERE rp.es_pernocte = 1"),
    ("taller_textil", "SELECT COUNT(DISTINCT comunidad_id) AS n FROM familia_anfitriona "
                      "WHERE activa = 1 AND FIND_IN_SET('taller_textil', servicios)"),
])
def test_el_filtro_de_experiencias(app, cliente, actividad, sql):
    html = cliente.get(f"/experiencias?actividad={actividad}").get_data(True)
    assert tarjetas(html) == consultar_valor(app, sql) and 'aria-current="true"' in html
    todas = cliente.get("/experiencias", query_string={"actividad": "<script>"}).get_data(True)
    assert tarjetas(todas) == consultar_valor(app, "SELECT COUNT(*) AS n FROM comunidad WHERE activa = 1")


def test_experiencias_en_ingles(cliente):
    cliente.get("/idioma/en")
    html = cliente.get("/experiencias").get_data(True)
    assert "Experiences on the lake" in html and "A night with a host family" in html


# --- Grupos -------------------------------------------------------------------------------------

def grupo(**cambios):
    return {"tipo": "colegio", "institucion": "Colegio de prueba", "personas": "30",
            "fecha": (date.today() + timedelta(days=30)).isoformat(), "ruta": "URO-TAQ",
            "nombre": "Rosa Quispe", "correo": "rosa@ejemplo.test", "telefono": "",
            "comentarios": "Somos 28 alumnos y 2 profesores.", **cambios}


def pedir(cliente, **cambios):
    csrf = token_csrf(cliente.get("/grupos"))
    return cliente.post("/grupos", data={**grupo(**cambios), "csrf_token": csrf})


def test_la_pagina_de_grupos(cliente):
    html = cliente.get("/grupos").get_data(True)
    assert "<h1>Viajes en grupo</h1>" in html and "Precios de referencia por persona" in html
    assert 'value="URO-TAQ"' in html and problemas(html) == []


def test_la_cotizacion_llega_con_el_precio_referencial(app, cliente, buzon):
    respuesta = pedir(cliente)
    assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/grupos"
    desde = consultar_valor(app, "SELECT MIN(t.precio_base) AS desde FROM tarifa t "
                                 "JOIN ruta r ON r.id = t.ruta_id "
                                 "JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id "
                                 "WHERE r.codigo = 'URO-TAQ' "
                                 "AND tp.codigo IN ('adulto_nacional', 'adulto_extranjero') "
                                 "AND t.vigente_desde <= CURDATE() "
                                 "AND (t.vigente_hasta IS NULL OR t.vigente_hasta >= CURDATE())")
    esperado = formato.soles(desde * 30)
    destino, asunto, texto = buzon[0]
    assert destino == "operador@titicaca-vivo.example" and "30 personas" in asunto
    assert f"desde {esperado}" in texto and "Colegio de prueba" in texto and "Rosa Quispe" in texto
    assert f"desde {esperado}" in cliente.get("/grupos").get_data(True)       # el aviso tras el 303
    detalle = json.loads(consultar_valor(app, "SELECT detalle FROM bitacora WHERE accion = "
                                              "'cotizacion_grupo' ORDER BY id DESC LIMIT 1"))
    assert detalle["personas"] == 30 and detalle["ruta"] == "URO-TAQ" and "nombre" not in detalle


@pytest.mark.parametrize("cambios, campo", [
    ({"personas": "1"}, "personas"),
    ({"personas": "muchos"}, "personas"),
    ({"fecha": "2020-01-01"}, "fecha"),
    ({"ruta": "NO-EXISTE"}, "ruta"),
    ({"correo": "", "telefono": ""}, "correo"),
    ({"tipo": "piratas"}, "tipo"),
])
def test_un_pedido_mal_llenado_da_422_junto_al_campo(cliente, buzon, cambios, campo):
    respuesta = pedir(cliente, **cambios)
    assert respuesta.status_code == 422 and f'id="{campo}-error"' in respuesta.get_data(True)
    assert buzon == []


def test_la_trampa_para_robots_y_el_limite(app, cliente, buzon):
    assert pedir(cliente, sitio_web="https://spam.example").status_code == 303 and buzon == []
    maximo = int(app.config["LIMITE_COTIZACIONES_GRUPO"].split()[0])
    codigos = [pedir(cliente).status_code for _ in range(maximo)]
    assert codigos[-1] == 429                       # la trampa también cuenta en el límite


def test_grupos_en_ingles(cliente, buzon):
    cliente.get("/idioma/en")
    assert "Group trips" in cliente.get("/grupos").get_data(True)
    respuesta = pedir(cliente, personas="1")
    assert "Write how many people you are (2 to 300)." in respuesta.get_data(True)
