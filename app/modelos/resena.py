"""Reseñas (RN-13): solo de reservas abordadas, cuando el viaje ya terminó, una por reserva.
Se publican después de la moderación del operador."""

import pymysql

from app import bd
from app.modelos import (
    ERROR_DUPLICADO,
    ErrorValidacion,
    EstadoNoPermite,
    bitacora,
    exigir_rol,
)

DECISIONES = ("publicada", "rechazada")
LARGO_COMENTARIO = 1000


def para_la_reserva(codigo):
    # Devuelve la reserva con su estado, si su viaje ya terminó (hora de retorno pasada) y su
    # reseña, si ya tiene una (LEFT JOIN: la mayoría todavía no tiene).
    return bd.consultar_uno(
        """
        SELECT r.id, r.codigo, r.estado, (s.fecha_hora_retorno <= NOW()) AS viaje_terminado,
               re.id AS resena_id, re.puntuacion, re.comentario, re.estado AS estado_resena
        FROM reserva r
        JOIN salida s       ON s.id = r.salida_id
        LEFT JOIN resena re ON re.reserva_id = r.id
        WHERE r.codigo = %s
        """,
        (codigo,),
    )


def por_que_no(fila):
    """None si se puede escribir la reseña; si no, el motivo."""
    if fila["resena_id"]:
        return "Ya dejaste tu opinión sobre este viaje. ¡Gracias!"
    if fila["estado"] != "abordada":
        return "Solo se opina de un viaje que se hizo (reserva abordada)."
    if not fila["viaje_terminado"]:
        return "Podrás opinar cuando termine tu viaje."
    return None


def crear(codigo, puntuacion, comentario, idioma="es", ip=None):
    errores = {}
    try:
        puntuacion = int(puntuacion)
    except (TypeError, ValueError):
        puntuacion = 0
    if not 1 <= puntuacion <= 5:
        errores["puntuacion"] = "Elige de 1 a 5 estrellas."
    comentario = (comentario or "").strip() or None
    if comentario and len(comentario) > LARGO_COMENTARIO:
        errores["comentario"] = f"Máximo {LARGO_COMENTARIO} caracteres."
    if errores:
        raise ErrorValidacion(errores)
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la reserva BLOQUEADA con su estado, si el viaje terminó y si ya tiene reseña.
        cur.execute(
            """
            SELECT r.id, r.estado, (s.fecha_hora_retorno <= NOW()) AS viaje_terminado,
                   (SELECT id FROM resena WHERE reserva_id = r.id) AS resena_id
            FROM reserva r
            JOIN salida s ON s.id = r.salida_id
            WHERE r.codigo = %s
            FOR UPDATE
            """,
            (codigo,),
        )
        fila = cur.fetchone()
        if fila is None:
            raise EstadoNoPermite("Esa reserva no existe.")
        motivo = por_que_no(fila)
        if motivo:
            raise EstadoNoPermite(motivo)
        try:
            cur.execute(
                """
                INSERT INTO resena (reserva_id, puntuacion, comentario, idioma, estado)
                VALUES (%s, %s, %s, %s, 'pendiente')
                """,
                (fila["id"], puntuacion, comentario, "en" if idioma == "en" else "es"),
            )
        except pymysql.err.IntegrityError as error:
            if error.args[0] == ERROR_DUPLICADO:          # UNIQUE: una reseña por reserva
                raise EstadoNoPermite(
                    "Ya dejaste tu opinión sobre este viaje. ¡Gracias!") from error
            raise
        bitacora.anotar(cur, None, "creacion", "resena", cur.lastrowid,
                        {"reserva": codigo, "puntuacion": puntuacion}, ip)


# --- Panel: moderación --------------------------------------------------------------------------

def listar_panel(actor):
    exigir_rol(actor, "admin", "operador")
    # Devuelve las reseñas pendientes primero y luego las últimas moderadas, con la ruta, la
    # fecha del viaje y la nacionalidad del titular (FIELD ordena los estados a mano).
    return bd.consultar(
        """
        SELECT re.id, re.puntuacion, re.comentario, re.idioma, re.estado, re.creada_en,
               r.codigo, ru.nombre AS ruta_nombre, s.fecha_hora_zarpe, t.nacionalidad,
               u.nombre_usuario AS moderada_por
        FROM resena re
        JOIN reserva r      ON r.id = re.reserva_id
        JOIN salida s       ON s.id = r.salida_id
        JOIN ruta ru        ON ru.id = s.ruta_id
        JOIN turista t      ON t.id = r.turista_id
        LEFT JOIN usuario u ON u.id = re.moderada_por
        ORDER BY FIELD(re.estado, 'pendiente', 'publicada', 'rechazada'), re.creada_en DESC
        LIMIT 50
        """
    )


def moderar(actor, resena_id, decision, ip=None):
    exigir_rol(actor, "operador")
    if decision not in DECISIONES:
        raise ErrorValidacion({"decision": "Elige publicar o rechazar."})
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la reseña BLOQUEADA (dos operadores no la moderan a la vez).
        cur.execute("SELECT estado FROM resena WHERE id = %s FOR UPDATE", (resena_id,))
        fila = cur.fetchone()
        if fila is None or fila["estado"] != "pendiente":
            raise EstadoNoPermite("Esa reseña ya fue moderada.")
        cur.execute("UPDATE resena SET estado = %s, moderada_por = %s WHERE id = %s",
                    (decision, actor.id, resena_id))
        bitacora.anotar(cur, actor.id, "cambio_estado", "resena", resena_id,
                        {"de": "pendiente", "a": decision}, ip)


# --- Público -----------------------------------------------------------------------------------

def publicadas_de_ruta(ruta_id, limite=5):
    # Devuelve las últimas reseñas PUBLICADAS de la ruta (de todas sus salidas), con el país del
    # titular y el mes del viaje (sin nombres), más el promedio y el total de TODAS las publicadas
    # con AVG() OVER () y COUNT(*) OVER (): se calculan antes del LIMIT.
    return bd.consultar(
        """
        SELECT re.puntuacion, re.comentario, re.idioma, t.nacionalidad, s.fecha_hora_zarpe,
               AVG(re.puntuacion) OVER () AS promedio, COUNT(*) OVER () AS total
        FROM resena re
        JOIN reserva r ON r.id = re.reserva_id
        JOIN salida s  ON s.id = r.salida_id
        JOIN turista t ON t.id = r.turista_id
        WHERE s.ruta_id = %s AND re.estado = 'publicada'
        ORDER BY re.creada_en DESC
        LIMIT %s
        """,
        (ruta_id, limite),
    )
