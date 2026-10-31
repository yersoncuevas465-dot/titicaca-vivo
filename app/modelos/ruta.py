"""Rutas: catálogo público, paradas y datos para el mapa. En el panel: rutas y paradas (F5)."""

import re

from app import bd
from app.modelos import (
    ROLES_CATALOGO,
    ErrorValidacion,
    EstadoNoPermite,
    bitacora,
    catalogo,
    exigir_rol,
)
from app.modelos import validacion as v

PATRON_CODIGO_RUTA = re.compile(r"^[A-Z0-9-]{3,12}$")


def listar_activas():
    # Devuelve las rutas activas con su precio base más bajo vigente hoy (el "desde S/").
    # LEFT JOIN: una ruta sin tarifa vigente igual aparece (con "desde" en NULL).
    return bd.consultar(
        """
        SELECT r.id, r.codigo, r.nombre, r.descripcion, r.duracion_horas, r.incluye_pernocte,
               MIN(t.precio_base) AS desde
        FROM ruta r
        LEFT JOIN tarifa t ON t.ruta_id = r.id
                          AND t.vigente_desde <= CURDATE()
                          AND (t.vigente_hasta IS NULL OR t.vigente_hasta >= CURDATE())
        WHERE r.activa = 1
        GROUP BY r.id, r.codigo, r.nombre, r.descripcion, r.duracion_horas, r.incluye_pernocte
        ORDER BY r.duracion_horas, r.nombre
        """
    )


def paradas(ruta_id):
    # Devuelve las paradas de una ruta en orden, con la comunidad, su idioma y si allí se duerme.
    return bd.consultar(
        """
        SELECT rp.orden, rp.minutos_estadia, rp.es_pernocte,
               c.nombre, c.slug, c.idioma_originario, c.senal
        FROM ruta_parada rp
        JOIN comunidad c ON c.id = rp.comunidad_id
        WHERE rp.ruta_id = %s
        ORDER BY rp.orden
        """,
        (ruta_id,),
    )


def muelles():
    """Los muelles de donde zarpan las rutas activas (v2.6, página de contacto)."""
    # Devuelve cada muelle de salida una sola vez (DISTINCT), en orden alfabético.
    filas = bd.consultar(
        "SELECT DISTINCT muelle_salida FROM ruta WHERE activa = 1 ORDER BY muelle_salida")
    return [f["muelle_salida"] for f in filas]


def paradas_para_mapa():
    # Devuelve, en UNA consulta, cada parada de cada ruta activa con la ubicación de su
    # comunidad, ordenadas por ruta y por orden de visita (así no hay una consulta por ruta).
    return bd.consultar(
        """
        SELECT r.id AS ruta_id, r.codigo, r.nombre, rp.orden,
               c.slug, c.latitud, c.longitud
        FROM ruta r
        JOIN ruta_parada rp ON rp.ruta_id = r.id
        JOIN comunidad c    ON c.id = rp.comunidad_id
        WHERE r.activa = 1
        ORDER BY r.duracion_horas, r.id, rp.orden
        """
    )


# --- Catálogo de rutas y paradas (panel, F5) -------------------------------------------------

def listar_panel(actor):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve todas las rutas (también inactivas) con cuántas paradas tienen, dónde se duerme
    # (la parada con es_pernocte) y cuántas salidas por venir tienen (subconsulta).
    return bd.consultar(
        """
        SELECT r.id, r.codigo, r.nombre, r.duracion_horas, r.incluye_pernocte, r.muelle_salida,
               r.activa, COUNT(rp.id) AS paradas,
               MAX(CASE WHEN rp.es_pernocte = 1 THEN c.nombre END) AS pernocte_en,
               (SELECT COUNT(*) FROM salida s
                WHERE s.ruta_id = r.id
                  AND s.estado IN ('programada','embarcando','suspendida')
                  AND s.fecha_hora_zarpe > NOW()) AS salidas_por_venir
        FROM ruta r
        LEFT JOIN ruta_parada rp ON rp.ruta_id = r.id
        LEFT JOIN comunidad c    ON c.id = rp.comunidad_id
        GROUP BY r.id, r.codigo, r.nombre, r.duracion_horas, r.incluye_pernocte,
                 r.muelle_salida, r.activa
        ORDER BY r.activa DESC, r.nombre
        """
    )


