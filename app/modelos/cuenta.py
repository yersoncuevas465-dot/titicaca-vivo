"""La cuenta de cada persona del personal: contraseña segura, recuperarla con un código,
«Mi cuenta» y los eventos de sesión que quedan en la bitácora (D-110 a D-113 y D-115).

- error_contrasena: la regla de una contraseña nueva (alta del admin, Mi cuenta y recuperación).
- sello: la sesión vale solo con la contraseña con la que se abrió. Si alguien la cambia,
  las demás sesiones de esa cuenta se cierran solas (seguridad.cargar_usuario).
- pedir_codigo / restablecer_con_codigo: «¿Olvidaste tu contraseña?» en 2 pasos.
- mis_datos, cambiar_contrasena, actualizar_contacto, ultimos_movimientos: «Mi cuenta».
- anotar_evento: inicio y cierre de sesión, intentos fallidos y recuperaciones (RN-14).
"""

import hashlib
import hmac
import json
import re
import secrets
import time

import bcrypt
import pymysql
from flask import current_app

from app import bd
from app.modelos import ERROR_DUPLICADO, ROLES_PERSONAL, ErrorNegocio, ErrorValidacion, exigir_rol
from app.modelos import validacion as v
from app.modelos.validacion import indice_duplicado
from app.servicios import correo

LARGO_MINIMO = 10
MAX_BYTES_BCRYPT = 72          # bcrypt 5 da error con contraseñas más largas
PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_CODIGO = re.compile(r"^\d{6}$")
CODIGO_INCORRECTO = "El código no es correcto."
# Lo que «Mi cuenta» muestra como «tus últimos movimientos»
ACCIONES_DE_CUENTA = ("inicio_sesion", "cierre_sesion", "intento_fallido",
                      "recuperacion_solicitada", "contrasena_restablecida", "contrasena_cambiada",
                      "contacto_actualizado")


class CodigoVencido(ErrorNegocio):
    """El código de recuperación ya no sirve (pasó su tiempo o se pidió en otro navegador)."""


# --- Regla de la contraseña -------------------------------------------------------------------

def error_contrasena(clave, nombre_usuario=None):
    """Devuelve el problema de una contraseña nueva, o None si sirve."""
    if not clave:
        return "Escribe la contraseña."
    if len(clave) < LARGO_MINIMO:
        return f"Al menos {LARGO_MINIMO} caracteres (tiene {len(clave)})."
    if len(clave.encode("utf-8")) > MAX_BYTES_BCRYPT:
        return f"Máximo {MAX_BYTES_BCRYPT} bytes."
    if any(c.isspace() for c in clave):
        return "Sin espacios."
    if not (any(c.isalpha() for c in clave) and any(c.isdigit() for c in clave)):
        return "Combina letras y números (por ejemplo, Totora-2026)."
    if len(set(clave.lower())) < 5:
        return "Es muy fácil de adivinar: usa caracteres distintos."
    if nombre_usuario and len(nombre_usuario) >= 3 and nombre_usuario.lower() in clave.lower():
        return "No puede contener tu nombre de usuario."
    return None


def hash_de(clave):
    return bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def coincide(clave, hash_guardado):
    datos = (clave or "").encode("utf-8")
    if len(datos) > MAX_BYTES_BCRYPT:
        return False
    return bcrypt.checkpw(datos, hash_guardado.encode("ascii"))


def sello(hash_contrasena):
    """16 caracteres que cambian cuando cambia la contraseña (HMAC con la SECRET_KEY).

    Va en la cookie de sesión junto al id: no deja ver el hash ni adivinarlo."""
    clave = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(clave, hash_contrasena.encode("ascii"), hashlib.sha256).hexdigest()[:16]


# --- Bitácora de la cuenta (RN-14) ------------------------------------------------------------

def anotar_evento(usuario_id, accion, detalle, ip):
    """Anota en la bitácora un evento de la cuenta, en su propia transacción."""
    with bd.transaccion() as cur:
        cur.execute(
            """
            INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
            VALUES (%s, %s, 'usuario', %s, %s, %s)
            """,
            (usuario_id, accion, usuario_id, json.dumps(detalle, default=str), ip),
        )


