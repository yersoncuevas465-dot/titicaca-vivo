"""Rutas de la reserva (F4): formulario, POST→redirect→GET, Mi reserva, boleto y pago."""

import itertools
import re

import pytest

from tests.conftest import consultar_valor, ejecutar_y_confirmar, token_csrf

_documentos = itertools.count(1)


def doc():
    return f"7998{next(_documentos):04d}"


def formulario(cliente, salida_id, acompanantes=0):
    respuesta = cliente.get(f"/salidas/{salida_id}/reservar?acompanantes={acompanantes}")
    html = respuesta.get_data(True)
    token = re.search(r'name="token_envio" type="hidden" value="([0-9a-f]{32})"', html).group(1)
    return respuesta, token_csrf(respuesta), token


def datos_validos(csrf, token, documento=None, metodo="muelle", acompanantes=()):
    datos = {
        "csrf_token": csrf, "token_envio": token,
        "titular_nombres": "Lucía", "titular_apellidos": "Prueba Ruta",
        "titular_tipo_documento": "DNI", "titular_numero_documento": documento or doc(),
        "titular_nacionalidad": "PE", "telefono": "987654321", "correo": "",
        "titular_viaja": "y", "titular_tipo_pasajero_id": "1", "metodo_pago": metodo,
    }
    for i, numero in enumerate(acompanantes):
        datos.update({f"acompanantes-{i}-nombres": "Mateo", f"acompanantes-{i}-apellidos": "Prueba Ruta",
                      f"acompanantes-{i}-tipo_documento": "DNI", f"acompanantes-{i}-numero_documento": numero,
                      f"acompanantes-{i}-nacionalidad": "PE", f"acompanantes-{i}-tipo_pasajero_id": "4"})
    return datos


def reservar(cliente, salida_id, **opciones):
    _, csrf, token = formulario(cliente, salida_id, len(opciones.get("acompanantes", ())))
    return cliente.post(f"/salidas/{salida_id}/reservar", data=datos_validos(csrf, token, **opciones))


# --- Formulario -------------------------------------------------------------------------------------

def test_formulario_de_reserva(cliente, salida_prueba):
    respuesta, _, _ = formulario(cliente, salida_prueba(), acompanantes=2)
    html = respuesta.get_data(True)
    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert html.count('class="pasajero"') == 3                    # 2 acompañantes + la plantilla para JS
    assert '<label class="campo__etiqueta" for="titular_nombres">Nombres</label>' in html
    assert '<datalist id="paises">' in html
    assert re.search(r'<script src="/estaticos/js/reservar\.js\?v=[^"]+" defer></script>', html)
    assert "<script>" not in html                                  # nada de JavaScript en línea (CSP)


def test_la_cantidad_de_acompanantes_tiene_tope(cliente, salida_prueba):
    respuesta, _, _ = formulario(cliente, salida_prueba(), acompanantes=99)
    assert respuesta.get_data(True).count('class="pasajero"') == 9 + 1


def test_salida_que_no_recibe_reservas_da_409(cliente):
    respuesta = cliente.get("/salidas/9/reservar")                 # salida 9: suspendida
    assert respuesta.status_code == 409
    assert "ya no recibe reservas" in respuesta.get_data(True)
    assert cliente.get("/salidas/99999/reservar").status_code == 404


def test_post_sin_csrf_da_400(cliente, salida_prueba):
    assert cliente.post(f"/salidas/{salida_prueba()}/reservar", data={}).status_code == 400


def test_campos_vacios_dan_422_con_resumen(cliente, salida_prueba):
    salida_id = salida_prueba()
    _, csrf, token = formulario(cliente, salida_id)
    respuesta = cliente.post(f"/salidas/{salida_id}/reservar", data={"csrf_token": csrf, "token_envio": token})
    html = respuesta.get_data(True)
    assert respuesta.status_code == 422
    assert 'id="resumen-errores"' in html and "Escribe tus nombres." in html
    assert consultar_valor(cliente.application, "SELECT COUNT(*) AS n FROM reserva WHERE salida_id = %s",
                           (salida_id,)) == 0


def test_regla_de_negocio_invalida_da_422_junto_al_campo(cliente, salida_prueba):
    salida_id = salida_prueba()
    respuesta = reservar(cliente, salida_id, documento="1234567")  # DNI de 7 dígitos (RN-09)
    html = respuesta.get_data(True)
    assert respuesta.status_code == 422
    assert 'id="titular_numero_documento-error">El DNI tiene 8 dígitos.' in html


