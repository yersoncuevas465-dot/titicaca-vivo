"""Usuarios del personal: inicio de sesión, carga de la sesión (Flask-Login) y, para el
admin, alta y edición del personal (F5)."""

import json
import re

import bcrypt
from flask_login import UserMixin

from app import bd
from app.modelos import ErrorNegocio, ErrorValidacion, bitacora, catalogo, cuenta, exigir_rol
from app.modelos import validacion as v

# Hash bcrypt de una clave al azar que nadie conoce. Si el usuario no existe,
# igual se compara contra este hash: así la respuesta tarda lo mismo y no
# delata qué nombres de usuario existen.
HASH_FICTICIO = b"$2b$12$OFDi1FKLR5dz13.47mCc..UMdAszIa16BIiKzimuOekHY1oocE6ee"
MAX_BYTES_BCRYPT = 72   # bcrypt 5 da error con contraseñas más largas


class UsuarioSesion(UserMixin):
    """Lo que la sesión necesita saber del usuario (nunca el hash)."""

    def __init__(self, fila):
        self.id = fila["id"]
        self.nombre_usuario = fila["nombre_usuario"]
        self.nombre_completo = fila["nombre_completo"]
        self.rol = fila["rol"]
        self.rol_nombre = fila["rol_nombre"]
        self.comunidad_id = fila["comunidad_id"]
        self.activo = bool(fila["activo"])
        self.sello = cuenta.sello(fila["hash_contrasena"])     # D-112 (nunca el hash)

    @property
    def is_active(self):
        return self.activo

    def get_id(self):
        # La cookie guarda "id.sello": si la contraseña cambia, esta sesión deja de valer.
        return f"{self.id}.{self.sello}"


def buscar_por_id(usuario_id):
    # Devuelve el usuario activo con ese id y el código de su rol
    # (lo usa Flask-Login en cada petición para saber quién es; el hash, para el sello).
    fila = bd.consultar_uno(
        """
        SELECT u.id, u.nombre_usuario, u.nombre_completo, u.comunidad_id, u.activo,
               u.hash_contrasena, r.codigo AS rol, r.nombre AS rol_nombre
        FROM usuario u
        JOIN rol r ON r.id = u.rol_id
        WHERE u.id = %s AND u.activo = 1
        """,
        (usuario_id,),
    )
    return UsuarioSesion(fila) if fila else None


def verificar_credenciales(nombre_usuario, contrasena):
    """Devuelve el UsuarioSesion si el usuario existe, está activo y la contraseña es correcta.

    Si algo falla devuelve None, sin decir qué falló (el mensaje es siempre el mismo).
    """
    # Devuelve el usuario con ese nombre, su rol y su hash (para comparar la contraseña).
    fila = bd.consultar_uno(
        """
        SELECT u.id, u.nombre_usuario, u.nombre_completo, u.comunidad_id, u.activo,
               u.hash_contrasena, r.codigo AS rol, r.nombre AS rol_nombre
        FROM usuario u
        JOIN rol r ON r.id = u.rol_id
        WHERE u.nombre_usuario = %s
        """,
        ((nombre_usuario or "").strip(),),
    )
    clave = (contrasena or "").encode("utf-8")
    demasiado_larga = len(clave) > MAX_BYTES_BCRYPT
    hash_guardado = fila["hash_contrasena"].encode("ascii") if fila else HASH_FICTICIO
    coincide = bcrypt.checkpw(clave[:MAX_BYTES_BCRYPT], hash_guardado)

    if fila is None or demasiado_larga or not coincide or not fila["activo"]:
        return None
    return UsuarioSesion(fila)


def registrar_inicio_sesion(usuario_id, ip):
    """RN-14: guarda el último acceso y anota el inicio de sesión en la bitácora.

    Las dos sentencias van en UNA transacción: o quedan las dos o ninguna.
    """
    with bd.transaccion() as cur:
        cur.execute("UPDATE usuario SET ultimo_acceso = NOW() WHERE id = %s", (usuario_id,))
        cur.execute(
            """
            INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
            VALUES (%s, 'inicio_sesion', 'usuario', %s, %s, %s)
            """,
            (usuario_id, usuario_id, json.dumps({"resultado": "ok"}), ip),
        )


# --- Administración de usuarios (solo admin, F5) ---------------------------------------------

PATRON_NOMBRE_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")
PATRON_CORREO = cuenta.PATRON_CORREO
LARGO_CONTRASENA = cuenta.LARGO_MINIMO      # mínimo; el máximo son 72 bytes (bcrypt)


def listar(actor):
    exigir_rol(actor, "admin")
    # Devuelve el personal con su rol, la comunidad (de los guías), la licencia (de los
    # capitanes), si está activo y su último acceso. LEFT JOIN: no todos tienen comunidad.
    return bd.consultar(
        """
        SELECT u.id, u.nombre_usuario, u.nombre_completo, u.correo, u.telefono,
               u.licencia_navegacion, u.activo, u.ultimo_acceso,
               r.codigo AS rol, r.nombre AS rol_nombre, c.nombre AS comunidad
        FROM usuario u
        JOIN rol r            ON r.id = u.rol_id
        LEFT JOIN comunidad c ON c.id = u.comunidad_id
        ORDER BY u.activo DESC, r.id, u.nombre_completo
        """
    )


