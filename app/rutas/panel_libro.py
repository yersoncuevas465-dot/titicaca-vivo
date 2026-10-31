"""Libro de reclamaciones en el panel (v2.8): el operador ve las hojas, su plazo y las responde;
el admin solo las mira. La respuesta llega al consumidor por correo y queda en la bitácora.

Las rutas se registran en el blueprint `panel` (url /panel/reclamaciones). Ningún SQL aquí.
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.modelos import ErrorNegocio, ErrorValidacion
from app.modelos import reclamacion as modelo_reclamacion
from app.rutas.panel import bp
from app.rutas.publico import hoy_en_lima
from app.rutas.publico_libro import texto_de_la_hoja
from app.seguridad import ip_cliente, requiere_rol
from app.servicios import correo


def _pagina(errores=None, codigo=200):
    return render_template("panel/reclamaciones.html",
                           hojas=modelo_reclamacion.listar_panel(current_user), hoy=hoy_en_lima(),
                           errores=errores or {}, puede=current_user.rol == "operador",
                           dias=modelo_reclamacion.DIAS_HABILES_PARA_RESPONDER), codigo


@bp.route("/reclamaciones")
@requiere_rol("admin", "operador")
def reclamaciones():
    return _pagina()


@bp.route("/reclamaciones/<int:hoja_id>/respuesta", methods=["POST"])
@requiere_rol("operador")
def reclamacion_responder(hoja_id):
    try:
        hoja = modelo_reclamacion.responder(current_user, hoja_id, request.form.get("respuesta"),
                                            ip_cliente())
    except ErrorValidacion as error:
        return _pagina({hoja_id: next(iter(error.errores.values()))}, 422)
    except ErrorNegocio as error:
        return _pagina({hoja_id: error.mensaje}, 422)
    correo.enviar(hoja["correo"], f"Respuesta a tu hoja de reclamación N.º {hoja['numero']}",
                  texto_de_la_hoja(hoja, "La agencia respondió tu hoja de reclamación."))
    flash(f"Listo: la hoja N.º {hoja['numero']} quedó respondida y la respuesta se envió a "
          f"{correo.oculto(hoja['correo'])}.", "exito")
    return redirect(url_for("panel.reclamaciones"), code=303)
