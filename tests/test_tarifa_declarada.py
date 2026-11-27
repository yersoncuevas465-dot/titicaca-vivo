"""Tarifas rebajadas (observación del docente, 27/11): «si soy adulto y marco niña para pagar menos,
¿se puede?». El DNI no dice la edad, así que el sistema no la conoce. Por eso:
- con una tarifa de niño, estudiante o adulto mayor, la reserva pide una declaración, y
- en el abordaje el panel avisa qué revisar en el documento de esa persona.
"""

from tests.conftest import consultar_valor, iniciar_sesion
from tests.test_rutas_reservas import datos_validos, doc, formulario


def _enviar(cliente, salida_id, acompanantes=(), declara=True):
    _, csrf, token = formulario(cliente, salida_id, len(acompanantes))
    datos = datos_validos(csrf, token, acompanantes=acompanantes, declara=declara)
    return cliente.post(f"/salidas/{salida_id}/reservar", data=datos), token


def test_pe01_con_tarifa_de_nino_sin_declarar_no_se_reserva(app, cliente, salida_prueba):
    respuesta, token = _enviar(cliente, salida_prueba(), acompanantes=[doc()], declara=False)
    assert respuesta.status_code == 422
    assert "Marca la declaración" in respuesta.get_data(True)
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM reserva WHERE token_envio = %s", (token,)) == 0


def test_pe02_con_la_declaracion_si_se_reserva(cliente, salida_prueba):
    respuesta, _ = _enviar(cliente, salida_prueba(), acompanantes=[doc()])
    assert respuesta.status_code == 303


def test_pe03_solo_adultos_no_piden_declaracion(cliente, salida_prueba):
    respuesta, _ = _enviar(cliente, salida_prueba(), declara=False)
    assert respuesta.status_code == 303


def test_pe04_en_el_abordaje_el_panel_dice_que_revisar(app, cliente, salida_prueba):
    respuesta, _ = _enviar(cliente, salida_prueba(), acompanantes=[doc()])
    codigo = respuesta.headers["Location"].rsplit("/", 1)[1]
    operador = app.test_client()
    iniciar_sesion(operador, "operador")
    html = operador.get(f"/panel/abordaje/{codigo}").get_data(True)
    assert "Verifica que tenga de" in html                          # el acompañante es «Niño o niña»
    assert html.count("Verifica") == 1                               # la titular es adulta: nada
