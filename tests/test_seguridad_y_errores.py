"""Cabeceras de seguridad, páginas de error sin trazas, /salud, registro y peso de página."""

import logging
import re

from app import crear_app
from app.config import ConfigPruebas
from tests.conftest import iniciar_sesion


def test_cabeceras_de_seguridad_en_todas_las_paginas(cliente):
    for url in ("/", "/entrar", "/no-existe", "/salud"):
        cabeceras = cliente.get(url).headers
        assert "default-src 'self'" in cabeceras["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in cabeceras["Content-Security-Policy"]
        assert cabeceras["X-Frame-Options"] == "DENY"
        assert cabeceras["X-Content-Type-Options"] == "nosniff"


def test_las_plantillas_no_usan_estilos_ni_scripts_en_linea(cliente):
    # La CSP los bloquearía: todo debe venir de archivos propios. Un <script src="/estaticos/...">
    # propio sí vale (el del panel avisa antes del cierre por inactividad, D-110).
    iniciar_sesion(cliente, "admin")
    for url in ("/", "/entrar", "/recuperar", "/panel", "/panel/bitacora", "/panel/mi-cuenta",
                "/no-existe"):
        html = cliente.get(url).get_data(True)
        assert " style=" not in html and "<style" not in html, url
        for etiqueta in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S):
            assert etiqueta.strip() == "", url                       # nada de código en línea
        scripts = re.findall(r"<script\b([^>]*)>", html)
        assert all(re.search(r'\bsrc="/estaticos/js/', s) for s in scripts), url
        assert "http://" not in html and "https://" not in html, url   # nada externo (CDN)


def test_pagina_404_propia_en_espanol(cliente):
    respuesta = cliente.get("/esto-no-existe")
    html = respuesta.get_data(True)
    assert respuesta.status_code == 404
    assert '<html lang="es">' in html
    assert "No encontramos la página" in html


def test_pagina_500_sin_trazas_y_queda_en_el_registro(caplog):
    app = crear_app(ConfigPruebas)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/romper")
    def romper():
        raise RuntimeError("detalle interno que el usuario no debe ver")

    with caplog.at_level(logging.ERROR):
        respuesta = app.test_client().get("/romper")
    html = respuesta.get_data(True)
    assert respuesta.status_code == 500
    assert "Algo salió mal" in html
    assert "Traceback" not in html and "detalle interno" not in html
    assert "detalle interno" in caplog.text                         # el detalle va al log


def test_salud_responde_ok_con_la_hora_de_lima(cliente):
    respuesta = cliente.get("/salud")
    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    assert datos["ok"] is True
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d-05:00", datos["hora"])
    assert set(datos) == {"ok", "hora"}


def test_salud_da_503_si_la_base_no_responde():
    class ConfigSinBase(ConfigPruebas):
        BD_PUERTO = 1                                              # nada escucha en el puerto 1

    respuesta = crear_app(ConfigSinBase).test_client().get("/salud")
    datos = respuesta.get_json()
    assert respuesta.status_code == 503
    assert datos["ok"] is False
    assert datos["hora"].endswith("-05:00")


def test_en_produccion_la_cookie_lleva_secure():
    class ConfigProduccionPrueba(ConfigPruebas):
        ENTORNO = "produccion"
        SESSION_COOKIE_SECURE = True

    cliente = crear_app(ConfigProduccionPrueba).test_client()
    respuesta = iniciar_sesion(cliente, "operador")
    assert "Secure" in respuesta.headers["Set-Cookie"]


def test_sin_secret_key_la_app_no_arranca():
    class ConfigSinClave(ConfigPruebas):
        SECRET_KEY = None

    try:
        crear_app(ConfigSinClave)
    except RuntimeError as error:
        assert "SECRET_KEY" in str(error)
    else:
        raise AssertionError("La app arrancó sin SECRET_KEY")


def test_registro_escribe_en_hora_de_lima(tmp_path):
    class ConfigConLog(ConfigPruebas):
        LOG_ARCHIVO = tmp_path / "app.log"

    app = crear_app(ConfigConLog)
    for manejador in app.logger.handlers:
        manejador.flush()
    texto = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "Arranque de Titicaca Vivo" in texto
    assert re.search(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d-0500 ", texto, re.M)
    for manejador in list(app.logger.handlers):                      # soltar el archivo (Windows)
        manejador.close()
        app.logger.removeHandler(manejador)


def test_la_pagina_de_entrar_pesa_menos_de_100_kb(cliente):
    html = cliente.get("/entrar").get_data()
    recursos = re.findall(rb'(?:href|src|srcset)="(/estaticos/[^"?]+)', html)
    peso = len(html) + sum(len(cliente.get(r.decode()).get_data()) for r in set(recursos))
    assert peso < 100 * 1024, peso


def test_estaticos_llevan_version_y_en_produccion_se_guardan_un_dia(cliente):
    html = cliente.get("/").get_data(True)
    assert "/estaticos/css/estilos.css?v=" in html

    class ConfigProduccionPrueba(ConfigPruebas):
        SEND_FILE_MAX_AGE_DEFAULT = 86400

    respuesta = crear_app(ConfigProduccionPrueba).test_client().get("/estaticos/css/estilos.css")
    assert "max-age=86400" in respuesta.headers["Cache-Control"]
