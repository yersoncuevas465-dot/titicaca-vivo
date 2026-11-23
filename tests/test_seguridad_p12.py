"""Práctica 12 · el ataque de la parte 2 escrito como prueba (PS = prueba de seguridad).

Lo que encontramos atacando Titicaca Vivo en localhost el 23/11/2026:
  1. /reservas/<código> responde 200 si el código existe y 404 si no: los códigos se pueden adivinar.
  2. Esa página, sin identificarse, muestra los últimos 3 dígitos del DNI del titular (•••••812).
  3. «Mi reserva» (código + documento) no tenía freno: 30 intentos seguidos, 30 respuestas 401.
Juntos: con un código adivinado faltan 5 dígitos del DNI (100 000 intentos) para entrar y ver
nombres, documentos, teléfono, correo y el boleto con QR de otra persona. El freno va en el servidor.
"""

import re

from tests.conftest import token_csrf

CODIGO, DNI = "TV-33VR", "40998812"          # reserva pagada de la semilla (USUARIOS_DEMO.txt)


def _intentar(cliente, documento):
    token = token_csrf(cliente.get(f"/mi-reserva?codigo={CODIGO}"))
    return cliente.post("/mi-reserva", data={"csrf_token": token, "codigo": CODIGO,
                                             "numero_documento": documento})


def test_ps01_mi_reserva_frena_al_undecimo_documento_equivocado(cliente):
    estados = [_intentar(cliente, f"4099{i:04d}").status_code for i in range(11)]
    assert estados[:10] == [401] * 10                 # el mismo «no encontramos» de siempre
    assert estados[10] == 429                         # y al undécimo, el servidor frena


def test_ps02_frenado_ni_el_documento_correcto_entra(cliente):
    for i in range(10):
        _intentar(cliente, f"4099{i:04d}")
    respuesta = _intentar(cliente, DNI)
    assert respuesta.status_code == 429               # no hay forma de saber si este era el bueno
    assert "Demasiados intentos" in respuesta.get_data(True)


def test_ps03_el_freno_no_castiga_al_turista_que_acierta(cliente):
    for _ in range(12):                               # volver a su reserva muchas veces está bien
        respuesta = _intentar(cliente, DNI)
        assert respuesta.status_code == 303
        assert respuesta.headers["Location"].endswith(f"/reservas/{CODIGO}")


def test_ps04_sin_identificarse_no_se_ve_ningun_digito_del_documento(app):
    # El punto 2: con «•••••812» a la vista solo faltaban 5 dígitos. Ahora no se ve ninguno.
    html = app.test_client().get(f"/reservas/{CODIGO}").get_data(True)
    titular = re.findall(r"<dt>DNI</dt><dd>([^<]*)</dd>", html)
    pasajeros = re.findall(r"<td>DNI ([^<]*)</td>", html)
    assert titular and pasajeros
    assert all(re.fullmatch("•+", dato) for dato in titular + pasajeros), (titular, pasajeros)
