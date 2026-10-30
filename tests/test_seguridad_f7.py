"""F7 · Seguridad (sección 11), revisada en TODA la aplicación y no página por página:
CSRF en cada POST, cada página del panel pide sesión, cabeceras, XSS escapado, SQL sin
texto del usuario, cookies y secretos fuera del repositorio."""

import ast
import re
from pathlib import Path

import pytest

from app.modelos import alerta, resena
from app.servicios.textos import t
from tests.conftest import actor, consultar_valor, ejecutar_y_confirmar, iniciar_sesion, reservar_en

RAIZ = Path(__file__).resolve().parent.parent
VALORES = {"int": "1", "codigo": "TV-WWUQ", "nombre": "rutas", "accion": "suspender",
           "decision": "publicada"}


def url_de_ejemplo(regla):
    """Arma una URL de la regla con valores de ejemplo en sus partes variables (<int:id>...)."""
    def reemplazar(encontrado):
        convertidor, _, nombre = encontrado.group(1).rpartition(":")
        if convertidor.startswith("any("):
            return convertidor[4:].split(",")[0].strip()
        return VALORES["int"] if convertidor == "int" else VALORES.get(nombre, "x")
    return re.sub(r"<([^>]+)>", reemplazar, regla.rule)


def reglas_post(app):
    return [r for r in app.url_map.iter_rules() if "POST" in r.methods]


def test_todo_post_sin_token_csrf_da_400(app, cliente):
    """Sección 11: CSRF en todos los formularios. Se prueba CADA ruta POST de la app."""
    iniciar_sesion(cliente, "operador")
    reglas = reglas_post(app)
    assert len(reglas) >= 25
    sin_csrf = {r.rule: cliente.post(url_de_ejemplo(r), data={}).status_code for r in reglas}
    assert set(sin_csrf.values()) == {400}, sin_csrf


def test_toda_pagina_del_panel_pide_sesion(app, cliente):
    """Si una ruta del panel olvidara @requiere_rol, aquí respondería 200 sin sesión."""
    reglas = [r for r in app.url_map.iter_rules()
              if r.rule.startswith("/panel") and "GET" in r.methods]
    assert len(reglas) >= 25
    for regla in reglas:
        respuesta = cliente.get(url_de_ejemplo(regla))
        assert respuesta.status_code == 302 and "/entrar?next=" in respuesta.headers["Location"], regla.rule


@pytest.mark.parametrize("url", ["/", "/salidas/10", "/idioma/en", "/mi-reserva", "/no-existe",
                                 "/salud", "/estaticos/css/estilos.css"])
