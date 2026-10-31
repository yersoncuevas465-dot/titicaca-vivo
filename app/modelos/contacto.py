"""Mensajes del formulario de contacto (v2.6).

No se guardan en la base: el modelo de datos del enunciado tiene 20 tablas y ninguna es para
esto. El mensaje llega por correo a la agencia (AGENCIA_CORREO) o a los operadores activos, y
la bitácora anota que llegó uno: el asunto y el idioma, sin el texto ni los datos de la persona.
"""

import re
from datetime import date, timedelta

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


# --- Cotización para grupos (v2.8) -------------------------------------------------------------

TIPOS_GRUPO = ("colegio", "universidad", "empresa", "familia", "otro")
PERSONAS_GRUPO = (2, 300)


def validar_grupo(datos, rutas, hoy):
    """Limpia el pedido de cotización y lanza ErrorValidacion con todos los errores.

    `rutas` son las rutas activas (con su precio «desde»): la elegida tiene que estar entre ellas.
    Devuelve la ruta elegida."""
    errores = {}
    try:
        validar({"nombre": datos.get("nombre"), "correo": datos.get("correo"),
                 "telefono": datos.get("telefono"), "asunto": "grupos",
                 "mensaje": "Pedido de cotización para un grupo."})
    except ErrorValidacion as error:
        errores.update(error.errores)
    datos["nombre"] = " ".join((datos.get("nombre") or "").split())
    datos["correo"] = (datos.get("correo") or "").strip().lower() or None
    datos["telefono"] = re.sub(r"[\s\-()]", "", datos.get("telefono") or "") or None
    datos["institucion"] = " ".join((datos.get("institucion") or "").split()) or None
    datos["comentarios"] = (datos.get("comentarios") or "").strip() or None
    if datos.get("tipo") not in TIPOS_GRUPO:
        errores["tipo"] = "Elige qué tipo de grupo es."
    if datos["institucion"] and len(datos["institucion"]) > 120:
        errores["institucion"] = "Máximo 120 caracteres."
    try:
        personas = int(str(datos.get("personas") or "").strip())
    except ValueError:
        personas = None
    datos["personas"] = personas
    if personas is None or not PERSONAS_GRUPO[0] <= personas <= PERSONAS_GRUPO[1]:
        errores["personas"] = (f"Escribe cuántas personas son (de {PERSONAS_GRUPO[0]} a "
                               f"{PERSONAS_GRUPO[1]}).")
    try:
        fecha = date.fromisoformat(str(datos.get("fecha") or "").strip())
    except ValueError:
        fecha = None
    datos["fecha"] = fecha
    if fecha is None or not hoy <= fecha <= hoy + timedelta(days=366):
        errores["fecha"] = "Elige una fecha desde hoy y dentro del próximo año."
    ruta = next((r for r in rutas if r["codigo"] == datos.get("ruta")), None)
    if ruta is None:
        errores["ruta"] = "Elige una ruta de la lista."
    if datos["comentarios"] and len(datos["comentarios"]) > 1000:
        errores["comentarios"] = "Máximo 1000 caracteres."
    if errores:
        raise ErrorValidacion(errores)
    return ruta


def estimar(ruta, personas):
    """Precio referencial del grupo: personas × el precio «desde» de la ruta (o None sin tarifa)."""
    return ruta["desde"] * personas if ruta.get("desde") is not None else None


def anotar_cotizacion(datos, enviados, ip):
    """RN-14: deja en la bitácora que se pidió una cotización (sin los datos de la persona)."""
    with bd.transaccion() as cur:
        bitacora.anotar(cur, None, "cotizacion_grupo", None, None,
                        {"tipo": datos["tipo"], "personas": datos["personas"],
                         "ruta": datos["ruta"], "fecha": datos["fecha"].isoformat(),
                         "idioma": datos.get("idioma"), "correos_enviados": enviados}, ip)
