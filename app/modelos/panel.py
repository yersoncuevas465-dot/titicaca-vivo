"""Resumen del día para la página /panel, distinto según el rol."""

from app import bd
from app.modelos import ROLES_PERSONAL, alerta, exigir_rol


def resumen(actor):
    exigir_rol(actor, *ROLES_PERSONAL)
    datos = {"alertas": alertas_vigentes()}
    if actor.rol in ("admin", "operador"):
        datos["salidas"] = salidas_de_hoy()
        datos["contadores"] = contadores_operacion()
    elif actor.rol == "capitan":
        datos["salidas"] = salidas_del_capitan(actor.id)
    else:
        datos["salidas"] = salidas_del_guia(actor.id)
    return datos


def salidas_de_hoy():
    # Devuelve las salidas de hoy con ruta, lancha, ocupados, libres y estado público
    # (usa la vista v_disponibilidad_salida: reglas RN-01 y RN-08).
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.embarcacion_nombre,
               v.cupo, v.ocupados, v.libres, v.estado, v.estado_publico
        FROM v_disponibilidad_salida v
        WHERE v.fecha_hora_zarpe >= CURDATE()
          AND v.fecha_hora_zarpe <  CURDATE() + INTERVAL 1 DAY
        ORDER BY v.fecha_hora_zarpe
        """
    )


def contadores_operacion():
    # Devuelve 3 números para el operador: pagos por verificar, reservas que esperan pago
    # y alertas vigentes (cada uno es una subconsulta COUNT).
    return bd.consultar_uno(
        """
        SELECT
          (SELECT COUNT(*) FROM pago WHERE estado = 'reportado') AS pagos_por_verificar,
          (SELECT COUNT(*) FROM reserva
            WHERE estado = 'pendiente_pago' AND vence_en > NOW())  AS reservas_esperando_pago,
          (SELECT COUNT(*) FROM alerta_lago
            WHERE vigente_desde <= NOW() AND vigente_hasta > NOW()) AS alertas_vigentes
        """
    )


def salidas_del_capitan(usuario_id):
    # Devuelve las salidas de este capitán de hoy y los 2 días siguientes, con sus ocupados.
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.embarcacion_nombre,
               v.matricula, v.cupo, v.ocupados, v.libres, v.estado, v.estado_publico
        FROM v_disponibilidad_salida v
        JOIN salida s ON s.id = v.salida_id
        WHERE s.capitan_id = %s
          AND v.fecha_hora_zarpe >= CURDATE()
          AND v.fecha_hora_zarpe <  CURDATE() + INTERVAL 3 DAY
        ORDER BY v.fecha_hora_zarpe
        """,
        (usuario_id,),
    )


def salidas_del_guia(usuario_id):
    # Devuelve las salidas asignadas a este guía de hoy y los 2 días siguientes, con sus ocupados.
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.embarcacion_nombre,
               v.matricula, v.cupo, v.ocupados, v.libres, v.estado, v.estado_publico
        FROM v_disponibilidad_salida v
        JOIN salida s ON s.id = v.salida_id
        WHERE s.guia_id = %s
          AND v.fecha_hora_zarpe >= CURDATE()
          AND v.fecha_hora_zarpe <  CURDATE() + INTERVAL 3 DAY
        ORDER BY v.fecha_hora_zarpe
        """,
        (usuario_id,),
    )


def alertas_vigentes():
    return alerta.vigentes()
