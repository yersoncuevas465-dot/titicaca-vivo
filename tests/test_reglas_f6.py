"""F6 en el modelo: alertas que suspenden en un paso (RN-11), reprogramar y devolución,
hospedajes (RN-10: reasignar, asignar, cumplida, transparencia), reseñas (RN-13) e indicadores."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modelos import (
    ErrorNegocio,
    ErrorValidacion,
    EstadoNoPermite,
    PermisoDenegado,
    alerta,
    hospedaje,
    indicadores,
    pago,
    resena,
)
from app.modelos import reprogramacion as reprog
from app.modelos.reserva import SalidaNoDisponible, SinCupo
from tests.conftest import actor, consultar_valor, ejecutar_y_confirmar, reservar_en

ADMIN, OPERADOR, ELENA = 1, 2, 3


def estado_salida(app, salida_id):
    return consultar_valor(app, "SELECT estado FROM salida WHERE id = %s", (salida_id,))


def fila(app, sql, parametros=None):
    from app import bd

    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchone()
    finally:
        conexion.close()


def suspender(app, salida_id):
    ejecutar_y_confirmar(app, "UPDATE salida SET estado = 'suspendida', motivo_estado = "
                              "'Oleaje (prueba)' WHERE id = %s", (salida_id,))


# --- Alertas (RN-11) ------------------------------------------------------------------------

@pytest.fixture
def alerta_lejana(app):
    """Crea alertas (con el modelo) en días sin salidas de la semilla y las borra al final."""
    creadas = []

    def crear(nivel="naranja", comunidad_id=1, dias=30, horas=24):
        hoy = consultar_valor(app, "SELECT CURDATE()")
        desde = dt.datetime.combine(hoy + dt.timedelta(days=dias), dt.time(0, 0))
        datos = {"tipo": "oleaje", "nivel": nivel, "fuente": "SENAMHI",
                 "titulo": "Oleaje de prueba", "descripcion": "", "comunidad_id": comunidad_id,
                 "vigente_desde": desde, "vigente_hasta": desde + dt.timedelta(hours=horas)}
        with app.app_context():
            alerta_id = alerta.guardar(actor(OPERADOR), None, datos, ip="203.0.113.4")
        creadas.append(alerta_id)
        return alerta_id

    yield crear
    for alerta_id in creadas:
        ejecutar_y_confirmar(app, "DELETE FROM alerta_lago WHERE id = %s", (alerta_id,))


def test_alerta_naranja_suspende_en_un_paso_las_salidas_afectadas(app, salida_prueba, alerta_lejana):
    pasa_por_uros = [salida_prueba(ruta_id=1, dias=30, hora=8), salida_prueba(ruta_id=2, dias=30, hora=12)]
    otro_dia = salida_prueba(ruta_id=1, dias=32, hora=8)
    alerta_id = alerta_lejana(comunidad_id=1, dias=30)
    with app.app_context():
        afectadas = alerta.salidas_afectadas(actor(OPERADOR), alerta_id)
        assert {s["salida_id"] for s in afectadas} == set(pasa_por_uros)
        suspendidas = alerta.suspender_afectadas(actor(OPERADOR), alerta_id, ip="203.0.113.4")
    assert sorted(suspendidas) == sorted(pasa_por_uros)
    assert [estado_salida(app, s) for s in pasa_por_uros] == ["suspendida", "suspendida"]
    assert estado_salida(app, otro_dia) == "programada"
    motivo = consultar_valor(app, "SELECT motivo_estado FROM salida WHERE id = %s", (pasa_por_uros[0],))
    assert motivo.startswith("Alerta naranja de oleaje: Oleaje de prueba")
    # El trigger anotó cada cambio con el operador (S-24) y el modelo anotó la suspensión en bloque
    assert consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE accion = 'cambio_estado' "
                                "AND tabla_afectada = 'salida' AND usuario_id = 2 AND registro_id IN (%s, %s)",
                           tuple(pasa_por_uros)) == 2
    with app.app_context(), pytest.raises(EstadoNoPermite, match="No hay salidas"):
        alerta.suspender_afectadas(actor(OPERADOR), alerta_id)          # ya no queda ninguna


def test_alerta_de_comunidad_que_la_ruta_no_visita_no_afecta(app, salida_prueba, alerta_lejana):
    salida_prueba(ruta_id=1, dias=30, hora=8)                            # solo Uros
    alerta_id = alerta_lejana(comunidad_id=3, dias=30)                  # Amantaní
    with app.app_context():
        assert alerta.salidas_afectadas(actor(OPERADOR), alerta_id) == []


def test_una_alerta_amarilla_solo_informa(app, salida_prueba, alerta_lejana):
    salida_prueba(ruta_id=1, dias=30, hora=8)
    alerta_id = alerta_lejana(nivel="amarillo", comunidad_id=None, dias=30)
    with app.app_context():
        assert alerta.salidas_afectadas(actor(OPERADOR), alerta_id) == []
        with pytest.raises(EstadoNoPermite, match="naranja o roja"):
            alerta.suspender_afectadas(actor(OPERADOR), alerta_id)


@pytest.mark.parametrize("cambios, campo", [
    ({"titulo": "Ola"}, "titulo"), ({"nivel": "morado"}, "nivel"),
    ({"vigente_hasta": dt.datetime(2030, 1, 1, 0, 0)}, "vigente_hasta"),
    ({"comunidad_id": 999}, "comunidad_id"),
])
def test_alerta_invalida(app, cambios, campo):
    datos = {"tipo": "oleaje", "nivel": "naranja", "fuente": "SENAMHI", "titulo": "Oleaje fuerte",
             "comunidad_id": None, "vigente_desde": dt.datetime(2030, 1, 2, 0, 0),
             "vigente_hasta": dt.datetime(2030, 1, 3, 0, 0), **cambios}
    with app.app_context(), pytest.raises(ErrorValidacion) as excinfo:
        alerta.guardar(actor(OPERADOR), None, datos)
    assert campo in excinfo.value.errores


def test_solo_el_operador_registra_y_suspende(app):
    with app.app_context():
        with pytest.raises(PermisoDenegado):
            alerta.guardar(actor(ADMIN), None, {})
        with pytest.raises(PermisoDenegado):
            alerta.suspender_afectadas(actor(ADMIN), 1)
        assert alerta.listar_panel(actor(ADMIN))                       # el admin sí mira


# --- Reprogramar y devolución (RN-11, D-04, D-11) ---------------------------------------------

def test_reprogramar_mantiene_codigo_pagos_y_precio(app, salida_prueba):
    vieja, nueva = salida_prueba(ruta_id=1, dias=20), salida_prueba(ruta_id=1, dias=21)
    codigo = reservar_en(app, vieja, acompanantes=1)
    total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
    with app.app_context():
        pago.registrar_cobro(actor(OPERADOR), codigo, "efectivo_muelle", 10, None)
    suspender(app, vieja)
    with app.app_context():
        opciones = reprog.opciones(codigo)
        assert nueva in [o["salida_id"] for o in opciones]
        reprog.reprogramar(codigo, nueva, ip="203.0.113.8")
    r = fila(app, "SELECT salida_id, reprogramada_desde_salida_id, total, estado FROM reserva "
                  "WHERE codigo = %s", (codigo,))
    assert (r["salida_id"], r["reprogramada_desde_salida_id"]) == (nueva, vieja)
    assert r["total"] == total and r["estado"] == "confirmada"
    assert consultar_valor(app, "SELECT COUNT(*) FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                "WHERE r.codigo = %s AND p.estado = 'verificado'", (codigo,)) == 1
    with app.app_context(), pytest.raises(EstadoNoPermite):
        reprog.reprogramar(codigo, vieja)                               # la nueva no está suspendida


def test_reprogramar_respeta_el_cupo_y_la_ruta(app, salida_prueba):
    vieja = salida_prueba(ruta_id=1, dias=20)
    chica = salida_prueba(ruta_id=1, dias=21, cupo=1)
    otra_ruta = salida_prueba(ruta_id=2, dias=22)
    codigo = reservar_en(app, vieja, acompanantes=1)                   # 2 personas
    suspender(app, vieja)
    with app.app_context():
        assert chica not in [o["salida_id"] for o in reprog.opciones(codigo)]
        with pytest.raises(SinCupo):
            reprog.reprogramar(codigo, chica)
        with pytest.raises(SalidaNoDisponible):
            reprog.reprogramar(codigo, otra_ruta)
    assert consultar_valor(app, "SELECT salida_id FROM reserva WHERE codigo = %s", (codigo,)) == vieja


def test_reprogramar_con_noche_cambia_la_familia_de_fecha(app, salida_prueba):
    vieja, nueva = salida_prueba(ruta_id=3, dias=23), salida_prueba(ruta_id=3, dias=24)
    codigo = reservar_en(app, vieja)                                    # muelle: familia asignada
    suspender(app, vieja)
    with app.app_context():
        reprog.reprogramar(codigo, nueva)
    noches = fila(app, "SELECT SUM(h.estado = 'asignado') AS asignadas, SUM(h.estado = 'cancelado') "
                       "AS canceladas, MAX(CASE WHEN h.estado = 'asignado' THEN h.fecha_noche END) AS noche "
                       "FROM hospedaje h JOIN reserva r ON r.id = h.reserva_id WHERE r.codigo = %s", (codigo,))
    assert (noches["asignadas"], noches["canceladas"]) == (1, 1)
    assert noches["noche"] == consultar_valor(app, "SELECT DATE(fecha_hora_zarpe) FROM salida WHERE id = %s",
                                              (nueva,))


def test_devolucion_cancela_y_queda_por_atender(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=20)
    codigo = reservar_en(app, salida_id)
    total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
    with app.app_context():
        pago.registrar_cobro(actor(OPERADOR), codigo, "efectivo_muelle", total, None)
        with pytest.raises(EstadoNoPermite):
            reprog.pedir_devolucion(codigo)                             # todavía no está suspendida
    suspender(app, salida_id)
    with app.app_context():
        assert reprog.pedir_devolucion(codigo, ip="203.0.113.8") == total
        pendientes = [d["codigo"] for d in reprog.devoluciones_pendientes(actor(OPERADOR))]
        assert codigo in pendientes
        reserva_id = consultar_valor(app, "SELECT id FROM reserva WHERE codigo = %s", (codigo,))
        with pytest.raises(ErrorValidacion):
            reprog.atender_devolucion(actor(OPERADOR), reserva_id, "  ")
        reprog.atender_devolucion(actor(OPERADOR), reserva_id, "Devuelto por Yape (operación 123)")
        assert codigo not in [d["codigo"] for d in reprog.devoluciones_pendientes(actor(OPERADOR))]
        with pytest.raises(EstadoNoPermite):
            reprog.atender_devolucion(actor(OPERADOR), reserva_id, "Otra vez")
    assert consultar_valor(app, "SELECT estado FROM reserva WHERE codigo = %s", (codigo,)) == "cancelada"


# --- Hospedajes (RN-10) ------------------------------------------------------------------------

def test_reasignar_una_noche_con_motivo(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(ruta_id=3, dias=27))
    hospedaje_id = consultar_valor(app, "SELECT h.id FROM hospedaje h JOIN reserva r ON r.id = h.reserva_id "
                                        "WHERE r.codigo = %s", (codigo,))
    with app.app_context():
        noche = hospedaje.buscar_panel(actor(OPERADOR), hospedaje_id)
        candidatas = hospedaje.candidatas(actor(OPERADOR), noche)
        assert noche["familia_id"] not in [f["id"] for f in candidatas]
        with pytest.raises(ErrorValidacion):
            hospedaje.reasignar(actor(OPERADOR), hospedaje_id, candidatas[0]["id"], "")
        with pytest.raises(ErrorValidacion) as excinfo:
            hospedaje.reasignar(actor(OPERADOR), hospedaje_id, 6, "Familia de Llachón")   # otra comunidad
        assert "familia_id" in excinfo.value.errores
        hospedaje.reasignar(actor(OPERADOR), hospedaje_id, candidatas[0]["id"], "La familia avisó que viaja")
    nueva = fila(app, "SELECT familia_id, motivo_reasignacion FROM hospedaje WHERE id = %s", (hospedaje_id,))
    assert nueva["familia_id"] == candidatas[0]["id"]
    assert nueva["motivo_reasignacion"] == "La familia avisó que viaja"
    assert consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE accion = 'reasignacion' "
                                "AND registro_id = %s", (hospedaje_id,)) == 1


def test_asignar_la_familia_que_falto_al_pagar(app, salida_prueba):
    codigo = reservar_en(app, salida_prueba(ruta_id=3, dias=28), metodo="yape")
    total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
    activas = consultar_valor(app, "SELECT GROUP_CONCAT(id) FROM familia_anfitriona "
                                   "WHERE comunidad_id = 3 AND activa = 1")
    ejecutar_y_confirmar(app, "UPDATE familia_anfitriona SET activa = 0 WHERE comunidad_id = 3")
    try:
        with app.app_context():
            pago.registrar_cobro(actor(OPERADOR), codigo, "efectivo_muelle", total, None)  # pagada, sin familia
            assert codigo in [r["codigo"] for r in hospedaje.reservas_sin_familia(actor(OPERADOR))]
    finally:
        ejecutar_y_confirmar(app, "UPDATE familia_anfitriona SET activa = 1 WHERE FIND_IN_SET(id, %s)",
                             (activas,))
    with app.app_context():
        familia = hospedaje.asignar_faltante(actor(OPERADOR), codigo)
        assert familia["nombre_familia"]
        assert codigo not in [r["codigo"] for r in hospedaje.reservas_sin_familia(actor(OPERADOR))]
        with pytest.raises(EstadoNoPermite):
            hospedaje.asignar_faltante(actor(OPERADOR), codigo)


def test_marcar_cumplida_solo_una_noche_pasada_de_quien_abordo(app):
    pasada = consultar_valor(app, "SELECT id FROM hospedaje WHERE reserva_id = 4")       # abordada, hace 6 días
    futura = consultar_valor(app, "SELECT id FROM hospedaje WHERE reserva_id = 23")      # en 3 días
    ejecutar_y_confirmar(app, "UPDATE hospedaje SET estado = 'asignado' WHERE id = %s", (pasada,))
    with app.app_context():
        hospedaje.marcar_cumplida(actor(OPERADOR), pasada)
        with pytest.raises(EstadoNoPermite):
            hospedaje.marcar_cumplida(actor(OPERADOR), futura)
        with pytest.raises(EstadoNoPermite):
            hospedaje.marcar_cumplida(actor(OPERADOR), pasada)               # ya está cumplida
    assert consultar_valor(app, "SELECT estado FROM hospedaje WHERE id = %s", (pasada,)) == "cumplido"


def test_transparencia_incluye_a_las_familias_sin_noches(app):
    with app.app_context():
        mes = hospedaje.meses_con_hospedaje()[0]
        filas = hospedaje.transparencia(actor(ADMIN), mes)
    familias_activas = consultar_valor(
        app, "SELECT COUNT(*) FROM familia_anfitriona f JOIN comunidad c ON c.id = f.comunidad_id "
             "WHERE c.tiene_hospedaje = 1 AND f.activa = 1")
    assert len([f for f in filas if f["activa"]]) == familias_activas
    assert any(f["noches"] == 0 and f["noches_por_cumplir"] == 0 for f in filas)
    for comunidad in {f["comunidad_id"] for f in filas}:
        grupo = [f for f in filas if f["comunidad_id"] == comunidad]
        assert sum(f["monto"] for f in grupo) == grupo[0]["monto_comunidad"]     # SUM() OVER


# --- Reseñas (RN-13) ---------------------------------------------------------------------------

def test_resena_solo_de_un_viaje_hecho_y_una_vez(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=20)
    codigo = reservar_en(app, salida_id)
    with app.app_context():
        assert "Solo se opina" in resena.por_que_no(resena.para_la_reserva(codigo))
    ejecutar_y_confirmar(app, "UPDATE reserva SET estado = 'abordada' WHERE codigo = %s", (codigo,))
    with app.app_context():
        assert "cuando termine" in resena.por_que_no(resena.para_la_reserva(codigo))
    ejecutar_y_confirmar(app, "UPDATE salida SET fecha_hora_zarpe = NOW() - INTERVAL 1 DAY, "
                              "fecha_hora_retorno = NOW() - INTERVAL 20 HOUR WHERE id = %s", (salida_id,))
    with app.app_context():
        with pytest.raises(ErrorValidacion):
            resena.crear(codigo, 6, "")
        resena.crear(codigo, 5, "Hermoso día en los Uros.", "es")
        with pytest.raises(EstadoNoPermite, match="Ya dejaste"):
            resena.crear(codigo, 4, "Otra")
        resena_id = consultar_valor(app, "SELECT re.id FROM resena re JOIN reserva r ON r.id = re.reserva_id "
                                         "WHERE r.codigo = %s", (codigo,))
        assert all(o["comentario"] != "Hermoso día en los Uros." for o in resena.publicadas_de_ruta(1))
        resena.moderar(actor(OPERADOR), resena_id, "publicada")
        with pytest.raises(EstadoNoPermite):
            resena.moderar(actor(OPERADOR), resena_id, "rechazada")
        publicadas = resena.publicadas_de_ruta(1)
    assert publicadas[0]["comentario"] == "Hermoso día en los Uros."
    assert publicadas[0]["total"] == len(publicadas)
    ejecutar_y_confirmar(app, "DELETE FROM resena WHERE id = %s", (resena_id,))


def test_moderar_es_del_operador(app):
    with app.app_context(), pytest.raises(PermisoDenegado):
        resena.moderar(actor(ADMIN), 4, "publicada")


# --- Indicadores (8.8) -------------------------------------------------------------------------

def test_indicadores_con_agregaciones_y_ventanas(app):
    with app.app_context():
        op = actor(OPERADOR)
        ocupacion = indicadores.ocupacion_por_ruta(op, 365)
        metodos = indicadores.ingresos_por_metodo(op, 365)
        paises = indicadores.nacionalidades(op, 365)
        familias = indicadores.noches_por_familia(op, 365)
        poca = indicadores.rutas_con_poca_ocupacion(op, 365, umbral=20)
        with pytest.raises(PermisoDenegado):
            indicadores.ocupacion_por_ruta(actor(ELENA), 30)
    assert [r["puesto"] for r in ocupacion] == sorted(r["puesto"] for r in ocupacion)
    assert ocupacion[0]["ocupacion"] >= ocupacion[-1]["ocupacion"]                     # RANK()
    assert abs(sum(m["porcentaje"] for m in metodos) - Decimal("100")) <= Decimal("0.5")
    assert paises[0]["nacionalidad"] == "PE"
    assert any(f["noches"] == 0 for f in familias)                                      # LEFT JOIN
    assert all(r["ocupacion"] < 20 for r in poca)                                       # HAVING


def test_error_de_negocio_es_la_base_de_las_reglas():
    assert issubclass(EstadoNoPermite, ErrorNegocio)
