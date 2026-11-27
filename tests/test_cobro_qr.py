"""QR de Yape y Plin (observación del docente, 27/11): el admin sube el QR de la agencia y la
página de pago lo muestra para escanearlo. El sistema no entra a la cuenta de Yape: el turista
paga con el QR, copia el número de operación y la agencia lo verifica (como siempre).
"""

import io

from PIL import Image, ImageDraw

from app.servicios import qr_cobro
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_rutas_reservas import reservar


def _png():
    imagen = Image.new("RGBA", (300, 300), (0, 0, 0, 0))            # fondo transparente
    ImageDraw.Draw(imagen).rectangle((40, 40, 120, 120), fill="black")
    memoria = io.BytesIO()
    imagen.save(memoria, "PNG")
    return memoria.getvalue()


def _subir(cliente, medio, contenido, nombre="qr.png"):
    token = token_csrf(cliente.get("/panel/cobro"))
    return cliente.post("/panel/cobro", content_type="multipart/form-data",
                        data={"csrf_token": token, f"qr_{medio}": (io.BytesIO(contenido), nombre)})


def _admin(app):
    cliente = app.test_client()
    iniciar_sesion(cliente, "admin")
    return cliente


def _pagina_de_pago(app, salida_prueba):
    turista = app.test_client()
    codigo = reservar(turista, salida_prueba(), metodo="yape").headers["Location"].rsplit("/", 1)[1]
    return turista.get(f"/reservas/{codigo}/pago").get_data(True)


def test_pq01_el_admin_sube_el_qr_de_yape_y_sale_en_la_pagina_de_pago(app, salida_prueba):
    assert _subir(_admin(app), "yape", _png()).status_code == 303
    try:
        imagen = app.test_client().get("/cobro/qr/yape")
        contenido = imagen.get_data()
        imagen.close()                                   # en Windows, si no se cierra, no se borra
        assert imagen.status_code == 200 and imagen.mimetype == "image/png"
        guardada = Image.open(io.BytesIO(contenido))
        assert guardada.mode == "RGB" and guardada.getpixel((5, 5)) == (255, 255, 255)  # fondo blanco
        html = _pagina_de_pago(app, salida_prueba)
        assert 'src="/cobro/qr/yape"' in html and "/cobro/qr/plin" not in html
    finally:
        with app.app_context():
            qr_cobro.borrar("yape")


def test_pq02_solo_el_admin_cambia_el_qr(app):
    operador = app.test_client()
    iniciar_sesion(operador, "operador")
    assert operador.get("/panel/cobro").status_code == 403
    assert app.test_client().get("/panel/cobro").status_code == 302          # sin sesión: a /entrar


def test_pq03_un_archivo_que_no_es_imagen_no_se_guarda(app):
    respuesta = _subir(_admin(app), "plin", b"esto no es una imagen")
    assert respuesta.status_code == 422 and "tiene que ser una imagen" in respuesta.get_data(True)
    assert app.test_client().get("/cobro/qr/plin").status_code == 404


def test_pq04_sin_qr_la_pagina_de_pago_no_muestra_imagenes_rotas(app, salida_prueba):
    assert "/cobro/qr/" not in _pagina_de_pago(app, salida_prueba)