def roles():
    # Devuelve los 4 roles (fijos: el CHECK de la tabla no deja crear otros) con cuántos
    # usuarios activos tiene cada uno.
    return bd.consultar(
        """
        SELECT r.id, r.codigo, r.nombre, r.descripcion, COUNT(u.id) AS usuarios
        FROM rol r
        LEFT JOIN usuario u ON u.rol_id = r.id AND u.activo = 1
        GROUP BY r.id, r.codigo, r.nombre, r.descripcion
        ORDER BY r.id
        """
    )


def buscar_para_editar(actor, usuario_id):
    exigir_rol(actor, "admin")
    # Devuelve un usuario para editarlo (sin el hash de la contraseña).
    return bd.consultar_uno(
        """
        SELECT id, rol_id, nombre_usuario, nombre_completo, correo, telefono, comunidad_id,
               licencia_navegacion, activo
        FROM usuario
        WHERE id = %s
        """,
        (usuario_id,),
    )


def _salidas_asignadas(cur, usuario_id):
    # Devuelve cuántas salidas por venir tiene la persona como capitán o como guía.
    cur.execute(
        """
        SELECT COUNT(*) AS salidas
        FROM salida
        WHERE (capitan_id = %s OR guia_id = %s)
          AND estado IN ('programada','embarcando','suspendida')
          AND fecha_hora_zarpe > NOW()
        """,
        (usuario_id, usuario_id),
    )
    return cur.fetchone()["salidas"]


