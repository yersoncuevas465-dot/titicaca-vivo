"""Reservas en el panel (operador y admin): buscarlas y ver la ficha completa de cada una.

- /panel/reservas: las últimas reservas, o las que coinciden con un código, documento, celular
  o nombre (del titular o de cualquier pasajero). Es lo que el operador necesita cuando un
  turista llama o escribe por WhatsApp.
- /panel/reservas/<código>: titular, pasajeros, pagos, noche con la familia y TODO su historial
  (la bitácora de la reserva, de sus pagos y de su hospedaje). El operador cobra, embarca o le
  manda la confirmación por WhatsApp; el admin solo mira.

La venta en el muelle o por WhatsApp usa el mismo formulario de reserva del turista (con el
canal), en rutas/reservas.py. Ningún SQL aquí.
"""

from flask import abort, current_app, render_template, request, url_for
from flask_login import current_user

from app.modelos import reprogramacion as modelo_reprogramacion
from app.modelos import reserva as modelo_reserva
from app.rutas.panel import bp
from app.seguridad import requiere_rol
from app.servicios import formato, whatsapp

CANALES = {"web": "Web", "mostrador": "Muelle u oficina", "whatsapp": "WhatsApp"}


@bp.route("/reservas")
@requiere_rol("admin", "operador")
def reservas():
    texto = (request.args.get("q") or "").strip()[:80]
    filas = (modelo_reserva.buscar_en_panel(current_user, texto) if texto
             else modelo_reserva.recientes(current_user))
    return render_template("panel/reservas.html", filas=filas, q=texto, canales=CANALES)


def _mensaje_de_confirmacion(r):
    """El texto que el operador le manda al turista por WhatsApp (sin su documento)."""
    zarpe = r["fecha_hora_zarpe"]
    saldo = r["total"] - r["pagado"]
    if saldo <= 0:
        pago = "pagada"
    elif r["reportado"] >= saldo:
        pago = f"tu pago de {formato.soles(r['reportado'])} está por verificar"
    elif r["estado"] == "pendiente_pago":
        pago = (f"por pagar {formato.soles(saldo)} con "
                f"{formato.METODOS_PAGO.get(r['metodo_pago_elegido'])}: repórtalo en «Mi reserva» "
                f"antes de las {formato.hora(r['vence_en'])}")
    else:
        pago = f"por pagar {formato.soles(saldo)} en el muelle, antes de subir"
    base = current_app.config.get("URL_PUBLICA") or request.host_url
    return "\n".join([
        f"Hola, {r['nombres']}. Tu reserva de Titicaca Vivo:",
        f"*{r['codigo']}* · {r['ruta_nombre']}",
        f"{formato.fecha_larga(zarpe).capitalize()} · zarpe {formato.hora(zarpe)} · "
        f"{r['muelle_salida']}",
        f"Total {formato.soles(r['total'])} · {pago}",
        "Tu reserva y tu boleto (con el número de tu documento): "
        + base.rstrip("/") + url_for("reservas.mi_reserva", codigo=r["codigo"]),
        "Preséntate en el muelle 30 minutos antes del zarpe con tu documento.",
    ])


@bp.route("/reservas/<codigo>")
@requiere_rol("admin", "operador")
def reserva_detalle(codigo):
    codigo = modelo_reserva.normalizar_codigo(codigo)
    if not modelo_reserva.PATRON_CODIGO.match(codigo):
        abort(404)
    r = modelo_reserva.buscar_por_codigo(codigo)
    if r is None:
        abort(404)
    texto = _mensaje_de_confirmacion(r)
    return render_template(
        "panel/reserva.html", r=r, canales=CANALES,
        pasajeros=modelo_reserva.pasajeros(r["id"]), pagos=modelo_reserva.pagos(r["id"]),
        hospedajes=modelo_reserva.hospedajes(r["id"]),
        historial=modelo_reserva.historial(current_user, r["id"]),
        puede_reprogramar=modelo_reprogramacion.puede(r),
        texto_whatsapp=texto, enlace_whatsapp=whatsapp.enlace(texto, r["telefono"]),
    )
