"""/entrar y /salir: CSRF, validación, mensaje genérico, límite de intentos y bitácora."""

import pytest

from app.seguridad import destino_seguro
from tests.conftest import (
    consultar_valor,
    ejecutar_y_confirmar,
    iniciar_sesion,
    token_csrf,
)


def test_formulario_de_entrar_tiene_labels_y_token(cliente):
    respuesta = cliente.get("/entrar")
    html = respuesta.get_data(True)
    assert respuesta.status_code == 200
    assert '<label class="campo__etiqueta" for="nombre_usuario">Usuario o correo</label>' in html
    assert '<label class="campo__etiqueta" for="contrasena">Contraseña</label>' in html
    assert 'href="/recuperar"' in html                     # «¿Olvidaste tu contraseña?» (D-111)
    assert token_csrf(respuesta)
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_post_sin_token_csrf_da_400(cliente):
    respuesta = cliente.post("/entrar", data={"nombre_usuario": "admin", "contrasena": "x"})
    assert respuesta.status_code == 400
    assert "El formulario venció" in respuesta.get_data(True)


def test_campos_vacios_dan_422_con_errores_junto_al_campo_y_resumen(cliente):
    respuesta = iniciar_sesion(cliente, "", "")
    html = respuesta.get_data(True)
    assert respuesta.status_code == 422
    assert 'id="resumen-errores"' in html and 'role="alert"' in html
    assert 'id="nombre_usuario-error">Escribe tu nombre de usuario o tu correo.' in html
    assert 'aria-invalid="true"' in html


@pytest.mark.parametrize("usuario, clave", [
    ("operador", "clave-equivocada"),       # usuario existe, clave mala
    ("no.existe", "Operador-Titicaca26"),   # usuario no existe
    ("operador", "x" * 100),                # más de 72 bytes: bcrypt 5 daría error
])
def test_credenciales_malas_dan_401_con_el_mismo_mensaje(cliente, usuario, clave):
    respuesta = iniciar_sesion(cliente, usuario, clave)
    assert respuesta.status_code == 401
    assert "Usuario o contraseña incorrectos." in respuesta.get_data(True)


def test_usuario_inactivo_no_puede_entrar(app, cliente):
    ejecutar_y_confirmar(app, "UPDATE usuario SET activo = 0 WHERE nombre_usuario = 'guia.marco'")
    try:
        respuesta = iniciar_sesion(cliente, "guia.marco")
        assert respuesta.status_code == 401
        assert "Usuario o contraseña incorrectos." in respuesta.get_data(True)
    finally:
        ejecutar_y_confirmar(app, "UPDATE usuario SET activo = 1 WHERE nombre_usuario = 'guia.marco'")


def test_entrar_bien_redirige_al_panel_y_queda_en_la_bitacora(app, cliente):
    sql_conteo = ("SELECT COUNT(*) AS n FROM bitacora "
                  "WHERE accion = 'inicio_sesion' AND usuario_id = 2")
    antes = consultar_valor(app, sql_conteo)

    respuesta = iniciar_sesion(cliente, "operador")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/panel"
    assert consultar_valor(app, sql_conteo) == antes + 1
    ultimo = consultar_valor(app, "SELECT TIMESTAMPDIFF(SECOND, ultimo_acceso, NOW()) AS s "
                                  "FROM usuario WHERE id = 2")
    assert ultimo is not None and ultimo < 60
    ip = consultar_valor(app, "SELECT ip FROM bitacora WHERE accion = 'inicio_sesion' "
                              "AND usuario_id = 2 ORDER BY id DESC LIMIT 1")
    assert ip == "127.0.0.1"


def test_la_cookie_de_sesion_es_httponly_y_samesite_lax(cliente):
    respuesta = iniciar_sesion(cliente, "operador")
    cookie = respuesta.headers.get("Set-Cookie", "")
    assert "titicaca_sesion=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie                   # en desarrollo no hay HTTPS


def test_vuelve_a_la_pagina_que_pidio_pero_solo_si_es_interna(cliente):
    respuesta = cliente.get("/panel/bitacora")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/entrar?next=%2Fpanel%2Fbitacora"

    assert iniciar_sesion(cliente, "admin", siguiente="/panel/bitacora").headers["Location"] \
        == "/panel/bitacora"


def test_un_next_externo_se_ignora(app):
    cliente = app.test_client()
    respuesta = iniciar_sesion(cliente, "admin", siguiente="https://sitio-falso.example/robar")
    assert respuesta.headers["Location"] == "/panel"


@pytest.mark.parametrize("url, esperado", [
    ("/panel", "/panel"),
    ("/panel/bitacora?pagina=2", "/panel/bitacora?pagina=2"),
    ("//sitio-falso.example", None),
    ("https://sitio-falso.example", None),
    ("/\\sitio-falso.example", None),
    ("panel", None),
    ("", None),
    (None, None),
])
def test_destino_seguro(url, esperado):
    assert destino_seguro(url) == esperado


def test_con_sesion_abierta_entrar_lleva_al_panel(cliente):
    iniciar_sesion(cliente, "operador")
    respuesta = cliente.get("/entrar")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/panel"


def test_limite_de_5_intentos_fallidos(cliente):
    for _ in range(5):
        assert iniciar_sesion(cliente, "operador", "mala").status_code == 401
    bloqueado = iniciar_sesion(cliente, "operador", "mala")
    assert bloqueado.status_code == 429
    assert "Demasiados intentos" in bloqueado.get_data(True)
    # Mientras dura el bloqueo, ni la clave correcta pasa.
    assert iniciar_sesion(cliente, "operador").status_code == 429


def test_los_ingresos_correctos_no_gastan_intentos(cliente):
    for _ in range(6):
        assert iniciar_sesion(cliente, "operador").status_code == 302
        salida = cliente.post("/salir", data={"csrf_token": token_csrf(cliente.get("/panel"))})
        assert salida.status_code == 302


def test_salir_cierra_la_sesion(cliente):
    iniciar_sesion(cliente, "operador")
    token = token_csrf(cliente.get("/panel"))       # el botón "Salir" trae su token
    respuesta = cliente.post("/salir", data={"csrf_token": token})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    assert cliente.get("/panel").status_code == 302


def test_salir_por_get_no_esta_permitido(cliente):
    respuesta = cliente.get("/salir")
    assert respuesta.status_code == 405
    assert "Acción no permitida" in respuesta.get_data(True)


def test_salir_sin_token_csrf_da_400(cliente):
    iniciar_sesion(cliente, "operador")
    assert cliente.post("/salir").status_code == 400
    assert cliente.get("/panel").status_code == 200   # la sesión sigue abierta
