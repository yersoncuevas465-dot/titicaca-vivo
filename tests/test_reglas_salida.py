"""Salidas en el modelo (F5): RN-07 al crear y editar, suspender, cancelar y marcar el zarpe."""

import datetime as dt

import pytest

from app.modelos import ErrorValidacion, EstadoNoPermite, PermisoDenegado, abordaje
from app.modelos import salida as m
from tests.conftest import actor, consultar_valor, ejecutar_y_confirmar, limpiar_salida, reservar_en

ADMIN, OPERADOR, ELENA, MARCO, TEODORO, FERMIN = 1, 2, 3, 4, 5, 6
IP = "203.0.113.9"


def datos(app, dias=40, hora=8, ruta=1, lancha=3, capitan=TEODORO, guia=None, cupo=10):
    """Datos de una salida en la lancha 3 (Wiñay Inti, 20 lugares) dentro de 40 días."""
    hoy = consultar_valor(app, "SELECT CURDATE()")
    return m.DatosSalida(ruta_id=ruta, embarcacion_id=lancha, capitan_id=capitan, guia_id=guia,
                         fecha=hoy + dt.timedelta(days=dias), hora=dt.time(hora, 0), cupo=cupo)


@pytest.fixture
def creadas(app):
    ids = []
    yield ids
    for salida_id in ids:
        limpiar_salida(app, salida_id)


def crear(app, d, quien=OPERADOR):
    with app.app_context():
        return m.crear(actor(quien), d, ip=IP)


def errores_al_crear(app, d):
    with pytest.raises(ErrorValidacion) as excinfo:
        crear(app, d)
    return excinfo.value.errores


def estado(app, salida_id):
    return consultar_valor(app, "SELECT estado FROM salida WHERE id = %s", (salida_id,))


# --- Crear: RN-07 ----------------------------------------------------------------------------------

def test_crear_una_salida_valida(app, creadas):
    salida_id = crear(app, datos(app, ruta=2, cupo=18))          # Uros y Taquile: 9.5 h
    creadas.append(salida_id)
    fila_minutos = consultar_valor(
        app, "SELECT TIMESTAMPDIFF(MINUTE, fecha_hora_zarpe, fecha_hora_retorno) FROM salida "
             "WHERE id = %s", (salida_id,))
    assert estado(app, salida_id) == "programada"
    assert fila_minutos == 570                                    # el retorno sale de la duración
    assert consultar_valor(app, "SELECT creada_por FROM salida WHERE id = %s", (salida_id,)) == 2
    assert consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE accion = 'creacion' "
                                "AND tabla_afectada = 'salida' AND registro_id = %s",
                           (salida_id,)) == 1


CASOS_RN07 = [
    ("lancha en mantenimiento", {"lancha": 4}, "embarcacion_id"),
    ("lancha de baja", {"lancha": 5}, "embarcacion_id"),
    ("cupo mayor que la capacidad", {"cupo": 21}, "cupo"),
    ("cupo cero", {"cupo": 0}, "cupo"),
    ("el capitán es una guía", {"capitan": ELENA}, "capitan_id"),
    ("el guía es el operador", {"guia": OPERADOR}, "guia_id"),
    ("ruta que no existe", {"ruta": 99}, "ruta_id"),
    ("zarpe en el pasado", {"dias": -1}, "hora"),
]


@pytest.mark.parametrize("descripcion, cambios, campo", CASOS_RN07, ids=[c[0] for c in CASOS_RN07])
def test_rn07_rechaza(app, descripcion, cambios, campo):
    assert campo in errores_al_crear(app, datos(app, **cambios))


def test_el_capitan_necesita_licencia(app):
    ejecutar_y_confirmar(app, "UPDATE usuario SET licencia_navegacion = NULL WHERE id = 6")
    try:
        errores = errores_al_crear(app, datos(app, capitan=FERMIN))
        assert errores["capitan_id"].startswith("El capitán no tiene licencia")
    finally:
        ejecutar_y_confirmar(app, "UPDATE usuario SET licencia_navegacion = 'LIC-PUN-00456' "
                                  "WHERE id = 6")


