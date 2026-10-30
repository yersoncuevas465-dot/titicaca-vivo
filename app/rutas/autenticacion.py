"""Cuenta del personal: GET/POST /entrar, POST /salir y «¿Olvidaste tu contraseña?»
(/recuperar y /recuperar/codigo, D-111). Ningún SQL aquí: todo está en los modelos."""

import time

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_user, logout_user

from app.formularios import poner_errores
from app.formularios.autenticacion import (
    FormularioCodigo,
    FormularioEntrar,
    FormularioPedirCodigo,
)
from app.modelos import ErrorValidacion, cuenta
from app.modelos import usuario as modelo_usuario
from app.seguridad import destino_seguro, id_de_la_sesion, ip_cliente, limitador, sin_cache

bp = Blueprint("autenticacion", __name__)

MENSAJE_GENERICO = "Usuario o contraseña incorrectos."
MAX_INTENTOS_CODIGO = 5          # códigos equivocados por pedido; después hay que pedir otro


def _solo_si_fallo(respuesta):
    # Solo cuentan para el límite los intentos que NO terminan en redirección (los fallidos).
    return respuesta.status_code != 302


def _aviso_de_intentos():
    """« Te quedan N intentos…» cuando quedan 2 o menos antes del bloqueo de 15 minutos."""
    limite = limitador.current_limit
    if limite is None:
        return ""
    restantes = max(0, limite.remaining - 1)     # este intento fallido se descuenta al responder
    if restantes > 2:
        return ""
    if restantes == 0:
        return " Se bloquearon los ingresos desde este equipo por 15 minutos."
    if restantes == 1:
        return " Te queda 1 intento antes de un bloqueo de 15 minutos."
    return f" Te quedan {restantes} intentos antes de un bloqueo de 15 minutos."


def _modo_demostracion():
    """El aviso «el código sale en la ventana del servidor»: solo con el correo simulado y
    fuera de producción."""
    config = current_app.config
    return config["CORREO_SIMULAR"] and config["ENTORNO"] != "produccion"


@bp.route("/entrar", methods=["GET", "POST"])
@limitador.limit(lambda: current_app.config["LIMITE_INTENTOS_ENTRAR"],
                 methods=["POST"], deduct_when=_solo_si_fallo)
@sin_cache
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for("panel.inicio"))

    formulario = FormularioEntrar()
    error_general = None
    codigo = 200

    if formulario.is_submitted():
        if not formulario.validate():
            codigo = 422            # faltan datos: los errores salen junto a cada campo
        else:
            identificador = formulario.nombre_usuario.data
            nombre = identificador
            if "@" in identificador:                       # también se entra con el correo
                nombre = cuenta.nombre_por_correo(identificador) or ""
            usuario = modelo_usuario.verificar_credenciales(nombre, formulario.contrasena.data)
            if usuario is None:
                cuenta.intento_fallido(identificador, ip_cliente())
                error_general = MENSAJE_GENERICO + _aviso_de_intentos()   # nunca qué parte falló
                codigo = 401
            else:
                destino = destino_seguro(request.args.get("next")) or url_for("panel.inicio")
                session.clear()                            # sesión nueva al entrar
                login_user(usuario)
                session["ultima_actividad"] = int(time.time())
                modelo_usuario.registrar_inicio_sesion(usuario.id, ip_cliente())
                current_app.logger.info("Inicio de sesión: %s desde %s",
                                        usuario.nombre_usuario, ip_cliente())
                flash(f"Hola, {usuario.nombre_completo}.", "exito")
                return redirect(destino)

    return render_template("autenticacion/entrar.html", formulario=formulario,
                           error_general=error_general,
                           minutos=current_app.config["SESION_INACTIVA_MIN"]), codigo


@bp.route("/salir", methods=["POST"])
def salir():
    usuario_id = id_de_la_sesion()
    logout_user()
    session.clear()
    if usuario_id is not None:
        cuenta.anotar_evento_sin_fallar(usuario_id, "cierre_sesion", {"motivo": "salir"},
                                        ip_cliente())
    flash("Cerraste tu sesión.", "info")
    return redirect(url_for("publico.inicio"))


