"""Reservar, ver la reserva, "Mi reserva", boleto con QR y reporte de pago (F4, nivel Oro).
F6: reprogramar o pedir la devolución si la salida se suspende (RN-11) y dejar una reseña
(RN-13). Todo en español o en inglés (servicios/textos.py).

Todo POST lleva CSRF y sigue el patrón POST → redirect (303) → GET.
"""

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
    session,
    url_for,
)
from flask_login import current_user

from app.formularios.reserva import (
    SIN_ELEGIR,
    FormularioMiReserva,
    FormularioPago,
    FormularioPasajero,
    FormularioReprogramar,
    FormularioResena,
    FormularioReserva,
)
from app.modelos import ErrorNegocio, ErrorValidacion, salida, tarifa
from app.modelos import reprogramacion as modelo_reprogramacion
from app.modelos import resena as modelo_resena
from app.modelos import reserva as modelo_reserva
from app.seguridad import ip_cliente
from app.servicios import formato, paises, pdf, qr, reniec, textos, tipo_cambio
from app.servicios.textos import mensaje, t, traducir_formulario

bp = Blueprint("reservas", __name__)

ESTADOS_CON_BOLETO = ("confirmada", "pagada", "abordada")
# El operador vende con este mismo formulario a quien llega al muelle o escribe por WhatsApp.
CANALES_DEL_OPERADOR = {"mostrador": "Muelle u oficina", "whatsapp": "WhatsApp"}


@bp.before_request
def sin_cache():
    # Estas páginas muestran datos personales: el navegador no debe guardarlas.
    g.sin_cache = True


# --- Acceso a una reserva (código + documento del titular) -----------------------------------

def _tiene_acceso(codigo):
    return codigo in session.get("reservas_validadas", [])


def _es_de_oficina():
    """Operador o admin con sesión: ven el boleto de cualquier reserva (para mandarlo o
    imprimirlo). Las acciones del turista (pagar, reprogramar, reseña) siguen siendo suyas."""
    return current_user.is_authenticated and current_user.rol in ("operador", "admin")


def _vende_el_operador():
    return current_user.is_authenticated and current_user.rol == "operador"


def _dar_acceso(codigo):
    lista = [c for c in session.get("reservas_validadas", []) if c != codigo] + [codigo]
    session["reservas_validadas"] = lista[-10:]


def _reserva_o_404(codigo):
    codigo = modelo_reserva.normalizar_codigo(codigo)
    if not modelo_reserva.PATRON_CODIGO.match(codigo):
        abort(404)
    datos = modelo_reserva.buscar_por_codigo(codigo)
    if datos is None:
        abort(404)
    return datos


def _pedir_acceso(datos):
    """Sin identificarse, las acciones de la reserva llevan a "Mi reserva"."""
    return redirect(url_for("reservas.mi_reserva", codigo=datos["codigo"]))


# --- Reservar --------------------------------------------------------------------------------

def _poner_errores(formulario, errores):
    """Pone cada error del modelo junto a su campo. Devuelve los que no tienen campo."""
    sueltos = []
    for nombre, texto in errores.items():
        texto = mensaje(texto)
        campo = None
        if nombre.startswith("acompanantes-"):
            _, indice, subcampo = nombre.split("-", 2)
            if int(indice) < len(formulario.acompanantes.entries):
                campo = formulario.acompanantes.entries[int(indice)].form[subcampo]
        elif nombre in formulario:
            campo = formulario[nombre]
        if campo is None:
            sueltos.append(texto)
        else:
            campo.errors = [*campo.errors, texto]
    return sueltos


def _solicitud(formulario, salida_id):
    def persona(nombres, apellidos, tipo, numero, pais, tipo_pasajero):
        return modelo_reserva.Persona(nombres, apellidos, tipo, numero, pais, tipo_pasajero or None)

    f = formulario
    return modelo_reserva.Solicitud(
        salida_id=salida_id,
        titular=persona(f.titular_nombres.data, f.titular_apellidos.data,
                        f.titular_tipo_documento.data, f.titular_numero_documento.data,
                        f.titular_nacionalidad.data, f.titular_tipo_pasajero_id.data),
        telefono=f.telefono.data,
        correo=f.correo.data,
        titular_viaja=f.titular_viaja.data,
        metodo_pago=f.metodo_pago.data,
        acompanantes=[persona(a.nombres.data, a.apellidos.data, a.tipo_documento.data,
                              a.numero_documento.data, a.nacionalidad.data, a.tipo_pasajero_id.data)
                      for a in (e.form for e in f.acompanantes.entries)],
        idioma=textos.idioma(),
    )