def test_sin_cupo_da_422_con_el_mensaje(cliente, salida_prueba):
    salida_id = salida_prueba(cupo=1)
    respuesta = reservar(cliente, salida_id, acompanantes=[doc()])
    assert respuesta.status_code == 422
    assert "Solo quedan 1 lugar" in respuesta.get_data(True)


# --- Nivel Oro: POST → redirect → GET, el dato queda y no se duplica --------------------------------

def test_reservar_redirige_y_el_dato_sigue_al_recargar(app, cliente, salida_prueba):
    salida_id = salida_prueba()
    respuesta = reservar(cliente, salida_id, acompanantes=[doc()])
    assert respuesta.status_code == 303
    destino = respuesta.headers["Location"]
    codigo = destino.rsplit("/", 1)[1]
    assert re.fullmatch(r"/reservas/TV-[A-HJKMNP-Z2-9]{4}", destino)
    for _ in range(2):                                            # recargar: sigue ahí
        html = cliente.get(destino).get_data(True)
        assert f"Reserva {codigo}" in html and "Lucía Prueba Ruta" in html
    assert consultar_valor(app, "SELECT estado FROM reserva WHERE codigo = %s", (codigo,)) == "confirmada"


def test_doble_clic_no_duplica_la_reserva(app, cliente, salida_prueba):
    salida_id = salida_prueba()
    _, csrf, token = formulario(cliente, salida_id)
    datos = datos_validos(csrf, token)
    primera = cliente.post(f"/salidas/{salida_id}/reservar", data=datos)
    segunda = cliente.post(f"/salidas/{salida_id}/reservar", data=datos)
    assert primera.status_code == segunda.status_code == 303
    assert primera.headers["Location"] == segunda.headers["Location"]
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM reserva WHERE token_envio = %s", (token,)) == 1


# --- Ver la reserva y "Mi reserva" -------------------------------------------------------------------

def test_otra_persona_ve_los_datos_ocultos(app, cliente, salida_prueba):
    respuesta = reservar(cliente, salida_prueba())
    otra_persona = app.test_client()
    pagina = otra_persona.get(respuesta.headers["Location"])
    html = pagina.get_data(True)
    assert pagina.status_code == 200 and pagina.headers["Cache-Control"] == "no-store"
    assert "Lucía" not in html
    assert "L**** P***** R***" in html                           # "Lucía Prueba Ruta" oculto
    assert "987654321" not in html and "9•••••321" in html


@pytest.mark.parametrize("codigo", ["TV-0000", "XX-ABCD", "TV-ABCDE", "TV-ZZZZ"])
def test_codigo_invalido_o_inexistente_da_404(cliente, codigo):
    assert cliente.get(f"/reservas/{codigo}").status_code == 404


def test_mi_reserva(app, salida_prueba):
    documento = doc()
    codigo = reservar(app.test_client(), salida_prueba(), documento=documento).headers["Location"].rsplit("/", 1)[1]
    cliente = app.test_client()
    csrf = token_csrf(cliente.get("/mi-reserva"))

    mal = cliente.post("/mi-reserva", data={"csrf_token": csrf, "codigo": codigo, "numero_documento": "00000000"})
    assert mal.status_code == 401 and "No encontramos una reserva" in mal.get_data(True)
    formato = cliente.post("/mi-reserva", data={"csrf_token": csrf, "codigo": "123", "numero_documento": "1"})
    assert formato.status_code == 422

    bien = cliente.post("/mi-reserva", data={"csrf_token": csrf, "codigo": codigo.lower(),
                                             "numero_documento": documento})
    assert bien.status_code == 303 and bien.headers["Location"] == f"/reservas/{codigo}"
    assert "Lucía Prueba Ruta" in cliente.get(f"/reservas/{codigo}").get_data(True)


# --- Boleto con QR -----------------------------------------------------------------------------------

def test_boleto_pide_identificarse(app, cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba()).headers["Location"].rsplit("/", 1)[1]
    otra_persona = app.test_client()
    respuesta = otra_persona.get(f"/reservas/{codigo}/boleto")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == f"/mi-reserva?codigo={codigo}"


