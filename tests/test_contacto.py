"""Contacto (v2.6): la página, el formulario (validación, trampa para robots y límite por IP) y
el correo a la agencia. El mensaje no se guarda en la base (el modelo tiene 20 tablas): llega
por correo y la bitácora anota solo que llegó, sin el texto ni los datos de la persona."""

import json

import pytest

from tests.conftest import consultar_valor, token_csrf
from tests.test_accesibilidad import problemas

DATOS = {"nombre": "Rosa Quispe", "correo": "rosa@ejemplo.test", "telefono": "", "asunto": "grupos",
         "mensaje": "Somos un colegio de 30 alumnos y queremos ir a Taquile en mayo."}
CONTAR = "SELECT COUNT(*) AS n FROM bitacora WHERE accion = 'mensaje_contacto'"


@pytest.fixture
def buzon(monkeypatch):
    """Los correos que «salen» (destino, asunto, texto): ninguno va a internet."""
    enviados = []

    def enviar_falso(destino, asunto, texto):
        enviados.append((destino, asunto, texto))
        return "simulado"

    monkeypatch.setattr("app.servicios.correo.enviar", enviar_falso)
    return enviados


def enviar(cliente, **cambios):
    csrf = token_csrf(cliente.get("/contacto"))
    return cliente.post("/contacto", data={**DATOS, **cambios, "csrf_token": csrf})


def test_la_pagina_de_contacto(cliente):
    html = cliente.get("/contacto").get_data(True)
    assert "<h1>Contacto</h1>" in html and 'aria-current="page">Contacto</a>' in html
    assert '<label class="campo__etiqueta" for="mensaje">' in html
    assert "Muelle" in html and "openstreetmap.org/?mlat=" in html       # el muelle sale de la base
    assert "wa.me" not in html                                          # sin WhatsApp en el .env
    assert problemas(html) == []


def test_con_los_datos_de_la_agencia_salen_whatsapp_correo_y_horario(app, cliente, monkeypatch):
    monkeypatch.setitem(app.config, "AGENCIA_WHATSAPP", "951234567")
    monkeypatch.setitem(app.config, "AGENCIA_CORREO", "reservas@titicaca-vivo.example")
    monkeypatch.setitem(app.config, "AGENCIA_HORARIO", "Todos los días, de 6:00 a 19:00")
    html = cliente.get("/contacto").get_data(True)
    assert 'href="https://wa.me/51951234567?text=' in html
    assert 'href="mailto:reservas@titicaca-vivo.example"' in html and "de 6:00 a 19:00" in html
    assert problemas(html) == []


def test_el_mensaje_llega_a_los_operadores_y_la_bitacora_no_guarda_datos_personales(
        app, cliente, buzon):
    antes = consultar_valor(app, CONTAR)
    respuesta = enviar(cliente)
    assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/contacto"
    assert [destino for destino, _, _ in buzon] == ["operador@titicaca-vivo.example"]
    _, asunto, texto = buzon[0]
    assert asunto == "[Titicaca Vivo] Contacto: Viaje en grupo o con un colegio"
    assert "Rosa Quispe" in texto and "30 alumnos" in texto and "rosa@ejemplo.test" in texto
    assert "Recibimos tu mensaje" in cliente.get("/contacto").get_data(True)   # POST → 303 → GET
    assert consultar_valor(app, CONTAR) == antes + 1
    detalle = consultar_valor(app, "SELECT detalle FROM bitacora WHERE accion = 'mensaje_contacto' "
                                   "ORDER BY id DESC LIMIT 1")
    assert json.loads(detalle) == {"asunto": "grupos", "idioma": "es", "correos_enviados": 1}


def test_con_correo_de_la_agencia_llega_solo_alli(app, cliente, buzon, monkeypatch):
    monkeypatch.setitem(app.config, "AGENCIA_CORREO", "reservas@titicaca-vivo.example")
    assert enviar(cliente).status_code == 303
    assert [destino for destino, _, _ in buzon] == ["reservas@titicaca-vivo.example"]


@pytest.mark.parametrize("cambios, campo, texto", [
    ({"correo": "", "telefono": ""}, "correo", "Deja un correo o un celular"),
    ({"correo": "no-es-un-correo"}, "correo", "Escribe un correo válido"),
    ({"telefono": "123"}, "telefono", "Celular peruano"),
    ({"mensaje": "hola"}, "mensaje", "Escribe entre 10 y 1500 caracteres."),
    ({"nombre": ""}, "nombre", "Escribe tu nombre."),
    ({"nombre": "R2-D2"}, "nombre", "Escribe tu nombre con letras."),
])
def test_datos_mal_escritos_dan_422_junto_al_campo(cliente, buzon, cambios, campo, texto):
    respuesta = enviar(cliente, **cambios)
    html = respuesta.get_data(True)
    assert respuesta.status_code == 422 and f'id="{campo}-error"' in html and texto in html
    assert 'id="resumen-errores"' in html and buzon == []


def test_la_trampa_para_robots_no_envia_nada(app, cliente, buzon):
    antes = consultar_valor(app, CONTAR)
    respuesta = enviar(cliente, sitio_web="https://spam.example")
    assert respuesta.status_code == 303 and buzon == [] and consultar_valor(app, CONTAR) == antes


def test_si_el_correo_falla_avisa_y_no_pierde_lo_escrito(app, cliente, monkeypatch):
    monkeypatch.setattr("app.servicios.correo.enviar", lambda *_: "error")
    antes = consultar_valor(app, CONTAR)
    respuesta = enviar(cliente)
    html = respuesta.get_data(True)
    assert respuesta.status_code == 503 and "No pudimos enviar tu mensaje" in html
    assert "30 alumnos" in html and consultar_valor(app, CONTAR) == antes


def test_el_formulario_tiene_limite_por_ip(app, cliente, buzon):
    maximo = int(app.config["LIMITE_MENSAJES_CONTACTO"].split()[0])
    codigos = [enviar(cliente).status_code for _ in range(maximo + 1)]
    assert codigos[:maximo] == [303] * maximo and codigos[-1] == 429


def test_contacto_en_ingles(cliente, buzon):
    cliente.get("/idioma/en")
    html = cliente.get("/contacto").get_data(True)
    assert "Write to us" in html and "Your message" in html and "Send message" in html
    respuesta = enviar(cliente, mensaje="corto")
    assert "Write between 10 and 1500 characters." in respuesta.get_data(True)
