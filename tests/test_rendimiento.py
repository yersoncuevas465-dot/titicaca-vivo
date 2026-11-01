"""F7 · Rendimiento (sección 11): cada página pesa 100 KB o menos sin contar las fotos, las
consultas principales usan sus índices (EXPLAIN) y las páginas del panel no hacen N+1."""

import posixpath
import re
from urllib.parse import urlsplit

import pymysql
import pytest

from app import bd
from scripts import explicar_consultas
from tests.conftest import iniciar_sesion, reservar_en

LIMITE = 100 * 1024
PUBLICAS = ["/", "/salidas", "/salidas/10", "/comunidades", "/comunidades/amantani", "/alertas",
            "/mi-reserva", "/salidas/10/reservar", "/galeria", "/contacto",
            "/privacidad", "/condiciones", "/libro-de-reclamaciones", "/experiencias", "/grupos",
            "/productos"]
PANEL = {
    "operador": ["/panel", "/panel/salidas", "/panel/salidas/8/pasajeros", "/panel/pagos",
                 "/panel/abordaje/TV-WWUQ", "/panel/alertas", "/panel/alertas/1", "/panel/hospedajes",
                 "/panel/hospedajes/transparencia", "/panel/resenas", "/panel/indicadores?dias=365",
                 "/panel/catalogos/familias", "/panel/catalogos/rutas/3/paradas",
                 "/panel/salidas/8/pasajeros?formato=whatsapp", "/panel/mi-cuenta",
                 "/panel/reservas", "/panel/reservas/TV-33VR", "/salidas/10/reservar",
                 "/panel/reclamaciones", "/panel/productos"],
    "admin": ["/panel/bitacora", "/panel/usuarios", "/panel/usuarios/nuevo", "/panel/respaldos"],
    "residente.juana": ["/panel", "/panel/productos", "/panel/productos/nuevo"],
}


def peso_de(cliente, url):
    """HTML + CSS + JS + SVG/PNG propios que la página pide, SIN las fotos de las comunidades
    ni las de los productos (v2.9): son fotos con loading="lazy", se bajan al llegar a ellas.

    También cuenta las imágenes de fondo que pide el CSS con url(...) (D-106)."""
    respuesta = cliente.get(url)
    assert respuesta.status_code == 200, url
    html = respuesta.get_data()
    recursos = {r.decode() for r in re.findall(rb'(?:src|href)="(/estaticos/[^"]+)"', html)
                if b"/img/comunidades/" not in r and b"/img/productos/" not in r}
    for css in [r for r in recursos if urlsplit(r).path.endswith(".css")]:
        carpeta = posixpath.dirname(urlsplit(css).path)
        for ruta in re.findall(rb'url\("?([^")]+)"?\)', cliente.get(css).get_data()):
            if not ruta.startswith(b"data:"):
                recursos.add(posixpath.normpath(posixpath.join(carpeta, ruta.decode())))
    return len(html) + sum(len(cliente.get(r).get_data()) for r in recursos)


def test_el_peso_cuenta_las_imagenes_de_fondo_del_css(cliente):
    fondos = ["/estaticos/img/fondo-lago.svg", "/estaticos/img/fondo-tejido.svg",
              "/estaticos/img/portada-paisaje.svg", "/estaticos/img/olas.svg"]
    for fondo in fondos:
        assert cliente.get(fondo).status_code == 200, fondo
    solo_html = len(cliente.get("/").get_data())
    assert peso_de(cliente, "/") > solo_html + sum(len(cliente.get(f).get_data()) for f in fondos)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_paginas_del_turista_pesan_100_kb_o_menos(cliente, idioma, capsys):
    cliente.get(f"/idioma/{idioma}")
    pesos = {url: peso_de(cliente, url) for url in PUBLICAS}
    with capsys.disabled():
        print("\n" + "\n".join(f"  {idioma} {url:32} {p / 1024:6.1f} KB" for url, p in pesos.items()))
    assert all(p <= LIMITE for p in pesos.values()), pesos


