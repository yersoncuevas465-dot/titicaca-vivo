"""Práctica 13 · Titicaca Vivo en el celular (PM = prueba del móvil).

Que se pueda instalar (manifiesto, íconos que miden lo que dicen, service worker desde la raíz) y
que lo de una persona (su reserva, su sesión, el panel) nunca quede en la caché del celular: el
celular se presta, se pierde, se comparte. Lo que se ve en la pantalla (360 px, toques de 48 px) no
lo mide ninguna de estas: eso se midió en el navegador (parte 1 de la práctica).
"""

import json
import re
from io import BytesIO

import pytest
from PIL import Image

from tests.conftest import iniciar_sesion
from tests.test_accesibilidad import PANEL, PUBLICAS

# Rutas de una persona: datos de su reserva, su sesión o el trabajo del personal.
DE_UNA_PERSONA = ["/panel", "/mi-reserva", "/reservas/", "/entrar", "/salir", "/recuperar", "/api/"]


def _manifiesto(cliente):
    respuesta = cliente.get("/manifest.webmanifest")
    assert respuesta.status_code == 200
    return respuesta, json.loads(respuesta.get_data(True))


def _lista_js(codigo, nombre):
    """Los textos de una lista de JavaScript: const NOMBRE = ["…", "…"];"""
    encontrada = re.search(rf"const {nombre} = \[(.*?)\];", codigo, re.S)
    assert encontrada, f"falta la lista {nombre} en sw.js"
    return re.findall(r'"([^"]*)"', encontrada.group(1))


def test_pm01_el_manifiesto_existe_y_trae_lo_suyo(cliente):
    respuesta, m = _manifiesto(cliente)
    assert respuesta.mimetype == "application/manifest+json"
    assert m["name"].startswith("Titicaca Vivo") and 0 < len(m["short_name"]) <= 12
    assert m["start_url"] == "/" and m["scope"] == "/" and m["display"] == "standalone"
    assert m["lang"].startswith("es") and m["theme_color"] and m["background_color"]


def test_pm02_los_iconos_miden_lo_que_dicen_y_hay_uno_maskable(cliente):
    _, m = _manifiesto(cliente)
    tamanos = set()
    for icono in m["icons"]:
        respuesta = cliente.get(icono["src"])
        assert respuesta.status_code == 200 and icono["type"] == "image/png", icono["src"]
        ancho, alto = Image.open(BytesIO(respuesta.data)).size
        assert f"{ancho}x{alto}" == icono["sizes"], icono["src"]
        tamanos.add(icono["sizes"])
    assert {"192x192", "512x512"} <= tamanos
    assert any("maskable" in icono.get("purpose", "") for icono in m["icons"])


@pytest.mark.parametrize("usuario", [None, "operador"])
def test_pm03_cada_pagina_enlaza_el_manifiesto_y_registra_el_service_worker(cliente, usuario):
    if usuario:
        iniciar_sesion(cliente, usuario)
    faltan = []
    for url in (PANEL[usuario] if usuario else PUBLICAS):
        html = cliente.get(url).get_data(True)
        if ('<link rel="manifest" href="/manifest.webmanifest">' not in html
                or not re.search(r'<script src="/estaticos/js/app\.js[^"]*" defer></script>', html)):
            faltan.append(url)
    assert faltan == []


def test_pm04_el_service_worker_se_sirve_desde_la_raiz_y_sin_cache(cliente):
    respuesta = cliente.get("/sw.js")
    assert respuesta.status_code == 200
    assert respuesta.mimetype in ("application/javascript", "text/javascript")
    assert "no-cache" in respuesta.headers.get("Cache-Control", "")
    assert respuesta.headers.get("Service-Worker-Allowed") == "/"


def test_pm05_lo_de_una_persona_va_solo_por_la_red(cliente):
    sw = cliente.get("/sw.js").get_data(True)
    solo_red = _lista_js(sw, "SOLO_RED")
    assert all(ruta in solo_red for ruta in DE_UNA_PERSONA), solo_red
    assert 'ruta.endsWith("/reservar")' in sw                  # el formulario de reserva, también
    al_instalar = _lista_js(sw, "AL_INSTALAR")
    publicas = _lista_js(sw, "PUBLICAS")
    for ruta in al_instalar + publicas:                          # nada de una persona en la caché
        assert not any(ruta.startswith(p) for p in DE_UNA_PERSONA), ruta
    assert 'no-store|private' in sw                              # y lo que el servidor marca, tampoco


def test_pm06_sin_red_hay_una_pantalla_sin_conexion_guardada_al_instalar(cliente):
    respuesta = cliente.get("/sin-conexion")
    assert respuesta.status_code == 200 and "Sin conexión" in respuesta.get_data(True)
    sw = cliente.get("/sw.js").get_data(True)
    assert "/sin-conexion" in _lista_js(sw, "AL_INSTALAR")


def test_pm07_con_la_sesion_abierta_ninguna_pagina_se_puede_guardar(cliente):
    assert "no-store" not in cliente.get("/").headers.get("Cache-Control", "")      # la portada sí
    iniciar_sesion(cliente, "operador")
    for url in ("/", "/salidas", "/panel", "/panel/pagos"):
        assert "no-store" in cliente.get(url).headers.get("Cache-Control", ""), url
