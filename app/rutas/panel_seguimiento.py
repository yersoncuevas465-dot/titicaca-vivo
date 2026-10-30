"""Panel (F6): alertas con suspensión en un paso (RN-11), hospedajes con reasignación y
reporte de transparencia (RN-10, 8.1), moderación de reseñas (RN-13), indicadores (8.8) y
devoluciones por atender (D-11).

Las rutas se registran en el mismo blueprint `panel` (url /panel/...). Ningún SQL aquí.
"""

from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.formularios import datos_de
from app.formularios.panel import (
    FormularioAccion,
    FormularioAlerta,
    FormularioNota,
    FormularioReasignar,
)
from app.modelos import (
    ErrorNegocio,
    ErrorValidacion,
    alerta,
    comunidad,
    hospedaje,
    indicadores,
    resena,
    ruta,
)
from app.modelos import reprogramacion as modelo_reprogramacion
from app.rutas.panel import _pagina_pagos, bp, procesar
from app.rutas.publico import hoy_en_lima
from app.seguridad import ip_cliente, requiere_rol
from app.servicios import mapa

# --- Alertas (RN-11) -----------------------------------------------------------------------------

@bp.route("/alertas")
@requiere_rol("admin", "operador")
def alertas():
    return render_template("panel/alertas.html", alertas=alerta.listar_panel(current_user))


def _opciones_alerta(formulario):
    formulario.comunidad_id.choices = [(0, "Todo el lago")] + [
        (c["id"], c["nombre"]) for c in alerta.opciones_comunidades()]


@bp.route("/alertas/nueva", methods=["GET", "POST"])
@bp.route("/alertas/<int:alerta_id>", methods=["GET", "POST"])
@requiere_rol("admin", "operador")
def alerta_formulario(alerta_id=None):
    actual = None
    if alerta_id is not None:
        actual = alerta.buscar_panel(current_user, alerta_id)
        if actual is None:
            abort(404)
    elif current_user.rol != "operador":
        abort(403)                                   # el admin mira, no registra
    formulario = FormularioAlerta(data={**actual, "comunidad_id": actual["comunidad_id"] or 0}
                                  if actual else None)
    _opciones_alerta(formulario)
    if request.method == "POST" and current_user.rol != "operador":
        abort(403)
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: alerta.guardar(current_user, alerta_id, datos_de(formulario), ip_cliente()),
        "Listo: la alerta quedó registrada. Revisa si afecta salidas.",
        lambda nuevo_id: url_for("panel.alerta_formulario", alerta_id=nuevo_id))
    return respuesta or _pagina_alerta(formulario, actual, sueltos, codigo)


def _mapa_de_la_alerta(actual):
    """El lago con el lugar de la alerta: su comunidad con un halo, o todo el lago teñido, y las
    rutas que pasan por ahí resaltadas."""
    comunidades = comunidad.listar_publicas()
    lugar = next((c["slug"] for c in comunidades if c["id"] == actual["comunidad_id"]), None)
    return mapa.construir(comunidades, ruta.paradas_para_mapa(),
                          resaltadas={lugar} if lugar else (),
                          todo_el_lago=not actual["comunidad_id"])


def _pagina_alerta(formulario, actual, errores=(), codigo=200):
    afectadas = alerta.salidas_afectadas(current_user, actual["id"]) if actual else []
    return render_template("panel/alerta.html", f=formulario, a=actual, afectadas=afectadas,
                           mapa=_mapa_de_la_alerta(actual) if actual else None,
                           sueltos=errores, accion=FormularioAccion()), codigo


@bp.route("/alertas/<int:alerta_id>/suspender", methods=["POST"])
@requiere_rol("operador")
def alerta_suspender(alerta_id):
    actual = alerta.buscar_panel(current_user, alerta_id)
    if actual is None:
        abort(404)
    try:
        ids = alerta.suspender_afectadas(current_user, alerta_id, ip_cliente())
    except ErrorNegocio as error:
        formulario = FormularioAlerta(formdata=None,
                                      data={**actual, "comunidad_id": actual["comunidad_id"] or 0})
        _opciones_alerta(formulario)
        return _pagina_alerta(formulario, actual, [error.mensaje], 422)
    flash(f"Listo: {len(ids)} salida(s) suspendidas en un solo paso. Cada turista verá el "
          "motivo y podrá reprogramar o pedir la devolución.", "exito")
    return redirect(url_for("panel.alerta_formulario", alerta_id=alerta_id), code=303)


# --- Hospedajes y transparencia (RN-10) ---------------------------------------------------------

@bp.route("/hospedajes")
@requiere_rol("admin", "operador")
def hospedajes():
    return _pagina_hospedajes()


def _pagina_hospedajes(errores=(), codigo=200):
    desde, errores = hoy_en_lima(), list(errores)
    try:
        if request.args.get("desde"):
            desde = date.fromisoformat(request.args["desde"])
    except ValueError:
        errores.append("La fecha no es válida: se muestran las noches desde hoy.")
        codigo = 422
    return render_template(
        "panel/hospedajes.html", noches=hospedaje.listar_panel(current_user, desde), desde=desde,
        sin_familia=hospedaje.reservas_sin_familia(current_user), accion=FormularioAccion(),
        puede=current_user.rol == "operador", errores=errores), codigo


