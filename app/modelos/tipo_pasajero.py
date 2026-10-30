"""Catálogo de tipos de pasajero. Los 5 códigos los fija el enunciado (CHECK en la base):
aquí solo se edita su nombre y sus edades, no se crean tipos nuevos."""

from app import bd
from app.modelos import ROLES_CATALOGO, ErrorValidacion, catalogo, exigir_rol
from app.modelos import validacion as v


def listar(actor):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve los tipos de pasajero con cuántas tarifas usa cada uno (LEFT JOIN + GROUP BY:
    # un tipo sin tarifas también aparece, con 0).
    return bd.consultar(
        """
        SELECT tp.id, tp.codigo, tp.nombre, tp.edad_minima, tp.edad_maxima,
               COUNT(t.id) AS tarifas
        FROM tipo_pasajero tp
        LEFT JOIN tarifa t ON t.tipo_pasajero_id = tp.id
        GROUP BY tp.id, tp.codigo, tp.nombre, tp.edad_minima, tp.edad_maxima
        ORDER BY tp.id
        """
    )


def buscar(actor, tipo_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve un tipo de pasajero para editarlo.
    return bd.consultar_uno(
        "SELECT id, codigo, nombre, edad_minima, edad_maxima FROM tipo_pasajero WHERE id = %s",
        (tipo_id,),
    )


def guardar(actor, tipo_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    if not tipo_id:
        raise ErrorValidacion(
            {"general": "Los tipos de pasajero son fijos: solo se pueden editar."})
    e = {}
    nombre = v.texto(datos, "nombre", e, 3, 40, nombre="el nombre")
    minima = v.entero(datos, "edad_minima", e, 0, 120)
    maxima = v.entero(datos, "edad_maxima", e, 0, 120, obligatorio=False)
    if minima is not None and maxima is not None and maxima < minima:
        e["edad_maxima"] = "La edad máxima no puede ser menor que la mínima."
    if e:
        raise ErrorValidacion(e)
    with bd.transaccion(lectura_actual=True) as cur:
        return catalogo.escribir(
            cur, actor, ip, "tipo_pasajero", tipo_id,
            insertar=(None, None),
            actualizar=("""
                UPDATE tipo_pasajero SET nombre = %s, edad_minima = %s, edad_maxima = %s
                WHERE id = %s
                """, (nombre, minima, maxima, tipo_id)),
            duplicados={},
            resumen={"nombre": nombre, "edad_minima": minima, "edad_maxima": maxima},
        )