def test_la_misma_lancha_no_tiene_salidas_que_se_cruzan(app, creadas):
    creadas.append(crear(app, datos(app, ruta=2, hora=7)))       # 07:00 a 16:30
    errores = errores_al_crear(app, datos(app, ruta=1, hora=12))  # 12:00 a 15:00: se cruza
    assert "ya tiene la salida" in errores["embarcacion_id"]
    creadas.append(crear(app, datos(app, ruta=1, hora=17)))      # 17:00 a 20:00: no se cruza


def test_el_capitan_y_el_guia_no_van_en_dos_salidas_a_la_vez(app, creadas):
    creadas.append(crear(app, datos(app, ruta=2, hora=7, guia=ELENA)))   # lancha 3, 07:00 a 16:30
    # Otra lancha, a las 12:00, con el mismo capitán: imposible estar en las dos
    errores = errores_al_crear(app, datos(app, ruta=1, hora=12, lancha=2))
    assert "ya va en la salida" in errores["capitan_id"] and "embarcacion_id" not in errores
    # Otro capitán, pero la misma guía
    errores = errores_al_crear(app, datos(app, ruta=1, hora=12, lancha=2, capitan=FERMIN,
                                          guia=ELENA))
    assert "ya va en la salida" in errores["guia_id"] and "capitan_id" not in errores
    # Otro capitán y otro guía: sí se puede
    creadas.append(crear(app, datos(app, ruta=1, hora=12, lancha=2, capitan=FERMIN, guia=MARCO)))
    # Y al editar tampoco se cruza: pasar la segunda al capitán de la primera
    with app.app_context(), pytest.raises(ErrorValidacion) as excinfo:
        m.editar(actor(OPERADOR), creadas[1], datos(app, ruta=1, hora=12, lancha=2, guia=MARCO))
    assert "ya va en la salida" in excinfo.value.errores["capitan_id"]


def test_una_salida_suspendida_no_ocupa_la_lancha(app, creadas):
    primera = crear(app, datos(app, ruta=2, hora=7))
    creadas.append(primera)
    with app.app_context():
        m.suspender(actor(OPERADOR), primera, "Oleaje fuerte (prueba)")
    creadas.append(crear(app, datos(app, ruta=1, hora=12)))      # ahora sí se puede


@pytest.mark.parametrize("quien", [ADMIN, ELENA, TEODORO])
def test_solo_el_operador_crea_salidas(app, quien):
    with pytest.raises(PermisoDenegado):
        crear(app, datos(app), quien)


# --- Editar ----------------------------------------------------------------------------------------

def test_editar_respeta_los_ocupados_y_el_dia(app, creadas):
    salida_id = crear(app, datos(app, cupo=10))
    creadas.append(salida_id)
    reservar_en(app, salida_id, acompanantes=2)                    # 3 pasajeros
    with app.app_context():
        operador = actor(OPERADOR)
        with pytest.raises(ErrorValidacion) as excinfo:
            m.editar(operador, salida_id, datos(app, cupo=2))
        assert "Ya hay 3 pasajeros" in excinfo.value.errores["cupo"]
        with pytest.raises(ErrorValidacion) as excinfo:
            m.editar(operador, salida_id, datos(app, dias=41))
        assert "fecha" in excinfo.value.errores
        assert m.editar(operador, salida_id, datos(app, hora=9, cupo=3)) is True
        assert m.editar(operador, salida_id, datos(app, hora=9, cupo=3)) is False   # nada cambió
    assert consultar_valor(app, "SELECT HOUR(fecha_hora_zarpe) FROM salida WHERE id = %s",
                           (salida_id,)) == 9
    detalle = consultar_valor(app, "SELECT detalle FROM bitacora WHERE accion = 'edicion' "
                                   "AND registro_id = %s AND tabla_afectada = 'salida'",
                              (salida_id,))
    assert '"cupo": [10, 3]' in detalle


def test_no_se_edita_una_salida_que_ya_zarpo(app):
    with app.app_context(), pytest.raises(EstadoNoPermite):
        m.editar(actor(OPERADOR), 4, datos(app))                     # salida 4: finalizada


# --- Suspender y cancelar --------------------------------------------------------------------------

