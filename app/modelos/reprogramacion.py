"""Salida suspendida (RN-11): el turista reprograma a otra salida de la misma ruta o pide la
devolución. Reprogramar actualiza la MISMA reserva (D-04, S-22): el código, los pagos, los
precios y el boleto siguen valiendo. La devolución se registra; el reembolso es a mano (D-11).
"""

import pymysql

from app import bd
from app.modelos import (
    ErrorNegocio,
    ErrorValidacion,
    EstadoNoPermite,
    bitacora,
    exigir_rol,
    hospedaje,
)
from app.modelos.reserva import DocumentoRepetido, SalidaNoDisponible, SinCupo
from app.modelos.salida import contar_ocupados

ESTADOS_QUE_REPROGRAMAN = ("pendiente_pago", "confirmada", "pagada")


def puede(reserva):
    """True si la reserva (de buscar_por_codigo) puede reprogramar o pedir la devolución."""
    return (reserva["salida_estado"] == "suspendida"
            and reserva["estado"] in ESTADOS_QUE_REPROGRAMAN
            and (reserva["estado"] != "pendiente_pago" or bool(reserva["vigente"])))


def opciones(codigo):
    # Devuelve las salidas de la MISMA ruta que todavía reciben reservas y tienen lugar para
    # todo el grupo (subconsulta que cuenta sus pasajeros), y si una alerta naranja o roja las
    # afecta (para avisar antes de elegir).
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.fecha_hora_retorno, v.libres,
               v.estado_publico, v.embarcacion_nombre,
               EXISTS (SELECT 1 FROM alerta_lago a
                       WHERE a.nivel IN ('naranja','rojo')
                         AND a.vigente_desde < v.fecha_hora_retorno
                         AND a.vigente_hasta > v.fecha_hora_zarpe
                         AND (a.comunidad_id IS NULL
                              OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp
                                                    WHERE rp.ruta_id = v.ruta_id))
               ) AS afectada_por_alerta
        FROM reserva r
        JOIN salida s0 ON s0.id = r.salida_id
        JOIN v_disponibilidad_salida v ON v.ruta_id = s0.ruta_id AND v.salida_id <> s0.id
        WHERE r.codigo = %s
          AND v.estado = 'programada'
          AND v.fecha_hora_zarpe > NOW()
          AND v.libres >= (SELECT COUNT(*) FROM reserva_pasajero rp WHERE rp.reserva_id = r.id)
        ORDER BY v.fecha_hora_zarpe
        LIMIT 20
        """,
        (codigo,),
    )


def _abrir(conexion):
    """Transacción en READ COMMITTED que empieza limpia (D-50)."""
    conexion.rollback()
    with conexion.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
    conexion.begin()


def _bloquear_reserva(cur, codigo):
    # Devuelve la reserva (sin bloquear: solo para saber qué salidas bloquear primero).
    cur.execute("SELECT id, salida_id FROM reserva WHERE codigo = %s", (codigo,))
    fila = cur.fetchone()
    if fila is None:
        raise EstadoNoPermite("Esa reserva no existe.")
    return fila


def reprogramar(codigo, salida_nueva_id, ip=None):
    """Pasa la reserva a otra salida de la misma ruta, con las reglas RN-02 y RN-09."""
    conexion = bd.obtener_conexion()
    _abrir(conexion)
    try:
        with conexion.cursor() as cur:
            ids = _bloquear_reserva(cur, codigo)
            vieja_id = ids["salida_id"]
            # Devuelve las DOS salidas y las bloquea en orden de id (S-22): dos turistas que
            # reprograman en sentidos opuestos no se quedan esperándose para siempre.
            cur.execute(
                """
                SELECT id, ruta_id, cupo, estado, fecha_hora_zarpe,
                       (fecha_hora_zarpe > NOW()) AS aun_no_zarpa
                FROM salida
                WHERE id IN (%s, %s)
                ORDER BY id
                FOR UPDATE
                """,
                (vieja_id, salida_nueva_id),
            )
            salidas = {s["id"]: s for s in cur.fetchall()}
            # Devuelve la reserva BLOQUEADA, con su estado actual y si su plazo sigue vigente.
            cur.execute(
                """
                SELECT id, estado, salida_id, (vence_en > NOW()) AS vigente
                FROM reserva
                WHERE id = %s
                FOR UPDATE
                """,
                (ids["id"],),
            )
            reserva = cur.fetchone()
            vieja, nueva = salidas.get(reserva["salida_id"]), salidas.get(salida_nueva_id)
            if reserva["salida_id"] != vieja_id or not puede({
                    "salida_estado": vieja["estado"], "estado": reserva["estado"],
                    "vigente": reserva["vigente"]}):
                raise EstadoNoPermite("Esta reserva no se puede reprogramar: su salida no está "
                                      "suspendida o la reserva ya no está activa.")
            if (nueva is None or nueva["id"] == vieja["id"] or nueva["ruta_id"] != vieja["ruta_id"]
                    or nueva["estado"] != "programada" or not nueva["aun_no_zarpa"]):
                raise SalidaNoDisponible("Elige otra salida de la misma ruta que todavía no zarpa.")

            # Devuelve los documentos de los pasajeros de la reserva.
            cur.execute(
                "SELECT tipo_documento, numero_documento FROM reserva_pasajero "
                "WHERE reserva_id = %s",
                (reserva["id"],),
            )
            pasajeros = cur.fetchall()
            libres = max(nueva["cupo"] - contar_ocupados(cur, nueva["id"]), 0)
            if len(pasajeros) > libres:
                raise SinCupo(f"Solo quedan {libres} lugares en esa salida.")
            _revisar_documentos(cur, nueva["id"], pasajeros)
            _mover_hospedaje(cur, reserva, vieja, nueva, len(pasajeros), ip)

            cur.execute(
                "UPDATE reserva SET salida_id = %s, reprogramada_desde_salida_id = %s "
                "WHERE id = %s",
                (nueva["id"], vieja["id"], reserva["id"]),
            )
            bitacora.anotar(cur, None, "reprogramacion", "reserva", reserva["id"],
                            {"desde_salida": vieja["id"], "a_salida": nueva["id"]}, ip)
        conexion.commit()
    except pymysql.err.OperationalError as error:
        conexion.rollback()
        if error.args[0] in (1205, 1213):
            raise ErrorNegocio(
                "Hay muchas reservas al mismo tiempo. Inténtalo de nuevo.") from error
        raise
    except Exception:
        conexion.rollback()
        raise


def _revisar_documentos(cur, salida_id, pasajeros):
    # RN-09: devuelve los documentos de esta reserva que YA viajan en la salida nueva.
    marcas = ", ".join(["(%s, %s)"] * len(pasajeros))      # un par (tipo, número) por pasajero
    cur.execute(
        f"""
        SELECT rp.tipo_documento, rp.numero_documento
        FROM reserva_pasajero rp
        JOIN reserva r ON r.id = rp.reserva_id
        WHERE r.salida_id = %s
          AND (r.estado IN ('confirmada','pagada','abordada')
               OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
          AND (rp.tipo_documento, rp.numero_documento) IN ({marcas})
        LOCK IN SHARE MODE
        """,  # noqa: S608 (solo marcas %s; los valores van como parámetros)
        [salida_id, *[x for p in pasajeros for x in (p["tipo_documento"], p["numero_documento"])]],
    )
    repetido = cur.fetchone()
    if repetido:
        raise DocumentoRepetido(f"El documento {repetido['tipo_documento']} "
                                f"{repetido['numero_documento']} ya viaja en esa salida.")


def _mover_hospedaje(cur, reserva, vieja, nueva, personas, ip):
    """S-20: si cambia la noche, la noche vieja pasa a 'cancelado' y se asigna una nueva (RN-10)."""
    comunidad_id = hospedaje.comunidad_de_pernocte(cur, nueva["ruta_id"])
    noche_nueva = nueva["fecha_hora_zarpe"].date()
    if comunidad_id is None or noche_nueva == vieja["fecha_hora_zarpe"].date():
        return                                       # sin noche, o la misma noche: nada cambia
    cur.execute(
        """
        UPDATE hospedaje SET estado = 'cancelado', motivo_reasignacion = %s
        WHERE reserva_id = %s AND estado = 'asignado'
        """,
        (f"Reprogramada a la salida {nueva['id']}", reserva["id"]),
    )
    if reserva["estado"] == "pendiente_pago":       # D-52: la familia se asigna al pagar
        if hospedaje.elegir_familia(cur, comunidad_id, noche_nueva, personas) is None:
            raise hospedaje.SinHospedaje(hospedaje.mensaje_sin_familia(personas))
    else:
        hospedaje.asignar(cur, reserva["id"], comunidad_id, noche_nueva, personas, None, ip)


def pedir_devolucion(codigo, ip=None):
    """D-11: la reserva pasa a 'cancelada' y queda 'devolucion_solicitada' en la bitácora.

    Devuelve el monto verificado que la agencia tiene que devolver (puede ser 0).
    """
    with bd.transaccion(lectura_actual=True) as cur:
        ids = _bloquear_reserva(cur, codigo)
        # Devuelve la salida con lectura compartida (mismo orden que el resto: salida y reserva).
        cur.execute("SELECT estado, motivo_estado FROM salida WHERE id = %s LOCK IN SHARE MODE",
                    (ids["salida_id"],))
        salida = cur.fetchone()
        # Devuelve la reserva BLOQUEADA, con su estado y si su plazo sigue vigente.
        cur.execute("SELECT id, estado, (vence_en > NOW()) AS vigente FROM reserva "
                    "WHERE id = %s FOR UPDATE", (ids["id"],))
        reserva = cur.fetchone()
        if not puede({"salida_estado": salida["estado"], "estado": reserva["estado"],
                      "vigente": reserva["vigente"]}):
            raise EstadoNoPermite("La devolución se pide cuando la salida está suspendida.")
        # Devuelve lo pagado y verificado de la reserva (eso es lo que se devuelve).
        cur.execute("SELECT COALESCE(SUM(monto), 0) AS pagado FROM pago "
                    "WHERE reserva_id = %s AND estado = 'verificado'", (reserva["id"],))
        pagado = cur.fetchone()["pagado"]
        cur.execute("UPDATE reserva SET estado = 'cancelada' WHERE id = %s", (reserva["id"],))
        cur.execute(
            """
            UPDATE hospedaje
            SET estado = 'cancelado', motivo_reasignacion = 'Devolución por suspensión'
            WHERE reserva_id = %s AND estado = 'asignado'
            """,
            (reserva["id"],),
        )
        bitacora.anotar(cur, None, "cambio_estado", "reserva", reserva["id"],
                        {"de": reserva["estado"], "a": "cancelada",
                         "motivo": "salida suspendida"}, ip)
        bitacora.anotar(cur, None, "devolucion_solicitada", "reserva", reserva["id"],
                        {"monto_verificado": pagado, "motivo": salida["motivo_estado"]}, ip)
    return pagado


# --- Panel: devoluciones por atender (D-11) ---------------------------------------------------

def devoluciones_pendientes(actor):
    exigir_rol(actor, "admin", "operador")
    # Devuelve las devoluciones pedidas que todavía no se atendieron (NOT EXISTS: no hay un
    # 'devolucion_atendida' para esa reserva), con el titular y lo pagado (subconsulta).
    return bd.consultar(
        """
        SELECT b.registro_id AS reserva_id, b.creado_en, r.codigo, t.nombres, t.apellidos,
               t.telefono, t.correo,
               COALESCE((SELECT SUM(p.monto) FROM pago p
                         WHERE p.reserva_id = r.id AND p.estado = 'verificado'), 0) AS pagado
        FROM bitacora b
        JOIN reserva r ON r.id = b.registro_id
        JOIN turista t ON t.id = r.turista_id
        WHERE b.accion = 'devolucion_solicitada' AND b.tabla_afectada = 'reserva'
          AND NOT EXISTS (SELECT 1 FROM bitacora b2
                          WHERE b2.accion = 'devolucion_atendida'
                            AND b2.tabla_afectada = 'reserva'
                            AND b2.registro_id = b.registro_id)
        ORDER BY b.creado_en
        """
    )


def atender_devolucion(actor, reserva_id, nota, ip=None):
    """El operador ya devolvió el dinero a mano: lo deja en la bitácora."""
    exigir_rol(actor, "operador")
    nota = " ".join((nota or "").split())
    if not 5 <= len(nota) <= 255:
        raise ErrorValidacion({"nota": "Escribe cómo se devolvió (5 a 255 caracteres)."})
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la reserva BLOQUEADA (dos operadores no atienden la misma devolución).
        cur.execute("SELECT id FROM reserva WHERE id = %s FOR UPDATE", (reserva_id,))
        if cur.fetchone() is None:
            raise EstadoNoPermite("Esa reserva no existe.")
        # Devuelve 1 si hay una devolución pedida y otra vez 1 si ya se atendió.
        cur.execute(
            """
            SELECT SUM(accion = 'devolucion_solicitada') AS pedidas,
                   SUM(accion = 'devolucion_atendida') AS atendidas
            FROM bitacora
            WHERE tabla_afectada = 'reserva' AND registro_id = %s
            """,
            (reserva_id,),
        )
        fila = cur.fetchone()
        if not fila["pedidas"] or fila["atendidas"]:
            raise EstadoNoPermite("Esa devolución no está pendiente.")
        bitacora.anotar(cur, actor.id, "devolucion_atendida", "reserva", reserva_id,
                        {"nota": nota}, ip)

