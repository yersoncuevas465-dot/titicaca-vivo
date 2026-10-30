"""Pagos (RN-06): el operador verifica o rechaza lo que reportó el turista y registra lo que
se cobra en el muelle. Cuando lo verificado alcanza el total, la reserva pasa a 'pagada' y, si
la ruta tiene noche, se asigna la familia anfitriona en la misma transacción (RN-10, D-52).

El reporte del turista (Yape/Plin) está en reserva.reportar_pago (F4).
"""

import re
from decimal import Decimal, InvalidOperation

import pymysql
from flask import current_app

from app import bd
from app.modelos import (
    ERROR_DUPLICADO,
    ErrorValidacion,
    EstadoNoPermite,
    bitacora,
    exigir_rol,
    hospedaje,
)

METODOS_MUELLE = ("efectivo_muelle", "pos", "transferencia")
PATRON_OPERACION = re.compile(r"^[A-Za-z0-9-]{4,30}$")
LARGO_OBSERVACION = (5, 255)


# --- Consultas -------------------------------------------------------------------------------

def listar_por_verificar(actor):
    """Pagos 'reportado', del más antiguo al más nuevo (el primero que llegó se revisa primero)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve los pagos que esperan verificación con su reserva, titular, salida y ruta, el
    # total y lo ya verificado de esa reserva (subconsulta), y si la reserva sigue vigente.
    return bd.consultar(
        """
        SELECT p.id, p.metodo, p.monto, p.numero_operacion, p.reportado_en,
               r.codigo, r.estado AS estado_reserva, r.total, r.vence_en,
               (r.vence_en > NOW()) AS vigente,
               t.nombres, t.apellidos, t.telefono,
               s.fecha_hora_zarpe, ru.nombre AS ruta_nombre,
               COALESCE((SELECT SUM(p2.monto) FROM pago p2
                         WHERE p2.reserva_id = r.id AND p2.estado = 'verificado'), 0) AS pagado
        FROM pago p
        JOIN reserva r  ON r.id = p.reserva_id
        JOIN turista t  ON t.id = r.turista_id
        JOIN salida s   ON s.id = r.salida_id
        JOIN ruta ru    ON ru.id = s.ruta_id
        WHERE p.estado = 'reportado'
        ORDER BY p.reportado_en, p.id
        """
    )


def ultimos_revisados(actor, limite=10):
    exigir_rol(actor, "admin", "operador")
    # Devuelve los últimos pagos ya verificados o rechazados, con quién los revisó y cuándo.
    return bd.consultar(
        """
        SELECT p.id, p.metodo, p.monto, p.numero_operacion, p.estado, p.verificado_en,
               p.observacion, r.codigo, u.nombre_usuario
        FROM pago p
        JOIN reserva r        ON r.id = p.reserva_id
        LEFT JOIN usuario u   ON u.id = p.verificado_por
        WHERE p.estado <> 'reportado'
        ORDER BY p.verificado_en DESC, p.id DESC
        LIMIT %s
        """,
        (limite,),
    )


# --- Bloqueos (siempre la reserva primero y después el pago) ---------------------------------

def _bloquear_reserva(cur, reserva_id=None, codigo=None):
    if reserva_id is None:
        # Devuelve el id de la reserva con ese código (sin bloquear: así se bloquea por la PK).
        cur.execute("SELECT id FROM reserva WHERE codigo = %s", (codigo,))
        fila = cur.fetchone()
        if fila is None:
            raise EstadoNoPermite("Esa reserva no existe.")
        reserva_id = fila["id"]
    # Devuelve la reserva y la BLOQUEA hasta el COMMIT, con si su plazo de pago sigue vigente.
    cur.execute(
        """
        SELECT r.id, r.codigo, r.estado, r.total, r.salida_id, (r.vence_en > NOW()) AS vigente
        FROM reserva r
        WHERE r.id = %s
        FOR UPDATE
        """,
        (reserva_id,),
    )
    reserva = cur.fetchone()
    if reserva is None:
        raise EstadoNoPermite("Esa reserva no existe.")
    return reserva


def _bloquear_pago(cur, pago_id):
    # Devuelve la reserva del pago (sin bloquear: solo para saber qué fila bloquear primero).
    cur.execute("SELECT reserva_id FROM pago WHERE id = %s", (pago_id,))
    fila = cur.fetchone()
    if fila is None:
        raise EstadoNoPermite("Ese pago no existe.")
    reserva = _bloquear_reserva(cur, reserva_id=fila["reserva_id"])
    # Devuelve el pago y lo BLOQUEA: dos operadores no pueden revisarlo a la vez.
    cur.execute("SELECT id, metodo, monto, estado FROM pago WHERE id = %s FOR UPDATE", (pago_id,))
    return reserva, cur.fetchone()


def _pagado(cur, reserva_id):
    # Devuelve la suma de los pagos verificados de la reserva (RN-06; un rechazado no suma).
    cur.execute(
        """
        SELECT COALESCE(SUM(monto), 0) AS pagado
        FROM pago
        WHERE reserva_id = %s AND estado = 'verificado'
        """,
        (reserva_id,),
    )
    return cur.fetchone()["pagado"]


def _pasar_a_pagada_si_alcanza(cur, actor, reserva, ip):
    """RN-06: con lo verificado >= total, la reserva pasa a 'pagada'. RN-10: familia (D-52)."""
    pagado = _pagado(cur, reserva["id"])
    resultado = {"codigo": reserva["codigo"], "pagado": pagado, "total": reserva["total"],
                 "pagada": False, "familia": None, "aviso": None}
    if pagado < reserva["total"] or reserva["estado"] not in ("pendiente_pago", "confirmada"):
        return resultado

    cur.execute("UPDATE reserva SET estado = 'pagada' WHERE id = %s", (reserva["id"],))
    bitacora.anotar(cur, actor.id, "cambio_estado", "reserva", reserva["id"],
                    {"de": reserva["estado"], "a": "pagada", "pagado": pagado}, ip)
    resultado["pagada"] = True

    # Devuelve la ruta y la fecha de la salida, cuántos pasajeros tiene la reserva y si ya
    # tiene una noche con familia (las reservas del muelle la reciben al crearse).
    cur.execute(
        """
        SELECT s.ruta_id, DATE(s.fecha_hora_zarpe) AS fecha_noche,
               (SELECT COUNT(*) FROM reserva_pasajero rp WHERE rp.reserva_id = %s) AS personas,
               (SELECT COUNT(*) FROM hospedaje h
                WHERE h.reserva_id = %s AND h.estado <> 'cancelado') AS noches
        FROM salida s
        WHERE s.id = %s
        """,
        (reserva["id"], reserva["id"], reserva["salida_id"]),
    )
    viaje = cur.fetchone()
    comunidad_id = hospedaje.comunidad_de_pernocte(cur, viaje["ruta_id"])
    if comunidad_id and not viaje["noches"]:
        try:
            familia = hospedaje.asignar(cur, reserva["id"], comunidad_id, viaje["fecha_noche"],
                                        viaje["personas"], actor.id, ip)
            resultado["familia"] = familia["nombre_familia"]
        except hospedaje.SinHospedaje:
            # El pago es real: se verifica igual y la reserva queda pagada, sin familia (D-69).
            bitacora.anotar(cur, actor.id, "sin_familia", "reserva", reserva["id"],
                            {"fecha_noche": viaje["fecha_noche"], "personas": viaje["personas"]},
                            ip)
            resultado["aviso"] = ("No hay una familia libre con capacidad para esa noche: "
                                  "la reserva quedó pagada pero SIN familia. Coordina con la "
                                  "comunidad.")
    return resultado


# --- Acciones del operador -------------------------------------------------------------------

def verificar(actor, pago_id, ip=None):
    """Marca el pago como verificado. Devuelve el resultado (si la reserva quedó pagada...)."""
    exigir_rol(actor, "operador")
    with bd.transaccion(lectura_actual=True) as cur:
        reserva, pago = _bloquear_pago(cur, pago_id)
        if pago["estado"] != "reportado":
            raise EstadoNoPermite("Este pago ya fue revisado.")
        if reserva["estado"] != "pendiente_pago" or not reserva["vigente"]:
            raise EstadoNoPermite(
                f"La reserva {reserva['codigo']} ya no espera este pago (venció, se canceló o ya "
                "está pagada): su lugar no está guardado. Rechaza el pago para devolver el dinero.")
        cur.execute(
            """
            UPDATE pago
            SET estado = 'verificado', verificado_por = %s, verificado_en = NOW()
            WHERE id = %s
            """,
            (actor.id, pago_id),
        )
        bitacora.anotar(cur, actor.id, "cambio_estado", "pago", pago_id,
                        {"de": "reportado", "a": "verificado", "reserva": reserva["codigo"],
                         "monto": pago["monto"]}, ip)
        return _pasar_a_pagada_si_alcanza(cur, actor, reserva, ip)


def _validar_observacion(observacion):
    observacion = " ".join((observacion or "").split())
    minimo, maximo = LARGO_OBSERVACION
    if not minimo <= len(observacion) <= maximo:
        raise ErrorValidacion({"observacion": "Escribe por qué se rechaza "
                                              f"({minimo} a {maximo} caracteres)."})
    return observacion


def rechazar(actor, pago_id, observacion, ip=None):
    """Rechaza el pago. Si era el único por revisar, el turista vuelve a tener 2 h (D-09)."""
    exigir_rol(actor, "operador")
    observacion = _validar_observacion(observacion)
    with bd.transaccion(lectura_actual=True) as cur:
        reserva, pago = _bloquear_pago(cur, pago_id)
        if pago["estado"] != "reportado":
            raise EstadoNoPermite("Este pago ya fue revisado.")
        cur.execute(
            """
            UPDATE pago
            SET estado = 'rechazado', verificado_por = %s, verificado_en = NOW(), observacion = %s
            WHERE id = %s
            """,
            (actor.id, observacion, pago_id),
        )
        bitacora.anotar(cur, actor.id, "cambio_estado", "pago", pago_id,
                        {"de": "reportado", "a": "rechazado", "reserva": reserva["codigo"],
                         "observacion": observacion}, ip)
        if reserva["estado"] == "pendiente_pago" and reserva["vigente"]:
            # Devuelve cuántos pagos de la reserva siguen esperando verificación.
            cur.execute(
                "SELECT COUNT(*) AS otros FROM pago WHERE reserva_id = %s AND estado = 'reportado'",
                (reserva["id"],),
            )
            if cur.fetchone()["otros"] == 0:
                # D-09: el cupo ya no se guarda hasta el zarpe, sino 2 horas desde ahora.
                cur.execute(
                    "UPDATE reserva SET vence_en = NOW() + INTERVAL %s MINUTE WHERE id = %s",
                    (current_app.config["MINUTOS_VENCIMIENTO_PAGO"], reserva["id"]),
                )


def registrar_cobro(actor, codigo, metodo, monto, numero_operacion, ip=None):
    """Cobro en el muelle (efectivo, POS o transferencia): queda verificado de una vez."""
    exigir_rol(actor, "operador")
    errores = {}
    if metodo not in METODOS_MUELLE:
        errores["metodo"] = "Elige efectivo, POS o transferencia."
    try:
        monto = Decimal(str(monto)).quantize(Decimal("0.01"))
        if monto <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errores["monto"] = "Escribe el monto cobrado, por ejemplo 80.00."
    numero_operacion = (numero_operacion or "").strip() or None
    if numero_operacion and not PATRON_OPERACION.match(numero_operacion):
        errores["numero_operacion"] = "De 4 a 30 letras, números o guiones."
    elif metodo == "transferencia" and not numero_operacion:
        errores["numero_operacion"] = "Una transferencia necesita su número de operación."
    if errores:
        raise ErrorValidacion(errores)

    with bd.transaccion(lectura_actual=True) as cur:
        reserva = _bloquear_reserva(cur, codigo=codigo)
        if reserva["estado"] == "pagada":
            raise EstadoNoPermite("Esta reserva ya está pagada.")
        pendiente_vigente = reserva["estado"] == "pendiente_pago" and reserva["vigente"]
        if not pendiente_vigente and reserva["estado"] not in ("confirmada", "abordada"):
            raise EstadoNoPermite(f"La reserva está {reserva['estado']}: no se registra un cobro.")
        saldo = reserva["total"] - _pagado(cur, reserva["id"])
        if saldo <= 0:
            raise EstadoNoPermite("Esta reserva ya está pagada.")
        if monto > saldo:
            raise ErrorValidacion({"monto": f"Falta pagar S/ {saldo:.2f}: el monto no puede ser "
                                            "mayor."})
        try:
            cur.execute(
                """
                INSERT INTO pago (reserva_id, metodo, monto, numero_operacion, estado,
                                  verificado_por, verificado_en, observacion)
                VALUES (%s, %s, %s, %s, 'verificado', %s, NOW(), 'Cobrado en el muelle')
                """,
                (reserva["id"], metodo, monto, numero_operacion, actor.id),
            )
        except pymysql.err.IntegrityError as error:
            if error.args[0] == ERROR_DUPLICADO:
                raise ErrorValidacion(
                    {"numero_operacion": "Ese número de operación ya está registrado."}) from error
            raise
        bitacora.anotar(cur, actor.id, "cobro_muelle", "pago", cur.lastrowid,
                        {"reserva": reserva["codigo"], "metodo": metodo, "monto": monto}, ip)
        return _pasar_a_pagada_si_alcanza(cur, actor, reserva, ip)