@pytest.mark.parametrize("usuario", list(PANEL))
def test_paginas_del_panel_pesan_100_kb_o_menos(cliente, usuario, capsys):
    iniciar_sesion(cliente, usuario)
    pesos = {url: peso_de(cliente, url) for url in PANEL[usuario]}
    with capsys.disabled():
        print("\n" + "\n".join(f"  {usuario:8} {url:45} {p / 1024:6.1f} KB" for url, p in pesos.items()))
    assert all(p <= LIMITE for p in pesos.values()), pesos


def test_el_pdf_del_manifiesto_es_liviano(cliente):
    iniciar_sesion(cliente, "operador")
    assert len(cliente.get("/panel/salidas/8/pasajeros?formato=pdf").data) <= LIMITE


# --- EXPLAIN de las 3 consultas más importantes ------------------------------------------------

def test_explain_de_las_3_consultas_principales(app):
    conexion = bd.conectar(app.config)
    try:
        planes = explicar_consultas.explicar(conexion)
    finally:
        conexion.close()
    ocupados, salidas_del_dia, rotacion = planes.values()
    # 1. Contar los ocupados: va directo por el índice (salida_id, estado) y no recorre reservas.
    reserva = next(f for f in ocupados if f["table"] == "r")
    assert reserva["key"] == "ix_reserva_salida_estado" and reserva["type"] == "ref"
    # 2. Salidas del día: la subconsulta de la vista cuenta las reservas de CADA salida por índice.
    assert any(f["key"] == "ix_reserva_salida_estado" for f in salidas_del_dia)
    # 3. Rotación: las familias se buscan por comunidad y sus noches por (familia, noche).
    assert any(f["table"] == "f" and f["key"] == "ix_familia_comunidad" for f in rotacion)
    assert any(f["key"] == "ix_hospedaje_familia_noche" for f in rotacion)


# --- Sin N+1: las consultas no crecen con la cantidad de pasajeros -------------------------------

def contar_consultas(cliente, url, monkeypatch):
    contador = {"n": 0}
    original = pymysql.cursors.Cursor.execute

    def contar(self, consulta, args=None):
        if consulta.lstrip().upper().startswith(("SELECT", "WITH")):
            contador["n"] += 1
        return original(self, consulta, args)

    monkeypatch.setattr(pymysql.cursors.Cursor, "execute", contar)
    try:
        assert cliente.get(url).status_code == 200, url
    finally:
        monkeypatch.setattr(pymysql.cursors.Cursor, "execute", original)
    return contador["n"]


def test_la_lista_de_pasajeros_no_hace_n_mas_1(app, cliente, salida_prueba, monkeypatch):
    chica, grande = salida_prueba(dias=20), salida_prueba(dias=21, cupo=12)
    reservar_en(app, chica)
    for _ in range(3):
        reservar_en(app, grande, acompanantes=2)          # 3 reservas, 9 pasajeros
    iniciar_sesion(cliente, "operador")
    for formato in ("", "?formato=imprimir", "?formato=whatsapp", "?formato=pdf"):
        con_1 = contar_consultas(cliente, f"/panel/salidas/{chica}/pasajeros{formato}", monkeypatch)
        con_9 = contar_consultas(cliente, f"/panel/salidas/{grande}/pasajeros{formato}", monkeypatch)
        assert con_1 == con_9, (formato, con_1, con_9)


@pytest.mark.parametrize("url, maximo", [
    ("/panel/pagos", 5), ("/panel/hospedajes", 4), ("/panel/indicadores?dias=365", 7),
    ("/panel/alertas", 3), ("/panel/resenas", 3), ("/panel/catalogos/familias", 3),
    ("/panel/reservas", 3), ("/panel/reservas?q=prueba", 3), ("/panel/reservas/TV-33VR", 7),
])
def test_paginas_del_panel_con_consultas_fijas(cliente, monkeypatch, url, maximo):
    iniciar_sesion(cliente, "operador")
    assert contar_consultas(cliente, url, monkeypatch) <= maximo
