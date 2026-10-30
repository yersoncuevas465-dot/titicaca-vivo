"""La cuenta del personal (D-109 a D-115): recuperar la contraseña con un código, Mi cuenta,
regla de contraseña, sesiones que se cierran solas, bitácora por periodo y en CSV, activar o
desactivar con un clic, comandos de consola y las fotos de fondo de cada sección."""

import re
import time
from pathlib import Path

import pytest
from PIL import Image

from app import bd
from app.modelos import cuenta
from app.servicios import correo
from app.servicios.hoja_de_calculo import celda
from tests.conftest import CLAVES, consultar_valor, ejecutar_y_confirmar, iniciar_sesion, token_csrf

RAIZ = Path(__file__).resolve().parent.parent
FONDOS = RAIZ / "app" / "estaticos" / "img" / "fondos"
CLAVE_NUEVA = "Totora-Nueva-2026"


@pytest.fixture(autouse=True)
def cuentas_intactas(app):
    """Estas pruebas cambian contraseñas, correos y estados: al terminar, todo vuelve a la semilla."""
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cur:
            cur.execute("SELECT id, hash_contrasena, correo, telefono, activo FROM usuario")
            semilla = cur.fetchall()
    finally:
        conexion.close()
    yield
    for fila in semilla:
        ejecutar_y_confirmar(app, "UPDATE usuario SET hash_contrasena = %s, correo = %s, telefono = %s, "
                                  "activo = %s WHERE id = %s",
                             (fila["hash_contrasena"], fila["correo"], fila["telefono"], fila["activo"],
                              fila["id"]))


@pytest.fixture
def correos(monkeypatch):
    """Junta los correos «enviados» (nada sale a internet) para leer el código."""
    enviados = []

    def falso(destino, asunto, texto):
        enviados.append({"destino": destino, "asunto": asunto, "texto": texto})
        return correo.SIMULADO

    monkeypatch.setattr(correo, "enviar", falso)
    return enviados


def codigo_de(enviados):
    return re.search(r"\b(\d{6})\b", enviados[-1]["texto"]).group(1)


def token(html, prefijo=""):
    nombre = f"{prefijo}-csrf_token" if prefijo else "csrf_token"
    return re.search(rf'name="{nombre}"[^>]*value="([^"]+)"', html).group(1)


def pedir_codigo(cliente, identificador):
    pagina = cliente.get("/recuperar")
    return cliente.post("/recuperar", data={"csrf_token": token_csrf(pagina),
                                            "identificador": identificador})


def enviar_codigo(cliente, codigo, clave=CLAVE_NUEVA, repetir=None):
    pagina = cliente.get("/recuperar/codigo")
    return cliente.post("/recuperar/codigo", data={
        "csrf_token": token_csrf(pagina), "codigo": codigo, "contrasena": clave,
        "repetir": clave if repetir is None else repetir})


def cuantos(app, accion, usuario_id=None):
    if usuario_id is None:
        return consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE accion = %s", (accion,))
    return consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE accion = %s AND usuario_id = %s",
                           (accion, usuario_id))


# --- Regla de la contraseña (D-113) -----------------------------------------------------------------

@pytest.mark.parametrize("clave, problema", [
    ("", "Escribe"), ("Corta-1", "Al menos 10"), ("x" * 80 + "1", "Máximo 72"),
    ("Lago Titicaca 26", "Sin espacios"), ("SoloLetrasAqui", "letras y números"),
    ("1234567890", "letras y números"), ("aaaa1111aaaa", "fácil"),
    ("operador-2026x", "nombre de usuario"),
])
def test_contrasenas_que_no_sirven(clave, problema):
    assert problema in cuenta.error_contrasena(clave, "operador")


def test_contrasena_que_sirve():
    assert cuenta.error_contrasena(CLAVE_NUEVA, "operador") is None


# --- Recuperar la contraseña con un código (D-111) ----------------------------------------------------

def test_entrar_tiene_el_enlace_y_recuperar_explica_el_modo_demostracion(cliente):
    assert 'href="/recuperar"' in cliente.get("/entrar").get_data(True)
    html = cliente.get("/recuperar").get_data(True)
    assert "Paso 1 de 2" in html and "Modo demostración" in html
    assert '<label class="campo__etiqueta" for="identificador">Usuario o correo</label>' in html


