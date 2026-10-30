"""Reglas de la reserva en el modelo: RN-02 a RN-06, RN-09 y RN-10."""

import itertools
from decimal import Decimal

import pytest

from app.modelos import hospedaje
from app.modelos import reserva as m
from tests.conftest import consultar_valor, ejecutar_y_confirmar

_documentos = itertools.count(1)


def doc():
    """Un DNI de prueba distinto cada vez (799xxxxx)."""
    return f"799{next(_documentos):05d}"


def persona(numero=None, tipo=1, nombres="Ana", apellidos="Prueba Lago", tipo_doc="DNI", pais="PE"):
    return m.Persona(nombres, apellidos, tipo_doc, numero or doc(), pais, tipo)


def solicitud(salida_id, acompanantes=0, metodo="muelle", titular=None, viaja=True,
              telefono="987654321", correo=None):
    return m.Solicitud(salida_id=salida_id, titular=titular or persona(), telefono=telefono,
                       correo=correo, titular_viaja=viaja, metodo_pago=metodo,
                       acompanantes=[persona(tipo=4, nombres="Leo") for _ in range(acompanantes)])


def crear(app, sol, token=None):
    with app.app_context():
        return m.crear(sol, token or m.generar_token())


def fila_reserva(app, codigo):
    from app import bd

    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT r.*, TIMESTAMPDIFF(MINUTE, NOW(), r.vence_en) AS minutos_para_vencer, "
                "(SELECT COUNT(*) FROM reserva_pasajero WHERE reserva_id = r.id) AS n_pasajeros "
                "FROM reserva r WHERE r.codigo = %s", (codigo,))
            return cursor.fetchone()
    finally:
        conexion.close()


# --- RN-02, RN-04, RN-05 ---------------------------------------------------------------------------

def test_reserva_en_el_muelle_queda_confirmada_con_su_total(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=1)                      # Uros: adulto nac. 30, niño 15
    codigo, nueva = crear(app, solicitud(salida_id, acompanantes=2))
    fila = fila_reserva(app, codigo)
    assert nueva and m.PATRON_CODIGO.match(codigo)
    assert fila["estado"] == "confirmada" and fila["vence_en"] is None
    assert fila["n_pasajeros"] == 3
    assert fila["total"] == Decimal("60.00")                  # 30 + 15 + 15
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM bitacora WHERE accion = 'creacion' "
                                "AND registro_id = %s", (fila["id"],)) == 1


def test_reserva_con_yape_queda_pendiente_y_vence_en_2_horas(app, salida_prueba):
    codigo, _ = crear(app, solicitud(salida_prueba(), metodo="yape"))
    fila = fila_reserva(app, codigo)
    assert fila["estado"] == "pendiente_pago"
    assert 118 <= fila["minutos_para_vencer"] <= 120


def test_el_titular_que_no_viaja_no_ocupa_lugar(app, salida_prueba):
    codigo, _ = crear(app, solicitud(salida_prueba(), acompanantes=1, viaja=False))
    assert fila_reserva(app, codigo)["n_pasajeros"] == 1


def test_el_precio_aplicado_es_una_foto(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=1)
    codigo, _ = crear(app, solicitud(salida_id))
    ejecutar_y_confirmar(app, "UPDATE tarifa SET precio_base = 99 WHERE ruta_id = 1 AND tipo_pasajero_id = 1 "
                              "AND vigente_desde = '2026-01-01'")
    try:
        assert fila_reserva(app, codigo)["total"] == Decimal("30.00")     # no cambió
    finally:
        ejecutar_y_confirmar(app, "UPDATE tarifa SET precio_base = 30 WHERE ruta_id = 1 AND "
                                  "tipo_pasajero_id = 1 AND vigente_desde = '2026-01-01'")


def test_recargo_de_temporada(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=25)
    ejecutar_y_confirmar(app, "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, recargo_porcentaje) "
                              "VALUES ('Prueba RN-04', CURDATE() + INTERVAL 25 DAY, CURDATE() + INTERVAL 25 DAY, 20)")
    try:
        codigo, _ = crear(app, solicitud(salida_id))
        assert fila_reserva(app, codigo)["total"] == Decimal("36.00")     # 30 × 1.20
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM temporada WHERE nombre = 'Prueba RN-04'")


