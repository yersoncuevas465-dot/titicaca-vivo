"""Práctica 14 · listo para la nube (PN = prueba de nube). Se escribieron antes del cambio.

En Render la app corre detrás de un proxy con https, el puerto lo pone la plataforma (PORT) y
las claves salen de variables del panel. Estas pruebas dicen qué tiene que cumplir el código.
"""

import re
from pathlib import Path

import bcrypt

from app import bd, crear_app
from app.config import ConfigPruebas
from tests.conftest import consultar_valor, ejecutar_y_confirmar, token_csrf

RAIZ = Path(__file__).resolve().parent.parent
CODIGO = "TV-33VR"                       # reserva pagada de la semilla (USUARIOS_DEMO.txt)


class ConfigNube(ConfigPruebas):
    """Como en Render: producción, https y un proxy delante."""

    SESSION_COOKIE_SECURE = True
    PROXY_SALTOS = 1


def _intento_fallido(cliente, ip):
    cabecera = {"X-Forwarded-For": ip}
    token = token_csrf(cliente.get(f"/mi-reserva?codigo={CODIGO}", headers=cabecera))
    return cliente.post("/mi-reserva", headers=cabecera, data={
        "csrf_token": token, "codigo": CODIGO, "numero_documento": "40990000"}).status_code


def test_pn01_el_puerto_sale_de_la_variable_port():
    from servidor import puerto_de

    assert puerto_de({"PORT": "10000"}) == 10000
    assert puerto_de({}) == 8080                      # en la laptop, como siempre


def test_pn02_salud_responde_200_con_la_base(cliente):
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200


def test_pn03_en_produccion_la_cookie_va_con_secure_y_se_manda_hsts(app):
    nube = crear_app(ConfigNube).test_client()
    respuesta = nube.get("/", base_url="https://localhost")
    assert "max-age=" in respuesta.headers.get("Strict-Transport-Security", "")
    assert crear_app(ConfigNube).config["SESSION_COOKIE_SECURE"] is True


def test_pn04_detras_del_proxy_cada_turista_tiene_su_propio_freno(app):
    # Sin leer X-Forwarded-For, todos llegan con la IP del proxy de Render: 10 fallos de uno
    # frenarían a todos (también al docente). Con PROXY_SALTOS=1 cuenta la IP de cada uno.
    nube = crear_app(ConfigNube).test_client()
    for _ in range(10):
        assert _intento_fallido(nube, "203.0.113.7") == 401
    assert _intento_fallido(nube, "203.0.113.7") == 429      # el atacante queda frenado
    assert _intento_fallido(nube, "198.51.100.20") == 401     # otra persona, no


def test_pn05_sin_proxy_declarado_no_se_cree_en_x_forwarded_for(cliente):
    # En la laptop (PROXY_SALTOS=0) cambiar la cabecera no sirve para saltarse el freno.
    for i in range(10):
        assert _intento_fallido(cliente, f"203.0.113.{i}") == 401
    assert _intento_fallido(cliente, "198.51.100.20") == 429


def test_pn06_clave_demo_cambia_la_de_todas_las_cuentas(app, monkeypatch):
    # Las claves de USUARIOS_DEMO.txt están en el repositorio: en internet se cambian todas por
    # la de la variable CLAVE_DEMO, que solo conoce el equipo (y el docente, por privado).
    with app.app_context(), bd.transaccion() as cur:
        cur.execute("SELECT id, hash_contrasena FROM usuario")
        antes = cur.fetchall()
    monkeypatch.setenv("CLAVE_DEMO", "Lago-Puno-2026-nube")
    resultado = app.test_cli_runner().invoke(args=["usuarios", "clave-demo"])
    try:
        assert resultado.exit_code == 0, resultado.output
        guardado = consultar_valor(app, "SELECT hash_contrasena AS h FROM usuario "
                                        "WHERE nombre_usuario = 'admin'").encode()
        assert bcrypt.checkpw(b"Lago-Puno-2026-nube", guardado)
        assert consultar_valor(app, "SELECT COUNT(DISTINCT hash_contrasena) AS n FROM usuario") == 1
    finally:                                         # las demás pruebas usan las claves de siempre
        for fila in antes:
            ejecutar_y_confirmar(app, "UPDATE usuario SET hash_contrasena = %s WHERE id = %s",
                                 (fila["hash_contrasena"], fila["id"]))


def test_pn07_env_example_nombra_cada_variable_que_lee_el_codigo():
    leidas = set(re.findall(r'os\.getenv\("([A-Z_]+)"', (RAIZ / "app" / "config.py").read_text("utf-8")))
    leidas |= {"PORT", "CLAVE_DEMO"}
    ejemplo = (RAIZ / ".env.example").read_text("utf-8")
    nombradas = set(re.findall(r"^([A-Z_]+)=", ejemplo, re.M))
    assert leidas <= nombradas, sorted(leidas - nombradas)


def test_pn08_el_arranque_en_la_nube_escucha_en_0000_y_en_port():
    arranque = (RAIZ / "scripts" / "nube_arrancar.sh").read_text("utf-8")
    assert '--bind "0.0.0.0:${PORT' in arranque
    assert "gunicorn" in (RAIZ / "requirements.txt").read_text("utf-8")
