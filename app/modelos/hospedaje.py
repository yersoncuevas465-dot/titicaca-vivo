"""Hospedaje con familias anfitrionas: rotación justa (RN-10) y, en el panel (F6), reasignar,
confirmar noches cumplidas y el reporte de transparencia comunitaria.

Estas funciones reciben el cursor de una transacción ya abierta (la de la reserva):
la asignación queda o no queda junto con la reserva, nunca a medias.
"""

import json

from flask import current_app

from app import bd
from app.modelos import ErrorNegocio, ErrorValidacion, EstadoNoPermite, bitacora, exigir_rol


class SinHospedaje(ErrorNegocio):
    """No hay ninguna familia libre con capacidad para el grupo esa noche."""


def comunidad_de_pernocte(cur, ruta_id):
    # Devuelve la comunidad donde se duerme en la ruta (su parada con es_pernocte = 1), o None.
    cur.execute(
        "SELECT comunidad_id FROM ruta_parada WHERE ruta_id = %s AND es_pernocte = 1",
        (ruta_id,),
    )
    fila = cur.fetchone()
    return fila["comunidad_id"] if fila else None


def elegir_familia(cur, comunidad_id, fecha_noche, personas):
    """Devuelve la familia que toca según RN-10, o None. Bloquea las candidatas hasta el COMMIT."""
    # Devuelve UNA familia activa de la comunidad, con capacidad para el grupo y libre esa noche.
    # Orden de prioridad (RN-10):
    #   1) la que tuvo MENOS noches en los 30 días anteriores a esa noche;
    #   2) la que lleva más tiempo esperando: última noche más antigua
    #      (si nunca recibió, va primero);
    #   3) la de menor id.
    # FOR UPDATE bloquea las familias candidatas: dos reservas para la misma noche no pueden
    # quedarse con la misma familia al mismo tiempo (la segunda espera y luego ya no la ve libre).
    cur.execute(
        """
        SELECT f.id, f.nombre_familia, f.capacidad_personas,
               (SELECT COUNT(*) FROM hospedaje h
                WHERE h.familia_id = f.id
                  AND h.estado IN ('asignado','cumplido')
                  AND h.fecha_noche BETWEEN %s - INTERVAL 30 DAY AND %s - INTERVAL 1 DAY
               ) AS noches_30_dias,
               (SELECT MAX(h.fecha_noche) FROM hospedaje h
                WHERE h.familia_id = f.id
                  AND h.estado IN ('asignado','cumplido')
                  AND h.fecha_noche < %s
               ) AS ultima_noche
        FROM familia_anfitriona f
        WHERE f.comunidad_id = %s
          AND f.activa = 1
          AND f.capacidad_personas >= %s
          AND NOT EXISTS (SELECT 1 FROM hospedaje h
                          WHERE h.familia_id = f.id
                            AND h.fecha_noche = %s
                            AND h.estado IN ('asignado','cumplido'))
        ORDER BY noches_30_dias, ultima_noche IS NOT NULL, ultima_noche, f.id
        LIMIT 1
        FOR UPDATE
        """,
        (fecha_noche, fecha_noche, fecha_noche, comunidad_id, personas, fecha_noche),
    )
    return cur.fetchone()


def mensaje_sin_familia(personas):
    return (f"No hay una familia anfitriona libre para {personas} "
            f"{'persona' if personas == 1 else 'personas'} esa noche. "
            "Prueba otra fecha, divide el grupo en dos reservas o escribe a la agencia.")


def asignar(cur, reserva_id, comunidad_id, fecha_noche, personas, usuario_id=None, ip=None):
    """RN-10: asigna la familia que toca y lo anota en la bitácora. Devuelve la familia."""
    familia = elegir_familia(cur, comunidad_id, fecha_noche, personas)
    if familia is None:
        raise SinHospedaje(mensaje_sin_familia(personas))
    monto = personas * current_app.config["PAGO_FAMILIA_PERSONA_NOCHE"]
    # Si la reserva ya tuvo esa noche y se canceló (reprogramó y volvió a esa fecha), se
    # reutiliza su fila: UNIQUE(reserva_id, fecha_noche). LAST_INSERT_ID(id) deja su id
    # en lastrowid.
    cur.execute(
        """
        INSERT INTO hospedaje (reserva_id, familia_id, fecha_noche, personas, monto_familia, estado)
        VALUES (%s, %s, %s, %s, %s, 'asignado')
        ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id), familia_id = VALUES(familia_id),
                                personas = VALUES(personas), monto_familia = VALUES(monto_familia),
                                estado = 'asignado', motivo_reasignacion = NULL
        """,
        (reserva_id, familia["id"], fecha_noche, personas, monto),
    )
    detalle = {"familia_id": familia["id"], "fecha_noche": fecha_noche.isoformat(),
               "noches_30_dias": familia["noches_30_dias"], "regla": "rotacion RN-10"}
    cur.execute(
        """
        INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
        VALUES (%s, 'asignacion', 'hospedaje', %s, %s, %s)
        """,
        (usuario_id, cur.lastrowid, json.dumps(detalle), ip),
    )
    return familia


