"""Alertas del lago: lo que ve el público (F3) y, en el panel (F6), registrarlas y suspender
en un solo paso las salidas que afectan (RN-11). Se registran a mano: sin scraping de SENAMHI."""

from datetime import datetime

from app import bd
from app.modelos import ErrorValidacion, EstadoNoPermite, bitacora, catalogo, exigir_rol
from app.modelos import validacion as v


def vigentes():
    # Devuelve las alertas vigentes ahora, de la más grave a la más leve
    # (un ENUM se ordena por su posición: verde=1 ... rojo=4, por eso DESC).
    return bd.consultar(
        """
        SELECT a.id, a.tipo, a.nivel, a.titulo, a.descripcion, a.fuente, a.vigente_hasta,
               COALESCE(c.nombre, 'Todo el lago') AS lugar, c.slug
        FROM alerta_lago a
        LEFT JOIN comunidad c ON c.id = a.comunidad_id
        WHERE a.vigente_desde <= NOW() AND a.vigente_hasta > NOW()
        ORDER BY a.nivel DESC, a.vigente_hasta
        """
    )


def para_pagina_publica(dias_atras=30):
    # Devuelve las alertas vigentes, las próximas y las que terminaron en los últimos días,
    # cada una con su grupo (CASE) para mostrarlas en tres listas.
    return bd.consultar(
        """
        SELECT a.id, a.tipo, a.nivel, a.titulo, a.descripcion, a.fuente,
               a.vigente_desde, a.vigente_hasta,
               COALESCE(c.nombre, 'Todo el lago') AS lugar, c.slug,
               CASE WHEN a.vigente_desde <= NOW() AND a.vigente_hasta > NOW() THEN 'vigente'
                    WHEN a.vigente_desde > NOW() THEN 'proxima'
                    ELSE 'pasada' END AS grupo
        FROM alerta_lago a
        LEFT JOIN comunidad c ON c.id = a.comunidad_id
        WHERE a.vigente_hasta >= NOW() - INTERVAL %s DAY
        ORDER BY FIELD(grupo, 'vigente', 'proxima', 'pasada'), a.nivel DESC, a.vigente_desde DESC
        """,
        (dias_atras,),
    )


# =============================================================================================
# Panel (F6): registrar alertas y suspender las salidas afectadas en un solo paso (RN-11)
# =============================================================================================

TIPOS = ("oleaje", "tormenta", "helada", "neblina", "granizo", "otro")
NIVELES = ("verde", "amarillo", "naranja", "rojo")
NIVELES_QUE_AFECTAN = ("naranja", "rojo")
FUENTES = ("SENAMHI", "Capitania", "Agencia", "Comunidad")


def listar_panel(actor):
    exigir_rol(actor, "admin", "operador")
    # Devuelve las alertas vigentes, próximas y de los últimos 30 días, con su lugar y cuántas
    # salidas programadas que todavía no zarpan afecta cada una (subconsulta correlacionada).
    return bd.consultar(
        """
        SELECT a.id, a.tipo, a.nivel, a.titulo, a.fuente, a.vigente_desde, a.vigente_hasta,
               COALESCE(c.nombre, 'Todo el lago') AS lugar,
               (a.vigente_desde <= NOW() AND a.vigente_hasta > NOW()) AS vigente,
               (SELECT COUNT(*)
                FROM salida s
                WHERE a.nivel IN ('naranja','rojo')
                  AND s.estado IN ('programada','embarcando')
                  AND s.fecha_hora_zarpe > NOW()
                  AND s.fecha_hora_zarpe < a.vigente_hasta
                  AND s.fecha_hora_retorno > a.vigente_desde
                  AND (a.comunidad_id IS NULL
                       OR EXISTS (SELECT 1 FROM ruta_parada rp
                                  WHERE rp.ruta_id = s.ruta_id
                                    AND rp.comunidad_id = a.comunidad_id))) AS por_suspender
        FROM alerta_lago a
        LEFT JOIN comunidad c ON c.id = a.comunidad_id
        WHERE a.vigente_hasta >= NOW() - INTERVAL 30 DAY
        ORDER BY (a.vigente_hasta > NOW()) DESC, a.nivel DESC, a.vigente_desde DESC
        """
    )


