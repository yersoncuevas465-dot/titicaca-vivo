"""Consultas en vivo para los formularios (v2.2). Por ahora una: DNI → nombres (RENIEC).

POST con el token CSRF del formulario (así no sirve como buscador abierto de DNIs desde otros
sitios), con límite de consultas por IP, sin caché del navegador y sin registrar el DNI.
Responde JSON: {ok, nombres, apellidos} o {ok: false, error}. Un DNI que RENIEC no tiene es una
búsqueda sin resultado (200, ok: false), no un error: no ensucia la consola del navegador.
"""

from flask import Blueprint, current_app, jsonify, request

from app.seguridad import limitador
from app.servicios import externas, reniec
from app.servicios.textos import t

bp = Blueprint("apis", __name__, url_prefix="/api")


def _json(codigo, **datos):
    respuesta = jsonify(ok="error" not in datos, **datos)
    respuesta.status_code = codigo
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@bp.route("/dni", methods=["POST"])
@limitador.limit(lambda: current_app.config["LIMITE_CONSULTAS_DNI"])
def dni():
    numero = reniec.limpiar_dni(request.form.get("dni"))
    if not reniec.PATRON_DNI.match(numero):
        return _json(422, error=t("El DNI tiene 8 dígitos."))
    if not reniec.disponible():
        return _json(503, error=t("La consulta a RENIEC no está activa: escribe los nombres."))
    try:
        persona = reniec.consultar(numero)
    except externas.ApiNoDisponible:
        return _json(503, error=t("RENIEC no responde ahora: escribe los nombres."))
    if persona is None:
        return _json(200, error=t("No encontramos ese DNI en RENIEC: revisa el número o "
                                  "escribe los nombres."))
    return _json(200, **persona)