@bp.route("/hospedajes/<int:hospedaje_id>/reasignar", methods=["GET", "POST"])
@requiere_rol("operador")
def hospedaje_reasignar(hospedaje_id):
    noche = hospedaje.buscar_panel(current_user, hospedaje_id)
    if noche is None:
        abort(404)
    formulario = FormularioReasignar()
    candidatas = hospedaje.candidatas(current_user, noche)
    formulario.familia_id.choices = [(0, "— Elige —")] + [
        (f["id"], f"{f['nombre_familia']} · {f['noches_30_dias']} noche(s) en 30 días")
        for f in candidatas]
    if request.method == "GET" and candidatas:
        formulario.familia_id.data = candidatas[0]["id"]           # la que toca por rotación
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: hospedaje.reasignar(current_user, hospedaje_id, formulario.familia_id.data,
                                    formulario.motivo.data, ip_cliente()),
        "Listo: la noche se reasignó y el motivo quedó en la bitácora.",
        url_for("panel.hospedajes", desde=noche["fecha_noche"].isoformat()))
    return respuesta or (render_template("panel/reasignar.html", f=formulario, n=noche,
                                         candidatas=candidatas, sueltos=sueltos), codigo)


@bp.route("/hospedajes/asignar/<codigo>", methods=["POST"])
@requiere_rol("operador")
def hospedaje_asignar(codigo):
    try:
        familia = hospedaje.asignar_faltante(current_user, codigo, ip_cliente())
    except ErrorNegocio as error:
        return _pagina_hospedajes([error.mensaje], 422)
    flash(f"Listo: la reserva {codigo} recibe a la {familia['nombre_familia']} (rotación).",
          "exito")
    return redirect(url_for("panel.hospedajes"), code=303)


@bp.route("/hospedajes/<int:hospedaje_id>/cumplida", methods=["POST"])
@requiere_rol("operador")
def hospedaje_cumplida(hospedaje_id):
    try:
        hospedaje.marcar_cumplida(current_user, hospedaje_id, ip_cliente())
    except ErrorNegocio as error:
        return _pagina_hospedajes([error.mensaje], 422)
    flash("Listo: la noche quedó como cumplida (ya cuenta como ingreso de la familia).", "exito")
    return redirect(url_for("panel.hospedajes", desde=request.form.get("desde") or None),
                    code=303)


@bp.route("/hospedajes/transparencia")
@requiere_rol("admin", "operador")
def transparencia():
    meses = hospedaje.meses_con_hospedaje()
    mes = request.args.get("mes") or (meses[0] if meses else hoy_en_lima().strftime("%Y-%m"))
    if mes not in meses and meses:
        mes = meses[0]                                # lista blanca: solo meses con datos
    filas = hospedaje.transparencia(current_user, mes)
    return render_template("panel/transparencia.html", filas=filas, mes=mes, meses=meses)


# --- Reseñas (RN-13) ---------------------------------------------------------------------------

@bp.route("/resenas")
@requiere_rol("admin", "operador")
def resenas():
    return _pagina_resenas()


def _pagina_resenas(errores=(), codigo=200):
    return render_template("panel/resenas.html", resenas=resena.listar_panel(current_user),
                           accion=FormularioAccion(), puede=current_user.rol == "operador",
                           errores=errores), codigo


@bp.route("/resenas/<int:resena_id>/<any(publicada, rechazada):decision>", methods=["POST"])
@requiere_rol("operador")
def resena_moderar(resena_id, decision):
    try:
        resena.moderar(current_user, resena_id, decision, ip_cliente())
    except ErrorNegocio as error:
        return _pagina_resenas([error.mensaje], 422)
    flash("Listo: la reseña quedó " + ("publicada." if decision == "publicada"
                                       else "rechazada."), "exito")
    return redirect(url_for("panel.resenas"), code=303)


# --- Indicadores (8.8) -------------------------------------------------------------------------

@bp.route("/indicadores")
@requiere_rol("admin", "operador")
def indicadores_panel():
    clave = request.args.get("dias", "30")
    if clave not in indicadores.PERIODOS:          # lista blanca de periodos
        clave = "30"
    dias = indicadores.PERIODOS[clave]
    return render_template(
        "panel/indicadores.html", dias=clave, periodos=indicadores.PERIODOS,
        ocupacion=indicadores.ocupacion_por_ruta(current_user, dias),
        poca=indicadores.rutas_con_poca_ocupacion(current_user, dias),
        umbral=indicadores.OCUPACION_BAJA,
        metodos=indicadores.ingresos_por_metodo(current_user, dias),
        paises=indicadores.nacionalidades(current_user, dias),
        familias=indicadores.noches_por_familia(current_user, dias))


# --- Devoluciones (D-11) -----------------------------------------------------------------------

@bp.route("/devoluciones/<int:reserva_id>/atendida", methods=["POST"])
@requiere_rol("operador")
def devolucion_atendida(reserva_id):
    formulario = FormularioNota()
    try:
        if not formulario.validate():
            raise ErrorValidacion({"nota": formulario.nota.errors[0]})
        modelo_reprogramacion.atender_devolucion(current_user, reserva_id, formulario.nota.data,
                                                 ip_cliente())
    except ErrorValidacion as error:
        return _pagina_pagos(errores_devolucion={reserva_id: next(iter(error.errores.values()))},
                             codigo_http=422)
    except ErrorNegocio as error:
        return _pagina_pagos(errores_devolucion={reserva_id: error.mensaje}, codigo_http=422)
    flash("Listo: la devolución quedó atendida en la bitácora.", "exito")
    return redirect(url_for("panel.pagos"), code=303)
