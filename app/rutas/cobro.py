"""QR de cobro (observación del docente, 27/11/2026).

- /panel/cobro (solo el admin): sube o quita el QR de Yape y el de Plin. Queda en la bitácora:
  cambiar el QR cambia a dónde va la plata, así que se sabe quién y cuándo.
- /cobro/qr/<yape|plin> (público): la imagen que muestra la página de pago.
"""

from flask import abort, flash, redirect, render_template, send_file, url_for
from flask_login import current_user
from werkzeug.datastructures import FileStorage

from app import bd
from app.formularios.cobro import FormularioCobro
from app.modelos import bitacora
from app.rutas import panel, publico
from app.seguridad import ip_cliente, requiere_rol
from app.servicios import qr_cobro


def _anotar(accion, medio):
    with bd.transaccion() as cur:
        bitacora.anotar(cur, current_user.id, accion, None, None, {"medio": medio}, ip_cliente())


@panel.bp.route("/cobro", methods=["GET", "POST"])
@requiere_rol("admin")
def cobro_qr():
    formulario = FormularioCobro()
    codigo = 200
    if formulario.validate_on_submit():
        guardados = []
        for medio, nombre in qr_cobro.MEDIOS.items():
            campo = getattr(formulario, f"qr_{medio}")
            if isinstance(campo.data, FileStorage) and campo.data.filename:
                try:
                    qr_cobro.guardar(medio, campo.data)
                except ValueError as error:
                    campo.errors = [str(error)]
                    codigo = 422
                else:
                    _anotar("qr_cobro_cambiado", medio)
                    guardados.append(nombre)
        if codigo == 200:
            if guardados:
                flash(f"Listo: se guardó el QR de {' y '.join(guardados)}. Escanéalo con tu "
                      "celular para comprobar que lleva a la cuenta de la agencia.", "exito")
            return redirect(url_for("panel.cobro_qr"), code=303)
    elif formulario.is_submitted():
        codigo = 422
    return render_template("panel/cobro.html", f=formulario, medios=qr_cobro.MEDIOS,
                           hay={medio: qr_cobro.hay(medio) for medio in qr_cobro.MEDIOS}), codigo


@panel.bp.route("/cobro/<any(yape, plin):medio>/quitar", methods=["POST"])
@requiere_rol("admin")
def cobro_qr_quitar(medio):
    qr_cobro.borrar(medio)
    _anotar("qr_cobro_quitado", medio)
    flash(f"Listo: la página de pago ya no muestra el QR de {qr_cobro.MEDIOS[medio]}.", "exito")
    return redirect(url_for("panel.cobro_qr"), code=303)


@publico.bp.route("/cobro/qr/<any(yape, plin):medio>")
def qr_cobro_imagen(medio):
    if not qr_cobro.hay(medio):
        abort(404)
    respuesta = send_file(qr_cobro.ruta(medio), mimetype="image/png", max_age=0)
    respuesta.headers["Cache-Control"] = "no-cache"      # si el admin lo cambia, se ve el nuevo
    return respuesta