def anotar_evento_sin_fallar(usuario_id, accion, detalle, ip):
    """Igual que anotar_evento, pero si la base no responde solo lo deja en el registro:
    cerrar la sesión no puede fallar porque la bitácora no se pudo escribir."""
    try:
        anotar_evento(usuario_id, accion, detalle, ip)
    except pymysql.MySQLError as error:
        current_app.logger.warning("No se pudo anotar %s de usuario %s: %r",
                                   accion, usuario_id, error)


def nombre_por_correo(correo_escrito):
    # Devuelve el nombre de usuario dueño de ese correo (para entrar con el correo).
    fila = bd.consultar_uno("SELECT nombre_usuario FROM usuario WHERE correo = %s",
                            ((correo_escrito or "").strip().lower(),))
    return fila["nombre_usuario"] if fila else None


def intento_fallido(identificador, ip):
    """Un ingreso fallido queda en la bitácora con la cuenta, si existe.

    Nunca se guarda lo que se escribió: podría ser una contraseña puesta en el campo equivocado."""
    nombre = (identificador or "").strip().lower()
    # Devuelve el id de la cuenta con ese usuario o ese correo, si existe.
    fila = bd.consultar_uno(
        "SELECT id FROM usuario WHERE nombre_usuario = %s OR correo = %s", (nombre, nombre))
    anotar_evento(fila["id"] if fila else None, "intento_fallido",
                  {"cuenta": "existe" if fila else "no encontrada"}, ip)


# --- «¿Olvidaste tu contraseña?» (D-111) ------------------------------------------------------

def firma_codigo(usuario_id, codigo, vence, hash_contrasena):
    """HMAC del código: lo que se guarda en la sesión del navegador (el código, en ninguna parte).

    Depende del hash actual: apenas cambia la contraseña, el código deja de servir."""
    clave = current_app.config["SECRET_KEY"].encode("utf-8")
    mensaje = f"{usuario_id}:{codigo}:{vence}:{hash_contrasena}".encode()
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


def buscar_para_recuperar(identificador):
    # Devuelve la cuenta ACTIVA con ese nombre de usuario o ese correo, con su hash.
    return bd.consultar_uno(
        """
        SELECT id, nombre_usuario, nombre_completo, correo, hash_contrasena
        FROM usuario
        WHERE activo = 1 AND (nombre_usuario = %s OR correo = %s)
        """,
        (identificador, identificador),
    )


def _texto_del_correo(nombre, codigo, minutos):
    return (f"Hola, {nombre}:\n\n"
            f"Tu código para cambiar la contraseña de Titicaca Vivo es: {codigo}\n\n"
            f"Vence en {minutos} minutos y sirve una sola vez. Si no lo pediste, ignora este "
            "correo: tu contraseña no cambia.\n\n"
            "Titicaca Vivo · Giant Trip Travel Agency · Puno")


def pedir_codigo(identificador, ip):
    """Paso 1: si hay una cuenta activa con correo, le envía un código de 6 dígitos.

    Devuelve lo que se guarda en la sesión del navegador: {uid, vence, firma, intentos}.
    Si la cuenta no existe o no tiene correo, devuelve lo mismo con uid None: la página
    dice siempre lo mismo y no delata qué cuentas hay.
    """
    minutos = current_app.config["MINUTOS_CODIGO_RECUPERACION"]
    vence = int(time.time()) + minutos * 60
    pedido = {"uid": None, "vence": vence, "firma": "", "intentos": 0}
    identificador = (identificador or "").strip().lower()
    fila = buscar_para_recuperar(identificador) if identificador else None
    if fila is None:
        anotar_evento(None, "recuperacion_solicitada", {"cuenta": "no encontrada"}, ip)
        return pedido
    if not fila["correo"]:
        anotar_evento(fila["id"], "recuperacion_solicitada", {"envio": "sin correo"}, ip)
        current_app.logger.warning("Recuperación: %s no tiene correo registrado.",
                                   fila["nombre_usuario"])
        if current_app.config["CORREO_SIMULAR"]:
            print(f"\n  [RECUPERACIÓN] {fila['nombre_usuario']} no tiene correo registrado: no se "
                  "envió ningún código.\n  El admin puede cambiarle la contraseña en Usuarios.\n",
                  flush=True)
        return pedido

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    resultado = correo.enviar(fila["correo"], "Titicaca Vivo · Código para cambiar tu contraseña",
                              _texto_del_correo(fila["nombre_completo"], codigo, minutos))
    if resultado == correo.FALLO:
        # Sin internet o con la clave SMTP mal escrita: para no dejar a la persona sin salida,
        # el código queda en la ventana del servidor (nunca en logs/app.log).
        print(f"\n  [RECUPERACIÓN] No se pudo enviar el correo. Código para "
              f"{fila['nombre_usuario']}: {codigo} (vence en {minutos} min)\n", flush=True)
    anotar_evento(fila["id"], "recuperacion_solicitada", {"envio": resultado}, ip)
    return {**pedido, "uid": fila["id"],
            "firma": firma_codigo(fila["id"], codigo, vence, fila["hash_contrasena"])}