def buscar_panel(actor, ruta_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve una ruta para editarla.
    return bd.consultar_uno(
        """
        SELECT id, codigo, nombre, descripcion, duracion_horas, incluye_pernocte, muelle_salida,
               activa
        FROM ruta
        WHERE id = %s
        """,
        (ruta_id,),
    )


def guardar(actor, ruta_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    codigo = (datos.get("codigo") or "").strip().upper()
    if not PATRON_CODIGO_RUTA.match(codigo):
        e["codigo"] = "De 3 a 12 letras mayúsculas, números o guiones (por ejemplo URO-TAQ)."
    nombre = v.texto(datos, "nombre", e, 3, 100, nombre="el nombre")
    descripcion = v.texto_largo(datos, "descripcion", e, 2000)
    duracion = v.decimal(datos, "duracion_horas", e, "0.5", "99.9", decimales=1)
    pernocte = v.booleano(datos, "incluye_pernocte")
    muelle = v.texto(datos, "muelle_salida", e, 3, 100, nombre="el muelle de salida")
    activa = v.booleano(datos, "activa")
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        if ruta_id:
            # Devuelve si la ruta tiene una parada donde se duerme y cuántas salidas por venir.
            cur.execute(
                """
                SELECT (SELECT COUNT(*) FROM ruta_parada
                        WHERE ruta_id = %s AND es_pernocte = 1) AS paradas_noche,
                       (SELECT COUNT(*) FROM salida
                        WHERE ruta_id = %s AND estado IN ('programada','embarcando','suspendida')
                          AND fecha_hora_zarpe > NOW()) AS salidas_por_venir
                """,
                (ruta_id, ruta_id),
            )
            uso = cur.fetchone()
            if not pernocte and uso["paradas_noche"]:
                e["incluye_pernocte"] = "Primero quita la noche de su parada (en Paradas)."
            if not activa and uso["salidas_por_venir"]:
                e["activa"] = (f"Tiene {uso['salidas_por_venir']} salidas por venir: cancélalas "
                               "o espera a que pasen antes de desactivarla.")
            if e:
                raise ErrorValidacion(e)
        valores = (codigo, nombre, descripcion, duracion, pernocte, muelle, activa)
        return catalogo.escribir(
            cur, actor, ip, "ruta", ruta_id,
            insertar=("""
                INSERT INTO ruta (codigo, nombre, descripcion, duracion_horas, incluye_pernocte,
                                  muelle_salida, activa)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, valores),
            actualizar=("""
                UPDATE ruta
                SET codigo = %s, nombre = %s, descripcion = %s, duracion_horas = %s,
                    incluye_pernocte = %s, muelle_salida = %s, activa = %s
                WHERE id = %s
                """, (*valores, ruta_id)),
            duplicados={"uk_ruta_codigo": ("codigo", "Ya hay una ruta con ese código.")},
            resumen={"codigo": codigo, "duracion_horas": duracion, "activa": activa},
        )


def paradas_panel(actor, ruta_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve las paradas de la ruta en orden, con el nombre de la comunidad.
    return bd.consultar(
        """
        SELECT rp.id, rp.comunidad_id, rp.orden, rp.minutos_estadia, rp.es_pernocte,
               c.nombre AS comunidad, c.tiene_hospedaje
        FROM ruta_parada rp
        JOIN comunidad c ON c.id = rp.comunidad_id
        WHERE rp.ruta_id = %s
        ORDER BY rp.orden
        """,
        (ruta_id,),
    )


def buscar_parada(actor, ruta_id, parada_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve una parada de esa ruta (si es de otra ruta, no la devuelve).
    return bd.consultar_uno(
        """
        SELECT id, comunidad_id, orden, minutos_estadia, es_pernocte
        FROM ruta_parada
        WHERE id = %s AND ruta_id = %s
        """,
        (parada_id, ruta_id),
    )


def guardar_parada(actor, ruta_id, parada_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    comunidad_id = v.entero(datos, "comunidad_id", e, 1, 4294967295)
    orden = v.entero(datos, "orden", e, 1, 50)
    minutos = v.entero(datos, "minutos_estadia", e, 0, 2880)
    pernocte = v.booleano(datos, "es_pernocte")
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la ruta y la BLOQUEA: los cambios de paradas de una ruta van de a uno.
        cur.execute("SELECT incluye_pernocte FROM ruta WHERE id = %s FOR UPDATE", (ruta_id,))
        ruta = cur.fetchone()
        if ruta is None:
            raise EstadoNoPermite("Esa ruta no existe.")
        # Devuelve la comunidad elegida, si está activa y si recibe hospedaje.
        cur.execute("SELECT activa, tiene_hospedaje FROM comunidad WHERE id = %s", (comunidad_id,))
        comunidad = cur.fetchone()
        if comunidad is None or not comunidad["activa"]:
            e["comunidad_id"] = "Elige una comunidad activa."
        if pernocte:
            # Devuelve cuántas OTRAS paradas de la ruta son de pernocte (S-16: solo una).
            cur.execute(
                """
                SELECT COUNT(*) AS otras
                FROM ruta_parada
                WHERE ruta_id = %s AND es_pernocte = 1 AND id <> %s
                """,
                (ruta_id, parada_id or 0),
            )
            if not ruta["incluye_pernocte"]:
                e["es_pernocte"] = "La ruta no incluye noche (márcalo en la ruta primero)."
            elif cur.fetchone()["otras"]:
                e["es_pernocte"] = "La ruta ya tiene una parada donde se duerme (S-16: solo una)."
            elif comunidad and not comunidad["tiene_hospedaje"]:
                e["es_pernocte"] = "Esa comunidad no recibe hospedaje vivencial."
        if e:
            raise ErrorValidacion(e)
        valores = (comunidad_id, orden, minutos, pernocte)
        return catalogo.escribir(
            cur, actor, ip, "ruta_parada", parada_id,
            insertar=("""
                INSERT INTO ruta_parada (comunidad_id, orden, minutos_estadia, es_pernocte, ruta_id)
                VALUES (%s, %s, %s, %s, %s)
                """, (*valores, ruta_id)),
            actualizar=("""
                UPDATE ruta_parada
                SET comunidad_id = %s, orden = %s, minutos_estadia = %s, es_pernocte = %s
                WHERE id = %s AND ruta_id = %s
                """, (*valores, parada_id, ruta_id)),
            duplicados={"uk_parada_orden": ("orden", "Ya hay una parada con ese orden."),
                        "uk_parada_comunidad": ("comunidad_id",
                                                "Esa comunidad ya es parada de esta ruta.")},
            resumen={"ruta_id": ruta_id, "comunidad_id": comunidad_id, "orden": orden,
                     "es_pernocte": pernocte},
        )


def borrar_parada(actor, ruta_id, parada_id, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    with bd.transaccion(lectura_actual=True) as cur:
        # Borra la parada solo si es de esa ruta (ruta_parada no tiene hijos: nada más se borra).
        cur.execute("DELETE FROM ruta_parada WHERE id = %s AND ruta_id = %s", (parada_id, ruta_id))
        if cur.rowcount == 0:
            raise EstadoNoPermite("Esa parada no existe.")
        bitacora.anotar(cur, actor.id, "borrado", "ruta_parada", parada_id, {"ruta_id": ruta_id},
                        ip)