# --- «¿Olvidaste tu contraseña?» en 2 pasos (D-111) --------------------------------------------

@bp.route("/recuperar", methods=["GET", "POST"])
@limitador.limit(lambda: current_app.config["LIMITE_PEDIR_CODIGO"], methods=["POST"])
@sin_cache
def recuperar():
    """Paso 1: usuario o correo → un código de 6 dígitos al correo de la cuenta."""
    if current_user.is_authenticated:
        return redirect(url_for("panel.mi_cuenta"))
    formulario = FormularioPedirCodigo()
    if formulario.validate_on_submit():
        session["recuperacion"] = cuenta.pedir_codigo(formulario.identificador.data, ip_cliente())
        # El mismo mensaje exista o no la cuenta: así nadie averigua qué cuentas hay.
        flash("Si los datos son de una cuenta activa con correo, te enviamos un código de "
              "6 dígitos. Revisa tu correo (también la carpeta de spam).", "info")
        return redirect(url_for("autenticacion.recuperar_codigo"), code=303)
    codigo = 422 if formulario.is_submitted() else 200
    return render_template("autenticacion/recuperar.html", formulario=formulario,
                           demostracion=_modo_demostracion()), codigo


@bp.route("/recuperar/codigo", methods=["GET", "POST"])
@limitador.limit(lambda: current_app.config["LIMITE_INTENTOS_CODIGO"], methods=["POST"],
                 deduct_when=lambda _respuesta: g.get("codigo_equivocado", False))
@sin_cache
def recuperar_codigo():
    """Paso 2: el código y la contraseña nueva. Sirve una sola vez y vence a los 15 minutos."""
    if current_user.is_authenticated:
        return redirect(url_for("panel.mi_cuenta"))
    pedido = session.get("recuperacion")
    if not pedido:
        flash("Primero escribe tu usuario o tu correo para recibir un código.", "info")
        return redirect(url_for("autenticacion.recuperar"))

    formulario = FormularioCodigo()
    codigo_http = 200
    if formulario.is_submitted():
        codigo_http = 422
        if pedido.get("intentos", 0) >= MAX_INTENTOS_CODIGO:
            session.pop("recuperacion", None)
            flash("Escribiste mal el código demasiadas veces. Pide uno nuevo.", "error")
            return redirect(url_for("autenticacion.recuperar"), code=303)
        if formulario.validate():
            try:
                nombre = cuenta.restablecer_con_codigo(
                    pedido, formulario.codigo.data, formulario.contrasena.data,
                    formulario.repetir.data, ip_cliente())
            except cuenta.CodigoVencido as error:
                session.pop("recuperacion", None)
                flash(error.mensaje, "error")
                return redirect(url_for("autenticacion.recuperar"), code=303)
            except ErrorValidacion as error:
                errores = dict(error.errores)
                if errores.get("codigo") == cuenta.CODIGO_INCORRECTO:
                    pedido["intentos"] = pedido.get("intentos", 0) + 1
                    session["recuperacion"] = pedido
                    g.codigo_equivocado = True                 # cuenta para el límite por IP
                    restantes = MAX_INTENTOS_CODIGO - pedido["intentos"]
                    errores["codigo"] += (f" Te quedan {restantes} intento(s)." if restantes
                                          else " Ya no quedan intentos: pide un código nuevo.")
                poner_errores(formulario, errores)
            else:
                session.pop("recuperacion", None)
                flash(f"Listo, {nombre}: tu contraseña cambió. Ya puedes entrar con la nueva.",
                      "exito")
                return redirect(url_for("autenticacion.entrar"), code=303)

    return render_template("autenticacion/recuperar_codigo.html", formulario=formulario,
                           minutos=current_app.config["MINUTOS_CODIGO_RECUPERACION"],
                           demostracion=_modo_demostracion()), codigo_http
