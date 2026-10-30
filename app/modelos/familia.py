"""Catálogo de familias anfitrionas (turismo vivencial). La rotación está en hospedaje.py."""

from app import bd
from app.modelos import ROLES_CATALOGO, ErrorValidacion, catalogo, exigir_rol
from app.modelos import validacion as v

SERVICIOS = ("desayuno", "almuerzo", "cena", "vestimenta", "taller_textil")


def listar_panel(actor, comunidad_id=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve las familias (también inactivas) con su comunidad y cuántas noches tienen
    # asignadas desde hoy (filtro opcional por comunidad).
    return bd.consultar(
        """
        SELECT f.id, f.nombre_familia, f.responsable, f.telefono, f.capacidad_personas,
               f.servicios, f.activa, c.nombre AS comunidad,
               (SELECT COUNT(*) FROM hospedaje h
                WHERE h.familia_id = f.id AND h.estado = 'asignado'
                  AND h.fecha_noche >= CURDATE()) AS noches_por_venir
        FROM familia_anfitriona f
        JOIN comunidad c ON c.id = f.comunidad_id
        WHERE (%s IS NULL OR f.comunidad_id = %s)
        ORDER BY c.nombre, f.activa DESC, f.nombre_familia
        """,
        (comunidad_id, comunidad_id),
    )


def buscar_panel(actor, familia_id):
    exigir_rol(actor, *ROLES_CATALOGO)
    # Devuelve una familia para editarla (con sus datos de contacto: solo para el panel).
    fila = bd.consultar_uno(
        """
        SELECT id, comunidad_id, nombre_familia, responsable, telefono, capacidad_personas,
               servicios, activa
        FROM familia_anfitriona
        WHERE id = %s
        """,
        (familia_id,),
    )
    if fila:
        # El SET de MariaDB llega como texto con comas: 'desayuno,cena' → ['desayuno', 'cena']
        fila["servicios"] = [s for s in (fila["servicios"] or "").split(",") if s]
    return fila


def guardar(actor, familia_id, datos, ip=None):
    exigir_rol(actor, *ROLES_CATALOGO)
    e = {}
    comunidad_id = v.entero(datos, "comunidad_id", e, 1, 4294967295)
    nombre = v.texto(datos, "nombre_familia", e, 2, 80, nombre="el nombre de la familia")
    responsable = v.texto(datos, "responsable", e, 3, 120, nombre="quién es el responsable")
    telefono = v.telefono(datos, "telefono", e)
    capacidad = v.entero(datos, "capacidad_personas", e, 1, 10)
    servicios = list(datos.get("servicios") or [])
    if not set(servicios) <= set(SERVICIOS):
        e["servicios"] = "Elige servicios de la lista."
    activa = v.booleano(datos, "activa")
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la comunidad elegida, si está activa y si recibe hospedaje vivencial.
        cur.execute("SELECT activa, tiene_hospedaje FROM comunidad WHERE id = %s", (comunidad_id,))
        comunidad = cur.fetchone()
        if comunidad is None or not comunidad["activa"] or not comunidad["tiene_hospedaje"]:
            e["comunidad_id"] = "Elige una comunidad activa que reciba hospedaje."
        if familia_id:
            # Devuelve la comunidad actual de la familia y la BLOQUEA: así la rotación (RN-10)
            # no le asigna una noche nueva mientras se edita.
            cur.execute("SELECT comunidad_id FROM familia_anfitriona WHERE id = %s FOR UPDATE",
                        (familia_id,))
            actual = cur.fetchone() or {}
            # Devuelve cuántas noches tiene asignadas desde hoy y el grupo más grande que recibirá
            # (su capacidad no puede bajar de ese grupo).
            cur.execute(
                """
                SELECT COUNT(*) AS noches, COALESCE(MAX(personas), 0) AS mayor_grupo
                FROM hospedaje
                WHERE familia_id = %s AND estado = 'asignado' AND fecha_noche >= CURDATE()
                """,
                (familia_id,),
            )
            actual.update(cur.fetchone())
            if actual["noches"]:
                if not activa:
                    e["activa"] = (f"Tiene {actual['noches']} noche(s) asignada(s) desde hoy: "
                                   "no se puede desactivar todavía.")
                if comunidad_id != actual["comunidad_id"]:
                    e["comunidad_id"] = "Tiene noches asignadas: no se puede cambiar de comunidad."
                if capacidad < actual["mayor_grupo"]:
                    e["capacidad_personas"] = (f"Recibirá un grupo de {actual['mayor_grupo']} "
                                               "personas: la capacidad no puede ser menor.")
        if e:
            raise ErrorValidacion(e)
        lista = ",".join(s for s in SERVICIOS if s in servicios)      # en el orden del SET
        valores = (comunidad_id, nombre, responsable, telefono, capacidad, lista, activa)
        return catalogo.escribir(
            cur, actor, ip, "familia_anfitriona", familia_id,
            insertar=("""
                INSERT INTO familia_anfitriona (comunidad_id, nombre_familia, responsable, telefono,
                                                capacidad_personas, servicios, activa)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, valores),
            actualizar=("""
                UPDATE familia_anfitriona
                SET comunidad_id = %s, nombre_familia = %s, responsable = %s, telefono = %s,
                    capacidad_personas = %s, servicios = %s, activa = %s
                WHERE id = %s
                """, (*valores, familia_id)),
            duplicados={},
            resumen={"comunidad_id": comunidad_id, "nombre_familia": nombre,
                     "capacidad": capacidad, "activa": activa},
        )
