"""Libro de reclamaciones (v2.8, Ley 29571): la hoja queda en la bitácora con su número
correlativo del año, la constancia solo la ve quien la registró, el operador la responde una
vez (el admin solo mira) y el plazo son 15 días hábiles. Ningún correo sale a internet."""

import json
import re
from datetime import date, datetime

import pytest

from app.modelos import reclamacion
from tests.conftest import consultar_valor, iniciar_sesion, token_csrf
from tests.test_accesibilidad import problemas

HOJA = {"tipo": "reclamo", "nombres": "Rosa Elena", "apellidos": "Quispe Prueba",
        "tipo_documento": "DNI", "numero_documento": "79940001", "domicilio": "Jr. Lima 123, Puno",
        "correo": "rosa@ejemplo.test", "telefono": "", "apoderado": "", "codigo_reserva": "",
        "monto": "80", "servicio": "La salida en lancha del sábado",
        "detalle": "La lancha salió una hora tarde y nadie nos avisó del cambio de horario.",
        "pedido": "Que me devuelvan la mitad del pasaje.", "acepto": "y"}
CONTAR = "SELECT COUNT(*) AS n FROM bitacora WHERE accion = 'reclamacion'"


@pytest.fixture
def buzon(monkeypatch):
    enviados = []

    def enviar_falso(destino, asunto, texto):
        enviados.append((destino, asunto, texto))
        return "simulado"

    monkeypatch.setattr("app.servicios.correo.enviar", enviar_falso)
    return enviados


def registrar(cliente, **cambios):
    csrf = token_csrf(cliente.get("/libro-de-reclamaciones"))
    return cliente.post("/libro-de-reclamaciones", data={**HOJA, **cambios, "csrf_token": csrf})


def numero_de(respuesta):
    return respuesta.headers["Location"].rsplit("/", 1)[1]


def test_el_libro_se_ve_desde_cualquier_pagina_y_es_accesible(cliente):
    assert 'href="/libro-de-reclamaciones"' in cliente.get("/").get_data(True)       # en el pie
    html = cliente.get("/libro-de-reclamaciones").get_data(True)
    assert "<h1>Libro de reclamaciones</h1>" in html and "Ley N.º 29571" in html
    assert "15 días hábiles" in html and 'name="tipo"' in html and problemas(html) == []


def test_la_hoja_queda_en_la_bitacora_con_numero_correlativo(app, cliente, buzon):
    antes = consultar_valor(app, CONTAR)
    primera = registrar(cliente)
    segunda = registrar(cliente, numero_documento="79940002")
    assert primera.status_code == segunda.status_code == 303
    uno, dos = numero_de(primera), numero_de(segunda)
    assert re.fullmatch(r"\d{6}-\d{4}", uno) and int(dos[:6]) == int(uno[:6]) + 1 and dos[7:] == uno[7:]
    assert consultar_valor(app, CONTAR) == antes + 2
    detalle = json.loads(consultar_valor(app, "SELECT detalle FROM bitacora WHERE accion = 'reclamacion' "
                                              "ORDER BY id DESC LIMIT 1"))
    assert detalle["numero"] == dos and detalle["monto"] == "80.00" and detalle["tipo"] == "reclamo"
    asuntos = [(destino, asunto) for destino, asunto, _ in buzon]
    assert ("rosa@ejemplo.test", f"Constancia de tu hoja de reclamación N.º {uno}") in asuntos
    assert ("operador@titicaca-vivo.example", f"[Titicaca Vivo] Nueva hoja de reclamación N.º {uno}") in asuntos


def test_la_constancia_solo_la_ve_quien_registro_la_hoja(app, cliente, buzon):
    url = registrar(cliente).headers["Location"]
    respuesta = cliente.get(url)
    html = respuesta.get_data(True)
    assert "Hoja de reclamación N.º" in html and "Rosa Elena Quispe Prueba" in html
    assert "Te respondemos por correo hasta el" in html and "S/ 80,00" in html
    assert respuesta.headers["Cache-Control"] == "no-store" and problemas(html) == []
    assert app.test_client().get(url).status_code == 404                 # otro navegador: no