def restablecer_con_codigo(pedido, codigo, nueva, repetida, ip):
    """Paso 2: con el código correcto, cambia la contraseña. Devuelve el nombre de usuario.

    Errores: CodigoVencido (hay que pedir otro) o ErrorValidacion junto a cada campo. Si el
    único error es una contraseña floja, el código sigue sirviendo: no gasta un intento.
    """
    if not pedido or time.time() > pedido.get("vence", 0):
        raise CodigoVencido("El código venció o no es de este navegador. Pide uno nuevo.")
    e = {}
    codigo = (codigo or "").strip()
    if not PATRON_CODIGO.match(codigo):
        e["codigo"] = "El código tiene 6 números: cópialo del correo."
    if nueva != repetida:
        e["repetir"] = "No coincide con la contraseña nueva."
    if e:
        raise ErrorValidacion(e)

    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la cuenta y su hash, BLOQUEADA hasta el COMMIT: si llegan dos pedidos con
        # el mismo código, el segundo ya ve el hash nuevo y el código no le sirve (una sola vez).
        cur.execute(
            """
            SELECT id, nombre_usuario, hash_contrasena
            FROM usuario
            WHERE id = %s AND activo = 1
            FOR UPDATE
            """,
            (pedido.get("uid") or 0,),
        )
        fila = cur.fetchone()
        esperada = (firma_codigo(fila["id"], codigo, pedido["vence"], fila["hash_contrasena"])
                    if fila else "")
        if not fila or not hmac.compare_digest(esperada, pedido.get("firma") or "-"):
            raise ErrorValidacion({"codigo": CODIGO_INCORRECTO})
        error = error_contrasena(nueva, fila["nombre_usuario"])
        if error:
            raise ErrorValidacion({"contrasena": error})
        cur.execute("UPDATE usuario SET hash_contrasena = %s WHERE id = %s",
                    (hash_de(nueva), fila["id"]))
        cur.execute(
            """
            INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
            VALUES (%s, 'contrasena_restablecida', 'usuario', %s, %s, %s)
            """,
            (fila["id"], fila["id"], json.dumps({"con": "código por correo"}), ip),
        )
    return fila["nombre_usuario"]


# --- «Mi cuenta» --------------------------------------------------------------------------------

def mis_datos(actor):
    exigir_rol(actor, *ROLES_PERSONAL)
    # Devuelve los datos de la propia cuenta con su rol y su comunidad (LEFT JOIN: no todos tienen).
    return bd.consultar_uno(
        """
        SELECT u.nombre_usuario, u.nombre_completo, u.correo, u.telefono, u.licencia_navegacion,
               u.ultimo_acceso, u.creado_en, r.codigo AS rol, r.nombre AS rol_nombre,
               c.nombre AS comunidad
        FROM usuario u
        JOIN rol r            ON r.id = u.rol_id
        LEFT JOIN comunidad c ON c.id = u.comunidad_id
        WHERE u.id = %s
        """,
        (actor.id,),
    )


