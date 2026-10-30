"""Nivel Oro: reservas simultáneas, cada una en su propio hilo y con su propia conexión.

- 8 hilos piden el ÚLTIMO lugar al mismo tiempo → exactamente 1 reserva (RN-02).
- 3 envíos simultáneos del MISMO formulario (mismo token) → 1 reserva (RN-03).

F7: la "prueba mutante" (quitar el FOR UPDATE y ver que la de 8 hilos falla) está en
test_mutante.py. Aquí se suman las carreras de la F5 y la F6: dos operadores verifican el
mismo pago, dos turistas reprograman al último lugar y dos guías leen el mismo QR.
"""

import threading

from app import bd
from app.modelos import reserva as m
from tests.conftest import consultar_valor


def _en_paralelo(app, cantidad, tarea):
    """Lanza `cantidad` hilos que arrancan a la vez (Barrier). Devuelve los resultados."""
    barrera = threading.Barrier(cantidad)
    resultados = [None] * cantidad

    def correr(indice):
        with app.app_context():
            # Cada hilo tiene su propio contexto, su propio flask.g y su propia conexión.
            bd.obtener_conexion()
            barrera.wait()
            try:
                resultados[indice] = ("ok", tarea(indice))
            except Exception as error:   # noqa: BLE001 (queremos ver qué error tuvo cada hilo)
                resultados[indice] = (type(error).__name__, str(error))

    hilos = [threading.Thread(target=correr, args=(i,)) for i in range(cantidad)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=60)
    return resultados


def _solicitud(salida_id, numero):
    titular = m.Persona("Hilo", "Concurrente", "DNI", numero, "PE", 1)
    return m.Solicitud(salida_id=salida_id, titular=titular, telefono="987654321", correo=None,
                       titular_viaja=True, metodo_pago="muelle")


def test_ocho_hilos_por_el_ultimo_lugar_crean_una_sola_reserva(app, salida_prueba):
    salida_id = salida_prueba(cupo=1)

    def tarea(indice):
        return m.crear(_solicitud(salida_id, f"7997{indice:04d}"), m.generar_token())

    resultados = _en_paralelo(app, 8, tarea)
    exitos = [r for r in resultados if r[0] == "ok"]
    sin_cupo = [r for r in resultados if r[0] == "SinCupo"]
    assert len(exitos) == 1, resultados
    assert len(sin_cupo) == 7, resultados
    ocupados = consultar_valor(app, "SELECT ocupados FROM v_disponibilidad_salida WHERE salida_id = %s",
                               (salida_id,))
    assert ocupados == 1


def test_tres_envios_del_mismo_formulario_crean_una_sola_reserva(app, salida_prueba):
    salida_id = salida_prueba(cupo=10)
    token = m.generar_token()

    def tarea(_indice):
        return m.crear(_solicitud(salida_id, "79970099"), token)

    resultados = _en_paralelo(app, 3, tarea)
    assert all(r[0] == "ok" for r in resultados), resultados
    codigos = {r[1][0] for r in resultados}
    nuevas = [r[1][1] for r in resultados]
    assert len(codigos) == 1                     # los 3 reciben el mismo código
    assert nuevas.count(True) == 1               # solo uno la creó; los otros la encontraron
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM reserva WHERE token_envio = %s", (token,)) == 1


# --- F7: carreras del panel y de la reprogramación -------------------------------------------

def test_dos_operadores_verifican_el_mismo_pago_a_la_vez(app, salida_prueba):
    from app.modelos import pago
    from tests.conftest import actor, reservar_en

    codigo = reservar_en(app, salida_prueba(), metodo="yape")
    total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
    with app.app_context():
        m.reportar_pago(codigo, "yape", total, f"CARRERA-{codigo[3:]}")
    pago_id = consultar_valor(app, "SELECT p.id FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                   "WHERE r.codigo = %s", (codigo,))

    resultados = _en_paralelo(app, 2, lambda _i: pago.verificar(actor(2), pago_id))
    assert sorted(r[0] for r in resultados) == ["EstadoNoPermite", "ok"], resultados
    assert consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE accion = 'cambio_estado' "
                                "AND tabla_afectada = 'pago' AND registro_id = %s", (pago_id,)) == 1


def test_dos_reprogramaciones_por_el_ultimo_lugar(app, salida_prueba):
    from app.modelos import reprogramacion
    from tests.conftest import ejecutar_y_confirmar, reservar_en

    vieja, nueva = salida_prueba(dias=20), salida_prueba(dias=21, cupo=1)
    codigos = [reservar_en(app, vieja), reservar_en(app, vieja)]
    ejecutar_y_confirmar(app, "UPDATE salida SET estado = 'suspendida' WHERE id = %s", (vieja,))

    resultados = _en_paralelo(app, 2, lambda i: reprogramacion.reprogramar(codigos[i], nueva))
    assert sorted(r[0] for r in resultados) == ["SinCupo", "ok"], resultados
    assert consultar_valor(app, "SELECT ocupados FROM v_disponibilidad_salida WHERE salida_id = %s",
                           (nueva,)) == 1


def test_dos_guias_leen_el_mismo_qr_a_la_vez(app, salida_cerca):
    from app.modelos import abordaje
    from tests.conftest import actor, reservar_en

    codigo = reservar_en(app, salida_cerca(minutos=30), acompanantes=1)
    with app.app_context():
        ids = [p["id"] for p in abordaje.buscar(actor(2), codigo)["pasajeros"]]

    resultados = _en_paralelo(app, 2, lambda _i: abordaje.registrar(actor(2), codigo, ids, "qr"))
    assert sorted(r[0] for r in resultados) == ["EstadoNoPermite", "ok"], resultados
    assert consultar_valor(app, "SELECT COUNT(*) FROM abordaje a JOIN reserva_pasajero rp "
                                "ON rp.id = a.reserva_pasajero_id JOIN reserva r ON r.id = rp.reserva_id "
                                "WHERE r.codigo = %s", (codigo,)) == 2
