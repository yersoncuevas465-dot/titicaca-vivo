"""Lista de pasajeros para WhatsApp: un enlace wa.me con el texto ya escrito (sin API).

La sección 17 deja fuera la API de WhatsApp Business. El enlace abre WhatsApp en el
celular del operador con el mensaje listo; la persona elige a quién enviarlo y lo envía
ella misma. El texto no lleva documentos ni teléfonos de los turistas (D-73).
"""

import re
from urllib.parse import quote

from app.servicios import formato


def texto_lista(salida, pasajeros):
    """Mensaje para el grupo de la salida: datos del viaje y pasajeros por reserva."""
    zarpe = salida["fecha_hora_zarpe"]
    lineas = [
        f"*Titicaca Vivo* · {salida['ruta_nombre']}",
        f"{formato.fecha_larga(zarpe).capitalize()} · zarpe {formato.hora(zarpe)} · "
        f"{salida['muelle_salida']}",
        f"Lancha {salida['embarcacion_nombre']} ({salida['matricula']}) · "
        f"Capitán {salida['capitan']}" + (f" · Guía {salida['guia']}" if salida["guia"] else ""),
        f"Pasajeros: {len(pasajeros)} de {salida['cupo']} lugares",
    ]
    reserva_actual = None
    for p in pasajeros:
        if p["codigo"] != reserva_actual:
            reserva_actual = p["codigo"]
            saldo = p["total"] - p["pagado"]
            pago = "pagada" if saldo <= 0 else f"falta pagar {formato.soles(saldo)}"
            if p["estado_reserva"] == "pendiente_pago":
                pago = "pago por verificar"
            lineas += ["", f"*{p['codigo']}* · {p['titular_nombres']} {p['titular_apellidos']} "
                           f"· {pago}"]
        marca = "✅" if p["abordo_en"] else "▫️"
        lineas.append(f"{marca} {p['nombres']} {p['apellidos']} ({p['tipo']})")
    return "\n".join(lineas)


def enlace(texto, telefono=None):
    """https://wa.me/<número>?text=... Sin número, WhatsApp deja elegir el contacto."""
    numero = ""
    if telefono:
        if telefono.startswith("+"):
            numero = telefono[1:]
        elif re.fullmatch(r"9\d{8}", telefono):       # celular peruano: se agrega el 51
            numero = "51" + telefono
    return f"https://wa.me/{numero}?text={quote(texto)}"