def ultimos_movimientos(actor, cantidad=8):
    exigir_rol(actor, *ROLES_PERSONAL)
    marcas = ", ".join(["%s"] * len(ACCIONES_DE_CUENTA))
    # Devuelve los últimos ingresos, salidas y cambios de la propia cuenta (índice por usuario).
    filas = bd.consultar(
        f"""
        SELECT accion, detalle, ip, creado_en
        FROM bitacora
        WHERE usuario_id = %s AND accion IN ({marcas})
        ORDER BY id DESC
        LIMIT %s
        """,  # noqa: S608 (solo marcas %s armadas aquí; los valores van como parámetros)
        (actor.id, *ACCIONES_DE_CUENTA, cantidad),
    )
    for fila in filas:
        fila["detalle"] = json.loads(fila["detalle"]) if fila["detalle"] else {}
    return filas


def _cuenta_bloqueada(cur, usuario_id):
    # Devuelve la cuenta con su hash, BLOQUEADA hasta el COMMIT (nadie la cambia a la vez).
    cur.execute(
        """
        SELECT id, nombre_usuario, correo, telefono, hash_contrasena
        FROM usuario
        WHERE id = %s AND activo = 1
        FOR UPDATE
        """,
        (usuario_id,),
    )
    fila = cur.fetchone()
    if fila is None:
        raise ErrorNegocio("Tu cuenta ya no está activa.")
    return fila


def cambiar_contrasena(actor, actual, nueva, repetida, ip):
    """Cambia la propia contraseña (pide la actual). Las demás sesiones de la cuenta se cierran."""
    exigir_rol(actor, *ROLES_PERSONAL)
    e = {}
    error = error_contrasena(nueva, actor.nombre_usuario)
    if error:
        e["nueva"] = error
    elif nueva == actual:
        e["nueva"] = "Tiene que ser distinta de la actual."
    if nueva != repetida:
        e["repetir"] = "No coincide con la contraseña nueva."
    with bd.transaccion(lectura_actual=True) as cur:
        fila = _cuenta_bloqueada(cur, actor.id)
        if not coincide(actual, fila["hash_contrasena"]):
            e["actual"] = "No es tu contraseña actual."
        if e:
            raise ErrorValidacion(e)
        cur.execute("UPDATE usuario SET hash_contrasena = %s WHERE id = %s",
                    (hash_de(nueva), actor.id))
        cur.execute(
            """
            INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
            VALUES (%s, 'contrasena_cambiada', 'usuario', %s, %s, %s)
            """,
            (actor.id, actor.id, json.dumps({"desde": "Mi cuenta"}), ip),
        )


def actualizar_contacto(actor, datos, ip):
    """Cambia el propio correo (el de la recuperación) y el teléfono. Pide la contraseña actual."""
    exigir_rol(actor, *ROLES_PERSONAL)
    e = {}
    correo_nuevo = (datos.get("correo") or "").strip().lower() or None
    if correo_nuevo and (len(correo_nuevo) > 120 or not PATRON_CORREO.match(correo_nuevo)):
        e["correo"] = "Escribe un correo válido."
    telefono = v.telefono(datos, "telefono", e)
    with bd.transaccion(lectura_actual=True) as cur:
        fila = _cuenta_bloqueada(cur, actor.id)
        if not coincide(datos.get("confirmar") or "", fila["hash_contrasena"]):
            e["confirmar"] = "No es tu contraseña actual."
        if e:
            raise ErrorValidacion(e)
        try:
            cur.execute("UPDATE usuario SET correo = %s, telefono = %s WHERE id = %s",
                        (correo_nuevo, telefono, actor.id))
        except pymysql.err.IntegrityError as error:
            if error.args[0] == ERROR_DUPLICADO and indice_duplicado(error) == "uk_usuario_correo":
                raise ErrorValidacion({"correo": "Ese correo ya es de otra cuenta."}) from error
            raise
        cambios = {"correo": fila["correo"] != correo_nuevo,
                   "telefono": fila["telefono"] != telefono}
        cur.execute(
            """
            INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
            VALUES (%s, 'contacto_actualizado', 'usuario', %s, %s, %s)
            """,
            (actor.id, actor.id, json.dumps(cambios), ip),
        )