@pytest.mark.parametrize("cambios, campo", [
    ({"tipo": ""}, "tipo"),
    ({"nombres": "R2-D2"}, "nombres"),
    ({"numero_documento": "123"}, "numero_documento"),
    ({"correo": "no-es-correo"}, "correo"),
    ({"monto": "mucho"}, "monto"),
    ({"codigo_reserva": "XX-1"}, "codigo_reserva"),
    ({"detalle": "muy corto"}, "detalle"),
    ({"acepto": ""}, "acepto"),
])
def test_una_hoja_mal_llenada_da_422_junto_al_campo(app, cliente, buzon, cambios, campo):
    antes = consultar_valor(app, CONTAR)
    respuesta = registrar(cliente, **cambios)
    assert respuesta.status_code == 422 and f'id="{campo}-error"' in respuesta.get_data(True)
    assert buzon == [] and consultar_valor(app, CONTAR) == antes


def test_la_trampa_para_robots_no_registra_nada(app, cliente, buzon):
    antes = consultar_valor(app, CONTAR)
    assert registrar(cliente, sitio_web="https://spam.example").status_code == 303
    assert buzon == [] and consultar_valor(app, CONTAR) == antes


def test_el_operador_responde_una_vez_y_el_admin_solo_mira(app, buzon):
    turista = app.test_client()
    numero = numero_de(registrar(turista))
    hoja_id = consultar_valor(app, "SELECT id FROM bitacora WHERE accion = 'reclamacion' "
                                   "AND JSON_VALUE(detalle, '$.numero') = %s", (numero,))
    url = f"/panel/reclamaciones/{hoja_id}/respuesta"
    admin = app.test_client()
    iniciar_sesion(admin, "admin")
    pagina = admin.get("/panel/reclamaciones")
    assert f"N.º {numero}" in pagina.get_data(True) and f'action="{url}"' not in pagina.get_data(True)
    assert admin.post(url, data={"csrf_token": token_csrf(pagina), "respuesta": "x" * 20}).status_code == 403

    operador = app.test_client()
    iniciar_sesion(operador, "operador")
    pagina = operador.get("/panel/reclamaciones")
    assert f'action="{url}"' in pagina.get_data(True) and problemas(pagina.get_data(True)) == []
    csrf = token_csrf(pagina)
    corta = operador.post(url, data={"csrf_token": csrf, "respuesta": "corta"})
    assert corta.status_code == 422 and "entre 10 y 2000" in corta.get_data(True)
    buzon.clear()
    texto = "Le devolvimos S/ 40 por Yape y le pedimos disculpas por la demora."
    assert operador.post(url, data={"csrf_token": csrf, "respuesta": texto}).status_code == 303
    assert buzon[0][0] == "rosa@ejemplo.test" and texto in buzon[0][2]
    assert "Respondida" in operador.get("/panel/reclamaciones").get_data(True)
    otra = operador.post(url, data={"csrf_token": csrf, "respuesta": texto})
    assert otra.status_code == 422 and "ya tiene respuesta" in otra.get_data(True)
    assert consultar_valor(app, "SELECT usuario_id FROM bitacora WHERE accion = 'reclamacion_respondida' "
                                "AND tabla_afectada = 'bitacora' AND registro_id = %s", (hoja_id,)) == 2
    assert texto in turista.get(f"/libro-de-reclamaciones/{numero}").get_data(True)


@pytest.mark.parametrize("usuario", ["guia.elena", "capitan.teodoro"])
def test_guia_y_capitan_no_ven_el_libro(app, usuario):
    cliente = app.test_client()
    iniciar_sesion(cliente, usuario)
    assert cliente.get("/panel/reclamaciones").status_code == 403


def test_el_resumen_del_operador_avisa_las_hojas_pendientes(app):
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel").get_data(True)
    assert "Responder las reclamaciones" in html and "hoja(s) del libro de reclamaciones" in html


def test_el_plazo_son_15_dias_habiles():
    assert reclamacion.vence_el(datetime(2026, 11, 2, 10, 0)) == date(2026, 11, 23)   # de lunes a lunes
    assert reclamacion.vence_el(datetime(2026, 11, 6, 18, 0)) == date(2026, 11, 27)   # de viernes a viernes


def test_el_libro_tiene_limite_por_ip(app, cliente, buzon):
    maximo = int(app.config["LIMITE_HOJAS_RECLAMACION"].split()[0])
    codigos = [registrar(cliente, numero_documento=f"7994{i:04d}").status_code for i in range(maximo + 1)]
    assert codigos[:maximo] == [303] * maximo and codigos[-1] == 429