def test_boleto_html_y_pdf_con_qr(cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba()).headers["Location"].rsplit("/", 1)[1]
    html = cliente.get(f"/reservas/{codigo}/boleto").get_data(True)
    assert '<svg class="qr" role="img"' in html and codigo in html
    assert " style=" not in html
    pdf = cliente.get(f"/reservas/{codigo}/boleto?formato=pdf")
    assert pdf.status_code == 200 and pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF") and len(pdf.data) > 3000


def test_sin_confirmar_no_hay_boleto(cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba(), metodo="yape").headers["Location"].rsplit("/", 1)[1]
    respuesta = cliente.get(f"/reservas/{codigo}/boleto")
    assert respuesta.status_code == 302 and respuesta.headers["Location"] == f"/reservas/{codigo}"


def test_url_del_qr(app):
    from app.servicios import qr

    with app.test_request_context(base_url="http://192.168.1.10:8080"):
        assert qr.url_de_abordaje("TV-RA57") == "http://192.168.1.10:8080/panel/abordaje/TV-RA57"
        app.config["URL_PUBLICA"] = "https://titicacavivo.example/"
        try:
            assert qr.url_de_abordaje("TV-RA57") == "https://titicacavivo.example/panel/abordaje/TV-RA57"
        finally:
            app.config["URL_PUBLICA"] = ""


# --- Reporte de pago ----------------------------------------------------------------------------------

def test_reportar_pago_desde_la_pagina(app, cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba(), metodo="yape").headers["Location"].rsplit("/", 1)[1]
    pagina = cliente.get(f"/reservas/{codigo}/pago")
    assert pagina.status_code == 200 and 'value="30.00"' in pagina.get_data(True)
    datos = {"csrf_token": token_csrf(pagina), "metodo": "yape", "monto": "30.00", "numero_operacion": "79981111"}
    respuesta = cliente.post(f"/reservas/{codigo}/pago", data=datos)
    assert respuesta.status_code == 303
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                "WHERE r.codigo = %s AND p.estado = 'reportado'", (codigo,)) == 1
    # Con el total reportado, la reserva dice "en revisión" y ya no ofrece pagar otra vez
    html = cliente.get(f"/reservas/{codigo}").get_data(True)
    assert "Recibimos tu reporte de pago." in html and "Reportar mi pago" not in html
    otra_vez = cliente.get(f"/reservas/{codigo}/pago")
    assert otra_vez.status_code == 302 and otra_vez.headers["Location"] == f"/reservas/{codigo}"


def test_numero_de_operacion_repetido_da_422(cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba(cupo=10), metodo="yape",
                      acompanantes=[doc()]).headers["Location"].rsplit("/", 1)[1]   # total S/ 45
    for numero, codigo_http in (("79982222", 303), ("79982222", 422)):
        pagina = cliente.get(f"/reservas/{codigo}/pago")
        datos = {"csrf_token": token_csrf(pagina), "metodo": "yape", "monto": "10.00",
                 "numero_operacion": numero}
        respuesta = cliente.post(f"/reservas/{codigo}/pago", data=datos)
        assert respuesta.status_code == codigo_http
    assert "ya fue reportado" in respuesta.get_data(True)


def test_pago_de_reserva_en_el_muelle_no_aplica(cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba()).headers["Location"].rsplit("/", 1)[1]
    respuesta = cliente.get(f"/reservas/{codigo}/pago")
    assert respuesta.status_code == 302 and respuesta.headers["Location"] == f"/reservas/{codigo}"


# --- Comando y peso ------------------------------------------------------------------------------------

def test_comando_reservas_vencer(app, cliente, salida_prueba):
    codigo = reservar(cliente, salida_prueba(), metodo="plin").headers["Location"].rsplit("/", 1)[1]
    ejecutar_y_confirmar(app, "UPDATE reserva SET vence_en = NOW() - INTERVAL 1 MINUTE WHERE codigo = %s",
                         (codigo,))
    resultado = app.test_cli_runner().invoke(args=["reservas", "vencer"])
    assert resultado.exit_code == 0 and codigo in resultado.output


def test_formulario_de_reserva_pesa_menos_de_100_kb(cliente, salida_prueba):
    respuesta, _, _ = formulario(cliente, salida_prueba(), acompanantes=9)
    html = respuesta.get_data()
    recursos = set(re.findall(rb'(?:href|src)="(/estaticos/[^"?]+)', html))
    peso = len(html) + sum(len(cliente.get(r.decode()).get_data()) for r in recursos)
    assert peso < 100 * 1024, peso