# =============================================================================================
# Panel (F6): asignaciones, reasignar con motivo, noches cumplidas y reporte de transparencia
# =============================================================================================

def listar_panel(actor, desde):
    exigir_rol(actor, "admin", "operador")
    # Devuelve las noches desde una fecha (no canceladas) con la familia, su comunidad, la
    # reserva (código y estado) y la ruta, y si la noche ya pasó (para marcarla cumplida).
    return bd.consultar(
        """
        SELECT h.id, h.fecha_noche, h.personas, h.monto_familia, h.estado, h.motivo_reasignacion,
               f.nombre_familia, c.nombre AS comunidad, r.codigo, r.estado AS estado_reserva,
               ru.nombre AS ruta_nombre, (h.fecha_noche < CURDATE()) AS ya_paso
        FROM hospedaje h
        JOIN familia_anfitriona f ON f.id = h.familia_id
        JOIN comunidad c          ON c.id = f.comunidad_id
        JOIN reserva r            ON r.id = h.reserva_id
        JOIN salida s             ON s.id = r.salida_id
        JOIN ruta ru              ON ru.id = s.ruta_id
        WHERE h.fecha_noche >= %s AND h.estado <> 'cancelado'
        ORDER BY h.fecha_noche, c.nombre, f.nombre_familia
        """,
        (desde,),
    )


def reservas_sin_familia(actor):
    exigir_rol(actor, "admin", "operador")
    # Devuelve las reservas confirmadas o pagadas de rutas con noche, por venir, que NO tienen
    # una noche asignada (NOT EXISTS): por ejemplo, si al pagar no quedaba familia libre (D-69).
    return bd.consultar(
        """
        SELECT r.codigo, r.estado, s.fecha_hora_zarpe, ru.nombre AS ruta_nombre,
               (SELECT COUNT(*) FROM reserva_pasajero rp WHERE rp.reserva_id = r.id) AS personas
        FROM reserva r
        JOIN salida s ON s.id = r.salida_id
        JOIN ruta ru  ON ru.id = s.ruta_id AND ru.incluye_pernocte = 1
        WHERE r.estado IN ('confirmada','pagada')
          AND s.estado IN ('programada','embarcando')
          AND s.fecha_hora_zarpe > NOW()
          AND NOT EXISTS (SELECT 1 FROM hospedaje h
                          WHERE h.reserva_id = r.id AND h.estado <> 'cancelado')
        ORDER BY s.fecha_hora_zarpe
        """
    )


def buscar_panel(actor, hospedaje_id):
    exigir_rol(actor, "admin", "operador")
    # Devuelve una noche con su familia actual, la comunidad y la reserva.
    return bd.consultar_uno(
        """
        SELECT h.id, h.reserva_id, h.familia_id, h.fecha_noche, h.personas, h.estado,
               h.motivo_reasignacion, f.nombre_familia, f.comunidad_id, c.nombre AS comunidad,
               r.codigo, (h.fecha_noche >= CURDATE()) AS por_venir
        FROM hospedaje h
        JOIN familia_anfitriona f ON f.id = h.familia_id
        JOIN comunidad c          ON c.id = f.comunidad_id
        JOIN reserva r            ON r.id = h.reserva_id
        WHERE h.id = %s
        """,
        (hospedaje_id,),
    )