def test_recuperar_la_contrasena_de_punta_a_punta(app, cliente, correos):
    pedidos = cuantos(app, "recuperacion_solicitada", 2)
    respuesta = pedir_codigo(cliente, "operador")
    assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/recuperar/codigo"
    assert correos[-1]["destino"] == "operador@titicaca-vivo.example"
    assert cuantos(app, "recuperacion_solicitada", 2) == pedidos + 1
    codigo = codigo_de(correos)

    cambio = enviar_codigo(cliente, codigo)
    assert cambio.status_code == 303 and cambio.headers["Location"] == "/entrar"
    assert cuantos(app, "contrasena_restablecida", 2) >= 1
    assert iniciar_sesion(app.test_client(), "operador", CLAVE_NUEVA).status_code == 302
    assert iniciar_sesion(app.test_client(), "operador").status_code == 401      # la vieja ya no

    # El mismo código no sirve dos veces: el pedido ya no está en la sesión
    assert cliente.get("/recuperar/codigo").headers["Location"] == "/recuperar"


def test_el_codigo_solo_vale_en_el_navegador_que_lo_pidio(app, cliente, correos):
    pedir_codigo(cliente, "admin@titicaca-vivo.example")          # también con el correo
    codigo = codigo_de(correos)
    otro = app.test_client()
    pedir_codigo(otro, "no.existe")
    assert enviar_codigo(otro, codigo).status_code == 422
    assert enviar_codigo(cliente, codigo).status_code == 303


@pytest.mark.parametrize("identificador", ["no.existe", "guia.marco"])     # sin cuenta / sin correo
def test_misma_respuesta_si_no_hay_cuenta_o_no_tiene_correo(cliente, correos, identificador):
    respuesta = pedir_codigo(cliente, identificador)
    assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/recuperar/codigo"
    assert correos == []
    html = cliente.get("/recuperar/codigo").get_data(True)
    assert "Si los datos son de una cuenta activa con correo" in html
    assert "El código no es correcto." in enviar_codigo(cliente, "123456").get_data(True)


def test_cinco_codigos_equivocados_y_hay_que_pedir_otro(cliente, correos):
    pedir_codigo(cliente, "operador")
    correcto = codigo_de(correos)
    equivocado = f"{(int(correcto) + 1) % 1_000_000:06d}"
    for restantes in (4, 3, 2, 1):
        html = enviar_codigo(cliente, equivocado).get_data(True)
        assert f"Te quedan {restantes} intento(s)." in html
    assert "Ya no quedan intentos" in enviar_codigo(cliente, equivocado).get_data(True)
    respuesta = enviar_codigo(cliente, correcto)                    # ni el correcto pasa ya
    assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/recuperar"


def test_una_contrasena_floja_no_gasta_el_codigo(cliente, correos):
    pedir_codigo(cliente, "operador")
    codigo = codigo_de(correos)
    floja = enviar_codigo(cliente, codigo, clave="corta")
    assert floja.status_code == 422 and "Al menos 10 caracteres" in floja.get_data(True)
    distinta = enviar_codigo(cliente, codigo, repetir="Otra-Clave-2026")
    assert "No coincide con la contraseña nueva." in distinta.get_data(True)
    assert enviar_codigo(cliente, codigo).status_code == 303


def test_el_codigo_vence(cliente, correos):
    pedir_codigo(cliente, "operador")
    with cliente.session_transaction() as sesion:
        sesion["recuperacion"] = {**sesion["recuperacion"], "vence": int(time.time()) - 1}
    respuesta = enviar_codigo(cliente, codigo_de(correos))
    assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/recuperar"
    assert "venció" in cliente.get("/recuperar").get_data(True)


def test_limite_de_pedidos_de_codigo(cliente, correos):
    for _ in range(5):
        assert pedir_codigo(cliente, "no.existe").status_code == 303
    assert pedir_codigo(cliente, "no.existe").status_code == 429