def test_sin_cupo_no_se_crea_nada(app, salida_prueba):
    salida_id = salida_prueba(cupo=2)
    with pytest.raises(m.SinCupo, match="Solo quedan 2 lugares"):
        crear(app, solicitud(salida_id, acompanantes=2))
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM reserva WHERE salida_id = %s", (salida_id,)) == 0


def test_una_reserva_vencida_ya_no_ocupa_lugar(app, salida_prueba):
    salida_id = salida_prueba(cupo=1)
    codigo, _ = crear(app, solicitud(salida_id, metodo="yape"))
    with pytest.raises(m.SinCupo):
        crear(app, solicitud(salida_id))
    ejecutar_y_confirmar(app, "UPDATE reserva SET vence_en = NOW() - INTERVAL 1 MINUTE WHERE codigo = %s",
                         (codigo,))
    otro, _ = crear(app, solicitud(salida_id))                  # RN-05: ahora sí hay lugar
    assert fila_reserva(app, otro)["estado"] == "confirmada"


@pytest.mark.parametrize("estado, dias", [("suspendida", 20), ("cancelada", 20), ("programada", -1)])
def test_salida_que_no_recibe_reservas(app, salida_prueba, estado, dias):
    salida_id = salida_prueba(estado=estado, dias=dias)
    with pytest.raises(m.SalidaNoDisponible):
        crear(app, solicitud(salida_id))


# --- RN-03: idempotencia ---------------------------------------------------------------------------

def test_el_mismo_token_no_duplica_la_reserva(app, salida_prueba):
    salida_id = salida_prueba()
    token = m.generar_token()
    sol = solicitud(salida_id)
    primero, nueva1 = crear(app, sol, token)
    segundo, nueva2 = crear(app, solicitud(salida_id, titular=sol.titular), token)
    assert (primero, nueva1, nueva2) == (segundo, True, False)
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM reserva WHERE token_envio = %s", (token,)) == 1


def test_token_invalido(app, salida_prueba):
    with pytest.raises(m.ErrorValidacion):
        crear(app, solicitud(salida_prueba()), token="no-es-un-token")


# --- RN-09: datos ------------------------------------------------------------------------------------

def test_un_documento_no_viaja_dos_veces_en_la_misma_salida(app, salida_prueba):
    salida_id = salida_prueba()
    titular = persona()
    crear(app, solicitud(salida_id, titular=titular))
    otra = solicitud(salida_id)
    otra.acompanantes = [persona(numero=titular.numero_documento, nombres="Ana", apellidos="Prueba Lago")]
    with pytest.raises(m.DocumentoRepetido):
        crear(app, otra)


def test_documento_repetido_dentro_del_mismo_formulario(app, salida_prueba):
    sol = solicitud(salida_prueba())
    sol.acompanantes = [persona(numero=sol.titular.numero_documento)]
    with pytest.raises(m.ErrorValidacion) as error:
        crear(app, sol)
    assert "acompanantes-0-numero_documento" in error.value.errores


CASOS_INVALIDOS = [
    ("DNI de 7 dígitos", {"titular": dict(numero="7999001")}, "titular_numero_documento"),
    ("CE de 8 dígitos", {"titular": dict(tipo_doc="CE", numero="79990012")}, "titular_numero_documento"),
    ("pasaporte corto", {"titular": dict(tipo_doc="PASAPORTE", numero="AB12")}, "titular_numero_documento"),
    ("país inexistente", {"titular": dict(pais="XX")}, "titular_nacionalidad"),
    ("nombre con números", {"titular": dict(nombres="Ana 2")}, "titular_nombres"),
    ("teléfono fijo", {"telefono": "054123456"}, "telefono"),
    ("sin teléfono ni correo", {"telefono": None}, "telefono"),
    ("correo inválido", {"correo": "ana@", "telefono": None}, "correo"),
    ("método inexistente", {"metodo": "tarjeta"}, "metodo_pago"),
    ("sin pasajeros", {"viaja": False}, "pasajeros"),
    ("11 pasajeros", {"acompanantes": 10}, "pasajeros"),
]