def test_cabeceras_de_seguridad_tambien_en_errores_y_estaticos(cliente, url):
    cabeceras = cliente.get(url).headers
    assert "default-src 'self'" in cabeceras["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in cabeceras["Content-Security-Policy"]
    assert cabeceras["X-Frame-Options"] == "DENY"
    assert cabeceras["X-Content-Type-Options"] == "nosniff"


def test_el_pdf_con_datos_personales_no_se_guarda_en_cache(cliente):
    iniciar_sesion(cliente, "operador")
    respuesta = cliente.get("/panel/salidas/8/pasajeros?formato=pdf")
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"


def test_la_cookie_de_sesion_es_httponly_y_samesite(cliente):
    respuesta = iniciar_sesion(cliente, "operador")
    cookie = respuesta.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


# --- XSS: lo que escribe una persona se muestra escapado ---------------------------------------

def test_comentario_con_script_se_muestra_escapado(app, cliente, salida_prueba):
    salida_id = salida_prueba(ruta_id=5, dias=20)
    codigo = reservar_en(app, salida_id)
    ejecutar_y_confirmar(app, "UPDATE reserva SET estado = 'abordada' WHERE codigo = %s", (codigo,))
    ejecutar_y_confirmar(app, "UPDATE salida SET fecha_hora_zarpe = NOW() - INTERVAL 1 DAY, "
                              "fecha_hora_retorno = NOW() - INTERVAL 20 HOUR WHERE id = %s", (salida_id,))
    ataque = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    with app.app_context():
        resena.crear(codigo, 5, ataque)
        resena_id = consultar_valor(app, "SELECT re.id FROM resena re JOIN reserva r "
                                         "ON r.id = re.reserva_id WHERE r.codigo = %s", (codigo,))
        resena.moderar(actor(2), resena_id, "publicada")
    try:
        iniciar_sesion(cliente, "operador")
        for url in ("/panel/resenas", f"/salidas/{salida_id}"):
            html = cliente.get(url).get_data(True)
            assert "&lt;script&gt;" in html and "<script>alert" not in html, url
            assert "<img src=x" not in html
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM resena WHERE id = %s", (resena_id,))


def test_titulo_de_alerta_con_html_se_muestra_escapado(app, cliente):
    import datetime as dt

    datos = {"tipo": "otro", "nivel": "verde", "fuente": "Agencia", "titulo": "<b>Ojo</b> en el muelle",
             "comunidad_id": None, "vigente_desde": dt.datetime(2020, 1, 1),
             "vigente_hasta": dt.datetime(2099, 1, 1)}
    with app.app_context():
        alerta_id = alerta.guardar(actor(2), None, datos)
    try:
        html = cliente.get("/alertas").get_data(True)
        assert "&lt;b&gt;Ojo&lt;/b&gt;" in html and "<b>Ojo</b>" not in html
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM alerta_lago WHERE id = %s", (alerta_id,))


def test_los_valores_dentro_de_t_se_escapan(app):
    with app.test_request_context():
        assert str(t("Vista de {nombre}", nombre="<b>Uros</b>")) == "Vista de &lt;b&gt;Uros&lt;/b&gt;"


# --- SQL: siempre con parámetros; nunca texto del usuario dentro del SQL ----------------------

FUNCIONES_SQL = {"execute", "executemany", "consultar", "consultar_uno"}
PERMITIDOS_EN_FSTRING = {"marcas", "nombre", "tabla", "consulta"}   # marcas %s o nombres validados


def test_ningun_sql_lleva_texto_del_usuario():
    """Sección 17: "nada de f-strings con datos". Toda consulta del código de la app es un texto
    fijo con %s; las pocas f-strings solo meten MARCAS (%s, %s...) o nombres de la lista blanca."""
    hallazgos = []
    for archivo in (RAIZ / "app").rglob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Call) and nodo.args):
                continue
            funcion = getattr(nodo.func, "attr", None) or getattr(nodo.func, "id", None)
            if funcion not in FUNCIONES_SQL:
                continue
            primero = nodo.args[0]
            if isinstance(primero, ast.JoinedStr):
                nombres = {n.id for v in primero.values if isinstance(v, ast.FormattedValue)
                           for n in ast.walk(v.value) if isinstance(n, ast.Name)}
                if not nombres <= PERMITIDOS_EN_FSTRING:
                    hallazgos.append(f"{archivo.name}:{nodo.lineno} {nombres}")
            elif isinstance(primero, ast.BinOp):            # "SELECT ..." % valor o "..." + valor
                hallazgos.append(f"{archivo.name}:{nodo.lineno} arma el SQL con + o %")
    assert hallazgos == []


# --- Secretos ------------------------------------------------------------------------------------

def test_el_env_de_ejemplo_no_trae_secretos():
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    valores = dict(linea.split("=", 1) for linea in ejemplo.splitlines()
                   if "=" in linea and not linea.startswith("#"))
    assert valores["SECRET_KEY"] == "" and valores["BD_CONTRASENA"] == ""
    assert ".env\n" in (RAIZ / ".gitignore").read_text(encoding="utf-8")


def test_no_hay_contrasenas_escritas_en_el_codigo():
    claves_demo = ("Admin-Titicaca26", "Operador-Titicaca26", "Guia-Titicaca26", "Capitan-Titicaca26")
    for archivo in (RAIZ / "app").rglob("*"):
        if archivo.suffix in (".py", ".html", ".js", ".sql"):
            texto = archivo.read_text(encoding="utf-8")
            assert not any(c in texto for c in claves_demo), archivo