def candidatas(actor, noche):
    """Familias a las que se puede pasar esa noche, en el orden de la rotación (RN-10)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve las OTRAS familias activas de la comunidad, con capacidad para el grupo y libres
    # esa noche, ordenadas con los 3 criterios de RN-10 (la primera es la que "toca").
    return bd.consultar(
        """
        SELECT f.id, f.nombre_familia, f.capacidad_personas,
               (SELECT COUNT(*) FROM hospedaje h
                WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido')
                  AND h.fecha_noche BETWEEN %s - INTERVAL 30 DAY AND %s - INTERVAL 1 DAY
               ) AS noches_30_dias,
               (SELECT MAX(h.fecha_noche) FROM hospedaje h
                WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido')
                  AND h.fecha_noche < %s) AS ultima_noche
        FROM familia_anfitriona f
        WHERE f.comunidad_id = %s AND f.activa = 1 AND f.id <> %s
          AND f.capacidad_personas >= %s
          AND NOT EXISTS (SELECT 1 FROM hospedaje h
                          WHERE h.familia_id = f.id AND h.fecha_noche = %s
                            AND h.estado IN ('asignado','cumplido'))
        ORDER BY noches_30_dias, ultima_noche IS NOT NULL, ultima_noche, f.id
        """,
        (noche["fecha_noche"], noche["fecha_noche"], noche["fecha_noche"], noche["comunidad_id"],
         noche["familia_id"], noche["personas"], noche["fecha_noche"]),
    )


def reasignar(actor, hospedaje_id, familia_id, motivo, ip=None):
    """RN-10: el operador pasa la noche a otra familia indicando el motivo (S-20: misma fila)."""
    exigir_rol(actor, "operador")
    motivo = " ".join((motivo or "").split())
    if not 5 <= len(motivo) <= 255:
        raise ErrorValidacion({"motivo": "Escribe el motivo (5 a 255 caracteres)."})
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la noche BLOQUEADA, con la comunidad de su familia actual.
        cur.execute(
            """
            SELECT h.id, h.familia_id, h.fecha_noche, h.personas, h.estado,
                   (h.fecha_noche >= CURDATE()) AS por_venir, f.comunidad_id
            FROM hospedaje h
            JOIN familia_anfitriona f ON f.id = h.familia_id
            WHERE h.id = %s
            FOR UPDATE
            """,
            (hospedaje_id,),
        )
        noche = cur.fetchone()
        if noche is None or noche["estado"] != "asignado" or not noche["por_venir"]:
            raise EstadoNoPermite("Solo se reasigna una noche asignada que todavía no pasó.")
        # Devuelve la familia elegida BLOQUEADA y si esa noche ya recibe a otro grupo.
        cur.execute(
            """
            SELECT f.comunidad_id, f.activa, f.capacidad_personas,
                   EXISTS (SELECT 1 FROM hospedaje h
                           WHERE h.familia_id = f.id AND h.fecha_noche = %s
                             AND h.estado IN ('asignado','cumplido')) AS ocupada
            FROM familia_anfitriona f
            WHERE f.id = %s
            FOR UPDATE
            """,
            (noche["fecha_noche"], familia_id),
        )
        nueva = cur.fetchone()
        if (nueva is None or familia_id == noche["familia_id"]
                or nueva["comunidad_id"] != noche["comunidad_id"] or not nueva["activa"]):
            raise ErrorValidacion(
                {"familia_id": "Elige otra familia activa de la misma comunidad."})
        if nueva["capacidad_personas"] < noche["personas"] or nueva["ocupada"]:
            raise ErrorValidacion(
                {"familia_id": "Esa familia no tiene lugar para el grupo esa noche."})
        cur.execute("UPDATE hospedaje SET familia_id = %s, motivo_reasignacion = %s WHERE id = %s",
                    (familia_id, motivo, hospedaje_id))
        bitacora.anotar(cur, actor.id, "reasignacion", "hospedaje", hospedaje_id,
                        {"de_familia": noche["familia_id"], "a_familia": familia_id,
                         "motivo": motivo}, ip)


def asignar_faltante(actor, codigo, ip=None):
    """Asigna por rotación la familia de una reserva con noche que quedó sin familia (D-69)."""
    exigir_rol(actor, "operador")
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la reserva BLOQUEADA, con la ruta y la fecha de su salida y sus pasajeros.
        cur.execute(
            """
            SELECT r.id, r.estado, s.ruta_id, DATE(s.fecha_hora_zarpe) AS fecha_noche,
                   (SELECT COUNT(*) FROM reserva_pasajero rp
                    WHERE rp.reserva_id = r.id) AS personas,
                   (SELECT COUNT(*) FROM hospedaje h
                    WHERE h.reserva_id = r.id AND h.estado <> 'cancelado') AS noches
            FROM reserva r
            JOIN salida s ON s.id = r.salida_id
            WHERE r.codigo = %s
            FOR UPDATE
            """,
            (codigo,),
        )
        reserva = cur.fetchone()
        if (reserva is None or reserva["estado"] not in ("confirmada", "pagada")
                or reserva["noches"]):
            raise EstadoNoPermite("Esa reserva no está esperando una familia.")
        comunidad_id = comunidad_de_pernocte(cur, reserva["ruta_id"])
        if comunidad_id is None:
            raise EstadoNoPermite("La ruta de esa reserva no tiene noche.")
        return asignar(cur, reserva["id"], comunidad_id, reserva["fecha_noche"],
                       reserva["personas"], actor.id, ip)


def marcar_cumplida(actor, hospedaje_id, ip=None):
    """La familia recibió al grupo: la noche pasa de 'asignado' a 'cumplido' (cuenta como ingreso
    en el reporte de transparencia). Solo noches que ya pasaron, de reservas que abordaron."""
    exigir_rol(actor, "operador")
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la noche BLOQUEADA, si ya pasó y el estado de su reserva.
        cur.execute(
            """
            SELECT h.estado, (h.fecha_noche < CURDATE()) AS ya_paso, r.estado AS estado_reserva
            FROM hospedaje h
            JOIN reserva r ON r.id = h.reserva_id
            WHERE h.id = %s
            FOR UPDATE
            """,
            (hospedaje_id,),
        )
        noche = cur.fetchone()
        if (noche is None or noche["estado"] != "asignado" or not noche["ya_paso"]
                or noche["estado_reserva"] != "abordada"):
            raise EstadoNoPermite("Solo se confirma una noche asignada que ya pasó, de una reserva "
                                  "que abordó.")
        cur.execute("UPDATE hospedaje SET estado = 'cumplido' WHERE id = %s", (hospedaje_id,))
        bitacora.anotar(cur, actor.id, "cambio_estado", "hospedaje", hospedaje_id,
                        {"de": "asignado", "a": "cumplido"}, ip)


def meses_con_hospedaje():
    # Devuelve los meses (AAAA-MM) que tienen noches, del más reciente al más antiguo.
    return [f["mes"] for f in bd.consultar(
        "SELECT DISTINCT mes FROM v_ingresos_familia ORDER BY mes DESC")]


def transparencia(actor, mes):
    """Reporte de transparencia comunitaria (sección 8.1): ingresos por familia y por comunidad."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve, para el mes, CADA familia de las comunidades con hospedaje (LEFT JOIN: también
    # las que no recibieron a nadie) con sus noches y montos (vista v_ingresos_familia), y los
    # totales de su comunidad con SUM(...) OVER (PARTITION BY comunidad): función de ventana.
    return bd.consultar(
        """
        SELECT c.id AS comunidad_id, c.nombre AS comunidad, f.id AS familia_id,
               f.nombre_familia, f.activa,
               COALESCE(v.noches, 0)             AS noches,
               COALESCE(v.personas_noche, 0)     AS personas_noche,
               COALESCE(v.monto, 0)              AS monto,
               COALESCE(v.noches_por_cumplir, 0) AS noches_por_cumplir,
               COALESCE(v.monto_por_cumplir, 0)  AS monto_por_cumplir,
               SUM(COALESCE(v.monto, 0)) OVER (PARTITION BY c.id) AS monto_comunidad,
               SUM(COALESCE(v.noches, 0) + COALESCE(v.noches_por_cumplir, 0))
                   OVER (PARTITION BY c.id) AS noches_comunidad
        FROM familia_anfitriona f
        JOIN comunidad c ON c.id = f.comunidad_id
        LEFT JOIN v_ingresos_familia v ON v.familia_id = f.id AND v.mes = %s
        WHERE c.tiene_hospedaje = 1 AND (f.activa = 1 OR v.familia_id IS NOT NULL)
        ORDER BY c.nombre, f.nombre_familia
        """,
        (mes,),
    )