@pytest.mark.parametrize("descripcion, cambios, campo", CASOS_INVALIDOS, ids=[c[0] for c in CASOS_INVALIDOS])
def test_datos_invalidos(app, salida_prueba, descripcion, cambios, campo):
    cambios = dict(cambios)
    titular = persona(**cambios.pop("titular", {}))
    with pytest.raises(m.ErrorValidacion) as error:
        crear(app, solicitud(salida_prueba(), titular=titular, **cambios))
    assert campo in error.value.errores


def test_los_datos_se_limpian_antes_de_guardar(app, salida_prueba):
    numero = doc()
    titular = persona(numero=f"{numero[:2]}.{numero[2:5]}.{numero[5:]}", pais="pe")
    sol = solicitud(salida_prueba(), titular=titular, telefono="+33 6 12 34 56 78")
    sol.acompanantes = [persona(tipo_doc="PASAPORTE", numero="ab" + doc(), tipo=2)]
    codigo, _ = crear(app, sol)
    assert consultar_valor(app, "SELECT telefono FROM turista t JOIN reserva r ON r.turista_id = t.id "
                                "WHERE r.codigo = %s", (codigo,)) == "+33612345678"
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM reserva_pasajero rp JOIN reserva r ON r.id = rp.reserva_id "
                                "WHERE r.codigo = %s AND (rp.numero_documento = %s OR rp.numero_documento LIKE 'AB799%%')",
                           (codigo, numero)) == 2


def test_titular_existente_se_reutiliza_y_otro_nombre_se_rechaza(app, salida_prueba):
    salida_id = salida_prueba(cupo=10)
    titular = persona(nombres="José", apellidos="Pérez Lago")
    crear(app, solicitud(salida_id, titular=titular))
    # Mismo documento, mismo nombre sin tildes y en mayúsculas: es la misma persona
    igual = persona(numero=titular.numero_documento, nombres="JOSE", apellidos="perez lago")
    crear(app, solicitud(salida_prueba(hora=13), titular=igual, telefono="912345678"))
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM turista WHERE numero_documento = %s",
                           (titular.numero_documento,)) == 1
    assert consultar_valor(app, "SELECT telefono FROM turista WHERE numero_documento = %s",
                           (titular.numero_documento,)) == "912345678"
    otro = persona(numero=titular.numero_documento, nombres="María", apellidos="Otra Persona")
    with pytest.raises(m.TitularDistinto):
        crear(app, solicitud(salida_prueba(hora=17), titular=otro))


# --- RN-10: familia anfitriona por rotación --------------------------------------------------------

def familia_asignada(app, codigo):
    return consultar_valor(app, "SELECT h.familia_id FROM hospedaje h JOIN reserva r ON r.id = h.reserva_id "
                                "WHERE r.codigo = %s AND h.estado = 'asignado'", (codigo,))


def test_rotacion_justa_de_familias(app, salida_prueba):
    # Llachón: familia 6 (última noche hace 12 días, fuera de la ventana de 30 días previa),
    # familia 7 (1 noche dentro de la ventana) y familia 8 (nunca recibió).
    salida_id = salida_prueba(ruta_id=4, cupo=12, hora=7, horas_duracion=31)
    primera, _ = crear(app, solicitud(salida_id))
    segunda, _ = crear(app, solicitud(salida_id))
    tercera, _ = crear(app, solicitud(salida_id, acompanantes=1))
    assert familia_asignada(app, primera) == 8     # 0 noches y nunca recibió → va primero
    assert familia_asignada(app, segunda) == 6     # 0 noches en la ventana, espera desde hace 12 días
    assert familia_asignada(app, tercera) == 7     # 1 noche: la última en la fila
    assert consultar_valor(app, "SELECT h.monto_familia FROM hospedaje h JOIN reserva r ON r.id = h.reserva_id "
                                "WHERE r.codigo = %s", (tercera,)) == Decimal("80.00")   # 2 × S/ 40
    with pytest.raises(hospedaje.SinHospedaje):                                          # ya no hay familias
        crear(app, solicitud(salida_id))