def test_con_sesion_abierta_recuperar_lleva_a_mi_cuenta(cliente):
    iniciar_sesion(cliente, "operador")
    assert cliente.get("/recuperar").headers["Location"] == "/panel/mi-cuenta"


# --- Entrar, salir y la bitácora de las cuentas (D-110, RN-14) ---------------------------------------

def test_se_entra_tambien_con_el_correo(cliente):
    respuesta = iniciar_sesion(cliente, "elena.yucra@titicaca-vivo.example", CLAVES["guia.elena"])
    assert respuesta.status_code == 302 and respuesta.headers["Location"] == "/panel"


def test_avisa_cuantos_intentos_quedan(cliente):
    textos = [iniciar_sesion(cliente, "operador", "mala").get_data(True) for _ in range(5)]
    assert "Te quedan" not in textos[1]
    assert "Te quedan 2 intentos" in textos[2] and "Te queda 1 intento" in textos[3]
    assert "Se bloquearon los ingresos" in textos[4]


def test_un_intento_fallido_queda_en_la_bitacora_sin_lo_escrito(app, cliente):
    antes = cuantos(app, "intento_fallido", 2)
    iniciar_sesion(cliente, "operador", "Clave-Secreta-Escrita-99")
    assert cuantos(app, "intento_fallido", 2) == antes + 1
    detalle = consultar_valor(app, "SELECT detalle FROM bitacora WHERE accion = 'intento_fallido' "
                                   "ORDER BY id DESC LIMIT 1")
    assert "Clave-Secreta" not in detalle and "existe" in detalle


def test_salir_queda_en_la_bitacora(app, cliente):
    antes = cuantos(app, "cierre_sesion", 2)
    iniciar_sesion(cliente, "operador")
    cliente.post("/salir", data={"csrf_token": token_csrf(cliente.get("/panel"))})
    assert cuantos(app, "cierre_sesion", 2) == antes + 1


def test_la_sesion_se_cierra_sola_por_inactividad(app, cliente):
    iniciar_sesion(cliente, "operador")
    assert cliente.get("/panel/sesion").status_code == 204          # «sigo trabajando»
    antes = cuantos(app, "cierre_sesion", 2)
    with cliente.session_transaction() as sesion:
        sesion["ultima_actividad"] = int(time.time()) - 31 * 60
    respuesta = cliente.get("/panel/pagos")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/entrar?next=/panel/pagos"     # vuelve a donde estaba
    assert "minutos sin actividad" in cliente.get("/entrar").get_data(True)
    assert cliente.get("/panel").status_code == 302
    detalle = consultar_valor(app, "SELECT detalle FROM bitacora WHERE accion = 'cierre_sesion' "
                                   "AND usuario_id = 2 ORDER BY id DESC LIMIT 1")
    assert cuantos(app, "cierre_sesion", 2) == antes + 1 and "inactividad" in detalle


def test_la_senal_de_actividad_responde_401_si_la_sesion_ya_se_cerro(cliente):
    iniciar_sesion(cliente, "guia.elena")
    with cliente.session_transaction() as sesion:
        sesion["ultima_actividad"] = int(time.time()) - 31 * 60
    assert cliente.get("/panel/sesion").status_code == 401


def test_el_panel_trae_el_aviso_de_inactividad(cliente):
    iniciar_sesion(cliente, "capitan.teodoro")
    html = cliente.get("/panel").get_data(True)
    assert re.search(r'<script src="/estaticos/js/sesion\.js\?v=[^"]+" defer\s+data-minutos="30" '
                     r'data-url="/panel/sesion"></script>', html)
    assert cliente.get("/estaticos/js/sesion.js").status_code == 200


def test_con_sesion_abierta_ninguna_pagina_queda_en_la_cache(cliente):
    assert "no-store" not in cliente.get("/salidas").headers.get("Cache-Control", "")
    iniciar_sesion(cliente, "operador")
    assert cliente.get("/salidas").headers["Cache-Control"] == "no-store"


# --- Mi cuenta (D-113) --------------------------------------------------------------------------------

@pytest.mark.parametrize("usuario, rol", [("admin", "Administrador"), ("operador", "Operador"),
                                          ("guia.elena", "Guía"), ("capitan.teodoro", "Capitán")])
