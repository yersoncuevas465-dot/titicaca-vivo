"""Tarifas y precio por pasajero (RN-04). En el panel: catálogo de tarifas (F5)."""

from decimal import ROUND_HALF_UP, Decimal

from app import bd
from app.modelos import ROLES_CATALOGO, ErrorValidacion, catalogo, exigir_rol
from app.modelos import validacion as v

CENTIMO = Decimal("0.01")


def calcular_precio(precio_base, recargo_porcentaje):
    """RN-04: precio = tarifa × (1 + recargo / 100), redondeado al céntimo (0.005 sube)."""
    recargo = Decimal(recargo_porcentaje or 0)
    return (Decimal(precio_base) * (1 + recargo / 100)).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def precios_para_salida(salida_id):
    """Devuelve la lista de tipos de pasajero con su precio para esa salida (o [] si no hay)."""
    # Devuelve, para la fecha de la salida, cada tipo de pasajero con:
    #  - la tarifa vigente MÁS RECIENTE (subconsulta con MAX de vigente_desde), y
    #  - el recargo y el nombre de la temporada que contiene esa fecha (si hay una).
    filas = bd.consultar(
        """
        SELECT tp.id AS tipo_pasajero_id, tp.codigo, tp.nombre, tp.edad_minima, tp.edad_maxima,
               t.precio_base,
               COALESCE((SELECT MAX(te.recargo_porcentaje) FROM temporada te
                         WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin),
                        0) AS recargo_porcentaje,
               (SELECT te.nombre FROM temporada te
                WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin
                ORDER BY te.recargo_porcentaje DESC
                LIMIT 1) AS temporada
        FROM salida s
        JOIN tarifa t         ON t.ruta_id = s.ruta_id
        JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id
        WHERE s.id = %s
          AND t.vigente_desde = (SELECT MAX(t2.vigente_desde) FROM tarifa t2
                                 WHERE t2.ruta_id = t.ruta_id
                                   AND t2.tipo_pasajero_id = t.tipo_pasajero_id
                                   AND t2.vigente_desde <= DATE(s.fecha_hora_zarpe)
                                   AND (t2.vigente_hasta IS NULL
                                        OR t2.vigente_hasta >= DATE(s.fecha_hora_zarpe)))
        ORDER BY tp.id
        """,
        (salida_id,),
    )
    for fila in filas:
        fila["precio"] = calcular_precio(fila["precio_base"], fila["recargo_porcentaje"])
    return filas


# --- Catálogo de tarifas (panel, F5) ---------------------------------------------------------

def listar_panel(actor, ruta_id=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve las tarifas con su ruta y su tipo de pasajero, y si están vigentes hoy
    # (con un filtro opcional por ruta). Las más nuevas primero dentro de cada ruta y tipo.
    return bd.consultar(
        """
        SELECT t.id, t.precio_base, t.vigente_desde, t.vigente_hasta,
               r.nombre AS ruta, tp.nombre AS tipo,
               (t.vigente_desde <= CURDATE()
                AND (t.vigente_hasta IS NULL OR t.vigente_hasta >= CURDATE())) AS vigente_hoy
        FROM tarifa t
        JOIN ruta r           ON r.id = t.ruta_id
        JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id
        WHERE (%s IS NULL OR t.ruta_id = %s)
        ORDER BY r.nombre, tp.id, t.vigente_desde DESC
        """,
        (ruta_id, ruta_id),
    )


def buscar_panel(actor, tarifa_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve una tarifa para editarla.
    return bd.consultar_uno(
        """
        SELECT id, ruta_id, tipo_pasajero_id, precio_base, vigente_desde, vigente_hasta
        FROM tarifa
        WHERE id = %s
        """,
        (tarifa_id,),
    )


def opciones():
    # Devuelve todas las rutas y todos los tipos de pasajero (para elegirlos en el formulario).
    return {
        "rutas": bd.consultar("SELECT id, nombre FROM ruta ORDER BY nombre"),
        "tipos": bd.consultar("SELECT id, nombre FROM tipo_pasajero ORDER BY id"),
    }


def guardar(actor, tarifa_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    ruta_id = v.entero(datos, "ruta_id", e, 1, 4294967295)
    tipo_id = v.entero(datos, "tipo_pasajero_id", e, 1, 4294967295)
    precio = v.decimal(datos, "precio_base", e, "0.01", "999999.99")
    desde = v.fecha(datos, "vigente_desde", e)
    hasta = v.fecha(datos, "vigente_hasta", e, obligatorio=False)
    if desde and hasta and hasta < desde:
        e["vigente_hasta"] = "El fin de la vigencia no puede ser anterior al inicio."
    if e:
        raise ErrorValidacion(e)
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve 1 si existen la ruta y el tipo de pasajero elegidos.
        cur.execute(
            """
            SELECT (SELECT COUNT(*) FROM ruta WHERE id = %s) AS ruta,
                   (SELECT COUNT(*) FROM tipo_pasajero WHERE id = %s) AS tipo
            """,
            (ruta_id, tipo_id),
        )
        existen = cur.fetchone()
        if not existen["ruta"]:
            e["ruta_id"] = "Elige una ruta."
        if not existen["tipo"]:
            e["tipo_pasajero_id"] = "Elige un tipo de pasajero."
        if e:
            raise ErrorValidacion(e)
        valores = (ruta_id, tipo_id, precio, desde, hasta)
        return catalogo.escribir(
            cur, actor, ip, "tarifa", tarifa_id,
            insertar=("""
                INSERT INTO tarifa (ruta_id, tipo_pasajero_id, precio_base, vigente_desde,
                                    vigente_hasta)
                VALUES (%s, %s, %s, %s, %s)
                """, valores),
            actualizar=("""
                UPDATE tarifa
                SET ruta_id = %s, tipo_pasajero_id = %s, precio_base = %s, vigente_desde = %s,
                    vigente_hasta = %s
                WHERE id = %s
                """, (*valores, tarifa_id)),
            duplicados={"uk_tarifa_vigencia": ("vigente_desde", "Ya hay una tarifa de esa ruta y "
                                                                "ese tipo desde esa fecha.")},
            resumen={"ruta_id": ruta_id, "tipo_pasajero_id": tipo_id, "precio": precio,
                     "desde": desde, "hasta": hasta},
        )
