"""Catálogo de embarcaciones (lanchas). RN-07: solo una lancha operativa puede salir."""

import re

from app import bd
from app.modelos import ROLES_CATALOGO, ErrorValidacion, catalogo, exigir_rol
from app.modelos import validacion as v

TIPOS = ("lancha", "deslizador", "balsa_totora")
ESTADOS = ("operativa", "mantenimiento", "baja")
PATRON_MATRICULA = re.compile(r"^[A-Z0-9-]{3,20}$")


def listar_panel(actor):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve todas las lanchas con cuántas salidas por venir tiene cada una (programadas,
    # embarcando o suspendidas): esas se verían afectadas si la lancha deja de estar operativa.
    return bd.consultar(
        """
        SELECT e.id, e.nombre, e.matricula, e.capacidad_maxima, e.tipo, e.estado,
               e.ultimo_mantenimiento,
               (SELECT COUNT(*) FROM salida s
                WHERE s.embarcacion_id = e.id
                  AND s.estado IN ('programada','embarcando','suspendida')
                  AND s.fecha_hora_zarpe > NOW()) AS salidas_por_venir
        FROM embarcacion e
        ORDER BY e.estado, e.nombre
        """
    )


def buscar_panel(actor, embarcacion_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve una lancha para editarla.
    return bd.consultar_uno(
        """
        SELECT id, nombre, matricula, capacidad_maxima, tipo, estado, ultimo_mantenimiento
        FROM embarcacion
        WHERE id = %s
        """,
        (embarcacion_id,),
    )


def guardar(actor, embarcacion_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    nombre = v.texto(datos, "nombre", e, 2, 60, nombre="el nombre")
    matricula = (datos.get("matricula") or "").strip().upper()
    if not PATRON_MATRICULA.match(matricula):
        e["matricula"] = "De 3 a 20 letras mayúsculas, números o guiones (por ejemplo PUN-LT-0101)."
    capacidad = v.entero(datos, "capacidad_maxima", e, 1, 40)
    tipo = v.opcion(datos, "tipo", e, TIPOS)
    estado = v.opcion(datos, "estado", e, ESTADOS)
    mantenimiento = v.fecha(datos, "ultimo_mantenimiento", e, obligatorio=False)
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la fecha de hoy según la base (hora de Lima).
        cur.execute("SELECT CURDATE() AS hoy")
        if mantenimiento and mantenimiento > cur.fetchone()["hoy"]:
            e["ultimo_mantenimiento"] = "El último mantenimiento no puede ser una fecha futura."
        if embarcacion_id:
            # Devuelve cuántas salidas por venir tiene la lancha y el cupo más alto de ellas.
            cur.execute(
                """
                SELECT COUNT(*) AS salidas, COALESCE(MAX(cupo), 0) AS mayor_cupo
                FROM salida
                WHERE embarcacion_id = %s
                  AND estado IN ('programada','embarcando','suspendida')
                  AND fecha_hora_zarpe > NOW()
                """,
                (embarcacion_id,),
            )
            uso = cur.fetchone()
            if uso["salidas"] and estado != "operativa":
                e["estado"] = (f"Tiene {uso['salidas']} salidas por venir: pásalas a otra lancha "
                               "antes de sacarla de operación.")
            if capacidad and capacidad < uso["mayor_cupo"]:
                e["capacidad_maxima"] = (f"Una salida por venir tiene cupo {uso['mayor_cupo']}: "
                                         "la capacidad no puede ser menor.")
        if e:
            raise ErrorValidacion(e)
        valores = (nombre, matricula, capacidad, tipo, estado, mantenimiento)
        return catalogo.escribir(
            cur, actor, ip, "embarcacion", embarcacion_id,
            insertar=("""
                INSERT INTO embarcacion (nombre, matricula, capacidad_maxima, tipo, estado,
                                         ultimo_mantenimiento)
                VALUES (%s, %s, %s, %s, %s, %s)
                """, valores),
            actualizar=("""
                UPDATE embarcacion
                SET nombre = %s, matricula = %s, capacidad_maxima = %s, tipo = %s, estado = %s,
                    ultimo_mantenimiento = %s
                WHERE id = %s
                """, (*valores, embarcacion_id)),
            duplicados={"uk_embarcacion_matricula": ("matricula", "Ya hay una lancha con esa "
                                                                   "matrícula.")},
            resumen={"matricula": matricula, "estado": estado, "capacidad": capacidad},
        )
