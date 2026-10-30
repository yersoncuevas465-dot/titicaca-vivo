"""Comunidades: listado y ficha para el público (familias sin datos personales) y
catálogo en el panel (F5)."""

from app import bd
from app.modelos import ROLES_CATALOGO, ErrorValidacion, catalogo, exigir_rol
from app.modelos import validacion as v

IDIOMAS = ("quechua", "aimara")
SENALES = ("buena", "debil", "sin_senal")


def listar_publicas():
    # Devuelve las comunidades activas con su ubicación, cuántas familias anfitrionas activas
    # tienen (y cuántas dan taller textil) y por cuántas rutas activas se las visita.
    # Cada LEFT JOIN es contra una subconsulta ya agrupada: así se evita una consulta por comunidad.
    return bd.consultar(
        """
        SELECT c.id, c.nombre, c.slug, c.distrito, c.provincia, c.idioma_originario, c.senal,
               c.tiene_hospedaje, c.descripcion, c.foto_credito, c.latitud, c.longitud,
               COALESCE(f.familias, 0) AS familias,
               COALESCE(f.talleres, 0) AS talleres,
               COALESCE(r.rutas, 0)    AS rutas
        FROM comunidad c
        LEFT JOIN (SELECT comunidad_id, COUNT(*) AS familias,
                          SUM(FIND_IN_SET('taller_textil', servicios) > 0) AS talleres
                   FROM familia_anfitriona
                   WHERE activa = 1
                   GROUP BY comunidad_id) f ON f.comunidad_id = c.id
        LEFT JOIN (SELECT rp.comunidad_id, COUNT(DISTINCT rp.ruta_id) AS rutas
                   FROM ruta_parada rp
                   JOIN ruta ru ON ru.id = rp.ruta_id AND ru.activa = 1
                   GROUP BY rp.comunidad_id) r ON r.comunidad_id = c.id
        WHERE c.activa = 1
        ORDER BY c.nombre
        """
    )


def buscar_por_slug(slug):
    # Devuelve la comunidad activa con ese slug (solo columnas públicas), o None.
    return bd.consultar_uno(
        """
        SELECT c.id, c.nombre, c.slug, c.distrito, c.provincia, c.idioma_originario, c.senal,
               c.tiene_hospedaje, c.descripcion, c.foto_credito, c.latitud, c.longitud
        FROM comunidad c
        WHERE c.slug = %s AND c.activa = 1
        """,
        (slug,),
    )


def familias_publicas(comunidad_id):
    # Devuelve las familias anfitrionas activas SIN datos personales: ni responsable ni teléfono.
    return bd.consultar(
        """
        SELECT f.nombre_familia, f.capacidad_personas, f.servicios
        FROM familia_anfitriona f
        WHERE f.comunidad_id = %s AND f.activa = 1
        ORDER BY f.nombre_familia
        """,
        (comunidad_id,),
    )


def rutas_que_la_visitan(comunidad_id):
    # Devuelve las rutas activas que pasan por la comunidad, en qué parada y si allí se duerme.
    return bd.consultar(
        """
        SELECT r.codigo, r.nombre, r.duracion_horas, rp.orden, rp.minutos_estadia, rp.es_pernocte
        FROM ruta_parada rp
        JOIN ruta r ON r.id = rp.ruta_id
        WHERE rp.comunidad_id = %s AND r.activa = 1
        ORDER BY r.duracion_horas, r.nombre
        """,
        (comunidad_id,),
    )


