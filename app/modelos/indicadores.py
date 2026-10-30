"""Panel de indicadores (sección 8.8): consultas de agregación con GROUP BY, HAVING,
subconsultas y funciones de ventana. Los gráficos son barras SVG propias (sin CDN)."""

from app import bd
from app.modelos import exigir_rol

PERIODOS = {"30": 30, "90": 90, "365": 365}      # días hacia atrás (lista blanca)
OCUPACION_BAJA = 50                               # % (para la lista de rutas con poca ocupación)


def ocupacion_por_ruta(actor, dias):
    exigir_rol(actor, "admin", "operador")
    # Devuelve, por ruta, las salidas no canceladas desde hace N días (y las que vienen), los
    # pasajeros, el cupo y el % de ocupación, con su puesto: RANK() OVER ordena las rutas por
    # ocupación SIN agruparlas otra vez (función de ventana sobre el resultado del GROUP BY).
    return bd.consultar(
        """
        SELECT v.ruta_id, v.ruta_nombre, COUNT(*) AS salidas,
               SUM(v.ocupados) AS ocupados, SUM(v.cupo) AS cupo,
               ROUND(100 * SUM(v.ocupados) / SUM(v.cupo), 1) AS ocupacion,
               RANK() OVER (ORDER BY SUM(v.ocupados) / SUM(v.cupo) DESC) AS puesto
        FROM v_disponibilidad_salida v
        WHERE v.estado <> 'cancelada'
          AND v.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY
        GROUP BY v.ruta_id, v.ruta_nombre
        ORDER BY puesto, v.ruta_nombre
        """,
        (dias,),
    )


def rutas_con_poca_ocupacion(actor, dias, umbral=OCUPACION_BAJA):
    exigir_rol(actor, "admin", "operador")
    # Devuelve solo las rutas cuya ocupación del periodo es menor al umbral. HAVING filtra
    # DESPUÉS de agrupar (WHERE no puede usar SUM: filtra filas antes de agrupar).
    return bd.consultar(
        """
        SELECT v.ruta_nombre, COUNT(*) AS salidas,
               ROUND(100 * SUM(v.ocupados) / SUM(v.cupo), 1) AS ocupacion
        FROM v_disponibilidad_salida v
        WHERE v.estado <> 'cancelada'
          AND v.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY
        GROUP BY v.ruta_id, v.ruta_nombre
        HAVING 100 * SUM(v.ocupados) / SUM(v.cupo) < %s
        ORDER BY ocupacion
        """,
        (dias, umbral),
    )


def ingresos_por_metodo(actor, dias):
    exigir_rol(actor, "admin", "operador")
    # Devuelve, por método de pago, cuántos pagos verificados hubo en el periodo y su suma, y qué
    # parte del total es: SUM(SUM(monto)) OVER () es el total de todos los métodos.
    return bd.consultar(
        """
        SELECT p.metodo, COUNT(*) AS pagos, SUM(p.monto) AS monto,
               ROUND(100 * SUM(p.monto) / SUM(SUM(p.monto)) OVER (), 1) AS porcentaje
        FROM pago p
        WHERE p.estado = 'verificado'
          AND p.verificado_en >= CURDATE() - INTERVAL %s DAY
        GROUP BY p.metodo
        ORDER BY monto DESC
        """,
        (dias,),
    )


def nacionalidades(actor, dias, limite=10):
    exigir_rol(actor, "admin", "operador")
    # Devuelve los países de los pasajeros que viajaron o tienen lugar (reservas confirmadas,
    # pagadas o abordadas) en salidas del periodo, con cuántos son y su porcentaje del total.
    return bd.consultar(
        """
        SELECT rp.nacionalidad, COUNT(*) AS pasajeros,
               ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS porcentaje
        FROM reserva_pasajero rp
        JOIN reserva r ON r.id = rp.reserva_id
        JOIN salida s  ON s.id = r.salida_id
        WHERE r.estado IN ('confirmada','pagada','abordada')
          AND s.fecha_hora_zarpe >= CURDATE() - INTERVAL %s DAY
        GROUP BY rp.nacionalidad
        ORDER BY pasajeros DESC, rp.nacionalidad
        LIMIT %s
        """,
        (dias, limite),
    )


def noches_por_familia(actor, dias):
    exigir_rol(actor, "admin", "operador")
    # Devuelve cada familia activa con sus noches (asignadas o cumplidas) desde hace N días: la
    # subconsulta agrupa las noches por familia y el LEFT JOIN deja a las que no tuvieron
    # ninguna. AVG(...) OVER (PARTITION BY comunidad) da el promedio de SU comunidad, para ver si
    # la rotación (RN-10) reparte parejo.
    return bd.consultar(
        """
        SELECT c.nombre AS comunidad, f.nombre_familia, COALESCE(n.noches, 0) AS noches,
               ROUND(AVG(COALESCE(n.noches, 0)) OVER (PARTITION BY c.id), 1) AS promedio_comunidad
        FROM familia_anfitriona f
        JOIN comunidad c ON c.id = f.comunidad_id
        LEFT JOIN (SELECT h.familia_id, COUNT(*) AS noches
                   FROM hospedaje h
                   WHERE h.estado IN ('asignado','cumplido')
                     AND h.fecha_noche >= CURDATE() - INTERVAL %s DAY
                   GROUP BY h.familia_id) n ON n.familia_id = f.id
        WHERE f.activa = 1
        ORDER BY c.nombre, noches DESC, f.nombre_familia
        """,
        (dias,),
    )