def test_la_familia_debe_tener_capacidad_para_el_grupo(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=4, cupo=12, hora=7, horas_duracion=31)
    codigo, _ = crear(app, solicitud(salida_id, acompanantes=5))        # 6 personas
    assert familia_asignada(app, codigo) == 6                            # la única con capacidad 6
    with pytest.raises(hospedaje.SinHospedaje):
        crear(app, solicitud(salida_id, acompanantes=5))                 # otra de 6: no hay


def test_con_yape_se_revisa_la_familia_pero_se_asigna_al_pagar(app, salida_prueba):
    salida_id = salida_prueba(ruta_id=4, cupo=12, hora=7, horas_duracion=31)
    codigo, _ = crear(app, solicitud(salida_id, metodo="yape"))
    assert familia_asignada(app, codigo) is None
    with pytest.raises(hospedaje.SinHospedaje):
        crear(app, solicitud(salida_id, acompanantes=6, metodo="yape"))   # 7 personas: ninguna familia


# --- RN-06: reporte de pago -------------------------------------------------------------------------

def test_reportar_pago_guarda_el_cupo_hasta_60_minutos_antes(app, salida_prueba):
    codigo, _ = crear(app, solicitud(salida_prueba(), metodo="yape"))
    with app.app_context():
        m.reportar_pago(codigo, "yape", "30.00", "79991234")
    assert consultar_valor(app, "SELECT p.estado FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                "WHERE r.codigo = %s", (codigo,)) == "reportado"
    assert consultar_valor(app, "SELECT TIMESTAMPDIFF(MINUTE, r.vence_en, s.fecha_hora_zarpe) FROM reserva r "
                                "JOIN salida s ON s.id = r.salida_id WHERE r.codigo = %s", (codigo,)) == 60
    with app.app_context(), pytest.raises(m.ErrorValidacion, match="Revisa"):
        m.reportar_pago(codigo, "yape", "30.00", "79991234")             # mismo número de operación


@pytest.mark.parametrize("monto, numero, campo", [
    ("0", "79995678", "monto"), ("abc", "79995678", "monto"), ("31.00", "79995678", "monto"),
    ("30.00", "12", "numero_operacion"),
])
def test_reporte_de_pago_invalido(app, salida_prueba, monto, numero, campo):
    codigo, _ = crear(app, solicitud(salida_prueba(), metodo="yape"))
    with app.app_context(), pytest.raises(m.ErrorValidacion) as error:
        m.reportar_pago(codigo, "yape", monto, numero)
    assert campo in error.value.errores


def test_no_se_reporta_pago_de_una_reserva_que_no_lo_espera(app, salida_prueba):
    codigo, _ = crear(app, solicitud(salida_prueba(), metodo="muelle"))
    with app.app_context(), pytest.raises(m.EstadoNoPermite):
        m.reportar_pago(codigo, "yape", "30.00", "79997777")


# --- RN-05: comando vencer ----------------------------------------------------------------------------

def test_vencer_pendientes(app, salida_prueba):
    codigo, _ = crear(app, solicitud(salida_prueba(), metodo="plin"))
    ejecutar_y_confirmar(app, "UPDATE reserva SET vence_en = NOW() - INTERVAL 5 MINUTE WHERE codigo = %s",
                         (codigo,))
    with app.app_context():
        vencidas = m.vencer_pendientes()
    assert codigo in vencidas
    assert fila_reserva(app, codigo)["estado"] == "vencida"
    with app.app_context():
        assert codigo not in m.vencer_pendientes()          # la segunda vez ya no hay nada que vencer


def test_validar_acceso(app, salida_prueba):
    titular = persona()
    codigo, _ = crear(app, solicitud(salida_prueba(), titular=titular))
    with app.app_context():
        assert m.validar_acceso(codigo.lower(), f" {titular.numero_documento} ")
        assert not m.validar_acceso(codigo, "00000000")