def buscar_panel(actor, alerta_id):
    exigir_rol(actor, "admin", "operador")
    # Devuelve una alerta para verla o editarla, con su lugar y si sigue vigente o por venir.
    return bd.consultar_uno(
        """
        SELECT a.id, a.tipo, a.nivel, a.titulo, a.descripcion, a.fuente, a.comunidad_id,
               a.vigente_desde, a.vigente_hasta, COALESCE(c.nombre, 'Todo el lago') AS lugar,
               (a.vigente_hasta > NOW()) AS sin_terminar
        FROM alerta_lago a
        LEFT JOIN comunidad c ON c.id = a.comunidad_id
        WHERE a.id = %s
        """,
        (alerta_id,),
    )


def salidas_afectadas(actor, alerta_id):
    """RN-11: las salidas que esta alerta marca (solo si es naranja o roja)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve las salidas que todavía no zarpan cuyo horario se cruza con la alerta naranja o
    # roja y que pasan por su comunidad (o cualquiera, si la alerta es de todo el lago), con sus
    # pasajeros. Las ya suspendidas también salen, para ver qué falta.
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.embarcacion_nombre, v.estado,
               v.ocupados, v.cupo
        FROM alerta_lago a
        JOIN v_disponibilidad_salida v ON v.fecha_hora_zarpe < a.vigente_hasta
                                      AND v.fecha_hora_retorno > a.vigente_desde
        WHERE a.id = %s
          AND a.nivel IN ('naranja','rojo')
          AND v.estado IN ('programada','embarcando','suspendida')
          AND v.fecha_hora_zarpe > NOW()
          AND (a.comunidad_id IS NULL
               OR EXISTS (SELECT 1 FROM ruta_parada rp
                          WHERE rp.ruta_id = v.ruta_id AND rp.comunidad_id = a.comunidad_id))
        ORDER BY v.fecha_hora_zarpe
        """,
        (alerta_id,),
    )


def opciones_comunidades():
    # Devuelve las comunidades activas (una alerta puede ser de una comunidad o de todo el lago).
    return bd.consultar("SELECT id, nombre FROM comunidad WHERE activa = 1 ORDER BY nombre")


