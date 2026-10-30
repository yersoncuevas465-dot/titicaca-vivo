"""Ayudante común de los catálogos: guardar un registro (INSERT o UPDATE) y anotarlo.

Cada catálogo escribe su propio SQL (con sus columnas a la vista, para poder explicarlo);
aquí solo se repite lo que es igual para todos: elegir INSERT o UPDATE, convertir un
UNIQUE repetido (error 1062) en un mensaje junto al campo y dejar el registro en la bitácora.
"""

import pymysql

from app.modelos import ERROR_DUPLICADO, ErrorValidacion, bitacora
from app.modelos.validacion import indice_duplicado


def escribir(cur, actor, ip, tabla, registro_id, insertar, actualizar, duplicados, resumen):
    """Devuelve el id del registro guardado.

    insertar / actualizar: (sql, parámetros). Si registro_id es None se usa `insertar`.
    duplicados: {nombre_del_unique: (campo, mensaje)}.
    resumen: lo que se anota en la bitácora (nunca contraseñas).
    """
    sql, parametros = actualizar if registro_id else insertar
    try:
        cur.execute(sql, parametros)
    except pymysql.err.IntegrityError as error:
        if error.args[0] == ERROR_DUPLICADO:
            por_defecto = ("general", "Ese dato ya existe.")
            campo, mensaje = duplicados.get(indice_duplicado(error), por_defecto)
            raise ErrorValidacion({campo: mensaje}) from error
        raise
    accion = "edicion" if registro_id else "creacion"
    registro_id = registro_id or cur.lastrowid
    bitacora.anotar(cur, actor.id, accion, tabla, registro_id, resumen, ip)
    return registro_id
