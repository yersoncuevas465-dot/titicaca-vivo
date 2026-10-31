"""Libro de reclamaciones virtual (v2.8): la hoja, su constancia y el aviso por correo.

Las rutas se registran en el blueprint `publico` (url /libro-de-reclamaciones). La hoja queda
en la bitácora (modelos/reclamacion.py). La constancia solo la ve quien la registró, en este
navegador: lleva datos personales. Ningún SQL aquí.
"""

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for

from app.formularios.reclamacion import FormularioReclamo
from app.modelos import ErrorNegocio, ErrorValidacion
from app.modelos import contacto as modelo_contacto
from app.modelos import reclamacion as modelo_reclamacion
from app.rutas.publico import bp
from app.seguridad import ip_cliente, limitador, sin_cache
from app.servicios import correo, formato, textos
from app.servicios.textos import t

CAMPOS = ("tipo", "nombres", "apellidos", "tipo_documento", "numero_documento", "domicilio",
          "correo", "telefono", "apoderado", "codigo_reserva", "monto", "servicio", "detalle",
          "pedido", "acepto")


def _proveedor():
    """«Titicaca Vivo · RUC 20...»: la razón social y el RUC del .env (la ley pide mostrarlos)."""
    ruc = current_app.config["AGENCIA_RUC"]
    return current_app.config["AGENCIA_RAZON_SOCIAL"] + (f" · RUC {ruc}" if ruc else "")


def texto_de_la_hoja(hoja, encabezado):
    """La hoja en texto, para el correo de la constancia, el aviso a la agencia y la respuesta."""
    lineas = [
        encabezado, "",
        f"Hoja de reclamación N.º {hoja['numero']} · {formato.fecha_hora(hoja['registrada_en'])}",
        f"Proveedor: {_proveedor()}",
        "",
        f"Tipo: {hoja['tipo'].capitalize()}",
        f"Consumidor: {hoja['nombres']} {hoja['apellidos']} · {hoja['tipo_documento']} "
        f"{hoja['numero_documento']}",
        f"Domicilio: {hoja['domicilio']}",
        f"Correo: {hoja['correo']}"
        + (f" · Celular: {hoja['telefono']}" if hoja["telefono"] else ""),
    ]
    if hoja.get("apoderado"):
        lineas.append(f"Padre, madre o apoderado: {hoja['apoderado']}")
    lineas += [
        f"Servicio contratado: {hoja['servicio']}"
        + (f" · Reserva {hoja['codigo_reserva']}" if hoja.get("codigo_reserva") else "")
        + (f" · Monto reclamado: S/ {hoja['monto']}" if hoja.get("monto") else ""),
        "", "Detalle:", hoja["detalle"], "", "Pedido:", hoja["pedido"], "",
        f"La agencia responde hasta el {formato.fecha_larga(hoja['vence_el'])} "
        f"({modelo_reclamacion.DIAS_HABILES_PARA_RESPONDER} días hábiles).",
    ]
    if hoja.get("respuesta"):
        lineas += ["", "Respuesta de la agencia:", hoja["respuesta"]]
    return "\n".join(lineas)


@bp.route("/libro-de-reclamaciones", methods=["GET", "POST"])
@limitador.limit(lambda: current_app.config["LIMITE_HOJAS_RECLAMACION"], methods=["POST"])
@sin_cache
def libro_reclamaciones():
    formulario = FormularioReclamo()
    sueltos, codigo_http = [], 200
    if request.method == "POST":
        if formulario.sitio_web.data:                  # la trampa para robots vino llena
            return redirect(url_for("publico.libro_reclamaciones"), code=303)
        datos = {campo: formulario[campo].data for campo in CAMPOS}
        datos["idioma"] = textos.idioma()
        try:
            if not formulario.validate():
                raise ErrorValidacion({})
            numero = modelo_reclamacion.registrar(datos, ip_cliente())
        except ErrorValidacion as error:
            for nombre, texto in error.errores.items():
                formulario[nombre].errors = [*formulario[nombre].errors, texto]
            codigo_http = 422
        except ErrorNegocio as error:
            sueltos, codigo_http = [error.mensaje], 503
        else:
            hoja = modelo_reclamacion.buscar(numero)
            correo.enviar(hoja["correo"], f"Constancia de tu hoja de reclamación N.º {numero}",
                          texto_de_la_hoja(hoja, "Esta es la constancia de tu hoja."))
            for destino in modelo_contacto.destinatarios(current_app.config["AGENCIA_CORREO"]):
                correo.enviar(destino, f"[Titicaca Vivo] Nueva hoja de reclamación N.º {numero}",
                              texto_de_la_hoja(hoja, "Llegó una hoja al libro de reclamaciones."))
            # Solo este navegador puede ver la constancia (lleva datos personales)
            propias = [n for n in session.get("hojas_reclamacion", []) if n != numero] + [numero]
            session["hojas_reclamacion"] = propias[-5:]
            flash(t("Listo: tu hoja quedó registrada con el N.º {numero}.", numero=numero), "exito")
            return redirect(url_for("publico.constancia_reclamacion", numero=numero), code=303)
    return render_template(
        "publico/libro_reclamaciones.html", f=formulario, sueltos=sueltos,
        proveedor=_proveedor(), dias=modelo_reclamacion.DIAS_HABILES_PARA_RESPONDER), codigo_http


@bp.route("/libro-de-reclamaciones/<numero>")
@sin_cache
def constancia_reclamacion(numero):
    if numero not in session.get("hojas_reclamacion", []):
        abort(404)                                   # no se dice si la hoja existe
    hoja = modelo_reclamacion.buscar(numero)
    if hoja is None:
        abort(404)
    return render_template(
        "publico/constancia_reclamacion.html", h=hoja, proveedor=_proveedor(),
        dias=modelo_reclamacion.DIAS_HABILES_PARA_RESPONDER)
