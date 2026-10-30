"""Catálogo de temporadas: recargo por rango de fechas (RN-04). S-14: no se solapan."""

from app import bd
from app.modelos import ROLES_CATALOGO, ErrorValidacion, catalogo, exigir_rol
from app.modelos import validacion as v


def listar(actor):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve las temporadas por fecha de inicio, y si hoy está dentro de alguna.
    return bd.consultar(
        """
        SELECT id, nombre, fecha_inicio, fecha_fin, recargo_porcentaje,
               (CURDATE() BETWEEN fecha_inicio AND fecha_fin) AS en_curso
        FROM temporada
        ORDER BY fecha_inicio
        """
    )


def buscar(actor, temporada_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve una temporada para editarla.
    return bd.consultar_uno(
        """
        SELECT id, nombre, fecha_inicio, fecha_fin, recargo_porcentaje
        FROM temporada
        WHERE id = %s
        """,
        (temporada_id,),
    )


def guardar(actor, temporada_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    nombre = v.texto(datos, "nombre", e, 3, 60, nombre="el nombre")
    inicio = v.fecha(datos, "fecha_inicio", e)
    fin = v.fecha(datos, "fecha_fin", e)
    recargo = v.decimal(datos, "recargo_porcentaje", e, 0, 100)
    if inicio and fin and fin < inicio:
        e["fecha_fin"] = "La fecha de fin no puede ser anterior a la de inicio."
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve una temporada (que no sea esta) cuyo rango se cruza con el nuevo (S-14).
        # Dos rangos se cruzan si cada uno empieza antes de que termine el otro.
        cur.execute(
            """
            SELECT nombre, fecha_inicio, fecha_fin
            FROM temporada
            WHERE id <> %s AND fecha_inicio <= %s AND %s <= fecha_fin
            LIMIT 1
            """,
            (temporada_id or 0, fin, inicio),
        )
        cruce = cur.fetchone()
        if cruce:
            raise ErrorValidacion({"fecha_inicio": (
                f"Se cruza con «{cruce['nombre']}» ({cruce['fecha_inicio']:%d/%m/%Y} al "
                f"{cruce['fecha_fin']:%d/%m/%Y}). Las temporadas no se solapan.")})
        valores = (nombre, inicio, fin, recargo)
        return catalogo.escribir(
            cur, actor, ip, "temporada", temporada_id,
            insertar=("""
                INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, recargo_porcentaje)
                VALUES (%s, %s, %s, %s)
                """, valores),
            actualizar=("""
                UPDATE temporada
                SET nombre = %s, fecha_inicio = %s, fecha_fin = %s, recargo_porcentaje = %s
                WHERE id = %s
                """, (*valores, temporada_id)),
            duplicados={},
            resumen={"nombre": nombre, "desde": inicio, "hasta": fin, "recargo": recargo},
        )
