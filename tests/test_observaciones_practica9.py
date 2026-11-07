"""Lo que observó el docente en la Práctica 9, revisado en las páginas de verdad:

- el menú del operador: tres opciones a la vista (Salidas de hoy, Pagos por verificar, Abordaje)
  y lo demás en «Más»;
- ninguna página muestra códigos internos (RN-, S-), el nombre de la vista, «por confirmar»,
  el código del país ni cifras al estilo inglés (S/ 1,250.00 o 25.0 %).
"""

import re
from html.parser import HTMLParser

import pytest

from tests.conftest import iniciar_sesion
from tests.test_accesibilidad import PANEL, PUBLICAS


class Menu(HTMLParser):
    """Los textos de los enlaces del menú del panel: los de arriba y los que van en «Más»."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.arriba, self.en_mas, self.mas = [], [], None
        self._nav = self._details = self._summary = self._enlace = False

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta == "nav" and dict(atributos).get("aria-label") == "Panel":
            self._nav = True
        elif self._nav and etiqueta == "details":
            self._details, self.mas = True, ""
        elif self._nav and etiqueta == "summary":
            self._summary = True
        elif self._nav and etiqueta == "a":
            self._enlace = True
            (self.en_mas if self._details else self.arriba).append("")

    def handle_endtag(self, etiqueta):
        if etiqueta in ("nav", "details", "summary", "a"):
            atributo = {"nav": "_nav", "details": "_details", "summary": "_summary", "a": "_enlace"}
            setattr(self, atributo[etiqueta], False)

    def handle_data(self, datos):
        if self._enlace:
            lista = self.en_mas if self._details else self.arriba
            lista[-1] += datos.strip()
        elif self._summary:
            self.mas += datos


def menu(cliente, url):
    lector = Menu()
    lector.feed(cliente.get(url).get_data(True))
    return lector


def test_el_operador_ve_tres_opciones_y_lo_demas_en_mas(cliente):
    iniciar_sesion(cliente, "operador")
    lector = menu(cliente, "/panel/salidas")
    assert lector.arriba == ["Salidas de hoy", "Pagos por verificar", "Abordaje"]
    assert lector.en_mas == ["Resumen", "Reservas", "Alertas", "Hospedajes", "Reseñas",
                             "Reclamaciones", "Productos", "Indicadores", "Catálogos", "Mi cuenta"]
    assert lector.mas.strip() == "Más"


def test_mas_dice_en_que_pagina_esta(cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel/reservas").get_data(True)
    assert 'class="subnav__mas-actual">Más: Reservas</summary>' in html
    assert 'aria-current="page">Reservas</a>' in html


@pytest.mark.parametrize(("usuario", "arriba", "en_mas"), [
    ("admin", ["Salidas de hoy", "Pagos por verificar", "Reservas"], {"Usuarios", "Bitácora", "Respaldos"}),
    ("capitan.teodoro", ["Resumen", "Abordaje", "Mi cuenta"], set()),
    ("residente.juana", ["Resumen", "Mis productos", "Mi cuenta"], set()),
])
def test_cada_rol_ve_su_menu_corto(cliente, usuario, arriba, en_mas):
    iniciar_sesion(cliente, usuario)
    lector = menu(cliente, "/panel")
    assert lector.arriba == arriba and en_mas <= set(lector.en_mas)
    assert (lector.mas is None) == (not en_mas)              # sin «Más» si no hay nada que esconder


class Texto(HTMLParser):
    """El texto que se ve en la página: sin <script>, <style> ni atributos."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self._oculto = [], 0

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta in ("script", "style"):
            self._oculto += 1

    def handle_endtag(self, etiqueta):
        if etiqueta in ("script", "style") and self._oculto:
            self._oculto -= 1

    def handle_data(self, datos):
        if not self._oculto:
            self.partes.append(datos)


NO_DEBE_VERSE = {
    "código interno": re.compile(r"\bRN-\d+|\(S-\d+|\bS-\d+:"),
    "nombre de la vista": re.compile(r"v_ingresos_familia"),
    "«por confirmar»": re.compile(r"por confirmar|to be confirmed", re.I),
    "código del país": re.compile(r"Per[uú] = PE"),
    "monto al estilo inglés": re.compile(r"S/\s?\d{1,3}(,\d{3})*\.\d"),
    "porcentaje al estilo inglés": re.compile(r"\d\.\d+\s?%"),
    "dólares con coma de miles": re.compile(r"US\$\s?\d{1,3},\d{3}"),
}


def lo_observado(html):
    lector = Texto()
    lector.feed(html)
    texto = " ".join(" ".join(lector.partes).split())
    return [f"{nombre}: …{texto[max(0, m.start() - 40):m.end() + 20]}…"
            for nombre, patron in NO_DEBE_VERSE.items() if (m := patron.search(texto))]


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_las_paginas_del_turista_no_muestran_lo_observado(cliente, idioma):
    cliente.get(f"/idioma/{idioma}")
    hallazgos = {url: lo_observado(cliente.get(url).get_data(True)) for url in PUBLICAS}
    assert {url: h for url, h in hallazgos.items() if h} == {}


@pytest.mark.parametrize("usuario", list(PANEL))
def test_las_paginas_del_panel_no_muestran_lo_observado(cliente, usuario):
    iniciar_sesion(cliente, usuario)
    hallazgos = {url: lo_observado(cliente.get(url).get_data(True)) for url in PANEL[usuario]}
    assert {url: h for url, h in hallazgos.items() if h} == {}