def test_suspender_guarda_el_motivo_y_la_bitacora_sabe_quien_fue(app, creadas):
    salida_id = crear(app, datos(app))
    creadas.append(salida_id)
    with app.app_context():
        m.suspender(actor(OPERADOR), salida_id, "  Alerta   naranja de oleaje ", ip=IP)
    assert estado(app, salida_id) == "suspendida"
    assert consultar_valor(app, "SELECT motivo_estado FROM salida WHERE id = %s",
                           (salida_id,)) == "Alerta naranja de oleaje"
    # El trigger trg_salida_au escribe la bitácora con @app_usuario_id y @app_ip (S-24)
    quien = consultar_valor(app, "SELECT CONCAT(usuario_id, ' ', ip) FROM bitacora "
                                 "WHERE accion = 'cambio_estado' AND tabla_afectada = 'salida' "
                                 "AND registro_id = %s", (salida_id,))
    assert quien == f"2 {IP}"


def test_suspender_pide_motivo_y_una_salida_activa(app):
    with app.app_context():
        with pytest.raises(ErrorValidacion):
            m.suspender(actor(OPERADOR), 10, "   ")
        with pytest.raises(EstadoNoPermite):
            m.suspender(actor(OPERADOR), 4, "Ya zarpó hace días")      # finalizada


def test_cancelar_solo_sin_reservas_activas(app, creadas):
    con_reservas = crear(app, datos(app, hora=7))
    sin_reservas = crear(app, datos(app, hora=17))
    creadas.extend([con_reservas, sin_reservas])
    reservar_en(app, con_reservas)
    with app.app_context():
        with pytest.raises(EstadoNoPermite, match="no se puede cancelar"):
            m.cancelar(actor(OPERADOR), con_reservas, "Pocos pasajeros")
        m.cancelar(actor(OPERADOR), sin_reservas, "Falla del motor")
    assert estado(app, con_reservas) == "programada"
    assert estado(app, sin_reservas) == "cancelada"


# --- Zarpe -----------------------------------------------------------------------------------------

def test_el_zarpe_se_marca_desde_60_minutos_antes(app, salida_cerca):
    salida_id = salida_cerca(minutos=120)
    with app.app_context(), pytest.raises(EstadoNoPermite, match="60 minutos"):
        m.marcar_zarpe(actor(OPERADOR), salida_id)
    assert estado(app, salida_id) == "programada"


def test_zarpe_marca_no_show_solo_a_quien_no_subio_nadie(app, salida_cerca):
    salida_id = salida_cerca(minutos=30)                          # capitán Teodoro
    subio_uno = reservar_en(app, salida_id, acompanantes=1)
    no_vino = reservar_en(app, salida_id)
    with app.app_context():
        datos_reserva = abordaje.buscar(actor(OPERADOR), subio_uno)
        abordaje.registrar(actor(OPERADOR), subio_uno, [datos_reserva["pasajeros"][0]["id"]], "qr")
        ausentes = m.marcar_zarpe(actor(TEODORO), salida_id, ip=IP)
    assert ausentes == [no_vino]
    assert estado(app, salida_id) == "zarpo"
    estados = dict(app_estados(app, (subio_uno, no_vino)))
    assert estados == {subio_uno: "confirmada", no_vino: "no_show"}


def app_estados(app, codigos):
    from app import bd

    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT codigo, estado FROM reserva WHERE codigo IN (%s, %s)", codigos)
            return [(f["codigo"], f["estado"]) for f in cursor.fetchall()]
    finally:
        conexion.close()


def test_otro_capitan_no_marca_el_zarpe(app, salida_cerca):
    salida_id = salida_cerca(minutos=30)                          # es de Teodoro
    with app.app_context():
        with pytest.raises(PermisoDenegado):
            m.marcar_zarpe(actor(FERMIN), salida_id)
        with pytest.raises(PermisoDenegado):
            m.marcar_zarpe(actor(ELENA), salida_id)                # una guía tampoco


def test_la_lista_de_pasajeros_es_solo_para_su_guia_o_capitan(app):
    with app.app_context():
        salida, filas = m.pasajeros_de_salida(actor(TEODORO), 13)     # 13: de Teodoro
        assert salida["salida_id"] == 13 and len(filas) == 3
        with pytest.raises(PermisoDenegado):
            m.pasajeros_de_salida(actor(FERMIN), 13)
        with pytest.raises(PermisoDenegado):
            m.pasajeros_de_salida(actor(ELENA), 10)                   # 10: su guía es Marco
        assert m.pasajeros_de_salida(actor(MARCO), 10)[0] is not None
        assert m.pasajeros_de_salida(actor(OPERADOR), 9999) == (None, [])