@bp.route("/salidas/<int:salida_id>/reservar", methods=["GET", "POST"])
def reservar(salida_id):
    datos_salida = salida.buscar_publica(salida_id)
    if datos_salida is None:
        abort(404)
    reservable = datos_salida["estado_publico"] in ("disponible", "pocos_cupos")
    precios = tarifa.precios_para_salida(salida_id)
    opciones = [SIN_ELEGIR] + [
        (p["tipo_pasajero_id"], f"{p['nombre']} · {formato.soles(p['precio'])}") for p in precios]
    maximo = current_app.config["MAX_PASAJEROS_POR_RESERVA"]

    formulario = FormularioReserva()
    if request.method == "GET":
        formulario.token_envio.data = modelo_reserva.generar_token()
        cantidad = min(max(request.args.get("acompanantes", 0, type=int), 0), maximo - 1)
        for _ in range(cantidad):
            formulario.acompanantes.append_entry()
    formulario.titular_tipo_pasajero_id.choices = opciones
    for entrada in formulario.acompanantes.entries:
        entrada.form.tipo_pasajero_id.choices = opciones
    plantilla = FormularioPasajero(prefix="acompanantes-__I__-")
    plantilla.tipo_pasajero_id.choices = opciones

    codigo_http = 200 if reservable else 409
    errores_sueltos = []
    venta = _vende_el_operador()
    canal = request.form.get("canal")
    canal = canal if canal in CANALES_DEL_OPERADOR else "mostrador"     # lista blanca
    if request.method == "POST":
        if not reservable:
            errores_sueltos.append(t("Esta salida ya no recibe reservas."))
        elif not formulario.validate():
            codigo_http = 422
        else:
            solicitud = _solicitud(formulario, salida_id)
            if venta:
                solicitud.canal = canal
            try:
                codigo, nueva = modelo_reserva.crear(
                    solicitud, formulario.token_envio.data, ip=ip_cliente(),
                    usuario_id=current_user.id if venta else None)   # la venta queda a su nombre
            except ErrorValidacion as error:
                errores_sueltos = _poner_errores(formulario, error.errores)
                codigo_http = 422
            except ErrorNegocio as error:
                if error.campo and error.campo in formulario:
                    _poner_errores(formulario, {error.campo: error.mensaje})
                else:
                    errores_sueltos.append(mensaje(error.mensaje))
                codigo_http = 422
            else:
                if venta:                    # el operador sigue en el panel, en la ficha
                    if nueva:
                        flash(f"Listo: la reserva {codigo} quedó registrada "
                              f"({CANALES_DEL_OPERADOR[canal]}). Mándale la confirmación por "
                              "WhatsApp.", "exito")
                    else:
                        flash(f"La reserva {codigo} ya estaba registrada: no se creó otra.", "info")
                    return redirect(url_for("panel.reserva_detalle", codigo=codigo), code=303)
                _dar_acceso(codigo)
                if nueva:
                    flash(t("¡Listo! Tu reserva {codigo} quedó registrada.", codigo=codigo),
                          "exito")
                else:
                    flash(t("Tu reserva {codigo} ya estaba registrada: no se creó otra.",
                            codigo=codigo), "info")
                return redirect(url_for("reservas.ver", codigo=codigo), code=303)

    traducir_formulario(formulario)
    traducir_formulario(plantilla)
    return render_template(
        "reservas/reservar.html", s=datos_salida, f=formulario, plantilla=plantilla,
        precios=precios, reservable=reservable, errores_sueltos=errores_sueltos,
        paises=paises.opciones(), maximo=maximo,
        minutos_pago=current_app.config["MINUTOS_VENCIMIENTO_PAGO"],
        venta=venta, canales=CANALES_DEL_OPERADOR, canal=canal,
        consulta_dni=reniec.disponible(), cambio=tipo_cambio.del_dia(),     # APIs (v2.2)
    ), codigo_http


# --- Ver la reserva y "Mi reserva" ---------------------------------------------------------------

