"""Seguridad transversal: sesiones (Flask-Login), CSRF, límite de intentos,
permisos por rol y cabeceras HTTP (sección 11 del enunciado).

Además (D-110 a D-112): la sesión se cierra sola tras SESION_INACTIVA_MIN minutos sin
actividad, vale solo con la contraseña con la que se abrió y ninguna página vista con la
sesión abierta se guarda en la caché del navegador.
"""

import hmac
import time
from functools import wraps
from urllib.parse import urlsplit

from flask import Response, abort, current_app, flash, g, redirect, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user, logout_user
from flask_wtf.csrf import CSRFProtect

from app.modelos import ROLES_PERSONAL

gestor_sesiones = LoginManager()
proteccion_csrf = CSRFProtect()
limitador = Limiter(get_remote_address, storage_uri="memory://")

# CSP: solo recursos propios. Sin CDN, sin scripts ni estilos en línea.
POLITICA_CONTENIDO = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)


def init_app(app):
    gestor_sesiones.init_app(app)
    gestor_sesiones.login_view = "autenticacion.entrar"
    gestor_sesiones.login_message = "Inicia sesión para entrar al panel."
    gestor_sesiones.login_message_category = "info"
    # "basic" y no "strong": en el lago el celular cambia de IP (3G/4G) y "strong"
    # cerraría la sesión del guía a cada rato.
    gestor_sesiones.session_protection = "basic"

    proteccion_csrf.init_app(app)
    limitador.init_app(app)
    app.before_request(revisar_inactividad)
    app.after_request(agregar_cabeceras)


@gestor_sesiones.user_loader
def cargar_usuario(id_de_sesion):
    from app.modelos import usuario  # import tardío: evita importaciones circulares

    # D-112: la cookie guarda "id.sello". Si la contraseña cambió (la cambió la persona, el
    # admin o la recuperación), el sello ya no coincide y esta sesión deja de valer.
    usuario_id, _, sello = str(id_de_sesion).partition(".")
    if not usuario_id.isdigit():
        return None
    encontrado = usuario.buscar_por_id(int(usuario_id))
    if encontrado is None or not hmac.compare_digest(encontrado.sello, sello):
        return None
    return encontrado


def id_de_la_sesion():
    """El id de la cuenta de esta sesión, sin ir a la base (None si no hay sesión)."""
    usuario_id = str(session.get("_user_id", "")).partition(".")[0]
    return int(usuario_id) if usuario_id.isdigit() else None


def revisar_inactividad():
    """D-110: tras SESION_INACTIVA_MIN minutos sin ningún clic, la sesión se cierra sola.

    Así un celular o una PC del muelle que queda sola no deja a la vista los datos de los
    pasajeros. La hora del último clic va en la sesión (no se consulta la base).
    """
    if request.endpoint in (None, "static") or "_user_id" not in session:
        return None
    ahora = int(time.time())
    ultima = session.get("ultima_actividad")
    minutos = current_app.config["SESION_INACTIVA_MIN"]
    if ultima is not None and ahora - ultima > minutos * 60:
        from app.modelos import cuenta

        usuario_id = id_de_la_sesion()
        logout_user()
        session.clear()
        cuenta.anotar_evento_sin_fallar(usuario_id, "cierre_sesion",
                                        {"motivo": "inactividad", "minutos": minutos}, ip_cliente())
        if request.endpoint == "panel.sesion_activa":
            return Response(status=401)
        flash(f"Tu sesión se cerró porque pasaron {minutos} minutos sin actividad. "
              "Vuelve a entrar.", "info")
        volver = None
        if request.method == "GET" and request.blueprint in ("panel", "catalogos"):
            volver = request.full_path.rstrip("?")
        return redirect(url_for("autenticacion.entrar", next=volver))
    if ultima is None or ahora - ultima >= 30:       # se anota cada 30 s como mucho
        session["ultima_actividad"] = ahora
    return None


def requiere_rol(*roles):
    """Decorador de ruta: sin sesión → a /entrar; con sesión pero sin el rol → 403.

    El modelo vuelve a revisar el rol (modelos.exigir_rol): doble verificación.
    """
    for rol in roles:
        if rol not in ROLES_PERSONAL:
            raise ValueError(f"Rol desconocido en @requiere_rol: {rol}")

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                return gestor_sesiones.unauthorized()
            if current_user.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def sin_cache(vista):
    """Marca la respuesta con Cache-Control: no-store (páginas con datos personales)."""

    @wraps(vista)
    def envoltura(*args, **kwargs):
        g.sin_cache = True
        return vista(*args, **kwargs)

    return envoltura


def agregar_cabeceras(respuesta):
    respuesta.headers["Content-Security-Policy"] = POLITICA_CONTENIDO
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    respuesta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # D-112: con la sesión abierta nada se guarda en la caché: tras «Salir», el botón «Atrás»
    # no vuelve a mostrar datos. g._login_user existe solo si la página ya leyó la sesión
    # (así un archivo estático no consulta la base).
    usuario = g.get("_login_user")
    if g.get("sin_cache") or (usuario is not None and usuario.is_authenticated):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def destino_seguro(url):
    """Devuelve `url` solo si es una ruta interna (/panel/...). Evita redirecciones abiertas."""
    if not url:
        return None
    partes = urlsplit(url)
    if partes.scheme or partes.netloc or not url.startswith("/") or url.startswith("//"):
        return None
    if "\\" in url:
        return None
    return url


def ip_cliente():
    """IP del cliente: la dirección de la conexión. Detrás de un proxy HTTPS, waitress la toma
    de X-Forwarded-For solo si se arrancó con --trusted-proxy (docs/fase-8-entrega.md)."""
    return request.remote_addr
