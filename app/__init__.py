"""Titicaca Vivo: fábrica de la aplicación (app factory).

Capas: rutas (blueprints) → modelos (reglas + SQL) → plantillas.
"""

from flask import Flask, g, request, session, url_for

from app.config import Config


def crear_app(config_clase=Config):
    app = Flask(__name__, template_folder="plantillas", static_folder="estaticos")
    app.config.from_object(config_clase)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta SECRET_KEY en el archivo .env (ver .env.example).")

    from app import bd, comandos, errores, registro, seguridad
    from app.rutas import (
        apis,
        autenticacion,
        catalogos,
        panel,
        panel_reservas,  # noqa: F401 (registra sus rutas en el panel)
        panel_seguimiento,  # noqa: F401 (registra sus rutas en el panel)
        publico,
        reservas,
    )
    from app.servicios import formato, imagenes, textos

    registro.configurar(app)
    bd.init_app(app)
    seguridad.init_app(app)
    comandos.registrar(app)
    errores.registrar(app)
    formato.registrar(app)

    app.register_blueprint(publico.bp)
    app.register_blueprint(autenticacion.bp)
    app.register_blueprint(panel.bp)
    app.register_blueprint(reservas.bp)
    app.register_blueprint(catalogos.bp)
    app.register_blueprint(apis.bp)

    def estatico(archivo):
        # ?v=versión: al publicar una versión nueva el navegador baja el archivo otra vez
        return url_for("static", filename=archivo, v=app.config["VERSION"])

    # Globales de Jinja (y no context_processor): así también las ven los macros importados.
    app.jinja_env.globals.update(estatico=estatico, foto_comunidad=imagenes.foto_comunidad,
                                 fondo_de_pagina=imagenes.fondo_de_pagina,
                                 estado_visible=formato.estado_visible,
                                 t=textos.t, fuerte=textos.fuerte, idioma_actual=textos.idioma)

    @app.before_request
    def fijar_idioma():
        # El turista elige español o inglés (queda en su sesión); el panel queda en español (8.9).
        # «apis» responde al formulario de reserva: sus mensajes van en el idioma del turista.
        en_paginas_del_turista = request.blueprint in ("publico", "reservas", "apis", None)
        g.idioma = session.get("idioma", "es") if en_paginas_del_turista else "es"

    return app
