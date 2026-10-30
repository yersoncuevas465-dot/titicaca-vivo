"""Páginas de error propias: sin trazas, sin consultar la base y en español."""

from flask import current_app, render_template
from flask_wtf.csrf import CSRFError

from app import diagnostico
from app.modelos import PermisoDenegado
from app.servicios.textos import t

PAGINAS = {
    400: ("Solicitud no válida", "No pudimos procesar lo que enviaste. Vuelve a intentarlo."),
    403: ("No tienes permiso", "Tu usuario no puede ver esta página. Si crees que es un error, "
                               "habla con el administrador."),
    404: ("No encontramos la página", "La dirección no existe o ya no está disponible."),
    405: ("Acción no permitida", "Esta dirección no acepta esa acción."),
    429: ("Demasiados intentos", "Hiciste demasiados intentos seguidos. Espera unos minutos "
                                 "y vuelve a intentarlo."),
    500: ("Algo salió mal", "Tuvimos un problema al atender tu pedido. Ya quedó registrado; "
                            "vuelve a intentarlo en unos minutos."),
}


def _pagina(codigo):
    titulo, mensaje = PAGINAS[codigo]
    # En un 500 puede que la base no responda: la página no muestra el menú del usuario
    # (que necesitaría leerlo de la base) para no fallar otra vez.
    return render_template("errores/error.html", codigo=codigo, titulo=t(titulo),
                           mensaje=t(mensaje), sin_menu=(codigo == 500)), codigo


def _sin_base():
    """MySQL no responde: la página lo dice (y, fuera de producción, cómo arreglarlo)."""
    ayuda = None
    if current_app.config["ENTORNO"] != "produccion":
        ayuda = ("Para el equipo: revisa que MySQL esté encendido en XAMPP (Start en MySQL) y "
                 "recarga la página. /salud muestra si la base responde.")
    return render_template(
        "errores/error.html", codigo=500, titulo=t("No hay conexión con la base de datos"),
        mensaje=t("El sistema no puede leer sus datos en este momento. Vuelve a intentarlo en "
                  "unos minutos."),
        ayuda=ayuda, sin_menu=True), 500


def registrar(app):
    for codigo in (400, 403, 404, 405, 429):
        app.register_error_handler(codigo, lambda _error, c=codigo: _pagina(c))

    @app.errorhandler(CSRFError)
    def csrf_vencido(_error):
        titulo = t("El formulario venció")
        mensaje = t("Por seguridad, vuelve a cargar la página y envía el formulario otra vez.")
        return render_template("errores/error.html", codigo=400, titulo=titulo,
                               mensaje=mensaje), 400

    @app.errorhandler(PermisoDenegado)
    def permiso_denegado(_error):
        return _pagina(403)

    @app.errorhandler(500)
    def error_interno(error):
        original = getattr(error, "original_exception", None) or error
        app.logger.error("Error 500: %r", original, exc_info=original)
        if diagnostico.sin_servidor(original):
            return _sin_base()
        return _pagina(500)
