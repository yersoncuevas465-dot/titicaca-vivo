"""Práctica 13 · Titicaca Vivo en el celular: lo que Chrome pide para instalar la página como app.

- /manifest.webmanifest: nombre, colores, íconos de 192 y 512 (y uno maskable).
- /sw.js: el service worker. Va en la raíz para que su alcance sea todo el sitio (desde
  /estaticos/ solo controlaría /estaticos/). Lo de una persona va SOLO por la red.
- /sin-conexion: lo que se ve sin red en una página que no se guardó.
"""

from flask import current_app, make_response, render_template, send_from_directory

from app.rutas.publico import bp


@bp.route("/manifest.webmanifest")
def manifiesto():
    return send_from_directory(current_app.static_folder, "manifest.webmanifest",
                               mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    respuesta = make_response(render_template("sw.js"))
    respuesta.mimetype = "application/javascript"
    respuesta.headers["Cache-Control"] = "no-cache"      # cada visita revisa si hay otra versión
    respuesta.headers["Service-Worker-Allowed"] = "/"
    return respuesta


@bp.route("/sin-conexion")
def sin_conexion():
    # sin_menu: la página se guarda al instalar y no debe llevar el nombre de nadie.
    return render_template("publico/sin_conexion.html", sin_menu=True)