def guardar(actor, alerta_id, datos, ip=None):
    """Registra o corrige una alerta (se registran a mano: sin scraping de SENAMHI)."""
    exigir_rol(actor, "operador")
    e = {}
    tipo = v.opcion(datos, "tipo", e, TIPOS)
    nivel = v.opcion(datos, "nivel", e, NIVELES)
    fuente = v.opcion(datos, "fuente", e, FUENTES)
    titulo = v.texto(datos, "titulo", e, 5, 120, nombre="el título")
    descripcion = v.texto_largo(datos, "descripcion", e, 2000)
    comunidad_id = datos.get("comunidad_id") or None               # vacío = todo el lago
    desde = datos.get("vigente_desde")
    hasta = datos.get("vigente_hasta")
    if not isinstance(desde, datetime):
        e["vigente_desde"] = "Elige desde cuándo rige."
    if not isinstance(hasta, datetime):
        e["vigente_hasta"] = "Elige hasta cuándo rige."
    elif isinstance(desde, datetime) and hasta <= desde:
        e["vigente_hasta"] = "Tiene que terminar después de empezar."
    if e:
        raise ErrorValidacion(e)
    with bd.transaccion(lectura_actual=True) as cur:
        if comunidad_id:
            # Devuelve 1 si la comunidad elegida existe y está activa.
            cur.execute("SELECT COUNT(*) AS hay FROM comunidad WHERE id = %s AND activa = 1",
                        (comunidad_id,))
            if not cur.fetchone()["hay"]:
                raise ErrorValidacion(
                    {"comunidad_id": "Elige una comunidad activa o todo el lago."})
        valores = (tipo, nivel, titulo, descripcion, fuente, comunidad_id, desde, hasta)
        return catalogo.escribir(
            cur, actor, ip, "alerta_lago", alerta_id,
            insertar=("""
                INSERT INTO alerta_lago (tipo, nivel, titulo, descripcion, fuente, comunidad_id,
                                         vigente_desde, vigente_hasta, registrada_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (*valores, actor.id)),
            actualizar=("""
                UPDATE alerta_lago
                SET tipo = %s, nivel = %s, titulo = %s, descripcion = %s, fuente = %s,
                    comunidad_id = %s, vigente_desde = %s, vigente_hasta = %s
                WHERE id = %s
                """, (*valores, alerta_id)),
            duplicados={},
            resumen={"nivel": nivel, "tipo": tipo, "comunidad_id": comunidad_id,
                     "desde": desde, "hasta": hasta},
        )


def suspender_afectadas(actor, alerta_id, ip=None):
    """RN-11: suspende EN UNA TRANSACCIÓN todas las salidas que la alerta afecta.

    Devuelve la lista de ids suspendidos. Si una falla, no se suspende ninguna.
    """
    exigir_rol(actor, "operador")
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la alerta y si todavía no termina.
        cur.execute(
            """
            SELECT id, tipo, nivel, titulo, fuente, comunidad_id, vigente_desde, vigente_hasta,
                   (vigente_hasta > NOW()) AS sin_terminar
            FROM alerta_lago
            WHERE id = %s
            """,
            (alerta_id,),
        )
        alerta = cur.fetchone()
        if alerta is None:
            raise EstadoNoPermite("Esa alerta no existe.")
        if alerta["nivel"] not in NIVELES_QUE_AFECTAN or not alerta["sin_terminar"]:
            raise EstadoNoPermite("Solo una alerta naranja o roja que no terminó suspende salidas.")
        # Devuelve (y BLOQUEA, en orden de id para no cruzar bloqueos) las salidas programadas
        # que todavía no zarpan, se cruzan con la alerta y pasan por su comunidad.
        cur.execute(
            """
            SELECT s.id
            FROM salida s
            WHERE s.estado IN ('programada','embarcando')
              AND s.fecha_hora_zarpe > NOW()
              AND s.fecha_hora_zarpe < %s
              AND s.fecha_hora_retorno > %s
              AND (%s IS NULL
                   OR EXISTS (SELECT 1 FROM ruta_parada rp
                              WHERE rp.ruta_id = s.ruta_id AND rp.comunidad_id = %s))
            ORDER BY s.id
            FOR UPDATE
            """,
            (alerta["vigente_hasta"], alerta["vigente_desde"], alerta["comunidad_id"],
             alerta["comunidad_id"]),
        )
        ids = [fila["id"] for fila in cur.fetchall()]
        if not ids:
            raise EstadoNoPermite("No hay salidas por suspender con esta alerta.")
        motivo = (f"Alerta {alerta['nivel']} de {alerta['tipo']}: {alerta['titulo']} "
                  f"({alerta['fuente']})")[:255]
        # El trigger trg_salida_au anota cada cambio de estado con quién y desde dónde (S-24).
        cur.execute("SET @app_usuario_id = %s, @app_ip = %s", (actor.id, ip))
        marcas = ", ".join(["%s"] * len(ids))                 # una marca %s por salida
        cur.execute(
            f"UPDATE salida SET estado = 'suspendida', motivo_estado = %s WHERE id IN ({marcas})",  # noqa: S608
            (motivo, *ids),
        )
        bitacora.anotar(cur, actor.id, "suspension_por_alerta", "alerta_lago", alerta_id,
                        {"salidas": ids}, ip)
    return ids
