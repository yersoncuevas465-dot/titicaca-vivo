"""RENIEC (v2.2): con el número de DNI se completan los nombres y apellidos del formulario.

API pública de graphperu: GET <RENIEC_API_URL>/<dni>. Responde, por ejemplo (datos ficticios):
    {"documentID": "12345678", "names": "ROSA ELENA", "paternalLastName": "QUISPE",
     "maternalLastName": "MAMANI", "fullName": "QUISPE MAMANI ROSA ELENA", ...}
Un DNI que no existe responde 4xx.

De aquí solo salen nombres y apellidos. Nada se guarda en la base: la reserva guarda lo que
la persona revisó y confirmó en el formulario.
"""

import re

from flask import current_app

from app.servicios import externas

PATRON_DNI = re.compile(r"^\d{8}$")
SEGUNDOS_EN_CACHE = 3600
# Partículas que van en minúscula dentro de un nombre: «María del Carmen», «De la Cruz» no.
_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e", "da", "di"}


def disponible():
    return externas.activas() and bool(current_app.config["RENIEC_API_URL"])


def limpiar_dni(texto):
    """' 41.020.304 ' → '41020304' (como se escribe a veces en el celular)."""
    return re.sub(r"[\s.\-]", "", texto or "")


def nombre_propio(texto):
    """'MARÍA DEL CARMEN' → 'María del Carmen' (RENIEC suele responder en mayúsculas)."""
    palabras = " ".join(str(texto or "").split()).lower().split(" ")
    return " ".join(p if i and p in _PARTICULAS else p[:1].upper() + p[1:]
                    for i, p in enumerate(palabras) if p)


def _persona(dni, datos):
    """Nombres y apellidos de la respuesta, o None si no trae los de ese DNI."""
    if not isinstance(datos, dict):
        raise externas.ApiNoDisponible("la respuesta no es un objeto JSON")
    if str(datos.get("documentID") or dni) != dni:
        return None
    nombres = nombre_propio(datos.get("names"))
    apellidos = nombre_propio(" ".join(filter(None, (datos.get("paternalLastName"),
                                                     datos.get("maternalLastName"))))
                              or datos.get("surnames"))
    if not nombres or not apellidos:
        return None
    return {"nombres": nombres, "apellidos": apellidos}


def consultar(dni):
    """{'nombres', 'apellidos'} del DNI, o None si RENIEC no lo tiene.

    Lanza ValueError si no son 8 dígitos y externas.ApiNoDisponible si el servicio no responde
    (eso no se guarda: se puede volver a intentar enseguida)."""
    if not PATRON_DNI.match(dni or ""):
        raise ValueError("El DNI tiene 8 dígitos.")
    clave = ("reniec", dni)
    hay, persona = externas.leer(clave)
    if hay:
        return persona
    url = current_app.config["RENIEC_API_URL"].rstrip("/") + "/" + dni
    try:
        persona = _persona(dni, externas.obtener_json(url))
    except externas.NoEncontrado:
        persona = None
    except externas.ApiNoDisponible as error:
        current_app.logger.warning("RENIEC sin respuesta: %s", error)     # sin el DNI
        raise
    externas.guardar(clave, persona, SEGUNDOS_EN_CACHE)
    return persona
