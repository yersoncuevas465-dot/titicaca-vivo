"""Productos y artesanías (v2.9, tabla 21, D-119 y D-120).

Los publica un residente de una comunidad (solo en la suya, la de su cuenta) o la agencia (el
operador, en Puno o en una comunidad), con su precio, sus características y dónde encontrarlos.

- El residente ve y edita solo los suyos: los retira o los vuelve a publicar.
- El operador edita los de la agencia y oculta el de un residente que no corresponda; lo oculto
  solo lo vuelve a mostrar él. El admin solo mira.
- La página pública muestra lo publicado de la agencia y de los residentes con la cuenta activa.

Cada cambio queda en la bitácora (creación, edición y cambio de estado). Nada se borra.
"""

from app import bd
from app.modelos import (
    ErrorNegocio,
    ErrorValidacion,
    EstadoNoPermite,
    PermisoDenegado,
    bitacora,
    catalogo,
    exigir_rol,
)
from app.modelos import validacion as v

CATEGORIAS = {"textil": "Tejidos y bordados", "artesania": "Tallados y artesanías",
              "alimento": "Productos del campo", "recuerdo": "Recuerdos"}
ESTADOS = {"publicado": "Publicado", "retirado": "Retirado", "oculto": "Oculto por la agencia"}
PRECIO_MINIMO, PRECIO_MAXIMO = "0.50", 10000


def puede_editar(actor, p):
    """El residente edita los suyos; el operador, los de la agencia."""
    if actor.rol == "residente":
        return p["residente_id"] == actor.id
    return actor.rol == "operador" and p["residente_id"] is None


def cambios_permitidos(actor, p):
    """Los estados a los que este actor puede pasar el producto (los botones del panel)."""
    if puede_editar(actor, p):            # quien lo publicó: retirar o volver a publicar
        return {"publicado": ("retirado",), "retirado": ("publicado",)}.get(p["estado"], ())
    if actor.rol == "operador":           # el de un residente: ocultar o volver a mostrar
        return {"publicado": ("oculto",), "oculto": ("publicado",)}.get(p["estado"], ())
    return ()


# --- Lo que ve el turista -----------------------------------------------------------------------

def publicados():
    """Todo lo publicado, del más nuevo al más antiguo (la página filtra en Python)."""
    # Devuelve los productos publicados con su comunidad y quién los ofrece. LEFT JOIN: los de
    # la agencia no tienen residente y los que están en Puno no tienen comunidad. No salen los
    # de un residente desactivado ni los de una comunidad desactivada.
    return bd.consultar(
        """
        SELECT p.id, p.nombre, p.categoria, p.descripcion, p.precio, p.lugar, p.foto,
               p.foto_credito, c.nombre AS comunidad, c.slug AS comunidad_slug,
               u.nombre_completo AS residente
        FROM producto p
        LEFT JOIN comunidad c ON c.id = p.comunidad_id
        LEFT JOIN usuario u ON u.id = p.residente_id
        WHERE p.estado = 'publicado'
          AND (p.residente_id IS NULL OR u.activo = 1)
          AND (p.comunidad_id IS NULL OR c.activa = 1)
        ORDER BY p.creado_en DESC, p.id DESC
        """
    )


def destacados(cantidad=3):
    """Los últimos publicados, para la portada."""
    # Devuelve los N productos publicados más nuevos (las mismas reglas que publicados()).
    return bd.consultar(
        """
        SELECT p.id, p.nombre, p.categoria, p.descripcion, p.precio, p.lugar, p.foto,
               p.foto_credito, c.nombre AS comunidad, c.slug AS comunidad_slug,
               u.nombre_completo AS residente
        FROM producto p
        LEFT JOIN comunidad c ON c.id = p.comunidad_id
        LEFT JOIN usuario u ON u.id = p.residente_id
        WHERE p.estado = 'publicado'
          AND (p.residente_id IS NULL OR u.activo = 1)
          AND (p.comunidad_id IS NULL OR c.activa = 1)
        ORDER BY p.creado_en DESC, p.id DESC
        LIMIT %s
        """,
        (cantidad,),
    )


# --- Panel ---------------------------------------------------------------------------------------

def listar_panel(actor):
    """El residente ve los suyos; el operador y el admin, todos. Cada uno con sus botones."""
    exigir_rol(actor, "admin", "operador", "residente")
    solo_de = actor.id if actor.rol == "residente" else None
    # Devuelve los productos (todos, o solo los de un residente) en cualquier estado, con su
    # comunidad y quién los publicó; los más nuevos primero.
    filas = bd.consultar(
        """
        SELECT p.id, p.residente_id, p.comunidad_id, p.nombre, p.categoria, p.descripcion,
               p.precio, p.lugar, p.foto, p.estado, p.creado_en, p.actualizado_en,
               c.nombre AS comunidad, u.nombre_completo AS residente, u.activo AS residente_activo
        FROM producto p
        LEFT JOIN comunidad c ON c.id = p.comunidad_id
        LEFT JOIN usuario u ON u.id = p.residente_id
        WHERE (%s IS NULL OR p.residente_id = %s)
        ORDER BY p.creado_en DESC, p.id DESC
        """,
        (solo_de, solo_de),
    )
    for fila in filas:
        fila["editable"] = puede_editar(actor, fila)
        fila["cambios"] = cambios_permitidos(actor, fila)
    return filas


def buscar_para_editar(actor, producto_id):
    """El producto si este actor lo puede editar; si no (o no existe), None (la ruta da 404)."""
    exigir_rol(actor, "operador", "residente")
    # Devuelve un producto por su id.
    fila = bd.consultar_uno(
        """
        SELECT id, residente_id, comunidad_id, nombre, categoria, descripcion, precio, lugar,
               foto, estado
        FROM producto
        WHERE id = %s
        """,
        (producto_id,),
    )
    return fila if fila and puede_editar(actor, fila) else None


