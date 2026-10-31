"""F7 · Accesibilidad (sección 11): labels en todos los campos, errores junto al campo y resumen
arriba, lang, uso con teclado. Se revisa el HTML de cada página con html.parser de Python
(sin dependencias nuevas). Lo que no se puede revisar así (contraste, foco visible, orden real
del teclado) se revisó a mano: ver docs/fase-7-calidad.md."""

import re
from html.parser import HTMLParser

import pytest

from tests.conftest import iniciar_sesion, token_csrf

CONTROLES = {"input", "select", "textarea"}
SIN_ETIQUETA = {"hidden", "submit", "button", "reset", "image"}


class Auditor(HTMLParser):
    """Junta lo necesario para revisar una página: idioma, títulos, campos, etiquetas, ids..."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.titulos = []                 # niveles de h1..h6 en orden
        self.controles = []               # (etiqueta, atributos, dentro_de_label)
        self.labels_for = set()
        self.ids = []
        self.imagenes_sin_alt = []
        self.tabindex_positivo = []
        self.referencias = []             # ids que se nombran en aria-labelledby/-describedby/for
        self.enlaces_vacios = []
        self.botones_vacios = []
        self.tablas_sin_th = 0
        self._labels_abiertos = 0
        self._pila = []                   # [etiqueta, atributos, texto] de <a> y <button> abiertos
        self._tablas = []                 # cantidad de <th> de cada tabla abierta

    def handle_starttag(self, etiqueta, atributos):
        a = dict(atributos)
        if etiqueta == "html":
            self.lang = a.get("lang")
        if re.fullmatch(r"h[1-6]", etiqueta):
            self.titulos.append(int(etiqueta[1]))
        if "id" in a:
            self.ids.append(a["id"])
        for clave in ("aria-labelledby", "aria-describedby"):
            if a.get(clave):
                self.referencias += a[clave].split()
        if a.get("tabindex", "0").lstrip("-").isdigit() and int(a.get("tabindex", "0")) > 0:
            self.tabindex_positivo.append(etiqueta)
        if etiqueta == "label":
            self._labels_abiertos += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if etiqueta in CONTROLES and a.get("type", "text") not in SIN_ETIQUETA:
            self.controles.append((etiqueta, a, self._labels_abiertos > 0))
        if etiqueta == "img" and "alt" not in a:
            self.imagenes_sin_alt.append(a.get("src"))
        if etiqueta == "img" and a.get("alt"):
            for abierto in self._pila:
                abierto[2] += a["alt"]
        if etiqueta in ("a", "button"):
            self._pila.append([etiqueta, a, a.get("aria-label", "")])
        if etiqueta == "table":
            self._tablas.append(0)
        if etiqueta == "th" and self._tablas:
            self._tablas[-1] += 1

    def handle_endtag(self, etiqueta):
        if etiqueta == "label":
            self._labels_abiertos = max(0, self._labels_abiertos - 1)
        if etiqueta in ("a", "button") and self._pila and self._pila[-1][0] == etiqueta:
            nombre, a, texto = self._pila.pop()
            if not texto.strip():
                (self.enlaces_vacios if nombre == "a" else self.botones_vacios).append(a)
        if etiqueta == "table" and self._tablas and self._tablas.pop() == 0:
            self.tablas_sin_th += 1

    def handle_data(self, datos):
        for abierto in self._pila:
            abierto[2] += datos


def problemas(html):
    """Lista de problemas de accesibilidad de una página (vacía = bien)."""
    auditor = Auditor()
    auditor.feed(html)
    errores = []
    if auditor.lang not in ("es", "en"):
        errores.append(f"<html lang> falta o es raro: {auditor.lang}")
    if auditor.titulos.count(1) != 1:
        errores.append(f"debe haber un solo <h1>, hay {auditor.titulos.count(1)}")
    for anterior, actual in zip(auditor.titulos, auditor.titulos[1:], strict=False):
        if actual > anterior + 1:
            errores.append(f"salto de título h{anterior} → h{actual}")
    for etiqueta, a, dentro_de_label in auditor.controles:
        tiene_nombre = (a.get("id") in auditor.labels_for or dentro_de_label
                        or a.get("aria-label") or a.get("aria-labelledby"))
        if not tiene_nombre:
            errores.append(f"<{etiqueta} name={a.get('name')}> sin etiqueta")
        if a.get("aria-invalid") == "true" and not a.get("aria-describedby"):
            errores.append(f"<{etiqueta} name={a.get('name')}> con error sin aria-describedby")
    repetidos = {i for i in auditor.ids if auditor.ids.count(i) > 1}
    if repetidos:
        errores.append(f"ids repetidos: {sorted(repetidos)}")
    rotas = {r for r in auditor.referencias if r not in auditor.ids}
    if rotas:
        errores.append(f"aria-* apunta a ids que no existen: {sorted(rotas)}")
    if auditor.imagenes_sin_alt:
        errores.append(f"<img> sin alt: {auditor.imagenes_sin_alt}")
    if auditor.tabindex_positivo:
        errores.append("tabindex > 0 cambia el orden del teclado")
    if auditor.enlaces_vacios:
        errores.append(f"enlaces sin texto: {[a.get('href') for a in auditor.enlaces_vacios]}")
    if auditor.botones_vacios:
        errores.append("botones sin texto")
    if auditor.tablas_sin_th:
        errores.append("tabla sin encabezados <th>")
    return errores


PUBLICAS = ["/", "/salidas", "/salidas?fecha=mal", "/salidas/10", "/salidas/9", "/comunidades",
            "/comunidades/amantani", "/alertas", "/mi-reserva", "/salidas/10/reservar?acompanantes=2",
            "/entrar", "/recuperar", "/no-existe", "/galeria", "/galeria?idioma=quechua", "/contacto",
            "/privacidad", "/condiciones", "/libro-de-reclamaciones", "/experiencias",
            "/experiencias?actividad=noche", "/grupos"]
PANEL = {
    "operador": ["/panel", "/panel/salidas", "/panel/salidas/nueva", "/panel/salidas/10/editar",
                 "/panel/salidas/10/suspender", "/panel/salidas/8/pasajeros",
                 "/panel/salidas/8/pasajeros?formato=imprimir", "/panel/salidas/8/pasajeros?formato=whatsapp",
                 "/panel/abordaje", "/panel/abordaje/TV-WWUQ", "/panel/pagos", "/panel/alertas",
                 "/panel/alertas/nueva", "/panel/alertas/1", "/panel/hospedajes",
                 "/panel/hospedajes/4/reasignar", "/panel/hospedajes/transparencia", "/panel/resenas",
                 "/panel/indicadores?dias=365", "/panel/catalogos", "/panel/catalogos/familias",
                 "/panel/catalogos/familias/1", "/panel/catalogos/comunidades/nuevo",
                 "/panel/catalogos/rutas/3/paradas", "/panel/mi-cuenta",
                 "/panel/reservas", "/panel/reservas?q=prueba", "/panel/reservas?q=nadie-asi",
                 "/panel/reservas/TV-WWUQ", "/panel/reservas/TV-33VR", "/panel/reservas/TV-TX69",
                 "/salidas/10/reservar?acompanantes=1", "/panel/reclamaciones"],
    "admin": ["/panel/reservas", "/panel/reservas/TV-WWUQ", "/panel/reclamaciones", "/panel/bitacora", "/panel/bitacora?periodo=hoy", "/panel/usuarios",
              "/panel/usuarios/nuevo", "/panel/usuarios/3", "/panel/mi-cuenta", "/panel/respaldos"],
    "capitan.teodoro": ["/panel", "/panel/salidas/13/pasajeros", "/panel/mi-cuenta"],
}


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_paginas_del_turista(cliente, idioma):
    cliente.get(f"/idioma/{idioma}")
    hallazgos = {url: problemas(cliente.get(url).get_data(True)) for url in PUBLICAS}
    assert {u: p for u, p in hallazgos.items() if p} == {}


@pytest.mark.parametrize("usuario", list(PANEL))
def test_paginas_del_panel(cliente, usuario):
    iniciar_sesion(cliente, usuario)
    hallazgos = {url: problemas(cliente.get(url).get_data(True)) for url in PANEL[usuario]}
    assert {u: p for u, p in hallazgos.items() if p} == {}


def test_formulario_con_errores_los_muestra_junto_al_campo_y_arriba(cliente, salida_prueba):
    salida_id = salida_prueba(dias=20)
    pagina = cliente.get(f"/salidas/{salida_id}/reservar?acompanantes=1")
    respuesta = cliente.post(f"/salidas/{salida_id}/reservar", data={
        "csrf_token": token_csrf(pagina), "titular_nombres": "", "titular_numero_documento": "12",
        "acompanantes-0-nombres": ""})
    html = respuesta.get_data(True)
    assert respuesta.status_code == 422
    assert problemas(html) == []
    assert 'class="resumen-errores" role="alert"' in html                         # resumen arriba
    assert re.search(r'aria-invalid="true"[^>]*aria-describedby="[^"]*titular_nombres-error', html) \
        or re.search(r'aria-describedby="[^"]*titular_nombres-error[^"]*"[^>]*aria-invalid="true"', html)
    assert 'id="titular_nombres-error"' in html                                   # junto al campo
    assert 'href="#titular_nombres"' in html                                      # el resumen lleva al campo


def test_formularios_del_panel_con_errores(cliente):
    iniciar_sesion(cliente, "operador")
    pagina = cliente.get("/panel/catalogos/embarcaciones/nuevo")
    html = cliente.post("/panel/catalogos/embarcaciones/nuevo",
                        data={"csrf_token": token_csrf(pagina), "nombre": ""}).get_data(True)
    assert problemas(html) == [] and 'role="alert"' in html


def test_el_auditor_si_encuentra_problemas():
    """El auditor mismo funciona: una página mala tiene que dar errores."""
    malo = ('<html><body><h1>A</h1><h1>B</h1><h4>C</h4><input name="x"><img src="a.png">'
            '<a href="/y"></a><button></button><div id="d"></div><div id="d" tabindex="3"></div>'
            '<table><tr><td>1</td></tr></table></body></html>')
    textos = " ".join(problemas(malo))
    for esperado in ("lang", "un solo <h1>", "h1 → h4", "sin etiqueta", "ids repetidos",
                     "sin alt", "tabindex", "enlaces sin texto", "botones sin texto", "sin encabezados"):
        assert esperado in textos, esperado


def test_el_atributo_hidden_siempre_oculta(cliente):
    """El JS esconde el selector de acompañantes con `hidden`; una clase con display:flex no
    puede volver a mostrarlo (error encontrado en la revisión de la F7)."""
    css = cliente.get("/estaticos/css/estilos.css").get_data(True)
    assert "[hidden] { display: none !important; }" in css
