"""Mensajes del formulario de contacto (v2.6).

No se guardan en la base: el modelo de datos del enunciado tiene 20 tablas y ninguna es para
esto. El mensaje llega por correo a la agencia (AGENCIA_CORREO) o a los operadores activos, y
la bitácora anota que llegó uno: el asunto y el idioma, sin el texto ni los datos de la persona.
"""

import re

from app import bd
from app.modelos import ErrorValidacion, bitacora
from app.modelos.reserva import PATRON_CORREO, PATRON_NOMBRE, PATRON_TELEFONO

ASUNTOS = ("informacion", "reserva", "grupos", "otro")


def validar(datos):
    """Limpia los datos y lanza ErrorValidacion con todos los errores (como la reserva)."""
    errores = {}
    datos["nombre"] = " ".join((datos.get("nombre") or "").split())
    datos["correo"] = (datos.get("correo") or "").strip().lower() or None
    datos["telefono"] = re.sub(r"[\s\-()]", "", datos.get("telefono") or "") or None
    datos["mensaje"] = (datos.get("mensaje") or "").strip()
    if not datos["nombre"] or len(datos["nombre"]) > 80 or not PATRON_NOMBRE.match(datos["nombre"]):
        errores["nombre"] = "Escribe tu nombre con letras."
    if datos["correo"] and (len(datos["correo"]) > 120 or not PATRON_CORREO.match(datos["correo"])):
        errores["correo"] = "Escribe un correo válido, por ejemplo nombre@correo.com."
    if datos["telefono"] and not PATRON_TELEFONO.match(datos["telefono"]):
        errores["telefono"] = "Celular peruano de 9 dígitos que empieza en 9, o +código del país."
    if not datos["correo"] and not datos["telefono"]:
        errores["correo"] = "Deja un correo o un celular para responderte."
    if datos.get("asunto") not in ASUNTOS:
        errores["asunto"] = "Elige sobre qué es tu mensaje."
    if not 10 <= len(datos["mensaje"]) <= 1500:
        errores["mensaje"] = "Escribe entre 10 y 1500 caracteres."
    if errores:
        raise ErrorValidacion(errores)
    return datos


def destinatarios(correo_agencia):
    """A quién llega el mensaje: el correo de la agencia o, sin él, los operadores activos."""
    if correo_agencia:
        return [correo_agencia]
    # Devuelve el correo de cada operador activo que tiene uno (los que atienden a los turistas).
    filas = bd.consultar(
        """
        SELECT u.correo
        FROM usuario u
        JOIN rol r ON r.id = u.rol_id
        WHERE r.codigo = 'operador' AND u.activo = 1 AND u.correo IS NOT NULL
        ORDER BY u.id
        """
    )
    return [f["correo"] for f in filas]


def anotar_recibido(asunto, idioma, enviados, ip):
    """RN-14: deja en la bitácora que llegó un mensaje (sin su texto ni los datos personales)."""
    with bd.transaccion() as cur:
        bitacora.anotar(cur, None, "mensaje_contacto", None, None,
                        {"asunto": asunto, "idioma": idioma, "correos_enviados": enviados}, ip)