def guardar(actor, usuario_id, datos, ip=None):
    """Crea o edita un usuario del personal. La contraseña solo se cambia si se escribe una."""
    exigir_rol(actor, "admin")
    e = {}
    nombre_usuario = (datos.get("nombre_usuario") or "").strip().lower()
    if not PATRON_NOMBRE_USUARIO.match(nombre_usuario):
        e["nombre_usuario"] = "De 3 a 30 minúsculas, números, puntos, guiones (ej. guia.rosa)."
    nombre_completo = v.texto(datos, "nombre_completo", e, 3, 120, nombre="el nombre completo")
    correo = (datos.get("correo") or "").strip().lower() or None
    if correo and (len(correo) > 120 or not PATRON_CORREO.match(correo)):
        e["correo"] = "Escribe un correo válido."
    telefono = v.telefono(datos, "telefono", e)
    rol_id = v.entero(datos, "rol_id", e, 1, 4294967295)
    activo = v.booleano(datos, "activo")
    contrasena = datos.get("contrasena") or ""
    if contrasena or not usuario_id:
        # D-113: la misma regla que en Mi cuenta y en la recuperación
        error = cuenta.error_contrasena(contrasena, nombre_usuario)
        if error:
            e["contrasena"] = error
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve el código del rol elegido.
        cur.execute("SELECT codigo FROM rol WHERE id = %s", (rol_id,))
        fila = cur.fetchone()
        rol = fila["codigo"] if fila else None
        if rol is None:
            e["rol_id"] = "Elige un rol."
        comunidad_id, licencia = None, None
        if rol == "guia":          # el guía pertenece a una comunidad (sección 6)
            comunidad_id = v.entero(datos, "comunidad_id", e, 1, 4294967295)
            # Devuelve 1 si la comunidad existe y está activa.
            cur.execute("SELECT COUNT(*) AS hay FROM comunidad WHERE id = %s AND activa = 1",
                        (comunidad_id,))
            if "comunidad_id" not in e and not cur.fetchone()["hay"]:
                e["comunidad_id"] = "El guía necesita una comunidad activa."
        if rol == "capitan":       # el capitán necesita licencia de navegación (sección 6)
            licencia = v.texto(datos, "licencia_navegacion", e, 3, 30,
                               nombre="la licencia de navegación")
        if usuario_id:
            # Devuelve el usuario y su rol actual, BLOQUEADO hasta el COMMIT.
            cur.execute(
                """
                SELECT u.activo, r.codigo AS rol
                FROM usuario u
                JOIN rol r ON r.id = u.rol_id
                WHERE u.id = %s
                FOR UPDATE
                """,
                (usuario_id,),
            )
            actual = cur.fetchone()
            if usuario_id == actor.id:             # nadie se deja a sí mismo afuera
                if not activo:
                    e["activo"] = "No puedes desactivar tu propio usuario."
                if rol != "admin":
                    e["rol_id"] = "No puedes quitarte el rol de admin."
            if actual and actual["rol"] in ("capitan", "guia") and (rol != actual["rol"]
                                                                   or not activo):
                salidas = _salidas_asignadas(cur, usuario_id)
                if salidas:
                    e["rol_id" if rol != actual["rol"] else "activo"] = (
                        f"Tiene {salidas} salida(s) por venir asignada(s): cámbialas primero.")
        if e:
            raise ErrorValidacion(e)

        valores = (rol_id, nombre_usuario, nombre_completo, correo, telefono, comunidad_id,
                   licencia, activo)
        hash_nuevo = cuenta.hash_de(contrasena) if contrasena else None
        nuevo_id = catalogo.escribir(
            cur, actor, ip, "usuario", usuario_id,
            insertar=("""
                INSERT INTO usuario (rol_id, nombre_usuario, nombre_completo, correo, telefono,
                                     comunidad_id, licencia_navegacion, activo, hash_contrasena)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (*valores, hash_nuevo)),
            actualizar=("""
                UPDATE usuario
                SET rol_id = %s, nombre_usuario = %s, nombre_completo = %s, correo = %s,
                    telefono = %s, comunidad_id = %s, licencia_navegacion = %s, activo = %s
                WHERE id = %s
                """, (*valores, usuario_id)),
            duplicados={"uk_usuario_nombre": ("nombre_usuario", "Ese nombre de usuario ya existe."),
                        "uk_usuario_correo": ("correo", "Ese correo ya es de otro usuario.")},
            # Nunca la contraseña ni su hash: solo si se cambió.
            resumen={"nombre_usuario": nombre_usuario, "rol": rol, "activo": activo,
                     "contrasena_cambiada": bool(contrasena)},
        )
        if usuario_id and hash_nuevo:
            cur.execute("UPDATE usuario SET hash_contrasena = %s WHERE id = %s",
                        (hash_nuevo, usuario_id))
    return nuevo_id


def cambiar_activo(actor, usuario_id, activo, ip):
    """Activa o desactiva una cuenta desde la lista de usuarios (un clic, D-114).

    Las mismas reglas que al editar: nadie se desactiva a sí mismo y un guía o capitán con
    salidas por venir no se desactiva hasta reasignarlas. Desactivada, pierde la sesión en su
    siguiente clic (buscar_por_id solo carga cuentas activas).
    """
    exigir_rol(actor, "admin")
    activo = 1 if activo else 0
    if usuario_id == actor.id and not activo:
        raise ErrorNegocio("No puedes desactivar tu propio usuario.")
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve el usuario y su rol, BLOQUEADO hasta el COMMIT.
        cur.execute(
            """
            SELECT u.id, u.nombre_usuario, u.activo, r.codigo AS rol
            FROM usuario u
            JOIN rol r ON r.id = u.rol_id
            WHERE u.id = %s
            FOR UPDATE
            """,
            (usuario_id,),
        )
        fila = cur.fetchone()
        if fila is None:
            raise ErrorNegocio("Ese usuario no existe.")
        if fila["activo"] == activo:
            return fila["nombre_usuario"]
        if not activo and fila["rol"] in ("capitan", "guia"):
            salidas = _salidas_asignadas(cur, usuario_id)
            if salidas:
                raise ErrorNegocio(f"{fila['nombre_usuario']} tiene {salidas} salida(s) por venir "
                                   "asignada(s): cámbialas primero.")
        cur.execute("UPDATE usuario SET activo = %s WHERE id = %s", (activo, usuario_id))
        bitacora.anotar(cur, actor.id, "usuario_activado" if activo else "usuario_desactivado",
                        "usuario", usuario_id, {"nombre_usuario": fila["nombre_usuario"]}, ip)
    return fila["nombre_usuario"]


# --- Desde la consola del servidor (flask usuarios ...) ---------------------------------------

def para_consola():
    # Devuelve el personal con su rol, si está activo y su correo (flask usuarios listar).
    return bd.consultar(
        """
        SELECT u.nombre_usuario, r.codigo AS rol, u.activo, u.correo
        FROM usuario u
        JOIN rol r ON r.id = u.rol_id
        ORDER BY r.id, u.nombre_usuario
        """
    )


def cambiar_clave_desde_consola(nombre_usuario, contrasena):
    """D-111: el encargado del servidor pone una contraseña nueva sin entrar al panel (por
    ejemplo, si el admin olvidó la suya y no tiene correo). Devuelve si la cuenta está activa."""
    nombre_usuario = (nombre_usuario or "").strip().lower()
    error = cuenta.error_contrasena(contrasena, nombre_usuario)
    if error:
        raise ErrorNegocio(f"No se cambió nada: {error}")
    with bd.transaccion() as cur:
        # Devuelve la cuenta, BLOQUEADA hasta el COMMIT.
        cur.execute("SELECT id, activo FROM usuario WHERE nombre_usuario = %s FOR UPDATE",
                    (nombre_usuario,))
        fila = cur.fetchone()
        if fila is None:
            raise ErrorNegocio(f"No existe el usuario «{nombre_usuario}». "
                               "Mira la lista con:  flask usuarios listar")
        cur.execute("UPDATE usuario SET hash_contrasena = %s WHERE id = %s",
                    (cuenta.hash_de(contrasena), fila["id"]))
        bitacora.anotar(cur, fila["id"], "contrasena_restablecida", "usuario", fila["id"],
                        {"con": "consola del servidor"}, "consola")
    return bool(fila["activo"])
