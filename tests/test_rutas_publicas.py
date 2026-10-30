"""Páginas públicas (F3): portada, salidas, detalle, comunidades y alertas."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import ejecutar_y_confirmar


def hoy():
    return datetime.now(ZoneInfo("America/Lima")).date()


def enlaces_a_salidas(html):
    return {int(n) for n in re.findall(r'href="/salidas/(\d+)"', html)}


def test_portada_muestra_datos_de_la_base(cliente):
    html = cliente.get("/").get_data(True)
    assert "Salidas de hoy" in html
    assert "Oleaje fuerte en el sector de Amantaní" in html          # alerta vigente
    for nombre in ("Uros", "Taquile", "Amantaní", "Llachón", "Luquina Chico", "Ticonata"):
        assert nombre in html
    assert "Uros, Amantaní y Taquile" in html and "desde" in html     # rutas con precio
    assert 'class="mapa__svg"' in html
    assert len(set(re.findall(r'href="/comunidades/([a-z-]+)"', html))) == 6


def test_salidas_por_defecto_muestra_las_de_hoy(cliente):
    html = cliente.get("/salidas").get_data(True)
    assert enlaces_a_salidas(html) == {6, 7, 8}
    assert 'aria-current="date"' in html


def test_salidas_de_manana_y_filtro_por_ruta(cliente):
    manana = (hoy() + timedelta(days=1)).isoformat()
    assert enlaces_a_salidas(cliente.get(f"/salidas?fecha={manana}").get_data(True)) == {9, 10, 11}
    filtrado = cliente.get(f"/salidas?fecha={manana}&ruta=URO-TAQ").get_data(True)
    assert enlaces_a_salidas(filtrado) == {10}


def test_salida_afectada_por_alerta_queda_marcada(cliente):
    manana = (hoy() + timedelta(days=1)).isoformat()
    html = cliente.get(f"/salidas?fecha={manana}").get_data(True)
    assert html.count("Hay una alerta en el lago para este horario") == 1   # solo la salida 9


def test_las_salidas_canceladas_no_se_listan(cliente):
    ayer = (hoy() - timedelta(days=1)).isoformat()
    assert 5 not in enlaces_a_salidas(cliente.get(f"/salidas?fecha={ayer}").get_data(True))


@pytest.mark.parametrize("consulta, campo", [
    ("fecha=21-10-2026", "fecha"),          # formato equivocado
    ("fecha=2099-01-01", "fecha"),          # más de un año
    ("ruta=NO-EXISTE", "ruta"),             # ruta fuera de la lista blanca
])
def test_filtro_invalido_da_422_con_el_error_junto_al_campo(cliente, consulta, campo):
    respuesta = cliente.get(f"/salidas?{consulta}")
    html = respuesta.get_data(True)
    assert respuesta.status_code == 422
    assert f'id="{campo}-error"' in html and 'aria-invalid="true"' in html
    assert enlaces_a_salidas(html) == {6, 7, 8}       # igual muestra las salidas reales de hoy


def test_detalle_de_salida(cliente):
    html = cliente.get("/salidas/10").get_data(True)
    assert html.index(">Uros<") < html.index(">Taquile<")            # paradas en orden
    assert "S/ 80.00" in html and "S/ 120.00" in html                  # tarifas URO-TAQ 2026
    assert 'href="/salidas/10/reservar"' in html                       # botón "Reservar" (F4)


def test_detalle_de_salida_suspendida_muestra_motivo_y_alerta(cliente):
    html = cliente.get("/salidas/9").get_data(True)
    assert "Salida suspendida:" in html
    assert "Alertas que afectan esta salida" in html


def test_salida_inexistente_da_404(cliente):
    assert cliente.get("/salidas/99999").status_code == 404
    assert cliente.get("/salidas/abc").status_code == 404


def test_comunidades_lista_y_mapa(cliente):
    html = cliente.get("/comunidades").get_data(True)
    assert html.count('class="comunidad-tarjeta comunidad-tarjeta--fila"') == 6
    assert 'class="mapa__svg"' in html


def test_ficha_de_comunidad_sin_datos_personales(cliente):
    html = cliente.get("/comunidades/amantani").get_data(True)
    for familia in ("Familia Quispe Cruz", "Familia Mamani Yucra", "Familia Huatta Calsin",
                    "Familia Pacompía Ccalla"):
        assert familia in html
    assert "Familia Cari Tito" not in html          # inactiva
    assert "Celestino" not in html                   # responsable: dato personal
    assert "900000301" not in html                   # teléfono: dato personal
    assert "Taller textil" in html
    assert enlaces_a_salidas(html) == {9, 12}        # próximas salidas que pasan por Amantaní


def test_comunidad_inexistente_o_inactiva_da_404(app, cliente):
    assert cliente.get("/comunidades/no-existe").status_code == 404
    ejecutar_y_confirmar(app, "UPDATE comunidad SET activa = 0 WHERE slug = 'ticonata'")
    try:
        assert cliente.get("/comunidades/ticonata").status_code == 404
    finally:
        ejecutar_y_confirmar(app, "UPDATE comunidad SET activa = 1 WHERE slug = 'ticonata'")


def test_alertas_en_tres_grupos(cliente):
    html = cliente.get("/alertas").get_data(True)
    vigentes, proximas, pasadas = (html.index(t) for t in ("Vigentes ahora", "Próximas", "De los últimos 30 días"))
    assert vigentes < html.index("Oleaje fuerte") < proximas
    assert proximas < html.index("Fiesta comunal en Llachón") < pasadas
    assert pasadas < html.index("Tormenta eléctrica sobre el lago")


URLS_PUBLICAS = ["/", "/salidas", "/salidas/10", "/comunidades", "/comunidades/amantani", "/alertas"]


@pytest.mark.parametrize("url", URLS_PUBLICAS)
def test_paginas_publicas_pesan_menos_de_100_kb(cliente, url):
    html = cliente.get(url).get_data()
    recursos = set(re.findall(rb'(?:href|src|srcset)="(/estaticos/[^"?]+)', html))
    # Sección 11: cada página pesa 100 KB o menos SIN contar las fotos (que además cargan diferidas)
    recursos = {r for r in recursos if b"/img/comunidades/" not in r}
    peso = len(html) + sum(len(cliente.get(r.decode()).get_data()) for r in recursos)
    assert peso < 100 * 1024, (url, peso)


@pytest.mark.parametrize("url", URLS_PUBLICAS)
def test_paginas_publicas_sin_estilos_ni_scripts_en_linea(cliente, url):
    html = cliente.get(url).get_data(True)
    assert " style=" not in html and "<style" not in html and "<script" not in html
    assert '<html lang="es">' in html


def test_hoy_en_lima_no_depende_de_la_pc(app):
    from app.rutas.publico import hoy_en_lima

    with app.test_request_context():
        assert isinstance(hoy_en_lima(), date)
        assert hoy_en_lima() == hoy()
