"""Pie de página completo y páginas legales (v2.7): el pie sale en todas las páginas del turista
(también en las de error) y es corto en el panel; las condiciones toman sus números de la
configuración y de los modelos, así nunca dicen algo distinto de lo que hace el sistema."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modelos import abordaje
from tests.conftest import iniciar_sesion
from tests.test_accesibilidad import problemas


@pytest.mark.parametrize("url", ["/", "/salidas", "/galeria", "/contacto", "/mi-reserva", "/no-existe"])
def test_el_pie_completo_sale_en_las_paginas_del_turista(cliente, url):
    html = cliente.get(url).get_data(True)
    pie = html[html.index('<footer class="pie">'):]
    assert 'class="pie__columnas"' in pie
    for enlace in ("/privacidad", "/condiciones", "/contacto", "/galeria", "/mi-reserva"):
        assert f'href="{enlace}"' in pie, (url, enlace)
    assert f"© {datetime.now(ZoneInfo('America/Lima')).year}" in pie


def test_en_el_panel_el_pie_es_corto(app):
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    pie = cliente.get("/panel").get_data(True).split('<footer class="pie">')[1]
    assert 'class="pie__columnas"' not in pie and 'href="/privacidad"' not in pie and "© " in pie


def test_el_pie_muestra_la_atencion_configurada(app, cliente, monkeypatch):
    sin_datos = cliente.get("/").get_data(True).split('<footer class="pie">')[1]
    assert "wa.me" not in sin_datos and "mailto:" not in sin_datos
    monkeypatch.setitem(app.config, "AGENCIA_WHATSAPP", "+51951234567")
    monkeypatch.setitem(app.config, "AGENCIA_CORREO", "reservas@titicaca-vivo.example")
    pie = cliente.get("/").get_data(True).split('<footer class="pie">')[1]
    assert 'href="https://wa.me/51951234567?text=' in pie
    assert 'href="mailto:reservas@titicaca-vivo.example"' in pie


def test_privacidad_y_condiciones(app, cliente):
    privacidad = cliente.get("/privacidad").get_data(True)
    assert "<h1 id=\"titulo-legal\">Política de privacidad</h1>" in privacidad
    assert "Ley N.º 29733" in privacidad and "No usamos cookies de publicidad" in privacidad
    assert problemas(privacidad) == []
    condiciones = cliente.get("/condiciones").get_data(True)
    assert f"guardamos tu lugar {app.config['MINUTOS_VENCIMIENTO_PAGO']} minutos" in condiciones
    assert f"hasta {app.config['MAX_PASAJEROS_POR_RESERVA']} pasajeros" in condiciones
    assert (f"El embarque abre {abordaje.MINUTOS_ANTES} minutos antes del zarpe y cierra "
            f"{abordaje.MINUTOS_DESPUES} minutos después") in condiciones
    assert problemas(condiciones) == []


def test_las_condiciones_siguen_a_la_configuracion(app, cliente, monkeypatch):
    monkeypatch.setitem(app.config, "MINUTOS_VENCIMIENTO_PAGO", 90)
    assert "guardamos tu lugar 90 minutos" in cliente.get("/condiciones").get_data(True)


def test_en_ingles_las_paginas_legales_avisan_que_estan_en_espanol(cliente):
    cliente.get("/idioma/en")
    html = cliente.get("/privacidad").get_data(True)
    assert "Privacy policy" in html and "This text is only available in Spanish." in html
    assert '<div lang="es">' in html and ">Privacy</a>" in html and ">Terms</a>" in html