def test_mi_cuenta_muestra_los_datos_y_lo_que_hace_cada_rol(cliente, usuario, rol):
    iniciar_sesion(cliente, usuario)
    html = cliente.get("/panel/mi-cuenta").get_data(True)
    assert f"<code>{usuario}</code>" in html and rol in html
    assert "Hace" in html and "No hace" in html
    assert "Tus últimos movimientos" in html and "Inicio de sesión" in html
    assert 'href="/panel/mi-cuenta"' in html                         # está en el menú


def test_cambiar_mi_contrasena(app, cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel/mi-cuenta").get_data(True)

    def cambiar(actual, nueva, repetir=None):
        return cliente.post("/panel/mi-cuenta/contrasena", data={
            "clave-csrf_token": token(html, "clave"), "clave-actual": actual, "clave-nueva": nueva,
            "clave-repetir": nueva if repetir is None else repetir})

    mala = cambiar("no-es-la-mia", CLAVE_NUEVA)
    assert mala.status_code == 422 and "No es tu contraseña actual." in mala.get_data(True)
    assert "Combina letras y números" in cambiar(CLAVES["operador"], "solo-letras-aqui").get_data(True)
    assert "No coincide" in cambiar(CLAVES["operador"], CLAVE_NUEVA, "Otra-Clave-2026").get_data(True)

    bien = cambiar(CLAVES["operador"], CLAVE_NUEVA)
    assert bien.status_code == 303 and bien.headers["Location"] == "/panel/mi-cuenta"
    assert cliente.get("/panel").status_code == 200                 # esta sesión sigue
    assert cuantos(app, "contrasena_cambiada", 2) >= 1
    assert iniciar_sesion(app.test_client(), "operador", CLAVE_NUEVA).status_code == 302
    igual = cambiar(CLAVE_NUEVA, CLAVE_NUEVA)
    assert igual.status_code == 422 and "distinta de la actual" in igual.get_data(True)


def test_al_cambiar_la_contrasena_se_cierran_las_otras_sesiones(app):
    en_el_muelle, en_la_oficina = app.test_client(), app.test_client()
    iniciar_sesion(en_el_muelle, "operador")
    iniciar_sesion(en_la_oficina, "operador")
    html = en_la_oficina.get("/panel/mi-cuenta").get_data(True)
    en_la_oficina.post("/panel/mi-cuenta/contrasena", data={
        "clave-csrf_token": token(html, "clave"), "clave-actual": CLAVES["operador"],
        "clave-nueva": CLAVE_NUEVA, "clave-repetir": CLAVE_NUEVA})
    assert en_la_oficina.get("/panel").status_code == 200
    assert en_el_muelle.get("/panel").status_code == 302             # D-112: el sello ya no vale


def test_actualizar_mi_correo_y_celular(app, cliente):
    iniciar_sesion(cliente, "guia.marco")
    html = cliente.get("/panel/mi-cuenta").get_data(True)
    assert "Sin correo" in html

    def guardar(correo_nuevo, telefono="987654321", confirmar=CLAVES["guia.marco"]):
        return cliente.post("/panel/mi-cuenta/contacto", data={
            "contacto-csrf_token": token(html, "contacto"), "contacto-correo": correo_nuevo,
            "contacto-telefono": telefono, "contacto-confirmar": confirmar})

    assert "No es tu contraseña actual." in guardar("marco@example.com", confirmar="mala").get_data(True)
    assert "Escribe un correo válido." in guardar("no-es-correo").get_data(True)
    assert "ya es de otra cuenta" in guardar("admin@titicaca-vivo.example").get_data(True)
    assert "Celular de 9 dígitos" in guardar("marco@example.com", telefono="12").get_data(True)
    assert guardar("Marco@Example.com").status_code == 303
    assert consultar_valor(app, "SELECT correo FROM usuario WHERE id = 4") == "marco@example.com"
    assert cuantos(app, "contacto_actualizado", 4) >= 1


# --- Usuarios: activar o desactivar con un clic (D-114) ----------------------------------------------

def test_desactivar_y_activar_con_un_clic(app, cliente):
    operador = app.test_client()
    iniciar_sesion(operador, "operador")
    iniciar_sesion(cliente, "admin")
    csrf = token_csrf(cliente.get("/panel/usuarios"))
    respuesta = cliente.post("/panel/usuarios/2/desactivar", data={"csrf_token": csrf})
    assert respuesta.status_code == 303
    assert "quedó desactivado" in cliente.get("/panel/usuarios").get_data(True)
    assert operador.get("/panel").status_code == 302                 # pierde la sesión al instante
    assert cuantos(app, "usuario_desactivado") >= 1
    cliente.post("/panel/usuarios/2/activar", data={"csrf_token": csrf})
    assert consultar_valor(app, "SELECT activo FROM usuario WHERE id = 2") == 1


def test_no_se_desactiva_a_si_mismo_ni_a_un_guia_con_salidas(app, cliente):
    iniciar_sesion(cliente, "admin")
    html = cliente.get("/panel/usuarios").get_data(True)
    assert 'action="/panel/usuarios/1/desactivar"' not in html       # sin botón para sí mismo
    csrf = token_csrf(cliente.get("/panel/usuarios"))
    cliente.post("/panel/usuarios/1/desactivar", data={"csrf_token": csrf})
    assert "propio usuario" in cliente.get("/panel/usuarios").get_data(True)
    cliente.post("/panel/usuarios/5/desactivar", data={"csrf_token": csrf})   # Teodoro: 13 y 14
    assert "salida(s) por venir" in cliente.get("/panel/usuarios").get_data(True)
    assert consultar_valor(app, "SELECT activo FROM usuario WHERE id IN (1, 5) AND activo = 0") is None


def test_solo_el_admin_activa_o_desactiva(cliente):
    iniciar_sesion(cliente, "operador")
    csrf = token_csrf(cliente.get("/panel"))
    assert cliente.post("/panel/usuarios/4/desactivar", data={"csrf_token": csrf}).status_code == 403


# --- Bitácora por periodo y en CSV (D-115) ----------------------------------------------------------

def test_la_bitacora_filtra_por_periodo_y_muestra_las_acciones_en_palabras(app, cliente):
    iniciar_sesion(cliente, "admin")
    html_hoy = cliente.get("/panel/bitacora?periodo=hoy").get_data(True)
    total_hoy = int(re.search(r"(\d+) registros", html_hoy).group(1))
    total = int(re.search(r"(\d+) registros", cliente.get("/panel/bitacora").get_data(True)).group(1))
    assert 1 <= total_hoy <= total
    assert "Inicio de sesión" in html_hoy and "hoy" in html_hoy


def test_descargar_la_bitacora_en_csv(app, cliente):
    iniciar_sesion(cliente, "admin")
    antes = cuantos(app, "bitacora_exportada", 1)
    respuesta = cliente.get("/panel/bitacora/exportar?periodo=hoy&tipo=sesiones")
    assert respuesta.status_code == 200 and respuesta.mimetype == "text/csv"
    assert "attachment" in respuesta.headers["Content-Disposition"]
    texto = respuesta.get_data(True)
    assert texto.startswith("﻿Fecha,Hora,Usuario,Acción")
    assert "Inicio de sesión,inicio_sesion" in texto and "cambio_estado" not in texto
    assert cuantos(app, "bitacora_exportada", 1) == antes + 1
    completa = cliente.get("/panel/bitacora/exportar").get_data(True)
    assert "cambio_estado" in completa


@pytest.mark.parametrize("valor, esperado", [("=HYPERLINK(1)", "'=HYPERLINK(1)"), ("+51", "'+51"),
                                              ("-1", "'-1"), ("@x", "'@x"), ("normal", "normal"),
                                              (None, ""), (7, "7")])
def test_el_csv_no_deja_formulas_de_excel(valor, esperado):
    assert celda(valor) == esperado


# --- Comandos de consola -----------------------------------------------------------------------------

def test_flask_usuarios_listar_y_clave(app):
    consola = app.test_cli_runner()
    lista = consola.invoke(args=["usuarios", "listar"])
    assert lista.exit_code == 0 and "guia.marco" in lista.output and "sin correo" in lista.output

    floja = consola.invoke(args=["usuarios", "clave", "admin", "--contrasena", "corta"])
    assert floja.exit_code != 0 and "Al menos 10 caracteres" in floja.output
    nadie = consola.invoke(args=["usuarios", "clave", "no.existe", "--contrasena", CLAVE_NUEVA])
    assert nadie.exit_code != 0 and "No existe el usuario" in nadie.output

    bien = consola.invoke(args=["usuarios", "clave", "admin", "--contrasena", CLAVE_NUEVA])
    assert bien.exit_code == 0 and "Listo" in bien.output
    assert iniciar_sesion(app.test_client(), "admin", CLAVE_NUEVA).status_code == 302
    ip = consultar_valor(app, "SELECT ip FROM bitacora WHERE accion = 'contrasena_restablecida' "
                              "AND usuario_id = 1 ORDER BY id DESC LIMIT 1")
    assert ip == "consola"


def test_flask_correo_probar_en_modo_simulacion(app):
    resultado = app.test_cli_runner().invoke(args=["correo", "probar", "equipo@example.com"])
    assert resultado.exit_code == 0 and "Modo simulación" in resultado.output


# --- Fotos de fondo como marca de agua (D-109) ------------------------------------------------------

@pytest.mark.parametrize("url, foto, autor", [
    ("/", "uros", "Entropy1963"), ("/salidas", "uros", "Entropy1963"),
    ("/comunidades", "taquile", "Alonso Cárdenas"), ("/comunidades/amantani", "amantani", "Pastor3571"),
    ("/comunidades/llachon", "llachon", "Hilda Maria FC"), ("/alertas", "ticonata", "Titico"),
    ("/mi-reserva", "amantani", "Pastor3571"), ("/entrar", "llachon", "Hilda Maria FC"),
])
def test_cada_seccion_tiene_su_foto_de_fondo_con_su_credito(cliente, url, foto, autor):
    html = cliente.get(url).get_data(True)
    assert re.search(rf'<img class="fondo-foto" src="/estaticos/img/fondos/{foto}\.webp\?v=[^"]+" '
                     r'alt="" width="960" height="600" loading="lazy"', html), url
    assert "Foto de fondo:" in html and autor in html


@pytest.mark.parametrize("usuario, url, foto", [
    ("operador", "/panel", "llachon"), ("operador", "/panel/salidas", "uros"),
    ("operador", "/panel/pagos", "luquina-chico"), ("operador", "/panel/hospedajes", "amantani"),
    ("operador", "/panel/resenas", "taquile"), ("operador", "/panel/catalogos", "taquile"),
    ("admin", "/panel/bitacora", "ticonata"), ("guia.elena", "/panel/mi-cuenta", "ticonata"),
])
def test_cada_seccion_del_panel_tiene_su_foto(cliente, usuario, url, foto):
    iniciar_sesion(cliente, usuario)
    assert f"/estaticos/img/fondos/{foto}.webp" in cliente.get(url).get_data(True)


def test_la_pagina_404_no_lleva_foto(cliente):
    assert "fondo-foto" not in cliente.get("/no-existe").get_data(True)


def test_las_fotos_de_fondo_son_livianas_y_solo_para_pantallas_anchas(cliente):
    fotos = sorted(FONDOS.glob("*.webp"))
    assert len(fotos) == 6
    for foto in fotos:
        assert foto.stat().st_size <= 20 * 1024, foto.name
        with Image.open(foto) as imagen:
            assert imagen.size == (960, 600), foto.name
    css = cliente.get("/estaticos/css/estilos.css").get_data(True)
    assert ".fondo-foto { display: none; }" in css                   # en el celular no se ve
    anchas = css.split("@media (min-width: 48em) {", 1)[1]
    assert re.search(r"\.fondo-foto \{\s*display: block;", anchas)  # en pantallas anchas, sí
    # v2.2: más visible en los márgenes (24 %) y tenue detrás de la columna del texto
    # (máscara al 65 % ≈ 16 %), donde el texto suave sigue con contraste AA (D-06).
    foto = anchas.split(".pie .pie__credito", 1)[0]
    assert "opacity: 0.24" in foto
    assert "mask-image: linear-gradient(" in foto and foto.count("rgb(0 0 0 / 0.65)") == 4