@bp.route("/reservas/<codigo>")
def ver(codigo):
    datos = _reserva_o_404(codigo)
    para_resena = modelo_resena.para_la_reserva(datos["codigo"])
    return render_template(
        "reservas/reserva.html", r=datos, acceso=_tiene_acceso(datos["codigo"]),
        pasajeros=modelo_reserva.pasajeros(datos["id"]),
        pagos=modelo_reserva.pagos(datos["id"]),
        hospedajes=modelo_reserva.hospedajes(datos["id"]),
        con_boleto=datos["estado"] in ESTADOS_CON_BOLETO,
        puede_reprogramar=modelo_reprogramacion.puede(datos),
        puede_resenar=modelo_resena.por_que_no(para_resena) is None,
    )


@bp.route("/mi-reserva", methods=["GET", "POST"])
def mi_reserva():
    formulario = FormularioMiReserva()
    if request.method == "GET" and request.args.get("codigo"):
        formulario.codigo.data = modelo_reserva.normalizar_codigo(request.args["codigo"])
    codigo_http, error_general = 200, None
    if formulario.is_submitted():
        if not formulario.validate():
            codigo_http = 422
        elif modelo_reserva.validar_acceso(formulario.codigo.data,
                                           formulario.numero_documento.data):
            _dar_acceso(formulario.codigo.data)
            return redirect(url_for("reservas.ver", codigo=formulario.codigo.data), code=303)
        else:
            # Mismo mensaje si falla el código o el documento: no se da pista de cuál está mal.
            error_general = t("No encontramos una reserva con ese código y ese documento.")
            codigo_http = 401
    traducir_formulario(formulario)
    return render_template("reservas/mi_reserva.html", f=formulario,
                           error_general=error_general), codigo_http


# --- Boleto con QR (HTML y PDF) ------------------------------------------------------------------

@bp.route("/reservas/<codigo>/boleto")
def boleto(codigo):
    datos = _reserva_o_404(codigo)
    if not (_tiene_acceso(datos["codigo"]) or _es_de_oficina()):
        return _pedir_acceso(datos)
    if datos["estado"] not in ESTADOS_CON_BOLETO:
        flash(t("El boleto estará listo cuando la reserva esté confirmada o pagada."), "info")
        return redirect(url_for("reservas.ver", codigo=datos["codigo"]))
    pasajeros = modelo_reserva.pasajeros(datos["id"])
    url_qr = qr.url_de_abordaje(datos["codigo"])
    if request.args.get("formato") == "pdf":
        datos = {**datos, "estado_texto": formato.estado_reserva(datos["estado"])}
        contenido = pdf.boleto(datos, pasajeros, qr.png(url_qr))
        return Response(contenido, mimetype="application/pdf", headers={
            "Content-Disposition": f'inline; filename="boleto-{datos["codigo"]}.pdf"'})
    return render_template("reservas/boleto.html", r=datos, pasajeros=pasajeros,
                           qr_svg=qr.svg(url_qr, t("Código QR del boleto {codigo}",
                                                   codigo=datos["codigo"])))


# --- Reporte de pago (RN-06) ---------------------------------------------------------------------

@bp.route("/reservas/<codigo>/pago", methods=["GET", "POST"])
def pago(codigo):
    datos = _reserva_o_404(codigo)
    if not _tiene_acceso(datos["codigo"]):
        return _pedir_acceso(datos)
    if datos["estado"] != "pendiente_pago" or not datos["vigente"]:
        flash(t("Esta reserva no está esperando un pago."), "info")
        return redirect(url_for("reservas.ver", codigo=datos["codigo"]))

    saldo = max(datos["total"] - datos["pagado"] - datos["reportado"], 0)
    if saldo <= 0:
        flash(t("Ya reportaste el total. La agencia está verificando tu pago."), "info")
        return redirect(url_for("reservas.ver", codigo=datos["codigo"]))
    formulario = FormularioPago()
    if request.method == "GET":
        formulario.metodo.data = datos["metodo_pago_elegido"]
        formulario.monto.data = f"{saldo:.2f}"
    codigo_http, errores_sueltos = 200, []
    if formulario.is_submitted():
        if not formulario.validate():
            codigo_http = 422
        else:
            try:
                modelo_reserva.reportar_pago(
                    datos["codigo"], formulario.metodo.data, formulario.monto.data,
                    formulario.numero_operacion.data, ip=ip_cliente())
            except ErrorValidacion as error:
                errores_sueltos = _poner_errores(formulario, error.errores)
                codigo_http = 422
            except ErrorNegocio as error:
                errores_sueltos.append(mensaje(error.mensaje))
                codigo_http = 422
            else:
                flash(t("Recibimos tu reporte de pago. La agencia lo verificará pronto."), "exito")
                return redirect(url_for("reservas.ver", codigo=datos["codigo"]), code=303)
    traducir_formulario(formulario)
    return render_template("reservas/pago.html", r=datos, f=formulario, saldo=saldo,
                           errores_sueltos=errores_sueltos), codigo_http


