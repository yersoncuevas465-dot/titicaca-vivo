"""Panel del personal.

F2: resumen del día según el rol y bitácora (solo admin).
F5: salidas (RN-07), lista de pasajeros / manifiesto PDF / WhatsApp, abordaje por QR o
manual (RN-12), pagos por verificar (RN-06) y usuarios (solo admin). Los catálogos están
en rutas/catalogos.py.

Además: Mi cuenta para todo el personal (D-113), la señal de «sigo trabajando» de la sesión
(D-110), la bitácora por periodo y en CSV (D-115) y los respaldos de la base (D-116).

Todo POST lleva CSRF y sigue el patrón POST → redirect (303) → GET. Ningún SQL aquí.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_user

from app.formularios import datos_de, poner_errores
from app.formularios.autenticacion import FormularioCambiarContrasena, FormularioContacto
from app.formularios.catalogos import FormularioUsuario
from app.formularios.panel import (
    FormularioAbordaje,
    FormularioAccion,
    FormularioBuscarReserva,
    FormularioCobro,
    FormularioMotivo,
    FormularioRechazo,
    FormularioSalida,
)
from app.modelos import ROLES_PERSONAL, ErrorNegocio, ErrorValidacion, comunidad, cuenta
from app.modelos import abordaje as modelo_abordaje
from app.modelos import bitacora as modelo_bitacora
from app.modelos import pago as modelo_pago
from app.modelos import panel as modelo_panel
from app.modelos import reclamacion as modelo_reclamacion
from app.modelos import reprogramacion as modelo_reprogramacion
from app.modelos import reserva as modelo_reserva
from app.modelos import respaldo as modelo_respaldo
from app.modelos import salida as modelo_salida
from app.modelos import usuario as modelo_usuario
from app.rutas.publico import hoy_en_lima
from app.seguridad import ip_cliente, requiere_rol
from app.servicios import clima, feriados, formato, hoja_de_calculo, pdf, whatsapp

bp = Blueprint("panel", __name__, url_prefix="/panel")

SIN_ELEGIR = (0, "— Elige —")


@bp.before_request
def todo_el_panel_sin_cache():
    # Todo el panel muestra datos personales: nada se guarda en la caché del navegador.
    g.sin_cache = True


def procesar(formulario, accion, mensaje, destino):
    """Valida el formulario y llama al modelo.

    Devuelve (respuesta, errores_sin_campo, código). Si todo salió bien, `respuesta` es la
    redirección 303 (POST → redirect → GET); si no, None y la página se vuelve a mostrar.
    """
    if not formulario.is_submitted():
        return None, [], 200
    if not formulario.validate():
        return None, [], 422
    try:
        resultado = accion()
    except ErrorValidacion as error:
        return None, poner_errores(formulario, error.errores), 422
    except ErrorNegocio as error:
        return None, [error.mensaje], 422
    flash(mensaje(resultado) if callable(mensaje) else mensaje, "exito")
    return redirect(destino(resultado) if callable(destino) else destino, code=303), [], 200


# --- Resumen y bitácora (F2) --------------------------------------------------------------------

@bp.route("")
@requiere_rol(*ROLES_PERSONAL)
def inicio():
    datos = modelo_panel.resumen(current_user)
    # El admin ve cuándo fue el último respaldo (solo mira la carpeta: no consulta la base)
    ultimo_respaldo = modelo_respaldo.ultimo() if current_user.rol == "admin" else None
    # v2.8: hojas del libro de reclamaciones que esperan respuesta (la ley da 15 días hábiles)
    reclamaciones = (modelo_reclamacion.pendientes(current_user)
                     if current_user.rol in ("admin", "operador") else None)
    return render_template("panel/inicio.html", buscar=FormularioBuscarReserva(formdata=None),
                           ultimo_respaldo=ultimo_respaldo, reclamaciones=reclamaciones, **datos)


PERIODOS = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes", "anio": "Este año"}


def _periodo():
    """El periodo elegido (lista blanca) o None si es toda la bitácora."""
    periodo = request.args.get("periodo") or None
    return periodo if periodo in PERIODOS else None


def _desde(periodo):
    """El primer momento del periodo, en hora de Lima (None = toda la bitácora)."""
    hoy = hoy_en_lima()
    inicio = {"hoy": hoy, "semana": hoy - timedelta(days=hoy.weekday()),
              "mes": hoy.replace(day=1), "anio": hoy.replace(month=1, day=1)}.get(periodo)
    return datetime.combine(inicio, datetime.min.time()) if inicio else None


@bp.route("/bitacora")
@requiere_rol("admin")
def bitacora():
    pagina = request.args.get("pagina", default=1, type=int)
    if pagina < 1:
        abort(404)
    acciones = modelo_bitacora.acciones_registradas(current_user)
    accion = request.args.get("accion") or None
    if accion is not None and accion not in acciones:   # lista blanca: solo acciones que existen
        accion = None
    periodo = _periodo()
    filas, total = modelo_bitacora.listar(current_user, pagina, accion, _desde(periodo))
    paginas = max(1, -(-total // modelo_bitacora.POR_PAGINA))
    if pagina > paginas:
        abort(404)
    return render_template("panel/bitacora.html", filas=filas, total=total, pagina=pagina,
                           paginas=paginas, acciones=acciones, accion=accion,
                           periodos=PERIODOS, periodo=periodo)


@bp.route("/bitacora/exportar")
@requiere_rol("admin")
def bitacora_exportar():
    """D-115: la bitácora (toda o solo los movimientos de las cuentas) en CSV para Excel."""
    periodo = _periodo()
    solo_sesiones = request.args.get("tipo") == "sesiones"
    filas = modelo_bitacora.exportar(current_user, _desde(periodo), solo_sesiones,
                                     PERIODOS.get(periodo, "Toda la bitácora"), ip_cliente())
    texto = hoja_de_calculo.csv_para_excel(
        ["Fecha", "Hora", "Usuario", "Acción", "Código", "Tabla", "Registro", "Detalle", "IP"],
        ([f["creado_en"].strftime("%d/%m/%Y"), f["creado_en"].strftime("%H:%M:%S"),
          f["nombre_usuario"] or "(turista o sistema)",
          formato.ACCIONES_BITACORA.get(f["accion"], f["accion"]), f["accion"],
          f["tabla_afectada"], f["registro_id"],
          "; ".join(f"{clave}: {valor}" for clave, valor in f["detalle"].items()), f["ip"]]
         for f in filas))
    nombre = (f"bitacora_{'sesiones' if solo_sesiones else 'completa'}_{periodo or 'todo'}_"
              f"{hoy_en_lima():%Y%m%d}.csv")
    return Response(texto, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# --- Mi cuenta: para todo el personal (D-113) ---------------------------------------------------

def _pagina_mi_cuenta(clave=None, contacto=None, sueltos=(), codigo=200):
    datos = cuenta.mis_datos(current_user)
    clave = clave or FormularioCambiarContrasena(prefix="clave", formdata=None)
    contacto = contacto or FormularioContacto(
        prefix="contacto", formdata=None,
        data={"correo": datos["correo"] or "", "telefono": datos["telefono"] or ""})
    return render_template("panel/mi_cuenta.html", datos=datos, clave=clave, contacto=contacto,
                           sueltos=sueltos, movimientos=cuenta.ultimos_movimientos(current_user),
                           minutos=current_app.config["SESION_INACTIVA_MIN"]), codigo


@bp.route("/mi-cuenta")
@requiere_rol(*ROLES_PERSONAL)
def mi_cuenta():
    return _pagina_mi_cuenta()


@bp.route("/mi-cuenta/contrasena", methods=["POST"])
@requiere_rol(*ROLES_PERSONAL)
def mi_contrasena():
    formulario = FormularioCambiarContrasena(prefix="clave")

    def cambiar():
        cuenta.cambiar_contrasena(current_user, formulario.actual.data, formulario.nueva.data,
                                  formulario.repetir.data, ip_cliente())
        # D-112: con la contraseña nueva cambió el sello. Esta sesión sigue (con el sello
        # nuevo) y las que estén abiertas en otros equipos se cierran en su siguiente clic.
        login_user(modelo_usuario.buscar_por_id(current_user.id))

    respuesta, sueltos, codigo = procesar(
        formulario, cambiar, "Listo: tu contraseña cambió. Si tenías la sesión abierta en otro "
        "equipo, allí se cerró.", url_for("panel.mi_cuenta"))
    return respuesta or _pagina_mi_cuenta(clave=formulario, sueltos=sueltos, codigo=codigo)


@bp.route("/mi-cuenta/contacto", methods=["POST"])
@requiere_rol(*ROLES_PERSONAL)
def mi_contacto():
    formulario = FormularioContacto(prefix="contacto")
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: cuenta.actualizar_contacto(current_user, datos_de(formulario), ip_cliente()),
        "Listo: tus datos de contacto se guardaron.", url_for("panel.mi_cuenta"))
    return respuesta or _pagina_mi_cuenta(contacto=formulario, sueltos=sueltos, codigo=codigo)


@bp.route("/sesion")
@requiere_rol(*ROLES_PERSONAL)
def sesion_activa():
    """D-110: el navegador avisa que la persona sigue trabajando (escribe o hace clic) aunque
    no cambie de página. Si la sesión ya se cerró por inactividad, responde 401."""
    return Response(status=204)


# --- Respaldos de la base (solo admin, D-116) --------------------------------------------------

@bp.route("/respaldos")
@requiere_rol("admin")
def respaldos():
    return render_template("panel/respaldos.html", respaldos=modelo_respaldo.listar(),
                           carpeta=modelo_respaldo.carpeta())


@bp.route("/respaldos/crear", methods=["POST"])
@requiere_rol("admin")
def respaldo_crear():
    if not FormularioAccion().validate_on_submit():
        abort(400)
    try:
        hecho = modelo_respaldo.crear_desde_panel(current_user, ip_cliente())
    except ErrorNegocio as error:
        flash(error.mensaje, "error")
    else:
        flash(f"Listo: se guardó {hecho['nombre']} ({hecho['tablas']} tablas, {hecho['filas']} "
              f"filas, {hecho['kb']} KB).", "exito")
    return redirect(url_for("panel.respaldos"), code=303)


@bp.route("/respaldos/reporte-general")
@requiere_rol("admin")
def respaldo_reporte():
    """Reservas, pagos, salidas y hospedajes en CSV, dentro de un ZIP (sin documentos)."""
    hojas, leeme = modelo_respaldo.reporte_general(current_user, ip_cliente())
    nombre = f"reporte_general_{hoy_en_lima():%Y%m%d}.zip"
    return Response(hoja_de_calculo.zip_de_csv(hojas, leeme), mimetype="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@bp.route("/respaldos/<nombre>")
@requiere_rol("admin")
def respaldo_descargar(nombre):
    ruta = modelo_respaldo.para_descargar(current_user, nombre, ip_cliente())
    if ruta is None:
        abort(404)
    return send_file(ruta, mimetype="application/sql", as_attachment=True, download_name=nombre)


# --- Salidas (RN-07) ------------------------------------------------------------------------------

@bp.route("/salidas")
@requiere_rol("admin", "operador")
def salidas():
    hoy = hoy_en_lima()
    fecha, error = hoy, None
    if request.args.get("fecha"):
        try:
            fecha = date.fromisoformat(request.args["fecha"])
        except ValueError:
            error = "La fecha no es válida: se muestran las salidas de hoy."
    filas = modelo_salida.listar_panel(current_user, fecha)
    pagina = render_template(
        "panel/salidas.html", salidas=filas, fecha=fecha, hoy=hoy, error=error,
        anterior=fecha - timedelta(days=1), siguiente=fecha + timedelta(days=1),
        feriado=feriados.de_la_fecha(fecha))                    # v2.2: feriado (Nager.Date)
    return pagina, (422 if error else 200)


def _opciones_salida(formulario, actual=None):
    """Carga en las listas desplegables las rutas, lanchas y personal de la base."""
    op = modelo_salida.opciones_formulario()
    formulario.ruta_id.choices = [SIN_ELEGIR] + [
        (r["id"], f"{r['nombre']} · {formato.duracion(r['duracion_horas'])}") for r in op["rutas"]]
    formulario.embarcacion_id.choices = [SIN_ELEGIR] + [
        (e["id"], f"{e['nombre']} · {e['matricula']} · hasta {e['capacidad_maxima']} personas")
        for e in op["lanchas"]]
    formulario.capitan_id.choices = [SIN_ELEGIR] + [
        (c["id"], c["nombre_completo"]) for c in op["capitanes"]]
    formulario.guia_id.choices = [(0, "— Sin guía —")] + [
        (x["id"], x["nombre_completo"]) for x in op["guias"]]
    if actual and actual["embarcacion_id"] not in dict(formulario.embarcacion_id.choices):
        # La lancha actual ya no está operativa: se muestra para que se vea y se cambie.
        formulario.embarcacion_id.choices.append(
            (actual["embarcacion_id"], f"{actual['embarcacion_nombre']} (no operativa)"))


def _datos_salida(formulario):
    f = formulario
    return modelo_salida.DatosSalida(
        ruta_id=f.ruta_id.data, embarcacion_id=f.embarcacion_id.data, capitan_id=f.capitan_id.data,
        guia_id=f.guia_id.data or None, fecha=f.fecha.data, hora=f.hora.data, cupo=f.cupo.data)


@bp.route("/salidas/nueva", methods=["GET", "POST"])
@requiere_rol("operador")
def salida_nueva():
    formulario = FormularioSalida()
    _opciones_salida(formulario)
    if request.method == "GET":
        formulario.fecha.data = hoy_en_lima() + timedelta(days=1)
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: modelo_salida.crear(current_user, _datos_salida(formulario), ip_cliente()),
        "Listo: la salida quedó programada.",
        lambda salida_id: url_for("panel.pasajeros", salida_id=salida_id))
    return respuesta or (render_template("panel/salida_formulario.html", f=formulario, s=None,
                                         sueltos=sueltos), codigo)


@bp.route("/salidas/<int:salida_id>/editar", methods=["GET", "POST"])
@requiere_rol("operador")
def salida_editar(salida_id):
    actual = modelo_salida.buscar_panel(current_user, salida_id)
    if actual is None:
        abort(404)
    if actual["estado"] not in modelo_salida.ESTADOS_EDITABLES or not actual["aun_no_zarpa"]:
        flash("Esta salida ya zarpó o se canceló: no se puede editar.", "info")
        return redirect(url_for("panel.pasajeros", salida_id=salida_id))
    zarpe = actual["fecha_hora_zarpe"]
    formulario = FormularioSalida(data={
        "ruta_id": actual["ruta_id"], "embarcacion_id": actual["embarcacion_id"],
        "capitan_id": actual["capitan_id"], "guia_id": actual["guia_id"] or 0,
        "fecha": zarpe.date(), "hora": zarpe.time(), "cupo": actual["cupo"]})
    _opciones_salida(formulario, actual)
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: modelo_salida.editar(current_user, salida_id, _datos_salida(formulario),
                                     ip_cliente()),
        lambda cambio: "Listo: la salida se actualizó." if cambio else "No había nada que cambiar.",
        url_for("panel.pasajeros", salida_id=salida_id))
    return respuesta or (render_template("panel/salida_formulario.html", f=formulario, s=actual,
                                         sueltos=sueltos), codigo)


@bp.route("/salidas/<int:salida_id>/<any(suspender, cancelar):accion>", methods=["GET", "POST"])
@requiere_rol("operador")
def salida_estado(salida_id, accion):
    actual = modelo_salida.buscar_panel(current_user, salida_id)
    if actual is None:
        abort(404)
    formulario = FormularioMotivo()
    formulario.enviar.label.text = "Suspender la salida" if accion == "suspender" else (
        "Cancelar la salida")
    funcion = modelo_salida.suspender if accion == "suspender" else modelo_salida.cancelar
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: funcion(current_user, salida_id, formulario.motivo.data, ip_cliente()),
        "Listo: la salida quedó " + ("suspendida." if accion == "suspender" else "cancelada."),
        url_for("panel.salidas", fecha=actual["fecha_hora_zarpe"].date().isoformat()))
    return respuesta or (render_template("panel/salida_motivo.html", f=formulario, s=actual,
                                         accion=accion, sueltos=sueltos), codigo)


@bp.route("/salidas/<int:salida_id>/zarpe", methods=["POST"])
@requiere_rol("operador", "capitan")
def salida_zarpe(salida_id):
    try:
        ausentes = modelo_salida.marcar_zarpe(current_user, salida_id, ip_cliente())
    except ErrorNegocio as error:
        return _pagina_pasajeros(salida_id, [error.mensaje], 422)
    mensaje = "Zarpe registrado."
    if ausentes:
        mensaje += (f" {len(ausentes)} reserva(s) sin nadie a bordo quedaron como «no se "
                    f"presentó»: {', '.join(ausentes)}.")
    flash(mensaje, "exito")
    return redirect(url_for("panel.pasajeros", salida_id=salida_id), code=303)


# --- Pasajeros, manifiesto (PDF) y WhatsApp -------------------------------------------------------

def _ahora_en_lima():
    return datetime.now(ZoneInfo(current_app.config["ZONA_HORARIA"]))


def _permisos_salida(s):
    """Qué botones ve cada rol en la página de la salida (el modelo lo vuelve a revisar)."""
    rol = current_user.rol
    activa = s["estado"] in modelo_salida.ESTADOS_ACTIVOS
    zarpe = activa and (rol == "operador"
                        or (rol == "capitan" and s["capitan_id"] == current_user.id))
    return {
        "editar": rol == "operador" and s["estado"] in modelo_salida.ESTADOS_EDITABLES
                  and s["aun_no_zarpa"],
        "suspender": rol == "operador" and activa,
        "cancelar": rol == "operador" and (activa or s["estado"] == "suspendida"),
        # El botón aparece desde 60 minutos antes (el modelo lo vuelve a revisar); antes, solo
        # el aviso de desde qué hora se podrá marcar.
        "zarpe": zarpe and bool(s["ventana_zarpe"]),
        "zarpe_desde": (s["fecha_hora_zarpe"]
                        - timedelta(minutes=modelo_salida.MINUTOS_ANTES_DEL_ZARPE)
                        if zarpe and not s["ventana_zarpe"] else None),
        "abordaje": rol in ("operador", "guia", "capitan"),
        # Venta en el muelle o por WhatsApp: solo si la salida todavía recibe reservas.
        "vender": rol == "operador" and s["estado_publico"] in ("disponible", "pocos_cupos"),
    }


def _pagina_pasajeros(salida_id, errores=(), codigo=200):
    salida, filas = modelo_salida.pasajeros_de_salida(current_user, salida_id)
    if salida is None:
        abort(404)
    pedido = request.args.get("formato", "")
    if pedido == "pdf":
        contenido = pdf.manifiesto(salida, filas, _ahora_en_lima())
        return Response(contenido, mimetype="application/pdf", headers={
            "Content-Disposition": f'inline; filename="manifiesto-salida-{salida_id}.pdf"'})
    if pedido == "whatsapp":
        texto = whatsapp.texto_lista(salida, filas)
        enlace_guia = (whatsapp.enlace(texto, salida["guia_telefono"])
                       if salida["guia_telefono"] else None)
        return render_template("panel/whatsapp.html", s=salida, texto=texto,
                               enlace=whatsapp.enlace(texto), enlace_guia=enlace_guia)
    plantilla = "panel/pasajeros_imprimir.html" if pedido == "imprimir" else "panel/pasajeros.html"
    return render_template(
        plantilla, s=salida, pasajeros=filas, errores=errores, accion=FormularioAccion(),
        abordaron=sum(1 for p in filas if p["abordo_en"]), puede=_permisos_salida(salida),
        generado_en=_ahora_en_lima(),
        # v2.2: el pronóstico a la hora del zarpe (Open-Meteo); en la hoja impresa no va
        clima=clima.para_la_hora(salida["fecha_hora_zarpe"]) if not pedido else None,
    ), codigo


@bp.route("/salidas/<int:salida_id>/pasajeros")
@requiere_rol(*ROLES_PERSONAL)
def pasajeros(salida_id):
    return _pagina_pasajeros(salida_id)


# --- Abordaje (RN-12) ----------------------------------------------------------------------------

@bp.route("/abordaje")
@requiere_rol("operador", "guia", "capitan")
def abordaje_buscar():
    formulario = FormularioBuscarReserva(formdata=request.args or None)
    codigo_http = 200
    if request.args:
        codigo = modelo_reserva.normalizar_codigo(formulario.codigo.data)
        if formulario.validate() and modelo_reserva.PATRON_CODIGO.match(codigo):
            return redirect(url_for("panel.abordaje", codigo=codigo, via="manual"))
        if not formulario.codigo.errors:
            formulario.codigo.errors.append("El código tiene la forma TV-XXXX.")
        codigo_http = 422
    return render_template("panel/abordaje_buscar.html", f=formulario), codigo_http


def _codigo_o_404(codigo):
    codigo = modelo_reserva.normalizar_codigo(codigo)
    if not modelo_reserva.PATRON_CODIGO.match(codigo):
        abort(404)
    return codigo


def _pagina_abordaje(codigo, formulario=None, cobro=None, errores=(), codigo_http=200):
    datos = modelo_abordaje.buscar(current_user, codigo)    # revisa el ◐ del guía y del capitán
    if datos is None:
        abort(404)
    if formulario is None:
        formulario = FormularioAbordaje(formdata=None)
        formulario.metodo.data = "manual" if request.args.get("via") == "manual" else "qr"
    saldo = max(datos["total"] - datos["pagado"], 0)
    puede_cobrar = (current_user.rol == "operador" and saldo > 0
                    and datos["estado"] in ("pendiente_pago", "confirmada", "abordada"))
    if puede_cobrar and cobro is None:
        cobro = FormularioCobro(formdata=None, data={"metodo": "efectivo_muelle",
                                                     "monto": f"{saldo:.2f}"})
    return render_template("panel/abordaje.html", r=datos, f=formulario, saldo=saldo,
                           cobro=cobro if puede_cobrar else None, errores=errores), codigo_http


@bp.route("/abordaje/<codigo>", methods=["GET", "POST"])
@requiere_rol("operador", "guia", "capitan")
def abordaje(codigo):
    codigo = _codigo_o_404(codigo)
    if request.method == "GET":
        return _pagina_abordaje(codigo)
    formulario = FormularioAbordaje()
    errores = []
    if formulario.validate():
        try:
            ids = [int(x) for x in request.form.getlist("pasajero")]
            resultado = modelo_abordaje.registrar(current_user, codigo, ids,
                                                  formulario.metodo.data, ip_cliente())
        except ValueError:
            errores = ["Marca los pasajeros de la lista."]
        except ErrorValidacion as error:
            errores = list(error.errores.values())
        except ErrorNegocio as error:
            errores = [error.mensaje]
        else:
            mensaje = f"Abordaje registrado: {resultado['registrados']} pasajero(s)."
            mensaje += (" Ya subió todo el grupo: la reserva quedó «abordada»."
                        if resultado["faltan"] == 0 else f" Faltan {resultado['faltan']}.")
            flash(mensaje, "exito")
            return redirect(url_for("panel.abordaje", codigo=codigo), code=303)
    return _pagina_abordaje(codigo, formulario, errores=errores, codigo_http=422)


@bp.route("/abordaje/<codigo>/cobro", methods=["POST"])
@requiere_rol("operador")
def cobro(codigo):
    codigo = _codigo_o_404(codigo)
    formulario = FormularioCobro()
    errores = []
    if formulario.validate():
        try:
            resultado = modelo_pago.registrar_cobro(
                current_user, codigo, formulario.metodo.data, formulario.monto.data,
                formulario.numero_operacion.data, ip_cliente())
        except ErrorValidacion as error:
            errores = poner_errores(formulario, error.errores)
        except ErrorNegocio as error:
            errores = [error.mensaje]
        else:
            flash(_mensaje_pago(resultado, "Cobro registrado."), "exito")
            # Vuelve al abordaje sin perder cómo se abrió: si fue escribiendo el código, el
            # abordaje se sigue registrando como «manual» y no como «qr».
            via = "manual" if request.args.get("via") == "manual" else None
            return redirect(url_for("panel.abordaje", codigo=codigo, via=via), code=303)
    return _pagina_abordaje(codigo, cobro=formulario, errores=errores, codigo_http=422)


# --- Pagos por verificar (RN-06) -----------------------------------------------------------------

def _mensaje_pago(resultado, inicio):
    if resultado["pagada"]:
        mensaje = f"{inicio} La reserva {resultado['codigo']} quedó PAGADA."
        if resultado["familia"]:
            mensaje += f" Familia anfitriona asignada: {resultado['familia']}."
        if resultado["aviso"]:
            mensaje += " " + resultado["aviso"]
        return mensaje
    falta = resultado["total"] - resultado["pagado"]
    return f"{inicio} A la reserva {resultado['codigo']} le falta {formato.soles(falta)}."


def _pagina_pagos(errores=None, codigo_http=200, errores_devolucion=None):
    return render_template(
        "panel/pagos.html", pagos=modelo_pago.listar_por_verificar(current_user),
        revisados=modelo_pago.ultimos_revisados(current_user), accion=FormularioAccion(),
        errores=errores or {}, puede_revisar=current_user.rol == "operador",
        devoluciones=modelo_reprogramacion.devoluciones_pendientes(current_user),
        errores_devolucion=errores_devolucion or {},
    ), codigo_http


@bp.route("/pagos")
@requiere_rol("admin", "operador")
def pagos():
    return _pagina_pagos()


@bp.route("/pagos/<int:pago_id>/verificar", methods=["POST"])
@requiere_rol("operador")
def pago_verificar(pago_id):
    try:
        resultado = modelo_pago.verificar(current_user, pago_id, ip_cliente())
    except ErrorNegocio as error:
        return _pagina_pagos({pago_id: error.mensaje}, 422)
    flash(_mensaje_pago(resultado, "Pago verificado."), "exito")
    return redirect(url_for("panel.pagos"), code=303)


@bp.route("/pagos/<int:pago_id>/rechazar", methods=["POST"])
@requiere_rol("operador")
def pago_rechazar(pago_id):
    formulario = FormularioRechazo()
    try:
        if not formulario.validate():
            raise ErrorValidacion({"observacion": formulario.observacion.errors[0]})
        modelo_pago.rechazar(current_user, pago_id, formulario.observacion.data, ip_cliente())
    except ErrorValidacion as error:
        return _pagina_pagos({pago_id: next(iter(error.errores.values()))}, 422)
    except ErrorNegocio as error:
        return _pagina_pagos({pago_id: error.mensaje}, 422)
    flash("Pago rechazado. El turista lo verá en su reserva con el motivo.", "exito")
    return redirect(url_for("panel.pagos"), code=303)


# --- Usuarios (solo admin) -----------------------------------------------------------------------

@bp.route("/usuarios")
@requiere_rol("admin")
def usuarios():
    return render_template("panel/usuarios.html", usuarios=modelo_usuario.listar(current_user),
                           roles=modelo_usuario.roles())


@bp.route("/usuarios/<int:usuario_id>/<any(activar, desactivar):accion>", methods=["POST"])
@requiere_rol("admin")
def usuario_estado(usuario_id, accion):
    """D-114: activar o desactivar una cuenta con un clic, desde la lista."""
    if not FormularioAccion().validate_on_submit():
        abort(400)
    try:
        nombre = modelo_usuario.cambiar_activo(current_user, usuario_id, accion == "activar",
                                               ip_cliente())
    except ErrorNegocio as error:
        flash(error.mensaje, "error")
    else:
        flash(f"Listo: {nombre} quedó activo." if accion == "activar" else
              f"Listo: {nombre} quedó desactivado. Pierde la sesión en su siguiente clic.", "exito")
    return redirect(url_for("panel.usuarios"), code=303)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@bp.route("/usuarios/<int:usuario_id>", methods=["GET", "POST"])
@requiere_rol("admin")
def usuario_formulario(usuario_id=None):
    actual = None
    if usuario_id is not None:
        actual = modelo_usuario.buscar_para_editar(current_user, usuario_id)
        if actual is None:
            abort(404)
    formulario = FormularioUsuario(data={**actual, "comunidad_id": actual["comunidad_id"] or 0}
                                   if actual else None)
    formulario.rol_id.choices = [SIN_ELEGIR] + [(r["id"], r["nombre"])
                                                for r in modelo_usuario.roles()]
    formulario.comunidad_id.choices = [(0, "— Ninguna —")] + [
        (c["id"], c["nombre"]) for c in comunidad.opciones()]
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: modelo_usuario.guardar(current_user, usuario_id, datos_de(formulario),
                                       ip_cliente()),
        "Listo: el usuario se guardó.", url_for("panel.usuarios"))
    titulo = f"Editar a {actual['nombre_usuario']}" if actual else "Nuevo usuario"
    return respuesta or (render_template(
        "panel/catalogos/formulario.html", f=formulario, titulo=titulo, sueltos=sueltos,
        volver=url_for("panel.usuarios"), volver_texto="Usuarios"), codigo)
