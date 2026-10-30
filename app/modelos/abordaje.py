"""Abordaje en el muelle (RN-12), por QR o desde la lista de pasajeros.

El QR del boleto abre /panel/abordaje/<código>. Pueden registrar el operador y el guía o el
capitán de ESA salida (S-23). Solo el día de la salida, de 60 minutos antes a 15 minutos
después del zarpe. Cada pasajero aborda una vez; cuando abordan todos, la reserva pasa a
'abordada'.
"""

import pymysql

from app import bd
from app.modelos import (
    ERROR_DUPLICADO,
    ErrorValidacion,
    EstadoNoPermite,
    PermisoDenegado,
    bitacora,
    exigir_rol,
)
from app.modelos.salida import es_suya

MINUTOS_ANTES, MINUTOS_DESPUES = 60, 15
ESTADOS_QUE_ABORDAN = ("confirmada", "pagada", "abordada")   # S-11: 'confirmada' paga en el muelle
METODOS = ("qr", "manual")
ROLES_ABORDAJE = ("operador", "guia", "capitan")


def buscar(actor, codigo):
    """La reserva con su salida y sus pasajeros (con quién ya abordó), o None si no existe."""
    exigir_rol(actor, *ROLES_ABORDAJE)
    # Devuelve la reserva con su salida (estado, hora, capitán y guía), el titular, lo pagado
    # (pagos verificados) y si AHORA está abierta la ventana de abordaje de RN-12.
    reserva = bd.consultar_uno(
        """
        SELECT r.id, r.codigo, r.estado, r.total, r.metodo_pago_elegido,
               s.id AS salida_id, s.fecha_hora_zarpe, s.estado AS salida_estado,
               s.capitan_id, s.guia_id, ru.nombre AS ruta_nombre,
               e.nombre AS embarcacion_nombre,
               t.nombres, t.apellidos, t.telefono,
               COALESCE((SELECT SUM(p.monto) FROM pago p
                         WHERE p.reserva_id = r.id AND p.estado = 'verificado'), 0) AS pagado,
               (NOW() BETWEEN s.fecha_hora_zarpe - INTERVAL %s MINUTE
                          AND s.fecha_hora_zarpe + INTERVAL %s MINUTE) AS en_ventana,
               (NOW() < s.fecha_hora_zarpe - INTERVAL %s MINUTE) AS antes_de_ventana
        FROM reserva r
        JOIN salida s      ON s.id = r.salida_id
        JOIN ruta ru       ON ru.id = s.ruta_id
        JOIN embarcacion e ON e.id = s.embarcacion_id
        JOIN turista t     ON t.id = r.turista_id
        WHERE r.codigo = %s
        """,
        (MINUTOS_ANTES, MINUTOS_DESPUES, MINUTOS_ANTES, codigo),
    )
    if reserva is None:
        return None
    if not es_suya(actor, reserva):
        raise PermisoDenegado("Esta reserva es de una salida que no tienes asignada.")
    # Devuelve los pasajeros de la reserva y, si ya abordaron esta salida, cuándo
    # (LEFT JOIN: el que no abordó aparece con abordo_en en NULL).
    reserva["pasajeros"] = bd.consultar(
        """
        SELECT rp.id, rp.nombres, rp.apellidos, rp.tipo_documento, rp.numero_documento,
               rp.nacionalidad, tp.nombre AS tipo, a.registrado_en AS abordo_en, a.metodo
        FROM reserva_pasajero rp
        JOIN tipo_pasajero tp ON tp.id = rp.tipo_pasajero_id
        LEFT JOIN abordaje a  ON a.reserva_pasajero_id = rp.id AND a.salida_id = %s
        WHERE rp.reserva_id = %s
        ORDER BY rp.id
        """,
        (reserva["salida_id"], reserva["id"]),
    )
    reserva["faltan"] = sum(1 for p in reserva["pasajeros"] if p["abordo_en"] is None)
    reserva["motivo_no"] = por_que_no_puede(reserva)
    return reserva


def por_que_no_puede(reserva):
    """None si se puede registrar el abordaje; si no, el motivo para mostrarlo."""
    if reserva["estado"] == "pendiente_pago":
        return "Falta verificar el pago (Yape o Plin) de esta reserva."
    if reserva["estado"] not in ESTADOS_QUE_ABORDAN:
        return f"La reserva está «{reserva['estado']}»: no puede abordar."
    if reserva["salida_estado"] not in ("programada", "embarcando"):
        return f"La salida está «{reserva['salida_estado']}»: ya no se registra el abordaje."
    if not reserva["en_ventana"]:
        if reserva["antes_de_ventana"]:
            return (f"El abordaje abre {MINUTOS_ANTES} minutos antes del zarpe "
                    f"({reserva['fecha_hora_zarpe']:%d/%m a las %H:%M}).")
        return f"El abordaje cerró {MINUTOS_DESPUES} minutos después del zarpe."
    if reserva.get("faltan") == 0:
        return "Todos los pasajeros de esta reserva ya abordaron."
    return None