# --- Salida suspendida: reprogramar o pedir la devolución (RN-11) ---------------------------

@bp.route("/reservas/<codigo>/reprogramar", methods=["GET", "POST"])
def reprogramar(codigo):
    datos = _reserva_o_404(codigo)
    if not _tiene_acceso(datos["codigo"]):
        return _pedir_acceso(datos)
    if not modelo_reprogramacion.puede(datos):
        flash(t("Esta reserva no necesita reprogramarse: su salida no está suspendida."), "info")
        return redirect(url_for("reservas.ver", codigo=datos["codigo"]))
    formulario = FormularioReprogramar()
    formulario.salida_id.choices = [
        (o["salida_id"], f"{formato.fecha_hora(o['fecha_hora_zarpe'])} · "
                         + t("{n} libres", n=o["libres"])
                         + (" · ⚠ " + t("alerta en el lago") if o["afectada_por_alerta"] else ""))
        for o in modelo_reprogramacion.opciones(datos["codigo"])]
    codigo_http, sueltos = 200, []
    if formulario.is_submitted():
        if not formulario.validate():
            codigo_http = 422
        else:
            try:
                modelo_reprogramacion.reprogramar(datos["codigo"], formulario.salida_id.data,
                                                  ip=ip_cliente())
            except ErrorNegocio as error:
                sueltos, codigo_http = [mensaje(error.mensaje)], 422
            else:
                flash(t("¡Listo! Tu reserva {codigo} pasó a la nueva salida. Tu código, tus pagos "
                        "y tu boleto siguen valiendo.", codigo=datos["codigo"]), "exito")
                return redirect(url_for("reservas.ver", codigo=datos["codigo"]), code=303)
    traducir_formulario(formulario)
    return render_template("reservas/reprogramar.html", r=datos, f=formulario, sueltos=sueltos,
                           personas=len(modelo_reserva.pasajeros(datos["id"]))), codigo_http


@bp.route("/reservas/<codigo>/devolucion", methods=["POST"])
def devolucion(codigo):
    datos = _reserva_o_404(codigo)
    if not _tiene_acceso(datos["codigo"]):
        return _pedir_acceso(datos)
    try:
        monto = modelo_reprogramacion.pedir_devolucion(datos["codigo"], ip=ip_cliente())
    except ErrorNegocio as error:
        flash(mensaje(error.mensaje), "error")
        return redirect(url_for("reservas.ver", codigo=datos["codigo"]), code=303)
    if monto:
        flash(t("Tu reserva quedó cancelada. La agencia te devolverá {monto} y se comunicará "
                "contigo.", monto=formato.soles(monto)), "exito")
    else:
        flash(t("Tu reserva quedó cancelada, sin costo."), "exito")
    return redirect(url_for("reservas.ver", codigo=datos["codigo"]), code=303)


# --- Reseña (RN-13) -------------------------------------------------------------------------------

@bp.route("/reservas/<codigo>/resena", methods=["GET", "POST"])
def resena(codigo):
    datos = _reserva_o_404(codigo)
    if not _tiene_acceso(datos["codigo"]):
        return _pedir_acceso(datos)
    motivo = modelo_resena.por_que_no(modelo_resena.para_la_reserva(datos["codigo"]))
    formulario = FormularioResena()
    codigo_http, sueltos = 200, []
    if formulario.is_submitted() and not motivo:
        if not formulario.validate():
            codigo_http = 422
        else:
            try:
                modelo_resena.crear(datos["codigo"], formulario.puntuacion.data,
                                    formulario.comentario.data, textos.idioma(), ip_cliente())
            except ErrorValidacion as error:
                sueltos, codigo_http = _poner_errores(formulario, error.errores), 422
            except ErrorNegocio as error:
                sueltos, codigo_http = [mensaje(error.mensaje)], 422
            else:
                flash(t("¡Gracias! Tu opinión se publicará cuando la agencia la revise."), "exito")
                return redirect(url_for("reservas.ver", codigo=datos["codigo"]), code=303)
    elif formulario.is_submitted():
        codigo_http = 422
    traducir_formulario(formulario)
    return render_template("reservas/resena.html", r=datos, f=formulario, sueltos=sueltos,
                           motivo=mensaje(motivo) if motivo else None), codigo_http