def resumen_residente(actor):
    """Para el «Resumen» del residente: su comunidad y cuántos productos tiene en cada estado."""
    exigir_rol(actor, "residente")
    # Devuelve la comunidad del residente y cuántos productos suyos hay en cada estado
    # (LEFT JOIN: con 0 productos igual sale su comunidad).
    return bd.consultar_uno(
        """
        SELECT c.nombre AS comunidad, c.slug AS comunidad_slug, COUNT(p.id) AS total,
               COALESCE(SUM(p.estado = 'publicado'), 0) AS publicados,
               COALESCE(SUM(p.estado = 'retirado'), 0) AS retirados,
               COALESCE(SUM(p.estado = 'oculto'), 0) AS ocultos
        FROM comunidad c
        LEFT JOIN producto p ON p.residente_id = %s
        WHERE c.id = %s
        GROUP BY c.id, c.nombre, c.slug
        """,
        (actor.id, actor.comunidad_id),
    )


def guardar(actor, producto_id, datos, ip=None, foto=None):
    """Crea (producto_id None) o edita un producto. Devuelve su id.

    El residente publica en SU comunidad (la de su cuenta, no la del formulario). El operador
    elige dónde está el de la agencia: en Puno (0) o en una comunidad activa. `foto` es la ruta
    de una foto nueva (servicios/fotos.py): reemplaza a la anterior y su crédito (es propia).
    """
    exigir_rol(actor, "operador", "residente")
    e = {}
    nombre = v.texto(datos, "nombre", e, 3, 80, nombre="el nombre del producto")
    categoria = v.opcion(datos, "categoria", e, CATEGORIAS, "Elige una categoría.")
    descripcion = v.texto_largo(datos, "descripcion", e, 600)
    if "descripcion" not in e and len(descripcion or "") < 10:
        e["descripcion"] = "Cuenta sus características: material, medidas o colores."
    precio = v.decimal(datos, "precio", e, PRECIO_MINIMO, PRECIO_MAXIMO)
    lugar = v.texto(datos, "lugar", e, 5, 160, nombre="dónde lo encuentran")

    with bd.transaccion() as cur:
        if producto_id:
            # Devuelve el producto que se edita, BLOQUEADO hasta el COMMIT.
            cur.execute("SELECT residente_id FROM producto WHERE id = %s FOR UPDATE",
                        (producto_id,))
            actual = cur.fetchone()
            if actual is None or not puede_editar(actor, actual):
                raise PermisoDenegado("Solo quien publicó el producto lo edita.")
        if actor.rol == "residente":
            if actor.comunidad_id is None:
                raise ErrorNegocio("Tu cuenta no tiene comunidad: pídele al admin que la ponga.")
            residente_id, comunidad_id = actor.id, actor.comunidad_id
        else:
            residente_id = None
            comunidad_id = v.entero(datos, "comunidad_id", e, 0, 4294967295) or None
            if comunidad_id and "comunidad_id" not in e:
                # Devuelve 1 si la comunidad existe y está activa.
                cur.execute("SELECT COUNT(*) AS hay FROM comunidad WHERE id = %s AND activa = 1",
                            (comunidad_id,))
                if not cur.fetchone()["hay"]:
                    e["comunidad_id"] = "Elige una comunidad activa o «En Puno, con la agencia»."
        if e:
            raise ErrorValidacion(e)
        return catalogo.escribir(
            cur, actor, ip, "producto", producto_id,
            insertar=(
                """
                INSERT INTO producto (residente_id, comunidad_id, nombre, categoria, descripcion,
                                      precio, lugar, foto)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (residente_id, comunidad_id, nombre, categoria, descripcion, precio, lugar, foto),
            ),
            actualizar=(
                """
                UPDATE producto
                SET comunidad_id = %s, nombre = %s, categoria = %s, descripcion = %s,
                    precio = %s, lugar = %s, foto = COALESCE(%s, foto),
                    foto_credito = IF(%s IS NULL, foto_credito, NULL)
                WHERE id = %s
                """,
                (comunidad_id, nombre, categoria, descripcion, precio, lugar, foto, foto,
                 producto_id),
            ),
            duplicados={},
            resumen={"nombre": nombre, "categoria": categoria, "precio": str(precio),
                     **({"foto": "nueva"} if foto else {})},
        )


def cambiar_estado(actor, producto_id, nuevo, ip=None):
    """Retira, vuelve a publicar, oculta o vuelve a mostrar. Devuelve el nombre del producto."""
    exigir_rol(actor, "operador", "residente")
    with bd.transaccion() as cur:
        # Devuelve el producto, BLOQUEADO hasta el COMMIT (dos clics a la vez no se pisan).
        cur.execute(
            "SELECT id, residente_id, nombre, estado FROM producto WHERE id = %s FOR UPDATE",
            (producto_id,),
        )
        fila = cur.fetchone()
        if fila is None or (actor.rol == "residente" and fila["residente_id"] != actor.id):
            raise PermisoDenegado("Ese producto no es tuyo.")
        if nuevo not in cambios_permitidos(actor, fila):
            raise EstadoNoPermite("Ese cambio no se puede hacer: recarga la página.")
        cur.execute("UPDATE producto SET estado = %s WHERE id = %s", (nuevo, producto_id))
        bitacora.anotar(cur, actor.id, "cambio_estado", "producto", producto_id,
                        {"nombre": fila["nombre"], "de": fila["estado"], "a": nuevo}, ip)
    return fila["nombre"]
