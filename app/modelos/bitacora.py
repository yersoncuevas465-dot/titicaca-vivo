"""Bitácora de auditoría (RN-14): anotar cambios y consultarlos (solo el admin).

D-115: el admin la filtra por acción y por periodo (hoy, semana, mes, año) y la descarga en
CSV para Excel: toda o solo los movimientos de las cuentas (entradas, salidas, intentos
fallidos y cambios de contraseña). La descarga también queda anotada.
"""

import json

from app import bd
from app.modelos import exigir_rol

POR_PAGINA = 25
MAXIMO_EXPORTAR = 50_000
# Movimientos de las cuentas: lo que se descarga con «solo sesiones»
ACCIONES_DE_SESION = ("inicio_sesion", "cierre_sesion", "intento_fallido",
                      "recuperacion_solicitada", "contrasena_restablecida", "contrasena_cambiada")


def anotar(cur, usuario_id, accion, tabla, registro_id, detalle, ip):
    """RN-14: escribe un registro de auditoría con el cursor de la transacción abierta.

    Así el registro queda o no queda junto con el cambio que describe.
    """
    cur.execute(
        """
        INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (usuario_id, accion, tabla, registro_id, json.dumps(detalle, default=str), ip),
    )


def acciones_registradas(actor):
    exigir_rol(actor, "admin")
    # Devuelve la lista de acciones distintas que hay en la bitácora (para el filtro).
    filas = bd.consultar("SELECT DISTINCT accion FROM bitacora ORDER BY accion")
    return [f["accion"] for f in filas]


def listar(actor, pagina=1, accion=None, desde=None):
    """Devuelve (filas, total) de una página de la bitácora. Solo el admin la ve.

    `desde` (datetime o None): solo lo anotado desde ese momento.
    """
    exigir_rol(actor, "admin")
    pagina = max(1, int(pagina))
    desplazamiento = (pagina - 1) * POR_PAGINA

    # Devuelve cuántos registros hay (con los filtros de acción y de periodo, si se eligieron).
    total = bd.consultar_uno(
        """
        SELECT COUNT(*) AS total
        FROM bitacora
        WHERE (%s IS NULL OR accion = %s) AND (%s IS NULL OR creado_en >= %s)
        """,
        (accion, accion, desde, desde),
    )["total"]

    # Devuelve una página de la bitácora, lo más reciente primero, con el usuario si lo hay.
    filas = bd.consultar(
        """
        SELECT b.id, b.creado_en, b.accion, b.tabla_afectada, b.registro_id,
               b.detalle, b.ip, u.nombre_usuario
        FROM bitacora b
        LEFT JOIN usuario u ON u.id = b.usuario_id
        WHERE (%s IS NULL OR b.accion = %s) AND (%s IS NULL OR b.creado_en >= %s)
        ORDER BY b.creado_en DESC, b.id DESC
        LIMIT %s OFFSET %s
        """,
        (accion, accion, desde, desde, POR_PAGINA, desplazamiento),
    )
    for fila in filas:
        fila["detalle"] = json.loads(fila["detalle"]) if fila["detalle"] else {}
    return filas, total


def exportar(actor, desde, solo_sesiones, descripcion, ip):
    """Las filas de la bitácora para el CSV (de la más antigua a la más nueva) y su anotación."""
    exigir_rol(actor, "admin")
    marcas = ", ".join(["%s"] * len(ACCIONES_DE_SESION))
    with bd.transaccion() as cur:
        # Devuelve la bitácora desde una fecha (o toda), opcionalmente solo los movimientos de
        # las cuentas, con el nombre de usuario (LEFT JOIN: un turista no tiene usuario).
        cur.execute(
            f"""
            SELECT b.creado_en, u.nombre_usuario, b.accion, b.tabla_afectada, b.registro_id,
                   b.detalle, b.ip
            FROM bitacora b
            LEFT JOIN usuario u ON u.id = b.usuario_id
            WHERE (%s IS NULL OR b.creado_en >= %s)
              AND (%s = 0 OR b.accion IN ({marcas}))
            ORDER BY b.creado_en, b.id
            LIMIT %s
            """,  # noqa: S608 (solo marcas %s armadas aquí; los valores van como parámetros)
            (desde, desde, 1 if solo_sesiones else 0, *ACCIONES_DE_SESION, MAXIMO_EXPORTAR),
        )
        filas = list(cur.fetchall())
        anotar(cur, actor.id, "bitacora_exportada", "bitacora", None,
               {"periodo": descripcion, "solo_sesiones": bool(solo_sesiones), "filas": len(filas)},
               ip)
    for fila in filas:
        fila["detalle"] = json.loads(fila["detalle"]) if fila["detalle"] else {}
    return filas