def registrar(actor, codigo, pasajero_ids, metodo, ip=None):
    """Registra el abordaje de los pasajeros marcados. Devuelve {registrados, faltan, abordada}."""
    exigir_rol(actor, *ROLES_ABORDAJE)
    if metodo not in METODOS:
        metodo = "manual"
    if not pasajero_ids:
        raise ErrorValidacion({"pasajeros": "Marca al menos un pasajero."})

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la reserva y su salida (sin bloquear: solo para saber qué bloquear
        # y en qué orden).
        cur.execute("SELECT id, salida_id FROM reserva WHERE codigo = %s", (codigo,))
        ids = cur.fetchone()
        if ids is None:
            raise EstadoNoPermite("Esa reserva no existe.")
        # Devuelve la salida con lectura compartida (mismo orden que el zarpe: salida y luego
        # reserva, así no se cruzan los bloqueos) y si la ventana de RN-12 está abierta.
        cur.execute(
            """
            SELECT id, estado AS salida_estado, capitan_id, guia_id, fecha_hora_zarpe,
                   (NOW() BETWEEN fecha_hora_zarpe - INTERVAL %s MINUTE
                              AND fecha_hora_zarpe + INTERVAL %s MINUTE) AS en_ventana,
                   (NOW() < fecha_hora_zarpe - INTERVAL %s MINUTE) AS antes_de_ventana
            FROM salida
            WHERE id = %s
            LOCK IN SHARE MODE
            """,
            (MINUTOS_ANTES, MINUTOS_DESPUES, MINUTOS_ANTES, ids["salida_id"]),
        )
        salida = cur.fetchone()
        if not es_suya(actor, salida):
            raise PermisoDenegado("Esta reserva es de una salida que no tienes asignada.")
        # Devuelve la reserva y la BLOQUEA: dos guías que leen el mismo QR van uno tras otro.
        cur.execute("SELECT id, codigo, estado FROM reserva WHERE id = %s FOR UPDATE", (ids["id"],))
        reserva = {**salida, **cur.fetchone()}
        motivo = por_que_no_puede(reserva)
        if motivo:
            raise EstadoNoPermite(motivo)

        # Devuelve los pasajeros de la reserva y, si ya abordaron, el id de su abordaje.
        cur.execute(
            """
            SELECT rp.id, a.id AS abordaje_id
            FROM reserva_pasajero rp
            LEFT JOIN abordaje a ON a.reserva_pasajero_id = rp.id AND a.salida_id = %s
            WHERE rp.reserva_id = %s
            """,
            (salida["id"], reserva["id"]),
        )
        pasajeros = {p["id"]: p["abordaje_id"] for p in cur.fetchall()}
        if not set(pasajero_ids) <= set(pasajeros):
            raise ErrorValidacion({"pasajeros": "Uno de los pasajeros no es de esta reserva."})
        nuevos = [pid for pid in sorted(set(pasajero_ids)) if pasajeros[pid] is None]
        if not nuevos:
            raise EstadoNoPermite("Esos pasajeros ya abordaron.")
        try:
            cur.executemany(
                """
                INSERT INTO abordaje (reserva_pasajero_id, salida_id, registrado_por, metodo)
                VALUES (%s, %s, %s, %s)
                """,
                [(pid, salida["id"], actor.id, metodo) for pid in nuevos],
            )
        except pymysql.err.IntegrityError as error:
            if error.args[0] == ERROR_DUPLICADO:               # RN-12: una sola vez (UNIQUE)
                raise EstadoNoPermite("Uno de esos pasajeros ya abordó.") from error
            raise
        bitacora.anotar(cur, actor.id, "abordaje", "reserva", reserva["id"],
                        {"pasajeros": nuevos, "metodo": metodo}, ip)

        faltan = sum(1 for abordo in pasajeros.values() if abordo is None) - len(nuevos)
        abordada = faltan == 0 and reserva["estado"] != "abordada"
        if abordada:
            cur.execute("UPDATE reserva SET estado = 'abordada' WHERE id = %s", (reserva["id"],))
            bitacora.anotar(cur, actor.id, "cambio_estado", "reserva", reserva["id"],
                            {"de": reserva["estado"], "a": "abordada"}, ip)
    return {"registrados": len(nuevos), "faltan": faltan, "abordada": abordada}