def proximas_salidas(comunidad_id, limite=6):
    # Devuelve las próximas salidas (de ahora a 7 días) cuyas rutas pasan por la comunidad.
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.libres, v.estado_publico,
               rp.es_pernocte
        FROM v_disponibilidad_salida v
        JOIN ruta_parada rp ON rp.ruta_id = v.ruta_id
        WHERE rp.comunidad_id = %s
          AND v.estado <> 'cancelada'
          AND v.fecha_hora_zarpe >= NOW()
          AND v.fecha_hora_zarpe <  CURDATE() + INTERVAL 7 DAY
        ORDER BY v.fecha_hora_zarpe
        LIMIT %s
        """,
        (comunidad_id, limite),
    )


# --- Catálogo de comunidades (panel, F5) -----------------------------------------------------

def listar_panel(actor):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve todas las comunidades (también inactivas) con cuántas familias activas tiene cada
    # una y en cuántas rutas es parada (LEFT JOIN a subconsultas agrupadas: una sola consulta).
    return bd.consultar(
        """
        SELECT c.id, c.nombre, c.slug, c.distrito, c.idioma_originario, c.senal,
               c.tiene_hospedaje, c.activa,
               COALESCE(f.familias, 0) AS familias, COALESCE(p.rutas, 0) AS rutas
        FROM comunidad c
        LEFT JOIN (SELECT comunidad_id, COUNT(*) AS familias
                   FROM familia_anfitriona
                   WHERE activa = 1
                   GROUP BY comunidad_id) f ON f.comunidad_id = c.id
        LEFT JOIN (SELECT comunidad_id, COUNT(*) AS rutas
                   FROM ruta_parada
                   GROUP BY comunidad_id) p ON p.comunidad_id = c.id
        ORDER BY c.activa DESC, c.nombre
        """
    )


def buscar_panel(actor, comunidad_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve todas las columnas de una comunidad para editarla.
    return bd.consultar_uno(
        """
        SELECT id, nombre, slug, distrito, provincia, idioma_originario, senal, whatsapp_contacto,
               descripcion, foto_credito, latitud, longitud, tiene_hospedaje, activa
        FROM comunidad
        WHERE id = %s
        """,
        (comunidad_id,),
    )


def opciones():
    # Devuelve las comunidades activas (para elegirlas en un formulario), con si dan hospedaje.
    return bd.consultar(
        "SELECT id, nombre, tiene_hospedaje FROM comunidad WHERE activa = 1 ORDER BY nombre")


def guardar(actor, comunidad_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    nombre = v.texto(datos, "nombre", e, 2, 80, nombre="el nombre")
    slug = (datos.get("slug") or "").strip().lower() or v.slug_de(nombre or "")
    if len(slug) > 80 or not v.PATRON_SLUG.match(slug):
        e["slug"] = "Solo minúsculas, números y guiones (por ejemplo luquina-chico)."
    distrito = v.texto(datos, "distrito", e, 2, 60, nombre="el distrito")
    provincia = v.texto(datos, "provincia", e, 2, 60, nombre="la provincia")
    idioma = v.opcion(datos, "idioma_originario", e, IDIOMAS)
    senal = v.opcion(datos, "senal", e, SENALES)
    whatsapp = v.telefono(datos, "whatsapp_contacto", e)
    descripcion = v.texto_largo(datos, "descripcion", e, 2000)
    credito = v.texto(datos, "foto_credito", e, 3, 200, obligatorio=False)
    latitud = v.decimal(datos, "latitud", e, -90, 90, decimales=6, obligatorio=False)
    longitud = v.decimal(datos, "longitud", e, -180, 180, decimales=6, obligatorio=False)
    if (latitud is None) != (longitud is None) and not {"latitud", "longitud"} & e.keys():
        e["longitud"] = "Escribe las dos coordenadas o ninguna (D-38)."
    hospedaje = v.booleano(datos, "tiene_hospedaje")
    activa = v.booleano(datos, "activa")
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        if comunidad_id:
            # Devuelve en cuántas rutas ACTIVAS es parada la comunidad y en cuántas se duerme allí.
            cur.execute(
                """
                SELECT COUNT(*) AS rutas, COALESCE(SUM(rp.es_pernocte), 0) AS noches
                FROM ruta_parada rp
                JOIN ruta r ON r.id = rp.ruta_id AND r.activa = 1
                WHERE rp.comunidad_id = %s
                """,
                (comunidad_id,),
            )
            uso = cur.fetchone()
            if not activa and uso["rutas"]:
                e["activa"] = (f"Es parada de {uso['rutas']} ruta(s) activa(s): quítala de esas "
                               "rutas antes de desactivarla.")
            if not hospedaje and uso["noches"]:
                e["tiene_hospedaje"] = ("En una ruta activa se duerme aquí: no puede quedar "
                                        "sin hospedaje.")
            if e:
                raise ErrorValidacion(e)
        valores = (nombre, slug, distrito, provincia, idioma, senal, whatsapp, descripcion, credito,
                   latitud, longitud, hospedaje, activa)
        return catalogo.escribir(
            cur, actor, ip, "comunidad", comunidad_id,
            insertar=("""
                INSERT INTO comunidad (nombre, slug, distrito, provincia, idioma_originario, senal,
                                       whatsapp_contacto, descripcion, foto_credito, latitud,
                                       longitud, tiene_hospedaje, activa)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, valores),
            actualizar=("""
                UPDATE comunidad
                SET nombre = %s, slug = %s, distrito = %s, provincia = %s, idioma_originario = %s,
                    senal = %s, whatsapp_contacto = %s, descripcion = %s, foto_credito = %s,
                    latitud = %s, longitud = %s, tiene_hospedaje = %s, activa = %s
                WHERE id = %s
                """, (*valores, comunidad_id)),
            duplicados={"uk_comunidad_nombre": ("nombre", "Ya hay una comunidad con ese nombre."),
                        "uk_comunidad_slug": ("slug", "Ya hay una comunidad con ese slug.")},
            resumen={"nombre": nombre, "slug": slug, "activa": activa},
        )
